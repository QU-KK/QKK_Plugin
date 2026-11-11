from __future__ import annotations

import enum
import os
import random
import re
import shutil
import sys
import subprocess
import tempfile
import time
import json
import traceback
import types
import ctypes
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

from . import mesh_read
from . import hang_watchdog
from . import derived_outputs
from . import distance_offset_queue
from . import bake_backends, bake_dependencies, cage, cage_offset_estimator, cage_session, collection_naming, constants, cycles_projection, diagnostics, dirty_rules, dirty_tracker, export, external_edit_watch, external_handoff, editor_handoff, high_mesh_cache, image_cleanup, image_inspection, indexed_geometry, map_rebuild, matching, material_detail, material_workflow, mesh_transport, metadata_sync, naming, overlays, preferences, preset_store, preview_materials, project_structure, properties, proximity_matching, protocol, quality, runtime, sidebar_state, startup_dialogs, storage_cleanup, tagging, texture_reprojection, uv_seam_optimizer, uv_snapshot, uv_transfer, validation
from . import update_policy
from . import paint_brush
from . import high_poly_park
from . import failure_guidance
from . import texture_set_guess
from .preview_sources import (
    abspath as _abspath_impl,
    image_source_label as _image_source_label_impl,
    image_source_path as _image_source_path_impl,
    refresh_source_image as _refresh_source_image_impl,
    resolve_live_normal_preview_source as _resolve_live_normal_preview_source_impl,
    resolve_map_source as _resolve_map_source_impl,
    resolve_output_target as _resolve_output_target_impl,
    resolve_pbr_preview_inputs as _resolve_pbr_preview_inputs_impl,
)
from .preview_on_low import (
    activate_live_normal_preview as _activate_live_normal_preview_impl,
    activate_preview_on_low as _activate_preview_on_low_impl,
    activate_preview_on_low_all_groups as _activate_preview_on_low_all_groups_impl,
    activate_preview_pbr_on_low as _activate_preview_pbr_on_low_impl,
    activate_preview_pbr_on_low_all_groups as _activate_preview_pbr_on_low_all_groups_impl,
    adopt_unmanaged_view3d_spaces as _adopt_unmanaged_view3d_spaces_impl,
    any_preview_on_low_is_active as _any_preview_on_low_is_active_impl,
    apply_preview_on_low_viewport_state as _apply_preview_on_low_viewport_state_impl,
    apply_runtime_preview_overlay_state as _apply_runtime_preview_overlay_state_impl,
    capture_view3d_shading_state as _capture_view3d_shading_state_impl,
    clear_preview_on_low_state as _clear_preview_on_low_state_impl,
    deactivate_preview_on_low as _deactivate_preview_on_low_impl,
    preview_on_low_project_name as _preview_on_low_project_name_impl,
    restore_preview_on_low_overlay_state as _restore_preview_on_low_overlay_state_impl,
    restore_preview_on_low_viewport_state as _restore_preview_on_low_viewport_state_impl,
    target_low_mesh_count as _target_low_mesh_count_impl,
)
from .live_normal_preview import (
    LiveNormalPreviewRuntimeState,
    cancel_live_normal_preview_runtime as _cancel_live_normal_preview_runtime_impl,
    clear_live_normal_preview_request as _clear_live_normal_preview_request_impl,
    ensure_live_normal_preview_timer_registered as _ensure_live_normal_preview_timer_registered_impl,
    find_live_normal_preview_record as _find_live_normal_preview_record_impl,
    handle_live_normal_preview_background_update as _handle_live_normal_preview_background_update_impl,
    live_normal_preview_signature as _live_normal_preview_signature_impl,
    live_normal_preview_timer_tick as _live_normal_preview_timer_tick_impl,
    request_live_normal_preview_refresh as _request_live_normal_preview_refresh_impl,
)
from .preview_lifecycle import (
    iter_loaded_scenes as _iter_loaded_scenes_impl,
    load_post as _load_post_impl,
    resolve_live_normal_preview_state as _resolve_live_normal_preview_state_impl,
    resolve_pbr_preview_state as _resolve_pbr_preview_state_impl,
    resolve_preview_material_target as _resolve_preview_material_target_impl,
    save_post as _save_post_impl,
    save_pre as _save_pre_impl,
    sync_preview_material_for_project as _sync_preview_material_for_project_impl,
)
from .preview_operator_actions import (
    execute_preview_map_output as _execute_preview_map_output_impl,
    execute_preview_pbr_output as _execute_preview_pbr_output_impl,
    execute_toggle_live_normal_preview as _execute_toggle_live_normal_preview_impl,
)
from .protocol import load_progress
from .registration import safe_register_class, safe_remove_attr, safe_unregister_class


_EXTERNAL_EDIT_WATCHER = external_edit_watch.ExternalEditWatcher()
_LIVE_NORMAL_PREVIEW_REQUESTED = False
_LIVE_NORMAL_PREVIEW_DUE_AT = 0.0
_LIVE_NORMAL_PREVIEW_REASON = ""
_LIVE_NORMAL_PREVIEW_TIMER_REGISTERED = False
_LIVE_NORMAL_PREVIEW_JOB: dict[str, object] | None = None
_LIVE_NORMAL_PREVIEW_LAST_SIGNATURE: tuple | None = None

# Dirty tracker — snapshot of what was dirty when the most recent incremental bake fired.
# Used on completion to clear exactly those entries from the dirty matrix.
_DIRTY_REBAKE_SNAPSHOT: dirty_tracker.DirtyMatrix | None = None
_DEFERRED_MATERIAL_BACKEND_RESULTS: dict[str, object] = {}
# Prepared jobs retained so a GPU→Cycles handoff can reuse the same outputs/groups
# after a background backend failure tagged with CYCLES_HANDOFF_MARKERS.
_CYCLES_HANDOFF_PREPARED: dict[str, object] = {}
_ASYNC_MATERIAL_ERRORS: dict[str, list[str]] = {}

# "Bake Missing Maps First": True while a bake fired by the export dialog is in
# flight and the export must re-run once it finishes cleanly. Only the async bake
# path uses it; the synchronous path re-exports inline (see bake_then_export).
_PENDING_EXPORT_AFTER_BAKE: bool = False

# Substance-Painter-style dependency ordering. Armed by _run_bake when a MATERIAL row
# reads a mesh map this same run writes: stage 1 bakes everything else, the referenced
# image datablocks are reloaded, then stage 2 re-runs _run_bake for the dependent rows
# alone -- which re-captures the material texel payload from the fresh pixels. Holds the
# stage-2 request while stage 1 is in flight; a single slot, because _run_bake refuses to
# start while another bake is running.
# FIFO of staged bake phases that run after the current bake lands cleanly. Two kinds:
# "dependency" (the Substance-Painter-style stage 2: material rows reading maps this run
# writes) and "per_group" (F8: a MATERIAL row whose only blocker was the multi-group
# MATSLOT sidecar bakes natively once per group). Each completed bake pops one entry;
# any failure or cancel drops the whole queue.
_PENDING_MATERIAL_PHASES: list[dict] = []
# Snapshot of the texture-set files a per-group native material pass is about to
# overwrite, plus that group's UV mask. Consumed once the pass lands: the group's
# own texels are composited back over the snapshot, so groups sharing one file do
# not erase each other. Empty for the first group (its pass IS the fresh base).
_PER_GROUP_MERGE_STATE: dict | None = None
# Set while a staged phase is being dispatched so _run_bake cannot re-plan (and re-split)
# the very rows it was handed. A staged phase never contains a mesh map, so the planner
# would return a no-op anyway; this makes that guarantee structural rather than incidental.
_MATERIAL_PHASE_TWO_ACTIVE: bool = False


def _clear_pending_material_phase() -> None:
    _PENDING_MATERIAL_PHASES.clear()


def _handle_async_material_complete(workspace_path, errors) -> None:
    workspace_key = str(Path(workspace_path))
    _ASYNC_MATERIAL_ERRORS[workspace_key] = list(errors or [])
    # Entries are popped only by the matching finished result; a job that failed
    # at launch or whose project vanished never pops, so bound the dict or the
    # stale warnings ride on any later bake that reuses the workspace path.
    while len(_ASYNC_MATERIAL_ERRORS) > 8:
        _ASYNC_MATERIAL_ERRORS.pop(next(iter(_ASYNC_MATERIAL_ERRORS)))
    deferred = _DEFERRED_MATERIAL_BACKEND_RESULTS.pop(workspace_key, None)
    if deferred is not None:
        _handle_background_bake_update(deferred)


def _handle_async_material_progress(status) -> None:
    """Mirror the Cycles material queue into the project's live status surfaces.

    The backend can finish long before this queue does, so without its own status
    the panel falls back to the previous run's readout and looks idle while Blender
    is still baking.
    """
    scene, settings, project = _find_project_record_by_job_id(getattr(status, "job_id", ""))
    if project is None:
        return
    label = status.label
    channel = str(getattr(status, "channel", "") or "")
    if channel:
        label = f"{label}: {channel.title()}"
    try:
        project.last_status_message = label
        if settings is not None:
            settings.status_message = label
    except Exception:
        return
    try:
        overlays.tag_redraw_all_view3d(scene=scene)
    except Exception:
        pass
    _poke_statusbar_redraw()

# Pending duplicate-output resolution: populated by bake operators when they detect
# that two or more enabled maps would write to the same output file.  Consumed by
# MASTER_BAKER_OT_handle_duplicate_map_outputs, which renames the offenders and
# re-invokes the original bake operator.
_PENDING_BAKE_STATE: dict = {}

# Bake low-impact viewport mode (L1 region-scoped progress redraw + L2 overlay-handler
# suspend). Snapshot is taken on bake START (operator context available) and consumed
# exactly once on bake END (poll finished-branch, which runs from a bpy.app.timer with
# NO operator context). No per-space snapshot is required for L1/L2: L1 mutates nothing
# (it only changes which regions the poll path tags), and L2 removes/re-adds the two
# class-wide SpaceView3D overlay draw handlers, so it is multi-window/multi-viewport
# correct by construction (one handler pair covers every viewport).
_LOW_IMPACT_STATE: dict = {
    "active": False,            # True while a low-impact bake is engaged (drives the L1 poll path)
    "overlays_suspended": False,  # True if L2 removed our overlay draw handlers (drives resume)
}

_MISSING_UV_ERROR_CODES = {
    "group.low_mesh.missing_uvs",
    "group.low_mesh.uv_layer_missing",
}

# Background-prepare debounce: True while a 1s timer is pending after a depsgraph change.
# Prevents stacking multiple timers when the user makes rapid changes.
_BG_PREPARE_DEBOUNCE_REGISTERED: bool = False

# Background-prepare self-trigger guard: monotonic timestamp until which the
# always-on depsgraph handler ignores updates.  A speculative PREPARE runs a full
# job export (object/cage create+remove, mesh evaluation, scene property writes),
# all of which emit their own depsgraph_update_post on the next evaluation cycle.
# Without this guard the handler mistakes the addon's own mutations for user edits
# and re-arms another PREPARE forever — a loop that runs heavy job prep on the main
# thread every cycle and makes Blender unusable (e.g. after a script reload).
_BG_PREPARE_SUPPRESS_UNTIL: float = 0.0
# True while the per-tick high-mesh warm chain owns the status-bar text
# ("Setting up bake project — preparing <mesh> (n/m)…"); cleared when the
# chain hands off to the actual export.
_HIGH_WARM_STATUS_ACTIVE: bool = False
# Name of the mesh whose warm-up was announced in the status bar last tick;
# the following tick performs the capture (announce/work alternation so the
# label is painted before the block, not after it).
_HIGH_WARM_ANNOUNCED: str | None = None
# High meshes whose warm export failed in this file (name -> error). The warm chain
# re-picked the first cold mesh every tick, so one that could not be exported was
# retried forever (2026-09-28: SvAT's 41.4M-triangle high, each attempt a multi-GB
# export). A failed mesh is skipped until the next file load; the bake itself still
# exports it and reports the error.
_HIGH_WARM_FAILED: dict[str, str] = {}
# Set once a warm export ran out of memory: warming anything else would only dig
# deeper, so the chain stops until the next file load.
_HIGH_WARM_OUT_OF_MEMORY: bool = False
# Grace window (seconds) covering the deferred depsgraph flush that follows a
# speculative prepare.  Long enough to outlast the post-call evaluation tick,
# short enough that a genuine user edit shortly after is still detected.
_BG_PREPARE_SELF_SUPPRESS_SECONDS: float = 2.0
# Last observed mesh topology signatures (vertex/polygon counts) keyed by mesh
# as_pointer(), used to ignore material-slot depsgraph false positives.
_BG_PREPARE_MESH_TOPO: dict[int, tuple[int, int]] = {}


def _cancel_pending_bg_prepare() -> None:
    """Drop a queued speculative-prepare debounce timer, if any."""
    global _BG_PREPARE_DEBOUNCE_REGISTERED
    _BG_PREPARE_DEBOUNCE_REGISTERED = False
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        return
    try:
        if hasattr(timers, "is_registered") and timers.is_registered(_bg_prepare_debounce_fired):
            timers.unregister(_bg_prepare_debounce_fired)
    except Exception:
        pass


def _suppress_bg_prepare(seconds: float = _BG_PREPARE_SELF_SUPPRESS_SECONDS) -> None:
    """Ignore self-induced depsgraph updates in the background-prepare handler."""
    global _BG_PREPARE_SUPPRESS_UNTIL
    _BG_PREPARE_SUPPRESS_UNTIL = max(_BG_PREPARE_SUPPRESS_UNTIL, time.monotonic() + max(0.0, seconds))
    _cancel_pending_bg_prepare()


def _mesh_topo_signature(mesh) -> tuple[int, int] | None:
    try:
        return (len(mesh.vertices), len(mesh.polygons))
    except Exception:
        return None


def _depsgraph_has_bake_relevant_mesh_edit(depsgraph) -> bool:
    """Return True only for edits that should invalidate the prepared-group cache.

    Material slot reassignment (show-on-low, PBR preview, etc.) often tags the
    Object with is_updated_geometry/transform even though mesh topology did not
    change. Treating those as bake-relevant armed the 1s speculative PREPARE and
    froze Blender for seconds while re-exporting multi-million-triangle highs.
    """
    materialish = False
    mesh_topo_changed = False
    object_geometry = False
    object_xform = False

    for update in getattr(depsgraph, "updates", ()) or ():
        id_data = getattr(update, "id", None)
        if id_data is None:
            continue
        if isinstance(id_data, bpy.types.Material):
            materialish = True
            continue
        shader_node_tree_type = getattr(bpy.types, "ShaderNodeTree", None)
        if shader_node_tree_type is not None and isinstance(id_data, shader_node_tree_type):
            materialish = True
            continue
        mesh_type = getattr(bpy.types, "Mesh", None)
        if mesh_type is not None and isinstance(id_data, mesh_type):
            sig = _mesh_topo_signature(id_data)
            if sig is not None:
                try:
                    key = int(id_data.as_pointer())
                except Exception:
                    key = 0
                if key:
                    prev = _BG_PREPARE_MESH_TOPO.get(key)
                    _BG_PREPARE_MESH_TOPO[key] = sig
                    if prev is not None and prev != sig:
                        mesh_topo_changed = True
            continue
        if isinstance(id_data, bpy.types.Object) and getattr(id_data, "type", "") == "MESH":
            if bool(getattr(update, "is_updated_transform", False)):
                object_xform = True
            if bool(getattr(update, "is_updated_geometry", False)):
                object_geometry = True

    if mesh_topo_changed:
        return True
    if materialish:
        return False
    return bool(object_geometry or object_xform)


def _live_normal_preview_runtime_state_from_globals() -> LiveNormalPreviewRuntimeState:
    return LiveNormalPreviewRuntimeState(
        requested=_LIVE_NORMAL_PREVIEW_REQUESTED,
        due_at=_LIVE_NORMAL_PREVIEW_DUE_AT,
        reason=_LIVE_NORMAL_PREVIEW_REASON,
        timer_registered=_LIVE_NORMAL_PREVIEW_TIMER_REGISTERED,
        job=_LIVE_NORMAL_PREVIEW_JOB,
        last_signature=_LIVE_NORMAL_PREVIEW_LAST_SIGNATURE,
    )


def _sync_live_normal_preview_runtime_state(state: LiveNormalPreviewRuntimeState) -> None:
    global _LIVE_NORMAL_PREVIEW_REQUESTED, _LIVE_NORMAL_PREVIEW_DUE_AT, _LIVE_NORMAL_PREVIEW_REASON
    global _LIVE_NORMAL_PREVIEW_TIMER_REGISTERED, _LIVE_NORMAL_PREVIEW_JOB, _LIVE_NORMAL_PREVIEW_LAST_SIGNATURE
    _LIVE_NORMAL_PREVIEW_REQUESTED = state.requested
    _LIVE_NORMAL_PREVIEW_DUE_AT = state.due_at
    _LIVE_NORMAL_PREVIEW_REASON = state.reason
    _LIVE_NORMAL_PREVIEW_TIMER_REGISTERED = state.timer_registered
    _LIVE_NORMAL_PREVIEW_JOB = state.job
    _LIVE_NORMAL_PREVIEW_LAST_SIGNATURE = state.last_signature


_next_available_label = project_structure.next_available_label
_create_default_project = project_structure.create_default_project
_ensure_active_project = project_structure.ensure_active_project
_ensure_active_group = project_structure.ensure_active_group
_collection_exists = project_structure.collection_exists
_has_child_collection = project_structure.has_child_collection
_ensure_project_collection_scaffold = project_structure.ensure_project_collection_scaffold
_ensure_group_collection_scaffold = project_structure.ensure_group_collection_scaffold
_copy_project = project_structure.copy_project
_add_unique_role_objects = project_structure.add_unique_role_objects
_discard_role_objects = project_structure.discard_role_objects
_remove_group_role_slot = project_structure.remove_group_role_slot
_link_objects_to_group_role_collection = project_structure.link_objects_to_group_role_collection
_unlink_object_from_group_role_collection = project_structure.unlink_object_from_group_role_collection
_group_object_set = project_structure.group_object_set
_group_role_targets = project_structure.group_role_targets
_normalize_group_name = project_structure.normalize_group_name
_primary_collection_for_object = project_structure.primary_collection_for_object
_role_from_object_and_collection = project_structure.role_from_object_and_collection
_ensure_group_slot = project_structure.ensure_group_slot
_get_or_create_group = project_structure.get_or_create_group
_get_or_create_group_with_flag = project_structure.get_or_create_group_with_flag
_group_index = project_structure.group_index
_remove_project_collections = project_structure.remove_project_collections
_remove_group_collections = project_structure.remove_group_collections


def _active_project_or_report(operator, context):
    project = properties.get_active_project(context.scene)
    if project is None:
        operator.report({"ERROR"}, "Create a Bake Project first")
        return None
    return project


def _iter_scene_project_records():
    for scene in getattr(bpy.data, "scenes", []):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []):
            yield scene, settings, project


def _find_project_record_by_job_id(job_id: str):
    """Resolve the project that owns *job_id*.

    Matches the bake-only id as well as `last_job_id`, because `last_job_id` is
    stamped by every `prepare_bake_job` call — including the speculative background
    one. A prepare landing while a bake was still running used to orphan it: the
    progress and completion callbacks all resolve the project through here, so they
    silently returned and the run went dark while Blender kept working.
    """
    target_job_id = str(job_id or "").strip()
    if not target_job_id:
        return None, None, None
    for scene, settings, project in _iter_scene_project_records():
        for attribute in ("last_bake_job_id", "last_job_id"):
            if str(getattr(project, attribute, "") or "").strip() == target_job_id:
                return scene, settings, project
    return None, None, None


def _project_runtime_name(project) -> str:
    return str(getattr(project, "name", "") or "").strip()


def _project_index(settings, target_project) -> int:
    for index, project in enumerate(getattr(settings, "projects", [])):
        # `==` compares the RNA pointer; `is` is never true for a CollectionProperty
        # element, which made this return -1 for every project.
        if project == target_project:
            return index
    return -1


def _preview_session_state(settings):
    if settings is None:
        return None
    return properties.preview_session_state(settings)


def _overlay_settings_state(settings):
    if settings is None:
        return None
    return properties.overlay_settings_state(settings)


def _group_role_assignments_state(group):
    if group is None:
        return None
    return properties.group_role_assignments_state(group)


def _clear_live_bake_state(settings) -> None:
    if settings is None:
        return
    session_state = _preview_session_state(settings)
    session_state.live_bake_active = False
    session_state.live_bake_project_name = ""
    session_state.live_bake_project_index = -1


def _resolve_live_bake_project(scene):
    settings = getattr(scene, "fyr_baker_settings", None)
    session_state = _preview_session_state(settings)
    if session_state is None or not bool(getattr(session_state, "live_bake_active", False)):
        return None

    projects = getattr(settings, "projects", [])
    project_index = int(getattr(session_state, "live_bake_project_index", -1))
    if 0 <= project_index < len(projects):
        project = projects[project_index]
        session_state.live_bake_project_name = _project_runtime_name(project)
        return project

    target_name = str(getattr(session_state, "live_bake_project_name", "") or "").strip()
    if not target_name:
        _clear_live_bake_state(settings)
        return None

    for index, project in enumerate(projects):
        if _project_runtime_name(project) != target_name:
            continue
        session_state.live_bake_project_index = index
        session_state.live_bake_project_name = _project_runtime_name(project)
        return project

    _clear_live_bake_state(settings)
    return None


def _live_bake_is_active(settings, project) -> bool:
    session_state = _preview_session_state(settings)
    if session_state is None or project is None or not bool(getattr(session_state, "live_bake_active", False)):
        return False

    target_name = str(getattr(session_state, "live_bake_project_name", "") or "").strip()
    if target_name and target_name == _project_runtime_name(project):
        return True

    project_index = int(getattr(session_state, "live_bake_project_index", -1))
    projects = getattr(settings, "projects", [])
    return 0 <= project_index < len(projects) and projects[project_index] == project


def _activate_live_bake(scene, project) -> None:
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None or project is None:
        return
    session_state = _preview_session_state(settings)
    session_state.live_bake_active = True
    session_state.live_bake_project_name = _project_runtime_name(project)
    session_state.live_bake_project_index = _project_index(settings, project)
    _start_dirty_tracker_session(project)


def _deactivate_live_bake(scene) -> None:
    settings = getattr(scene, "fyr_baker_settings", None)
    _clear_live_bake_state(settings)
    _stop_dirty_tracker_session()


def _sync_live_bake_runtime(scene):
    settings = getattr(scene, "fyr_baker_settings", None)
    session_state = _preview_session_state(settings)
    if session_state is None or not bool(getattr(session_state, "live_bake_active", False)):
        _clear_live_bake_state(settings)
        _stop_dirty_tracker_session()
        return None

    project = _resolve_live_bake_project(scene)
    if project is None:
        _stop_dirty_tracker_session()
        return None

    if not dirty_tracker.is_session_active():
        _start_dirty_tracker_session(project)
    return project


def _active_group_or_report(operator, project):
    group = properties.get_active_group(project)
    if group is None:
        operator.report({"ERROR"}, "Create a bake group first")
        return None
    return group


def _cage_target_project_group_or_report(operator, context):
    project = _active_project_or_report(operator, context)
    if project is None:
        return None, None
    group = _active_group_or_report(operator, project)
    if group is None:
        return None, None
    return project, group


def _project_preset_folder_label() -> str:
    """The directory a save will write into, WITHOUT creating it.

    ``draw`` runs on every redraw of the dialog, and ensure_preset_dir() creates
    directories; showing a path is not a reason to make one.
    """
    directory = preset_store.user_preset_dir()
    if directory is None:
        directory = preset_store.builtin_preset_dir()
    return str(directory)


def _scene_object_lookup(scene):
    objects = getattr(scene, "objects", None)
    if objects is None:
        return lambda _name: None
    return objects.get if hasattr(objects, "get") else lambda _name: None


def _append_unique_objects(target_collection, selected_objects):
    existing_ids = {slot.object_ref.as_pointer() for slot in target_collection if slot.object_ref is not None}
    added = 0
    for obj in selected_objects:
        if obj.type != "MESH":
            continue
        pointer = obj.as_pointer()
        if pointer in existing_ids:
            continue
        item = target_collection.add()
        item.object_ref = obj
        existing_ids.add(pointer)
        added += 1
    return added


def _remove_indexed_slot(target_collection, active_index_attr, owner):
    if not target_collection:
        return None
    index = getattr(owner, active_index_attr, 0)
    removed_object = None
    if 0 <= index < len(target_collection):
        removed_object = getattr(target_collection[index], "object_ref", None)
        target_collection.remove(index)
    setattr(owner, active_index_attr, min(max(index - 1, 0), max(len(target_collection) - 1, 0)))
    return removed_object


def _deselect_all_in_view_layer(context) -> None:
    view_layer_objects = getattr(getattr(context, "view_layer", None), "objects", None)
    try:
        objects = list(view_layer_objects or ())
    except TypeError:
        return
    for obj in objects:
        try:
            obj.select_set(False)
        except Exception:
            pass


def _select_objects_in_view_layer(context, targets, *, active_object=None) -> bool:
    objects = [obj for obj in targets if obj is not None]
    if not objects:
        return False

    view_layer_objects = getattr(getattr(context, "view_layer", None), "objects", None)
    # Deselect without bpy.ops.object.select_all, which only polls in Object mode —
    # the group/role select buttons would otherwise raise an uncaught error when the
    # user is in a non-Object mode (e.g. Texture Paint, entered via the paint-offset
    # and paint-skew cage tools).
    if view_layer_objects is not None:
        try:
            existing = list(view_layer_objects)
        except TypeError:
            existing = []
        for obj in existing:
            try:
                obj.select_set(False)
            except Exception:
                pass
    for obj in objects:
        try:
            obj.select_set(True)
        except Exception:
            pass

    target_active = active_object if active_object is not None else objects[0]
    if view_layer_objects is not None:
        try:
            view_layer_objects.active = target_active
        except Exception:
            pass
    return True


def _selected_objects(context):
    return [obj for obj in getattr(context, "selected_objects", []) if obj is not None]


def _selected_mesh_objects(context):
    return [obj for obj in _selected_objects(context) if getattr(obj, "type", None) == "MESH"]


def _scene_mesh_objects(context):
    """Every mesh object visible in the current view layer.

    The name matcher (`collect_role_matches`) ignores meshes without a role suffix,
    so scanning the whole scene only picks up LP/HP, Low/High, and Cage meshes — no
    manual selection needed for the setup auto-build flow.
    """
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", None) if view_layer is not None else None
    if objects is None:
        scene = getattr(context, "scene", None)
        objects = getattr(scene, "objects", None) or []
    return [obj for obj in objects if getattr(obj, "type", None) == "MESH"]


def _hidden_collection_names(context) -> set[str]:
    """Collections whose eye or monitor toggle is off, directly or through a parent."""
    hidden: set[str] = set()
    view_layer = getattr(context, "view_layer", None)
    root = getattr(view_layer, "layer_collection", None)
    if root is None:
        return hidden

    def _walk(layer_collection, parent_hidden: bool) -> None:
        collection = getattr(layer_collection, "collection", None)
        is_hidden = parent_hidden or bool(
            getattr(layer_collection, "exclude", False)
            or getattr(layer_collection, "hide_viewport", False)
            or getattr(collection, "hide_viewport", False)
        )
        if is_hidden and collection is not None:
            hidden.add(str(getattr(collection, "name", "") or ""))
        for child in getattr(layer_collection, "children", ()) or ():
            _walk(child, is_hidden)

    for child in getattr(root, "children", ()) or ():
        _walk(child, False)
    return hidden


_BLENDER_DUPLICATE_SUFFIX_RE = re.compile(r"\.\d{3,}$")


def _name_build_mesh_objects(context):
    """The meshes Auto-Build from Names groups.

    A customer's spare copies (``Box_low.001``) parked in a hidden collection were
    pulled into their groups (2026-10-27), so a Blender ``.001`` duplicate is left out
    when it lives only in hidden collections. Hidden collections are not
    skipped wholesale: the same customer keeps every high poly in a hidden ``high``
    collection, the way Painter and Marmoset users work. With meshes selected, the
    build is limited to the selection plus the name partners it needs (a hidden high
    cannot be selected), the way Auto Setup already scopes itself.
    """
    hidden = _hidden_collection_names(context)

    def _shown(obj) -> bool:
        names = [str(getattr(c, "name", "") or "") for c in (getattr(obj, "users_collection", ()) or ())]
        return not names or any(name not in hidden for name in names)

    meshes = _scene_mesh_objects(context)
    pool = [obj for obj in meshes if _shown(obj) or not _BLENDER_DUPLICATE_SUFFIX_RE.search(obj.name)]
    selected = [obj for obj in _selected_mesh_objects(context) if matching.detect_role(obj.name)]
    if not selected:
        return pool, "scene"
    # The exact part only: the prefix key ("Cube") pulled Cube_low / Cube_high in with a
    # selected Cube_009_low, adding a group nobody selected.
    keys = {matching.part_key_for_name(obj.name) for obj in selected}
    chosen = {obj.name for obj in selected}
    partners = [
        obj
        for obj in pool
        if obj.name not in chosen
        and matching.detect_role(obj.name)
        and matching.part_key_for_name(obj.name) in keys
    ]
    return list(selected) + partners, "selected"


def _scene_object_getter(scene):
    scene_objects = getattr(scene, "objects", None)
    get_object = getattr(scene_objects, "get", None)
    if callable(get_object):
        return get_object

    object_lookup = {getattr(obj, "name", ""): obj for obj in (scene_objects or [])}
    return object_lookup.get


def _group_role_objects(group, role: str) -> list:
    """Every object currently assigned to ``group`` in ``role``."""
    collections, _index_attr, _role_state = project_structure.group_role_slot_collections(group, role)
    objects = []
    for collection in collections:
        for slot in collection:
            obj = getattr(slot, "object_ref", None)
            if obj is not None and not any(existing is obj for existing in objects):
                objects.append(obj)
    return objects


def _group_tagged_objects(group) -> list:
    """Every object a group claims: both mesh lists plus a custom cage."""
    objects = _group_role_objects(group, constants.OBJECT_ROLE_LOW)
    for obj in _group_role_objects(group, constants.OBJECT_ROLE_HIGH):
        if not any(existing is obj for existing in objects):
            objects.append(obj)
    cage = getattr(group, "custom_cage", None)
    if cage is not None and not any(existing is cage for existing in objects):
        objects.append(cage)
    return objects


def _objects_owned_by_groups(groups) -> list:
    objects = []
    for group in groups or ():
        if group is None:
            continue
        for obj in _group_tagged_objects(group):
            if not any(existing is obj for existing in objects):
                objects.append(obj)
    return objects


def _objects_owned_by_live_groups(context, *, exclude=()) -> list:
    """Every object still claimed by a bake group in ANY project of this scene."""
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    excluded = [group for group in (exclude or ()) if group is not None]
    live = []
    for project in getattr(settings, "projects", []) or []:
        for group in getattr(project, "groups", []) or []:
            # `==` compares the RNA pointer; `is` never matches a CollectionProperty
            # element, so the caller's exclusion list was silently ignored.
            if any(group == item for item in excluded):
                continue
            for obj in _group_tagged_objects(group):
                if not any(existing is obj for existing in live):
                    live.append(obj)
    return live


def _role_tag_snapshot(objects) -> dict:
    """Capture the role tags of ``objects``, keyed by object name."""
    snapshot: dict = {}
    for obj in objects or ():
        name = str(getattr(obj, "name", "") or "")
        if not name:
            continue
        tag = tagging.read_role_tag(obj)
        if tag:
            snapshot[name] = dict(tag)
    return snapshot


def _clear_stale_role_tags(context, groups) -> None:
    """Strip the role tags of the objects ``groups`` owned, before they are removed.

    Removal used to leave the tags behind, and a stale tag is not inert. It says the
    mesh belongs to a bake group that no longer exists, and _preppable refuses any
    object whose tag source is not "suffix" -- so after removing a group its meshes
    could never be auto-renamed again ("No unlabeled meshes to prep"), and
    project_structure.resolve_role kept answering with the dead group's role.

    An object still claimed by a LIVE group keeps its tag: a high-poly shared between
    two groups is only stale for the one that went away.
    """
    targets = _objects_owned_by_groups(groups)
    if not targets:
        return
    still_owned = _objects_owned_by_live_groups(context, exclude=groups)
    for obj in targets:
        if any(obj is kept for kept in still_owned):
            continue
        try:
            tagging.clear_role_tag(obj)
        except Exception:
            pass


def _reapply_role_tag_snapshot(context, snapshot) -> None:
    """Replay the tags _clear_stale_role_tags stripped, so Undo Remove is exact.

    Only untagged objects are written: something that has been re-tagged since the
    removal (added to another group, re-prepped) owns its tag now, and clobbering it
    with the stale one would undo more than the removal.
    """
    if not snapshot:
        return
    lookup = _scene_object_lookup(getattr(context, "scene", None))
    for name, tag in dict(snapshot).items():
        try:
            obj = lookup(str(name))
        except Exception:
            obj = None
        if obj is None or tagging.is_tagged(obj):
            continue
        try:
            tagging.restore_role_tag(obj, tag)
        except Exception:
            pass


def _opposite_role(role: str) -> str:
    if role == constants.OBJECT_ROLE_LOW:
        return constants.OBJECT_ROLE_HIGH
    return constants.OBJECT_ROLE_LOW


def _reject_meshes_already_in_opposite_role(group, role: str, meshes) -> tuple[list, list[str]]:
    """Split ``meshes`` into (assignable, rejected names) against the other role.

    A mesh in both Low and High is a hard validation error ("Low and High
    assignments contain the same mesh"), and the way testers reach it is by
    selecting a low AND its high, then pressing the per-role add button on both
    lists in turn -- each press does exactly what it says, and the group ends up
    with the same two meshes in both roles. Assigning by hand stays unfiltered
    otherwise; this only refuses the one combination that cannot bake.

    Groups that deliberately bake a mesh against itself say so with
    ``use_low_as_high``, which routes around the role lists entirely.
    """
    if properties.group_uses_low_as_high(group):
        return list(meshes), []
    opposite = _group_role_objects(group, _opposite_role(role))
    if not opposite:
        return list(meshes), []
    assignable = []
    rejected: list[str] = []
    for obj in meshes:
        if any(existing is obj for existing in opposite):
            rejected.append(str(getattr(obj, "name", "") or ""))
        else:
            assignable.append(obj)
    return assignable, rejected


def _split_meshes_by_detected_role(meshes) -> tuple[dict[str, list], list[str]]:
    """Bucket meshes by the role their own name declares; return (buckets, unsuffixed)."""
    buckets: dict[str, list] = {
        constants.OBJECT_ROLE_LOW: [],
        constants.OBJECT_ROLE_HIGH: [],
    }
    unsuffixed: list[str] = []
    for obj in meshes:
        name = str(getattr(obj, "name", "") or "")
        role = matching.detect_role(name)
        if role in buckets:
            buckets[role].append(obj)
        else:
            unsuffixed.append(name)
    return buckets, unsuffixed


def _warn_on_role_suffix_mismatch(operator, group, role: str, meshes) -> None:
    """Flag a manual assignment that contradicts the mesh's own name.

    Assigning by hand stays unfiltered — picking the slot IS the artist's decision,
    and plenty of production meshes carry no suffix at all. But a mesh whose name
    says it belongs somewhere else is almost always a misclick, and staying silent
    about it is how a group quietly ends up holding another group's geometry.
    """
    group_name = str(getattr(group, "name", "") or "")
    group_key = matching.group_key_for_name(group_name)
    mismatched: list[str] = []
    for obj in meshes:
        name = str(getattr(obj, "name", "") or "")
        detected_role = matching.detect_role(name)
        if detected_role is None:
            continue  # unsuffixed is a legitimate manual assignment, not a mistake
        detected_group = matching.group_key_for_name(matching.strip_role_suffix(name))
        if detected_role == role and detected_group == group_key:
            continue
        mismatched.append(name)
    if not mismatched:
        return
    shown = ", ".join(mismatched[:3])
    if len(mismatched) > 3:
        shown += f", +{len(mismatched) - 3} more"
    operator.report(
        {"WARNING"},
        f"{len(mismatched)} mesh(es) assigned against their name suffix "
        f"(now {role.title()} in '{group_name}'): {shown}",
    )


def _group_selected_meshes_by_suffix(operator, context, *, status_message: str) -> bool:
    return _group_meshes_by_suffix(
        operator,
        context,
        _selected_mesh_objects(context),
        status_message=status_message,
        no_match_error=(
            "No selected meshes have _low/_high (LP/HP) suffixes. "
            "Use Add as Low / Add as High to assign them without renaming"
        ),
    )


from . import low_material_subset  # noqa: E402


def _group_primary_material_name(group) -> str:
    """The group's own material, else the first found on its low meshes ("" if none)."""
    restricted = getattr(group, "low_material", None)
    if restricted is not None and getattr(restricted, "name", ""):
        return str(restricted.name)
    role_state = properties.group_role_assignments_state(group)
    # A slot no face uses is not a texturing decision, so it does not name the set.
    for slot in getattr(role_state, "low_meshes", []):
        obj = getattr(slot, "object_ref", None)
        used = low_material_subset.used_materials(obj) if obj is not None else []
        if used:
            return str(used[0].name)
    for slot in getattr(role_state, "low_meshes", []):
        obj = getattr(slot, "object_ref", None)
        for mat_slot in getattr(obj, "material_slots", []) or []:
            mat = getattr(mat_slot, "material", None)
            if mat is not None and getattr(mat, "name", ""):
                return str(mat.name)
    return ""


def _group_low_objects(group) -> list:
    role_state = properties.group_role_assignments_state(group)
    return [
        obj
        for obj in (getattr(slot, "object_ref", None) for slot in getattr(role_state, "low_meshes", []))
        if obj is not None and getattr(obj, "type", "") == "MESH"
    ]


def _low_uv_triangles(obj):
    """[T, 3, 2] UVs of a low mesh's triangles on its active UV map (None without one)."""
    import numpy as np

    mesh = getattr(obj, "data", None)
    uv_layer = getattr(getattr(mesh, "uv_layers", None), "active", None)
    if mesh is None or uv_layer is None:
        return None
    mesh.calc_loop_triangles()
    triangle_count = len(mesh.loop_triangles)
    if triangle_count == 0:
        return np.empty((0, 3, 2), dtype=np.float64)
    loops = np.empty(triangle_count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", loops)
    uvs = np.empty(len(uv_layer.data) * 2, dtype=np.float32)
    uv_layer.data.foreach_get("uv", uvs)
    return uvs.reshape(-1, 2)[loops].reshape(-1, 3, 2).astype(np.float64)


def _group_has_placeholder_material(group, material_name: str) -> bool:
    """Every low mesh's material is just named after that mesh (ZBrush GoZ / GoB)."""
    lows = _group_low_objects(group)
    if not lows or not material_name:
        return False
    for obj in lows:
        names = [str(getattr(obj, "name", "") or ""), str(getattr(getattr(obj, "data", None), "name", "") or "")]
        materials = [
            str(getattr(getattr(slot, "material", None), "name", "") or "")
            for slot in getattr(obj, "material_slots", []) or []
            if getattr(slot, "material", None) is not None
        ]
        if not materials or not all(texture_set_guess.is_placeholder_material(name, names) for name in materials):
            return False
    return True


def _apply_auto_texture_set_mode(project, groups, mode: str) -> list[str]:
    """Re-assign the touched groups' texture-set links per the auto-build mode.

    PER_GROUP keeps the per-group name assigned at creation; COMBINED points every
    group at one shared set (the project name); PER_MATERIAL keys the set off each
    group's low-mesh material (groups without one share the project-name set).
    Returns the groups whose placeholder material could share the project set; they
    keep their own sets here, and the setup asks the artist whether to combine them.
    """
    if mode == constants.AUTO_TEXTURE_SET_COMBINED:
        shared = (getattr(project, "name", "") or "").strip() or "TextureSet"
        for group in groups:
            group.texture_set_name = shared
    elif mode == constants.AUTO_TEXTURE_SET_PER_MATERIAL:
        # Painter's model: one texture set per material. Lows without a material share
        # one set instead of each baking into its own images.
        shared = (getattr(project, "name", "") or "").strip() or "TextureSet"
        materials = {id(group): _group_primary_material_name(group) for group in groups}
        # A material named after its own mesh is usually a sculpt-app placeholder (ZBrush
        # GoZ / GoB gives every mesh one), not a texturing decision. Those groups are
        # candidates for the shared set when their UVs can share one texture; overlapping
        # layouts need the separate sets they already get, so no question is asked.
        placeholders = [
            group for group in groups if _group_has_placeholder_material(group, materials[id(group)])
        ]
        joining = placeholders + [group for group in groups if not materials[id(group)]]
        if len(joining) < 2:
            # One mesh alone gains nothing from the shared set; keep its own name.
            placeholders = []
        if placeholders:
            layouts = []
            for group in joining:
                for obj in _group_low_objects(group):
                    tri_uvs = _low_uv_triangles(obj)
                    if tri_uvs is not None:
                        layouts.append(tri_uvs)
            if texture_set_guess.uv_layouts_overlap(layouts):
                placeholders = []
        for group in groups:
            group.texture_set_name = materials[id(group)] or shared
        return [str(getattr(group, "name", "") or "") for group in placeholders]
    return []


def _ask_to_combine_placeholder_sets(group_names) -> None:
    """Ask, once the setup has finished, whether placeholder sets should be combined.

    Deferred to a timer so the dialog opens after the setup operator returns rather
    than inside it. Headless runs have nobody to ask and keep the separate sets.
    """
    if bpy.app.background or not group_names:
        return
    names = "\n".join(str(name) for name in group_names)

    def _open():
        try:
            window_manager = bpy.context.window_manager
            window = next(iter(window_manager.windows), None)
            if window is None:
                return None
            with bpy.context.temp_override(window=window, screen=window.screen):
                bpy.ops.master_baker.combine_placeholder_texture_sets("INVOKE_DEFAULT", group_names=names)
        except Exception as exc:  # noqa: BLE001 - a timer callback must never raise
            print(f"[Fyr Baker] Could not ask about combining texture sets: {exc}")
        return None

    bpy.app.timers.register(_open, first_interval=0.05)


class MASTER_BAKER_OT_combine_placeholder_texture_sets(bpy.types.Operator):
    bl_idname = "master_baker.combine_placeholder_texture_sets"
    bl_label = "Use One Texture Set"
    bl_description = (
        "Put the bake groups whose material is only named after their own mesh "
        "into one shared texture set"
    )
    bl_options = {"REGISTER", "UNDO"}

    group_names: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def _names(self) -> list[str]:
        return [name for name in str(self.group_names or "").split("\n") if name]

    def invoke(self, context, _event):
        if not self._names():
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self, width=420, title="Use one texture set?", confirm_text="Use One Texture Set"
        )

    def draw(self, _context):
        count = len(self._names())
        column = self.layout.column(align=True)
        column.label(text=f"{count} meshes each have a material named after the mesh itself.")
        column.label(text="ZBrush adds these when it sends meshes to Blender.")
        column.label(text=f"Right now they bake into {count} separate texture sets.")
        column.separator()
        column.label(text="Their UVs don't overlap, so they fit in one texture set.")
        column.label(text="Cancel keeps the separate texture sets.")

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        wanted = set(self._names())
        shared = (getattr(project, "name", "") or "").strip() or "TextureSet"
        changed = 0
        old_sets = set()
        for group in project.groups:
            if str(getattr(group, "name", "") or "") in wanted:
                old_sets.add(str(getattr(group, "texture_set_name", "") or "").strip())
                group.texture_set_name = shared
                changed += 1
        if not changed:
            self.report({"WARNING"}, "Those bake groups are no longer in this project")
            return {"CANCELLED"}
        # The per-mesh sets the setup made are empty now; leaving them would show the
        # artist three texture sets with nothing in them.
        still_used = {str(getattr(group, "texture_set_name", "") or "").strip() for group in project.groups}
        texture_sets = getattr(project, "texture_sets", None)
        if texture_sets is not None:
            for index in reversed(range(len(texture_sets))):
                name = str(getattr(texture_sets[index], "name", "") or "").strip()
                if name in old_sets and name not in still_used:
                    texture_sets.remove(index)
            if hasattr(project, "active_texture_set_index"):
                project.active_texture_set_index = max(
                    0, min(int(project.active_texture_set_index), len(texture_sets) - 1)
                )
        properties.reconcile_texture_sets(project)
        overlays.tag_redraw_all_view3d()
        self.report({"INFO"}, f"{changed} bake groups now share the texture set '{shared}'")
        return {"FINISHED"}


def _reportable_skipped_meshes(context, meshes, assigned_names) -> list[str]:
    """Unsuffixed meshes worth naming, out of everything the build scanned.

    The scene build has to SCAN the whole view layer -- a high-poly parked in a
    hidden collection still has to be found -- but scanning everything is not a
    reason to complain about everything. A tester with two spare cubes in a hidden
    `Spare` collection got them named in the status bar after an auto-build that had
    correctly grouped four other meshes, and read it as the addon having used the
    wrong selection.

    So the pool and the report are separated. A mesh is only worth naming when the
    artist could plausibly have meant it: it is selected, or it is visible, or it
    shares a collection with something the build actually matched. Anything else is
    clutter the build was right to walk past silently.
    """
    matched_collections = set()
    for mesh in meshes:
        if str(getattr(mesh, "name", "") or "") not in assigned_names:
            continue
        for collection in getattr(mesh, "users_collection", ()) or ():
            matched_collections.add(getattr(collection, "name", ""))

    selected = {
        str(getattr(obj, "name", "") or "") for obj in _selected_mesh_objects(context)
    }

    reportable: list[str] = []
    for mesh in meshes:
        name = str(getattr(mesh, "name", "") or "")
        if not name or name in assigned_names:
            continue
        if name in selected:
            reportable.append(name)
            continue
        visible = True
        try:
            visible = not bool(mesh.hide_get()) and not bool(getattr(mesh, "hide_viewport", False))
        except (AttributeError, RuntimeError):
            visible = True
        if visible:
            reportable.append(name)
            continue
        if any(
            getattr(collection, "name", "") in matched_collections
            for collection in (getattr(mesh, "users_collection", ()) or ())
        ):
            reportable.append(name)
    return reportable


def _split_oversized_prefix_matches(matches, high_triangle_count, threshold: int):
    """Split every prefix bucket whose high meshes exceed `threshold` triangles into parts.

    `high_triangle_count(name)` returns the evaluated triangle count of one high mesh.
    Returns ``(matches, prefix_by_part, splits)`` where each split is
    ``(prefix, high_triangles, part_count)``. A bucket with one low mesh cannot be split
    and is kept whole (the bake's own preflight still refuses it with a clear message).
    """
    result: dict = {}
    prefix_by_part: dict[str, str] = {}
    splits: list[tuple[str, int, int]] = []
    for prefix, bucket in matches.items():
        lows = bucket.get(constants.OBJECT_ROLE_LOW, []) or []
        total = 0
        if threshold > 0 and len(lows) > 1:
            for name in bucket.get(constants.OBJECT_ROLE_HIGH, []) or []:
                try:
                    total += int(high_triangle_count(name) or 0)
                except Exception:
                    pass
        if threshold > 0 and len(lows) > 1 and total > threshold:
            parts, part_prefixes = matching.split_role_matches_per_part({prefix: bucket})
            # A high shared by every part (one merged sculpt) is copied into each part,
            # so the split can multiply the oversized scene instead of shrinking it.
            # Split only when the heaviest part really carries less than the prefix.
            largest_part = 0
            for part_bucket in parts.values():
                part_total = 0
                for name in part_bucket.get(constants.OBJECT_ROLE_HIGH, []) or []:
                    try:
                        part_total += int(high_triangle_count(name) or 0)
                    except Exception:
                        pass
                largest_part = max(largest_part, part_total)
            if len(parts) > 1 and largest_part < total:
                result.update(parts)
                prefix_by_part.update(part_prefixes)
                splits.append((prefix, total, len(parts)))
                continue
        result[prefix] = bucket
        prefix_by_part[prefix] = prefix
    return result, prefix_by_part, splits


def _apply_estimated_cage_offsets_to_new_groups(context, groups, created_group_names) -> int:
    """Give every Distance-mode group the build just CREATED the estimator's offset.

    The Distance offset starts at the 0.02 default in world units whatever the asset's
    scale. On the donated weapons scene (2026-09-15) that default missed most of the axe
    blade: the low sits 0.03 to 0.08 units inside the sculpt, the ray starts at
    low + normal * 0.02 and traces inward, so everything further out than 0.02 was
    unreachable and the dilation painted over the holes. The estimator (99th-percentile
    low-to-high clearance plus padding) gave 0.10 for the blade and fixed it. Fit it
    right after the build so the first bake of a new group starts from a fitted offset;
    a group the artist already had keeps whatever they set (only newly created groups,
    only while still on the default). Returns the number of groups queued.

    The fit itself is queued (see distance_offset_queue): it builds a BVH of
    every high, ~17 s on a customer's 71-group gun of ~100 M triangles, which Distance
    becoming the default (2026-10-27) would otherwise have added to Auto-Build.
    """
    created = {str(name) for name in (created_group_names or ())}
    if not created:
        return 0
    queued = 0
    for group in groups:
        if str(getattr(group, "name", "") or "") not in created:
            continue
        if str(getattr(group, "cage_mode", "") or "") != constants.CAGE_MODE_DISTANCE:
            continue
        if distance_offset_queue.enqueue(context, group):
            queued += 1
    return queued


def _group_meshes_by_suffix(
    operator,
    context,
    meshes,
    *,
    status_message: str,
    empty_error: str = "Select one or more mesh objects first",
    no_match_error: str = "No selected meshes matched LP/HP, Low/High, or Cage suffixes",
    texture_set_mode: str | None = None,
    scope_label: str = "selected",
) -> bool:
    """Build/update bake groups from `meshes` by shared name prefix + role suffix.

    Shared between the selection-driven ops and the scene-wide auto-build op; only
    the source mesh list and the two error strings differ. `texture_set_mode` (or the
    saved ui_state default) controls how the resulting groups are bucketed into
    texture sets: one-per-group, combined, or per-material.
    """
    if not meshes:
        operator.report({"ERROR"}, empty_error)
        return False

    if texture_set_mode is None:
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        ui_state = properties.scene_ui_state(settings) if settings is not None else None
        texture_set_mode = str(
            getattr(ui_state, "auto_texture_set_mode", constants.AUTO_TEXTURE_SET_PER_GROUP)
            if ui_state is not None
            else constants.AUTO_TEXTURE_SET_PER_GROUP
        )

    # Clear stale object tags before suffix detection so old tags from a previous
    # grouping run don't override the suffix-based group names.
    for obj in meshes:
        try:
            tagging.clear_role_tag(obj)
        except Exception:
            pass

    # prefer_suffix: this operator is "group by NAME". Without it a mesh already
    # linked into another group's role collection is classified back into that group
    # by collection name, so the build could never move a mesh its name had left.
    matches = matching.collect_role_matches(meshes, prefer_suffix=True)
    if not matches:
        operator.report({"ERROR"}, no_match_error)
        return False

    # Granularity. PART (the default): one group per low mesh, named by everything before
    # its role word as Painter and Marmoset do, the parts of a prefix sharing a texture
    # set. PREFIX defaulted until 1.1.1 and merged Object_001 and Object_002 into one
    # "Object" group, which customers read as wrong matching. PREFIX: one group per prefix, except a prefix whose high
    # meshes are too many triangles for one GPU scene, which is split into parts here
    # rather than failing its VRAM preflight at bake time (the 20-part, 41.8 M-triangle
    # scythe of 2026-09-14).
    granularity = constants.AUTO_GROUP_GRANULARITY_PART
    try:
        _settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        _ui_state = properties.scene_ui_state(_settings) if _settings is not None else None
        granularity = str(
            getattr(_ui_state, "auto_group_granularity", constants.AUTO_GROUP_GRANULARITY_PART)
            or constants.AUTO_GROUP_GRANULARITY_PART
        )
    except Exception:
        granularity = constants.AUTO_GROUP_GRANULARITY_PART
    prefix_by_part: dict[str, str] = {name: name for name in matches}
    split_reports: list[tuple[str, int, int]] = []
    if granularity == constants.AUTO_GROUP_GRANULARITY_PART:
        matches, prefix_by_part = matching.split_role_matches_per_part(matches)
    else:
        _depsgraph = None
        try:
            _depsgraph = context.evaluated_depsgraph_get()
        except Exception:
            _depsgraph = None
        _tri_cache: dict[str, int] = {}
        _resolve_high = _scene_object_getter(context.scene)

        def _high_triangles(name: str) -> int:
            if name not in _tri_cache:
                obj = _resolve_high(name)
                _tri_cache[name] = _evaluated_tri_count(obj, _depsgraph) if obj is not None else 0
            return _tri_cache[name]

        matches, prefix_by_part, split_reports = _split_oversized_prefix_matches(
            matches, _high_triangles, int(constants.AUTO_GROUP_SPLIT_HIGH_TRIANGLES)
        )

    # Per Material is Painter's model: one texture set per material, also when one low
    # mesh carries several. Each material becomes a group restricted to its faces.
    material_by_group: dict[str, str] = {}
    if texture_set_mode == constants.AUTO_TEXTURE_SET_PER_MATERIAL:
        _resolve_low = _scene_object_getter(context.scene)

        def _low_materials(name: str) -> list[str]:
            obj = _resolve_low(name)
            return [material.name for material in low_material_subset.used_materials(obj)] if obj is not None else []

        matches, prefix_by_part, material_by_group = matching.split_role_matches_per_material(
            matches, prefix_by_part, _low_materials
        )

    # Meshes whose name carries no Low/High/Cage role are not grouped. Count them so the
    # summary can say so: silently ignoring half a selection reads as "the addon only
    # added some of my objects" with nothing on screen to explain which, or why.
    assigned_names = {
        name
        for bucket in matches.values()
        for names in bucket.values()
        for name in names
    }
    skipped_mesh_names = _reportable_skipped_meshes(context, meshes, assigned_names)

    project, _created_project = _ensure_active_project(context)
    resolve_object = _scene_object_getter(context.scene)
    created_count = 0
    touched_count = 0
    evicted_count = 0
    # Names, not PropertyGroup references. Every `project.groups.add()` below can
    # reallocate the collection's IDProperty array, which leaves every earlier
    # Python wrapper pointing into freed memory; the first write through one of
    # them (`group.texture_set_name = ...`) is an EXCEPTION_ACCESS_VIOLATION inside
    # IDP_AddToGroup. Small scenes rarely realloc, a 66-group character did every
    # time (2026-09-07). Re-resolve from `project.groups` once the loop is done.
    last_group_name = None
    touched_group_names: list[str] = []
    created_group_names: list[str] = []

    # Assigning role slots fires _group_membership_update per object (twice, once
    # per slot collection); that per-slot overlay/preview/backend-prewarm cascade
    # on multi-million-tri high meshes is what freezes Blender on a scene-wide
    # build. Suppress it here and run one consolidated refresh after the loop.
    with properties.suspend_group_membership_updates():
        # The name is the authority on membership, so a mesh this run assigns must
        # first leave every OTHER group. Without this the operation was purely
        # additive: re-running it after a rename created the right group and left the
        # wrong one holding the mesh too, which is how both 2026-08-19 tester bundles
        # ended up with group #1 owning every mesh in the project. Swept before any
        # assignment, and keyed on each mesh's destination so a mesh already in the
        # right group is not counted (or churned) as a move.
        destinations_by_name: dict[str, set[str]] = {}
        for group_name, bucket in matches.items():
            for names in bucket.values():
                for name in names:
                    destinations_by_name.setdefault(name, set()).add(group_name)
        emptied_candidates: set[str] = set()
        for existing_group in project.groups:
            existing_name = str(getattr(existing_group, "name", "") or "")
            strangers = [
                obj
                for obj in (
                    resolve_object(name)
                    for name, destinations in destinations_by_name.items()
                    if existing_name not in destinations
                )
                if obj is not None
            ]
            evicted = _discard_role_objects(existing_group, strangers)
            evicted_count += evicted
            if evicted:
                emptied_candidates.add(existing_name)

        for group_name, match_bucket in matches.items():
            group, created = _get_or_create_group_with_flag(project, group_name)
            if created:
                # A part group starts in its prefix's texture set, so the parts of one
                # asset still batch together on the GPU.
                group.texture_set_name = prefix_by_part.get(group_name, group_name)
                created_count += 1
                created_group_names.append(str(group.name))
            group.low_material = bpy.data.materials.get(material_by_group.get(group_name, ""))
            _ensure_group_collection_scaffold(context, project, group)
            touched_count += 1
            last_group_name = str(group.name)
            touched_group_names.append(last_group_name)

            for role, names in match_bucket.items():
                if role == constants.OBJECT_ROLE_CAGE:
                    if not names:
                        continue
                    obj = resolve_object(names[0])
                    if obj is None:
                        continue
                    group.cage_mode = constants.CAGE_MODE_CUSTOM
                    group.custom_cage = obj
                    tagging.apply_role_tag(obj, role, group_name=group.name, source="suffix")
                    _link_objects_to_group_role_collection(context, project, group, role, [obj])
                    continue

                linked_objects = []
                for object_name in names:
                    obj = resolve_object(object_name)
                    if obj is None:
                        continue
                    if _add_unique_role_objects(group, role, [obj]) <= 0:
                        continue
                    linked_objects.append(obj)
                    tagging.apply_role_tag(obj, role, group_name=group.name, source="suffix")
                _link_objects_to_group_role_collection(context, project, group, role, linked_objects)

    # A group this build took every mesh from has nothing left to bake (re-running after
    # the materials of "mod" split it into "mod_Mat_01"...): an empty group would only
    # fail the bake's checks. Removing it can move the others, so wrappers are fetched after.
    touched_before_cleanup = set(touched_group_names)
    for index in range(len(project.groups) - 1, -1, -1):
        leftover = project.groups[index]
        leftover_name = str(getattr(leftover, "name", "") or "")
        if leftover_name not in emptied_candidates or leftover_name in touched_before_cleanup:
            continue
        leftover_roles = properties.group_role_assignments_state(leftover)
        if any(
            getattr(slot, "object_ref", None) is not None
            for slot in list(getattr(leftover_roles, "low_meshes", [])) + list(getattr(leftover_roles, "high_meshes", []))
        ):
            continue
        _remove_group_collections(leftover)
        project.groups.remove(index)

    # Fresh wrappers: no more adds happen from here on (texture-set entries live in
    # a separate collection, so `reconcile_texture_sets` cannot move the groups).
    touched_name_set = set(touched_group_names)
    touched_groups = [
        group for group in project.groups if str(getattr(group, "name", "") or "") in touched_name_set
    ]

    # Bucket the touched groups into texture sets per the chosen mode (per-group /
    # combined / per-material) before creating the set entries.
    placeholder_groups = _apply_auto_texture_set_mode(project, touched_groups, texture_set_mode)

    if last_group_name is not None:
        for index, group in enumerate(project.groups):
            if str(getattr(group, "name", "") or "") == last_group_name:
                project.active_group_index = index
                break
        project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP

    # Create texture-set entries for the names the grouping just assigned so the sets
    # are selectable in the hierarchy and carry their own naming settings.
    properties.reconcile_texture_sets(project)

    # Run the suppressed membership cascade once, now that every slot is assigned.
    properties.bulk_group_membership_refresh(context, touched_groups)

    # Queue the Distance offset fit of every group this build created.
    estimated_offset_count = _apply_estimated_cage_offsets_to_new_groups(
        context, touched_groups, created_group_names
    )

    # Present the low-poly as the working geometry and tuck the high-poly away so the
    # freshly-built project isn't buried under its multi-million-tri high meshes. Runs
    # after the membership refresh so this visibility state is the final word.
    _present_low_poly_after_build(touched_groups)

    summary = status_message.format(
        count=touched_count,
        created=created_count,
        updated=max(0, touched_count - created_count),
    )
    # Always state the mesh count next to the group count. Groups are keyed on the
    # NAME PREFIX, so "Prop_A_low/high" and "Prop_B_low/high" deliberately land in one
    # "Prop" group — correct, but indistinguishable from "half my objects were dropped"
    # unless the numbers are shown.
    summary = f"{summary} ({len(assigned_names)} mesh(es) assigned)"
    if estimated_offset_count:
        summary = f"{summary}; fitting {estimated_offset_count} cage offset(s)"
    if placeholder_groups:
        _ask_to_combine_placeholder_sets(placeholder_groups)
    for split_prefix, split_triangles, split_parts in split_reports:
        split_message = (
            f"Split '{split_prefix}' ({split_triangles / 1e6:.1f} M high-poly triangles) into "
            f"{split_parts} per-part bake groups sharing one texture set"
        )
        operator.report({"INFO"}, split_message)
        summary = f"{summary}; '{split_prefix}' split into {split_parts} parts"
    if evicted_count:
        # Silent eviction is how the bug this fixes went unnoticed for so long. Say
        # it happened, so a rename that moves geometry between groups is visible.
        move_message = (
            f"Moved {evicted_count} mesh assignment(s) out of the group(s) their names "
            f"no longer match"
        )
        operator.report({"INFO"}, move_message)
        summary = f"{summary}; {evicted_count} moved"
    if skipped_mesh_names:
        shown = ", ".join(skipped_mesh_names[:3])
        if len(skipped_mesh_names) > 3:
            shown += f", +{len(skipped_mesh_names) - 3} more"
        # Name the scope. The scene-wide build reports meshes the artist never
        # selected, and without saying so it reads as an accusation about the
        # selection — a tester hit exactly that with correctly named meshes and two
        # unrelated leftovers elsewhere in the scene.
        skip_message = (
            f"{len(skipped_mesh_names)} {scope_label} mesh(es) had no Low/High/Cage "
            f"suffix and were not grouped: {shown}"
        )
        operator.report({"WARNING"}, skip_message)
        summary = f"{summary}; {len(skipped_mesh_names)} skipped"
    _sync_tag_status(context, summary)
    overlays.tag_redraw_all_view3d()
    return True


def _active_collection(context):
    collection = getattr(context, "collection", None)
    if collection is not None:
        return collection
    view_layer = getattr(context, "view_layer", None)
    active_layer_collection = getattr(view_layer, "active_layer_collection", None)
    if active_layer_collection is None:
        return None
    return getattr(active_layer_collection, "collection", None)


def _sync_tag_status(context, message: str):
    settings = getattr(context.scene, "fyr_baker_settings", None)
    if settings is not None:
        settings.status_message = message
    project = properties.get_active_project(context.scene)
    if project is not None:
        project.last_status_message = message


def _resolve_slot_object(slot_collection, active_index: int = 0):
    if slot_collection:
        if 0 <= active_index < len(slot_collection):
            active_object = getattr(slot_collection[active_index], "object_ref", None)
            if active_object is not None:
                return active_object
        for slot in slot_collection:
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                return obj
    return None


def _active_low_mesh_object(group):
    role_state = _group_role_assignments_state(group)
    return _resolve_slot_object(getattr(role_state, "low_meshes", []), getattr(role_state, "low_mesh_index", 0))


def _active_low_mesh_slot(group):
    return properties.peek_active_low_slot(group)


def _iter_group_role_meshes(group, role):
    for obj in _group_role_targets(group, role):
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield obj


def _present_low_poly_after_build(groups) -> None:
    """After a project is built from names/selection, show the low-poly (the geometry
    you actually bake to) and tuck the high-poly source out of the viewport so a fresh
    project isn't buried under its multi-million-tri high meshes. Mirrors the low-only
    default of the group-visibility eye; shift-clicking that eye (or turning on the High
    reference preview) brings the high-poly back."""
    high_objs = []
    low_objs = []
    for group in groups:
        high_objs.extend(_iter_group_role_meshes(group, constants.OBJECT_ROLE_HIGH))
        low_objs.extend(_iter_group_role_meshes(group, constants.OBJECT_ROLE_LOW))
    # Hide highs first, then reveal lows, so a mesh that is a low in one group and a
    # high in another ends up visible — the low role wins, matching the eye toggle.
    for obj in high_objs:
        _set_object_hidden_with_fallback(obj, True)
    for obj in low_objs:
        _set_object_hidden_with_fallback(obj, False)


def _world_bounds_for_objects(objects):
    minimum = [None, None, None]
    maximum = [None, None, None]

    for obj in objects:
        bound_box = getattr(obj, "bound_box", None)
        if not bound_box:
            continue
        for corner in bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            for axis, value in enumerate((float(world_corner.x), float(world_corner.y), float(world_corner.z))):
                if minimum[axis] is None or value < minimum[axis]:
                    minimum[axis] = value
                if maximum[axis] is None or value > maximum[axis]:
                    maximum[axis] = value

    if any(value is None for value in minimum + maximum):
        return None
    return tuple(minimum), tuple(maximum)


def _estimate_auto_cage_offset(group, depsgraph=None) -> float | None:
    active_low = _active_low_mesh_object(group)
    if active_low is None:
        return None
    high_meshes = properties.effective_high_mesh_objects(group)
    if not high_meshes:
        return None
    low_bounds = _world_bounds_for_objects([active_low])
    high_bounds = _world_bounds_for_objects(high_meshes)
    return cage_offset_estimator.CageOffsetEstimator().estimate(
        active_low,
        high_meshes,
        depsgraph,
        low_bounds=low_bounds,
        high_bounds=high_bounds,
    )


def _estimate_group_cage_offset(group, depsgraph=None) -> float | None:
    """The Distance offset that reaches the high from EVERY low mesh of the group.

    The group offset applies to all its lows; fitting it from the active low alone left
    a blade that needs 0.10 on the 0.02 default whenever the handle was listed first.
    """
    high_meshes = properties.effective_high_mesh_objects(group)
    if not high_meshes:
        return None
    high_bounds = _world_bounds_for_objects(high_meshes)
    role_state = properties.group_role_assignments_state(group)
    lows = []
    for slot in getattr(role_state, "low_meshes", []) or []:
        obj = getattr(slot, "object_ref", None)
        if obj is None or getattr(obj, "type", None) != "MESH" or any(existing is obj for existing in lows):
            continue
        lows.append(obj)
    if not lows:
        return _estimate_auto_cage_offset(group, depsgraph=depsgraph)
    estimator = cage_offset_estimator.CageOffsetEstimator()
    if depsgraph is not None:
        try:
            reach = estimator.estimate_group_reach(
                lows,
                high_meshes,
                depsgraph,
                smooth_normals=cage.auto_cage_uses_average_normals(group),
            )
        except Exception:
            reach = None
        if reach is not None:
            return float(reach)
    # Without the GPU pass (background Blender): one pass for the whole group: the highs' trees are built once (not once per low),
    # and the content-keyed on-disk store answers a group measured in any earlier
    # session. Same value per low as estimate(); a low the surface pass cannot measure
    # falls back to the bounds estimate exactly as estimate() does.
    measured = [None] * len(lows)
    if depsgraph is not None:
        try:
            measured = estimator.estimate_group(lows, high_meshes, depsgraph)
        except Exception:
            measured = [None] * len(lows)
    best = None
    for low, estimate in zip(lows, measured):
        if estimate is None:
            estimate = estimator.estimate(
                low,
                high_meshes,
                None,
                low_bounds=_world_bounds_for_objects([low]),
                high_bounds=high_bounds,
            )
        if estimate is not None and (best is None or float(estimate) > best):
            best = float(estimate)
    return best


def _estimate_low_slot_offset_delta(group, slot, depsgraph=None) -> float | None:
    active_low = getattr(slot, "object_ref", None) if slot is not None else None
    if active_low is None or getattr(active_low, "type", None) != "MESH":
        return None
    high_meshes = properties.effective_high_mesh_objects(group)
    if not high_meshes:
        return None
    low_bounds = _world_bounds_for_objects([active_low])
    high_bounds = _world_bounds_for_objects(high_meshes)
    estimate = cage_offset_estimator.CageOffsetEstimator().estimate(
        active_low,
        high_meshes,
        depsgraph,
        low_bounds=low_bounds,
        high_bounds=high_bounds,
    )
    if estimate is None:
        return None
    return float(estimate) - float(getattr(group, "cage_offset", 0.0))


def _estimate_active_low_object_offset_delta(group, depsgraph=None) -> float | None:
    estimate = _estimate_auto_cage_offset(group, depsgraph=depsgraph)
    if estimate is None:
        return None
    return float(estimate) - float(getattr(group, "cage_offset", 0.0))


def _apply_cage_offset_change(context, group, new_offset: float, *, status_message: str) -> None:
    group.cage_offset = max(0.0, float(new_offset))
    settings = context.scene.fyr_baker_settings
    settings.status_message = status_message
    project = properties.get_active_project(context.scene)
    if project is not None:
        project.last_status_message = status_message
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))


def _apply_object_cage_offset_change(context, slot, new_delta: float, *, status_message: str) -> None:
    slot.cage_offset_delta = float(new_delta)
    settings = context.scene.fyr_baker_settings
    settings.status_message = status_message
    project = properties.get_active_project(context.scene)
    if project is not None:
        project.last_status_message = status_message
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))


def _selected_low_slot_targets(context) -> list[cage_session.ResolvedLowSlotTarget]:
    return cage_session.resolve_selected_low_slot_targets(
        getattr(context, "scene", None),
        context=context,
    )


def _selected_low_slot_targets_or_report(operator, context) -> list[cage_session.ResolvedLowSlotTarget]:
    targets = _selected_low_slot_targets(context)
    if targets:
        return targets
    operator.report({"ERROR"}, "Select one or more low meshes assigned to the active project's bake groups")
    return []


def _selected_low_target_groups(context) -> list[object]:
    return cage_session.selected_low_target_groups(
        getattr(context, "scene", None),
        context=context,
    )


def _selected_low_target_groups_or_report(operator, context) -> list[object]:
    groups = _selected_low_target_groups(context)
    if groups:
        return groups
    operator.report({"ERROR"}, "Select one or more low meshes assigned to the active project's bake groups")
    return []


def _cleanup_generated_cage_object(cage_object) -> None:
    if cage_object is None or not bool(cage_object.get("_master_baker_generated_cage")):
        return

    cage_mesh = getattr(cage_object, "data", None)
    bpy.data.objects.remove(cage_object, do_unlink=True)
    if cage_mesh is not None and getattr(cage_mesh, "users", 0) == 0:
        bpy.data.meshes.remove(cage_mesh)


def _create_generated_cage_from_triangles(context, triangles, *, object_name: str, group_name: str, target_collection=None):
    positions, faces = cage.mesh_geometry_from_triangles(triangles)
    if not positions or not faces:
        raise RuntimeError(f"Unable to create a cage mesh for '{object_name}'")

    cage_mesh = bpy.data.meshes.new(f"{object_name}_mesh")
    cage_mesh.from_pydata(positions, [], faces)
    cage_mesh.update()

    cage_object = bpy.data.objects.new(object_name, cage_mesh)
    cage_object.display_type = "SOLID"
    cage_object.show_wire = False
    cage_object.hide_render = True
    if hasattr(cage_object, "show_transparent"):
        cage_object.show_transparent = True
    if hasattr(cage_object, "show_in_front"):
        cage_object.show_in_front = False
    cage_object.color = (0.18, 0.88, 0.46, 0.38)

    destination = target_collection if target_collection is not None else context.scene.collection
    try:
        destination.objects.link(cage_object)
    except Exception:
        context.scene.collection.objects.link(cage_object)

    cage_object["_master_baker_generated_cage"] = True
    tagging.apply_role_tag(cage_object, constants.OBJECT_ROLE_CAGE, group_name=group_name, source="generated")
    return cage_object


def _create_generated_cage_from_object(context, source_object, *, group_name: str):
    depsgraph = context.evaluated_depsgraph_get()
    evaluated_object = source_object.evaluated_get(depsgraph)

    try:
        cage_mesh = bpy.data.meshes.new_from_object(
            evaluated_object,
            preserve_all_data_layers=True,
            depsgraph=depsgraph,
        )
    except TypeError:
        cage_mesh = bpy.data.meshes.new_from_object(evaluated_object, depsgraph=depsgraph)

    if cage_mesh is None:
        raise RuntimeError(f"Unable to create a cage mesh from '{source_object.name}'")

    cage_name = f"{source_object.name}_cage"
    cage_mesh.name = f"{cage_name}_mesh"
    cage_object = bpy.data.objects.new(cage_name, cage_mesh)
    cage_object.matrix_world = source_object.matrix_world.copy()
    cage_object.display_type = "SOLID"
    cage_object.show_wire = False
    cage_object.hide_render = True
    if hasattr(cage_object, "show_transparent"):
        cage_object.show_transparent = True
    if hasattr(cage_object, "show_in_front"):
        cage_object.show_in_front = False
    cage_object.color = (0.18, 0.88, 0.46, 0.38)

    collection = _primary_collection_for_object(source_object) or context.scene.collection
    collection.objects.link(cage_object)

    cage_object["_master_baker_generated_cage"] = True
    tagging.apply_role_tag(cage_object, constants.OBJECT_ROLE_CAGE, group_name=group_name, source="generated")
    return cage_object


def _custom_cage_object_or_report(operator, context):
    project, group = _cage_target_project_group_or_report(operator, context)
    if project is None or group is None:
        return None, None, None
    if getattr(group, "cage_mode", "") != constants.CAGE_MODE_CUSTOM:
        operator.report({"ERROR"}, "These tools only apply to Custom Cage mode")
        return project, group, None

    cage_object = getattr(group, "custom_cage", None)
    if cage_object is None:
        operator.report({"ERROR"}, "Assign a custom cage first")
        return project, group, None
    if str(getattr(cage_object, "type", "MESH") or "MESH") != "MESH":
        operator.report({"ERROR"}, "The active custom cage must be a mesh object")
        return project, group, None
    return project, group, cage_object


def _triangulated_mesh_faces(mesh) -> list[tuple[int, int, int]]:
    faces: list[tuple[int, int, int]] = []
    for polygon in getattr(mesh, "polygons", []):
        polygon_vertices = list(getattr(polygon, "vertices", ()))
        if len(polygon_vertices) < 3:
            continue
        root = int(polygon_vertices[0])
        for offset in range(1, len(polygon_vertices) - 1):
            faces.append((root, int(polygon_vertices[offset]), int(polygon_vertices[offset + 1])))
    return faces


def _mesh_geometry_from_object(cage_object) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    mesh = getattr(cage_object, "data", None)
    if mesh is None:
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' has no mesh data")

    positions: list[tuple[float, float, float]] = []
    for vertex in getattr(mesh, "vertices", []):
        coordinate = getattr(vertex, "co", None)
        if coordinate is None:
            positions.append((0.0, 0.0, 0.0))
            continue
        if hasattr(coordinate, "x") and hasattr(coordinate, "y") and hasattr(coordinate, "z"):
            positions.append((float(coordinate.x), float(coordinate.y), float(coordinate.z)))
            continue
        positions.append((float(coordinate[0]), float(coordinate[1]), float(coordinate[2])))

    faces = _triangulated_mesh_faces(mesh)
    if not positions or not faces:
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' has no editable mesh faces")
    return positions, faces


def _write_mesh_geometry_to_object(cage_object, positions: list[tuple[float, float, float]]) -> None:
    mesh = getattr(cage_object, "data", None)
    vertices = getattr(mesh, "vertices", None)
    if mesh is None or vertices is None:
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' has no mesh data")
    if len(vertices) != len(positions):
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' vertex count changed unexpectedly")

    for vertex, position in zip(vertices, positions):
        vertex.co = Vector(position)

    if hasattr(mesh, "update"):
        mesh.update()


def _ensure_single_user_cage_mesh(cage_object) -> None:
    mesh = getattr(cage_object, "data", None)
    if mesh is None:
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' has no mesh data")
    if int(getattr(mesh, "users", 1) or 1) <= 1:
        return
    if not hasattr(mesh, "copy"):
        return
    cage_object.data = mesh.copy()


def _cage_object_local_delta(cage_object, world_delta: float) -> float:
    """A world-unit offset expressed in the cage object's local space.

    The offsets and deltas an artist sees are world units (the estimator
    measures world distance; generated cages sit at identity), but the tools
    read and write raw local vertex.co. On a user cage scaled 0.1 an Inflate of
    0.005 moved the cage 0.0005 world units.
    """
    try:
        scale = [abs(float(component)) for component in cage_object.matrix_world.to_scale()]
        mean_scale = sum(scale) / 3.0
    except Exception:
        mean_scale = 1.0
    if mean_scale <= 1e-9:
        return float(world_delta)
    return float(world_delta) / mean_scale


def _apply_custom_cage_mesh_positions(context, cage_object, positions: list[tuple[float, float, float]], *, status_message: str) -> None:
    # Check the count before touching the datablock: making the mesh single-user
    # first left an orphan copy behind when the write was refused.
    mesh = getattr(cage_object, "data", None)
    if mesh is None or mesh_read.element_count(mesh, "vertices") != len(positions):
        raise RuntimeError(f"Custom cage '{getattr(cage_object, 'name', 'Cage')}' vertex count changed unexpectedly")
    _ensure_single_user_cage_mesh(cage_object)
    _write_mesh_geometry_to_object(cage_object, positions)
    _sync_tag_status(context, status_message)
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="custom_cage_tool",
    )
    request_live_normal_preview_refresh(context, reason="custom_cage_tool")


def _restore_isolation_state(scene):
    for obj in scene.objects:
        if "_master_baker_prev_hidden" in obj:
            obj.hide_set(bool(obj["_master_baker_prev_hidden"]))
            del obj["_master_baker_prev_hidden"]


def _set_hidden_state_for_objects(objects, hidden: bool):
    for obj in objects:
        obj.hide_set(bool(hidden))
        if "_master_baker_prev_hidden" in obj:
            obj["_master_baker_prev_hidden"] = bool(hidden)


def _clear_group_isolation_flags(scene) -> None:
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return
    for project in getattr(settings, "projects", []):
        for group in getattr(project, "groups", []):
            if hasattr(group, "isolate_in_viewport"):
                group.isolate_in_viewport = False


def _isolation_snapshot_active(scene) -> bool:
    for obj in getattr(scene, "objects", []):
        try:
            if "_master_baker_prev_hidden" in obj:
                return True
        except Exception:
            continue
    return False


def _toggle_isolation_targets(scene, targets) -> bool | None:
    scene_objects = list(getattr(scene, "objects", []))
    target_objects = [obj for obj in targets if obj is not None]
    if not scene_objects or not target_objects:
        return None

    target_set = set(target_objects)
    if _isolation_snapshot_active(scene):
        visible_set = {obj for obj in scene_objects if not bool(obj.hide_get())}
        _restore_isolation_state(scene)
        _clear_group_isolation_flags(scene)
        if visible_set == target_set:
            return False

    _clear_group_isolation_flags(scene)
    for obj in scene_objects:
        obj["_master_baker_prev_hidden"] = bool(obj.hide_get())
        obj.hide_set(obj not in target_set)
    return True


def _report_validation_issues(operator, issues):
    errors, warnings = validation.summarize_issues(issues)
    primary_message = validation.primary_issue_message(issues)
    # Dedupe identical messages before surfacing them — the same issue (e.g. a
    # missing source material, or an untracked output target) is reported once
    # per bake group, which otherwise floods the header with 3+ identical popups.
    for level, batch in (("ERROR", errors), ("WARNING", warnings)):
        seen: list[str] = []
        for issue in batch:
            if issue.message in seen:
                continue
            seen.append(issue.message)
            operator.report({level}, issue.message)
            if len(seen) >= 3:
                break
    return errors, warnings, primary_message


def _preflight_depsgraph():
    """The evaluated depsgraph for a bake preflight, or None outside a live context.

    Only the ownership check uses it, to scan the OTHER projects' UDIM occupancy
    so the tile-aware collision test sees both sides the same way.
    """
    try:
        return bpy.context.evaluated_depsgraph_get()
    except Exception:
        return None


def _validate_prepared_job(operator, prepared, project, scene_settings):
    from . import project_output_validation

    issues = validation.validate_bake_job(
        prepared.job,
        material_bake_spec_count=len(getattr(prepared, "material_bake_specs", []) or []),
        derived_output_count=len(getattr(prepared, "derived_outputs", []) or []),
    )
    issues.extend(
        project_output_validation.validate_prepared_output_ownership(
            project, prepared, depsgraph=_preflight_depsgraph()
        )
    )
    errors, warnings, primary_message = _report_validation_issues(operator, issues)
    # Notes the job preparation itself produced: things the bake will quietly NOT
    # include (currently material normal/AO detail that could not be shared across
    # the selected groups). These are not validation issues (the bake is valid and
    # proceeds) but the user has to hear them, or the map just comes out looking
    # wrong with nothing on screen explaining why. Returned as a copy so the
    # ValidationReport itself is left untouched.
    preparation_notes = [
        str(note).strip()
        for note in (getattr(prepared, "warnings", []) or [])
        if str(note).strip()
    ]
    if preparation_notes:
        warnings = list(warnings)
        for note in preparation_notes:
            operator.report({"WARNING"}, note)
            warnings.append(
                validation.ValidationIssue(
                    severity=validation.SEVERITY_WARNING,
                    code="MATERIAL_DETAIL_SKIPPED",
                    message=note,
                )
            )
    if errors:
        project.last_status_message = primary_message or "Fix job validation errors before continuing"
        if scene_settings is not None:
            scene_settings.status_message = constants.STATUS_FAILED
        return None, errors, warnings
    return issues, errors, warnings


def _recover_backend_from_out_of_memory() -> bool:
    """Restart the resident worker after an OOM so the next bake starts with a clean
    memory footprint. Best-effort — never let recovery raise into the bake handler."""
    try:
        runtime.restart_backend_worker(oom_recovery=True)
        return True
    except Exception:  # noqa: BLE001 - recovery must not mask the original failure
        return False


def _failure_guidance_for_progress(progress) -> tuple[str, str]:
    """``(guided_message, raw_line)`` for a failed bake, or ``("", "")``.

    Says whether the failure is the artist's setup, the GPU or the renderer, and what
    to do next, with the raw line kept as the details. Out-of-memory failures are left
    alone: their own path restarts the worker and already writes an actionable summary.
    """
    try:
        if diagnostics.failure_is_out_of_memory(progress):
            return "", ""
        texts: list[str] = []
        message = str(getattr(progress, "message", "") or "").strip()
        if message:
            texts.append(message)
        for error in list(getattr(progress, "errors", None) or []):
            text = str(error or "").strip()
            if text and text not in texts:
                texts.append(text)
        match = failure_guidance.explain_failures(texts)
    except Exception:  # noqa: BLE001 - guidance is an explanation, never a new failure
        return "", ""
    if match is None:
        return "", ""
    guidance, raw = match
    return failure_guidance.format_guided_message(guidance, raw), raw


def _apply_failure_guidance_summary(project, progress) -> str:
    """Put the guided form of a failure into the project's error summary, if any."""
    guided, _raw = _failure_guidance_for_progress(progress)
    if guided:
        try:
            project.last_error_summary = guided
        except Exception:
            pass
    return guided


def _report_backend_failure(operator, project, progress, *, progress_path: str | Path):
    guided, guided_raw = _failure_guidance_for_progress(progress)
    messages = diagnostics.backend_failure_messages(progress, progress_path=progress_path)
    if guided:
        # The guided line carries the raw text as its details, so the raw copy is
        # dropped and the guided one is reported last, where Blender's status bar
        # shows it.
        messages = [message for message in messages if message != guided_raw]
        messages.append(guided)
    for message in messages:
        operator.report({"ERROR"}, message)
    project.last_error_count = len(progress.errors)
    project.last_warning_count = len(progress.warnings)
    raw_summary = progress.message or (progress.errors[0] if progress.errors else "Backend bake failed")
    if diagnostics.failure_is_out_of_memory(progress):
        restarted = _recover_backend_from_out_of_memory()
        project.last_error_summary = diagnostics.out_of_memory_summary(raw_summary, restarted=restarted)
        operator.report({"WARNING"}, project.last_error_summary)
    else:
        project.last_error_summary = guided or raw_summary
    project.last_warning_summary = progress.warnings[0] if progress.warnings else ""
    project.last_status_message = constants.STATUS_FAILED


def _remember_cycles_handoff_prepared(prepared) -> None:
    job = getattr(prepared, "job", None)
    job_id = str(getattr(job, "job_id", "") or "").strip()
    if job_id:
        _CYCLES_HANDOFF_PREPARED[job_id] = prepared


def _pop_cycles_handoff_prepared(job_id: str | None):
    key = str(job_id or "").strip()
    if not key:
        return None
    return _CYCLES_HANDOFF_PREPARED.pop(key, None)


# The automatic retry after a GPU failure runs on the SAME modal driver as a deliberate
# Route = Cycles bake (`MASTER_BAKER_OT_cycles_bake_step`): one Cycles pass per timer tick,
# every non-timer event passed through, Esc and the Stop button both cancelling after the
# current pass. Blender stays responsive, the progress surfaces keep moving, and the user can stop the
# retry at any point, so there is no project size at which the handoff has to be refused.
#
# It used to call `execute_cycles_projection_fallback` directly, and that is a SYNCHRONOUS
# driver: `bpy.ops.object.bake` with no execution context holds the main thread for the whole
# retry with no progress bar, no redraw and no Esc. On a 16.4M-triangle three-group project
# that froze Blender hard enough to need killing, which is why a 2,000,000-face refusal used
# to live here. The freeze is gone, so the refusal is too.
#
# Headless / background runs (no window, so no modal handler) still take the synchronous
# driver below. Nothing there can redraw or be cancelled anyway, and there is no interactive
# session to lock up.


class CyclesHandoffOutcome(enum.Enum):
    """Result of asking for an automatic Cycles retry after a GPU bake failure.

    RECOVERED / FAILED are terminal: the synchronous driver has already finished baking
    by the time it returns one. PENDING means the modal driver took the job and the
    caller's post-processing has been deferred to its `on_complete` callback.
    """

    NOT_ATTEMPTED = "not_attempted"
    RECOVERED = "recovered"
    FAILED = "failed"
    PENDING = "pending"


# `_start_cycles_handoff_async` says the plan had nothing to step, which is not a launch
# failure: the synchronous driver re-plans and returns the same errors without baking.
_CYCLES_HANDOFF_NO_STEPS = "no-steps"


def _announce_cycles_handoff(context, project) -> None:
    try:
        project.last_status_message = "GPU bake failed, retrying via Cycles..."
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = project.last_status_message
    except Exception:
        pass


def _apply_cycles_handoff_success(project, progress) -> None:
    """Progress/project state after a fully recovered retry.

    Shared by both drivers so an async retry leaves exactly what the synchronous one did.
    """
    progress.errors = []
    progress.status = constants.STATUS_COMPLETE
    progress.message = "Bake complete (Cycles fallback)"
    # The stepper reports progress before each map, so it tops out one map short of the
    # end. A finished recovery is 100%, not "2/3".
    progress.percent = 100.0
    progress.warnings = list(getattr(progress, "warnings", None) or [])
    progress.warnings.append("GPU bake recovered via Blender/Cycles fallback")
    project.last_warning_summary = progress.warnings[-1]
    project.last_error_summary = ""
    project.last_error_count = 0


def _apply_cycles_handoff_failure(
    project, progress, handoff_errors, *, cancelled: bool = False, note: str | None = None
) -> None:
    """Progress/project state after a retry that did not recover every map.

    The GPU errors stay in place: they are the failure the user has to act on, and the
    Cycles errors are appended to them rather than replacing them.
    """
    existing = list(getattr(progress, "errors", None) or [])
    for message in handoff_errors:
        if message and message not in existing:
            existing.append(message)
    progress.errors = existing
    progress.warnings = list(getattr(progress, "warnings", None) or [])
    if note is None:
        note = (
            "Cycles retry stopped early, some maps were not recovered"
            if cancelled
            else "GPU bake handed off to Cycles; some maps could not be recovered"
        )
    progress.warnings.append(note)
    project.last_warning_summary = note
    if handoff_errors:
        project.last_error_summary = handoff_errors[0]
    elif existing:
        project.last_error_summary = existing[0]
    else:
        project.last_error_summary = note
    if cancelled:
        progress.status = constants.STATUS_CANCELLED


def _try_cycles_projection_handoff(
    context, project, progress, prepared, *, map_types=None, on_complete=None
) -> CyclesHandoffOutcome:
    """Retry supported maps via Cycles after a GPU handoff error.

    Returns PENDING when the modal driver took the job: the retry is running, and the
    caller's post-processing has been deferred to ``on_complete(recovered, operator,
    context)``, called exactly once from `_finalize_cycles_handoff_bake`. RECOVERED and
    FAILED come only from the synchronous driver, which has finished by then; the caller
    may post-process immediately. NOT_ATTEMPTED means no handoff was requested.
    """
    if prepared is None or not cycles_projection.progress_requests_cycles_handoff(progress):
        return CyclesHandoffOutcome.NOT_ATTEMPTED
    blocked_reason = cycles_projection.auto_recovery_blocked_reason(
        progress, prepared, map_types=map_types
    )
    if blocked_reason:
        # Refusing is the safe outcome here: the synchronous Cycles driver would hold
        # Blender's main thread for hours on a scene this size (2026-09-14, axe_scythe).
        _apply_cycles_handoff_failure(
            project,
            progress,
            [blocked_reason],
            note="The automatic Cycles retry was not started: baking this job that way unattended would take too long",
        )
        return CyclesHandoffOutcome.FAILED
    _announce_cycles_handoff(context, project)

    if _cycles_async_supported():
        problem = _start_cycles_handoff_async(
            context,
            project,
            progress,
            prepared,
            map_types=map_types,
            on_complete=on_complete,
        )
        if not problem:
            return CyclesHandoffOutcome.PENDING
        if problem != _CYCLES_HANDOFF_NO_STEPS:
            # The modal driver could not be launched. Falling back to the synchronous
            # driver here would reintroduce the freeze, so report instead of baking.
            _apply_cycles_handoff_failure(project, progress, [problem])
            return CyclesHandoffOutcome.FAILED

    handoff_errors = cycles_projection.execute_cycles_projection_fallback(
        prepared,
        context,
        map_types=map_types,
        on_progress=lambda label: setattr(project, "last_status_message", label),
    )
    if handoff_errors:
        _apply_cycles_handoff_failure(project, progress, handoff_errors)
        return CyclesHandoffOutcome.FAILED

    _apply_cycles_handoff_success(project, progress)
    return CyclesHandoffOutcome.RECOVERED


# One in-flight Cycles-primary session. `bpy.ops.object.bake` is a blocking main-thread
# call, so the session is stepped one Cycles bake PASS per modal timer tick: the UI
# redraws, progress advances and ESC lands between passes (a derived map such as a
# bent normal is up to eight passes). A single pass still blocks for its own
# duration — that is Blender's bake, not something chunking can subdivide.
_CYCLES_ASYNC_STATE: dict | None = None
_CYCLES_ASYNC_TIMER_INTERVAL = 0.05


def cycles_async_bake_active() -> bool:
    """True while a Cycles-primary bake is stepping through its modal driver."""
    return _CYCLES_ASYNC_STATE is not None


def request_cycles_async_cancel() -> bool:
    """Ask the running Cycles session to stop after the current pass. False if idle."""
    if _CYCLES_ASYNC_STATE is None:
        return False
    _CYCLES_ASYNC_STATE["cancel_requested"] = True
    _CYCLES_ASYNC_STATE.setdefault("cancel_requested_at", time.monotonic())
    return True


def cycles_async_cancel_pending() -> bool:
    """Whether a Cycles bake is finishing its current pass before it stops.

    Blender's bake operator is not interruptible mid-pass, so this wait is a hard
    floor, not a bug. The panel says so rather than leaving Stop looking broken.
    """
    return bool(_CYCLES_ASYNC_STATE is not None and _CYCLES_ASYNC_STATE.get("cancel_requested"))


def cycles_async_cancel_elapsed() -> float:
    if not cycles_async_cancel_pending():
        return 0.0
    requested_at = float(_CYCLES_ASYNC_STATE.get("cancel_requested_at", 0.0) or 0.0)
    return max(0.0, time.monotonic() - requested_at) if requested_at else 0.0


def _cycles_async_supported() -> bool:
    """Modal stepping needs a real window; headless/background runs stay synchronous."""
    if bool(getattr(getattr(bpy, "app", None), "background", False)):
        return False
    wm = getattr(bpy.context, "window_manager", None)
    return bool(wm is not None and getattr(wm, "windows", None))


def _cycles_state_job_id(state: dict) -> str:
    """Job id of a Cycles-primary run, for addressing its material queue."""
    prepared = state.get("prepared")
    return str(getattr(getattr(prepared, "job", None), "job_id", "") or "")


def _record_cycles_step_output(state: dict, step) -> None:
    """Report a finished map as a ProducedFile so the Outputs panel lights up."""
    progress = state["progress"]
    try:
        progress.produced_files.append(
            protocol.ProducedFile(
                group_name=step.group_name,
                map_type=step.map_type,
                path=str(step.output_path),
                map_uuid=step.map_uuid,
            )
        )
    except Exception:
        pass


def _cycles_step_pass_count(step) -> int:
    """How many Cycles bake passes one planned step costs (at least 1).

    The planner resolves this per step (a world-space bent normal needs fewer probes
    than a tangent one), so the step's own count wins; the map's strategy is the
    fallback for a step that does not carry one.
    """
    try:
        passes = int(getattr(step, "passes", 0) or 0)
    except (TypeError, ValueError):
        passes = 0
    if passes < 1:
        try:
            strategy = cycles_projection.cycles_map_strategy(getattr(step, "map_type", ""))
            passes = int(getattr(strategy, "passes", 1) or 1)
        except Exception:
            passes = 1
    return max(1, passes)


def _cycles_plan_pass_weights(state: dict) -> list[int]:
    """Per-step pass counts for the plan, computed once per run."""
    weights = state.get("pass_weights")
    steps = state["plan"].steps
    if not isinstance(weights, list) or len(weights) != len(steps):
        weights = [_cycles_step_pass_count(step) for step in steps]
        state["pass_weights"] = weights
    return weights


def _cycles_step_message(
    step, index: int, total: int, pass_index: int | None = None, pass_count: int = 1
) -> str:
    try:
        map_name = naming.map_label(step.map_type)
    except Exception:
        map_name = str(getattr(step, "map_type", "") or "")
    tile = int(getattr(step, "udim_tile", 0) or 0)
    tile_text = f" .{tile}" if tile else ""
    group = str(getattr(step, "group_name", "") or "")
    target = f"{group} / {map_name}" if group else map_name
    approx_text = " (approx)" if bool(getattr(step, "approximate", False)) else ""
    # Only multi-pass maps name the pass: "pass 1/1" on every single-bake map is noise.
    pass_text = ""
    if pass_index is not None and pass_count > 1:
        pass_text = f", pass {min(max(0, pass_index), pass_count - 1) + 1}/{pass_count}"
    return f"Baking {target}{tile_text}{approx_text} via Cycles{pass_text} ({index + 1}/{total})"


def _cycles_step_progress(state: dict, step, index: int, pass_index: int | None = None) -> None:
    """Mirror per-map progress onto the same surfaces the FYR poller drives.

    Called BEFORE step ``index`` (or its pass ``pass_index``) runs, so the percent is
    the Cycles work already finished, counted in bake passes across the whole plan (a
    tangent bent normal is eight bakes, a normal map one), never credit for the pass
    about to block the main thread. ``pass_index`` None is the synchronous driver,
    which runs a whole map per call and so names no pass.
    """
    plan = state["plan"]
    total = max(1, len(plan.steps))
    project = state["project"]
    progress = state["progress"]
    weights = _cycles_plan_pass_weights(state)
    total_passes = max(1, sum(weights))
    bounded_index = max(0, min(index, len(weights)))
    done_passes = sum(weights[:bounded_index])
    pass_count = weights[bounded_index] if bounded_index < len(weights) else 1
    if pass_index is not None:
        done_passes += min(max(0, int(pass_index)), pass_count)
    # A material stage, when there was one, already advanced the bar to 50%.
    floor = 50.0 if state.get("material_ran") else 0.0
    progress.percent = min(100.0, floor + (100.0 - floor) * done_passes / total_passes)
    progress.active_group = step.group_name
    progress.active_map = step.map_type
    progress.message = _cycles_step_message(step, index, total, pass_index, pass_count)
    try:
        project.last_status_message = progress.message
        project.last_active_group = progress.active_group
        project.last_active_map = progress.active_map
        project.last_progress_percent = progress.percent
        state["scene_settings"].status_message = progress.message
    except Exception:
        pass
    try:
        _tag_bake_progress_regions()
    except Exception:
        pass
    _poke_statusbar_redraw()


def _cycles_run_one_pass(state: dict, step, device: str) -> bool:
    """Run the next Cycles bake pass of ``step`` for the modal driver.

    The step's ``CyclesMapJob`` lives in ``state["active_job"]`` between ticks. After
    its last pass the job composes and saves in the same tick. Returns True once the
    map is over (written, or failed with its error recorded and its temporaries
    released), False while passes remain.
    """
    job = state.get("active_job")
    try:
        if job is None:
            job = cycles_projection.start_cycles_projection_job(step, device=device)
            state["active_job"] = job
        if job.passes_remaining:
            job.next_pass()
        if job.passes_remaining:
            return False
        job.finish()
    except Exception as exc:  # noqa: BLE001 - one failed map must not strand the driver
        state["errors"].append(cycles_projection.cycles_step_error(step, exc))
        _abort_cycles_active_job(state)
        return True
    state["active_job"] = None
    _record_cycles_step_output(state, step)
    return True


def _abort_cycles_active_job(state) -> None:
    """Release the in-flight map's temp images / UV offset without writing it.

    Safe on every path (ESC, Stop, the operator's cancel(), a failed pass, normal
    completion with nothing in flight): the job is popped before it is aborted, and
    ``CyclesMapJob.abort`` is itself idempotent.
    """
    if not isinstance(state, dict):
        return
    job = state.pop("active_job", None)
    if job is None:
        return
    try:
        job.abort()
    except Exception:  # noqa: BLE001 - teardown must finish regardless
        traceback.print_exc()


def _run_cycles_primary_bake(
    operator,
    context,
    project,
    scene_settings,
    prepared,
    *,
    start_message: str,
    reason: str = "",
    silent: bool = False,
):
    """Bake prepared projection outputs through Cycles without launching FYR.

    Plans the whole job up front (so unresolvable maps fail before any Cycles time is
    spent), then steps it through a modal driver when a window is available.
    """
    global _CYCLES_ASYNC_STATE

    if _CYCLES_ASYNC_STATE is not None:
        operator.report({"ERROR"}, "A Cycles bake is already running")
        return {"CANCELLED"}

    try:
        project.last_status_message = "Baking via Cycles..."
        scene_settings.status_message = constants.STATUS_BAKING
    except Exception:
        pass

    progress = protocol.BakeProgress(
        status=constants.STATUS_BAKING,
        message="Baking via Cycles...",
    )
    if reason:
        progress.warnings.append(reason)
    try:
        high_triangles = cycles_projection.prepared_high_triangle_total(prepared)
    except Exception:  # noqa: BLE001 - a warning must never stop the bake
        high_triangles = 0
    if high_triangles > constants.CYCLES_AUTO_RECOVERY_MAX_TRIANGLES:
        progress.warnings.append(
            f"The high poly is {high_triangles / 1e6:.1f}M triangles. Cycles loads all of it into"
            " memory, so this bake can be very slow or run out of memory. Decimate the high poly"
            " if you can."
        )

    # Plan before any Cycles time is spent, so an unresolvable map fails immediately
    # rather than after the material phase has already burned minutes. Material rows
    # are subtracted first: they belong to the material queue below, and handing them
    # to the projection planner made it reject the job outright ("Material channels
    # already use the dedicated Cycles material path") — every Route = Cycles bake
    # with a material row failed on that before it baked anything.
    projection_map_types = [
        map_type
        for map_type in prepared.effective_map_types
        if str(map_type or "").strip().upper() not in constants.MATERIAL_EFFECTIVE_MAP_TYPES
    ]
    plan = cycles_projection.plan_cycles_projection(prepared, map_types=projection_map_types)
    if plan.device_note:
        progress.warnings.append(plan.device_note)

    has_material_work = bool(prepared.material_bake_specs)
    state: dict = {
        "plan": plan,
        "index": 0,
        "errors": list(plan.errors),
        "progress": progress,
        "prepared": prepared,
        "project": project,
        "scene_settings": scene_settings,
        "started_at": time.monotonic(),
        "start_message": start_message,
        "cancel_requested": False,
        "silent": bool(silent),
        # Stage 1 of a Cycles-primary run is the material queue; the modal driver
        # idles until it drains, then steps the projection plan. Both stages drive
        # bpy.ops.object.bake, and Blender runs exactly one OBJECT_BAKE job, so they
        # are sequenced rather than overlapped.
        "material_pending": has_material_work,
        "material_started": False,
        "material_ran": has_material_work,
        # The modal driver's in-flight CyclesMapJob: one map, stepped a pass per tick.
        "active_job": None,
    }

    if (plan.steps or has_material_work) and _cycles_async_supported():
        _CYCLES_ASYNC_STATE = state
        try:
            launched = bpy.ops.master_baker.cycles_bake_step("INVOKE_DEFAULT")
        except Exception:
            _CYCLES_ASYNC_STATE = None
        else:
            if "CANCELLED" in set(launched or ()):
                # The driver refused the job (no window, no modal handler). Fall through
                # to the synchronous run below rather than leaving a session that never
                # steps and blocks every later Cycles bake.
                _CYCLES_ASYNC_STATE = None
            else:
                if not silent:
                    operator.report({"INFO"}, start_message or "Baking via Cycles...")
                return {"FINISHED"}

    # Headless / no-window fallback: the whole run is synchronous, including the
    # material queue. Nothing can redraw or cancel here, which is exactly why the
    # modal path above is preferred whenever a window exists.
    state["material_pending"] = False
    if has_material_work:
        state["errors"].extend(
            export.execute_material_bakes(prepared, context, owns_machine=True) or []
        )
    for index, step in enumerate(plan.steps):
        _cycles_step_progress(state, step, index)
        error = cycles_projection.run_cycles_projection_step(step, device=plan.device)
        if error:
            state["errors"].append(error)
        else:
            _record_cycles_step_output(state, step)
        state["index"] = index + 1
    return _finalize_cycles_primary_bake(operator, context, state)


def _start_cycles_material_stage(context, state: dict) -> None:
    """Kick off stage 1 of a Cycles-primary run: the async material queue.

    Failing to schedule is not fatal — the stage is simply marked done and the
    driver moves on to the projection plan, which is the same outcome as a job with
    no material rows.
    """
    state["material_started"] = True
    prepared = state["prepared"]

    def _on_progress(status, _state=state):
        _state["material_status"] = status
        _cycles_material_stage_progress(_state, status)

    def _on_complete(errors, _state=state):
        _state["errors"].extend(list(errors or []))
        _state["material_pending"] = False
        _state["material_status"] = None

    try:
        scheduled = export.execute_material_bakes_async(
            prepared,
            context,
            on_complete=_on_complete,
            on_progress=_on_progress,
            owns_machine=True,
        )
    except Exception as exc:  # noqa: BLE001 - a failed stage must not strand the driver
        state["errors"].append(f"Material bake queue failed to start: {exc}")
        scheduled = False
    if not scheduled:
        state["material_pending"] = False


def _cycles_material_stage_progress(state: dict, status) -> None:
    """Mirror the material queue onto the same surfaces the map stepper drives.

    Without this the HUD sits on the projection plan's 0% for the whole material
    stage, which is the longest part of a Cycles-primary run.
    """
    project = state["project"]
    progress = state["progress"]
    total = max(1, int(getattr(status, "total", 1) or 1))
    done = max(0, int(getattr(status, "done", 0) or 0))
    channel = str(getattr(status, "channel", "") or "")
    message = status.label
    if channel:
        message = f"{message}: {channel.title()}"
    progress.message = message
    progress.active_group = str(getattr(status, "group_name", "") or "")
    progress.active_map = channel
    # Stage 1 owns the first half of the bar when there is a projection plan behind
    # it; on a material-only job it owns all of it.
    span = 50.0 if state["plan"].steps else 100.0
    progress.percent = min(span, span * done / total)
    try:
        project.last_status_message = message
        project.last_active_group = progress.active_group
        project.last_active_map = channel
        project.last_progress_percent = progress.percent
        state["scene_settings"].status_message = message
    except Exception:
        pass
    try:
        _tag_bake_progress_regions()
    except Exception:
        pass
    _poke_statusbar_redraw()


def _finalize_cycles_primary_bake(operator, context, state: dict):
    """Shared success/failure tail for both the modal and synchronous Cycles paths."""
    plan = state["plan"]
    project = state["project"]
    scene_settings = state["scene_settings"]
    prepared = state["prepared"]
    progress = state["progress"]
    errors = list(state["errors"])
    cancelled = bool(state.get("cancel_requested"))
    silent = bool(state.get("silent"))

    if _PER_GROUP_MERGE_STATE is not None:
        # A per-group pass routed through Cycles finishes here, not in the backend
        # poll, so its composite has to run here too or the state strands and a
        # later backend bake composites stale backups over fresh outputs.
        try:
            _finish_per_group_merge(project, succeeded=not cancelled and not errors)
        except Exception:
            pass

    if cancelled or errors:
        # Dependency ordering: neither a cancel nor a failure may release stage 2 —
        # the material rows would re-read stage 1's stale outputs.
        _clear_pending_material_phase()

    if cancelled:
        done = int(state.get("index", 0))
        progress.status = constants.STATUS_CANCELLED
        progress.message = f"Bake cancelled (Cycles), {done}/{len(plan.steps)} maps written"
        progress.errors = []
        export.apply_progress_to_project(project, progress, merge_existing=True)
        with dirty_tracker.suppress():
            runtime.refresh_project_output_images(project)
        map_rebuild.clear_active_bake_map_types(project)
        project.last_status_message = progress.message
        scene_settings.status_message = constants.STATUS_CANCELLED
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        if not silent:
            operator.report({"INFO"}, progress.message)
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        return {"CANCELLED"}

    if errors:
        progress.errors = errors
        progress.status = constants.STATUS_FAILED
        progress.message = errors[0]
        export.apply_progress_to_project(project, progress, merge_existing=True)
        map_rebuild.clear_active_bake_map_types(project)
        _report_backend_failure(operator, project, progress, progress_path=prepared.progress_path)
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    progress.errors = []
    progress.status = constants.STATUS_COMPLETE
    progress.message = "Bake complete (Cycles)"
    progress.percent = 100.0
    detail_warnings = material_detail.apply_workspace_material_detail(prepared.workspace_path)
    progress.warnings.extend(detail_warnings)
    progress.warnings.extend(derived_outputs.apply_workspace_derived_outputs(prepared.workspace_path, progress))
    export.apply_progress_to_project(project, progress, merge_existing=True)
    with dirty_tracker.suppress():
        runtime.refresh_project_output_images(project)
        _sync_preview_material_for_project(context.scene, project)

    _finalize_successful_bake_state(project)
    dirty_tracker.set_post_bake_cooldown()
    map_rebuild.clear_active_bake_map_types(project)
    duration_text = _format_bake_duration(time.monotonic() - float(state.get("started_at", 0.0)))
    final_message = (
        f"{progress.message} ({duration_text})" if duration_text else progress.message
    )
    project.last_status_message = final_message
    scene_settings.status_message = final_message
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
    start_message = state.get("start_message") or ""
    if not silent:
        operator.report({"INFO"}, start_message if start_message else final_message)
    runtime.release_workspace_geometry_transports(prepared.workspace_path)
    storage_cleanup.slim_job_workspace(prepared.workspace_path)
    _consume_pending_material_phase(succeeded=True)
    return {"FINISHED"}


def _start_cycles_handoff_async(
    context, project, progress, prepared, *, map_types=None, on_complete=None
) -> str:
    """Hand the post-failure Cycles retry to the modal driver.

    Returns "" once the driver is running. `_CYCLES_HANDOFF_NO_STEPS` means the plan had
    nothing to bake; any other string is a launch failure the caller should surface.
    """
    global _CYCLES_ASYNC_STATE

    if _CYCLES_ASYNC_STATE is not None:
        return "The automatic Cycles retry was skipped: another Cycles bake is already running"
    try:
        plan = cycles_projection.plan_cycles_projection(prepared, map_types=map_types)
    except Exception as exc:  # noqa: BLE001 - a planning crash must not freeze the retry
        return f"The automatic Cycles retry could not be planned: {exc}"
    if not plan.steps:
        return _CYCLES_HANDOFF_NO_STEPS

    progress.warnings = list(getattr(progress, "warnings", None) or [])
    if plan.device_note:
        progress.warnings.append(plan.device_note)
    state: dict = {
        "plan": plan,
        "index": 0,
        "errors": list(plan.errors),
        # The GPU bake's own progress object: the retry edits it in place, exactly as the
        # synchronous driver did, so the caller sees one bake with one outcome.
        "progress": progress,
        "prepared": prepared,
        "project": project,
        "scene_settings": getattr(getattr(context, "scene", None), "fyr_baker_settings", None),
        "started_at": time.monotonic(),
        "start_message": "",
        "cancel_requested": False,
        # The retry reports through the failed bake's own status surfaces, not a second
        # round of operator reports.
        "silent": True,
        # A recovery retries projection maps only; material rows have their own Cycles route.
        "material_pending": False,
        "material_started": False,
        "material_ran": False,
        "handoff": True,
        # The modal driver's in-flight CyclesMapJob: one map, stepped a pass per tick.
        "active_job": None,
        "on_complete": on_complete,
        "finalize": _finalize_cycles_handoff_bake,
    }
    _CYCLES_ASYNC_STATE = state
    try:
        result = bpy.ops.master_baker.cycles_bake_step("INVOKE_DEFAULT")
    except Exception as exc:  # noqa: BLE001 - report the failure, never fall back to a freeze
        _CYCLES_ASYNC_STATE = None
        return f"The automatic Cycles retry could not be started: {exc}"
    if "CANCELLED" in set(result or ()):
        _CYCLES_ASYNC_STATE = None
        return "The automatic Cycles retry could not be started"
    return ""


def _finalize_cycles_handoff_bake(operator, context, state: dict):
    """Completion tail for the async Cycles retry after a GPU failure.

    Leaves the GPU progress object in the state the synchronous retry would have left it
    in, then runs the caller's deferred post-processing. Separate from
    `_finalize_cycles_primary_bake` because a recovery is a tail of someone else's bake:
    the caller owns the project bookkeeping, the workspace and the final message.
    """
    project = state["project"]
    progress = state["progress"]
    errors = list(state.get("errors") or [])
    cancelled = bool(state.get("cancel_requested"))
    recovered = not cancelled and not errors

    if recovered:
        _apply_cycles_handoff_success(project, progress)
    else:
        _apply_cycles_handoff_failure(project, progress, errors, cancelled=cancelled)

    on_complete = state.get("on_complete")
    if callable(on_complete):
        try:
            on_complete(recovered, operator, context)
        except Exception:  # noqa: BLE001 - a broken tail must not strand the modal driver
            traceback.print_exc()

    scene_settings = state.get("scene_settings")
    if scene_settings is not None:
        try:
            scene_settings.status_message = project.last_status_message
        except Exception:
            pass
    try:
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None), window=getattr(context, "window", None)
        )
    except Exception:
        pass
    _poke_statusbar_redraw()
    return {"FINISHED"} if recovered else {"CANCELLED"}


def _on_bg_prepare_depsgraph_update(scene, depsgraph) -> None:  # noqa: ARG001
    """Always-on depsgraph handler: debounces a speculative PREPARE when mesh objects
    change (geometry or transform edits invalidate the prepared-group cache key, so
    without a fresh PREPARE the next bake pays a full cold prepare).

    Bake-SETTINGS changes (AA, resolution, margin, ...) never reach this handler —
    custom-property writes produce no depsgraph updates at all (verified
    empirically) — so those re-fire the PREPARE from their property update
    callbacks in properties.py (_schedule_settings_prepare) instead.

    Runs outside of live-bake sessions (dirty_tracker handles those separately).
    Lightweight — exits fast on the common path where nothing bake-relevant changed.
    """
    global _BG_PREPARE_DEBOUNCE_REGISTERED

    if time.monotonic() < _BG_PREPARE_SUPPRESS_UNTIL:
        return  # Ignore depsgraph churn caused by our own speculative prepare
    if properties.peek_active_project(scene) is None:
        return
    if runtime.active_bake_snapshot() is not None:
        return
    if not runtime.is_bake_worker_warm():
        return
    if dirty_tracker.is_session_active():
        return  # Live bake — dirty_tracker owns rebaking there

    if not _depsgraph_has_bake_relevant_mesh_edit(depsgraph):
        return

    if _BG_PREPARE_DEBOUNCE_REGISTERED:
        return  # Timer already queued

    _BG_PREPARE_DEBOUNCE_REGISTERED = True
    try:
        bpy.app.timers.register(_bg_prepare_debounce_fired, first_interval=1.0)
    except Exception:
        _BG_PREPARE_DEBOUNCE_REGISTERED = False


def _bg_prepare_debounce_fired() -> None:
    """Timer callback: attempt a speculative PREPARE after the 1s debounce window."""
    global _BG_PREPARE_DEBOUNCE_REGISTERED
    _BG_PREPARE_DEBOUNCE_REGISTERED = False
    if runtime.is_prepare_in_flight():
        # A PREPARE is already running; mark stale so _prepare_ready_check_timer
        # re-fires the callback with the up-to-date scene when READY arrives.
        runtime.flag_bg_prepare_stale()
        return None
    _do_speculative_prepare()
    return None


def _dismiss_setup_progress() -> None:
    """Hide the viewport setup/bake HUD if it is currently showing.

    Uses ``sys.modules`` so the common speculative-prepare decline path does not
    import drawing modules just to check whether the overlay is up.
    """
    module = sys.modules.get(f"{__package__}.setup_progress")
    if module is None:
        return
    try:
        is_active = getattr(module, "is_active", None)
        if callable(is_active) and not is_active():
            return
        end_fn = getattr(module, "end", None)
        if callable(end_fn):
            end_fn()
    except Exception:
        pass


def _note_high_warm_failure(object_name: str, exc: BaseException) -> None:
    """Skip a high mesh whose warm export failed; stop warming after a memory error."""
    global _HIGH_WARM_OUT_OF_MEMORY
    _HIGH_WARM_FAILED[str(object_name)] = f"{exc.__class__.__name__}: {exc}"
    if isinstance(exc, MemoryError):
        _HIGH_WARM_OUT_OF_MEMORY = True
    print(f"[FyrBaker] Skipped preparing '{object_name}' ahead of the bake: {exc}")


def _end_high_warm_status() -> None:
    """Release the status-bar text the per-tick high-mesh warm chain owns."""
    global _HIGH_WARM_STATUS_ACTIVE, _HIGH_WARM_ANNOUNCED
    _HIGH_WARM_ANNOUNCED = None
    if not _HIGH_WARM_STATUS_ACTIVE:
        return
    _HIGH_WARM_STATUS_ACTIVE = False
    try:
        workspace = getattr(getattr(bpy, "context", None), "workspace", None)
        if workspace is not None:
            workspace.status_text_set(None)
    except Exception:
        pass


def _do_speculative_prepare() -> None:
    """Export a probe job file and send PREPARE to the warm worker without running a bake.

    Called by the speculative-prepare timer after the worker spawns (or when a new
    blend file is loaded while the worker is already warm).  Always does a fresh
    speculative export so the PREPARE cache key matches the subsequent bake.
    """
    # Imported after the bail-out guards below: setup_progress pulls in Blender's
    # drawing modules, and the common case for this function is to decline.
    if runtime.active_bake_snapshot() is not None:
        _dismiss_setup_progress()
        return
    if export.active_material_bake_status() is not None:
        # The backend can finish long before the addon-side Cycles material queue
        # does, and that queue is still part of the running bake. Exporting a probe
        # job now would evaluate the depsgraph while MaterialBakeSession has objects
        # temporarily unhidden and bake nodes injected, and it overwrites
        # project.last_job_id -- which every progress and completion callback looks
        # the project up by, so the run would go dark mid-flight and never finish in
        # the UI while Blender kept baking.
        _dismiss_setup_progress()
        return
    if runtime.is_prepare_in_flight():
        # A PREPARE is already running in the worker. Exporting a superseding
        # job here would release the workspace that in-flight PREPARE is still
        # reading — the worker then fails it with "Failed to open file" and its
        # stray ERR reply used to desync every later bake's reply matching by
        # one (bakes "failing"/"finishing" instantly with the previous job's
        # result). Mark stale instead: _prepare_ready_check_timer re-invokes
        # this callback on READY with the up-to-date scene.
        runtime.flag_bg_prepare_stale()
        _dismiss_setup_progress()
        return
    context = getattr(bpy, "context", None)
    if context is None:
        _dismiss_setup_progress()
        return
    scene = getattr(context, "scene", None)
    if scene is None:
        _dismiss_setup_progress()
        return
    project = properties.peek_active_project(scene)
    if project is None:
        _dismiss_setup_progress()
        return

    # Nothing the worker prepares has changed since it last replied READY, so a
    # fresh export would hand it byte-identical work. Skipping is not just a
    # saving: every trigger that fires on an unchanged scene (depsgraph churn
    # from our own export, a membership refresh, the post-READY stale refire)
    # would otherwise re-arm the next one and the panel would sit at "Warming up
    # scene cache" indefinitely while each pass re-exports on the main thread.
    scene_signature = export.speculative_prepare_signature(project)
    if scene_signature and scene_signature == runtime.prepared_scene_signature():
        # An edit-then-undo can land here with the per-tick high-mesh warm chain
        # part way through; it owns the status-bar text, so hand it back rather
        # than leaving "Setting up bake project" pinned to the footer.
        _end_high_warm_status()
        _dismiss_setup_progress()
        return

    from . import setup_progress

    loading_label = runtime.prepare_in_flight_status_label()

    def _status_shows_completed_bake(message: str) -> bool:
        # Completion messages end with a duration suffix, e.g. "Finished baking
        # (5.5s)" / "Bake complete (1.2m)". A post-bake speculative prepare must
        # not clobber that with "Loading scene caches..." — the prewarm is
        # already surfaced by the warming-up indicator, and the completion
        # message is the one the artist is waiting to see.
        return bool(re.search(r"\(\d+(?:\.\d+)?[sm]\)$", str(message or "").strip()))

    suppress_hud = _status_shows_completed_bake(getattr(project, "last_status_message", ""))

    def _set_loading_status():
        if not _status_shows_completed_bake(getattr(project, "last_status_message", "")):
            project.last_status_message = loading_label
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is not None and not _status_shows_completed_bake(
            getattr(settings, "status_message", "")
        ):
            settings.status_message = loading_label
        try:
            overlays.tag_redraw_all_view3d(scene=scene)
        except Exception:
            pass

    # Always do a fresh speculative export so the PREPARE cache key matches the
    # subsequent bake exactly.  Reusing last_bake_job_path across sessions is
    # unsafe: after a rename or format change the persisted path references stale
    # mesh files (e.g. .mbmesh before the FyrBaker rename), causing PREPARE to
    # prime the session cache under a different key than the actual bake.  With
    # the committed .fymesh export cache the re-export is fast (manifest lookup,
    # no large-file re-hash), so the one-off shortcut is not worth the risk.
    #
    # Use shared memory so the mesh binary packing is identical to the actual
    # bake, ensuring the backend's resident-cache key matches on the next RUN.
    # Amortize cold high-mesh captures ONE OBJECT PER TICK before the heavy
    # export below: capturing a multi-million-poly evaluated mesh blocks the UI
    # for seconds (measured 9.8s for a fresh 4-high-mesh scene in one gulp
    # right after Auto-Build — the "few seconds of loading" users see). Warming
    # them across timer invocations keeps Blender responsive between meshes and
    # shows progress in the status bar; once everything is warm the export
    # proper costs milliseconds.
    global _HIGH_WARM_STATUS_ACTIVE
    try:
        high_objs = []
        seen_names = set()
        for warm_group in project.groups:
            for warm_slot in properties.effective_high_mesh_slots(warm_group):
                warm_obj = getattr(warm_slot, "object_ref", None)
                if warm_obj is None or getattr(warm_obj, "type", "") != "MESH":
                    continue
                if warm_obj.name in seen_names:
                    continue
                seen_names.add(warm_obj.name)
                high_objs.append(warm_obj)
        cold_objs = (
            []
            if indexed_geometry.enabled() or _HIGH_WARM_OUT_OF_MEMORY
            else [
                o
                for o in high_objs
                if o.name not in _HIGH_WARM_FAILED and not high_mesh_cache.high_mesh_ref_is_warm(o)
            ]
        )
    except Exception:
        cold_objs = []
    if cold_objs and not runtime.speculative_prepare_allows_cold_high_warm():
        # Settings-triggered prepare must not freeze the UI capturing cold highs
        # (pottery-scale: multi-second Not Responding). Skip; bake/membership
        # paths still warm geometry when the user expects a wait.
        _dismiss_setup_progress()
        return
    if cold_objs:
        global _HIGH_WARM_ANNOUNCED
        warm_obj = cold_objs[0]
        done = len(high_objs) - len(cold_objs)
        workspace = getattr(context, "workspace", None)
        if _HIGH_WARM_ANNOUNCED != warm_obj.name:
            # Announce-tick: paint the centered "please wait" overlay + status
            # text and yield BEFORE the blocking capture — painting in the same
            # tick as the work would only make them visible after the freeze
            # they are meant to explain.
            _HIGH_WARM_ANNOUNCED = warm_obj.name
            try:
                detail = f"Preparing {warm_obj.name} ({done + 1}/{len(high_objs)})…"
                if not suppress_hud:
                    setup_progress.begin("Setting up bake project", detail)
                    if workspace is not None:
                        workspace.status_text_set(f"Setting up bake project: {detail}")
                        _HIGH_WARM_STATUS_ACTIVE = True
                    overlays.tag_redraw_all_view3d(scene=scene)
            except Exception:
                pass
            runtime.schedule_speculative_prepare(delay=0.05, restart=True)
            return
        _HIGH_WARM_ANNOUNCED = None
        _suppress_bg_prepare()
        try:
            depsgraph = context.evaluated_depsgraph_get()
            high_mesh_cache.resolve_high_mesh_ref(warm_obj, depsgraph)
        except Exception as exc:
            _note_high_warm_failure(warm_obj.name, exc)
        finally:
            _suppress_bg_prepare()
        try:
            overlays.tag_redraw_all_view3d(scene=scene)
        except Exception:
            pass
        # Come back next tick for the next mesh (or, once warm, the export).
        runtime.schedule_speculative_prepare(delay=0.05, restart=True)
        return
    if runtime.speculative_prepare_allows_cold_high_warm() and _step_automatic_cage_fit(
        context, project, _SPECULATIVE_CAGE_FIT_STATE, None
    ):
        _HIGH_WARM_STATUS_ACTIVE = True
        runtime.schedule_speculative_prepare(delay=0.05, restart=True)
        return
    _SPECULATIVE_CAGE_FIT_STATE.clear()
    if _HIGH_WARM_STATUS_ACTIVE and _HIGH_WARM_ANNOUNCED != "__finalize__":
        # Meshes are warm; the export below still runs the cage fit + job write
        # (up to a couple of seconds cold). Announce it on its own tick so the
        # overlay text is on screen while it blocks.
        _HIGH_WARM_ANNOUNCED = "__finalize__"
        try:
            setup_progress.begin("Setting up bake project", "Writing the bake job…")
            overlays.tag_redraw_all_view3d(scene=scene)
        except Exception:
            pass
        runtime.schedule_speculative_prepare(delay=0.05, restart=True)
        return
    if _HIGH_WARM_STATUS_ACTIVE:
        _HIGH_WARM_STATUS_ACTIVE = False
        _HIGH_WARM_ANNOUNCED = None
        try:
            workspace = getattr(context, "workspace", None)
            if workspace is not None:
                workspace.status_text_set(None)
        except Exception:
            pass
    if not runtime.is_bake_worker_warm():
        # Worker still spawning/restarting; the prepare re-fires when it is
        # ready. Don't leave the setup popup hanging over an idle viewport.
        try:
            if setup_progress.is_active():
                setup_progress.end()
        except Exception:
            pass
        return
    # Suppress the always-on depsgraph handler across the whole prepare: exporting a
    # job mutates the scene (cage create+remove, mesh evaluation, property writes),
    # which would otherwise be misread as a user edit and re-arm this prepare forever.
    _suppress_bg_prepare()
    prior_project_status = str(getattr(project, "last_status_message", "") or "")
    try:
        prepared = export.prepare_bake_job(
            context,
            project,
            preserve_latest_outputs=True,
            use_shared_memory=True,
            use_binary_job_transport=True,
            cancel_check=_capture_cancel_requested,
            # Main-thread timer: skip bake-only export work that would freeze the UI.
            speculative=True,
        )
        # prepare_bake_job stamps STATUS_EXPORTED on the project as a side
        # effect; for this background prepare that would wipe a completion
        # message the artist is still reading — put it back before the guarded
        # loading-status write below evaluates the current message.
        if _status_shows_completed_bake(prior_project_status):
            project.last_status_message = prior_project_status
        job_maps = getattr(getattr(prepared, "job", None), "maps", None)
        if job_maps is not None and not any(getattr(item, "enabled", True) for item in job_maps):
            # Every selected output goes through Cycles, so the worker has nothing to
            # warm and would refuse the job. That refusal used to count as a prewarm
            # failure: it restarted the worker, turned prewarm off for the session and
            # replaced the status line. Remember the scene so an unchanged one is not
            # exported again on the next trigger.
            project.last_status_message = prior_project_status
            runtime.note_scene_needs_no_prepare(scene_signature)
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
            return
        project.last_bake_job_path = str(prepared.job_path)
        runtime.set_speculative_prepare_workspace(prepared.workspace_path)
        if runtime.send_prepare_for_job(prepared.job_path, scene_signature=scene_signature):
            _set_loading_status()
        else:
            # PREPARE wasn't sent (e.g. already issued for same path) — free immediately
            runtime.set_speculative_prepare_workspace(None)
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
    except Exception:
        pass
    finally:
        # The setup overlay (begun by the warm chain above) must never outlive
        # the export it was explaining.
        try:
            if setup_progress.is_active():
                setup_progress.end()
        except Exception:
            pass
        # Re-arm the window so the deferred depsgraph flush that lands after this
        # call returns is still ignored.
        _suppress_bg_prepare()


def _trigger_dirty_rebake() -> None:
    """Called by the dirty-check timer when pending dirty changes need rebaking."""
    global _DIRTY_REBAKE_SNAPSHOT

    if not dirty_tracker.is_session_active():
        return
    if not dirty_tracker.has_pending_dirty():
        return
    if not dirty_tracker.debounce_elapsed():
        return
    snapshot = runtime.active_bake_snapshot()
    if snapshot is not None and snapshot.running:
        return

    context = bpy.context
    if context is None:
        return
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    project = _sync_live_bake_runtime(scene)
    if project is None:
        return
    if _CYCLES_ASYNC_STATE is not None:
        # A Cycles-primary bake has no runtime snapshot, so neither the dirty
        # timer nor the snapshot guard above sees it: every 0.25 s tick re-ran a
        # full prepare_bake_job, overwrote the in-flight bake's map/group
        # bookkeeping and then bailed. Stand down until it finishes.
        return
    if export.active_material_bake_status() is not None or _DEFERRED_MATERIAL_BACKEND_RESULTS:
        # Same reason the Bake button refuses here: the previous bake's Cycles
        # material queue outlives its backend job, so snapshot.running is already
        # False while that queue still owns the temporary materials and the output
        # files. A rebake started now also replaces _DIRTY_REBAKE_SNAPSHOT, and the
        # older bake's deferred completion then clears dirty entries this one has
        # not written yet -- stale maps reported as clean.
        return
    if export.refuse_temporary_output_bake(project):
        # Recovered autosave session: the interactive Bake button already
        # explains the refusal; the background timer just stands down instead
        # of repeating the report every debounce tick.
        return

    dirty_snapshot = dirty_tracker.get_pending_dirty()
    if not dirty_snapshot:
        return
    dirty_object_snapshot = dirty_tracker.get_pending_dirty_objects()

    enabled = set(map_rebuild.enabled_map_types(project))
    selected_dirty_snapshot = dirty_rules.select_dirty_rebake_batch(dirty_snapshot, enabled)
    if not selected_dirty_snapshot:
        for group_name, map_types in dirty_snapshot.items():
            disabled_map_types = set(map_types) - enabled
            if disabled_map_types:
                dirty_tracker.clear_dirty(group_name, disabled_map_types)
        return

    selected_map_types = sorted(next(iter(selected_dirty_snapshot.values())))
    selected_group_names = sorted(selected_dirty_snapshot.keys())
    # Occlude Other Groups rows need every group in the job, or they lose those occluders.
    if set(selected_map_types) & set(dirty_rules.world_occlusion_dirty_map_types(getattr(project, "maps", []))):
        selected_group_names = sorted(set(selected_group_names) | set(map_rebuild.group_names(project)))

    if not selected_map_types or not selected_group_names:
        return

    try:
        prepared = export.prepare_bake_job(
            context,
            project,
            map_types=selected_map_types,
            group_names=selected_group_names,
            dirty_object_names_by_group={
                group_name: set(dirty_object_snapshot.get(group_name, set()))
                for group_name in selected_group_names
            },
            preserve_latest_outputs=True,
            use_shared_memory=True,
            use_binary_job_transport=True,
            cancel_check=_capture_cancel_requested,
        )
        map_rebuild.record_active_bake_map_types(project, selected_map_types)
        map_rebuild.record_active_bake_group_names(project, selected_group_names)
        try:
            project.last_bake_job_path = str(prepared.job_path)
            project.last_bake_workspace_path = str(prepared.workspace_path)
            project.last_bake_job_id = str(getattr(prepared.job, "job_id", "") or "")
            project.last_bake_cache_state = runtime.classify_bake_cache_state(prepared.job_path)
        except Exception:
            pass
        _DIRTY_REBAKE_SNAPSHOT = selected_dirty_snapshot
        try:
            active_backend = bake_backends.resolve_active_render_backend(force_refresh=True)
        except RuntimeError:
            _DIRTY_REBAKE_SNAPSHOT = None
            dirty_tracker.clear_all_dirty()
            return
        # Rows this job left out for another colour stream bake right after it; their
        # dirty flags clear with this job's, so they must not be dropped.
        _arm_color_stream_stages(project, prepared, selected_group_names, live_bake_mode="preserve")
        if not prepared.effective_map_types and not prepared.material_bake_specs and prepared.derived_outputs:
            # Only Wireframe rows are dirty: draw them here, no backend job to launch.
            class _QuietReporter:
                def report(self, _type, _message):
                    return None

            _run_derived_only_bake(_QuietReporter(), context, project, scene.fyr_baker_settings, prepared)
            for group_name, maps in (selected_dirty_snapshot or {}).items():
                dirty_tracker.clear_dirty(group_name, maps)
            _DIRTY_REBAKE_SNAPSHOT = None
            return
        if active_backend.backend_id == "cycles":
            settings = getattr(scene, "fyr_baker_settings", None)
            if settings is None:
                _DIRTY_REBAKE_SNAPSHOT = None
                return
            # Live rebake reuses the primary Cycles helper. A stand-in reporter keeps
            # the *launch* quiet; `silent` keeps the modal driver's completion report
            # quiet too, so live baking does not spam the info bar every edit.
            class _SilentReporter:
                def report(self, _type, _message):
                    return None

            _run_cycles_primary_bake(
                _SilentReporter(),
                context,
                project,
                settings,
                prepared,
                start_message="Live Bake (Cycles)",
                reason=active_backend.reason,
                silent=True,
            )
            _DIRTY_REBAKE_SNAPSHOT = None
            return
        runtime.launch_bake_job_background(
            prepared.job_path,
            prepared.progress_path,
            job_id=prepared.job.job_id,
            selected_map_types=prepared.effective_map_types,
        )
        _remember_cycles_handoff_prepared(prepared)
        # The backend projects geometry on the GPU while Blender evaluates any
        # material-only fallback/detail layers on the CPU.
        # Poll before the material scheduler: a raise from it used to leave the
        # launched backend job with no poll timer, so _ACTIVE_BAKE never cleared
        # and every later bake refused with "Another bake is already running".
        runtime.start_background_polling(_handle_background_bake_update)
        if prepared.material_bake_specs:
            export.execute_material_bakes_async(
                prepared,
                context,
                on_complete=lambda errors, path=prepared.workspace_path: _handle_async_material_complete(path, errors),
                on_progress=_handle_async_material_progress,
            )
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = constants.STATUS_BAKING
        project.last_status_message = constants.STATUS_BAKING
        overlays.tag_redraw_all_view3d(scene=scene, window=getattr(context, "window", None))
    except Exception:
        _DIRTY_REBAKE_SNAPSHOT = None
        dirty_tracker.clear_all_dirty()


def _format_bake_duration(seconds: float) -> str:
    """Compact elapsed bake time (see runtime.format_duration for the canonical impl)."""
    return runtime.format_duration(seconds)


def _append_bake_duration_to_status(project, snapshot) -> None:
    """Append the total wall-clock bake time to the user-visible status message.

    The panel reports e.g. "Bake complete (1m 23s)" once the run is done. The raw
    duration is persisted too so the panel can show a stable "Last bake" readout
    independent of the status-message string.
    """
    try:
        start_time = float(getattr(snapshot, "start_time", 0.0) or 0.0)
        if start_time <= 0.0:
            return
        elapsed_seconds = max(0.0, time.monotonic() - start_time)
        try:
            project.last_bake_duration_seconds = elapsed_seconds
        except Exception:
            pass
        duration_text = _format_bake_duration(elapsed_seconds)
        if not duration_text:
            return
        current = str(getattr(project, "last_status_message", "") or "")
        if duration_text not in current:
            project.last_status_message = (
                f"{current} ({duration_text})" if current else duration_text
            )
    except Exception:
        pass


def _deferred_poll_handoff_completion(project, progress, snapshot, *, dirty_snapshot):
    """Build the tail the background-poll handler owes a bake whose Cycles retry is
    still running.

    The poll handler cannot finish a bake it no longer knows the outcome of, so
    everything it would have done between "did the bake succeed" and "the bake is over"
    is captured here and replayed once the modal driver completes. It mirrors that
    handler's own branches, so an async retry leaves the project exactly where the
    synchronous retry left it.
    """

    def _complete(recovered: bool, operator, context) -> None:  # noqa: ARG001 - operator unused here
        global _PENDING_EXPORT_AFTER_BAKE

        export.apply_progress_to_project(project, progress, merge_existing=True)
        with dirty_tracker.suppress():
            try:
                runtime.refresh_project_output_images(project)
            except Exception:
                pass
            try:
                _sync_preview_material_for_project(getattr(context, "scene", None), project)
            except Exception:
                pass

        if recovered:
            # A clean bake means the post-OOM re-prewarm (if any) did its job; drop the
            # recovery marker so the label reverts to normal next time.
            runtime.clear_prewarm_oom_recovery()
            if dirty_snapshot is not None:
                # Partial incremental bake -- only clear what we actually baked.
                _update_bake_state_partial(project, dirty_snapshot)
                for group_name, maps in dirty_snapshot.items():
                    dirty_tracker.clear_dirty(group_name, maps)
            else:
                map_rebuild.record_bake_state(project)
                dirty_tracker.clear_all_dirty()
            dirty_tracker.set_post_bake_cooldown()
            _rebase_live_reproject(project)
        else:
            # Keep dirty state so the user can retry, and show the canonical failure
            # status rather than the raw error text apply_progress_to_project placed in
            # last_status_message.
            failed_status = getattr(progress, "status", None)
            if failed_status not in {
                constants.STATUS_FAILED,
                constants.STATUS_CANCELLED,
                constants.STATUS_CANCELLING,
            }:
                failed_status = constants.STATUS_FAILED
            project.last_status_message = failed_status
            if diagnostics.failure_is_out_of_memory(progress):
                raw_oom = str(
                    getattr(progress, "message", "")
                    or (progress.errors[0] if progress.errors else "")
                )
                restarted = _recover_backend_from_out_of_memory()
                project.last_error_summary = diagnostics.out_of_memory_summary(
                    raw_oom, restarted=restarted
                )
            elif failed_status == constants.STATUS_FAILED:
                _apply_failure_guidance_summary(project, progress)
            warning = str(getattr(project, "last_warning_summary", "") or "")
            if progress.errors and ", using CPU fallback" in warning:
                project.last_warning_summary = warning.replace(
                    ", using CPU fallback", ", CPU fallback also failed"
                )
            if progress.errors and cycles_projection.progress_requests_cycles_handoff(progress):
                project.last_warning_summary = (
                    str(project.last_warning_summary or "")
                    + (", " if project.last_warning_summary else "")
                    + "Cycles fallback could not recover all maps"
                ).strip(", ")

        map_rebuild.clear_active_bake_map_types(project)
        _append_bake_duration_to_status(project, snapshot)

        staged_second_phase = False
        try:
            staged_second_phase = _consume_pending_material_phase(succeeded=recovered)
        except Exception:
            _clear_pending_material_phase()
        if _PENDING_EXPORT_AFTER_BAKE and not staged_second_phase:
            _PENDING_EXPORT_AFTER_BAKE = False
            if recovered:
                try:
                    bpy.app.timers.register(_run_pending_export_after_bake, first_interval=0.0)
                except Exception:
                    pass

    return _complete


def _deferred_sync_handoff_completion(project, progress, prepared, scene_settings, *, started_at):
    """Build the tail the foreground bake path owes a Cycles retry that went modal.

    This is the no-background-polling bake path, so it normally finishes its own bake
    inline. When a window is present the retry still steps through the modal driver, and
    everything after the handoff call moves here.
    """

    def _complete(recovered: bool, operator, context) -> None:
        if recovered:
            try:
                progress.warnings.extend(
                    material_detail.apply_workspace_material_detail(prepared.workspace_path)
                )
            except Exception:
                pass
            progress.warnings.extend(
                derived_outputs.apply_workspace_derived_outputs(prepared.workspace_path, progress)
            )
        export.apply_progress_to_project(project, progress, merge_existing=True)
        with dirty_tracker.suppress():
            try:
                runtime.refresh_project_output_images(project)
            except Exception:
                pass
            try:
                _sync_preview_material_for_project(getattr(context, "scene", None), project)
            except Exception:
                pass

        if not recovered:
            _clear_pending_material_phase()
            map_rebuild.clear_active_bake_map_types(project)
            _report_backend_failure(
                operator, project, progress, progress_path=prepared.progress_path
            )
            storage_cleanup.slim_job_workspace(prepared.workspace_path)
            if scene_settings is not None:
                scene_settings.status_message = constants.STATUS_FAILED
            return

        _finalize_successful_bake_state(project)
        dirty_tracker.set_post_bake_cooldown()
        map_rebuild.clear_active_bake_map_types(project)
        base_message = progress.message or constants.STATUS_COMPLETE
        duration_text = _format_bake_duration(time.monotonic() - float(started_at or 0.0))
        final_message = f"{base_message} ({duration_text})" if duration_text else base_message
        project.last_status_message = final_message
        if scene_settings is not None:
            scene_settings.status_message = final_message
        try:
            operator.report({"INFO"}, final_message)
        except Exception:
            pass
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        # Stage 1 is on disk now, so hand stage 2 to a timer for the same settled-context
        # reasons the async path does.
        _consume_pending_material_phase(succeeded=True)

    return _complete


# Heavy progress-application throttle for _handle_background_bake_update: the
# poll ticks at up to 20Hz mid-bake; the heavy pass runs at most this often
# unless the produced-file count changes (a new map landed) or the bake ends.
_BAKE_PROGRESS_HEAVY_INTERVAL_SECONDS = 1.0
_BAKE_PROGRESS_HEAVY_THROTTLE = {"t": 0.0, "produced": -1}


def bake_then_export(operator, context, project, missing_types) -> set:
    """Bake ``missing_types``, then run the export -- the "Bake Missing Maps First" path.

    Called from the export operator when the template needs enabled maps this
    project has not baked. Reuses the normal bake pipeline (:func:`_run_bake`,
    targeted by map type) so validation, duplicate handling and worker reuse all
    behave exactly as a hand-triggered bake would.

    - **Async bakes** (the production path) return ``FINISHED`` as soon as the job
      is queued, so completion is handled in :func:`_handle_background_bake_update`:
      a flag is armed here and the export re-runs from that finished-branch.
    - **Synchronous bakes** finish inside :func:`_run_bake`, so the export runs
      inline right after, once, with ``skip_bake`` set.
    """
    global _PENDING_EXPORT_AFTER_BAKE
    _PENDING_EXPORT_AFTER_BAKE = False

    types_label = ", ".join(missing_types)
    result = _run_bake(
        operator,
        context,
        project,
        map_types=list(missing_types),
        start_message=f"Baking missing map(s) before export: {types_label}",
    )
    if "FINISHED" not in result:
        # Validation failed or another bake is running -- _run_bake already
        # reported why. Do not export half-baked sources.
        return result

    if runtime.background_polling_supported():
        _PENDING_EXPORT_AFTER_BAKE = True
        return {"FINISHED"}

    # Synchronous path: the bake is already on disk, so pack it now.
    return bpy.ops.master_baker.export_textures("EXEC_DEFAULT", skip_bake=True)


def _run_pending_export_after_bake() -> None:
    """Fire the deferred export once, from a timer with a valid context."""
    try:
        bpy.ops.master_baker.export_textures("EXEC_DEFAULT", skip_bake=True)
    except Exception as exc:
        # An operator ERROR report raised from a timer reaches no status bar, so the
        # export the artist asked for would fail with no trace at all.
        message = f"Export after bake failed: {str(exc).strip() or type(exc).__name__}"
        print(f"[MasterBaker] {message}")
        try:
            scene = bpy.context.scene
            settings = getattr(scene, "fyr_baker_settings", None)
            if settings is not None:
                settings.status_message = message
            project = properties.get_active_project(scene)
            if project is not None:
                project.last_status_message = message
        except Exception:
            pass


def _material_phase_status(stage: int, total: int = 2) -> str:
    """Stage marker for the existing status surfaces — no new UI."""
    what = "mesh maps" if stage == 1 else "materials"
    return f"Stage {stage}/{total}: {what}…"


def _arm_pending_material_phase(project, plan, selected_group_names, *, live_bake_mode: str) -> None:
    """Queue the staged phases while stage 1 runs.

    With a Normal row going first (plan.normal_first_map_uuid) stage 1 is that row
    alone; the mesh maps follow as their own entry, naming the row as their material
    normal source; the dependent materials, when any, come last.
    """
    normal_first = bool(plan.normal_first_map_uuid) and bool(plan.mesh_phase_map_uuids)
    total = 1 + (1 if normal_first else 0) + (1 if plan.deferred_map_uuids else 0)
    if normal_first:
        labels = []
        for map_uuid in plan.mesh_phase_map_uuids:
            map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
            if map_setting is not None:
                labels.append(properties.map_output_label(map_setting) or "map")
        _PENDING_MATERIAL_PHASES.append({
            "kind": "mesh_after_normal",
            "project_name": str(getattr(project, "name", "") or ""),
            "map_uuids": list(plan.mesh_phase_map_uuids),
            "group_names": list(selected_group_names or []),
            "reload_path_keys": [],
            "labels": labels,
            "live_bake_mode": str(live_bake_mode or "preserve"),
            "phase_label": f"Stage 2/{total}: mesh maps",
            "material_normal_source": plan.material_normal_source(),
        })
    if not plan.deferred_map_uuids:
        return
    _PENDING_MATERIAL_PHASES.append({
        "kind": "dependency",
        "project_name": str(getattr(project, "name", "") or ""),
        "map_uuids": list(plan.deferred_map_uuids),
        "group_names": list(selected_group_names or []),
        "reload_path_keys": list(plan.reload_path_keys),
        "labels": plan.deferred_labels(),
        "live_bake_mode": str(live_bake_mode or "preserve"),
        **({"phase_label": f"Stage {total}/{total}: materials"} if normal_first else {}),
    })


def _arm_per_group_material_phases(project, deferred_map_uuids, group_names) -> int:
    """Queue one native material bake per group (F8 multi-group split).

    The union program across a Combined texture set needs the per-texel MATSLOT
    sidecar, which cannot span groups; each group alone compiles native. Each
    queued entry re-runs the deferred MATERIAL rows for exactly one group, and
    prepare_bake_job (single group) routes them to the backend.
    """
    uuids = [str(u or "").strip() for u in (deferred_map_uuids or []) if str(u or "").strip()]
    names = [str(g or "").strip() for g in (group_names or []) if str(g or "").strip()]
    if not uuids or not names:
        return 0
    labels = []
    for map_uuid in uuids:
        map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        if map_setting is not None:
            labels.append(properties.map_output_label(map_setting) or "Material")
    total = len(names)
    configured = [str(getattr(group, "name", "") or "") for group in getattr(project, "groups", []) or []]
    # A bake of some of the project's groups: the shared files already hold the others, so
    # no pass writes a fresh base. Each merges its own texels and leaves the rest alone.
    subset = _is_user_group_subset(names, configured)
    for index, group_name in enumerate(names):
        _PENDING_MATERIAL_PHASES.append({
            "kind": "per_group",
            "project_name": str(getattr(project, "name", "") or ""),
            "map_uuids": list(uuids),
            "group_names": [group_name],
            "group_index": index,
            "previous_group_names": (
                [name for name in configured if name != group_name] if subset else names[:index]
            ),
            **(
                {
                    "merge_onto_base": True,
                    "exclude_group_names": [name for name in configured if name != group_name],
                }
                if subset
                else {}
            ),
            "reload_path_keys": [],
            "labels": list(labels),
            "live_bake_mode": "preserve",
            "phase_label": f"Baking materials natively: {group_name} ({index + 1}/{total})",
        })
    return total


def _arm_native_normal_group_phases(project, prepared) -> int:
    """Queue one native Normal bake per group whose material detail compiles alone.

    prepare_bake_job (``native_normal_group_phases``) found Normal rows whose detail does
    not compile as one program over every selected group, but does for some groups on
    their own, and left the hidden Cycles layer out for those. The job it prepared bakes
    their geometry Normal; each queued entry re-runs the row for exactly one group, which
    then compiles natively and rides the ordinary backend job. Its texels are composited
    over the geometry Normal already in the texture set's file.

    Unlike the F8 material split nothing earlier is the fresh base: stage 1 already
    holds every group, so every entry merges (``merge_onto_base``) and treats every other
    group of the set as a neighbour whose own texels it must not overwrite.
    """
    plans = getattr(prepared, "deferred_native_normal_groups", None) or {}
    if not plans:
        return 0
    project_group_names = [
        str(getattr(group, "name", "") or "")
        for group in getattr(project, "groups", []) or []
        if str(getattr(group, "name", "") or "").strip()
    ]
    queued = 0
    for map_uuid, names in plans.items():
        ordered = [name for name in project_group_names if name in set(names)]
        map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        label = (properties.map_output_label(map_setting) if map_setting is not None else "") or "Normal"
        for index, group_name in enumerate(ordered):
            _PENDING_MATERIAL_PHASES.append({
                "kind": "per_group",
                "project_name": str(getattr(project, "name", "") or ""),
                "map_uuids": [str(map_uuid)],
                "group_names": [group_name],
                "group_index": index + 1,
                "merge_onto_base": True,
                "previous_group_names": [name for name in project_group_names if name != group_name],
                "exclude_group_names": [name for name in project_group_names if name != group_name],
                "reload_path_keys": [],
                "labels": [label],
                "live_bake_mode": "preserve",
                "phase_label": f"Baking material detail natively: {group_name} ({index + 1}/{len(ordered)})",
                # Adds this group's texels to the composite the mesh maps read.
                "material_normal_source": {"composite": True},
            })
            queued += 1
    return queued


def _arm_color_stream_stages(project, prepared, group_names, *, live_bake_mode: str) -> int:
    """Queue one follow-up bake per colour stream the prepared job left out.

    A job carries one corner colour stream (color_stream), so a second Attribute row,
    or an Attribute row next to Vertex Color, bakes as its own stage right after this
    one. Queued at the FRONT: a deferred material stage that samples one of these
    outputs must find it already baked.
    """
    stages = [
        [str(u or "").strip() for u in (stage or []) if str(u or "").strip()]
        for stage in (getattr(prepared, "deferred_color_stream_stages", None) or [])
    ]
    stages = [stage for stage in stages if stage]
    if not stages:
        return 0
    entries = []
    for index, uuids in enumerate(stages):
        labels = []
        for map_uuid in uuids:
            map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
            if map_setting is not None:
                labels.append(
                    properties.effective_map_output_suffix(project, map_setting)
                    or properties.map_output_label(map_setting)
                    or "Attribute"
                )
        entries.append({
            "kind": "color_stream",
            "project_name": str(getattr(project, "name", "") or ""),
            "map_uuids": uuids,
            "group_names": list(group_names or []),
            "reload_path_keys": [],
            "labels": labels,
            "live_bake_mode": str(live_bake_mode or "preserve"),
            "phase_label": f"Attribute stage {index + 2}/{len(stages) + 1}",
        })
    _PENDING_MATERIAL_PHASES[:0] = entries
    return len(entries)


def _find_group_by_name(project, group_name: str):
    for group in getattr(project, "groups", []) or []:
        if str(getattr(group, "name", "") or "") == str(group_name or ""):
            return group
    return None


def _udim_tile_from_output_path(path) -> int:
    """The .NNNN tile a tokenized output file name carries, or 0 for an untiled file."""
    match = re.search(r"\.(\d{4})\.[^.]+$", str(path or ""))
    if not match:
        return 0
    tile = int(match.group(1))
    return tile if 1001 <= tile <= 9999 else 0


#: Rasterized group UV masks, memoized for the duration of one merge: the merge asks for
#: the same group's islands several times (own texels, neighbour union, texture-set union)
#: and each rasterization walks every low triangle in Python.
_MERGE_RASTER_CACHE: dict | None = None


def _group_uv_mask(group, width: int, height: int, *, dilate_texels: int = 0, udim_tile: int = 0):
    cache = _MERGE_RASTER_CACHE
    key = (str(getattr(group, "name", "") or ""), int(width), int(height), int(dilate_texels or 0), int(udim_tile or 0))
    if cache is not None and key in cache:
        return cache[key]
    mask = export.rasterize_group_low_uv_mask(
        group, width, height, dilate_texels=dilate_texels, udim_tile=udim_tile
    )
    if cache is not None:
        cache[key] = mask
    return mask


def _texture_set_island_union(project, group, width: int, height: int, udim_tile: int = 0):
    """Undilated UV islands of every group sharing this group's texture set.

    The composite may fill a texel outside all of these from the pass's own margin
    dilation; inside them, only the owning group's pass may write.
    """
    metadata_state = properties.group_metadata_state(group)
    set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip().casefold()
    union = None
    for candidate in getattr(project, "groups", []) or []:
        candidate_state = properties.group_metadata_state(candidate)
        candidate_key = (getattr(candidate_state, "texture_set_name", "") or "").strip().casefold()
        if candidate_key != set_key:
            continue
        mask = _group_uv_mask(candidate, width, height, udim_tile=udim_tile)
        if mask is None:
            continue
        union = mask if union is None else (union | mask)
    return union


def _previous_group_island_union(project, group, previous_names, width: int, height: int, udim_tile: int):
    """UV islands already present in this texture set's shared output."""
    metadata_state = properties.group_metadata_state(group)
    set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip().casefold()
    union = None
    for name in previous_names:
        candidate = _find_group_by_name(project, name)
        if candidate is None:
            continue
        candidate_state = properties.group_metadata_state(candidate)
        if (getattr(candidate_state, "texture_set_name", "") or "").strip().casefold() != set_key:
            continue
        mask = _group_uv_mask(candidate, width, height, udim_tile=udim_tile)
        if mask is not None:
            union = mask if union is None else (union | mask)
    return union


def _prepare_per_group_merge(project, state) -> None:
    """Back up the shared output files this per-group pass is about to overwrite."""
    global _PER_GROUP_MERGE_STATE
    _PER_GROUP_MERGE_STATE = None
    if int(state.get("group_index", 0)) <= 0 and not state.get("merge_onto_base"):
        # First group: its pass writes the fresh base every later group merges onto.
        return
    group_name = (state.get("group_names") or [""])[0]
    group = _find_group_by_name(project, group_name)
    if group is None:
        return
    # The pass leaves the other tiles alone (own_tiles_only), so they need no merge.
    own_tiles = export.group_occupied_tiles(group)
    backups: list[tuple[str, str]] = []
    for map_uuid in state.get("map_uuids") or []:
        map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        if map_setting is None:
            continue
        # One path per UDIM tile: a tokenized set writes Set_Albedo.1001.png, so the
        # untokenized name matched no file at all, no backup was taken, and the merge
        # silently never ran -- group 2's pass overwrote group 1's islands with
        # background and the bake still reported success.
        for path in export.resolve_group_map_output_paths(project, group, map_setting):
            if not path or not os.path.isfile(path):
                continue
            tile = _udim_tile_from_output_path(path)
            if own_tiles and tile and tile not in own_tiles:
                continue
            backup = f"{path}.pergroup_base"
            try:
                shutil.copyfile(path, backup)
            except OSError:
                continue
            backups.append((path, backup))
    if not backups:
        return
    _PER_GROUP_MERGE_STATE = {
        "project_name": str(getattr(project, "name", "") or ""),
        "group_name": group_name,
        "backups": backups,
        "margin": int(getattr(project, "margin", 4) or 0),
        "infinite_dilation": str(getattr(project, "margin_mode", constants.DILATION_DISTANCE)) == constants.DILATION_INFINITE,
        "previous_group_names": list(state.get("previous_group_names") or []),
        "exclude_group_names": list(state.get("exclude_group_names") or []),
    }


def _prepare_subset_merge(project, group_names, map_uuids) -> None:
    """Back up the shared files a bake of some of the project's groups will overwrite.

    The job holds only these groups, so it writes a file without the others: without the
    merge, Bake Changed after an edit to one group erases every other group of the texture
    set. A file or UDIM tile no other group occupies stays a plain write.
    """
    global _PER_GROUP_MERGE_STATE
    _PER_GROUP_MERGE_STATE = None
    selected = {str(name or "") for name in (group_names or [])}
    groups = list(getattr(project, "groups", []) or [])
    chosen = [group for group in groups if str(getattr(group, "name", "") or "") in selected]
    others = [group for group in groups if str(getattr(group, "name", "") or "") not in selected]
    if not chosen or not others:
        return

    def occupied_paths(group, map_setting):
        tiles = export.group_occupied_tiles(group)
        return [
            path
            for path in export.resolve_group_map_output_paths(project, group, map_setting)
            if path and (not tiles or not _udim_tile_from_output_path(path) or _udim_tile_from_output_path(path) in tiles)
        ]

    subset_groups: dict[str, list[str]] = {}
    for map_uuid in map_uuids or []:
        map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        if map_setting is None:
            continue
        shared = {path for other in others for path in occupied_paths(other, map_setting)}
        for group in chosen:
            for path in occupied_paths(group, map_setting):
                if path in shared and os.path.isfile(path):
                    names = subset_groups.setdefault(path, [])
                    if str(group.name) not in names:
                        names.append(str(group.name))
    backups: list[tuple[str, str]] = []
    for path in subset_groups:
        backup = f"{path}.pergroup_base"
        try:
            shutil.copyfile(path, backup)
        except OSError:
            continue
        backups.append((path, backup))
    if not backups:
        return
    other_names = [str(getattr(group, "name", "") or "") for group in others]
    _PER_GROUP_MERGE_STATE = {
        "project_name": str(getattr(project, "name", "") or ""),
        "group_name": str(chosen[0].name),
        "subset_groups": subset_groups,
        "backups": backups,
        "margin": int(getattr(project, "margin", 4) or 0),
        "infinite_dilation": str(getattr(project, "margin_mode", constants.DILATION_DISTANCE)) == constants.DILATION_INFINITE,
        "previous_group_names": other_names,
        "exclude_group_names": other_names,
    }


def _island_reach_steps(islands, steps: int):
    """Per texel, the dilation step (4-neighbourhood, like the margin mask) that first reaches it.

    0 on the islands themselves, 255 where nothing reaches within ``steps``.
    """
    import numpy as np

    reach = np.full(islands.shape, 255, dtype=np.uint8)
    reach[islands] = 0
    current = islands.copy()
    for step in range(1, max(1, int(steps)) + 1):
        grown = current.copy()
        grown[1:, :] |= current[:-1, :]
        grown[:-1, :] |= current[1:, :]
        grown[:, 1:] |= current[:, :-1]
        grown[:, :-1] |= current[:, 1:]
        reach[grown & ~current] = min(step, 254)
        current = grown
    return reach


def _own_texels_winning_overlap(project, group, width: int, height: int, udim_tile: int):
    """This group's island texels no later group of the texture set also covers.

    Where groups overlap in UV, the last group in the project list owns the texel on every
    map: a whole-set bake's raster keeps the highest item, and Toolbag draws its newest group
    first with the first draw winning. A per-group pass has to follow the same rule, or the
    winner's material detail is cut out of the overlap. None when it cannot be told.
    """
    own = _group_uv_mask(group, width, height, udim_tile=udim_tile)
    if own is None:
        return None
    configured = [str(getattr(item, "name", "") or "") for item in getattr(project, "groups", []) or []]
    name = str(getattr(group, "name", "") or "")
    later_names = configured[configured.index(name) + 1:] if name in configured else []
    later = _previous_group_island_union(project, group, later_names, width, height, udim_tile)
    return own if later is None else own & ~later


def _mask_without_neighbour_groups(project, group, mask, neighbour_names, width: int, height: int, udim_tile: int, margin: int = 16):
    """The group's dilated mask minus every neighbour group's own texels and nearer ring.

    The pass bakes this group alone, so its margin dilation knows nothing of the other
    groups of the texture set: where islands sit closer together than the margin, taking
    the whole dilated mask overwrote the neighbour's real texels with this group's
    smeared edge. A texel stays with the neighbour when it lies on the neighbour's island
    or at least as close to it as to this group's.

    Distances come from ``margin`` dilation steps of each side rather than a full-image
    nearest-texel search: that costs one pass per margin texel instead of seconds on a
    map whose islands spread across the whole sheet.
    """
    try:
        own = _group_uv_mask(group, width, height, udim_tile=udim_tile)
        others = _previous_group_island_union(project, group, neighbour_names, width, height, udim_tile)
        if own is None or others is None:
            return mask
        steps = max(1, int(margin))
        own_reach = _island_reach_steps(own, steps)
        other_reach = _island_reach_steps(others, steps)
        kept = mask & ~others & (own_reach < other_reach)
        winning = _own_texels_winning_overlap(project, group, width, height, udim_tile)
        return kept if winning is None else kept | winning
    except Exception:
        return mask


def _finish_per_group_merge(project, *, succeeded: bool) -> None:
    global _MERGE_RASTER_CACHE
    _MERGE_RASTER_CACHE = {}
    try:
        _finish_per_group_merge_pass(project, succeeded=succeeded)
    finally:
        _MERGE_RASTER_CACHE = None


def _finish_per_group_merge_pass(project, *, succeeded: bool) -> None:
    """Composite the finished pass's own texels back over the pre-pass snapshot."""
    global _PER_GROUP_MERGE_STATE
    state = _PER_GROUP_MERGE_STATE
    _PER_GROUP_MERGE_STATE = None
    if not state:
        return
    _merge_started = time.perf_counter()
    group = _find_group_by_name(project, state.get("group_name", "")) if project is not None else None
    if project is not None and str(getattr(project, "name", "") or "") != str(state.get("project_name") or ""):
        # A stranded merge from another project must never composite its stale
        # backups over this project's fresh outputs: drop the state, keep the files.
        for _path, backup in state.get("backups") or []:
            try:
                os.remove(backup)
            except OSError:
                pass
        return
    # Every map row in one pass writes the same resolution, so the island rasterization
    # is computed once and reused across this pass's output files.
    island_union_cache: dict[tuple[int, int], object] = {}
    infinite_take_cache: dict[tuple, object] = {}

    def group_take_mask(member, width, height, udim_tile):
        if bool(state.get("infinite_dilation")):
            cache_key = (str(getattr(member, "name", "") or ""), width, height, udim_tile)
            if cache_key not in infinite_take_cache:
                current = _group_uv_mask(member, width, height, udim_tile=udim_tile)
                previous = _previous_group_island_union(
                    project, member, state.get("previous_group_names") or [],
                    width, height, udim_tile,
                )
                if current is not None:
                    import numpy as np
                    if previous is None:
                        previous = np.zeros_like(current)
                    _take = export.infinite_dilation_group_take_mask(current, previous)
                    _winning = _own_texels_winning_overlap(project, member, width, height, udim_tile)
                    infinite_take_cache[cache_key] = _take if _winning is None else _take | _winning
            return infinite_take_cache.get(cache_key)
        mask = _group_uv_mask(
            member, width, height, dilate_texels=state.get("margin", 4), udim_tile=udim_tile
        )
        if mask is not None and state.get("exclude_group_names"):
            mask = _mask_without_neighbour_groups(
                project, member, mask, state.get("exclude_group_names") or [],
                width, height, udim_tile, int(state.get("margin", 16) or 16),
            )
        return mask

    try:
        for path, backup in state.get("backups") or []:
            keep_backup = False
            try:
                if succeeded and group is not None:
                    mask = None
                    try:
                        image = bpy.data.images.load(path, check_existing=False)
                        try:
                            width, height = image.size
                        finally:
                            image_cleanup.remove_image_when_safe(image, reason="per-group merge probe")
                        udim_tile = _udim_tile_from_output_path(path)
                        cache_key = (width, height, udim_tile)
                        members = [group]
                        if state.get("subset_groups"):
                            members = [
                                _find_group_by_name(project, name)
                                for name in state["subset_groups"].get(path, [state.get("group_name", "")])
                            ]
                        for member in members:
                            member_mask = group_take_mask(member, width, height, udim_tile) if member is not None else None
                            if member_mask is None:
                                mask = None
                                break
                            mask = member_mask if mask is None else (mask | member_mask)
                    except Exception:
                        mask = None
                    if mask is not None:
                        if not bool(state.get("infinite_dilation")) and cache_key not in island_union_cache:
                            island_union_cache[cache_key] = _texture_set_island_union(
                                project, group, width, height, udim_tile
                            )
                        # backup (all earlier groups) + this pass's own texels.
                        shutil.copyfile(path, f"{path}.pergroup_new")
                        shutil.copyfile(backup, path)
                        merged = export.composite_group_texels(
                            path,
                            f"{path}.pergroup_new",
                            mask,
                            # A base that already holds every group has its own margins, and
                            # black ones are real (a concave Curvature edge): only a fresh base
                            # has empty texels this pass's dilation may fill.
                            island_union=(None if bool(state.get("infinite_dilation")) or state.get("exclude_group_names")
                                          else island_union_cache[cache_key]),
                        )
                        if not merged:
                            # Never leave the artist with the snapshot instead of the bake.
                            shutil.copyfile(f"{path}.pergroup_new", path)
                        _remove_quietly(f"{path}.pergroup_new")
                    else:
                        # No mask (the group lost its low objects, or the probe failed):
                        # the file holds THIS pass only and the backup holds every
                        # earlier group. Merging is impossible, so keep the fresh pass
                        # but do not destroy the evidence -- deleting the backup here
                        # silently dropped the other groups' composite from a bake that
                        # reported success.
                        keep_backup = True
                        print(
                            "[MasterBaker] per-group merge skipped for "
                            f"{path}: could not rasterize the group's UV mask. That file now "
                            f"holds only this pass; the previous composite is kept at {backup}."
                        )
                else:
                    shutil.copyfile(backup, path)
            except OSError:
                pass
            finally:
                if not keep_backup:
                    _remove_quietly(backup)
    except Exception:
        pass
    print(
        f"[Fyr Baker] per-group merge of '{state.get('group_name', '')}' took "
        f"{time.perf_counter() - _merge_started:.2f}s"
    )


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


_PHASE_TIMERS = os.environ.get("FYR_BAKE_PHASE_TIMERS", "") == "1"
_PHASE_MARK_LAST = [0.0]


def _phase_mark(label: str) -> None:
    """Print the seconds since the previous mark when FYR_BAKE_PHASE_TIMERS=1.

    Silent by default. It exists to attribute host-side time between two staged
    phases, which no stage timer covers."""
    if not _PHASE_TIMERS:
        return
    now = time.perf_counter()
    last = _PHASE_MARK_LAST[0]
    _PHASE_MARK_LAST[0] = now
    print(f"[Fyr Baker] phase-mark {label} +{(now - last) if last else 0.0:.2f}s", flush=True)


def _consume_pending_material_phase(*, succeeded: bool) -> bool:
    """Schedule the next staged phase after a clean bake; drop the queue otherwise.

    Returns True when a phase was scheduled. A failed or cancelled bake must never
    run staged phases — dependent materials would consume the same stale mesh maps
    this feature exists to eliminate, and the bake's own error is what the user
    needs to see.
    """
    if not _PENDING_MATERIAL_PHASES:
        return False
    if not succeeded:
        _clear_pending_material_phase()
        return False
    try:
        bpy.app.timers.register(_run_pending_material_phase, first_interval=0.0)
    except Exception:
        _clear_pending_material_phase()
        return False
    return True


def _run_pending_material_phase() -> None:
    """Run the next staged phase: the dependency stage 2, or one per-group native pass.

    Runs from a timer so the previous bake's completion callback has returned and no
    bake is still registered as running. Pops ONE entry; the popped bake's own
    completion schedules the next through _consume_pending_material_phase, so the
    queue drains one clean bake at a time and any failure drops the remainder.

    For the dependency kind, the image reload is what makes the re-capture honest:
    every material texel payload is snapshotted inside ``export.prepare_bake_job``, so
    calling ``_run_bake`` again is exactly what re-reads the fresh pixels.
    """
    global _MATERIAL_PHASE_TWO_ACTIVE

    if not _PENDING_MATERIAL_PHASES:
        return
    state = _PENDING_MATERIAL_PHASES.pop(0)
    if not state:
        return
    _phase_mark("phase-timer fired")
    context = bpy.context
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = None
    for candidate in (getattr(settings, "projects", []) or []) if settings is not None else []:
        if str(getattr(candidate, "name", "") or "") == state["project_name"]:
            project = candidate
            break
    if project is None:
        # Project removed or file swapped while stage 1 ran. The remaining
        # entries would otherwise survive to the next unrelated successful bake
        # and dispatch a stale per-group pass.
        _clear_pending_material_phase()
        return

    reporter = _DeferredBakeReporter()
    try:
        reloaded, packed, failed = bake_dependencies.reload_images_for_path_keys(
            state.get("reload_path_keys") or []
        )
    except Exception as exc:  # noqa: BLE001 - a failed reload must not strand the run
        reporter.report({"WARNING"}, f"Could not refresh baked mesh maps: {exc}")
        reloaded, packed, failed = [], [], []
    _phase_mark("phase: reload images")
    if reloaded:
        print(f"[Fyr Baker] Stage 2/2: refreshed {len(reloaded)} baked map image(s): {', '.join(reloaded)}")
    for name in packed:
        reporter.report(
            {"WARNING"},
            f"Image '{name}' is packed into the .blend, so it still holds the previous bake. "
            "Unpack it to let materials read this run's output",
        )
    for name in failed:
        # Silently skipping this let stage 2 shade from the previous run's mesh maps
        # and still report success.
        reporter.report(
            {"WARNING"},
            f"Image '{name}' could not be reloaded, so this stage may read the previous "
            "bake's pixels",
        )

    labels = state.get("labels") or []
    label_text = ", ".join(labels) if labels else "materials"
    phase_label = str(state.get("phase_label") or "").strip()
    if phase_label:
        start_message = f"{phase_label}: {label_text}"
        initial_status = phase_label
        failure_prefix = phase_label
    else:
        start_message = f"{_material_phase_status(2)} baking {label_text}"
        initial_status = _material_phase_status(2)
        failure_prefix = "Stage 2/2"
    if str(state.get("kind") or "") == "per_group":
        # Snapshot what this pass will overwrite BEFORE it runs; its completion
        # composites this group's own texels back over that snapshot.
        _prepare_per_group_merge(project, state)
    _MATERIAL_PHASE_TWO_ACTIVE = True
    _phase_mark("phase: entering _run_bake")
    try:
        outcome = _run_bake(
            reporter,
            context,
            project,
            map_uuids=list(state.get("map_uuids") or []),
            group_names=list(state.get("group_names") or []),
            start_message=start_message,
            initial_status=initial_status,
            live_bake_mode=str(state.get("live_bake_mode") or "preserve"),
            material_normal_source=state.get("material_normal_source"),
            own_tiles_only=_phase_writes_only_own_tiles(project, state),
        )
        if "FINISHED" not in (outcome or set()):
            # The phase never launched (validation refusal, a competing bake, ...);
            # no completion callback will fire, so the rest of the queue would
            # strand as a stale request for a later unrelated bake.
            _finish_per_group_merge(project, succeeded=False)
            _clear_pending_material_phase()
    except Exception as exc:  # noqa: BLE001 - surface, never leave the panel mid-stage
        reporter.report({"ERROR"}, f"{failure_prefix} failed: {exc}")
        _finish_per_group_merge(project, succeeded=False)
        _clear_pending_material_phase()
        try:
            project.last_status_message = constants.STATUS_FAILED
        except Exception:
            pass
    finally:
        _MATERIAL_PHASE_TWO_ACTIVE = False


def _phase_writes_only_own_tiles(project, state) -> bool:
    """Whether a staged phase plans only the UDIM tiles its own groups occupy.

    A merge pass always does. The later stages of a user subset bake (mesh maps after
    Normal, dependent materials) hold the same subset of groups as stage 1 and keep the
    other groups' tiles. The first F8 per-group pass does not: it writes the fresh base of
    every tile, which each later pass only adds its own tiles to. A later pass writing the
    others would leave them blank.
    """
    if bool(state.get("merge_onto_base")):
        return True
    if str(state.get("kind") or "") == "per_group":
        return int(state.get("group_index", 0)) > 0
    configured = [str(getattr(group, "name", "") or "") for group in getattr(project, "groups", []) or []]
    return _is_user_group_subset(state.get("group_names"), configured)


def _handle_background_bake_update(result) -> None:
    if _handle_live_normal_preview_background_update(result):
        return
    snapshot = getattr(result, "snapshot", None)
    if snapshot is None:
        return
    scene, settings, project = _find_project_record_by_job_id(getattr(snapshot, "job_id", ""))
    if project is None:
        # The project that launched this bake is gone (removed, or undone past the
        # launch). The finished branch below is the only place that leaves the
        # low-impact viewport mode, so leave it here too or the overlays stay
        # suspended and the viewport stays in reduced-redraw mode until file load.
        if getattr(result, "finished", False):
            try:
                _bake_low_impact_restore()
            except Exception:
                pass
            _ASYNC_MATERIAL_ERRORS.pop(str(Path(str(getattr(snapshot, "job_path", "") or "")).parent), None)
        return
    workspace_path = Path(str(getattr(snapshot, "job_path", "") or "")).parent
    workspace_key = str(workspace_path)
    if getattr(result, "finished", False) and export.material_bakes_pending(workspace_path):
        _DEFERRED_MATERIAL_BACKEND_RESULTS[workspace_key] = result
        try:
            project.last_status_message = "Finishing Cycles material bakes…"
            if settings is not None:
                settings.status_message = "Finishing Cycles material bakes…"
        except Exception:
            pass
        return
    # Mid-bake tick throttle: the poll fires at up to 20Hz while a bake runs, and
    # the full progress application below (descriptor merge + disk healing +
    # output-image refresh + preview-material sync) at that cadence contends with
    # the backend for the GPU/main thread (~30% of full-bake wall time measured
    # on the 2K Pottery scene). Between heavy passes, mirror only the cheap
    # status surfaces every tick so all progress UI stays live at full cadence.
    if not getattr(result, "finished", False):
        now = time.monotonic()
        produced_count = len(getattr(result.progress, "produced_files", []) or [])
        throttle = _BAKE_PROGRESS_HEAVY_THROTTLE
        if (
            produced_count == throttle["produced"]
            and (now - throttle["t"]) < _BAKE_PROGRESS_HEAVY_INTERVAL_SECONDS
        ):
            try:
                export.apply_progress_status_to_project(project, result.progress)
                if settings is not None:
                    settings.status_message = project.last_status_message
            except Exception:
                pass
            try:
                if _LOW_IMPACT_STATE.get("active"):
                    _tag_bake_progress_regions()
                else:
                    overlays.tag_redraw_all_view3d(scene=scene)
            except Exception:
                pass
            _poke_statusbar_redraw()
            return
        throttle["t"] = now
        throttle["produced"] = produced_count
    material_errors = _ASYNC_MATERIAL_ERRORS.pop(workspace_key, [])
    if material_errors:
        result.progress.warnings.extend(material_errors)
    if getattr(result, "finished", False) and _PER_GROUP_MERGE_STATE is not None:
        # A per-group native material pass just wrote its own group into the texture
        # set's shared file. Composite before anything below reads those files, so the
        # output images, previews and thumbnails all see the merged result.
        _finish_per_group_merge(
            project,
            succeeded=not getattr(result.progress, "errors", None)
            and getattr(result.progress, "status", "") not in {
                constants.STATUS_FAILED,
                constants.STATUS_CANCELLED,
                constants.STATUS_CANCELLING,
            },
        )
    _active_types = set(map_rebuild.active_bake_map_types(project))
    _active_uuids = set(map_rebuild.active_bake_map_uuids(project))
    _merge = map_rebuild.active_bake_is_partial(project) or any(
        (
            str(getattr(_oi, "map_uuid", "") or "").strip() not in _active_uuids
            if _active_uuids and str(getattr(_oi, "map_uuid", "") or "").strip()
            else str(getattr(_oi, "map_type", "") or "") not in _active_types
        )
        for _oi in project.latest_outputs
        if str(getattr(_oi, "map_type", "") or "").strip() or str(getattr(_oi, "map_uuid", "") or "").strip()
    )
    if getattr(result, "finished", False):
        _phase_mark("stage-done: poll result received, pre-apply")
    export.apply_progress_to_project(project, result.progress, merge_existing=True)
    if getattr(result, "finished", False):
        _phase_mark("stage-done: apply_progress_to_project")
    if (
        getattr(result, "finished", False)
        and not getattr(result.progress, "errors", None)
        and getattr(result.progress, "status", "") not in {
            constants.STATUS_FAILED,
            constants.STATUS_CANCELLED,
            constants.STATUS_CANCELLING,
        }
    ):
        detail_warnings = material_detail.apply_workspace_material_detail(workspace_path)
        if detail_warnings:
            result.progress.warnings.extend(detail_warnings)
        has_derived = bool(derived_outputs.read_sidecar(workspace_path))
        if has_derived:
            # After the material detail: a Derivative converts the finished normal.
            result.progress.warnings.extend(
                derived_outputs.apply_workspace_derived_outputs(workspace_path, result.progress)
            )
        if detail_warnings or has_derived:
            export.apply_progress_to_project(project, result.progress, merge_existing=True)
        _phase_mark("stage-done: material detail + derived outputs")
    with dirty_tracker.suppress():
        try:
            runtime.refresh_project_output_images(project)
        except Exception:
            pass
        if getattr(result, "finished", False):
            _phase_mark("stage-done: refresh_project_output_images")
        try:
            _sync_preview_material_for_project(scene, project)
        except Exception:
            pass
        if getattr(result, "finished", False):
            _phase_mark("stage-done: preview material sync")
    if getattr(result, "finished", False):
        _phase_mark("stage-done: handler reached finished branch (progress applied)")
        # First: start putting parked meshes back, in timer slices (restoring all 71 highs
        # of a customer's gun in one go froze the UI for 6-9 s). The readers below take
        # what they need first: the bake state is recorded from the snapshot park took of
        # each high, and a Cycles retry, staged material phases and the export-after-bake
        # call high_poly_park.ensure_restored() before they touch a mesh.
        if not getattr(result.progress, "errors", None):
            try:
                high_poly_park.record_bake_peak()
            except Exception:
                pass
        if high_poly_park.is_parked():
            try:
                high_poly_park.restore_async()
            except Exception as exc:
                print(f"[Fyr Baker] high-poly park: restore failed, timer will retry: {exc}")
                high_poly_park.arm_restore_timer()
        _dismiss_setup_progress()
        _phase_mark("stage-done: park restore + dismiss")
        global _DIRTY_REBAKE_SNAPSHOT
        # Bound before the swallow-all block below so the pending-export check at
        # the end of this branch can trust it even if reading progress raised.
        bake_succeeded = False
        # True once the Cycles retry is running on the modal driver: this bake has no
        # outcome yet, so every tail below belongs to the retry's completion instead.
        handoff_pending = False
        try:
            # str(Path("")) is ".", so the old `if str(job_path)` guard let a snapshot
            # without a job path slim the CURRENT DIRECTORY: every .fymesh under the
            # repository or project root, including the Live Reproject baseline blobs.
            raw_job_path = str(getattr(snapshot, "job_path", "") or "")
            if raw_job_path:
                job_path = Path(raw_job_path)
                if job_path.is_absolute():
                    storage_cleanup.slim_job_workspace(job_path.parent)
        except Exception:
            pass
        try:
            try:
                bake_succeeded = not result.progress.errors and getattr(result.progress, "status", "") not in {
                    constants.STATUS_FAILED,
                    constants.STATUS_CANCELLED,
                    constants.STATUS_CANCELLING,
                }
                if not bake_succeeded:
                    prepared_for_handoff = _pop_cycles_handoff_prepared(
                        getattr(getattr(result, "snapshot", None), "job_id", None)
                    )
                    if prepared_for_handoff is not None:
                        # Cycles bakes from the real high-poly: every one back first.
                        high_poly_park.ensure_restored()
                        outcome = _try_cycles_projection_handoff(
                            bpy.context,
                            project,
                            result.progress,
                            prepared_for_handoff,
                            map_types=map_rebuild.active_bake_map_types(project) or None,
                            on_complete=_deferred_poll_handoff_completion(
                                project,
                                result.progress,
                                snapshot,
                                dirty_snapshot=_DIRTY_REBAKE_SNAPSHOT,
                            ),
                        )
                        handoff_pending = outcome is CyclesHandoffOutcome.PENDING
                        bake_succeeded = outcome is CyclesHandoffOutcome.RECOVERED
                        if bake_succeeded:
                            export.apply_progress_to_project(
                                project, result.progress, merge_existing=True
                            )
                            try:
                                runtime.refresh_project_output_images(project)
                            except Exception:
                                pass
                    else:
                        _pop_cycles_handoff_prepared(
                            getattr(getattr(result, "snapshot", None), "job_id", None)
                        )
                else:
                    _pop_cycles_handoff_prepared(
                        getattr(getattr(result, "snapshot", None), "job_id", None)
                    )
                if bake_succeeded:
                    # A clean bake means the post-OOM re-prewarm (if any) did its job;
                    # drop the recovery marker so the label reverts to normal next time.
                    runtime.clear_prewarm_oom_recovery()
                    if _DIRTY_REBAKE_SNAPSHOT is not None:
                        # Partial incremental bake — only clear what we actually baked.
                        _update_bake_state_partial(project, _DIRTY_REBAKE_SNAPSHOT)
                        for gname, maps in _DIRTY_REBAKE_SNAPSHOT.items():
                            dirty_tracker.clear_dirty(gname, maps)
                    else:
                        map_rebuild.record_bake_state(project)
                        dirty_tracker.clear_all_dirty()
                    dirty_tracker.set_post_bake_cooldown()
                    _rebase_live_reproject(project)
                elif not handoff_pending:
                    # On failure, keep dirty state so the user can retry, and
                    # show the canonical failure status rather than the raw error
                    # text that apply_progress_to_project placed in last_status_message.
                    failed_status = getattr(result.progress, "status", None)
                    if failed_status not in {
                        constants.STATUS_FAILED,
                        constants.STATUS_CANCELLED,
                        constants.STATUS_CANCELLING,
                    }:
                        failed_status = constants.STATUS_FAILED
                    project.last_status_message = failed_status
                    # An out-of-memory failure (the long-lived worker's host
                    # footprint grew until a large allocation gave up) keeps
                    # failing at the same spot on retry. Restart the worker to
                    # reclaim memory and swap the raw "bad allocation" for an
                    # actionable summary so the user isn't stuck in a fail loop.
                    if diagnostics.failure_is_out_of_memory(result.progress):
                        raw_oom = str(
                            getattr(result.progress, "message", "")
                            or (result.progress.errors[0] if result.progress.errors else "")
                        )
                        restarted = _recover_backend_from_out_of_memory()
                        project.last_error_summary = diagnostics.out_of_memory_summary(
                            raw_oom, restarted=restarted
                        )
                    elif failed_status == constants.STATUS_FAILED:
                        # This timer path has no operator to report through; the
                        # panel's error line is where the artist reads the failure.
                        _apply_failure_guidance_summary(project, result.progress)
                    # If a legacy warning still mentions Embree CPU fallback but the bake
                    # failed, clarify so the user doesn't think that path saved them.
                    warning = str(getattr(project, "last_warning_summary", "") or "")
                    if result.progress.errors and ", using CPU fallback" in warning:
                        project.last_warning_summary = warning.replace(
                            ", using CPU fallback", ", CPU fallback also failed"
                        )
                    if result.progress.errors and cycles_projection.progress_requests_cycles_handoff(
                        result.progress
                    ):
                        project.last_warning_summary = (
                            str(project.last_warning_summary or "")
                            + (". " if project.last_warning_summary else "")
                            + "Cycles fallback could not recover all maps"
                        ).strip()
            except Exception:
                pass
        finally:
            _DIRTY_REBAKE_SNAPSHOT = None
            if not handoff_pending:
                # The Cycles retry still needs the active-bake record to decide what a
                # partial bake actually covered, so its completion clears this instead.
                map_rebuild.clear_active_bake_map_types(project)
            # Refresh group membership in case objects were added/removed.
            try:
                dirty_tracker.refresh_membership_index(project)
            except Exception:
                pass
            # Memory watchdog: the resident worker keeps its per-bake working set
            # resident as a high-water mark that never shrinks, so RSS ratchets up
            # across a session until a bake std::bad_alloc's. Now that this bake has
            # finalized (worker idle), recycle it if it has bloated enough to
            # threaten the next bake — the restart re-prewarms in the background so
            # the worker stays warm. Skip if an OOM recovery already restarted it.
            _phase_mark("stage-done: bookkeeping before worker recycle check")
            try:
                if not runtime.prewarm_is_oom_recovery():
                    runtime.maybe_recycle_worker_for_memory()
            except Exception:
                pass
            _phase_mark("stage-done: maybe_recycle_worker_for_memory")
        # Append the total wall-clock bake duration to the user-visible status
        # so the panel reports e.g. "Bake complete (1m 23s)" once the run is done.
        # Skipped while a Cycles retry runs: the bake is not over, and its completion
        # appends the duration including the retry.
        if not handoff_pending:
            _append_bake_duration_to_status(project, snapshot)
        # Bake finished (clean finish OR cancel — both reach this branch). Restore the
        # low-impact viewport mode exactly once, BEFORE the full redraw below so the
        # re-added overlays draw on the final frame. This runs from a bpy.app.timer with
        # no operator context; _bake_low_impact_restore iterates windows itself.
        try:
            _bake_low_impact_restore()
        except Exception:
            pass
        # Dependency ordering: stage 1 just finished, so refresh the images the
        # dependent material rows read and bake them now. Checked before the export
        # re-run below and left armed through stage 2, so "Bake Missing Maps First"
        # still exports only once every map is on disk.
        staged_second_phase = False
        if not handoff_pending:
            try:
                if _PENDING_MATERIAL_PHASES or globals().get("_PENDING_EXPORT_AFTER_BAKE"):
                    high_poly_park.ensure_restored()
                _phase_mark("stage-done: ensure_restored")
                staged_second_phase = _consume_pending_material_phase(succeeded=bake_succeeded)
            except Exception:
                _clear_pending_material_phase()
            _phase_mark("stage-done: phase scheduled")
        # "Bake Missing Maps First": the export dialog armed a re-run before this
        # bake. Fire it only on a clean bake, and always disarm so a later failed
        # bake cannot inherit the request. Deferred to a timer so the export runs
        # after this poll callback returns with a settled context.
        global _PENDING_EXPORT_AFTER_BAKE
        if _PENDING_EXPORT_AFTER_BAKE and not staged_second_phase and not handoff_pending:
            _PENDING_EXPORT_AFTER_BAKE = False
            if bake_succeeded:
                try:
                    bpy.app.timers.register(
                        _run_pending_export_after_bake, first_interval=0.0
                    )
                except Exception:
                    pass
    settings.status_message = project.last_status_message
    try:
        if _LOW_IMPACT_STATE.get("active") and not getattr(result, "finished", False):
            # L1: mid-bake, redraw only the progress surfaces (N-panel / Render tab /
            # status bar) — never the VIEW_3D WINDOW region on the baking GPU.
            _tag_bake_progress_regions()
        else:
            overlays.tag_redraw_all_view3d(scene=scene)
    except Exception:
        pass
    _poke_statusbar_redraw()


def _poke_statusbar_redraw() -> None:
    """Force the bottom status bar to redraw so its footer progress bar tracks the bake.

    The status bar is a global area absent from screen.areas, so it cannot be
    tag_redraw()'d directly. Setting the workspace status text reliably tags it for
    redraw (even with an unchanged value), which drives the footer bar at the poll
    cadence. Gated on the preference so it is a no-op when the footer bar is disabled."""
    try:
        prefs = preferences.get_preferences()
        if prefs is not None and not getattr(prefs, "show_statusbar_progress", True):
            return
        wm = getattr(bpy.context, "window_manager", None)
        seen = set()
        for window in getattr(wm, "windows", []):
            workspace = getattr(window, "workspace", None)
            if workspace is None or workspace.as_pointer() in seen:
                continue
            seen.add(workspace.as_pointer())
            workspace.status_text_set(None)
    except Exception:
        pass


def _bake_low_impact_enabled() -> bool:
    """Whether the bake low-impact viewport mode should engage for this bake.

    Engaged only when the user has the optimization on (bake_low_impact_viewport) and
    has NOT opted to watch the bake live (bake_keep_viewport_live). When prefs are
    unavailable, default to engaged (the feature's default-True state)."""
    prefs = preferences.get_preferences()
    if prefs is None:
        return True
    if getattr(prefs, "bake_keep_viewport_live", False):
        return False
    return bool(getattr(prefs, "bake_low_impact_viewport", True))


def _tag_bake_progress_regions() -> None:
    """L1: during a bake redraw ONLY the progress surfaces, never the VIEW_3D WINDOW
    region.

    The WINDOW region is the 3D view itself; force-redrawing it ~20x/sec re-runs
    EEVEE/Cycles shading and our overlay passes on the same GPU the worker is baking on.
    The bake progress bar lives in the N-panel (VIEW_3D UI/TOOLS region) and the Render
    tab (PROPERTIES editor), and the footer bar is poked separately via
    _poke_statusbar_redraw, so tagging just those keeps progress live while the 3D
    pixels hold their last frame."""
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in getattr(wm, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            atype = getattr(area, "type", "")
            if atype == "VIEW_3D":
                for region in area.regions:
                    if region.type in {"UI", "TOOLS", "HEADER"}:
                        region.tag_redraw()
            elif atype == "PROPERTIES":
                # The Render-tab progress mirror draws in the PROPERTIES WINDOW region
                # (property panels), which is cheap and carries no 3D shading cost.
                for region in area.regions:
                    if region.type in {"WINDOW", "HEADER"}:
                        region.tag_redraw()


def _set_setup_progress_viewport_quiet(quiet: bool) -> None:
    # setup_progress is imported lazily everywhere else in this module; these call
    # sites used the bare name, so every bake start raised NameError (swallowed by the
    # caller) and the HUD was never quieted.
    try:
        from . import setup_progress
        setup_progress.set_viewport_quiet(quiet)
    except Exception:
        pass


def _bake_low_impact_engage(context) -> None:
    """Engage bake low-impact viewport mode on bake START (operator context available).

    L1 needs only the module-level 'active' flag — the poll path then tags progress
    regions instead of the whole VIEW_3D area. L2 removes our two overlay draw handlers
    for the duration of the bake. Both are undone exactly once on bake END by
    _bake_low_impact_restore. Safe to call unconditionally; it no-ops (and clears any
    stale flags) when the mode is disabled by preference."""
    if not _bake_low_impact_enabled():
        _LOW_IMPACT_STATE["active"] = False
        _LOW_IMPACT_STATE["overlays_suspended"] = False
        _set_setup_progress_viewport_quiet(False)
        return
    _LOW_IMPACT_STATE["active"] = True
    # The viewport HUD lives on the VIEW_3D WINDOW region this mode stops redrawing;
    # tell it to stay hidden rather than sit frozen on its first frame.
    _set_setup_progress_viewport_quiet(True)
    suspended = False
    try:
        suspended = bool(overlays.suspend_bake_overlay_draw_handlers())
    except Exception:
        suspended = False
    # If a prior engage already removed the handlers (a re-entrant START before the
    # previous restore ran, e.g. live-bake re-bakes), suspend() returns False because the
    # handlers are already gone — keep the flag True so the eventual restore still re-adds.
    _LOW_IMPACT_STATE["overlays_suspended"] = suspended or bool(_LOW_IMPACT_STATE.get("overlays_suspended"))


def _bake_low_impact_restore(*, readd_overlays: bool = True) -> None:
    """Restore bake low-impact viewport mode. Idempotent — a no-op when the mode is not
    engaged, so it is safe to call from the poll finished-branch (the normal END), from
    load_post, and from unregister as failsafes.

    L1 mutates nothing, so there is nothing to undo for it beyond clearing the 'active'
    flag (which reverts the poll path to full redraws). L2 re-adds the overlay draw
    handlers we removed. On addon teardown pass readd_overlays=False: overlays.unregister
    already drops the handlers and overlays.register re-installs them on the next enable,
    so re-adding here would risk leaking a handler past teardown."""
    suspended = bool(_LOW_IMPACT_STATE.get("overlays_suspended"))
    _LOW_IMPACT_STATE["active"] = False
    _LOW_IMPACT_STATE["overlays_suspended"] = False
    _set_setup_progress_viewport_quiet(False)
    if suspended and readd_overlays:
        try:
            overlays.resume_bake_overlay_draw_handlers()
        except Exception:
            pass


def _assign_image_to_best_editor(context, image) -> bool:
    area = getattr(context, "area", None)
    if area is not None and area.type == "IMAGE_EDITOR":
        area.spaces.active.image = image
        return True

    wm = getattr(context, "window_manager", None)
    if wm is None:
        return False

    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for candidate_area in screen.areas:
            if candidate_area.type != "IMAGE_EDITOR":
                continue
            candidate_area.spaces.active.image = image
            return True
    return False


def _window_key(window) -> int:
    as_pointer = getattr(window, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(window)


def _open_image_in_new_editor_window(context, image) -> bool:
    wm = getattr(context, "window_manager", None)
    if wm is None or not hasattr(bpy.ops, "wm") or not hasattr(bpy.ops.wm, "window_new"):
        return False

    existing_window_keys = {_window_key(window) for window in getattr(wm, "windows", [])}
    try:
        bpy.ops.wm.window_new()
    except Exception:
        return False

    new_window = None
    for window in getattr(wm, "windows", []):
        if _window_key(window) not in existing_window_keys:
            new_window = window
            break
    if new_window is None:
        windows = list(getattr(wm, "windows", []) or [])
        new_window = windows[-1] if windows else None
    if new_window is None:
        return False

    screen = getattr(new_window, "screen", None)
    if screen is None:
        return False
    areas = list(getattr(screen, "areas", []) or [])
    if not areas:
        return False
    target_area = areas[0]
    try:
        target_area.type = "IMAGE_EDITOR"
    except Exception:
        return False

    active_space = getattr(getattr(target_area, "spaces", None), "active", None)
    if active_space is None:
        return False
    try:
        active_space.image = image
    except Exception:
        return False
    return True


def _show_image_in_editor(context, image) -> bool:
    if _assign_image_to_best_editor(context, image):
        return True
    return _open_image_in_new_editor_window(context, image)


def _iter_image_editor_spaces(context):
    seen = set()

    area = getattr(context, "area", None)
    if area is not None and area.type == "IMAGE_EDITOR":
        active_space = getattr(getattr(area, "spaces", None), "active", None)
        if active_space is not None:
            key = _space_key(active_space)
            seen.add(key)
            yield active_space

    wm = getattr(context, "window_manager", None)
    if wm is None:
        return

    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for candidate_area in screen.areas:
            if candidate_area.type != "IMAGE_EDITOR":
                continue
            active_space = getattr(candidate_area.spaces, "active", None)
            if active_space is None:
                continue
            key = _space_key(active_space)
            if key in seen:
                continue
            seen.add(key)
            yield active_space



def _active_group_name(project) -> str:
    active_group = properties.peek_active_group(project)
    return str(getattr(active_group, "name", "") or "")


def _space_key(space) -> int:
    as_pointer = getattr(space, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(space)


def _object_hidden_with_fallback(obj) -> bool:
    """hide_get() falls back to hide_viewport when the object isn't in the active view layer."""
    try:
        return bool(obj.hide_get())
    except Exception:
        return bool(getattr(obj, "hide_viewport", False))


def _set_object_hidden_with_fallback(obj, hidden: bool) -> None:
    """hide_set() falls back to hide_viewport when the object isn't in the active view layer."""
    try:
        obj.hide_set(hidden)
    except Exception:
        obj.hide_viewport = hidden


def _iter_view3d_spaces(context):
    seen = set()
    area = getattr(context, "area", None)
    if area is not None and getattr(area, "type", "") == "VIEW_3D":
        active_space = getattr(getattr(area, "spaces", None), "active", None)
        if active_space is not None:
            key = _space_key(active_space)
            seen.add(key)
            yield active_space

    wm = getattr(context, "window_manager", None)
    if wm is None:
        return

    for window in getattr(wm, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for candidate_area in getattr(screen, "areas", []):
            if getattr(candidate_area, "type", "") != "VIEW_3D":
                continue
            active_space = getattr(getattr(candidate_area, "spaces", None), "active", None)
            if active_space is None:
                continue
            key = _space_key(active_space)
            if key in seen:
                continue
            seen.add(key)
            yield active_space

    # window.screen only covers the workspace each window currently shows. The
    # preview is project state, not workspace state: an artist who activates it in
    # Layout and hops to UV Editing must still see the map on the low there, so
    # every workspace's 3D viewports are captured, configured and restored too.
    workspaces = getattr(getattr(bpy, "data", None), "workspaces", None) or []
    for workspace in workspaces:
        for screen in getattr(workspace, "screens", []) or []:
            for candidate_area in getattr(screen, "areas", []) or []:
                if getattr(candidate_area, "type", "") != "VIEW_3D":
                    continue
                active_space = getattr(getattr(candidate_area, "spaces", None), "active", None)
                if active_space is None:
                    continue
                key = _space_key(active_space)
                if key in seen:
                    continue
                seen.add(key)
                yield active_space


def _preview_on_low_project_name(project) -> str:
    return _preview_on_low_project_name_impl(project)


def _any_preview_on_low_is_active(settings) -> bool:
    return _any_preview_on_low_is_active_impl(settings)


def _preview_on_low_is_active(
    settings,
    project,
    *,
    group_name: str = "",
    map_uuid: str = "",
    map_type: str = "",
    map_stack_index: int = -1,
) -> bool:
    session_state = _preview_session_state(settings)
    if session_state is None or not bool(getattr(session_state, "preview_on_low_active", False)):
        return False
    if str(getattr(session_state, "preview_on_low_project_name", "") or "") != _preview_on_low_project_name(project):
        return False
    stored_group = str(getattr(session_state, "preview_on_low_group_name", "") or "")
    if stored_group and group_name and stored_group != str(group_name or ""):
        return False
    normalized_map_uuid = str(map_uuid or "").strip()
    stored_map_uuid = str(getattr(session_state, "preview_on_low_map_uuid", "") or "").strip()
    if normalized_map_uuid:
        if stored_map_uuid:
            return stored_map_uuid == normalized_map_uuid
        # The stored preview carries no uuid (activated programmatically or by a
        # legacy path). Compare against the stored MAP TYPE — resolving the
        # *requested* map and matching its uuid to the *requested* uuid was a
        # tautology: every other map's button read as "already showing", so
        # switching maps toggled the preview OFF instead ("Restored low-mesh
        # material preview" with no map applied).
        stored_map_type = str(getattr(session_state, "preview_on_low_map_type", "") or "").strip().upper()
        if map_type:
            return bool(stored_map_type) and stored_map_type == str(map_type or "").strip().upper()
        requested_map = properties.find_map_setting_by_uuid(project, normalized_map_uuid)
        if requested_map is None:
            return False
        return bool(stored_map_type) and \
            str(getattr(requested_map, "map_type", "") or "").strip().upper() == stored_map_type
    if stored_map_uuid:
        active_map = properties.find_map_setting_by_uuid(project, stored_map_uuid)
        if active_map is None:
            return False
        if map_type and str(getattr(active_map, "map_type", "") or "").upper() != str(map_type or "").upper():
            return False
        if map_stack_index >= 0:
            resolved_map = properties.resolve_map_setting(project, map_stack_index=map_stack_index, map_type=map_type)
            if resolved_map is None:
                return False
            return properties.ensure_map_setting_uuid(resolved_map) == stored_map_uuid
        return True
    if map_type and str(getattr(session_state, "preview_on_low_map_type", "") or "").upper() != str(map_type or "").upper():
        return False
    if map_stack_index >= 0:
        stored_index = int(getattr(session_state, "preview_on_low_map_index", -1))
        if stored_index >= 0 and stored_index != map_stack_index:
            return False
    return True


def _preview_pbr_on_low_is_active(settings, project, *, group_name: str = "") -> bool:
    session_state = _preview_session_state(settings)
    if session_state is None or not bool(getattr(session_state, "preview_pbr_on_low_active", False)):
        return False
    if str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") != _preview_on_low_project_name(project):
        return False
    stored_group = str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "")
    if not stored_group:
        return True
    if group_name and stored_group != str(group_name or ""):
        return False
    return True


def _live_normal_preview_is_active(settings, project, *, group_name: str = "") -> bool:
    session_state = _preview_session_state(settings)
    if session_state is None or not bool(getattr(session_state, "live_normal_preview_active", False)):
        return False
    if str(getattr(session_state, "live_normal_preview_project_name", "") or "") != _preview_on_low_project_name(project):
        return False
    if group_name and str(getattr(session_state, "live_normal_preview_group_name", "") or "") != str(group_name or ""):
        return False
    return True


def _clear_preview_on_low_state(settings) -> None:
    _clear_preview_on_low_state_impl(settings)


def _restore_preview_on_low_overlay_state(settings) -> None:
    _restore_preview_on_low_overlay_state_impl(settings)


def _apply_runtime_preview_overlay_state(settings) -> None:
    _apply_runtime_preview_overlay_state_impl(settings)


def _capture_view3d_shading_state(context) -> str:
    return _capture_view3d_shading_state_impl(
        context,
        iter_view3d_spaces_fn=_iter_view3d_spaces,
        space_key_fn=_space_key,
    )


def _apply_preview_on_low_viewport_state(context) -> None:
    _apply_preview_on_low_viewport_state_impl(
        context,
        iter_view3d_spaces_fn=_iter_view3d_spaces,
    )


def _restore_preview_on_low_viewport_state(context, settings) -> None:
    _restore_preview_on_low_viewport_state_impl(
        context,
        settings,
        iter_view3d_spaces_fn=_iter_view3d_spaces,
        space_key_fn=_space_key,
    )


def _adopt_unmanaged_view3d_spaces(context, settings) -> int:
    return _adopt_unmanaged_view3d_spaces_impl(
        context,
        settings,
        iter_view3d_spaces_fn=_iter_view3d_spaces,
        space_key_fn=_space_key,
    )


# Owner token for the Window.workspace and View3DShading.type message-bus
# subscriptions. msgbus drops all subscriptions on file load, so _load_post re-subscribes.
_WORKSPACE_SWITCH_MSGBUS_OWNER = object()


def _on_window_workspace_changed(*_args) -> None:
    """A workspace switch can surface 3D viewports the preview never configured."""
    try:
        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        if settings is None or not _any_preview_on_low_is_active(settings):
            return
        if _adopt_unmanaged_view3d_spaces(context, settings) > 0:
            overlays.tag_redraw_all_view3d(scene=scene, window=getattr(context, "window", None), sync_preview=False)
    except Exception:
        pass


#: Last shading type seen per 3D viewport (space pointer -> type), so a shading change
#: notification can tell WHICH viewport switched: msgbus does not say.
_VIEWPORT_SHADING_TYPES: dict[int, str] = {}


def _record_viewport_shading_types(context) -> list:
    """Refresh the per-viewport record; return the spaces that just switched to Solid."""
    switched_to_solid = []
    seen = set()
    for space in _iter_view3d_spaces(context):
        key = _space_key(space)
        seen.add(key)
        shading_type = str(getattr(getattr(space, "shading", None), "type", "") or "")
        previous = _VIEWPORT_SHADING_TYPES.get(key)
        if previous is not None and previous != "SOLID" and shading_type == "SOLID":
            switched_to_solid.append(space)
        _VIEWPORT_SHADING_TYPES[key] = shading_type
    for key in [key for key in _VIEWPORT_SHADING_TYPES if key not in seen]:
        del _VIEWPORT_SHADING_TYPES[key]
    return switched_to_solid


def _on_viewport_shading_changed(*_args) -> None:
    """A viewport switched to Solid while Preview Baked Material is on: stop the preview.

    Solid mode cannot show the material preview (no normal map; with Color = Texture it
    shows whichever baked map node is active as flat colour), which read as "the preview
    is broken". Leaving it is the same as clicking the button off: the artist's own
    materials come back. The single-map preview is made for Solid and is left alone.
    """
    try:
        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        switched = _record_viewport_shading_types(context) if context is not None else []
        if not switched or settings is None:
            return
        session = _preview_session_state(settings)
        if session is None or not bool(getattr(session, "preview_pbr_on_low_active", False)):
            return
        _deactivate_preview_on_low(context)
    except Exception:
        pass


def _subscribe_workspace_switch() -> None:
    msgbus = getattr(bpy, "msgbus", None)
    window_type = getattr(getattr(bpy, "types", None), "Window", None)
    shading_type = getattr(getattr(bpy, "types", None), "View3DShading", None)
    if msgbus is None or window_type is None:
        return
    try:
        msgbus.clear_by_owner(_WORKSPACE_SWITCH_MSGBUS_OWNER)
        msgbus.subscribe_rna(
            key=(window_type, "workspace"),
            owner=_WORKSPACE_SWITCH_MSGBUS_OWNER,
            args=(),
            notify=_on_window_workspace_changed,
        )
        if shading_type is not None:
            _VIEWPORT_SHADING_TYPES.clear()
            context = getattr(bpy, "context", None)
            if context is not None:
                _record_viewport_shading_types(context)
            msgbus.subscribe_rna(
                key=(shading_type, "type"),
                owner=_WORKSPACE_SWITCH_MSGBUS_OWNER,
                args=(),
                notify=_on_viewport_shading_changed,
            )
    except Exception:
        pass


def _unsubscribe_workspace_switch() -> None:
    msgbus = getattr(bpy, "msgbus", None)
    if msgbus is None:
        return
    try:
        msgbus.clear_by_owner(_WORKSPACE_SWITCH_MSGBUS_OWNER)
    except Exception:
        pass


def _target_low_mesh_count(project, group_name: str) -> int:
    return _target_low_mesh_count_impl(project, group_name)


def _abspath(path_value: str) -> str:
    return _abspath_impl(path_value)


def _image_source_path(image) -> str:
    return _image_source_path_impl(image, abspath_fn=_abspath)


def _image_source_label(image) -> str:
    return _image_source_label_impl(image, image_source_path_fn=_image_source_path)


def _refresh_source_image(image):
    return _refresh_source_image_impl(image, image_source_path_fn=_image_source_path)


def _resolve_map_source(project, *, map_uuid: str = "", map_type: str = "", group_name: str = "", output_suffix: str = "", scene=None):
    return _resolve_map_source_impl(
        project,
        map_uuid=map_uuid,
        map_type=map_type,
        group_name=group_name,
        output_suffix=output_suffix,
        scene=scene,
        active_group_name_fn=_active_group_name,
        resolve_live_normal_preview_source_fn=_resolve_live_normal_preview_source,
        refresh_source_image_fn=_refresh_source_image,
        resolve_output_target_fn=_resolve_output_target,
        image_source_path_fn=_image_source_path,
        image_source_label_fn=_image_source_label,
        abspath_fn=_abspath,
    )


def _resolve_pbr_preview_inputs(project, group_name: str) -> dict:
    settings = getattr(getattr(bpy, "context", None), "scene", None)
    settings = getattr(settings, "fyr_baker_settings", None)
    session_state = _preview_session_state(settings)
    normal_source = str(
        getattr(session_state, "pbr_preview_normal_source", constants.PBR_PREVIEW_NORMAL_TANGENT)
        or constants.PBR_PREVIEW_NORMAL_TANGENT
    ).strip().upper()
    normal_map_type = (
        constants.MAP_BENT_NORMAL
        if normal_source == constants.PBR_PREVIEW_NORMAL_BENT
        else constants.MAP_NORMAL
    )
    return _resolve_pbr_preview_inputs_impl(
        project,
        group_name,
        resolve_map_source_fn=_resolve_map_source,
        normal_map_type=normal_map_type,
        ao_strength=float(getattr(session_state, "pbr_preview_ao_strength", 1.0) or 0.0),
    )


def _find_live_normal_preview_record():
    return _find_live_normal_preview_record_impl(
        _iter_scene_project_records,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
    )


def _clear_live_normal_preview_request() -> None:
    state = _live_normal_preview_runtime_state_from_globals()
    _clear_live_normal_preview_request_impl(state)
    _sync_live_normal_preview_runtime_state(state)


def _ensure_live_normal_preview_timer_registered(first_interval: float) -> bool:
    state = _live_normal_preview_runtime_state_from_globals()
    registered = _ensure_live_normal_preview_timer_registered_impl(
        state,
        timers=getattr(getattr(bpy, "app", None), "timers", None),
        timer_fn=_live_normal_preview_timer,
        first_interval=first_interval,
    )
    _sync_live_normal_preview_runtime_state(state)
    return registered


def _cancel_live_normal_preview_runtime() -> None:
    state = _live_normal_preview_runtime_state_from_globals()
    _cancel_live_normal_preview_runtime_impl(
        state,
        active_bake_snapshot_fn=runtime.active_bake_snapshot,
        cancel_active_bake_fn=runtime.cancel_active_bake,
    )
    _sync_live_normal_preview_runtime_state(state)


def _live_normal_preview_signature(project, group) -> tuple:
    return _live_normal_preview_signature_impl(
        project,
        group,
        constants_module=constants,
        resolve_live_normal_preview_dimensions_fn=export.resolve_live_normal_preview_dimensions,
        find_map_setting_fn=properties.find_map_setting,
        effective_normal_format_fn=properties.effective_normal_format,
        map_flip_green_fn=properties.map_flip_green,
        default_normal_format_for_map_fn=constants.default_normal_format_for_map,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
    )


def _live_normal_preview_timer():
    state = _live_normal_preview_runtime_state_from_globals()
    delay = _live_normal_preview_timer_tick_impl(
        state,
        find_live_normal_preview_record_fn=_find_live_normal_preview_record,
        active_bake_snapshot_fn=runtime.active_bake_snapshot,
        now_fn=time.monotonic,
        live_normal_preview_signature_fn=_live_normal_preview_signature,
        context=getattr(bpy, "context", None),
        prepare_live_normal_preview_job_fn=export.prepare_live_normal_preview_job,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        launch_bake_job_background_fn=runtime.launch_bake_job_background,
        start_background_polling_fn=runtime.start_background_polling,
        handle_background_bake_update_fn=_handle_background_bake_update,
    )
    _sync_live_normal_preview_runtime_state(state)
    return delay


def request_live_normal_preview_refresh(context, *, reason: str = "", delay_seconds: float = 0.2) -> bool:
    state = _live_normal_preview_runtime_state_from_globals()
    scheduled = _request_live_normal_preview_refresh_impl(
        state,
        context,
        ensure_live_normal_preview_timer_registered_fn=lambda first_interval: _ensure_live_normal_preview_timer_registered_impl(
            state,
            timers=getattr(getattr(bpy, "app", None), "timers", None),
            timer_fn=_live_normal_preview_timer,
            first_interval=first_interval,
        ),
        now_fn=time.monotonic,
        reason=reason,
        delay_seconds=delay_seconds,
    )
    _sync_live_normal_preview_runtime_state(state)
    return scheduled


def _resolve_live_normal_preview_source(scene, project):
    return _resolve_live_normal_preview_source_impl(
        scene,
        project,
        live_normal_preview_is_active_fn=_live_normal_preview_is_active,
    )


def _activate_live_normal_preview(context, project, group):
    return _activate_live_normal_preview_impl(
        context,
        project,
        group,
        constants_module=constants,
        target_low_mesh_count_fn=_target_low_mesh_count,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        resolve_map_source_fn=_resolve_map_source,
        sync_preview_material_for_project_fn=_sync_preview_material_for_project,
        request_live_normal_preview_refresh_fn=request_live_normal_preview_refresh,
        apply_preview_output_fn=preview_materials.apply_preview_output,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _handle_live_normal_preview_background_update(result) -> bool:
    state = _live_normal_preview_runtime_state_from_globals()
    handled = _handle_live_normal_preview_background_update_impl(
        state,
        result,
        find_live_normal_preview_record_fn=_find_live_normal_preview_record,
        sync_preview_material_for_project_fn=_sync_preview_material_for_project,
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
        ensure_live_normal_preview_timer_registered_fn=lambda first_interval: _ensure_live_normal_preview_timer_registered_impl(
            state,
            timers=getattr(getattr(bpy, "app", None), "timers", None),
            timer_fn=_live_normal_preview_timer,
            first_interval=first_interval,
        ),
        constants_module=constants,
    )
    _sync_live_normal_preview_runtime_state(state)
    return handled


def _deactivate_preview_on_low(context) -> int:
    return _deactivate_preview_on_low_impl(
        context,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        restore_preview_materials_fn=preview_materials.restore_preview_materials,
        restore_preview_on_low_overlay_state_fn=_restore_preview_on_low_overlay_state,
        restore_preview_on_low_viewport_state_fn=_restore_preview_on_low_viewport_state,
        clear_preview_on_low_state_fn=_clear_preview_on_low_state,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _activate_preview_on_low(context, project, source):
    return _activate_preview_on_low_impl(
        context,
        project,
        source,
        target_low_mesh_count_fn=_target_low_mesh_count,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        apply_preview_output_fn=preview_materials.apply_preview_output,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _activate_preview_on_low_all_groups(context, project, *, map_uuid: str = "", map_type: str, per_group_sources: list):
    return _activate_preview_on_low_all_groups_impl(
        context,
        project,
        map_uuid=map_uuid,
        map_type=map_type,
        per_group_sources=per_group_sources,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        apply_preview_output_all_groups_fn=preview_materials.apply_preview_output_all_groups,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _activate_preview_pbr_on_low(context, project, *, group_name: str, preview_inputs: dict | None = None):
    return _activate_preview_pbr_on_low_impl(
        context,
        project,
        group_name=group_name,
        preview_inputs=preview_inputs,
        constants_module=constants,
        target_low_mesh_count_fn=_target_low_mesh_count,
        resolve_pbr_preview_inputs_fn=_resolve_pbr_preview_inputs,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        apply_preview_pbr_output_fn=preview_materials.apply_preview_pbr_output,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _activate_preview_pbr_on_low_all_groups(context, project):
    return _activate_preview_pbr_on_low_all_groups_impl(
        context,
        project,
        constants_module=constants,
        resolve_pbr_preview_inputs_fn=_resolve_pbr_preview_inputs,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        cancel_live_normal_preview_runtime_fn=_cancel_live_normal_preview_runtime,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        apply_preview_pbr_output_all_groups_fn=preview_materials.apply_preview_pbr_output_all_groups,
        cancel_debug_overlay_refresh_fn=getattr(runtime, "cancel_debug_overlay_refresh", None),
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


def _resolve_output_target(
    project,
    *,
    output_index: int = -1,
    map_uuid: str = "",
    map_type: str = "",
    group_name: str = "",
    output_suffix: str = "",
    strict: bool = False,
):
    return _resolve_output_target_impl(
        project,
        output_index=output_index,
        map_uuid=map_uuid,
        map_type=map_type,
        group_name=group_name,
        output_suffix=output_suffix,
        strict=strict,
    )


def _apply_image_editor_display_channels(context, channel_mode: str) -> bool:
    applied = False
    for active_space in _iter_image_editor_spaces(context):
        if not hasattr(active_space, "display_channels"):
            continue
        active_space.display_channels = channel_mode
        applied = True
    return applied


def _apply_image_editor_mip_level(context, mip_level: int) -> bool:
    applied = False
    zoom_percentage = image_inspection.zoom_percentage_for_mip(mip_level)
    for active_space in _iter_image_editor_spaces(context):
        if not hasattr(active_space, "zoom_percentage"):
            continue
        active_space.zoom_percentage = zoom_percentage
        applied = True
    return applied


def _set_bake_panel_section(settings, section: str) -> str:
    if settings is None:
        return constants.BAKE_PANEL_SETTINGS
    normalized_section = str(section or constants.BAKE_PANEL_SETTINGS).strip().upper()
    valid_sections = {item[0] for item in constants.BAKE_PANEL_SECTION_ITEMS}
    if normalized_section not in valid_sections:
        normalized_section = constants.BAKE_PANEL_SETTINGS
    setattr(properties.scene_ui_state(settings), "bake_panel_section", normalized_section)
    return normalized_section


def _load_output_target(context, project, target, index=None):
    if target is None:
        return None

    properties.set_preview_map_type(context.scene.fyr_baker_settings, target.map_type)
    editor_state = properties.image_editor_state(context.scene.fyr_baker_settings)
    image = runtime.load_managed_output_image(target.file_path)
    _sync_preview_material_for_project(context.scene, project)
    _show_image_in_editor(context, image)
    _apply_image_editor_display_channels(
        context,
        getattr(editor_state, "channel_mode", constants.IMAGE_CHANNEL_COLOR),
    )
    _apply_image_editor_mip_level(
        context,
        getattr(editor_state, "mip_level", 0),
    )

    if index is not None:
        # Use the exact index the caller navigated to. Composite (texture-set) outputs
        # register one entry per group but share a file path, so matching by file_path
        # collapses duplicates to the first match — breaking linear Next/Previous
        # traversal and making a clicked entry jump to a sibling.
        project.active_output_index = int(index)
    else:
        project.active_output_index = next(
            (idx for idx, item in enumerate(project.latest_outputs) if item.file_path == target.file_path),
            0,
        )
    return image


def _load_map_source(context, project, source):
    if source is None:
        return None
    target = source["target"]
    image = source["image"]
    resolved_index = source["resolved_index"]
    properties.set_preview_map_type(context.scene.fyr_baker_settings, target.map_type)
    editor_state = properties.image_editor_state(context.scene.fyr_baker_settings)
    _sync_preview_material_for_project(context.scene, project)
    _show_image_in_editor(context, image)
    _apply_image_editor_display_channels(
        context,
        getattr(editor_state, "channel_mode", constants.IMAGE_CHANNEL_COLOR),
    )
    _apply_image_editor_mip_level(
        context,
        getattr(editor_state, "mip_level", 0),
    )
    if resolved_index is not None:
        project.active_output_index = int(resolved_index)
    return image


def _resolve_preview_material_target(scene, project):
    return _resolve_preview_material_target_impl(
        scene,
        project,
        preview_on_low_is_active_fn=_preview_on_low_is_active,
        resolve_map_source_fn=_resolve_map_source,
    )


def _resolve_live_normal_preview_state(scene, project):
    return _resolve_live_normal_preview_state_impl(
        scene,
        project,
        live_normal_preview_is_active_fn=_live_normal_preview_is_active,
        resolve_live_normal_preview_source_fn=_resolve_live_normal_preview_source,
    )


def _resolve_pbr_preview_state(scene, project):
    return _resolve_pbr_preview_state_impl(
        scene,
        project,
        preview_pbr_on_low_is_active_fn=_preview_pbr_on_low_is_active,
        resolve_pbr_preview_inputs_fn=_resolve_pbr_preview_inputs,
    )


def _is_bake_running() -> bool:
    snapshot = runtime.active_bake_snapshot()
    return snapshot is not None and bool(getattr(snapshot, "running", False))


def _sync_preview_material_for_project(scene, project) -> int:
    return _sync_preview_material_for_project_impl(
        scene,
        project,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        preview_on_low_is_active_fn=_preview_on_low_is_active,
        preview_on_low_project_name_fn=_preview_on_low_project_name,
        live_normal_preview_is_active_fn=_live_normal_preview_is_active,
        resolve_live_normal_preview_state_fn=_resolve_live_normal_preview_state,
        resolve_pbr_preview_state_fn=_resolve_pbr_preview_state,
        clear_preview_on_low_state_fn=_clear_preview_on_low_state,
        resolve_preview_material_target_fn=_resolve_preview_material_target,
        apply_preview_output_fn=preview_materials.apply_preview_output,
        apply_preview_output_all_groups_fn=preview_materials.apply_preview_output_all_groups,
        resolve_map_source_fn=_resolve_map_source,
        apply_preview_pbr_output_fn=preview_materials.apply_preview_pbr_output,
        apply_preview_pbr_output_all_groups_fn=preview_materials.apply_preview_pbr_output_all_groups,
        restore_preview_materials_fn=preview_materials.restore_preview_materials,
        is_bake_running_fn=_is_bake_running,
    )


def _start_dirty_tracker_session(project) -> None:
    """Start the dirty tracker and auto-rebake timer for the given project."""
    prefs = preferences.get_preferences()
    debounce = float(getattr(prefs, "dirty_rebake_debounce", 0.3)) if prefs is not None else 0.3
    dirty_tracker.start_session(project, debounce=debounce)
    runtime.set_dirty_rebake_callback(_trigger_dirty_rebake)
    runtime.start_dirty_check_timer()


def _stop_dirty_tracker_session() -> None:
    """Stop the dirty tracker and auto-rebake timer."""
    dirty_tracker.stop_session()
    runtime.clear_dirty_rebake_callback()
    runtime.stop_dirty_check_timer()


def _reset_live_bake_runtime_on_load() -> None:
    global _DIRTY_REBAKE_SNAPSHOT
    _DIRTY_REBAKE_SNAPSHOT = None
    _stop_dirty_tracker_session()
    stop_background_polling = getattr(runtime, "stop_background_polling", None)
    if callable(stop_background_polling):
        stop_background_polling()
    active_bake_snapshot = getattr(runtime, "active_bake_snapshot", None)
    cancel_active_bake = getattr(runtime, "cancel_active_bake", None)
    if callable(active_bake_snapshot) and callable(cancel_active_bake):
        snapshot = active_bake_snapshot()
        if snapshot is not None and bool(getattr(snapshot, "running", False)):
            cancel_active_bake()
    # cancel_active_bake only *requests* cancellation; it relies on a later poll
    # to finalize and drop _ACTIVE_BAKE. We stopped background polling just above,
    # and the newly loaded file has no project to finalize the old job against, so
    # that poll never comes — the resident worker stays alive, so snapshot.running
    # would read True forever and the file would open onto a phantom "a bake is
    # running" banner. Clear the bookkeeping outright (worker/warm state kept).
    clear_active_bake_state = getattr(runtime, "clear_active_bake_state", None)
    if callable(clear_active_bake_state):
        # Keep the cancel request we just wrote: clearing it would delete the file
        # the resident worker polls, and the worker would keep baking the project
        # from the file we just closed.
        try:
            clear_active_bake_state(keep_requests=True)
        except TypeError:
            clear_active_bake_state()
    # The Cycles material queue runs on a NON-persistent timer that Blender drops on
    # load, while its registry entry survives: without this, every bake for the rest
    # of the session is refused with "Blender is still baking material detail from
    # the previous run", and Stop cannot clear it either.
    try:
        dropped = export.reset_async_material_bakes()
    except Exception as exc:
        print(f"[MasterBaker] could not reset the material bake queue on load: {exc!r}")
        dropped = 0
    if dropped:
        print(f"[MasterBaker] dropped {dropped} material bake queue(s) belonging to the closed file")
    _DEFERRED_MATERIAL_BACKEND_RESULTS.clear()
    _reset_prepare_feedback_runtime()


def _active_partial_bake_snapshot(project) -> dirty_tracker.DirtyMatrix | None:
    if not map_rebuild.active_bake_is_partial(project):
        return None
    selected_map_types = set(map_rebuild.active_bake_map_types(project))
    selected_group_names = map_rebuild.active_bake_group_names(project)
    if not selected_map_types or not selected_group_names:
        return None
    return {group_name: set(selected_map_types) for group_name in selected_group_names}


def _finalize_successful_bake_state(project, *, dirty_snapshot: dirty_tracker.DirtyMatrix | None = None) -> None:
    # The backend build has now baked here, so its GPU shaders are compiled: retire the
    # first-bake-after-update notice.
    runtime.mark_backend_shaders_ready()
    if map_rebuild.active_bake_is_partial(project):
        map_rebuild.update_partial_bake_state(
            project,
            map_rebuild.active_bake_group_names(project),
            map_rebuild.active_bake_map_types(project),
            map_rebuild.active_bake_map_uuids(project),
        )
        clear_snapshot = dirty_snapshot or _active_partial_bake_snapshot(project)
        if clear_snapshot is not None:
            for group_name, map_types in clear_snapshot.items():
                dirty_tracker.clear_dirty(group_name, map_types)
        _rebase_live_reproject(project)
        return
    map_rebuild.record_bake_state(project)
    dirty_tracker.clear_all_dirty()
    _rebase_live_reproject(project)


def _rebase_live_reproject(project) -> None:
    # The bake just replaced the output textures; a Live Reproject reference
    # captured before it would resample the old pixels over them on the next UV edit.
    try:
        texture_reprojection.rebase_after_bake(project)
    except Exception:
        traceback.print_exc()


def _update_bake_state_partial(project, dirty_snapshot: dirty_tracker.DirtyMatrix) -> None:
    del dirty_snapshot
    map_rebuild.update_partial_bake_state(
        project,
        map_rebuild.active_bake_group_names(project),
        map_rebuild.active_bake_map_types(project),
        map_rebuild.active_bake_map_uuids(project),
    )


def _set_pending_bake_state(
    context,
    project,
    operator_name: str,
    collision_groups,
    live_bake_mode="preserve",
    *,
    allow_missing_uvs: bool = False,
):
    """Populate _PENDING_BAKE_STATE with duplicate-conflict info so the dialog operator can act on it.

    ``collision_groups`` is the list-of-groups returned by
    ``export.find_duplicate_output_map_settings`` — each group is a list of
    ``(map_setting, effective_type, effective_suffix)`` tuples for all maps in a collision."""
    scene_name = getattr(getattr(context, "scene", None), "name", "") or ""
    serialised = []
    for group in collision_groups:
        if not group:
            continue
        _ms0, effective_type, effective_suffix = group[0]
        serialised.append({
            "effective_type": str(effective_type),
            "effective_suffix": str(effective_suffix or ""),
            "label": naming.map_label(str(effective_type)),
            "uuids": [properties.ensure_map_setting_uuid(ms) for ms, _t, _s in group],
        })

    _PENDING_BAKE_STATE.clear()
    _PENDING_BAKE_STATE.update({
        "scene_name": scene_name,
        "project_name": getattr(project, "name", "") or "",
        "operator_name": operator_name,
        "live_bake_mode": live_bake_mode,
        "allow_missing_uvs": bool(allow_missing_uvs),
        "conflict_groups": serialised,
    })


def _groups_without_bakeable_low_meshes(project, group_names) -> set[str]:
    """Names of the given groups whose low meshes all lack UV layers.

    Such a group has nothing to write into, so baking it can only produce a
    fabricated unwrap over its texture set's other meshes. See export._iter_bakeable_low_slots.
    """
    wanted = {str(name or "") for name in (group_names or [])}
    skipped: set[str] = set()
    for group in getattr(project, "groups", []):
        name = str(getattr(group, "name", "") or "")
        if name not in wanted:
            continue
        role_state = properties.group_role_assignments_state(group)
        slots = [
            slot
            for slot in getattr(role_state, "low_meshes", [])
            if getattr(slot, "object_ref", None) is not None
        ]
        if slots and not any(export.slot_object_has_uv_layers(slot) for slot in slots):
            skipped.add(name)
    return skipped


def _selected_map_uuids_for_bake(project, *, map_types=None, map_uuids=None) -> list[str]:
    if map_uuids is not None:
        return [str(map_uuid or "").strip() for map_uuid in map_uuids if str(map_uuid or "").strip()]
    if map_types is None:
        return map_rebuild.enabled_map_uuids(project)

    selected_types = {str(map_type or "").strip().upper() for map_type in map_types if str(map_type or "").strip()}
    if not selected_types:
        return []
    selected_uuids: list[str] = []
    for map_setting in getattr(project, "maps", []):
        if getattr(map_setting, "is_add_phantom", False):
            continue
        if not bool(getattr(map_setting, "enabled", False)):
            continue
        if str(getattr(map_setting, "map_type", "") or "").strip().upper() not in selected_types:
            continue
        map_uuid = properties.ensure_map_setting_uuid(map_setting)
        if map_uuid:
            selected_uuids.append(map_uuid)
    return selected_uuids


def _map_types_for_bake(project, *, map_types=None, map_uuids=None) -> list[str]:
    if map_uuids is not None:
        wanted = {str(map_uuid or "").strip() for map_uuid in map_uuids}
        return [
            str(getattr(item, "map_type", "") or "")
            for item in getattr(project, "maps", [])
            if str(getattr(item, "uuid", "") or "").strip() in wanted
        ]
    if map_types is not None:
        return [str(map_type or "").strip().upper() for map_type in map_types]
    return map_rebuild.enabled_map_types(project)


# First bake of a session on a cold scene: capturing every evaluated high mesh
# inside the operator freezes the UI for the whole scene at once (7.6s measured
# on an 8M-tri scene in a fresh Blender). When any high mesh is cold, the bake
# is deferred: a timer warms one mesh per tick behind the "Setting up bake
# project" overlay (same announce-then-work pattern as the speculative
# prepare), then starts the real bake.
_DEFERRED_BAKE_STATE: dict | None = None
_DEFERRED_BAKE_RUNNING = False


def _reset_prepare_feedback_runtime() -> None:
    """Drop prepare timers and UI state that cannot survive a reload or file load."""
    global _DEFERRED_BAKE_STATE, _DEFERRED_BAKE_RUNNING
    global _HIGH_WARM_STATUS_ACTIVE, _HIGH_WARM_ANNOUNCED

    cancel_speculative_prepare = getattr(runtime, "cancel_speculative_prepare", None)
    if callable(cancel_speculative_prepare):
        cancel_speculative_prepare()
    # Blender drops the debounce timer on load but not its flag, and the depsgraph
    # handler trusts the flag alone, so a load mid-debounce disabled background
    # prepare for the rest of the session (2026-09-26).
    _cancel_pending_bg_prepare()

    # That cancels the SCHEDULING timer only. A PREPARE already dispatched belongs to
    # the file being closed, and the ready-check timer that would have cleared it did
    # not survive the load, so the flag has to be dropped here.
    reset_prepare_state = getattr(runtime, "reset_prepare_state_for_file_load", None)
    if callable(reset_prepare_state):
        reset_prepare_state()

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister"):
        try:
            if not hasattr(timers, "is_registered") or timers.is_registered(_deferred_bake_timer):
                timers.unregister(_deferred_bake_timer)
        except Exception:
            pass

    _DEFERRED_BAKE_STATE = None
    _DEFERRED_BAKE_RUNNING = False
    _HIGH_WARM_STATUS_ACTIVE = False
    _HIGH_WARM_ANNOUNCED = None
    global _HIGH_WARM_OUT_OF_MEMORY
    _HIGH_WARM_FAILED.clear()
    _HIGH_WARM_OUT_OF_MEMORY = False

    try:
        workspace = getattr(getattr(bpy, "context", None), "workspace", None)
        if workspace is not None:
            workspace.status_text_set(None)
    except Exception:
        pass
    try:
        from . import setup_progress

        setup_progress.end()
    except Exception:
        pass


_ESCAPE_POLL = [0.0, False]
#: Escape is polled at most this often: the check runs several times per exported mesh and
#: GetAsyncKeyState costs ~0.25 ms of a busy Blender (0.5 s over a 300-group job build).
_ESCAPE_POLL_INTERVAL_S = 0.05


def _capture_cancel_requested() -> bool:
    """Allow Escape to abort an indexed capture while Blender's UI loop is blocked."""
    state = _DEFERRED_BAKE_STATE
    if state is not None and bool(state.get("cancel_requested", False)):
        return True
    now = time.monotonic()
    if now - _ESCAPE_POLL[0] < _ESCAPE_POLL_INTERVAL_S:
        return _ESCAPE_POLL[1]
    try:
        pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000)
    except (AttributeError, OSError):
        pressed = False
    _ESCAPE_POLL[0] = now
    _ESCAPE_POLL[1] = pressed
    return pressed


class _DeferredBakeReporter:
    """Operator stand-in for a bake started from a timer tick. Reports go to
    the console; the status properties _run_bake sets carry the user-visible
    outcome."""

    def report(self, _levels, message):
        print(f"[Fyr Baker] {message}")


def _high_mesh_warm_state(project, group_names=None):
    """Return (cold_objects, total_high_count) for the groups selected to bake."""
    wanted = {str(name or "") for name in group_names} if group_names else None
    cold = []
    total = 0
    seen = set()
    for group in getattr(project, "groups", []):
        if wanted is not None and str(getattr(group, "name", "") or "") not in wanted:
            continue
        for slot in properties.effective_high_mesh_slots(group):
            obj = getattr(slot, "object_ref", None)
            if obj is None or getattr(obj, "type", "") != "MESH" or obj.name in seen:
                continue
            seen.add(obj.name)
            total += 1
            try:
                if not high_mesh_cache.high_mesh_ref_is_warm(obj):
                    cold.append(obj)
            except Exception:
                pass
    return cold, total


def _selected_bake_has_material_detail(project, map_types, map_uuids, group_names) -> bool:
    wanted_groups = {str(name or "") for name in group_names} if group_names else None
    groups = [
        group
        for group in getattr(project, "groups", [])
        if wanted_groups is None or str(getattr(group, "name", "") or "") in wanted_groups
    ]
    for item in export._selected_project_maps(project, map_types, map_uuids):  # noqa: SLF001
        map_type = str(getattr(item, "map_type", "") or "").strip().upper()
        mode = str(
            getattr(item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
            or constants.MATERIAL_DETAIL_AUTO
        ).strip().upper()
        if mode == constants.MATERIAL_DETAIL_OFF:
            continue
        if map_type == constants.MAP_NORMAL and any(
            export._group_has_material_normal_detail(group) for group in groups  # noqa: SLF001
        ):
            return True
        if map_type == constants.MAP_AO:
            explicit = (
                getattr(item, "material_detail_image", None)
                if mode == constants.MATERIAL_DETAIL_MANUAL
                else None
            )
            if any(
                export._group_material_ao_source(group, explicit) is not None  # noqa: SLF001
                for group in groups
            ):
                return True
    return False


def _end_deferred_bake_feedback():
    from . import setup_progress

    try:
        setup_progress.end()
    except Exception:
        pass
    try:
        workspace = getattr(bpy.context, "workspace", None)
        if workspace is not None:
            workspace.status_text_set(None)
    except Exception:
        pass


#: _step_automatic_cage_fit state for the background prepare (the bake path keeps its own).
_SPECULATIVE_CAGE_FIT_STATE: dict = {}


def _automatic_cage_groups_to_fit(project, group_names=None) -> list:
    try:
        return export.automatic_cage_groups_to_fit(project, group_names)
    except Exception:
        return []


def _step_automatic_cage_fit(context, project, state: dict, group_names) -> bool:
    """One tick of fitting the bake's automatic cages behind the setup card.

    Announce tick, then a fit tick that fits groups until ~0.2 s have passed (a stored fit
    is a few ms; a cold one takes seconds, so the card is on screen during the freeze it
    explains). Returns True while there is more to do.

    The groups to fit are listed once per run: listing signs every group's objects
    (~0.4 s on a 73-group gun), and listing again on every tick, two ticks per group,
    was ~40 s of a bake whose fits were all stored (1.6 s of real work)."""
    from . import setup_progress

    queue = state.get("cage_fit_queue")
    if queue is None:
        pending_groups = _automatic_cage_groups_to_fit(project, group_names)
        queue = [str(getattr(group, "name", "") or "") for group in pending_groups]
        if len(pending_groups) > 1:
            export.begin_cage_tree_pool(pending_groups)  # shared highs are built once
        state["cage_fit_queue"] = queue
        state["cage_fit_total"] = len(queue)
        state["cage_fit_rechecked"] = False
    if not queue and not state.get("cage_fit_rechecked"):
        # Anything edited while the queue ran is fitted too (one more listing, not one a tick).
        state["cage_fit_rechecked"] = True
        queue.extend(str(getattr(group, "name", "") or "") for group in _automatic_cage_groups_to_fit(project, group_names))
        state["cage_fit_total"] = int(state.get("cage_fit_total", 0) or 0) + len(queue)
    if not queue:
        export.end_cage_tree_pool()
        for key in ("cage_fit_queue", "cage_fit_total", "cage_fit_announced", "cage_fit_rechecked", "cage_fit_batch_tried"):
            state.pop(key, None)
        return False
    total = max(int(state.get("cage_fit_total", 0) or 0), len(queue))
    if not state.get("cage_fit_announced"):
        state["cage_fit_announced"] = True
        done = total - len(queue)
        detail = f"{queue[0]} ({done + 1}/{total})"
        try:
            setup_progress.begin("Fitting cages for the bake", detail, done / total)
            workspace = getattr(context, "workspace", None)
            if workspace is not None:
                workspace.status_text_set(f"Fitting cages for the bake: {detail}")
            overlays.tag_redraw_all_view3d(scene=getattr(context, "scene", None))
        except Exception:
            pass
        return True
    state["cage_fit_announced"] = False
    groups = {str(getattr(group, "name", "") or ""): group for group in getattr(project, "groups", []) or []}
    depsgraph = context.evaluated_depsgraph_get()
    if not state.get("cage_fit_batch_tried"):
        # GPU cage fit: every pending group in one batched request (see export.prefit_automatic_cages_batch).
        state["cage_fit_batch_tried"] = True
        batch = [groups[name] for name in queue if name in groups]
        _suppress_bg_prepare()
        try:
            if batch and export.prefit_automatic_cages_batch(batch, depsgraph):
                queue.clear()
                return True
        except Exception:
            traceback.print_exc()
        finally:
            _suppress_bg_prepare()
    deadline = time.perf_counter() + 0.2
    while queue:
        group = groups.get(queue.pop(0))
        if group is None:
            continue
        _suppress_bg_prepare()
        try:
            export.prefit_automatic_cage(group, depsgraph)
        except Exception:
            # Leave it to the export's own fit (which reports the error); do not spin.
            traceback.print_exc()
        finally:
            _suppress_bg_prepare()
        if time.perf_counter() >= deadline:
            break
    return True


#: Main-thread seconds one deferred-bake tick may spend capturing high meshes.
_DEFERRED_TICK_BUDGET_SECONDS = 0.07
#: A high that was exported this many times and still reads cold is left to the bake's own
#: synchronous export instead of being retried forever.
_DEFERRED_EXPORT_ATTEMPTS = 2


def _announce_deferred_progress(setup_progress, context, scene, state, upcoming) -> None:
    """Paint the setup card for the next mesh(es); ``upcoming`` is objects or names."""
    done = max(0, state["total"] - len(state.get("cold_names") or ()))
    first = upcoming[0] if upcoming else "high-poly meshes"
    name = getattr(first, "name", first)
    detail = f"Preparing {name} ({min(done + 1, state['total'])}/{state['total']})…"
    try:
        setup_progress.begin("Setting up bake project", detail)
        workspace = getattr(context, "workspace", None)
        if workspace is not None:
            workspace.status_text_set(f"Setting up bake project: {detail}")
        overlays.tag_redraw_all_view3d(scene=scene, sync_preview=False)
    except Exception:
        pass


def _deferred_bake_timer():
    from . import setup_progress

    global _DEFERRED_BAKE_STATE, _DEFERRED_BAKE_RUNNING, _MATERIAL_PHASE_TWO_ACTIVE
    state = _DEFERRED_BAKE_STATE
    if state is None:
        return None
    context = bpy.context
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = None
    for candidate in getattr(settings, "projects", []) if settings is not None else []:
        if str(getattr(candidate, "name", "") or "") == state["project_name"]:
            project = candidate
            break
    if project is None:
        # Project removed / file changed while the warm-up was pending.
        _DEFERRED_BAKE_STATE = None
        _end_deferred_bake_feedback()
        return None

    # The cold list is taken once and shrinks as objects warm: re-checking every high
    # on every tick made the wait quadratic in the group count.
    high_mesh_cache.reap_prewarm_writes()
    cold_names = state.get("cold_names")
    if cold_names is None:
        cold, _total = _high_mesh_warm_state(project, state["selected_group_names"])
        cold_names = state["cold_names"] = [obj.name for obj in cold]
    attempts = state.setdefault("attempts", {})
    waiting: list = []  # cold and not being written yet
    still_cold: list[str] = []
    for name in cold_names:
        candidate = bpy.data.objects.get(name)
        if candidate is None or getattr(candidate, "type", "") != "MESH":
            continue
        if attempts.get(name, 0) >= _DEFERRED_EXPORT_ATTEMPTS:
            # Exported twice and still cold (capture keeps failing): move on instead of
            # spinning forever; the bake's own export captures it synchronously.
            continue
        try:
            if high_mesh_cache.high_mesh_ref_is_warm(candidate):
                continue
        except Exception:
            pass
        still_cold.append(name)
        if not high_mesh_cache.write_in_flight(candidate):
            waiting.append(candidate)
    cold_names[:] = still_cold
    if cold_names:
        if not state.get("card_shown"):
            # Announce tick: paint the overlay first, capture on the next tick so the
            # text is on screen during the freeze it explains.
            state["card_shown"] = True
            _announce_deferred_progress(setup_progress, context, scene, state, waiting or cold_names)
            return 0.01
        if not waiting:
            # Everything is captured; the last writes finish on their worker threads.
            return 0.02
        # Several meshes per tick, within a main-thread budget. Only the evaluated-mesh
        # capture runs here (87 ms on average on the 71-high Uzi); the file write runs on
        # the prewarm's worker threads, the capture of mesh n+1 overlapping the write of n.
        started = time.perf_counter()
        _suppress_bg_prepare()
        try:
            depsgraph = context.evaluated_depsgraph_get()
            for obj in waiting:
                status = high_mesh_cache.submit_high_write(obj, depsgraph)
                if status == high_mesh_cache.WRITE_BUSY:
                    break
                if status == high_mesh_cache.WRITE_PENDING:
                    continue
                attempts[obj.name] = attempts.get(obj.name, 0) + 1
                if status == high_mesh_cache.WRITE_SYNC:
                    # Nothing for a worker to write (floater faces, a mesh without the
                    # fast path): the export has to run here.
                    high_mesh_cache.resolve_high_mesh_ref(obj, depsgraph)
                if time.perf_counter() - started >= _DEFERRED_TICK_BUDGET_SECONDS:
                    break
        except MemoryError as exc:
            # Out of memory exporting a high mesh: running the bake anyway (the
            # attempts fallback above) would export it again synchronously, another
            # multi-GB attempt on a machine that is already out of memory.
            _DEFERRED_BAKE_STATE = None
            _end_deferred_bake_feedback()
            _sync_tag_status(context, f"Bake failed: {exc}")
            return None
        except Exception:
            pass
        finally:
            _suppress_bg_prepare()
        _announce_deferred_progress(setup_progress, context, scene, state, cold_names)
        return 0.01

    # Automatic cages are fitted one group per tick behind the card (a dense group's fit
    # and ray check take seconds), so the bake never freezes on them in one block.
    if not state.get("cages_fitted"):
        if _step_automatic_cage_fit(context, project, state, state["selected_group_names"]):
            return 0.05
        state["cages_fitted"] = True

    if not state.get("writing_announced"):
        # Announce tick: writing the job (and parking a big scene's highs) blocks for
        # tens of seconds on a 71-group gun, and set in the same tick the card never
        # drew, so the freeze showed the last cage group's name.
        state["writing_announced"] = True
        try:
            setup_progress.begin("Setting up bake project", "Writing the bake job…")
            overlays.tag_redraw_all_view3d(scene=scene)
        except Exception:
            pass
        return 0.05

    _DEFERRED_BAKE_STATE = None
    _DEFERRED_BAKE_RUNNING = True
    # A staged phase stays that phase across the wait: without the mark it plans its
    # stages again and queues itself, rebaking the Normal row forever.
    phase_two = bool(state.get("material_phase_two"))
    _MATERIAL_PHASE_TWO_ACTIVE = phase_two
    launched = False
    try:
        outcome = _run_bake(
            _DeferredBakeReporter(),
            context,
            project,
            map_types=state["map_types"],
            map_uuids=state["map_uuids"],
            group_names=state["group_names"],
            start_message=state["start_message"],
            initial_status=state["initial_status"],
            live_bake_mode=state["live_bake_mode"],
            allow_missing_uvs=bool(state.get("allow_missing_uvs", False)),
            material_normal_source=state.get("material_normal_source"),
            own_tiles_only=bool(state.get("own_tiles_only")),
        )
        launched = "FINISHED" in (outcome or set())
    finally:
        _MATERIAL_PHASE_TWO_ACTIVE = False
        _DEFERRED_BAKE_RUNNING = False
        _end_deferred_bake_feedback()
        if phase_two and not launched:
            # No completion callback will fire for a phase that never launched, so the
            # rest of the queue would strand for a later unrelated bake.
            _finish_per_group_merge(project, succeeded=False)
            _clear_pending_material_phase()
    return None


def _defer_bake_until_high_meshes_warm(
    operator,
    context,
    project,
    *,
    map_types,
    map_uuids,
    group_names,
    start_message,
    initial_status,
    live_bake_mode,
    selected_group_names,
    allow_missing_uvs: bool = False,
    material_normal_source: dict | None = None,
    own_tiles_only: bool = False,
) -> bool:
    global _DEFERRED_BAKE_STATE
    if not export.selection_needs_high_geometry(project, map_types, map_uuids):
        # Wireframe-only: nothing samples the high-poly, so no cache warm-up or cage fit.
        return False
    material_detail_pending = _selected_bake_has_material_detail(
        project, map_types, map_uuids, selected_group_names
    )
    # Indexed geometry must be captured into the bake workspace's live section.
    # Warming through the legacy export cache would create a high .fymesh and
    # turn the production bake back into file transport.
    if indexed_geometry.enabled() and not material_detail_pending:
        return False
    if _DEFERRED_BAKE_RUNNING:
        return False
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False
    cold, total = (
        ([], 0)
        if indexed_geometry.enabled()
        else _high_mesh_warm_state(project, selected_group_names)
    )
    cage_fits_pending = bool(_automatic_cage_groups_to_fit(project, selected_group_names))
    if not cold and not material_detail_pending and not cage_fits_pending:
        return False
    _DEFERRED_BAKE_STATE = {
        "project_name": str(getattr(project, "name", "") or ""),
        "selected_group_names": list(selected_group_names or []),
        "map_types": list(map_types) if map_types is not None else None,
        "map_uuids": list(map_uuids) if map_uuids is not None else None,
        "group_names": list(group_names) if group_names is not None else None,
        "start_message": start_message,
        "initial_status": initial_status,
        "live_bake_mode": live_bake_mode,
        "allow_missing_uvs": bool(allow_missing_uvs),
        "material_normal_source": dict(material_normal_source) if material_normal_source else None,
        "material_phase_two": bool(_MATERIAL_PHASE_TWO_ACTIVE),
        "own_tiles_only": bool(own_tiles_only),
        "card_shown": False,
        "attempts": {},
        "cold_names": [obj.name for obj in cold],
        "total": total,
    }
    scene_settings = context.scene.fyr_baker_settings
    project.last_status_message = "Setting up bake project…"
    scene_settings.status_message = "Setting up bake project…"
    if material_detail_pending and not cold:
        try:
            from . import setup_progress

            setup_progress.begin(
                "Setting up bake project",
                "Preparing high-poly material detail…",
            )
            overlays.tag_redraw_all_view3d(scene=context.scene)
        except Exception:
            pass
    try:
        if not timers.is_registered(_deferred_bake_timer):
            timers.register(_deferred_bake_timer, first_interval=0.05)
    except Exception:
        _DEFERRED_BAKE_STATE = None
        return False
    operator.report(
        {"INFO"},
        "Preparing high-poly material detail…" if material_detail_pending and not cold else "Preparing high-poly meshes…",
    )
    return True


def _run_derived_only_bake(operator, context, project, scene_settings, prepared):
    """Finish a job whose every output is drawn by the addon (Wireframe rows)."""
    progress = protocol.BakeProgress(
        status=constants.STATUS_COMPLETE, message="Bake complete", percent=100.0
    )
    try:
        progress.warnings.extend(
            derived_outputs.apply_workspace_derived_outputs(prepared.workspace_path, progress)
        )
        export.apply_progress_to_project(project, progress, merge_existing=True)
        with dirty_tracker.suppress():
            runtime.refresh_project_output_images(project)
            _sync_preview_material_for_project(context.scene, project)
    finally:
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
    for message in progress.warnings:
        operator.report({"WARNING"}, message)
    project.last_warning_count = len(progress.warnings)
    project.last_warning_summary = progress.warnings[0] if progress.warnings else ""
    project.last_status_message = constants.STATUS_COMPLETE
    scene_settings.status_message = constants.STATUS_COMPLETE
    operator.report({"INFO"}, f"Bake complete, {len(progress.produced_files)} map(s)")
    _consume_pending_material_phase(succeeded=True)
    return {"FINISHED"}


def _run_material_only_bake(
    operator, context, project, scene_settings, prepared,
    selected_map_types, selected_map_uuids, selected_group_names,
):
    """Run a MATERIAL-workflow bake entirely addon-side (Cycles self-bake), with no backend
    geometry phase. Writes outputs, registers them, refreshes the reversible PBR preview."""
    if not prepared.material_bake_specs:
        operator.report({"ERROR"}, "No material outputs to bake for this project")
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    from . import project_output_validation

    ownership_issues = project_output_validation.validate_prepared_output_ownership(
        project, prepared, depsgraph=_preflight_depsgraph()
    )
    errors, _warnings, primary_message = _report_validation_issues(operator, ownership_issues)
    if errors:
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        project.last_status_message = primary_message
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    scene_settings.status_message = constants.STATUS_BAKING
    project.last_status_message = constants.STATUS_BAKING
    map_rebuild.record_active_bake_map_types(project, selected_map_types)
    map_rebuild.record_active_bake_map_uuids(project, selected_map_uuids)
    map_rebuild.record_active_bake_group_names(project, selected_group_names)

    try:
        mat_errors = export.execute_material_bakes(prepared, context)
    except Exception as exc:  # noqa: BLE001 - surface, don't crash the operator
        operator.report({"ERROR"}, f"Material bake failed: {exc}")
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        return {"CANCELLED"}

    # execute_material_bakes adds at most one error per spec, so as many errors as
    # specs means nothing was written. Reporting that as complete left the artist
    # with a success message and no maps.
    if mat_errors and len(mat_errors) >= len(prepared.material_bake_specs):
        for message in mat_errors:
            operator.report({"WARNING"}, message)
        operator.report({"ERROR"}, f"Material bake failed: {mat_errors[0]}")
        project.last_warning_count = len(mat_errors)
        project.last_warning_summary = mat_errors[0]
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        runtime.release_workspace_geometry_transports(prepared.workspace_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        return {"CANCELLED"}

    # Preflight warnings raised while building the job (e.g. a view-dependent
    # channel that can only bake as a flat constant) reach the artist on the
    # backend route through the progress record. This route never builds one, so
    # they were dropped and the bake reported 0 warnings
    # (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P4).
    prepared_warnings = [
        str(message) for message in (getattr(prepared, "warnings", None) or []) if str(message)
    ]
    all_warnings = prepared_warnings + list(mat_errors)
    for message in all_warnings:
        operator.report({"WARNING"}, message)

    export.track_material_only_outputs(project, prepared)
    if getattr(prepared, "derived_outputs", None):
        derived_progress = protocol.BakeProgress(status=constants.STATUS_COMPLETE, percent=100.0)
        all_warnings.extend(derived_outputs.apply_workspace_derived_outputs(prepared.workspace_path, derived_progress))
        export.apply_progress_to_project(project, derived_progress, merge_existing=True)
    with dirty_tracker.suppress():
        runtime.refresh_project_output_images(project)
        _sync_preview_material_for_project(context.scene, project)

    runtime.release_workspace_geometry_transports(prepared.workspace_path)
    storage_cleanup.slim_job_workspace(prepared.workspace_path)

    baked = len(project.latest_outputs)
    # Recorded AFTER the output/preview refresh above, which rewrites the project's
    # status fields -- setting it earlier left last_warning_count at 0 while the
    # summary string was present.
    project.last_warning_count = len(all_warnings)
    project.last_warning_summary = all_warnings[0] if all_warnings else ""
    project.last_status_message = constants.STATUS_COMPLETE
    scene_settings.status_message = constants.STATUS_COMPLETE
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
    operator.report(
        {"INFO"},
        f"Material bake complete, {baked} map(s)"
        + (f", {len(all_warnings)} warning(s)" if all_warnings else ""),
    )
    return {"FINISHED"}


#: Longest a bake waits for a request still running in the GPU cage tool before it starts anyway.
_CAGE_TOOL_RELEASE_WAIT_SECONDS = 5.0


def _release_cage_tool_for_bake() -> bool:
    """Hand the GPU cage tool's resident scenes (VRAM and host commit) back before the backend
    starts. Never raises; True when nothing is held any more."""
    try:
        from . import cage_gpu

        return bool(cage_gpu.release_gpu_memory(_CAGE_TOOL_RELEASE_WAIT_SECONDS))
    except Exception:
        return False


def _park_high_poly_for_bake(context, project, prepared, selected_group_names, *, blocked: bool) -> None:
    """Free Blender's copy of the high-poly meshes for the length of the bake when the
    backend worker would not fit next to it (high_poly_park). The job's geometry is
    already exported; nothing reads the high-poly again until the bake finishes,
    unless Cycles material phases or a live bake run alongside it (never parked)."""
    if blocked or getattr(prepared, "material_bake_specs", None):
        return
    try:
        if runtime.debug_overlay_enabled(getattr(context.scene, "fyr_baker_settings", None)):
            return
    except Exception:
        pass
    selected = set(selected_group_names or [])
    objects = []
    largest_group = 0
    for group in getattr(project, "groups", []):
        if selected and group.name not in selected:
            continue
        if getattr(group, "use_low_as_high", False):
            return
        group_objects = []
        for slot in properties.effective_high_mesh_slots(group):
            obj = getattr(slot, "object_ref", None)
            if obj is not None and getattr(obj, "type", "") == "MESH":
                group_objects.append(obj)
                if obj not in objects:
                    objects.append(obj)
        largest_group = max(largest_group, high_poly_park.triangle_count(group_objects))
    if not objects:
        return
    park, reason = high_poly_park.should_park(
        objects,
        largest_group_triangles=largest_group,
        project_name=str(getattr(project, "name", "") or ""),
    )
    print(f"[Fyr Baker] high-poly park: decision={'park' if park else 'keep'} {reason}")
    park_dir = Path(prepared.workspace_path).parent.parent / "parked"
    if not park:
        # Kept in Blender: watch the commit for the length of the bake and park late if
        # it runs short (the estimate is a model, not a promise).
        high_poly_park.arm_commit_guard(objects, park_dir)
        return
    try:
        project.last_status_message = "Freeing memory for the bake..."
    except Exception:
        pass
    if high_poly_park.park(objects, park_dir):
        high_poly_park.arm_restore_timer()


def _is_user_group_subset(group_names, configured_group_names) -> bool:
    """True when ``group_names`` names fewer groups than the project holds."""
    if group_names is None:
        return False
    requested = {str(name or "") for name in group_names if str(name or "").strip()}
    configured = {str(name or "") for name in configured_group_names if str(name or "").strip()}
    return bool(requested) and requested < configured


def _run_bake(
    operator,
    context,
    project,
    *,
    map_types=None,
    map_uuids=None,
    group_names=None,
    start_message: str = "Bake started",
    initial_status: str = "",
    live_bake_mode: str = "preserve",
    allow_missing_uvs: bool = False,
    material_normal_source: dict | None = None,
    own_tiles_only: bool = False,
):
    global _DIRTY_REBAKE_SNAPSHOT, _LIVE_NORMAL_PREVIEW_JOB
    _clear_live_normal_preview_request()
    # Blender reports a mesh's corner data (UVs) as empty while it is in Edit Mode, and the
    # mesh misses the unsaved edits. Object Mode flushes them, so the bake sees what the
    # artist sees.
    if getattr(context, "mode", "OBJECT") == "EDIT_MESH":
        try:
            _set_object_interaction_mode(context, "OBJECT")
        except Exception as exc:  # noqa: BLE001 - say what to do instead of failing inside the capture
            operator.report({"ERROR"}, f"Leave Edit Mode, then bake again ({exc})")
            context.scene.fyr_baker_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}
    # A restore still running in slices from the last bake: this bake exports the highs.
    # (While a bake is active they stay parked; the active-bake check below rejects us.)
    high_poly_park.ensure_restored(only_when_idle=True)
    if not _DEFERRED_BAKE_RUNNING:
        _dismiss_setup_progress()
    # A speculative PREPARE may still be grinding in the worker (settings were
    # changed after it was issued); the RUN we are about to queue would wait it
    # out at "Warming up scene cache" for its full duration. Abort it now — it
    # cancels at the next phase boundary while we export, completed groups keep
    # their caches, and the RUN re-prepares only what is missing.
    try:
        runtime.cancel_inflight_prepare_for_bake()
    except Exception:
        pass
    runtime.notify_worker_bake_pending(_map_types_for_bake(project, map_types=map_types, map_uuids=map_uuids))
    _sync_live_bake_runtime(context.scene)
    scene_settings = context.scene.fyr_baker_settings
    live_bake_requested = (
        live_bake_mode == "enable"
        or (live_bake_mode == "preserve" and _live_bake_is_active(scene_settings, project))
    )
    if live_bake_requested and not runtime.background_polling_supported():
        operator.report({"ERROR"}, "Live Bake requires background job support")
        return {"CANCELLED"}
    active_snapshot = runtime.active_bake_snapshot()
    if (
        active_snapshot is not None
        and active_snapshot.running
        and _LIVE_NORMAL_PREVIEW_JOB is not None
        and str(getattr(active_snapshot, "job_id", "") or "") == str(_LIVE_NORMAL_PREVIEW_JOB.get("job_id", "") or "")
    ):
        runtime.cancel_active_bake()
        preview_finished = False
        for _attempt in range(8):
            result = runtime.poll_active_bake()
            if result is None or getattr(result, "finished", False):
                preview_finished = True
                break
            time.sleep(0.05)
        # Only forget the job when the cancel actually landed. Dropping the handle
        # after 400 ms of a still-running preview meant its completion no longer
        # matched any known job: the preview output was never applied and its
        # signature never updated, so the next tick re-baked the same preview --
        # while this bake was refused with "Another bake is already running".
        if preview_finished:
            _LIVE_NORMAL_PREVIEW_JOB = None
        active_snapshot = runtime.active_bake_snapshot()
    if active_snapshot is not None and active_snapshot.running:
        operator.report({"ERROR"}, "Another bake is already running")
        return {"CANCELLED"}
    # Blender's material queue routinely outlives the backend process. Starting a
    # second bake while it runs would fight the same Cycles job, temporary materials,
    # and output files.
    pending_materials = export.active_material_bake_status()
    if pending_materials is not None:
        operator.report({"ERROR"}, "Blender is still baking material detail from the previous run")
        return {"CANCELLED"}

    # A recovered autosave session resolves "//" output roots into the OS temp
    # folder: the bake would report success while writing where the artist
    # never looks (and where the scratch cleanup deletes files). Refuse with
    # the fix in hand instead of quietly diverging outputs from previews.
    temporary_output_error = export.refuse_temporary_output_bake(project)
    if temporary_output_error:
        operator.report({"ERROR"}, temporary_output_error)
        project.last_status_message = export.RECOVERED_AUTOSAVE_STATUS
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    _phase_mark("run_bake: preamble before validation")
    issues = validation.validate_bake_project(project, check_topology=False)
    _phase_mark("run_bake: validate_bake_project")
    if allow_missing_uvs:
        issues.issues = [issue for issue in issues.issues if issue.code not in _MISSING_UV_ERROR_CODES]

    errors, warnings, primary_message = _report_validation_issues(operator, issues)
    if errors:
        project.last_status_message = primary_message or "Fix validation errors before baking"
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}
    if warnings:
        project.last_status_message = primary_message or f"Baking with {len(warnings)} warning(s)"

    enabled_map_types = map_rebuild.enabled_map_types(project)
    enabled_map_uuids = map_rebuild.enabled_map_uuids(project)
    selected_map_uuids = _selected_map_uuids_for_bake(project, map_types=map_types, map_uuids=map_uuids)
    if map_types is not None:
        selected_map_types = list(map_types)
    elif map_uuids is not None:
        selected_map_types = [
            str(getattr(map_setting, "map_type", "") or "")
            for map_setting in (
                properties.find_map_setting_by_uuid(project, map_uuid)
                for map_uuid in selected_map_uuids
            )
            if map_setting is not None and str(getattr(map_setting, "map_type", "") or "").strip()
        ]
    else:
        selected_map_types = enabled_map_types
    configured_group_names = [
        str(getattr(group, "name", "") or "")
        for group in getattr(project, "groups", [])
        if str(getattr(group, "name", "") or "").strip()
    ]
    selected_group_names = list(group_names) if group_names is not None else configured_group_names
    # "Bake Anyway" past the Missing UVs dialog: export.py already drops individual
    # UV-less low meshes so they cannot stamp a fabricated unwrap over the rest of
    # their texture set. A group whose lows are ALL UV-less would then export with an
    # empty low list and raise "has no low meshes assigned", failing the whole bake --
    # so drop those groups here and say which ones went.
    if allow_missing_uvs:
        skipped_group_names = _groups_without_bakeable_low_meshes(project, selected_group_names)
        if skipped_group_names:
            selected_group_names = [
                name for name in selected_group_names if name not in skipped_group_names
            ]
            operator.report(
                {"WARNING"},
                "Skipped (no UVs): " + ", ".join(sorted(skipped_group_names)),
            )
    # Groups still being filled (validation "group.incomplete.skipped") stay out of the
    # run. Validation already warned about each one, and a bake with nothing else in
    # it errored before this point.
    incomplete_group_names = set(validation.incomplete_group_names(project))
    if incomplete_group_names:
        bakeable_group_names = [name for name in selected_group_names if name not in incomplete_group_names]
        if bakeable_group_names:
            selected_group_names = bakeable_group_names
    if not selected_map_types:
        operator.report({"ERROR"}, "Enable at least one output map before baking")
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}
    if not selected_map_uuids:
        operator.report({"ERROR"}, "Could not resolve any map entries to bake")
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}
    if not selected_group_names:
        operator.report({"ERROR"}, "Create at least one bake group before baking")
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    # A user subset bake (Bake Changed, a group bake) holds fewer groups than the project: the
    # texture-set tiles only the other groups touch keep their files, so the job plans only
    # the tiles its own groups occupy. Never for a staged phase: the F8 per-group passes run
    # with _MATERIAL_PHASE_TWO_ACTIVE and their first pass must write the fresh base.
    if not own_tiles_only and not _MATERIAL_PHASE_TWO_ACTIVE and _is_user_group_subset(group_names, configured_group_names):
        own_tiles_only = True

    # Substance-Painter-style dependency ordering. A MATERIAL row whose channel graph
    # samples a mesh map this same run writes has to bake AFTER that map exists: the
    # material texel payload is snapshotted inside prepare_bake_job, long before the
    # backend writes a pixel. Plan the split here, before any export work.
    #
    # When nothing depends on this run's own outputs the plan is empty and every line
    # below runs byte-for-byte as it did before this feature existed — same single job,
    # same dispatch, same timing.
    phase_plan = None
    source_only_map_uuids: list[str] = []
    if not _MATERIAL_PHASE_TWO_ACTIVE:
        try:
            phase_plan = bake_dependencies.plan_bake_phases(
                project, selected_map_uuids, selected_group_names
            )
        except Exception as exc:  # noqa: BLE001 - detection must never block a bake
            print(f"[Fyr Baker] Bake dependency scan skipped: {exc}")
            phase_plan = None
    if phase_plan is not None and phase_plan.errors:
        # v1 is two phases, full stop. A material that reads a MATERIAL output baked in
        # the same run would need a third phase, so refuse it by name instead of baking
        # something that silently reads last run's pixels.
        for message in phase_plan.errors:
            operator.report({"ERROR"}, message)
        project.last_status_message = phase_plan.errors[0]
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}
    if (
        phase_plan is not None
        and phase_plan.normal_first_map_uuid
        and phase_plan.mesh_phase_map_uuids
    ):
        # Material-detail normals: the Normal row bakes first, alone (an all-material
        # job, so a Bevel in its graph runs natively), the worker retains its texels and
        # the mesh maps follow as a staged phase reading them. Armed below with the
        # other staged phases, after validation.
        total = 3 if phase_plan.is_split else 2
        selected_map_uuids = [phase_plan.normal_first_map_uuid]
        selected_map_types = [constants.MAP_NORMAL]
        # A Normal row outside the selection bakes only as the source: its file stays
        # in the job workspace and the artist's Normal output is left alone.
        source_only_map_uuids = list(phase_plan.normal_first_source_only_uuids)
        initial_status = f"Stage 1/{total}: Normal map…"
        start_message = (
            f"Stage 1/{total}: baking {phase_plan.normal_first_label or 'the Normal map'} first; "
            "its material detail feeds Curvature, Object Normal, AO and Bent Normal"
        )
    elif phase_plan is not None and phase_plan.is_split and phase_plan.first_phase_map_uuids:
        selected_map_uuids = list(phase_plan.first_phase_map_uuids)
        selected_map_types = [
            str(getattr(map_setting, "map_type", "") or "")
            for map_setting in (
                properties.find_map_setting_by_uuid(project, map_uuid)
                for map_uuid in selected_map_uuids
            )
            if map_setting is not None and str(getattr(map_setting, "map_type", "") or "").strip()
        ]
        initial_status = _material_phase_status(1)
        start_message = (
            f"{_material_phase_status(1)} then {len(phase_plan.deferred_map_uuids)} "
            f"{phase_plan.deferred_reason_label()} material map(s)"
        )
    else:
        phase_plan = None

    _phase_mark("run_bake: planning")
    low_disk_warnings: list[str] = []
    try:
        output_root, _ = export.resolve_output_root(project)
        low_disk_warnings = storage_cleanup.low_disk_space_warnings(
            (
                ("output drive", output_root),
                ("cache drive", storage_cleanup.cache_root()),
            )
        )
    except Exception as exc:
        operator.report({"WARNING"}, f"Disk space check skipped: {exc}")
    # Low system RAM is the common cause of a mid-bake "bad allocation" (the
    # postprocess allocates several GB in one burst). Surface it up front so the
    # failure isn't a mystery, rather than letting the backend crash 10s in.
    low_memory_warnings: list[str] = []
    try:
        low_memory_warnings = storage_cleanup.low_memory_warnings()
    except Exception as exc:
        operator.report({"WARNING"}, f"Memory check skipped: {exc}")
    resource_warnings = list(low_disk_warnings) + list(low_memory_warnings)
    for warning in resource_warnings:
        operator.report({"WARNING"}, warning)
    if resource_warnings and not warnings:
        project.last_warning_count = len(resource_warnings)
        project.last_warning_summary = resource_warnings[0]
        project.last_status_message = resource_warnings[0]

    _selected_set = set(selected_map_types)
    _selected_uuid_set = {str(map_uuid or "").strip() for map_uuid in selected_map_uuids if str(map_uuid or "").strip()}
    preserve_existing_outputs = (
        _selected_uuid_set != {str(map_uuid or "").strip() for map_uuid in enabled_map_uuids if str(map_uuid or "").strip()}
        or set(selected_group_names) != set(configured_group_names)
        or any(
            (
                str(getattr(_item, "map_uuid", "") or "").strip() not in _selected_uuid_set
                if str(getattr(_item, "map_uuid", "") or "").strip()
                else str(getattr(_item, "map_type", "") or "") not in _selected_set
            )
            for _item in project.latest_outputs
            if str(getattr(_item, "map_type", "") or "").strip() or str(getattr(_item, "map_uuid", "") or "").strip()
        )
    )

    _phase_mark("run_bake: disk/memory checks")
    if _defer_bake_until_high_meshes_warm(
        operator,
        context,
        project,
        map_types=map_types,
        map_uuids=map_uuids,
        group_names=group_names,
        start_message=start_message,
        initial_status=initial_status,
        live_bake_mode=live_bake_mode,
        selected_group_names=selected_group_names,
        allow_missing_uvs=allow_missing_uvs,
        material_normal_source=material_normal_source,
        own_tiles_only=own_tiles_only,
    ):
        return {"FINISHED"}

    _phase_mark("run_bake: defer check")
    try:
        project.last_status_message = "Preparing bake..."
        scene_settings.status_message = constants.STATUS_BAKING
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
    except Exception:
        pass
    try:
        prepared = export.prepare_bake_job(
            context,
            project,
            map_types=selected_map_types,
            map_uuids=selected_map_uuids,
            group_names=selected_group_names,
            preserve_latest_outputs=preserve_existing_outputs,
            use_shared_memory=True,
            use_binary_job_transport=True,
            cancel_check=_capture_cancel_requested,
            material_normal_source=material_normal_source,
            source_only_map_uuids=source_only_map_uuids,
            native_normal_group_phases=True,
            own_tiles_only=own_tiles_only,
        )
        _phase_mark("run_bake: export.prepare_bake_job")
        # If every selected output is handled addon-side via Cycles, there is no
        # backend geometry phase. This includes MATERIAL-workflow self-bakes and
        # High-to-Low material maps whose channel graph was routed to Cycles by
        # the Material IR capability gate. Do not dispatch an empty backend job.
        deferred_multi_group = (
            []
            if _MATERIAL_PHASE_TWO_ACTIVE
            else [
                str(map_uuid or "").strip()
                for map_uuid in (getattr(prepared, "deferred_multi_group_material_uuids", None) or [])
                if str(map_uuid or "").strip()
            ]
        )
        material_only = (
            not prepared.effective_map_types
            and bool(getattr(prepared, "material_bake_specs", None))
        )
        if material_only:
            if own_tiles_only and _PER_GROUP_MERGE_STATE is None:
                _prepare_subset_merge(project, selected_group_names, selected_map_uuids)
            material_only_result = _run_material_only_bake(
                operator, context, project, scene_settings, prepared,
                selected_map_types, selected_map_uuids, selected_group_names,
            )
            if _PER_GROUP_MERGE_STATE is not None:
                # Cycles wrote this pass synchronously: no backend poll will composite it.
                _finish_per_group_merge(project, succeeded="FINISHED" in (material_only_result or set()))
                with dirty_tracker.suppress():
                    runtime.refresh_project_output_images(project)
            # A split whose stage 1 turned out to be entirely addon-side still owes the
            # user its staged phases; without this the deferred rows would be dropped
            # silently.
            if deferred_multi_group:
                _arm_per_group_material_phases(project, deferred_multi_group, selected_group_names)
            if phase_plan is not None:
                _arm_pending_material_phase(
                    project, phase_plan, selected_group_names, live_bake_mode=live_bake_mode
                )
            color_stream_stages = _arm_color_stream_stages(
                project, prepared, selected_group_names, live_bake_mode=live_bake_mode
            )
            # Unconditional: this may itself be a queued pass (a group whose high has no
            # compilable material), and no backend poll follows to start the next one.
            _consume_pending_material_phase(
                succeeded="FINISHED" in (material_only_result or set())
            )
            return material_only_result
        if (
            not prepared.effective_map_types
            and not prepared.material_bake_specs
            and not deferred_multi_group
            and getattr(prepared, "derived_outputs", None)
        ):
            # Only Wireframe rows: nothing for the backend, the addon draws them now.
            return _run_derived_only_bake(operator, context, project, scene_settings, prepared)
        if (
            deferred_multi_group
            and not prepared.effective_map_types
            and not prepared.material_bake_specs
        ):
            # The whole selection deferred to per-group native passes (a Material row
            # baked alone across a Combined set): there is no stage-1 job to dispatch.
            # Queue the passes and start the first one now.
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
            storage_cleanup.slim_job_workspace(prepared.workspace_path)
            _arm_per_group_material_phases(project, deferred_multi_group, selected_group_names)
            if phase_plan is not None:
                _arm_pending_material_phase(
                    project, phase_plan, selected_group_names, live_bake_mode=live_bake_mode
                )
            if not _consume_pending_material_phase(succeeded=True):
                project.last_status_message = constants.STATUS_FAILED
                scene_settings.status_message = constants.STATUS_FAILED
                return {"CANCELLED"}
            operator.report({"INFO"}, "Baking materials natively per bake group")
            return {"FINISHED"}
        _issues, errors, warnings = _validate_prepared_job(operator, prepared, project, scene_settings)
        if errors:
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
            storage_cleanup.slim_job_workspace(prepared.workspace_path)
            scene_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}
        # Persist job path now so future sessions can send PREPARE before the user
        # presses Bake (cross-session background pre-loading).
        try:
            project.last_bake_job_path = str(prepared.job_path)
        except Exception:
            pass
        # Bake-only workspace pointer. Set HERE and at the live-rebake launch, never
        # in the speculative background prepare, so the support bundle can always be
        # collected from a workspace a bake actually ran in.
        try:
            project.last_bake_workspace_path = str(prepared.workspace_path)
            project.last_bake_job_id = str(getattr(prepared.job, "job_id", "") or "")
        except Exception:
            pass
        try:
            project.last_bake_cache_state = runtime.classify_bake_cache_state(prepared.job_path)
        except Exception:
            project.last_bake_cache_state = ""
        if warnings:
            project.last_status_message = f"Baking with {len(warnings)} job warning(s)"
        else:
            if runtime.is_prepare_in_flight():
                project.last_status_message = initial_status or "Loading scene caches..."
            else:
                project.last_status_message = initial_status or constants.STATUS_BAKING
        scene_settings.status_message = constants.STATUS_BAKING
        map_rebuild.record_active_bake_map_types(project, selected_map_types)
        map_rebuild.record_active_bake_map_uuids(project, selected_map_uuids)
        map_rebuild.record_active_bake_group_names(project, selected_group_names)
        # Stage 1 is really going out now. Arm the staged phases here rather than at
        # plan time so a validation bail above can never leave a stale request behind;
        # every failure path from this point clears them explicitly.
        if deferred_multi_group:
            _arm_per_group_material_phases(project, deferred_multi_group, selected_group_names)
        native_normal_phases = _arm_native_normal_group_phases(project, prepared)
        if phase_plan is not None:
            _arm_pending_material_phase(
                project, phase_plan, selected_group_names, live_bake_mode=live_bake_mode
            )
            if native_normal_phases:
                # Each native pass leaves only its own group's texels, so the mesh maps read
                # the composite of all of them. Where it has none (a group without material
                # detail) they shade from the raw hit normal, like that group baked alone.
                _native_uuids = set(getattr(prepared, "deferred_native_normal_groups", None) or ())
                for _entry in _PENDING_MATERIAL_PHASES:
                    if _entry.get("kind") == "mesh_after_normal":
                        _source = _entry.get("material_normal_source")
                        _entry["material_normal_source"] = (
                            dict(_source, composite=True)
                            if _source and _source.get("map_uuid") in _native_uuids
                            else None
                        )
        color_stream_stages = _arm_color_stream_stages(
            project, prepared, selected_group_names, live_bake_mode=live_bake_mode
        )
        if own_tiles_only and _PER_GROUP_MERGE_STATE is None:
            _prepare_subset_merge(project, selected_group_names, selected_map_uuids)
        try:
            active_backend = bake_backends.resolve_active_render_backend(force_refresh=True)
        except RuntimeError as exc:
            _clear_pending_material_phase()
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
            storage_cleanup.slim_job_workspace(prepared.workspace_path)
            map_rebuild.clear_active_bake_map_types(project)
            operator.report({"ERROR"}, str(exc))
            project.last_status_message = constants.STATUS_FAILED
            scene_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}
        if active_backend.backend_id == "cycles":
            return _run_cycles_primary_bake(
                operator,
                context,
                project,
                scene_settings,
                prepared,
                start_message=start_message,
                reason=active_backend.reason,
            )
        _phase_mark("run_bake: validate prepared job + arm phases + backend resolve")
        # The GPU cage tool keeps the high scenes of the fits and the prewarm resident (~4 GB of
        # commit on the Uzi) until it has been idle for 30 s. The backend's host-build admission
        # and the park decision below count that against this bake, so let it go first.
        _release_cage_tool_for_bake()
        if runtime.background_polling_supported():
            partial_bake_snapshot = _active_partial_bake_snapshot(project)
            if partial_bake_snapshot is not None and _DIRTY_REBAKE_SNAPSHOT is None:
                _DIRTY_REBAKE_SNAPSHOT = partial_bake_snapshot
            _park_high_poly_for_bake(
                context, project, prepared, selected_group_names,
                blocked=bool(
                    live_bake_requested
                    or deferred_multi_group
                    or native_normal_phases
                    or phase_plan is not None
                    or color_stream_stages
                ),
            )
            _phase_mark("run_bake: park decision")
            low_disk_notice = high_poly_park.take_low_disk_notice()
            if low_disk_notice:
                operator.report({"INFO"}, low_disk_notice)
            runtime.launch_bake_job_background(
                prepared.job_path,
                prepared.progress_path,
                job_id=prepared.job.job_id,
                selected_map_types=prepared.effective_map_types,
            )
            _remember_cycles_handoff_prepared(prepared)
            _phase_mark("run_bake: launch_bake_job_background")
            # From here the backend OWNS this workspace. Anything below that raises must
            # not reach the outer handler: that one assumes nothing was dispatched and
            # releases the geometry transports and slims the job workspace out from
            # under the running bake.
            polling_started = False
            try:
                # Overlap CPU material evaluation with the backend's GPU projection
                # instead of serializing both phases.
                # Poll first: see _trigger_dirty_rebake for why the order matters.
                runtime.start_background_polling(_handle_background_bake_update)
                polling_started = True
                if prepared.material_bake_specs:
                    export.execute_material_bakes_async(
                        prepared,
                        context,
                        on_complete=lambda errors, path=prepared.workspace_path: _handle_async_material_complete(path, errors),
                        on_progress=_handle_async_material_progress,
                    )
                # Bake low-impact viewport mode: snapshot/engage here while the operator
                # still has full context (window/area). Restored exactly once on bake END
                # in the poll finished-branch (which has no operator context). See
                # _bake_low_impact_engage.
                try:
                    _bake_low_impact_engage(context)
                except Exception:
                    pass
                if live_bake_requested:
                    _activate_live_bake(context.scene, project)
                overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
            except Exception as exc:
                if not polling_started:
                    # No poll timer means nothing will ever consume the result: the job
                    # would run to completion while _ACTIVE_BAKE stays set and every
                    # later bake is refused with "Another bake is already running" for
                    # the rest of the session. Stop the job we just started instead.
                    try:
                        runtime.cancel_active_bake()
                        runtime.clear_active_bake_state(keep_requests=True)
                    except Exception:
                        pass
                    _clear_pending_material_phase()
                    _DIRTY_REBAKE_SNAPSHOT = None
                    map_rebuild.clear_active_bake_map_types(project)
                    operator.report({"ERROR"}, f"Could not start the bake: {exc}")
                    project.last_status_message = constants.STATUS_FAILED
                    scene_settings.status_message = constants.STATUS_FAILED
                    return {"CANCELLED"}
                # The bake is running and polled; the rest is presentation.
                print(f"[MasterBaker] bake started, but its follow-up steps failed: {exc!r}")
                operator.report({"WARNING"}, f"Bake started; {exc}")
            if runtime.first_bake_after_update_pending():
                # The panel shows it too; the status bar line is what is read at the click.
                operator.report({"INFO"}, f"{start_message}. {runtime.SHADER_COMPILE_NOTICE}")
            else:
                operator.report({"INFO"}, start_message)
            return {"FINISHED"}
        if prepared.material_bake_specs:
            mat_errors = export.execute_material_bakes(prepared, context)
            for mat_err in mat_errors:
                operator.report({"WARNING"}, mat_err)
        sync_bake_started_at = time.monotonic()
        progress = runtime.run_bake_job(
            prepared.job_path,
            prepared.progress_path,
            selected_map_types=prepared.effective_map_types,
        )
        if progress.errors:
            outcome = _try_cycles_projection_handoff(
                context,
                project,
                progress,
                prepared,
                map_types=prepared.effective_map_types,
                on_complete=_deferred_sync_handoff_completion(
                    project,
                    progress,
                    prepared,
                    scene_settings,
                    started_at=sync_bake_started_at,
                ),
            )
            if outcome is CyclesHandoffOutcome.PENDING:
                # The modal driver owns the rest of this bake: its completion runs the
                # same tail this function would have run here.
                return {"FINISHED"}
        if not progress.errors:
            detail_warnings = material_detail.apply_workspace_material_detail(prepared.workspace_path)
            progress.warnings.extend(detail_warnings)
            progress.warnings.extend(
                derived_outputs.apply_workspace_derived_outputs(prepared.workspace_path, progress)
            )
        if _PER_GROUP_MERGE_STATE is not None:
            # Same as the Cycles tail: this route never reaches the backend poll.
            _finish_per_group_merge(project, succeeded=True)
        export.apply_progress_to_project(project, progress, merge_existing=True)
        with dirty_tracker.suppress():
            runtime.refresh_project_output_images(project)
            _sync_preview_material_for_project(context.scene, project)
    except InterruptedError:
        if _PER_GROUP_MERGE_STATE is not None:
            _finish_per_group_merge(project, succeeded=False)
        _clear_pending_material_phase()
        _DIRTY_REBAKE_SNAPSHOT = None
        map_rebuild.clear_active_bake_map_types(project)
        project.last_status_message = constants.STATUS_CANCELLED
        scene_settings.status_message = constants.STATUS_CANCELLED
        operator.report({"INFO"}, constants.STATUS_CANCELLED)
        return {"CANCELLED"}
    except Exception as exc:
        if _PER_GROUP_MERGE_STATE is not None:
            try:
                _finish_per_group_merge(project, succeeded=False)
            except Exception:
                pass
        _clear_pending_material_phase()
        if "prepared" in locals():
            runtime.release_workspace_geometry_transports(prepared.workspace_path)
            storage_cleanup.slim_job_workspace(prepared.workspace_path)
        _DIRTY_REBAKE_SNAPSHOT = None
        map_rebuild.clear_active_bake_map_types(project)
        operator.report({"ERROR"}, str(exc))
        project.last_status_message = constants.STATUS_FAILED
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    if progress.errors:
        _clear_pending_material_phase()
        map_rebuild.clear_active_bake_map_types(project)
        _report_backend_failure(operator, project, progress, progress_path=prepared.progress_path)
        storage_cleanup.slim_job_workspace(prepared.workspace_path)
        scene_settings.status_message = constants.STATUS_FAILED
        return {"CANCELLED"}

    _finalize_successful_bake_state(project)
    dirty_tracker.set_post_bake_cooldown()
    map_rebuild.clear_active_bake_map_types(project)
    base_message = progress.message or constants.STATUS_COMPLETE
    duration_text = _format_bake_duration(time.monotonic() - sync_bake_started_at)
    final_message = f"{base_message} ({duration_text})" if duration_text else base_message
    project.last_status_message = final_message
    scene_settings.status_message = final_message
    overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
    info_message = final_message if progress.message else (
        f"Bake complete ({duration_text})" if duration_text else "Bake complete"
    )
    operator.report({"INFO"}, info_message)
    storage_cleanup.slim_job_workspace(prepared.workspace_path)
    # Synchronous path (no background polling): stage 1 is on disk right now, so hand
    # stage 2 to a timer for the same settled-context reasons the async path does.
    _consume_pending_material_phase(succeeded=True)
    return {"FINISHED"}


class MASTER_BAKER_OT_add_project(bpy.types.Operator):
    bl_idname = "master_baker.add_project"
    bl_label = "Add Bake Project"
    bl_description = "Create a bake project in this blend file"
    # No UNDO: a global (memfile) undo step reallocates the whole fyr_baker_settings
    # IDProperty, dangling any retained custom-panel text button bound to per-project
    # data and crashing the next redraw (Blender T74067). Structural project churn is
    # not undo-managed for the same reason on remove/duplicate below.
    bl_options = {"REGISTER"}

    def execute(self, context):
        _create_default_project(context)
        # The artist has moved past the removal, so the stashed payload is no longer an
        # "undo". Leaving it armed offered "Undo Remove 'X'" next to a live project X and
        # then ADDED a second same-named project instead of undoing anything
        # (RC sweep 2026-08-29, finding 2).
        runtime.clear_removed_project_stash()
        return {"FINISHED"}


# Review-dialog channel rows: (material_channel constant, operator bool-prop name, label).
# The material-space Normal row uses the sentinel "NORMAL" channel (map_type MAP_NORMAL).
_MATERIAL_DIALOG_CHANNELS = (
    (constants.MATERIAL_CHANNEL_ALBEDO, "bake_albedo", "Base Color"),
    (constants.MATERIAL_CHANNEL_ROUGHNESS, "bake_roughness", "Roughness"),
    (constants.MATERIAL_CHANNEL_METALNESS, "bake_metalness", "Metalness"),
    (constants.MATERIAL_CHANNEL_EMISSION, "bake_emission", "Emission"),
    (constants.MATERIAL_CHANNEL_OPACITY, "bake_opacity", "Opacity"),
    (constants.MATERIAL_CHANNEL_SPECULAR, "bake_specular", "Specular"),
    (constants.MATERIAL_CHANNEL_TRANSMISSION, "bake_transmission", "Transmission"),
    ("NORMAL", "bake_normal", "Normal"),
)


class MASTER_BAKER_OT_bake_selected_materials(bpy.types.Operator):
    """Analyze the selected objects' materials and create an editable Material Project.

    This is the "Bake Selected Materials" onboarding route (docs/MATERIAL_BAKING_WORKFLOW_PLAN.md).
    It opens a compact review dialog reporting detected PBR channels and any missing UVs,
    lets the user toggle channels, and on confirm creates a same-object material-flatten
    project. It does NOT begin baking -- the user reviews and presses the normal Bake button.
    """
    bl_idname = "master_baker.bake_selected_materials"
    bl_label = "Bake Selected Materials"
    bl_description = (
        "Create a new material bake project from the selected mesh objects. "
        "Each object gets one texture set combining its assigned materials; existing projects are kept"
    )
    # No UNDO for the same memfile-realloc reason as add_project (structural project churn).
    bl_options = {"REGISTER"}

    bake_albedo: bpy.props.BoolProperty(name="Base Color", default=True)
    bake_roughness: bpy.props.BoolProperty(name="Roughness", default=False)
    bake_metalness: bpy.props.BoolProperty(name="Metalness", default=False)
    bake_emission: bpy.props.BoolProperty(name="Emission", default=False)
    bake_opacity: bpy.props.BoolProperty(name="Opacity", default=False)
    bake_specular: bpy.props.BoolProperty(name="Specular", default=False)
    bake_transmission: bpy.props.BoolProperty(name="Transmission", default=False)
    bake_normal: bpy.props.BoolProperty(name="Normal", default=False)
    generate_missing_uvs: bpy.props.BoolProperty(
        name="Generate Smart UVs for missing objects",
        description="Create a new FyrMaterialBake UV layer via Smart UV Project only on objects that lack usable UVs",
        default=True,
    )

    # Analysis snapshot carried invoke -> draw -> execute.
    snap_selected_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    snap_material_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    snap_set_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    snap_available_channels: bpy.props.StringProperty(default="", options={"HIDDEN"})
    snap_approximate_channels: bpy.props.StringProperty(default="", options={"HIDDEN"})
    snap_missing_uv_names: bpy.props.StringProperty(default="", options={"HIDDEN"})
    snap_unsupported_note: bpy.props.StringProperty(default="", options={"HIDDEN"})

    def _apply_analysis(self, analysis):
        available = {p.channel for p in analysis.channels}
        approximate = {p.channel for p in analysis.channels if getattr(p, "approximate", False)}
        proposed = {p.channel for p in analysis.channels if p.proposed}
        self.snap_available_channels = ",".join(sorted(available))
        self.snap_approximate_channels = ",".join(sorted(approximate))
        for channel, prop_name, _label in _MATERIAL_DIALOG_CHANNELS:
            setattr(self, prop_name, channel in proposed)
        self.snap_selected_count = len(analysis.objects)
        self.snap_material_count = sum(int(getattr(o, "material_count", 0)) for o in analysis.objects)
        self.snap_set_count = int(getattr(analysis, "expected_texture_sets", 0))
        self.snap_missing_uv_names = ",".join(analysis.objects_without_uvs)
        notes: list[str] = []
        for o in analysis.objects:
            for note in getattr(o, "unsupported", []) or []:
                if note not in notes:
                    notes.append(note)
        self.snap_unsupported_note = " | ".join(notes[:3])
        self.generate_missing_uvs = bool(analysis.objects_without_uvs)

    def invoke(self, context, event):
        analysis = material_workflow.analyze_selection(context)
        if analysis.blocking_error:
            self.report({"ERROR"}, analysis.blocking_error)
            return {"CANCELLED"}
        if not analysis.objects:
            self.report({"ERROR"}, "Select one or more visible mesh objects with materials")
            return {"CANCELLED"}
        self._apply_analysis(analysis)
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        available = set(filter(None, self.snap_available_channels.split(",")))
        approximate = set(filter(None, self.snap_approximate_channels.split(",")))

        info = layout.column(align=True)
        info.label(text=f"{self.snap_selected_count} object(s), {self.snap_material_count} material(s)")
        info.label(text=f"New project: {self.snap_set_count} texture set(s), one per object")

        box = layout.box()
        box.label(text="Channels")
        col = box.column(align=True)
        for channel, prop_name, label in _MATERIAL_DIALOG_CHANNELS:
            row = col.row(align=True)
            is_available = channel in available
            row.enabled = is_available
            suffix = "  (approx.)" if channel in approximate else ("" if is_available else "  (not detected)")
            row.prop(self, prop_name, text=f"{label}{suffix}")

        if self.snap_unsupported_note:
            note_box = layout.box()
            note_box.label(text="Approximate / unsupported:", icon="ERROR")
            for line in self.snap_unsupported_note.split(" | "):
                note_box.label(text=line)

        if self.snap_missing_uv_names:
            uv_box = layout.box()
            missing = [n for n in self.snap_missing_uv_names.split(",") if n]
            uv_box.label(text=f"{len(missing)} object(s) have no usable UVs", icon="ERROR")
            uv_box.prop(self, "generate_missing_uvs")

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        # Re-fetch targets so a selection change between invoke and confirm is honored.
        objects = material_workflow.selected_material_target_objects(context)
        if not objects:
            self.report({"ERROR"}, "Select one or more visible mesh objects with materials")
            return {"CANCELLED"}

        available = set(filter(None, self.snap_available_channels.split(",")))
        chosen_channels: list[str] = []
        include_normal = False
        for channel, prop_name, _label in _MATERIAL_DIALOG_CHANNELS:
            if channel not in available or not getattr(self, prop_name):
                continue
            if channel == "NORMAL":
                include_normal = True
            else:
                chosen_channels.append(channel)

        if not chosen_channels and not include_normal:
            self.report({"ERROR"}, "Enable at least one material channel")
            return {"CANCELLED"}

        if self.generate_missing_uvs:
            missing = [o for o in objects if not material_workflow.object_has_usable_uvs(o)]
            if missing:
                ok, message = material_workflow.generate_smart_uvs(missing)
                if not ok:
                    self.report({"ERROR"}, f"Smart UV generation failed: {message}")
                    return {"CANCELLED"}

        project = project_structure.create_material_project(
            context, objects, chosen_channels, include_normal=include_normal
        )
        channel_total = len(chosen_channels) + (1 if include_normal else 0)
        self.report(
            {"INFO"},
            f"Created Material Project '{project.name}' - {len(project.groups)} object(s), {channel_total} channel(s)",
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_rescan_materials(bpy.types.Operator):
    """Re-run material channel detection on a Material Project and propose newly meaningful
    channels. Never disables selected rows, resets row settings, changes UUIDs, or deletes
    output history (docs/MATERIAL_BAKING_WORKFLOW_PLAN.md sec 4)."""
    bl_idname = "master_baker.rescan_materials"
    bl_label = "Rescan Materials"
    bl_description = "Detect newly meaningful material channels for this project without changing existing rows"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        project = properties.get_active_project(context.scene)
        return project is not None and getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        # Gather the project's target objects, temporarily selecting them so the shared
        # analyzer (which reads the active selection) sees the right set.
        target_objects: list = []
        for group in project.groups:
            for obj in project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW):
                if obj is not None and obj not in target_objects:
                    target_objects.append(obj)
        if not target_objects:
            self.report({"WARNING"}, "This project has no target objects to rescan")
            return {"CANCELLED"}

        analysis = material_workflow.analyze_objects(target_objects)

        existing_channels = set()
        has_normal_row = False
        for item in project.maps:
            if getattr(item, "is_add_phantom", False):
                continue
            map_type = str(getattr(item, "map_type", "") or "").strip().upper()
            if map_type == constants.MAP_MATERIAL:
                existing_channels.add(str(getattr(item, "material_channel", "") or "").strip().upper())
            elif map_type == constants.MAP_NORMAL:
                has_normal_row = True

        added = 0
        for proposal in analysis.channels:
            if not proposal.proposed:
                continue
            if proposal.channel == "NORMAL":
                if has_normal_row:
                    continue
                item = properties.add_map_setting(project, constants.MAP_NORMAL)
                item.enabled = True
                item.execution_route = constants.EXECUTION_ROUTE_AUTO
                item.output_suffix = ""
                has_normal_row = True
                added += 1
            else:
                if proposal.channel in existing_channels:
                    continue
                item = properties.add_map_setting(project, constants.MAP_MATERIAL)
                item.material_channel = proposal.channel
                item.enabled = True
                item.execution_route = constants.EXECUTION_ROUTE_AUTO
                # Clean per-channel filename suffix (matches create_material_project) so the
                # new row does not collide on the generic "Material" output name.
                effective_type = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(proposal.channel, constants.MAP_MATERIAL_ALBEDO)
                item.output_suffix = naming.resolved_map_file_label(effective_type)
                existing_channels.add(proposal.channel)
                added += 1

        message = f"Rescan added {added} channel(s)" if added else "Rescan found no new channels"
        project.last_status_message = message
        context.scene.fyr_baker_settings.status_message = message
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_set_output_size_preset(bpy.types.Operator):
    bl_idname = "master_baker.set_output_size_preset"
    bl_label = "Set Output Size"
    bl_options = {"REGISTER", "UNDO"}

    preset: bpy.props.EnumProperty(name="Size", items=constants.OUTPUT_SIZE_ITEMS, default=constants.OUTPUT_SIZE_2048)

    @classmethod
    def description(cls, _context, properties):
        preset = getattr(properties, "preset", constants.OUTPUT_SIZE_2048)
        if preset == constants.OUTPUT_SIZE_CUSTOM:
            return "Switch the output size preset to Custom without changing X and Y"
        label = next((item[1] for item in constants.OUTPUT_SIZE_ITEMS if item[0] == preset), preset)
        return f"Set the project output size to {label}"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        project.resolution_preset = self.preset
        context.scene.fyr_baker_settings.status_message = "Output size updated"
        return {"FINISHED"}


def _bake_groups_for_setting_edit(context, project, fallback_group):
    """Bake groups that receive a setting change from the group popover.

    Shift-click in the bake-group menu stores more than one name. An empty
    selection means the active group alone.
    """
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    names = set(properties.bake_group_target_names(project, settings))
    groups = [
        group
        for group in getattr(project, "groups", []) or []
        if str(getattr(group, "name", "") or "").strip() in names
    ]
    if groups:
        return groups
    return [fallback_group] if fallback_group is not None else []


class MASTER_BAKER_OT_clear_group_uv_override(bpy.types.Operator):
    bl_idname = "master_baker.clear_group_uv_override"
    bl_label = "Clear UV Override"
    bl_description = "Use each low-poly mesh's active UV layer for the selected bake groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        for target in _bake_groups_for_setting_edit(context, project, group):
            target.uv_layer_name = ""
        context.scene.fyr_baker_settings.status_message = "Using active UV layer"
        return {"FINISHED"}


class MASTER_BAKER_OT_set_group_uv_override(bpy.types.Operator):
    bl_idname = "master_baker.set_group_uv_override"
    bl_label = "Set UV Override"
    bl_description = "Use this UV layer for the selected bake groups"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: bpy.props.StringProperty(name="UV Layer", default="", options={"HIDDEN"})

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        layer_name = str(self.layer_name or "").strip()
        for target in _bake_groups_for_setting_edit(context, project, group):
            target.uv_layer_name = layer_name
        status = f"Baking with UV layer '{layer_name}'" if layer_name else "Using active UV layer"
        context.scene.fyr_baker_settings.status_message = status
        return {"FINISHED"}


class MASTER_BAKER_OT_assign_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.assign_texture_set"
    bl_label = "Assign Texture Set"
    bl_description = "Assign this bake group to a texture set so it shares output files with other bake groups in the same set"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})
    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})
    apply_to_targets: bpy.props.BoolProperty(
        name="Apply To Selected Groups",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if self.apply_to_targets:
            settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
            names = set(properties.bake_group_target_names(project, settings))
            matched = False
            for group in getattr(project, "groups", []) or []:
                if str(getattr(group, "name", "") or "").strip() in names:
                    group.texture_set_name = self.name
                    matched = True
            if not matched:
                self.report({"ERROR"}, "No bake group selected")
                return {"CANCELLED"}
            return {"FINISHED"}
        target_name = self.group_name.strip()
        if target_name:
            group = next((g for g in project.groups if g.name == target_name), None)
            if group is None:
                self.report({"ERROR"}, f"Bake group '{target_name}' not found")
                return {"CANCELLED"}
        else:
            group = _active_group_or_report(self, project)
            if group is None:
                return {"CANCELLED"}
        group.texture_set_name = self.name
        return {"FINISHED"}


class MASTER_BAKER_OT_set_active_group(bpy.types.Operator):
    bl_idname = "master_baker.set_active_group"
    bl_label = "Set Active Bake Group"
    bl_description = "Set this bake group as the active bake group"
    bl_options = {"INTERNAL"}

    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        target_name = self.group_name.strip()
        if not target_name:
            return {"CANCELLED"}
        for i, g in enumerate(project.groups):
            if g.name == target_name:
                project.active_group_index = i
                project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
                set_name = (getattr(g, "texture_set_name", "") or "").strip()
                if set_name:
                    for index, texture_set in enumerate(getattr(project, "texture_sets", []) or []):
                        if str(getattr(texture_set, "name", "") or "") == set_name:
                            project.active_texture_set_index = index
                            break
                settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
                properties.set_bake_group_targets(settings, [])
                return {"FINISHED"}
        return {"CANCELLED"}


class MASTER_BAKER_OT_set_active_group_by_index(bpy.types.Operator):
    bl_idname = "master_baker.set_active_group_by_index"
    bl_label = "Set Active Bake Group by Index"
    bl_description = "Make this the active bake group. Shift-click to include another group; setting changes apply to every included group"
    bl_options = {"INTERNAL"}

    group_index: bpy.props.IntProperty(name="Bake Group Index", default=0, options={"HIDDEN"})
    extend: bpy.props.BoolProperty(name="Extend", default=False, options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        self.extend = bool(getattr(event, "shift", False))
        return self.execute(context)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if not (0 <= self.group_index < len(project.groups)):
            return {"CANCELLED"}
        clicked = project.groups[self.group_index]
        clicked_name = str(getattr(clicked, "name", "") or "").strip()
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        active = properties.peek_active_group(project)
        active_name = str(getattr(active, "name", "") or "").strip() if active is not None else ""
        current = properties.bake_group_target_names(project, settings) if self.extend else []
        chosen = properties.resolve_bake_group_target_click(
            current,
            active_name,
            clicked_name,
            extend=bool(self.extend),
        )
        properties.set_bake_group_targets(settings, chosen if len(chosen) > 1 else [])
        active_after = clicked_name if clicked_name in chosen else (chosen[0] if chosen else clicked_name)
        for index, group in enumerate(project.groups):
            if str(getattr(group, "name", "") or "").strip() == active_after:
                project.active_group_index = index
                break
        else:
            project.active_group_index = self.group_index
        project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
        _clear_revealed_item_settings(context)
        return {"FINISHED"}


class MASTER_BAKER_OT_select_all_groups(bpy.types.Operator):
    bl_idname = "master_baker.select_all_groups"
    bl_label = "Select All Bake Groups"
    bl_description = "Select every mesh assigned to the bake project"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        all_objects = set()
        for group in project.groups:
            role_state = properties.group_role_assignments_state(group)
            for slot in getattr(role_state, "low_meshes", []):
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    all_objects.add(obj)
            for slot in getattr(role_state, "high_meshes", []):
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    all_objects.add(obj)
            cage = getattr(group, "custom_cage", None)
            if cage is not None:
                all_objects.add(cage)

        if not all_objects:
            self.report({"INFO"}, "No objects to select in bake groups")
            return {"CANCELLED"}

        for obj in all_objects:
            obj.select_set(True)
            context.view_layer.objects.active = obj

        self.report({"INFO"}, f"Selected {len(all_objects)} objects")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_all_cage_overlays(bpy.types.Operator):
    bl_idname = "master_baker.toggle_all_cage_overlays"
    bl_label = "Toggle Cage"
    bl_description = "Show or hide the cage for this bake project. Skew needles stay on their own toggle"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def description(cls, context, _properties):
        project = properties.get_active_project(getattr(context, "scene", None))
        groups = list(getattr(project, "groups", []) or []) if project is not None else []
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        global_on = bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state else False
        showing = bool(groups) and global_on and not any(bool(getattr(group, "cage_overlay_hidden", False)) for group in groups)
        if showing:
            return "Hide the cage for this bake project. Skew needles stay on their own toggle"
        return "Show the cage for this bake project"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        groups = list(getattr(project, "groups", []))
        if not groups:
            self.report({"INFO"}, "No bake groups to toggle")
            return {"CANCELLED"}

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        global_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state else False
        all_visible = global_cage_visible and not any(bool(getattr(g, "cage_overlay_hidden", False)) for g in groups)

        if all_visible:
            # This project only. The scene-wide cage switch stays as it is, so
            # another bake project's cage is left alone. Skew, offset, and
            # coverage have their own toggles.
            for g in groups:
                g.cage_overlay_hidden = True
            action = "hidden"
        else:
            # Showing needs the scene cage switch on, or these groups never draw.
            # Turn that on before clearing the per-group hide flags.
            if overlay_state is not None:
                overlay_state.show_cage_overlay = True
            for g in groups:
                g.cage_overlay_hidden = False
            action = "shown"

        self.report({"INFO"}, f"Cage {action} for this bake project")
        # Visibility-only change: hidden groups are filtered at draw assembly, so
        # keep the static cage batches intact and just redraw.
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_group_cage_overlay(bpy.types.Operator):
    bl_idname = "master_baker.toggle_group_cage_overlay"
    bl_label = "Toggle Bake Group Cage Overlay"
    bl_description = "Show or hide the cage overlay for this bake group"
    bl_options = {"REGISTER", "UNDO"}

    group_index: bpy.props.IntProperty(name="Bake Group Index", default=0)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        group_index = self.group_index
        if group_index < 0 or group_index >= len(project.groups):
            return {"CANCELLED"}

        group = project.groups[group_index]
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        master_visible = bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state else False
        currently_hidden = bool(getattr(group, "cage_overlay_hidden", False))
        # Decide from what is actually on screen, not just the per-group flag: the
        # cage is only visible when the global overlay is on AND this group is not
        # hidden. This keeps the click direction aligned with the button's icon,
        # which uses the same effective-visibility test — so clicking an
        # off-looking toggle always turns the cage on.
        effective_visible = master_visible and not currently_hidden

        if effective_visible:
            group.cage_overlay_hidden = True
        else:
            # Showing this group: enable the global overlay FIRST so that the
            # update callback on cage_overlay_hidden sees show_cage_overlay=True
            # and correctly syncs the cage preview visibility.
            if overlay_state:
                overlay_state.show_cage_overlay = True
            group.cage_overlay_hidden = False

        # Visibility-only change: hidden groups are filtered at draw assembly, so
        # keep the static cage batches intact and just redraw.
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_group_cage_coverage(bpy.types.Operator):
    bl_idname = "master_baker.toggle_group_cage_coverage"
    bl_label = "Toggle Bake Group Cage Coverage"
    bl_description = (
        "Show or hide cage coverage for this bake group. Blue areas are covered; red areas "
        "are outside the cage and may produce missed rays. The overlay remains visible when "
        "you select another bake group"
    )
    bl_options = {"REGISTER", "UNDO"}

    group_index: bpy.props.IntProperty(name="Bake Group Index", default=0)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        group_index = self.group_index
        if group_index < 0 or group_index >= len(project.groups):
            return {"CANCELLED"}

        # Per-group flag: does NOT change the active group, so coverage stays on whatever
        # groups the user enabled it for. The flag's update callback engages the coverage
        # gate + cage overlay when turning on.
        group = project.groups[group_index]
        group.show_cage_coverage = not bool(getattr(group, "show_cage_coverage", False))

        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_all_cage_coverage(bpy.types.Operator):
    bl_idname = "master_baker.toggle_all_cage_coverage"
    bl_label = "Toggle Cage Coverage"
    bl_description = (
        "Show or hide cage coverage for this bake project. Blue areas are covered; "
        "red areas are outside the cage and may produce missed rays"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        groups = list(getattr(project, "groups", []))
        any_on = any(bool(getattr(group, "show_cage_coverage", False)) for group in groups)
        for group in groups:
            group.show_cage_coverage = not any_on
        if any_on and overlay_state is not None:
            still_on = any(
                bool(getattr(other_group, "show_cage_coverage", False))
                for other in list(getattr(settings, "projects", []) or [])
                for other_group in list(getattr(other, "groups", []) or [])
            )
            if not still_on:
                overlay_state.show_error_heatmap = False
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_project_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_project_visibility"
    bl_label = "Toggle Project Visibility"
    bl_description = "Show or hide the entire bake project: meshes, cage, and coverage"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        groups = list(getattr(project, "groups", []))
        objects = []
        for group in groups:
            role_state = properties.group_role_assignments_state(group)
            for slot in list(getattr(role_state, "low_meshes", [])) + list(getattr(role_state, "high_meshes", [])):
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    objects.append(obj)

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None

        any_mesh_visible = any(not _object_hidden_with_fallback(o) for o in objects)
        cage_on = bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state else False
        coverage_on = bool(getattr(overlay_state, "show_error_heatmap", False)) if overlay_state else False
        currently_visible = any_mesh_visible or cage_on or coverage_on

        if currently_visible:
            # Hide everything: meshes, cage overlay, and coverage heatmap.
            for obj in objects:
                _set_object_hidden_with_fallback(obj, True)
            if overlay_state:
                overlay_state.show_cage_overlay = False
                overlay_state.show_error_heatmap = False
        else:
            # Show meshes and the cage overlay. Coverage stays off; it is a
            # diagnostic the user re-enables per group as needed.
            for obj in objects:
                _set_object_hidden_with_fallback(obj, False)
            if overlay_state:
                overlay_state.show_cage_overlay = True

        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_cage_menu_expansion(bpy.types.Operator):
    bl_idname = "master_baker.toggle_cage_menu_expansion"
    bl_label = "Toggle Cage Menu Expansion"
    bl_description = "Show or hide this bake group's meshes in the tree"
    # View state only: an undo step per arrow click would make Ctrl+Z replay
    # tree folding instead of the artist's last real edit.
    bl_options = {"INTERNAL"}

    group_index: bpy.props.IntProperty(name="Bake Group Index", default=0)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        group_index = self.group_index
        if group_index < 0 or group_index >= len(project.groups):
            return {"CANCELLED"}

        group = project.groups[group_index]
        group.cage_menu_expanded = not group.cage_menu_expanded
        return {"FINISHED"}


class MASTER_BAKER_OT_rename_group_meshes(bpy.types.Operator):
    bl_idname = "master_baker.rename_group_meshes"
    bl_label = "Rename Meshes from Group"
    bl_description = (
        "Rename this group's low/high objects using its name: boots_low, "
        "boots_high_01, boots_high_02. Multiple lows are numbered too. "
        "Includes meshes in its Low/High collections; keeps mesh data and cage names"
    )
    bl_options = {"REGISTER", "UNDO"}

    group_index: bpy.props.IntProperty(default=-1, options={"HIDDEN"})

    def execute(self, context):
        from .group_mesh_naming import rename_group_meshes

        project = properties.get_active_project(context.scene)
        index = self.group_index if self.group_index >= 0 else getattr(project, "active_group_index", -1)
        if project is None or not 0 <= index < len(project.groups):
            self.report({"WARNING"}, "Select a bake group first")
            return {"CANCELLED"}
        try:
            count = rename_group_meshes(project.groups[index], bpy.data.objects)
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        overlays.tag_redraw_all_view3d()
        self.report({"INFO"}, f"Renamed {count} mesh(es)" if count else "Mesh names already match the group")
        return {"FINISHED"}


class MASTER_BAKER_OT_select_cage_object(bpy.types.Operator):
    bl_idname = "master_baker.select_cage_object"
    bl_label = "Select Cage Object"
    bl_description = (
        "Select this mesh and make it the active object.\n"
        "Shift/Ctrl-click to add or remove it from the current selection"
    )
    bl_options = {"REGISTER", "UNDO"}

    object_name: bpy.props.StringProperty(name="Object Name", default="", options={"HIDDEN"})
    extend: bpy.props.BoolProperty(name="Extend", default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        # A plain click selects only this mesh; Shift/Ctrl-click toggles it in the
        # current selection (multi-select, like the Outliner). UI button operators
        # receive the triggering click event here, so the modifier state is readable.
        self.extend = bool(getattr(event, "shift", False) or getattr(event, "ctrl", False))
        return self.execute(context)

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None:
            self.report({"WARNING"}, f"Object '{self.object_name}' not found")
            return {"CANCELLED"}
        view_layer_objects = getattr(getattr(context, "view_layer", None), "objects", None)
        if not self.extend:
            if not _select_objects_in_view_layer(context, [obj], active_object=obj):
                self.report({"WARNING"}, f"Object '{self.object_name}' is not in the active view layer")
                return {"CANCELLED"}
            return {"FINISHED"}
        # Extend/toggle: flip this object's selection while keeping the rest selected.
        try:
            was_selected = bool(obj.select_get())
            obj.select_set(not was_selected)
        except Exception:
            self.report({"WARNING"}, f"Object '{self.object_name}' is not in the active view layer")
            return {"CANCELLED"}
        if view_layer_objects is not None:
            if not was_selected:
                view_layer_objects.active = obj
            elif getattr(view_layer_objects, "active", None) == obj:
                # Deselected the active object: hand active to another selected one.
                remaining = [o for o in getattr(context, "selected_objects", []) if o is not obj]
                view_layer_objects.active = remaining[0] if remaining else None
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_cage_object_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_cage_object_visibility"
    bl_label = "Toggle Object Visibility"
    bl_description = "Show or hide this mesh in the viewport"
    bl_options = {"REGISTER", "UNDO"}

    object_name: bpy.props.StringProperty(name="Object Name", default="", options={"HIDDEN"})

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None:
            self.report({"WARNING"}, f"Object '{self.object_name}' not found")
            return {"CANCELLED"}
        # hide_get/hide_set drive the outliner eye (per-view-layer visibility),
        # which is what the user expects this toggle to mirror.
        try:
            obj.hide_set(not bool(obj.hide_get()))
        except Exception:
            obj.hide_viewport = not bool(obj.hide_viewport)
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_cage_overlay(bpy.types.Operator):
    bl_idname = "master_baker.toggle_cage_overlay"
    bl_label = "Toggle Cage"
    bl_description = "Show or hide the cage and its coverage in the viewport"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def description(cls, context, _properties):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        if overlay_state and bool(getattr(overlay_state, "show_cage_overlay", False)):
            return "Hide the cage and its coverage. Skew needles stay on their own toggle"
        return "Show the cage and its coverage in the viewport, hiding the high-poly meshes while it is on"

    def execute(self, context):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is None:
            return {"CANCELLED"}
        overlay_state = properties.overlay_settings_state(settings)
        if overlay_state is None:
            return {"CANCELLED"}
        current_value = bool(getattr(overlay_state, "show_cage_overlay", False))
        overlay_state.show_cage_overlay = not current_value
        return {"FINISHED"}


def _suggest_combined_texture_set_name(project) -> str:
    existing_names: list[str] = []
    seen_names: set[str] = set()
    for group in getattr(project, "groups", []):
        current_name = (getattr(group, "texture_set_name", "") or "").strip()
        if not current_name:
            continue
        folded_name = current_name.casefold()
        if folded_name in seen_names:
            continue
        seen_names.add(folded_name)
        existing_names.append(current_name)
    if len(existing_names) == 1:
        return existing_names[0]
    project_name = str(getattr(project, "name", "") or "").strip()
    return project_name or "TextureSet"


class MASTER_BAKER_OT_combine_groups_into_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.combine_groups_into_texture_set"
    bl_label = "Combine All Bake Groups"
    bl_description = "Assign every bake group to one shared texture set so the project writes a single set of output files"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        groups = list(getattr(project, "groups", []))
        if len(groups) < 2:
            self.report({"ERROR"}, "Create at least two bake groups before combining them")
            return {"CANCELLED"}
        shared_name = (getattr(self, "name", "") or "").strip() or _suggest_combined_texture_set_name(project)
        if not shared_name:
            self.report({"ERROR"}, "Texture set name cannot be empty")
            return {"CANCELLED"}
        for group in groups:
            group.texture_set_name = shared_name
        properties.ensure_texture_set(project, shared_name)
        status_message = f"Combined {len(groups)} bake groups into texture set {shared_name}"
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = status_message
        project.last_status_message = status_message
        # Texture-set membership drives the Active Texture Set cage preview scope, so
        # rebuild the static overlay cache to redraw cages across the new set.
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        self.report({"INFO"}, status_message)
        return {"FINISHED"}


def _prune_export_rows_for_texture_set(project, set_name: str) -> None:
    """Remove the export dialog's override and exclusion rows keyed by ``set_name``."""
    export_settings = getattr(project, "export_settings", None)
    if export_settings is None:
        return
    target = str(set_name or "").strip().casefold()
    if not target:
        return
    for collection_name in ("set_overrides", "excluded_texture_sets"):
        collection = getattr(export_settings, collection_name, None)
        if collection is None or not hasattr(collection, "remove"):
            continue
        for index in range(len(collection) - 1, -1, -1):
            if str(getattr(collection[index], "name", "") or "").strip().casefold() == target:
                try:
                    collection.remove(index)
                except Exception:
                    pass


def _texture_set_name_clash(project, desired: str, *, skip_name: str | None = None) -> str | None:
    """The existing set name that ``desired`` would collide with, or None.

    Two sets sharing a name is unrecoverable state, not a cosmetic problem:
    ``properties.find_texture_set`` returns the FIRST match, so the second set's
    UDIM and naming config becomes unreachable from the UI while both sets' groups
    keep compositing into the same output files. Matching is trimmed and
    case-insensitive because the output filenames land on a case-insensitive
    filesystem, where "SetA" and "seta" are the same file.

    ``skip_name`` is the set being renamed, so a deliberate case-only rename
    ("body" -> "Body") is still allowed.
    """
    target = (desired or "").strip().casefold()
    if not target:
        return None
    skip = (skip_name or "").strip() if skip_name is not None else None
    for texture_set in getattr(project, "texture_sets", []) or []:
        name = str(getattr(texture_set, "name", "") or "").strip()
        if skip is not None and name == skip:
            continue
        if name.casefold() == target:
            return name
    return None


def _reveal_created_item_settings(context) -> None:
    """Open Meshes and keep the new item's settings expanded."""
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    if settings is None:
        return
    sidebar_state.select_single(settings, constants.SIDEBAR_MESHES)
    ui_state = properties.scene_ui_state(settings)
    if ui_state is not None and hasattr(ui_state, "reveal_hierarchy_context"):
        ui_state.reveal_hierarchy_context = True


def _clear_revealed_item_settings(context) -> None:
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    ui_state = properties.scene_ui_state(settings) if settings is not None else None
    if ui_state is not None and hasattr(ui_state, "reveal_hierarchy_context"):
        ui_state.reveal_hierarchy_context = False


class MASTER_BAKER_OT_new_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.new_texture_set"
    bl_label = "New Texture Set"
    bl_description = "Create a new texture set and optionally assign the active bake group to it"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    name: bpy.props.StringProperty(name="Name", default="TextureSet")
    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})
    assign_active_group: bpy.props.BoolProperty(
        name="Assign Active Bake Group",
        default=True,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    apply_to_targets: bpy.props.BoolProperty(
        name="Apply To Selected Groups",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        clean_name = self.name.strip()
        if not clean_name:
            self.report({"ERROR"}, "Texture set name cannot be empty")
            return {"CANCELLED"}

        # Create TextureSet item if it doesn't exist
        if not hasattr(project, "texture_sets"):
            self.report({"ERROR"}, "Project does not support texture sets - please migrate first")
            return {"CANCELLED"}

        existing_ts = next((ts for ts in project.texture_sets if ts.name == clean_name), None)
        if existing_ts is None:
            clash = _texture_set_name_clash(project, clean_name)
            if clash is not None:
                self.report(
                    {"ERROR"},
                    f"A texture set called '{clash}' already exists in this project. Pick a different name",
                )
                return {"CANCELLED"}
            ts = project.texture_sets.add()
            ts.name = clean_name
            project.active_texture_set_index = len(project.texture_sets) - 1

        # Assign to group if specified. The set list's New leaves the current group
        # where it is. The group menu's New puts the selected groups in the new set.
        if self.apply_to_targets:
            settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
            names = set(properties.bake_group_target_names(project, settings))
            for group in getattr(project, "groups", []) or []:
                if str(getattr(group, "name", "") or "").strip() in names:
                    group.texture_set_name = clean_name
        elif self.assign_active_group:
            target_name = self.group_name.strip()
            if target_name:
                group = next((g for g in project.groups if g.name == target_name), None)
                if group is None:
                    self.report({"ERROR"}, f"Bake group '{target_name}' not found")
                    return {"CANCELLED"}
                group.texture_set_name = clean_name
            else:
                group = _active_group_or_report(self, project)
                if group is not None:
                    group.texture_set_name = clean_name

        project.hierarchy_focus = constants.HIERARCHY_FOCUS_TEXTURE_SET
        _reveal_created_item_settings(context)
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.clear_texture_set"
    bl_label = "Remove from Texture Set"
    bl_description = "Remove this bake group from its texture set so it produces standalone output files"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})
    apply_to_targets: bpy.props.BoolProperty(
        name="Apply To Selected Groups",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if self.apply_to_targets:
            settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
            names = set(properties.bake_group_target_names(project, settings))
            matched = False
            for group in getattr(project, "groups", []) or []:
                if str(getattr(group, "name", "") or "").strip() in names:
                    group.texture_set_name = ""
                    matched = True
            if not matched:
                self.report({"ERROR"}, "No bake group selected")
                return {"CANCELLED"}
            return {"FINISHED"}
        target_name = self.group_name.strip()
        if target_name:
            group = next((g for g in project.groups if g.name == target_name), None)
            if group is None:
                self.report({"ERROR"}, f"Bake group '{target_name}' not found")
                return {"CANCELLED"}
        else:
            group = _active_group_or_report(self, project)
            if group is None:
                return {"CANCELLED"}
        group.texture_set_name = ""
        return {"FINISHED"}


class MASTER_BAKER_OT_migrate_texture_sets(bpy.types.Operator):
    bl_idname = "master_baker.migrate_texture_sets"
    bl_label = "Migrate Texture Sets"
    bl_description = "Migrate texture set names from bake groups to the new texture_sets collection"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        # Skip if already migrated (texture_sets collection exists and has items)
        if hasattr(project, "texture_sets") and len(project.texture_sets) > 0:
            self.report({"INFO"}, "Texture sets already migrated")
            return {"CANCELLED"}

        # Collect unique texture set names from groups
        texture_set_names = set()
        for group in project.groups:
            ts_name = (getattr(group, "texture_set_name", "") or "").strip()
            if ts_name:
                texture_set_names.add(ts_name)

        # Create TextureSet items for each unique name
        for ts_name in sorted(texture_set_names):
            ts = project.texture_sets.add()
            ts.name = ts_name

        self.report({"INFO"}, f"Migrated {len(texture_set_names)} texture sets")
        return {"FINISHED"}


class MASTER_BAKER_OT_dissolve_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.dissolve_texture_set"
    bl_label = "Dissolve Texture Set"
    bl_description = (
        "Remove this texture set and unlink every bake group from it. "
        "Restore is offered until the next change"
    )
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        if not hasattr(project, "texture_sets") or len(project.texture_sets) == 0:
            self.report({"ERROR"}, "No texture sets to dissolve")
            return {"CANCELLED"}

        requested = str(getattr(self, "set_name", "") or "").strip()
        if requested:
            active_index = next(
                (
                    index
                    for index, texture_set in enumerate(project.texture_sets)
                    if str(getattr(texture_set, "name", "") or "") == requested
                ),
                -1,
            )
            if active_index < 0:
                self.report({"ERROR"}, f"Texture set '{requested}' not found")
                return {"CANCELLED"}
        else:
            active_index = getattr(project, "active_texture_set_index", 0)
            if active_index < 0 or active_index >= len(project.texture_sets):
                self.report({"ERROR"}, "Invalid texture set index")
                return {"CANCELLED"}

        ts = project.texture_sets[active_index]
        target = ts.name

        # Membership is the half of this that cannot be retyped from the set alone:
        # dissolving clears texture_set_name on every member, so the undo payload has
        # to carry who was in it as well as the set's own name / UDIM configuration.
        member_group_names = [
            str(getattr(group, "name", "") or "")
            for group in _texture_set_member_groups(project, target)
        ]
        _stash_removed_item(
            runtime.STASH_KIND_TEXTURE_SET,
            lambda: preset_store.texture_set_to_payload(ts),
            label=f"Undo Dissolve '{target}'" if target else "Undo Dissolve Texture Set",
            location={
                "project_name": str(getattr(project, "name", "") or ""),
                "index": int(active_index),
                "member_group_names": member_group_names,
            },
        )

        # Remove the TextureSet item
        project.texture_sets.remove(active_index)
        project.active_texture_set_index = max(0, min(active_index, len(project.texture_sets) - 1))
        # The Export dialog's per-set override and exclusion rows outlived the set:
        # a later set with the same name silently inherited a stale 512px override
        # or a stale exclusion. Drop them with the set (the undo payload does not
        # carry them; a restored set starts from the project defaults).
        _prune_export_rows_for_texture_set(project, target)

        # Clear texture_set_name from all groups
        for group in project.groups:
            if (getattr(group, "texture_set_name", "") or "").strip() == target:
                group.texture_set_name = ""

        self.report({"INFO"}, f"Dissolved texture set '{target}'. Use Undo Dissolve to restore")
        return {"FINISHED"}


class MASTER_BAKER_OT_show_texture_set_picker(bpy.types.Operator):
    """Open the contextual texture-set picker menu for a specific group.

    The menu is driven by a group *name* (stashed on the ui module) rather than a
    context_pointer_set to the live project.groups element: a pointer into that
    CollectionProperty dangles the moment the collection is resized, and resolving
    it inside the popup's draw() would be a use-after-free crash. A string name is
    immune to that.
    """

    bl_idname = "master_baker.show_texture_set_picker"
    bl_label = "Texture Set"
    bl_description = "Assign, rename, or clear this bake group's texture set"
    bl_options = {"INTERNAL"}

    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})

    def execute(self, context):
        from . import ui as _ui_module

        _ui_module._texture_set_menu_target_group = self.group_name
        _ui_module._texture_set_menu_apply_to_targets = False
        bpy.ops.wm.call_menu(name="MASTER_BAKER_MT_texture_set_picker")
        return {"FINISHED"}


class MASTER_BAKER_OT_show_assign_texture_set_menu(bpy.types.Operator):
    """Open the texture-set menu for one group, or for the header's selection."""

    bl_idname = "master_baker.show_assign_texture_set_menu"
    bl_label = "Texture Set"
    bl_description = "Choose the texture set these bake groups write into"
    bl_options = {"INTERNAL"}

    group_name: bpy.props.StringProperty(name="Bake Group", default="", options={"HIDDEN"})
    apply_to_targets: bpy.props.BoolProperty(
        name="Apply To Selected Groups",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context):
        from . import ui as _ui_module

        _ui_module._texture_set_menu_target_group = self.group_name
        _ui_module._texture_set_menu_apply_to_targets = bool(self.apply_to_targets)
        bpy.ops.wm.call_menu(name="MASTER_BAKER_MT_assign_texture_set")
        return {"FINISHED"}


class MASTER_BAKER_OT_show_texture_set_row_menu(bpy.types.Operator):
    bl_idname = "master_baker.show_texture_set_row_menu"
    bl_label = "Texture Set"
    bl_description = "Dissolve this texture set"
    bl_options = {"INTERNAL"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        from . import ui as _ui_module

        _ui_module._texture_set_row_target = self.set_name
        bpy.ops.wm.call_menu(name="MASTER_BAKER_MT_texture_set_row")
        return {"FINISHED"}


class MASTER_BAKER_OT_rename_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.rename_texture_set"
    bl_label = "Rename Texture Set"
    bl_description = "Rename this texture set and update every bake group assigned to it"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    old_name: bpy.props.StringProperty(name="Old Name", default="", options={"HIDDEN"})
    new_name: bpy.props.StringProperty(name="New Name", default="TextureSet")

    def invoke(self, context, event):
        self.new_name = self.old_name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        old_name = self.old_name.strip()
        new_name = self.new_name.strip()
        if not old_name:
            self.report({"ERROR"}, "Texture set name cannot be empty")
            return {"CANCELLED"}
        if not new_name:
            self.report({"ERROR"}, "New texture set name cannot be empty")
            return {"CANCELLED"}
        if old_name == new_name:
            return {"CANCELLED"}
        # A case-only rename ("body" -> "Body") is a real rename: the set name is what
        # every output file is called. It used to be refused without a word.

        # Renaming ONTO another set's name is not a rename, it is a silent merge:
        # both sets end up called the same thing, the second one's UDIM/naming config
        # becomes unreachable (find_texture_set returns the first match) and both
        # sets' groups composite into one set of output files.
        clash = _texture_set_name_clash(project, new_name, skip_name=old_name)
        if clash is not None:
            self.report(
                {"ERROR"},
                f"A texture set called '{clash}' already exists in this project. Pick a different name",
            )
            return {"CANCELLED"}

        # Update the groups BEFORE the TextureSet item: assigning ts.name syncs
        # member groups' texture_set_name as a side effect, so renaming the item
        # first left this loop with zero matches and a false "not found" error
        # after the rename had in fact already succeeded.
        updated_count = 0
        for group in project.groups:
            if (getattr(group, "texture_set_name", "") or "").strip().casefold() == old_name.casefold():
                group.texture_set_name = new_name
                updated_count += 1

        renamed_item = False
        if hasattr(project, "texture_sets"):
            ts = next((t for t in project.texture_sets if t.name == old_name), None)
            if ts is not None:
                ts.name = new_name
                renamed_item = True

        if updated_count == 0 and not renamed_item:
            self.report({"ERROR"}, f"Texture set '{old_name}' not found")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Renamed texture set '{old_name}' to '{new_name}' ({updated_count} bake groups)")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_texture_set_expansion(bpy.types.Operator):
    bl_idname = "master_baker.toggle_texture_set_expansion"
    bl_label = "Toggle Texture Set Expansion"
    bl_description = "Expand or collapse this texture set in the hierarchy"
    bl_options = {"INTERNAL"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        ui_state = properties.scene_ui_state(settings)
        target = self.set_name
        if not target or ui_state is None:
            return {"CANCELLED"}
        collapsed = [name for name in str(getattr(ui_state, "hierarchy_collapsed_sets", "") or "").split("\n") if name]
        if target in collapsed:
            collapsed.remove(target)
        else:
            collapsed.append(target)
        ui_state.hierarchy_collapsed_sets = "\n".join(collapsed)
        return {"FINISHED"}


class MASTER_BAKER_OT_set_active_project_by_index(bpy.types.Operator):
    bl_idname = "master_baker.set_active_project_by_index"
    bl_label = "Set Active Bake Project"
    bl_description = "Make this the active bake project"
    bl_options = {"INTERNAL"}

    project_index: bpy.props.IntProperty(name="Bake Project Index", default=0, options={"HIDDEN"})

    def execute(self, context):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        projects = getattr(settings, "projects", None) if settings is not None else None
        if projects is None or not (0 <= self.project_index < len(projects)):
            return {"CANCELLED"}
        settings.active_project_index = self.project_index
        return {"FINISHED"}


class MASTER_BAKER_OT_set_active_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.set_active_texture_set"
    bl_label = "Set Active Texture Set"
    bl_description = "Make this the active texture set"
    bl_options = {"INTERNAL"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        set_name = str(getattr(properties, "set_name", "") or "").strip()
        if set_name:
            return f"Make '{set_name}' the active texture set"
        return "Make this the active texture set"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        target = self.set_name.strip()
        # Auto-heal: groups may reference a set name that has no collection entry yet
        # (named by the auto-build/suffix ops). Create any missing entries so every set
        # shown in the hierarchy is selectable.
        properties.reconcile_texture_sets(project)
        for index, texture_set in enumerate(getattr(project, "texture_sets", [])):
            if str(getattr(texture_set, "name", "") or "") == target:
                project.active_texture_set_index = index
                project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
                _clear_revealed_item_settings(context)
                members = _texture_set_member_groups(project, target)
                active = properties.peek_active_group(project)
                if members and active not in members:
                    member_name = str(getattr(members[0], "name", "") or "")
                    for group_index, group in enumerate(project.groups):
                        if str(getattr(group, "name", "") or "") == member_name:
                            project.active_group_index = group_index
                            break
                settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
                properties.set_bake_group_targets(settings, [])
                return {"FINISHED"}
        return {"CANCELLED"}


def _texture_set_member_groups(project, set_name: str):
    target = str(set_name or "").strip()
    return [
        group
        for group in getattr(project, "groups", [])
        if (getattr(group, "texture_set_name", "") or "").strip() == target
    ]


class MASTER_BAKER_OT_toggle_texture_set_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_texture_set_visibility"
    bl_label = "Toggle Texture Set Visibility"
    bl_description = "Show or hide every mesh in this texture set's bake groups"
    bl_options = {"REGISTER", "UNDO"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        objects = []
        for group in _texture_set_member_groups(project, self.set_name):
            role_state = properties.group_role_assignments_state(group)
            for slot in list(getattr(role_state, "low_meshes", [])) + list(getattr(role_state, "high_meshes", [])):
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    objects.append(obj)
        if not objects:
            return {"CANCELLED"}

        any_visible = any(not _object_hidden_with_fallback(o) for o in objects)
        for obj in objects:
            _set_object_hidden_with_fallback(obj, any_visible)

        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_group_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_group_visibility"
    bl_label = "Toggle Bake Group Visibility"
    bl_options = {"REGISTER", "UNDO"}

    group_index: bpy.props.IntProperty(name="Bake Group Index", default=0)
    # Plain click controls only the low-poly meshes — the geometry you actually work with —
    # so showing a group doesn't drag the high-poly back into the viewport. Shift-click
    # includes the high-poly to show/hide the whole group at once.
    include_high: bpy.props.BoolProperty(name="Include High Poly", default=False, options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        if bool(getattr(properties, "include_high", False)):
            return "Show or hide every mesh in this bake group, including the high-poly"
        return "Show or hide this bake group's low-poly meshes. Shift-click to include the high-poly"

    def invoke(self, context, event):
        self.include_high = bool(getattr(event, "shift", False))
        return self.execute(context)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if self.group_index < 0 or self.group_index >= len(project.groups):
            return {"CANCELLED"}
        group = project.groups[self.group_index]

        role_state = properties.group_role_assignments_state(group)
        role_names = ["low_meshes", "high_meshes"] if self.include_high else ["low_meshes"]
        objects = []
        for role_name in role_names:
            for slot in getattr(role_state, role_name, []):
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    objects.append(obj)
        if not objects:
            role_label = "meshes" if self.include_high else "low-poly meshes"
            self.report({"ERROR"}, f"No {role_label} are assigned to this bake group")
            return {"CANCELLED"}

        any_visible = any(not _object_hidden_with_fallback(o) for o in objects)
        for obj in objects:
            _set_object_hidden_with_fallback(obj, any_visible)
        if hasattr(group, "isolate_in_viewport"):
            group.isolate_in_viewport = False

        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            clear_static=True,
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_texture_set_cage_overlay(bpy.types.Operator):
    bl_idname = "master_baker.toggle_texture_set_cage_overlay"
    bl_label = "Toggle Texture Set Cage Overlay"
    bl_description = "Show or hide the cage overlay for every bake group in this texture set"
    bl_options = {"REGISTER", "UNDO"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        member_groups = _texture_set_member_groups(project, self.set_name)
        if not member_groups:
            return {"CANCELLED"}

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        overlay_state = properties.overlay_settings_state(settings) if settings else None
        global_visible = bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state else False
        currently_visible = global_visible and any(
            not bool(getattr(group, "cage_overlay_hidden", False)) for group in member_groups
        )

        if currently_visible:
            for group in member_groups:
                group.cage_overlay_hidden = True
        else:
            # Enable the global overlay FIRST so the update callback on
            # cage_overlay_hidden sees show_cage_overlay=True (same ordering
            # requirement as the per-group toggle).
            if overlay_state:
                overlay_state.show_cage_overlay = True
            for group in member_groups:
                group.cage_overlay_hidden = False

        # Visibility-only change: hidden groups are filtered at draw assembly, so
        # keep the static cage batches intact and just redraw.
        overlays.tag_redraw_all_view3d(
            scene=getattr(context, "scene", None),
            window=getattr(context, "window", None),
        )
        return {"FINISHED"}


class _MasterBakerSidebarSelectorBase(bpy.types.Operator):
    section = constants.SIDEBAR_SETUP
    multi_select: bpy.props.BoolProperty(name="Multi Select", default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.multi_select = bool(getattr(event, "shift", False))
        return self.execute(context)

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        sidebar_state.handle_selector_click(settings, self.section, self.multi_select)
        return {"FINISHED"}


class MASTER_BAKER_OT_select_sidebar_meshes(_MasterBakerSidebarSelectorBase):
    bl_idname = "master_baker.select_sidebar_meshes"
    bl_label = "Meshes"
    bl_description = constants.SIDEBAR_SECTION_TOOLTIPS[constants.SIDEBAR_MESHES]
    section = constants.SIDEBAR_MESHES


class MASTER_BAKER_OT_select_sidebar_cage(_MasterBakerSidebarSelectorBase):
    bl_idname = "master_baker.select_sidebar_cage"
    bl_label = "Cage"
    bl_description = constants.SIDEBAR_SECTION_TOOLTIPS[constants.SIDEBAR_CAGE]
    section = constants.SIDEBAR_CAGE


class MASTER_BAKER_OT_select_sidebar_maps(_MasterBakerSidebarSelectorBase):
    bl_idname = "master_baker.select_sidebar_maps"
    bl_label = "Maps"
    bl_description = constants.SIDEBAR_SECTION_TOOLTIPS[constants.SIDEBAR_MAPS]
    section = constants.SIDEBAR_MAPS


class MASTER_BAKER_OT_select_sidebar_output(_MasterBakerSidebarSelectorBase):
    bl_idname = "master_baker.select_sidebar_output"
    bl_label = "Output"
    bl_description = constants.SIDEBAR_SECTION_TOOLTIPS[constants.SIDEBAR_OUTPUT]
    section = constants.SIDEBAR_OUTPUT


class MASTER_BAKER_OT_select_sidebar_preview(_MasterBakerSidebarSelectorBase):
    bl_idname = "master_baker.select_sidebar_preview"
    bl_label = "Preview"
    bl_description = constants.SIDEBAR_SECTION_TOOLTIPS[constants.SIDEBAR_PREVIEW]
    section = constants.SIDEBAR_PREVIEW


class MASTER_BAKER_OT_select_bake_panel_section(bpy.types.Operator):
    bl_idname = "master_baker.select_bake_panel_section"
    bl_label = "Select Bake Panel Section"
    bl_options = {"INTERNAL"}

    section: bpy.props.EnumProperty(
        name="Section",
        items=constants.BAKE_PANEL_SECTION_ITEMS,
        default=constants.BAKE_PANEL_SETTINGS,
        options={"HIDDEN"},
    )

    @classmethod
    def description(cls, _context, properties):
        section = str(getattr(properties, "section", constants.BAKE_PANEL_SETTINGS) or constants.BAKE_PANEL_SETTINGS)
        return constants.BAKE_PANEL_SECTION_TOOLTIPS.get(section, "Show this section in the Bake panel")

    def execute(self, context):
        _set_bake_panel_section(context.scene.fyr_baker_settings, self.section)
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_settings_section(bpy.types.Operator):
    bl_idname = "master_baker.toggle_settings_section"
    bl_label = "Toggle Section"
    bl_description = "Expand or collapse this section"
    bl_options = {"INTERNAL"}

    prop_name: bpy.props.StringProperty(name="Property", default="", options={"HIDDEN"})

    def execute(self, context):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        prop_name = str(getattr(self, "prop_name", "") or "").strip()
        target = properties.resolve_settings_surface(settings, prop_name)
        if target is None:
            return {"CANCELLED"}

        current_value = bool(getattr(target, prop_name, False))
        setattr(target, prop_name, not current_value)
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_mm_calibration(bpy.types.Operator):
    bl_idname = "master_baker.reset_mm_calibration"
    bl_label = "Reset to Calibrated Defaults"
    bl_description = "Restore the curvature response sliders to their calibrated defaults"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is None:
            return {"CANCELLED"}
        properties.reset_mm_calibration(settings)
        return {"FINISHED"}


class MASTER_BAKER_OT_save_project_preset(bpy.types.Operator):
    bl_idname = "master_baker.save_project_preset"
    bl_label = "Save Preset"
    bl_description = "Save the active bake project as a reusable preset"
    bl_options = {"REGISTER"}

    preset_name: bpy.props.StringProperty(name="Preset Name", default="")

    def invoke(self, context, event):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if not self.preset_name:
            self.preset_name = project.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.label(text=_project_preset_folder_label())

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        try:
            path = preset_store.save_project_preset(project, self.preset_name or project.name)
        except preset_store.PresetError as error:
            # Two names can sanitize onto one file; refusing is the whole point, so
            # the artist has to see it rather than lose the preset that was there.
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        context.scene.fyr_baker_settings.status_message = f"Saved preset {path.stem}"
        project.last_status_message = f"Saved preset {path.stem}"
        self.report({"INFO"}, f"Saved preset: {path}")
        return {"FINISHED"}


def _project_is_unconfigured(project) -> bool:
    """True when a project holds no work worth protecting.

    A freshly created project -- no bake groups and no texture sets -- is a container the
    artist made *in order to* load something into it, so loading in place is what they
    meant. Anything with groups is real work.
    """
    if project is None:
        return True
    if len(getattr(project, "groups", []) or []) > 0:
        return False
    if len(getattr(project, "texture_sets", []) or []) > 0:
        return False
    return True


class MASTER_BAKER_OT_load_project_preset(bpy.types.Operator):
    bl_idname = "master_baker.load_project_preset"
    bl_label = "Load Preset"
    bl_description = (
        "Load a saved bake project preset. Loads into the active project when it is still "
        "empty, otherwise creates a new project so existing work is not overwritten"
    )
    # REGISTER only, matching add_project / remove_project / restore_removed_project /
    # add_group / migrate_texture_sets / dissolve_texture_set. This operator mutates the
    # same structural project state they do, so it carries the same T74067 memfile-undo
    # hazard; it was the only one of the seven declaring UNDO (RC sweep 2026-08-29,
    # finding 6).
    bl_options = {"REGISTER"}

    preset_name: bpy.props.EnumProperty(name="Preset", items=preset_store.list_preset_items)

    def invoke(self, context, event):
        return context.window_manager.invoke_search_popup(self)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        settings = context.scene.fyr_baker_settings
        project = properties.get_active_project(context.scene)
        # Loading used to overwrite whatever was active, with no confirmation and no way
        # back -- a mis-click in the search popup was enough to destroy a configured
        # project. Only reuse the active one when there is nothing in it to lose.
        replaced_in_place = _project_is_unconfigured(project)
        if project is None or not replaced_in_place:
            project = _create_default_project(context)

        if self.preset_name == "__none__":
            self.report({"ERROR"}, "No preset files exist yet")
            return {"CANCELLED"}

        try:
            with properties.suppress_low_sample_warning():
                preset_store.load_project_preset(
                    project,
                    self.preset_name,
                    object_lookup=_scene_object_lookup(context.scene),
                )
        except FileNotFoundError:
            self.report({"ERROR"}, f"Preset file not found: {self.preset_name}")
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        properties.ensure_default_maps(project)
        properties.bulk_group_membership_refresh(context, project.groups)
        # The payload carries the project name it was saved under, so loading the same
        # preset twice would otherwise give two projects that write the same filenames.
        project.name = _unique_project_name(settings, getattr(project, "name", ""), skip=project)
        settings.active_project_index = min(max(settings.active_project_index, 0), len(settings.projects) - 1)
        # payload["name"] is the PROJECT name stored in the preset, not the preset's own
        # name — reporting it read as "Loaded preset BakeProject" for every preset.
        settings.status_message = f"Loaded preset {self.preset_name}"
        project.last_status_message = settings.status_message
        if replaced_in_place:
            self.report({"INFO"}, f"Loaded preset: {self.preset_name}")
        else:
            self.report(
                {"INFO"},
                f"Loaded preset '{self.preset_name}' into a new project "
                f"'{getattr(project, 'name', '')}' (the previous project was kept)",
            )
        return {"FINISHED"}


class MASTER_BAKER_OT_duplicate_project(bpy.types.Operator):
    bl_idname = "master_baker.duplicate_project"
    bl_label = "Duplicate Bake Project"
    bl_description = "Duplicate the active bake project and its current settings"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        source = _active_project_or_report(self, context)
        if source is None:
            return {"CANCELLED"}
        settings = context.scene.fyr_baker_settings
        target = settings.projects.add()
        _copy_project(source, target)
        settings.active_project_index = len(settings.projects) - 1
        _ensure_project_collection_scaffold(context, target)
        for group in target.groups:
            _ensure_group_collection_scaffold(context, target, group)
        settings.status_message = "Duplicated Bake Project"
        return {"FINISHED"}


class MASTER_BAKER_OT_remove_project(bpy.types.Operator):
    bl_idname = "master_baker.remove_project"
    bl_label = "Remove Bake Project"
    bl_description = "Remove the active bake project from this blend file"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        if not settings.projects:
            self.report({"ERROR"}, "No Bake Project to remove")
            return {"CANCELLED"}
        project = settings.projects[settings.active_project_index]
        # Stash a full serialization first so the removal can be undone via
        # master_baker.restore_removed_project. This replaces native {"UNDO"},
        # which reallocs fyr_baker_settings and dangles panel buttons (T74067).
        removed_name = str(getattr(project, "name", "") or "")
        removed_groups = list(getattr(project, "groups", []) or [])
        tag_snapshot = _role_tag_snapshot(_objects_owned_by_groups(removed_groups))
        try:
            payload = preset_store.project_to_payload(project)
            # Rides along with the project payload so Undo Remove can replay the exact
            # tags the clearing below strips. preset_store's generic property sweep
            # skips dict values, so this key never lands on the restored project.
            payload["object_role_tags"] = tag_snapshot
            runtime.stash_removed_project(payload)
        except Exception:
            runtime.stash_removed_project(None)
        # Role tags live on the objects, so a removed project used to leave every one
        # of its meshes claiming a bake group that no longer exists.
        _clear_stale_role_tags(context, removed_groups)
        if _live_bake_is_active(settings, project):
            _deactivate_live_bake(context.scene)
        # Put the artist's own materials back before the project goes away. The
        # preview swaps a generated material into every low slot, and removing the
        # project used to leave it there: the object kept wearing the preview, and
        # the only operator that undoes it is drawn inside the project's own Preview
        # panel, which no longer exists. That state is unrecoverable from the UI.
        try:
            _deactivate_preview_on_low(context)
        except Exception:
            pass
        _remove_project_collections(context, project)
        settings.projects.remove(settings.active_project_index)
        high_mesh_cache.reconcile_scene_tracking(context.scene)
        settings.active_project_index = max(0, min(settings.active_project_index, len(settings.projects) - 1))
        settings.status_message = (
            f"Removed '{removed_name}'. Use Undo Remove to restore" if removed_name else "Removed Bake Project"
        )
        _tag_redraw_every_area(context)
        return {"FINISHED"}


def _tag_redraw_every_area(context):
    """Force every open region to rebuild its buttons.

    Removing a project frees the PropertyGroup its panel buttons point at.
    Blender retains uiBlocks between draws, so without this the next redraw can
    dereference a freed RNA pointer and die inside widget_draw_text_icon --
    a crash with no Python frames, because the fault is in Blender's own button
    draw. Tagging every area discards those blocks instead of reusing them.
    """
    window_manager = getattr(context, "window_manager", None)
    for window in getattr(window_manager, "windows", ()) or ():
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", ()) or ():
            try:
                area.tag_redraw()
            except Exception:
                pass


class MASTER_BAKER_OT_restore_removed_project(bpy.types.Operator):
    bl_idname = "master_baker.restore_removed_project"
    bl_label = "Undo Remove Project"
    bl_description = "Restore the bake project that was most recently removed"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    @classmethod
    def poll(cls, _context):
        return runtime.has_removed_project()

    def execute(self, context):
        payload = runtime.pop_removed_project()
        if not payload:
            self.report({"ERROR"}, "No removed project to restore")
            return {"CANCELLED"}
        settings = context.scene.fyr_baker_settings
        project = settings.projects.add()
        try:
            with properties.suppress_low_sample_warning():
                preset_store.apply_payload_to_project(
                    project, payload, object_lookup=_scene_object_lookup(context.scene)
                )
            project.name = _unique_project_name(settings, getattr(project, "name", ""), skip=project)
        except Exception as exc:
            # Roll back the half-built project and re-stash so the user can retry.
            settings.projects.remove(len(settings.projects) - 1)
            runtime.stash_removed_project(payload)
            self.report({"ERROR"}, f"Could not restore project: {exc}")
            return {"CANCELLED"}
        properties.ensure_default_maps(project)
        _ensure_project_collection_scaffold(context, project)
        for group in project.groups:
            _ensure_group_collection_scaffold(context, project, group)
        properties.bulk_group_membership_refresh(context, project.groups)
        _reapply_role_tag_snapshot(context, (payload or {}).get("object_role_tags") or {})
        settings.active_project_index = len(settings.projects) - 1
        settings.status_message = f"Restored '{project.name}'"
        project.last_status_message = settings.status_message
        return {"FINISHED"}


def _unique_project_name(settings, desired: str, *, skip=None) -> str:
    """Blender-style uniquifier so two projects never share a name.

    This is not cosmetic. A project's name drives its texture set name and every group's
    ``texture_set_name``, which drives the OUTPUT FILENAMES -- so two projects called
    "Skull" both write ``Skull_Normal.tga`` and silently overwrite each other. Renaming the
    second to ``Skull.001`` is what keeps their outputs apart, and it matches how Blender
    uniquifies every other datablock.
    """
    base = str(desired or "").strip() or "BakeProject"
    skip_pointer = skip.as_pointer() if skip is not None and hasattr(skip, "as_pointer") else None
    existing = {
        str(getattr(item, "name", "") or "")
        for item in getattr(settings, "projects", [])
        if skip_pointer is None or item.as_pointer() != skip_pointer
    }
    if base not in existing:
        return base
    for suffix in range(1, 1000):
        candidate = f"{base}.{suffix:03d}"
        if candidate not in existing:
            return candidate
    return base


# --- Undo Remove: stash + restore for the destructive structural ops -------------
#
# remove_group / remove_map / dissolve_texture_set / clear_role_slot are one-click,
# icon-only, unconfirmed actions. They cannot carry {"UNDO"} for the T74067 reason
# add_project documents, so each one serializes what it is about to destroy into the
# single-slot runtime stash and the sidebar offers one "Undo Remove" row until the
# next structural action. Same contract as remove_project / restore_removed_project.


def _project_by_name_or_active(context, project_name: str):
    """The project a stashed item came from, falling back to the active one.

    Matching by NAME, not index: the stash outlives whatever reordering happened in
    between, and a pointer into settings.projects dangles the moment that collection
    is resized.
    """
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    target = str(project_name or "")
    if settings is not None and target:
        for project in getattr(settings, "projects", []) or []:
            if str(getattr(project, "name", "") or "") == target:
                return project
        # The stash names a project that no longer exists (renamed or removed after
        # the removal). Falling back to the ACTIVE project restored the item into
        # whatever project happened to be selected; every caller already reports
        # "the bake project it belonged to is gone" for None, so say that instead.
        return None
    return properties.peek_active_project(getattr(context, "scene", None))


def _move_collection_item(collection, from_index: int, to_index: int) -> None:
    """Put a just-appended item back at ``to_index``.

    A restored map row or texture set that lands at the bottom of the stack is not
    restored -- its position is part of what the artist had. Blender collections
    expose move(); the unit-test fakes are plain lists, so fall back to a splice.
    """
    length = len(collection)
    if length <= 0:
        return
    from_index = max(0, min(int(from_index), length - 1))
    to_index = max(0, min(int(to_index), length - 1))
    if from_index == to_index:
        return
    mover = getattr(collection, "move", None)
    if callable(mover):
        try:
            mover(from_index, to_index)
            return
        except Exception:
            pass
    try:
        item = collection[from_index]
        del collection[from_index]
        collection.insert(to_index, item)
    except Exception:
        pass


def _unique_group_name(project, desired: str, *, skip=None) -> str:
    """Blender-style uniquifier for bake group names.

    Group names drive output filenames for standalone groups, so two groups sharing
    one name write the same files. Only reachable when something else claimed the
    name while the removal was still undoable.
    """
    base = str(desired or "").strip() or "BakeGroup"
    skip_pointer = skip.as_pointer() if skip is not None and hasattr(skip, "as_pointer") else None
    existing = set()
    for item in getattr(project, "groups", []) or []:
        if item is skip:
            continue
        if skip_pointer is not None and hasattr(item, "as_pointer") and item.as_pointer() == skip_pointer:
            continue
        existing.add(str(getattr(item, "name", "") or ""))
    if base not in existing:
        return base
    for suffix in range(1, 1000):
        candidate = f"{base}.{suffix:03d}"
        if candidate not in existing:
            return candidate
    return base


def _stash_removed_item(kind: str, payload_factory, *, label: str, location: dict) -> None:
    """Arm the Undo Remove offer, or arm nothing if the serialization failed.

    Takes a FACTORY, not a payload: serialization runs inside the guard, so a field
    this build cannot read can never turn a one-click remove into a Python error
    popup. A Restore button that cannot restore is worse than no button, so a payload
    that could not be built clears the stash rather than leaving a stale one armed.
    """
    try:
        runtime.stash_removed_item(kind, payload_factory(), label=label, location=location)
    except Exception:
        runtime.clear_removed_item_stash()


def _restore_group_from_stash(context, entry) -> str:
    location = entry.get("location") or {}
    project = _project_by_name_or_active(context, location.get("project_name", ""))
    if project is None:
        raise RuntimeError("the bake project it belonged to is gone")
    group = project.groups.add()
    with properties.suspend_group_membership_updates():
        preset_store.apply_payload_to_group(
            group, entry.get("payload") or {}, _scene_object_lookup(context.scene), project=project
        )
    group.name = _unique_group_name(project, getattr(group, "name", ""), skip=group)
    index = int(location.get("index", len(project.groups) - 1) or 0)
    _move_collection_item(project.groups, len(project.groups) - 1, index)
    index = max(0, min(index, len(project.groups) - 1))
    project.active_group_index = index
    project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
    restored = project.groups[index]
    _ensure_group_collection_scaffold(context, project, restored)
    properties.bulk_group_membership_refresh(context, [restored])
    _reapply_role_tag_snapshot(context, location.get("object_tags") or {})
    overlays.tag_redraw_all_view3d()
    return f"Restored bake group '{getattr(restored, 'name', '')}'"


def _restore_map_from_stash(context, entry) -> str:
    location = entry.get("location") or {}
    project = _project_by_name_or_active(context, location.get("project_name", ""))
    if project is None:
        raise RuntimeError("the bake project it belonged to is gone")
    properties.remove_phantom_map_items(project)
    item = project.maps.add()
    preset_store.apply_payload_to_map(item, entry.get("payload") or {})
    index = int(location.get("index", len(project.maps) - 1) or 0)
    _move_collection_item(project.maps, len(project.maps) - 1, index)
    index = max(0, min(index, len(project.maps) - 1))
    project.active_map_index = index
    label = naming.map_label(getattr(project.maps[index], "map_type", ""))
    return f"Restored {label} map"


def _restore_texture_set_from_stash(context, entry) -> str:
    location = entry.get("location") or {}
    project = _project_by_name_or_active(context, location.get("project_name", ""))
    if project is None:
        raise RuntimeError("the bake project it belonged to is gone")
    texture_sets = getattr(project, "texture_sets", None)
    if texture_sets is None or not hasattr(texture_sets, "add"):
        raise RuntimeError("this project has no texture sets")
    texture_set = texture_sets.add()
    preset_store.apply_payload_to_texture_set(texture_set, entry.get("payload") or {})
    index = int(location.get("index", len(texture_sets) - 1) or 0)
    _move_collection_item(texture_sets, len(texture_sets) - 1, index)
    index = max(0, min(index, len(texture_sets) - 1))
    project.active_texture_set_index = index
    set_name = str(getattr(texture_sets[index], "name", "") or "")
    # Re-link the members. Dissolving cleared texture_set_name on every member group,
    # so the set alone is only half the state -- without this the restored set comes
    # back empty and every group it owned still writes standalone output files.
    member_names = {str(name or "") for name in (location.get("member_group_names") or [])}
    for group in getattr(project, "groups", []) or []:
        if str(getattr(group, "name", "") or "") in member_names:
            group.texture_set_name = set_name
    return f"Restored texture set '{set_name}'"


def _restore_role_slot_from_stash(context, entry) -> str:
    location = entry.get("location") or {}
    project = _project_by_name_or_active(context, location.get("project_name", ""))
    if project is None:
        raise RuntimeError("the bake project it belonged to is gone")
    group_name = str(location.get("group_name", "") or "")
    group = next(
        (item for item in getattr(project, "groups", []) or [] if str(getattr(item, "name", "") or "") == group_name),
        None,
    )
    if group is None:
        raise RuntimeError(f"bake group '{group_name}' is gone")
    role = str(location.get("role", constants.OBJECT_ROLE_LOW) or constants.OBJECT_ROLE_LOW)
    collections, index_attr, role_state = project_structure.group_role_slot_collections(group, role)
    if not collections:
        raise RuntimeError("this bake group has no such mesh list")
    # The whole pre-removal list is replayed, not just the dropped slot: that restores
    # its ORDER and its per-mesh cage offset in one write, and the group mirrors the
    # list across two collections that must not disagree.
    lookup = _scene_object_lookup(context.scene)
    with properties.suspend_group_membership_updates():
        preset_store.sync_slot_payload_to_collections(entry.get("payload") or [], collections, lookup)
    index = max(0, min(int(location.get("index", 0) or 0), max(len(collections[0]) - 1, 0)))
    if hasattr(role_state, index_attr):
        setattr(role_state, index_attr, index)
    if hasattr(group, index_attr):
        setattr(group, index_attr, index)
    restored_name = str(location.get("object_name", "") or "")
    restored_object = lookup(restored_name) if restored_name else None
    if restored_object is not None:
        _link_objects_to_group_role_collection(context, project, group, role, [restored_object])
    properties.bulk_group_membership_refresh(context, [group])
    overlays.tag_redraw_all_view3d()
    return f"Restored {role.title()} mesh '{restored_name}'" if restored_name else "Restored mesh assignment"


_STASH_RESTORE_HANDLERS = {}


class MASTER_BAKER_OT_restore_removed_item(bpy.types.Operator):
    """Put back whatever the last destructive click removed.

    One operator for every kind because there is only ever one stashed item: the
    stash is a single slot, which is also what stops two Restore rows appearing in
    the sidebar at once.
    """

    bl_idname = "master_baker.restore_removed_item"
    bl_label = "Undo Remove"
    bl_description = "Restore the bake group, map, texture set, or mesh assignment that was just removed"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    @classmethod
    def poll(cls, _context):
        return runtime.has_removed_item()

    def execute(self, context):
        entry = runtime.peek_removed_item()
        handler = _STASH_RESTORE_HANDLERS.get((entry or {}).get("kind", ""))
        if entry is None or handler is None:
            self.report({"ERROR"}, "There is nothing to restore")
            return {"CANCELLED"}
        runtime.pop_removed_item()
        try:
            message = handler(context, entry)
        except Exception as exc:
            # Re-arm so the artist can retry rather than silently losing the payload
            # to a half-applied restore.
            runtime.stash_removed_item(
                entry.get("kind", ""),
                entry.get("payload"),
                label=entry.get("label", ""),
                location=entry.get("location") or {},
            )
            self.report({"ERROR"}, f"Could not restore: {exc}")
            return {"CANCELLED"}
        settings = getattr(context.scene, "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = message
        self.report({"INFO"}, message)
        _tag_redraw_every_area(context)
        return {"FINISHED"}


_STASH_RESTORE_HANDLERS.update(
    {
        runtime.STASH_KIND_GROUP: _restore_group_from_stash,
        runtime.STASH_KIND_MAP: _restore_map_from_stash,
        runtime.STASH_KIND_TEXTURE_SET: _restore_texture_set_from_stash,
        runtime.STASH_KIND_ROLE_SLOT: _restore_role_slot_from_stash,
    }
)


class MASTER_BAKER_OT_add_group(bpy.types.Operator):
    bl_idname = "master_baker.add_group"
    bl_label = "Add Bake Group"
    bl_description = "Add a new bake group to the active bake project"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        _add_empty_bake_group(context, project)
        project.last_status_message = "Added bake group"
        _reveal_created_item_settings(context)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


def _add_empty_bake_group(context, project):
    """Append a new, empty bake group and make it the only selected one."""
    existing = {str(getattr(item, "name", "") or "").strip().casefold() for item in project.groups}
    number = len(project.groups) + 1
    # Counting groups alone reused a live name once one was removed (BakeGroup_01,
    # BakeGroup_03 -> a second BakeGroup_03), and two groups sharing a name write the
    # same output files.
    while f"BakeGroup_{number:02d}".casefold() in existing:
        number += 1
    group = project.groups.add()
    group.name = f"BakeGroup_{number:02d}"
    # Join the project's active texture set when the artist actually has one, so the new
    # group lands alongside the rest of the project rather than in a separate tree node.
    # With no sets defined the group stays standalone (texture_set_name == "") and its
    # outputs are named after the GROUP -- fabricating a project-named set here is what
    # made fresh projects write BakeProject_*.tga instead of Pottery_*.tga.
    active_set = properties.get_active_texture_set(project)
    if active_set is not None:
        group.texture_set_name = active_set.name
    project.active_group_index = len(project.groups) - 1
    project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
    _ensure_group_collection_scaffold(context, project, group)
    properties.set_bake_group_targets(getattr(getattr(context, "scene", None), "fyr_baker_settings", None), [])
    return group


class MASTER_BAKER_OT_create_group_from_selection(bpy.types.Operator):
    bl_idname = "master_baker.create_group_from_selection"
    bl_label = "Create Bake Group From Selection"
    bl_description = "Create bake groups by matching common Low/High, LP/HP, and Cage name suffixes on the selected meshes"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        if not _group_selected_meshes_by_suffix(
            self,
            context,
            status_message="Created or updated {count} bake group(s) from selection",
        ):
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_remove_group(bpy.types.Operator):
    bl_idname = "master_baker.remove_group"
    bl_label = "Remove Bake Group"
    bl_description = "Remove this bake group. Restore is offered until the next change"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    # -1 removes the active group; a valid index removes that specific group (used by
    # the per-row remove button in the hierarchy).
    group_index: bpy.props.IntProperty(name="Bake Group Index", default=-1, options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if not project.groups:
            self.report({"ERROR"}, "No bake group to remove")
            return {"CANCELLED"}
        target = self.group_index if 0 <= self.group_index < len(project.groups) else project.active_group_index
        group = project.groups[target]
        # Serialize before the removal: meshes, cage mode, per-mesh cage offsets,
        # metadata and texture-set membership all live on the PropertyGroup that is
        # about to be freed. Stashing replaces native {"UNDO"}, which reallocs
        # fyr_baker_settings and dangles panel buttons (T74067).
        removed_name = str(getattr(group, "name", "") or "")
        # The role tags live on the OBJECTS, not on the group, so they survive the
        # removal unless they are cleared here. Snapshot them into the stash first so
        # Undo Remove can replay the exact tag (source included) rather than a guess.
        tag_snapshot = _role_tag_snapshot(_group_tagged_objects(group))
        _stash_removed_item(
            runtime.STASH_KIND_GROUP,
            lambda: preset_store.group_to_payload(
                group, project_ignore_backface=bool(getattr(project, "ignore_backface", False))
            ),
            label=f"Undo Remove '{removed_name}'" if removed_name else "Undo Remove Bake Group",
            location={
                "project_name": str(getattr(project, "name", "") or ""),
                "index": int(target),
                "object_tags": tag_snapshot,
            },
        )
        _clear_stale_role_tags(context, [group])
        _remove_group_collections(group)
        project.groups.remove(target)
        project.active_group_index = max(0, min(project.active_group_index, len(project.groups) - 1))
        project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
        project.last_status_message = (
            f"Removed '{removed_name}'. Use Undo Remove to restore" if removed_name else "Removed bake group"
        )
        overlays.tag_redraw_all_view3d()
        _tag_redraw_every_area(context)
        return {"FINISHED"}


class MASTER_BAKER_OT_add_selected_to_role(bpy.types.Operator):
    bl_idname = "master_baker.add_selected_to_role"
    bl_label = "Assign Selected to Bake Group"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    role: bpy.props.EnumProperty(name="Role", items=constants.TAG_ROLE_ITEMS, default=constants.OBJECT_ROLE_LOW)
    new_group: bpy.props.BoolProperty(
        name="New Bake Group",
        description="Put the selected meshes in a new bake group instead of the active one",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        if role == constants.OBJECT_ROLE_CAGE:
            return "Assign the selected mesh as the active bake group's custom cage"
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
        return (
            f"Add the selected meshes to the active bake group's {role_label} list.\n"
            "Shift or Ctrl-click to add them to a new bake group"
        )

    def invoke(self, context, event):
        self.new_group = bool(getattr(event, "shift", False) or getattr(event, "ctrl", False))
        return self.execute(context)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"ERROR"}, "Select one or more mesh objects first")
            return {"CANCELLED"}

        settings = context.scene.fyr_baker_settings
        created_project = False
        created_group = False
        project, created_project = _ensure_active_project(context)
        if self.new_group and self.role != constants.OBJECT_ROLE_CAGE and not created_project and project.groups:
            group, created_group = _add_empty_bake_group(context, project), True
        else:
            group, created_group = _ensure_active_group(project, seed_objects=selected_meshes, context=context)

        if self.role == constants.OBJECT_ROLE_CAGE:
            if len(selected_meshes) != 1:
                self.report({"ERROR"}, "Select exactly one mesh object to assign as the custom cage")
                return {"CANCELLED"}
            group.custom_cage = selected_meshes[0]
            group.cage_mode = constants.CAGE_MODE_CUSTOM
            _link_objects_to_group_role_collection(context, project, group, self.role, selected_meshes[:1])
            added = 1
        else:
            assignable, rejected = _reject_meshes_already_in_opposite_role(
                group, self.role, selected_meshes
            )
            if rejected:
                other = _opposite_role(self.role).title()
                shown = ", ".join(rejected[:3])
                if len(rejected) > 3:
                    shown += f", +{len(rejected) - 3} more"
                self.report(
                    {"WARNING"},
                    f"Skipped {len(rejected)} mesh(es) already assigned as {other} "
                    f"in this group: {shown}",
                )
            if not assignable:
                return {"CANCELLED"}
            selected_meshes = assignable
            added = _add_unique_role_objects(group, self.role, selected_meshes)
            if added == 0:
                self.report({"INFO"}, "Selected objects were already assigned")
                return {"CANCELLED"}
            _link_objects_to_group_role_collection(context, project, group, self.role, selected_meshes)
            _warn_on_role_suffix_mismatch(self, group, self.role, selected_meshes)

        if group.name.startswith("BakeGroup_"):
            group.name = _unique_group_name(project, matching.suggest_group_name(selected_meshes), skip=group)
        for obj in selected_meshes:
            tagging.apply_role_tag(obj, self.role, group_name=group.name, source="manual")
        project.last_status_message = f"Added {added} object(s) as {self.role.title()}"
        if created_project:
            context.scene.fyr_baker_settings.status_message = "Created Bake Project"
        if created_group and not created_project:
            context.scene.fyr_baker_settings.status_message = "Created bake group"
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_add_selected_split_by_role(bpy.types.Operator):
    bl_idname = "master_baker.add_selected_split_by_role"
    bl_label = "Add Selected (Auto Low/High)"
    bl_description = (
        "Add the selected meshes to the active bake group, sending each one to the Low "
        "or High list its own name suffix asks for. Meshes with no suffix are reported "
        "and left unassigned"
    )
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        selected_meshes = _selected_mesh_objects(context)
        if not selected_meshes:
            self.report({"ERROR"}, "Select one or more mesh objects first")
            return {"CANCELLED"}

        buckets, unsuffixed = _split_meshes_by_detected_role(selected_meshes)
        if not any(buckets.values()):
            self.report(
                {"ERROR"},
                "None of the selected meshes carry a _low/_high suffix. Use Add as Low / "
                "Add as High to assign them without renaming",
            )
            return {"CANCELLED"}

        project, created_project = _ensure_active_project(context)
        group, created_group = _ensure_active_group(
            project, seed_objects=selected_meshes, context=context
        )

        summary: list[str] = []
        for role in (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH):
            meshes = buckets[role]
            if not meshes:
                continue
            added = _add_unique_role_objects(group, role, meshes)
            _link_objects_to_group_role_collection(context, project, group, role, meshes)
            for obj in meshes:
                tagging.apply_role_tag(obj, role, group_name=group.name, source="manual")
            summary.append(f"{added} {role.title()}")

        if group.name.startswith("BakeGroup_"):
            group.name = matching.suggest_group_name(selected_meshes)

        message = f"Added {', '.join(summary)}" if summary else "Nothing to add"
        if unsuffixed:
            shown = ", ".join(sorted(unsuffixed)[:3])
            if len(unsuffixed) > 3:
                shown += f", +{len(unsuffixed) - 3} more"
            message += f"; skipped {len(unsuffixed)} unsuffixed ({shown})"
            self.report({"WARNING"}, message)
        else:
            self.report({"INFO"}, message)

        project.last_status_message = message
        if created_project:
            context.scene.fyr_baker_settings.status_message = "Created Bake Project"
        if created_group and not created_project:
            context.scene.fyr_baker_settings.status_message = "Created bake group"
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_role_slot(bpy.types.Operator):
    bl_idname = "master_baker.clear_role_slot"
    bl_label = "Remove Mesh"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    role: bpy.props.EnumProperty(name="Role", items=constants.OBJECT_ROLE_ITEMS, default=constants.OBJECT_ROLE_LOW)

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly" if role == constants.OBJECT_ROLE_HIGH else role.lower()
        return f"Remove the active {role_label} mesh from this bake group. Restore is offered until the next change"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        # Snapshot the WHOLE role list before the removal, not just the dropped slot.
        # The per-mesh cage offset delta rides on the slot and is a number the artist
        # tuned by eye -- re-adding the mesh by hand would not bring it back, and the
        # list order would be wrong too.
        collections, index_attr, role_state = project_structure.group_role_slot_collections(group, self.role)
        slots_payload = preset_store.slot_collection_to_payload(collections[0]) if collections else []
        removed_index = int(getattr(role_state, index_attr, getattr(group, index_attr, 0)) or 0)

        removed_object = _remove_group_role_slot(group, self.role)
        _unlink_object_from_group_role_collection(group, self.role, removed_object)
        removed_name = str(getattr(removed_object, "name", "") or "")
        if removed_object is not None:
            _stash_removed_item(
                runtime.STASH_KIND_ROLE_SLOT,
                lambda: slots_payload,
                label=f"Undo Remove '{removed_name}'" if removed_name else "Undo Remove Mesh",
                location={
                    "project_name": str(getattr(project, "name", "") or ""),
                    "group_name": str(getattr(group, "name", "") or ""),
                    "role": str(self.role),
                    "index": removed_index,
                    "object_name": removed_name,
                },
            )
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_select_group_slot_object(bpy.types.Operator):
    bl_idname = "master_baker.select_group_slot_object"
    bl_label = "Select Mesh"
    bl_options = {"REGISTER", "UNDO"}

    role: bpy.props.EnumProperty(name="Role", items=constants.TAG_ROLE_ITEMS, default=constants.OBJECT_ROLE_LOW)
    slot_index: bpy.props.IntProperty(name="Slot Index", default=0, min=0)

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        if role == constants.OBJECT_ROLE_CAGE:
            return "Select the active bake group's custom cage object"
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
        return f"Select this {role_label} mesh"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        if self.role == constants.OBJECT_ROLE_CAGE:
            target_object = getattr(group, "custom_cage", None)
            if target_object is None:
                self.report({"ERROR"}, "No custom cage is assigned to the active bake group")
                return {"CANCELLED"}
            if not _select_objects_in_view_layer(context, [target_object], active_object=target_object):
                self.report({"ERROR"}, "Unable to select the active bake group's custom cage")
                return {"CANCELLED"}
            self.report({"INFO"}, f"Selected {target_object.name}")
            return {"FINISHED"}

        role_state = _group_role_assignments_state(group)
        flat_slot_collection = getattr(group, "high_meshes", []) if self.role == constants.OBJECT_ROLE_HIGH else getattr(group, "low_meshes", [])
        slot_collection = getattr(role_state, "high_meshes", []) if self.role == constants.OBJECT_ROLE_HIGH else getattr(role_state, "low_meshes", [])
        if not slot_collection and flat_slot_collection:
            slot_collection = flat_slot_collection
        index_attr = "high_mesh_index" if self.role == constants.OBJECT_ROLE_HIGH else "low_mesh_index"
        role_label = "high" if self.role == constants.OBJECT_ROLE_HIGH else "low"
        if self.slot_index < 0 or self.slot_index >= len(slot_collection):
            self.report({"ERROR"}, f"The requested {role_label} mesh is missing")
            return {"CANCELLED"}

        target_object = getattr(slot_collection[self.slot_index], "object_ref", None)
        if target_object is None:
            self.report({"ERROR"}, f"The requested {role_label} mesh has no object assigned")
            return {"CANCELLED"}

        setattr(role_state, index_attr, self.slot_index)
        setattr(group, index_attr, self.slot_index)
        if not _select_objects_in_view_layer(context, [target_object], active_object=target_object):
            self.report({"ERROR"}, f"Unable to select {target_object.name}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Selected {target_object.name}")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_group_slot_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_group_slot_visibility"
    bl_label = "Toggle Mesh Visibility"
    bl_options = {"REGISTER", "UNDO"}

    role: bpy.props.EnumProperty(name="Role", items=constants.TAG_ROLE_ITEMS, default=constants.OBJECT_ROLE_LOW)
    slot_index: bpy.props.IntProperty(name="Slot Index", default=0, min=0)
    isolate: bpy.props.BoolProperty(name="Isolate", default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.isolate = bool(getattr(event, "shift", False))
        return self.execute(context)

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        if bool(getattr(properties, "isolate", False)):
            if role == constants.OBJECT_ROLE_CAGE:
                return "Isolate the custom cage, or restore visibility if it is already isolated"
            role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
            return f"Isolate this {role_label} mesh, or restore visibility if it is already isolated"
        if role == constants.OBJECT_ROLE_CAGE:
            return "Hide the active bake group's custom cage if visible, or show it if hidden"
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
        return f"Hide this {role_label} mesh if visible, or show it if hidden"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        if self.role == constants.OBJECT_ROLE_CAGE:
            target_object = getattr(group, "custom_cage", None)
            if target_object is None:
                self.report({"ERROR"}, "No custom cage is assigned to the active bake group")
                return {"CANCELLED"}
        else:
            role_state = _group_role_assignments_state(group)
            flat_slot_collection = getattr(group, "high_meshes", []) if self.role == constants.OBJECT_ROLE_HIGH else getattr(group, "low_meshes", [])
            slot_collection = getattr(role_state, "high_meshes", []) if self.role == constants.OBJECT_ROLE_HIGH else getattr(role_state, "low_meshes", [])
            if not slot_collection and flat_slot_collection:
                slot_collection = flat_slot_collection
            index_attr = "high_mesh_index" if self.role == constants.OBJECT_ROLE_HIGH else "low_mesh_index"
            role_label = "high" if self.role == constants.OBJECT_ROLE_HIGH else "low"
            if self.slot_index < 0 or self.slot_index >= len(slot_collection):
                self.report({"ERROR"}, f"The requested {role_label} mesh is missing")
                return {"CANCELLED"}
            target_object = getattr(slot_collection[self.slot_index], "object_ref", None)
            if target_object is None:
                self.report({"ERROR"}, f"The requested {role_label} mesh has no object assigned")
                return {"CANCELLED"}
            setattr(role_state, index_attr, self.slot_index)
            setattr(group, index_attr, self.slot_index)

        if self.isolate:
            isolation_result = _toggle_isolation_targets(context.scene, [target_object])
            if isolation_result is None:
                self.report({"ERROR"}, f"Unable to isolate {target_object.name}")
                return {"CANCELLED"}
            message = f"Isolated {target_object.name}" if isolation_result else "Restored viewport visibility"
            self.report({"INFO"}, message)
            overlays.tag_redraw_all_view3d()
            return {"FINISHED"}

        new_hidden = not bool(target_object.hide_get())
        _set_hidden_state_for_objects([target_object], new_hidden)
        action = "Hid" if new_hidden else "Showed"
        self.report({"INFO"}, f"{action} {target_object.name}")
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_sync_group_metadata(bpy.types.Operator):
    bl_idname = "master_baker.sync_group_metadata"
    bl_label = "Sync Bake Group Metadata"
    bl_options = {"REGISTER", "UNDO"}

    source: bpy.props.EnumProperty(
        name="Source",
        items=(
            ("OBJECT", "Object", "Sync bake group metadata from the active object's tag and collection metadata"),
            ("COLLECTION", "Collection", "Sync bake group metadata from the active collection metadata"),
        ),
        default="OBJECT",
    )

    @classmethod
    def description(cls, _context, properties):
        source = getattr(properties, "source", "OBJECT")
        if source == "COLLECTION":
            return "Copy the active collection name into the active bake group's texture set and ID collection fields"
        return "Copy the active object's tag or collection naming into the active bake group's texture set and ID collection fields"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        group = _active_group_or_report(self, project)
        if group is None:
            return {"CANCELLED"}

        if self.source == "COLLECTION":
            source_target = _active_collection(context)
            if source_target is None:
                self.report({"ERROR"}, "No active collection found")
                return {"CANCELLED"}
            metadata = metadata_sync.collection_group_metadata(source_target)
            label = getattr(source_target, "name", "Active Collection")
            source_name = f"collection '{label}'"
        else:
            source_target = getattr(context, "active_object", None)
            if source_target is None:
                self.report({"ERROR"}, "No active object found")
                return {"CANCELLED"}
            metadata = metadata_sync.object_group_metadata(source_target)
            label = getattr(source_target, "name", "Active Object")
            source_name = f"object '{label}'"

        if not metadata:
            self.report({"ERROR"}, f"No metadata could be resolved from {source_name}")
            return {"CANCELLED"}

        changed = metadata_sync.apply_group_metadata(group, metadata)
        if not changed:
            self.report({"INFO"}, f"Bake group metadata already matches {source_name}")
            return {"CANCELLED"}
        # apply_group_metadata writes texture_set_name straight onto the group. Every
        # other assignment path materialises the set; without this the group pointed
        # at a set that did not exist and the UI healer no-ops once any set exists.
        texture_set_name = str(getattr(group, "texture_set_name", "") or "").strip()
        if texture_set_name:
            try:
                properties.ensure_texture_set(project, texture_set_name)
            except Exception:
                pass

        message = f"Synced bake group metadata from {source_name}"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_apply_group_metadata_to_target(bpy.types.Operator):
    bl_idname = "master_baker.apply_group_metadata_to_target"
    bl_label = "Apply Bake Group Metadata"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=(
            ("OBJECT", "Object", "Write the active bake group's texture-set and ID collection metadata onto the active object"),
            ("COLLECTION", "Collection", "Write the active bake group's texture-set and ID collection metadata onto the active collection"),
        ),
        default="OBJECT",
    )

    @classmethod
    def description(cls, _context, properties):
        target = getattr(properties, "target", "OBJECT")
        if target == "COLLECTION":
            return "Write the active bake group's texture set and ID collection metadata onto the active collection"
        return "Write the active bake group's texture set and ID collection metadata onto the active object"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        group = _active_group_or_report(self, project)
        if group is None:
            return {"CANCELLED"}

        metadata = metadata_sync.group_metadata_payload(group)
        if not metadata:
            self.report({"ERROR"}, "Active bake group has no metadata to apply")
            return {"CANCELLED"}

        if self.target == "COLLECTION":
            target = _active_collection(context)
            if target is None:
                self.report({"ERROR"}, "No active collection found")
                return {"CANCELLED"}
            label = getattr(target, "name", "Active Collection")
            target_name = f"collection '{label}'"
        else:
            target = getattr(context, "active_object", None)
            if target is None:
                self.report({"ERROR"}, "No active object found")
                return {"CANCELLED"}
            label = getattr(target, "name", "Active Object")
            target_name = f"object '{label}'"

        changed = metadata_sync.apply_group_metadata_to_target(target, metadata)
        if not changed:
            self.report({"INFO"}, f"{target_name} already matches the active bake group metadata")
            return {"CANCELLED"}

        message = f"Applied bake group metadata to {target_name}"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_set_custom_cage_from_selection(bpy.types.Operator):
    bl_idname = "master_baker.set_custom_cage_from_selection"
    bl_label = "Use Selected as Custom Cage"
    bl_description = "Use the selected mesh as the custom cage for the active bake group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if len(selected_meshes) != 1:
            self.report({"ERROR"}, "Select exactly one mesh object to use as the custom cage")
            return {"CANCELLED"}

        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        group.custom_cage = selected_meshes[0]
        group.cage_mode = constants.CAGE_MODE_CUSTOM
        tagging.apply_role_tag(selected_meshes[0], constants.OBJECT_ROLE_CAGE, group_name=group.name, source="manual")
        project.last_status_message = f"Using {selected_meshes[0].name} as the custom cage"
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_diagnose_cage_check(bpy.types.Operator):
    bl_idname = "master_baker.diagnose_cage_check"
    bl_label = "Diagnose Cage Check"
    bl_description = "Copy detailed Cage Check and viewport-overlay diagnostics to the clipboard"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        settings = getattr(context.scene, "fyr_baker_settings", None)
        if settings is None:
            self.report({"ERROR"}, "Fyr Baker settings are unavailable on the active scene")
            return {"CANCELLED"}

        from . import overlay_cage_check_gpu

        overlay_state = properties.overlay_settings_state(settings)
        debug_result = runtime.peek_debug_overlay_result(context.scene, project, group)
        input_signature = export.debug_overlay_input_signature(project, group)
        signature_match = runtime.debug_overlay_result_matches_input_signature(
            context.scene,
            project,
            group,
            input_signature,
        )
        diag = overlay_cage_check_gpu.diagnose_cage_check_overlay(context, settings, project, group)
        overlay_gpu_diag = overlays.overlay_gpu_diagnostics() if hasattr(overlays, "overlay_gpu_diagnostics") else {}
        log_path = runtime.project_backend_log_path(project, prefer_live=True, scene=context.scene)
        lines = [
            "Fyr Baker Cage Check Diagnostics",
            f"project={getattr(project, 'name', '')}",
            f"group={getattr(group, 'name', '')}",
            f"cage_mode={getattr(group, 'cage_mode', '')}",
            f"average_normals={getattr(group, 'average_normals', False)}",
            f"cage_offset={getattr(group, 'cage_offset', 0.0)}",
            f"custom_cage={getattr(group, 'custom_cage', None)}",
            f"show_error_heatmap={getattr(overlay_state, 'show_error_heatmap', False)}",
            f"heatmap_inside_color={getattr(overlay_state, 'heatmap_inside_color', None)}",
            f"heatmap_outside_color={getattr(overlay_state, 'heatmap_outside_color', None)}",
            f"debug_result={debug_result}",
            f"input_signature={input_signature}",
            f"signature_match={signature_match}",
            f"overlay_gpu_diag={overlay_gpu_diag}",
            f"log_path={log_path}",
        ]
        diag_text = "\n".join(str(line) for line in lines)
        context.window_manager.clipboard = diag_text
        self.report({"INFO"}, "Cage Check diagnostics copied to clipboard")
        return {"FINISHED"}


class MASTER_BAKER_OT_create_custom_cage_from_low(bpy.types.Operator):
    bl_idname = "master_baker.create_custom_cage_from_low"
    bl_label = "Create Custom Cage from Low"
    bl_description = "Create an editable custom cage from the low-poly mesh using the current cage settings"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        source_mode = str(getattr(group, "cage_mode", "") or "")
        if source_mode not in {constants.CAGE_MODE_DISTANCE, constants.CAGE_MODE_AUTOMATIC, constants.CAGE_MODE_AUTO}:
            self.report({"ERROR"}, "This action only applies to Distance Based or Automatic mode")
            return {"CANCELLED"}

        low_slots = [slot for slot in getattr(group, "low_meshes", []) if getattr(slot, "object_ref", None) is not None]
        if not low_slots:
            self.report({"ERROR"}, "Assign a low mesh to the active bake group first")
            return {"CANCELLED"}

        depsgraph = context.evaluated_depsgraph_get()
        auto_cage_triangles = []
        for slot in low_slots:
            source_object = slot.object_ref
            total_offset = max(0.0, float(group.cage_offset) + float(getattr(slot, "cage_offset_delta", 0.0)))
            source_triangles = cage.capture_cage_source_triangles(
                source_object,
                depsgraph,
                smooth_normals=cage.auto_cage_uses_average_normals(group),
                uv_layer_name=(getattr(group, "uv_layer_name", "") or "").strip() or None,
            )
            auto_cage_triangles.extend(
                cage.offset_triangles_with_local_inflation(
                    source_triangles,
                    offset=total_offset,
                )
            )

        object_name = f"{group.name}_cage" if len(low_slots) > 1 else f"{low_slots[0].object_ref.name}_cage"
        previous_cage = getattr(group, "custom_cage", None)
        try:
            cage_object = _create_generated_cage_from_triangles(
                context,
                auto_cage_triangles,
                object_name=object_name,
                group_name=group.name,
                # The group's Fyr Cage collection, else next to the low mesh in the
                # artist's own collection ("Use My Collections" has no Cage collection).
                target_collection=project_structure.generated_cage_target_collection(
                    group, low_slots[0].object_ref
                ),
            )
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        group.custom_cage = cage_object
        group.cage_mode = constants.CAGE_MODE_CUSTOM
        _cleanup_generated_cage_object(previous_cage)

        # Not select_all: it only polls in Object Mode, and raising here after the
        # cage exists left the group half-converted when the button was pressed
        # from Edit Mode (2026-09-06).
        _select_objects_in_view_layer(context, [cage_object], active_object=cage_object)

        if source_mode in {constants.CAGE_MODE_AUTOMATIC, constants.CAGE_MODE_AUTO}:
            message = f"Converted Auto Cage to custom cage '{cage_object.name}'"
        else:
            message = f"Converted Distance Based cage to custom cage '{cage_object.name}'"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_auto_fit_cage(bpy.types.Operator):
    bl_idname = "master_baker.auto_fit_cage"
    bl_label = "Auto-Fit Cage"
    bl_description = (
        "Create a tight, editable cage by fitting each low-poly vertex to the nearest high-poly surface"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Auto-Fit Cage only applies to Distance Based mode")
            return {"CANCELLED"}

        low_slots = [slot for slot in getattr(group, "low_meshes", []) if getattr(slot, "object_ref", None) is not None]
        if not low_slots:
            self.report({"ERROR"}, "Assign a low mesh to the active bake group first")
            return {"CANCELLED"}

        high_meshes = properties.effective_high_mesh_objects(group)
        if not high_meshes:
            self.report({"ERROR"}, "Assign at least one high mesh to the active bake group first")
            return {"CANCELLED"}

        depsgraph = context.evaluated_depsgraph_get()
        high_source_data = []
        high_object_names = []
        for obj in high_meshes:
            captured = cage.capture_high_mesh_fit_source_data(obj, depsgraph)
            if captured is not None:
                high_source_data.append(captured)
                high_object_names.append(str(getattr(obj, "name", "")))
        if not high_source_data:
            self.report({"ERROR"}, "Could not build a proximity structure from the high meshes")
            return {"CANCELLED"}

        # Fit all of the group's low meshes together so no low mesh balloons out to reach another
        # mesh's high detail (e.g. the lower-teeth cage inflating up into the upper teeth).
        low_tri_groups = []
        for slot in low_slots:
            source_triangles = cage.capture_cage_source_triangles(
                slot.object_ref,
                depsgraph,
                smooth_normals=cage.auto_cage_uses_average_normals(group),
                uv_layer_name=(getattr(group, "uv_layer_name", "") or "").strip() or None,
            )
            if source_triangles:
                low_tri_groups.append(source_triangles)
        offsets = cage.build_group_coverage_offsets(
            low_tri_groups,
            high_source_data,
            high_object_names=high_object_names,
            match_by_isolation=bool(getattr(group, "match_by_isolation", False)),
            high_surface_index=cage.get_or_build_high_surface_index(high_meshes, depsgraph, retain=False),
        )
        fitted_triangles = []
        for source_triangles in low_tri_groups:
            fitted_triangles.extend(cage.offset_triangles_with_proximity_fit(source_triangles, offsets))

        object_name = f"{group.name}_cage" if len(low_slots) > 1 else f"{low_slots[0].object_ref.name}_cage"
        previous_cage = getattr(group, "custom_cage", None)
        try:
            cage_object = _create_generated_cage_from_triangles(
                context,
                fitted_triangles,
                object_name=object_name,
                group_name=group.name,
                # The group's Fyr Cage collection, else next to the low mesh in the
                # artist's own collection ("Use My Collections" has no Cage collection).
                target_collection=project_structure.generated_cage_target_collection(
                    group, low_slots[0].object_ref
                ),
            )
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        group.custom_cage = cage_object
        group.cage_mode = constants.CAGE_MODE_CUSTOM
        _cleanup_generated_cage_object(previous_cage)

        # Not select_all: it only polls in Object Mode, and raising here after the
        # cage exists left the group half-converted when the button was pressed
        # from Edit Mode (2026-09-06).
        _select_objects_in_view_layer(context, [cage_object], active_object=cage_object)

        message = f"Auto-fitted cage created for '{group.name}'"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_estimate_scoped_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.estimate_scoped_cage_offset"
    bl_label = "Estimate Cage Offset"
    bl_description = (
        "Fit the Distance Based cage offset from the distance between the low- and high-poly "
        "surfaces, for what Apply To covers (each selected mesh, or each bake group in scope)"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group, slot, scope, pairs = properties.cage_offset_scope_from_context(context)
        if project is None or group is None or not pairs:
            self.report({"ERROR"}, "Estimate Offset needs a Distance Based bake group with a low mesh")
            return {"CANCELLED"}
        depsgraph = context.evaluated_depsgraph_get()
        per_pair = {}
        if scope == constants.CAGE_SCOPE_SELECTED:
            for index, (pair_group, pair_slot) in enumerate(pairs):
                delta = _estimate_low_slot_offset_delta(pair_group, pair_slot, depsgraph=depsgraph)
                if delta is not None:
                    per_pair[index] = float(getattr(pair_group, "cage_offset", 0.0) or 0.0) + float(delta)
        else:
            group_estimates = []
            for index, (pair_group, _pair_slot) in enumerate(pairs):
                cached = next((value for owner, value in group_estimates if owner == pair_group), None)
                if cached is None and not any(owner == pair_group for owner, _value in group_estimates):
                    cached = _estimate_group_cage_offset(pair_group, depsgraph=depsgraph)
                    group_estimates.append((pair_group, cached))
                if cached is not None:
                    per_pair[index] = float(cached)
        if not per_pair:
            self.report({"ERROR"}, "Assign low and high meshes to estimate an offset")
            return {"CANCELLED"}
        pairs = [pair for index, pair in enumerate(pairs) if index in per_pair]
        per_pair = {new_index: per_pair[old_index] for new_index, old_index in enumerate(sorted(per_pair))}
        properties.focus_cage_offset_target(project, group, slot)
        properties.apply_scoped_cage_offset(project, group, pairs, scope, per_pair[0], per_pair=per_pair)
        message = f"Estimated cage offset for {len(pairs)} low mesh{'es' if len(pairs) != 1 else ''}"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_scoped_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.reset_scoped_cage_offset"
    bl_label = "Reset Cage Offset"
    bl_description = "Reset the Distance Based cage offset of what Apply To covers to the default"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group, slot, scope, pairs = properties.cage_offset_scope_from_context(context)
        if project is None or group is None or not pairs:
            self.report({"ERROR"}, "Reset Offset needs a Distance Based bake group with a low mesh")
            return {"CANCELLED"}
        properties.focus_cage_offset_target(project, group, slot)
        properties.apply_scoped_cage_offset(project, group, pairs, scope, float(constants.DEFAULT_CAGE_OFFSET))
        message = f"Reset cage offset for {len(pairs)} low mesh{'es' if len(pairs) != 1 else ''}"
        _sync_tag_status(context, message)
        self.report({"INFO"}, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_rear_distance(bpy.types.Operator):
    bl_idname = "master_baker.reset_rear_distance"
    bl_label = "Reset Rear Distance"
    bl_description = "Reset Rear Distance to 0 (Auto): as deep as the cage reaches out, at least 5% of the low-poly mesh's size"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = properties.get_active_project(context.scene)
        group = properties.get_active_group(project) if project is not None else None
        if group is None:
            self.report({"ERROR"}, "Reset Rear Distance needs an active bake group")
            return {"CANCELLED"}
        # The property's update propagates the value across the Apply To scope.
        group.projection_rear_distance = 0.0
        return {"FINISHED"}


class MASTER_BAKER_OT_estimate_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.estimate_cage_offset"
    bl_label = "Estimate Cage Offset"
    bl_description = "Estimate a starting Distance Based cage offset from the distance between the low- and high-poly surfaces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Estimate Offset only applies to Distance Based mode")
            return {"CANCELLED"}

        estimate = _estimate_auto_cage_offset(group, depsgraph=context.evaluated_depsgraph_get())
        if estimate is None:
            self.report({"ERROR"}, "Assign one low mesh and at least one high mesh to estimate an offset")
            return {"CANCELLED"}

        _apply_cage_offset_change(
            context,
            group,
            estimate,
            status_message=f"Estimated cage offset for {group.name}",
        )
        self.report({"INFO"}, f"Estimated cage offset: {group.cage_offset:.4f}")
        return {"FINISHED"}


class MASTER_BAKER_OT_adjust_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.adjust_cage_offset"
    bl_label = "Adjust Bake Group Cage Offset"
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.FloatProperty(
        name="Delta",
        default=0.005,
        precision=4,
        options={"HIDDEN"},
    )

    @classmethod
    def description(cls, _context, properties):
        delta = float(getattr(properties, "delta", 0.0))
        action = "Inflate" if delta >= 0.0 else "Relax"
        return f"{action} the active bake group's Distance Based cage offset by {abs(delta):.4f}"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Offset adjustments only apply to Distance Based mode")
            return {"CANCELLED"}

        new_offset = max(0.0, float(getattr(group, "cage_offset", 0.0)) + float(self.delta))
        action = "Inflated" if self.delta >= 0.0 else "Relaxed"
        _apply_cage_offset_change(
            context,
            group,
            new_offset,
            status_message=f"{action} cage offset for {group.name}",
        )
        self.report({"INFO"}, f"{action} cage offset to {group.cage_offset:.4f}")
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.reset_cage_offset"
    bl_label = "Reset Bake Group Cage Offset"
    bl_description = "Reset the active bake group's Distance Based cage offset to the default value"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Reset Offset only applies to Distance Based mode")
            return {"CANCELLED"}

        _apply_cage_offset_change(
            context,
            group,
            float(constants.DEFAULT_CAGE_OFFSET),
            status_message=f"Reset cage offset for {group.name}",
        )
        self.report({"INFO"}, f"Reset cage offset to {group.cage_offset:.4f}")
        return {"FINISHED"}


class MASTER_BAKER_OT_estimate_selected_group_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.estimate_selected_group_cage_offset"
    bl_label = "Estimate Selected Base Offset"
    bl_description = "Estimate a Distance Based cage offset for each bake group containing a selected low-poly mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Estimate Selected Base only applies to Distance Based mode")
            return {"CANCELLED"}

        target_groups = _selected_low_target_groups_or_report(self, context)
        if not target_groups:
            return {"CANCELLED"}

        updated_count = 0
        depsgraph = context.evaluated_depsgraph_get()
        for target_group in target_groups:
            estimate = _estimate_auto_cage_offset(target_group, depsgraph=depsgraph)
            if estimate is None:
                continue
            target_group.cage_offset = max(0.0, float(estimate))
            updated_count += 1

        if updated_count <= 0:
            self.report({"ERROR"}, "Assign at least one low mesh and one high mesh to each selected bake group before estimating")
            return {"CANCELLED"}

        plural = "group" if updated_count == 1 else "groups"
        message = f"Estimated base offsets for {updated_count} selected bake {plural}"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_selected_group_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.reset_selected_group_cage_offset"
    bl_label = "Reset Selected Base Offset"
    bl_description = "Reset the Distance Based cage offset for each bake group containing a selected low-poly mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Reset Selected Base only applies to Distance Based mode")
            return {"CANCELLED"}

        target_groups = _selected_low_target_groups_or_report(self, context)
        if not target_groups:
            return {"CANCELLED"}

        for target_group in target_groups:
            target_group.cage_offset = float(constants.DEFAULT_CAGE_OFFSET)

        plural = "group" if len(target_groups) == 1 else "groups"
        message = f"Reset base offsets for {len(target_groups)} selected bake {plural}"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Paint Offset / Paint Skew helpers
# ---------------------------------------------------------------------------

def _pack_paint_image(image) -> None:
    """Store the paint image's pixels inside the .blend so they survive reload."""
    if image is None:
        return
    try:
        image.pack()
    except Exception:
        pass


#: Name of the throwaway object the Texture Paint sessions of older versions painted
#: (a joined copy of the group's lows). Files saved mid-session can still carry one;
#: it is swept on load and when a paint session opens.
PAINT_PROXY_NAME = "_FYR_PAINT_TARGET"
#: Custom property on the proxy naming the meshes it stands in for, so exiting can
#: put their visibility back without keeping state in a module global (which would
#: not survive an addon reload, and would strand the originals hidden).
PAINT_PROXY_HIDDEN_KEY = "fyr_paint_hidden"


def find_paint_proxy():
    """The live paint proxy object, or None."""
    return bpy.data.objects.get(PAINT_PROXY_NAME)


def _remove_paint_proxy(context) -> bool:
    """Delete the paint proxy and unhide whatever it stood in for. Idempotent."""
    proxy = find_paint_proxy()
    if proxy is None:
        return False
    scene = getattr(context, "scene", None)
    scene_objects = getattr(scene, "objects", None) if scene is not None else None
    for name in list(proxy.get(PAINT_PROXY_HIDDEN_KEY, []) or []):
        obj = scene_objects.get(str(name)) if scene_objects is not None else None
        if obj is None:
            obj = bpy.data.objects.get(str(name))
        if obj is not None:
            try:
                obj.hide_set(False)
            except Exception:
                pass
    mesh = getattr(proxy, "data", None)
    try:
        bpy.data.objects.remove(proxy)
    except Exception:
        return False
    if mesh is not None and getattr(mesh, "users", 1) == 0:
        try:
            bpy.data.meshes.remove(mesh)
        except Exception:
            pass
    return True


def _find_view3d_area_region(context):
    """Return (area, region) for the first VIEW_3D in the current screen, or (None, None)."""
    candidate = getattr(context, "area", None)
    if candidate is not None and candidate.type == "VIEW_3D":
        region = next((r for r in candidate.regions if r.type == "WINDOW"), None)
        if region is not None:
            return candidate, region
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is not None:
                return area, region
    return None, None


def _exit_texture_paint_mode_if_active(context) -> None:
    """If the active object is in Texture Paint mode, return it to Object mode."""
    active_obj = getattr(context.view_layer.objects, "active", None) if hasattr(context, "view_layer") else None
    if active_obj is None:
        active_obj = getattr(context, "active_object", None)
    if active_obj is None or getattr(active_obj, "mode", "") != "TEXTURE_PAINT":
        return
    # Captured before the mode change clears it: only a SKEW session has a field to
    # rebuild, and an offset exit must not pay for one.
    exiting_canvas = getattr(
        getattr(getattr(context, "scene", None), "tool_settings", None), "image_paint", None
    )
    exiting_canvas = getattr(exiting_canvas, "canvas", None)
    view3d_area, view3d_region = _find_view3d_area_region(context)
    if view3d_area is not None:
        try:
            with context.temp_override(area=view3d_area, region=view3d_region):
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    else:
        # No 3D viewport on this screen: still put back everything below, or the
        # proxy, the hidden originals and the isolation snapshot were left behind.
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    _pack_paint_image(exiting_canvas)
    _restore_paint_tool_state(context)
    _restore_paint_isolation(context)
    _restore_paint_overlay_flags(context)
    # Only once the mode is left: removing the active object mid-mode is what
    # leaves Blender holding a freed pointer.
    _remove_paint_proxy(context)
    if exiting_canvas is not None:
        _settings, _project, exited_group = cage_session.resolve_project_group(
            getattr(context, "scene", None)
        )
        if exited_group is not None:
            paint_state = properties.group_paint_projection_settings_state(exited_group)
            if getattr(paint_state, "paint_skew_image", None) is exiting_canvas:
                overlays.bump_skew_paint_version()


#: Scene property holding the tool state a paint session overrode, so a reload
#: mid-session can still put it back (module globals would not survive one).
PAINT_TOOL_STATE_KEY = "fyr_paint_tool_state"


def _restore_paint_tool_state(context) -> None:
    """Undo what _enter_texture_paint_mode forced on the shared tool settings.

    Brushes are shared datablocks: without this one Paint Skew session left the
    artist's own texture-paint brush permanently desaturated and backface
    culling off.
    """
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    raw = scene.get(PAINT_TOOL_STATE_KEY)
    if not raw:
        return
    try:
        del scene[PAINT_TOOL_STATE_KEY]
    except Exception:
        pass
    try:
        state = json.loads(str(raw))
    except Exception:
        return
    paint = getattr(getattr(scene, "tool_settings", None), "image_paint", None)
    if paint is None:
        return
    for name in ("use_normal_falloff", "use_occlude", "use_backface_culling"):
        if name in state and hasattr(paint, name):
            try:
                setattr(paint, name, bool(state[name]))
            except Exception:
                pass
    try:
        if state.get("mode"):
            paint.mode = state["mode"]
    except Exception:
        pass
    try:
        paint.canvas = bpy.data.images.get(state.get("canvas") or "") if state.get("canvas") else None
    except Exception:
        pass
    brush = bpy.data.brushes.get(state.get("brush") or "") if state.get("brush") else getattr(paint, "brush", None)
    if brush is not None:
        for name in ("color", "secondary_color"):
            values = state.get(name) or []
            if len(values) == 3 and hasattr(brush, name):
                try:
                    setattr(brush, name, tuple(values))
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Undo / redo across a paint session
# ---------------------------------------------------------------------------
#
# Entering Paint Offset / Paint Skew creates an image datablock, builds the joined
# paint proxy, hides the originals and switches the viewport into Texture Paint.
# None of that carries its own undo step any more (see the operators' bl_options),
# but the next memfile step still snapshots the result, so undo and redo can land
# in a state Blender half-remembers: the proxy back in the scene with nobody
# painting it, the originals hidden with nothing to unhide them, or the active
# object still in Texture Paint on a proxy whose canvas is no longer one of ours.
# Every undo/redo therefore drops the overlay display cache (it holds GPU textures
# snapshotted from images the step may have freed) and repairs the session state.

#: Decisions of ``classify_paint_session_after_undo``.
PAINT_UNDO_KEEP = "keep"
PAINT_UNDO_EXIT = "exit"
PAINT_UNDO_DROP_PROXY = "drop_proxy"


def classify_paint_session_after_undo(
    *, proxy_exists: bool, active_is_proxy: bool, active_in_paint: bool, canvas_is_ours: bool
) -> str:
    """What to do with the paint session after an undo or redo step.

    - The proxy being painted with one of the group's masks is a live session: keep.
    - The proxy being painted with anything else is a torn session: leave Texture
      Paint, then remove the proxy (never the other way round; removing the active
      object mid-mode is what leaves Blender holding a freed pointer).
    - A proxy nobody is painting is debris: remove it and unhide the originals.
    - A session on a plain low mesh, or an artist's own Texture Paint session, is
      never touched: Blender reverts its mode and canvas consistently by itself.
    """
    if active_in_paint and active_is_proxy:
        return PAINT_UNDO_KEEP if canvas_is_ours else PAINT_UNDO_EXIT
    if proxy_exists:
        return PAINT_UNDO_DROP_PROXY
    return PAINT_UNDO_KEEP


def _group_paint_images(settings):
    """Every Paint Offset / Paint Skew image any bake group currently references."""
    images = []
    for project in getattr(settings, "projects", None) or []:
        for group in getattr(project, "groups", None) or []:
            try:
                paint_state = properties.group_paint_projection_settings_state(group)
            except Exception:
                paint_state = group
            for attr in ("paint_offset_image", "paint_skew_image"):
                image = getattr(paint_state, attr, None)
                if image is not None:
                    images.append(image)
    return images


def reconcile_paint_session_after_undo(context) -> str:
    """Repair whatever an undo or redo step left of a paint session. Returns the decision."""
    proxy = find_paint_proxy()
    view_layer = getattr(context, "view_layer", None)
    active = getattr(getattr(view_layer, "objects", None), "active", None)
    active_in_paint = active is not None and getattr(active, "mode", "") == "TEXTURE_PAINT"
    scene = getattr(context, "scene", None)
    image_paint = getattr(getattr(scene, "tool_settings", None), "image_paint", None)
    canvas = getattr(image_paint, "canvas", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    canvas_is_ours = canvas is not None and any(canvas is image for image in _group_paint_images(settings))

    decision = classify_paint_session_after_undo(
        proxy_exists=proxy is not None,
        active_is_proxy=proxy is not None and active is proxy,
        active_in_paint=active_in_paint,
        canvas_is_ours=canvas_is_ours,
    )
    if decision == PAINT_UNDO_EXIT:
        _exit_texture_paint_mode_if_active(context)
        if getattr(active, "mode", "") == "TEXTURE_PAINT":
            # No 3D viewport to leave the mode through; the proxy must stay until
            # there is one. The next undo/redo or file load retries.
            return decision
        _remove_paint_proxy(context)
    elif decision == PAINT_UNDO_DROP_PROXY:
        _remove_paint_proxy(context)
    if decision != PAINT_UNDO_KEEP:
        _restore_paint_overlay_flags(context)
        overlays.bump_skew_paint_version()
        overlays.invalidate_overlay_cache(clear_static=True)
        overlays.tag_redraw_all_view3d(scene=scene, sync_preview=False)
    return decision


def _reconcile_paint_session_timer():
    """One-shot timer: run the reconcile with a window so mode_set has a viewport."""
    context = getattr(bpy, "context", None)
    if context is None:
        return None
    window = getattr(context, "window", None)
    if window is None:
        windows = getattr(getattr(context, "window_manager", None), "windows", None) or []
        window = next(iter(windows), None)
    try:
        if window is None or not hasattr(context, "temp_override"):
            reconcile_paint_session_after_undo(context)
            return None
        overrides = {"window": window}
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", None) or []:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is not None:
                overrides.update(area=area, region=region)
                break
        with context.temp_override(**overrides):
            reconcile_paint_session_after_undo(bpy.context)
    except Exception:
        pass
    return None


def _schedule_paint_session_reconcile() -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    try:
        if hasattr(timers, "is_registered") and timers.is_registered(_reconcile_paint_session_timer):
            return
        timers.register(_reconcile_paint_session_timer, first_interval=0.0)
    except Exception:
        pass


def handle_undo_or_redo_post() -> None:
    """Shared body of the undo_post / redo_post handlers.

    The cache drop happens here, before the next redraw can sample a texture the
    step freed. The session repair needs a window (mode_set runs as an operator),
    which handlers are not guaranteed, so it runs from a one-shot timer.
    """
    try:
        overlays.invalidate_overlay_cache(clear_static=False)
    except Exception:
        pass
    _schedule_paint_session_reconcile()


def _toggle_paint_brush(operator, context, kind: str) -> set[str]:
    """Enter or leave the Paint Offset / Paint Skew brush on the active bake group."""
    project, group = _cage_target_project_group_or_report(operator, context)
    if project is None or group is None:
        return {"CANCELLED"}
    # A Texture Paint session saved by an older version (proxy, hidden originals) is
    # closed first so the brush never paints under it.
    _exit_texture_paint_mode_if_active(context)
    if find_paint_proxy() is not None:
        _remove_paint_proxy(context)
    if paint_brush.session_owns(group, kind):
        paint_brush.end_session(context)
        return {"FINISHED"}
    ok, message = paint_brush.start_session(context, project, group, kind)
    if not ok:
        operator.report({"ERROR"}, message)
        return {"CANCELLED"}
    operator.report({"INFO"}, message)
    return {"FINISHED"}


class MASTER_BAKER_OT_create_paint_offset_image(bpy.types.Operator):
    bl_idname = "master_baker.create_paint_offset_image"
    bl_label = "Paint Offset"
    bl_description = (
        "Paint where the cage sits on the low meshes of this bake group. Add pushes the "
        "cage out, Ctrl pulls it in, Shift smooths. Press again to stop"
    )
    # No UNDO here: the layer it may create is part of the first stroke's undo step, and
    # a memfile step over a tool switch only restores a half-remembered session.
    bl_options = {"REGISTER"}

    def execute(self, context):
        return _toggle_paint_brush(self, context, paint_brush.KIND_OFFSET)


class MASTER_BAKER_OT_create_paint_skew_image(bpy.types.Operator):
    bl_idname = "master_baker.create_paint_skew_image"
    bl_label = "Paint Skew"
    bl_description = (
        "Paint where bake rays straighten out on this bake group: painted areas fire rays "
        "straight off the low-poly faces. The needles show the ray direction. Press again to stop"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        return _toggle_paint_brush(self, context, paint_brush.KIND_SKEW)


#: Scene flag marking the isolation snapshot as belonging to a paint session, so
#: leaving the session restores it without disturbing an isolation the artist set up
#: independently through the bake-group isolate button.
PAINT_ISOLATE_KEY = "_fyr_paint_isolated"


def _paint_isolation_targets(context) -> list:
    """The meshes the live paint session paints (every low of the group)."""
    session = paint_brush.active_session()
    if session is None:
        return []
    targets = []
    for entry in session.entries:
        obj = bpy.data.objects.get(entry.name)
        if obj is not None:
            targets.append(obj)
    return targets


def _restore_paint_isolation(context) -> None:
    """Undo a paint-session isolation, if this session is the one that set it."""
    scene = getattr(context, "scene", None)
    if scene is None or not scene.get(PAINT_ISOLATE_KEY):
        return
    try:
        _restore_isolation_state(scene)
    except Exception:
        pass
    try:
        del scene[PAINT_ISOLATE_KEY]
    except Exception:
        pass


#: Scene flag holding the overlay toggles a paint session switched on, so leaving the
#: session puts the viewport back the way the artist had it (entering Paint Offset
#: turned the cage on and it stayed on after exit, even if it was off before).
PAINT_OVERLAY_RESTORE_KEY = "_fyr_paint_overlay_restore"


def _restore_paint_overlay_flags(context) -> None:
    """Undo the overlay toggles a paint session flipped. Idempotent."""
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    try:
        restore = scene.get(PAINT_OVERLAY_RESTORE_KEY)
    except Exception:
        return
    if restore is None:
        return
    try:
        restore = dict(restore)
    except Exception:
        restore = {}
    try:
        del scene[PAINT_OVERLAY_RESTORE_KEY]
    except Exception:
        pass
    overlay_state = _overlay_settings_state(getattr(scene, "fyr_baker_settings", None))
    if overlay_state is None:
        return
    for name, previous in restore.items():
        if not hasattr(overlay_state, name):
            continue
        # Only while it still reads the session's value: a change the artist made
        # during the session is their own choice and stays.
        if bool(getattr(overlay_state, name, False)) == bool(previous):
            continue
        try:
            setattr(overlay_state, name, bool(previous))
        except Exception:
            pass
    overlays.invalidate_overlay_cache(clear_static=True)


class MASTER_BAKER_OT_toggle_paint_isolate(bpy.types.Operator):
    bl_idname = "master_baker.toggle_paint_isolate"
    bl_label = "Isolate Painted Mesh"
    bl_description = (
        "Hide everything except the mesh being painted, or restore the previous "
        "viewport visibility. Surrounding geometry usually buries the surface you are "
        "painting on"
    )
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    @classmethod
    def poll(cls, context):
        return bool(_paint_isolation_targets(context)) or bool(getattr(context.scene, "get", lambda _k: None)(PAINT_ISOLATE_KEY))

    def execute(self, context):
        targets = _paint_isolation_targets(context)
        scene = context.scene
        if not targets and not scene.get(PAINT_ISOLATE_KEY):
            self.report({"ERROR"}, "Open Paint Offset or Paint Skew first")
            return {"CANCELLED"}

        isolation_result = _toggle_isolation_targets(scene, targets)
        if isolation_result is None:
            self.report({"ERROR"}, "Nothing to isolate")
            return {"CANCELLED"}
        if isolation_result:
            scene[PAINT_ISOLATE_KEY] = True
            self.report({"INFO"}, "Isolated the painted mesh")
        else:
            try:
                del scene[PAINT_ISOLATE_KEY]
            except Exception:
                pass
            self.report({"INFO"}, "Restored viewport visibility")
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_paint_image(bpy.types.Operator):
    bl_idname = "master_baker.clear_paint_image"
    bl_label = "Clear Paint"
    bl_description = (
        "Clear the painted values on every low mesh in this bake group. An old paint image "
        "is detached and stays in the blend file"
    )
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.StringProperty(name="Target", default="OFFSET")  # "OFFSET" | "SKEW"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        _exit_texture_paint_mode_if_active(context)
        kind = paint_brush.KIND_OFFSET if self.target == "OFFSET" else paint_brush.KIND_SKEW
        live = paint_brush.session_owns(group, kind)
        if live:
            paint_brush.end_session(context)
        paint_brush.clear_group_layer(group, kind)
        prop = "paint_offset_image" if self.target == "OFFSET" else "paint_skew_image"
        setattr(group, prop, None)
        if self.target == "OFFSET":
            group.paint_offset_scale = constants.DEFAULT_PAINT_OFFSET_SCALE
        else:
            group.paint_skew = constants.DEFAULT_PAINT_SKEW
        overlays.invalidate_overlay_cache(clear_static=True)
        overlays.tag_redraw_all_view3d(scene=context.scene, sync_preview=False)
        if live:
            paint_brush.start_session(context, project, group, kind)
        return {"FINISHED"}


class MASTER_BAKER_OT_estimate_object_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.estimate_object_cage_offset"
    bl_label = "Estimate Per-Mesh Cage Offset"
    bl_description = "Estimate an additional cage offset for the active low-poly mesh from the surrounding high-poly meshes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Estimate Per-Mesh Offset only applies to Distance Based mode")
            return {"CANCELLED"}

        slot = _active_low_mesh_slot(group)
        active_low_mesh = getattr(slot, "object_ref", None) if slot is not None else None
        if active_low_mesh is None:
            self.report({"ERROR"}, "Select a low mesh in this bake group to estimate its per-mesh offset")
            return {"CANCELLED"}

        estimate_delta = _estimate_active_low_object_offset_delta(group, depsgraph=context.evaluated_depsgraph_get())
        if estimate_delta is None:
            self.report({"ERROR"}, "Assign one low mesh and at least one high mesh to estimate a per-mesh offset")
            return {"CANCELLED"}

        _apply_object_cage_offset_change(
            context,
            slot,
            estimate_delta,
            status_message=f"Estimated per-mesh offset for {active_low_mesh.name}",
        )
        final_offset = max(0.0, float(getattr(group, "cage_offset", 0.0)) + float(slot.cage_offset_delta))
        self.report({"INFO"}, f"Estimated per-mesh offset: {slot.cage_offset_delta:.4f} (final {final_offset:.4f})")
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_object_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.reset_object_cage_offset"
    bl_label = "Reset Per-Mesh Cage Offset"
    bl_description = "Reset the active low-poly mesh's additional cage offset to zero"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Reset Per-Mesh Offset only applies to Distance Based mode")
            return {"CANCELLED"}

        slot = _active_low_mesh_slot(group)
        active_low_mesh = getattr(slot, "object_ref", None) if slot is not None else None
        if active_low_mesh is None:
            self.report({"ERROR"}, "Select a low mesh in this bake group to reset its per-mesh offset")
            return {"CANCELLED"}

        _apply_object_cage_offset_change(
            context,
            slot,
            0.0,
            status_message=f"Reset per-mesh offset for {active_low_mesh.name}",
        )
        self.report({"INFO"}, f"Reset per-mesh offset for {active_low_mesh.name}")
        return {"FINISHED"}


class MASTER_BAKER_OT_estimate_selected_low_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.estimate_selected_low_cage_offset"
    bl_label = "Estimate Selected Per-Mesh Offsets"
    bl_description = "Estimate an additional cage offset for every selected low-poly mesh in the project"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Estimate Selected Offset only applies to Distance Based mode")
            return {"CANCELLED"}

        targets = _selected_low_slot_targets_or_report(self, context)
        if not targets:
            return {"CANCELLED"}

        updated_count = 0
        depsgraph = context.evaluated_depsgraph_get()
        for target in targets:
            estimate_delta = _estimate_low_slot_offset_delta(target.group, target.slot, depsgraph=depsgraph)
            if estimate_delta is None:
                continue
            target.slot.cage_offset_delta = float(estimate_delta)
            updated_count += 1

        if updated_count <= 0:
            self.report({"ERROR"}, "Assign at least one high mesh to each selected low mesh's bake group before estimating")
            return {"CANCELLED"}

        plural = "mesh" if updated_count == 1 else "meshes"
        message = f"Estimated per-mesh offsets for {updated_count} selected low {plural}"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_reset_selected_low_cage_offset(bpy.types.Operator):
    bl_idname = "master_baker.reset_selected_low_cage_offset"
    bl_label = "Reset Selected Per-Mesh Offsets"
    bl_description = "Reset the additional cage offset for every selected low-poly mesh in the project"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}
        if group.cage_mode != constants.CAGE_MODE_DISTANCE:
            self.report({"ERROR"}, "Reset Selected Per-Mesh Offsets only applies to Distance Based mode")
            return {"CANCELLED"}

        targets = _selected_low_slot_targets_or_report(self, context)
        if not targets:
            return {"CANCELLED"}

        for target in targets:
            target.slot.cage_offset_delta = 0.0

        plural = "mesh" if len(targets) == 1 else "meshes"
        message = f"Reset per-mesh offsets for {len(targets)} selected low {plural}"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_adjust_custom_cage_mesh(bpy.types.Operator):
    bl_idname = "master_baker.adjust_custom_cage_mesh"
    bl_label = "Adjust Custom Cage"
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.FloatProperty(name="Delta", default=0.005, precision=4, options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        delta = float(getattr(properties, "delta", 0.0))
        action = "Inflate" if delta >= 0.0 else "Relax"
        return f"{action} the custom cage mesh along its averaged vertex normals by {abs(delta):.4f}"

    def execute(self, context):
        project, group, cage_object = _custom_cage_object_or_report(self, context)
        if project is None or group is None or cage_object is None:
            return {"CANCELLED"}

        try:
            # Flush Edit Mode first: obj.data is stale there and writes through it
            # are discarded when Edit Mode ends, so the tool reported success and
            # the change vanished.
            with _object_mode_scope(context):
                positions, faces = _mesh_geometry_from_object(cage_object)
                updated_positions = cage.inflate_mesh_geometry(
                    positions, faces, _cage_object_local_delta(cage_object, float(self.delta))
                )
            action = "Inflated" if self.delta >= 0.0 else "Relaxed"
            _apply_custom_cage_mesh_positions(
                context,
                cage_object,
                updated_positions,
                status_message=f"{action} custom cage for {group.name}",
            )
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        action = "Inflated" if self.delta >= 0.0 else "Relaxed"
        self.report({"INFO"}, f"{action} custom cage '{cage_object.name}'")
        return {"FINISHED"}


class MASTER_BAKER_OT_smooth_custom_cage_mesh(bpy.types.Operator):
    bl_idname = "master_baker.smooth_custom_cage_mesh"
    bl_label = "Smooth Custom Cage"
    bl_description = "Smooth the custom cage mesh while preserving open boundaries"
    bl_options = {"REGISTER", "UNDO"}

    factor: bpy.props.FloatProperty(name="Factor", default=0.5, min=0.0, max=1.0, options={"HIDDEN"})
    iterations: bpy.props.IntProperty(name="Iterations", default=2, min=1, max=32, options={"HIDDEN"})

    def execute(self, context):
        project, group, cage_object = _custom_cage_object_or_report(self, context)
        if project is None or group is None or cage_object is None:
            return {"CANCELLED"}

        try:
            with _object_mode_scope(context):
                positions, faces = _mesh_geometry_from_object(cage_object)
                updated_positions = cage.smooth_mesh_geometry(
                    positions,
                    faces,
                    factor=float(self.factor),
                    iterations=int(self.iterations),
                    preserve_boundary=True,
                )
                _apply_custom_cage_mesh_positions(
                    context,
                    cage_object,
                    updated_positions,
                    status_message=f"Smoothed custom cage for {group.name}",
                )
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Smoothed custom cage '{cage_object.name}'")
        return {"FINISHED"}


class MASTER_BAKER_OT_cleanup_custom_cage_spikes(bpy.types.Operator):
    bl_idname = "master_baker.cleanup_custom_cage_spikes"
    bl_label = "Clean Custom Cage"
    bl_description = "Remove outlier spike vertices from the custom cage mesh"
    bl_options = {"REGISTER", "UNDO"}

    spike_ratio: bpy.props.FloatProperty(name="Spike Ratio", default=2.5, min=1.0, max=32.0, options={"HIDDEN"})
    blend: bpy.props.FloatProperty(name="Blend", default=0.85, min=0.0, max=1.0, options={"HIDDEN"})

    def execute(self, context):
        project, group, cage_object = _custom_cage_object_or_report(self, context)
        if project is None or group is None or cage_object is None:
            return {"CANCELLED"}

        try:
            with _object_mode_scope(context):
                positions, faces = _mesh_geometry_from_object(cage_object)
                updated_positions = cage.cleanup_spike_vertices(
                    positions,
                    faces,
                    spike_ratio=float(self.spike_ratio),
                    blend=float(self.blend),
                    preserve_boundary=True,
                )
                _apply_custom_cage_mesh_positions(
                    context,
                    cage_object,
                    updated_positions,
                    status_message=f"Cleaned custom cage for {group.name}",
                )
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Cleaned custom cage '{cage_object.name}'")
        return {"FINISHED"}


def _evict_object_from_other_groups(project, destination_group, obj) -> int:
    """Auto-Build is a move, not an add: a mesh renamed into another group used
    to stay a member of its old one as well (the 2026-08-19 "group #1 owns
    everything" bundles). Same sweep the suffix path performs."""
    evicted = 0
    for existing_group in getattr(project, "groups", []) or []:
        if existing_group is destination_group or str(getattr(existing_group, "name", "") or "") == str(
            getattr(destination_group, "name", "") or ""
        ):
            continue
        try:
            evicted += int(_discard_role_objects(existing_group, [obj]) or 0)
        except Exception:
            pass
    return evicted


class MASTER_BAKER_OT_auto_group_selected_by_suffix(bpy.types.Operator):
    bl_idname = "master_baker.auto_group_selected_by_suffix"
    bl_label = "Auto-Build Bake Groups by Suffix"
    bl_description = "Create bake groups by matching common Low/High, LP/HP, and Cage name suffixes on the selected meshes"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        if not _group_selected_meshes_by_suffix(
            self,
            context,
            status_message="Created or updated {count} bake group(s) from suffix matches",
        ):
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_auto_group_selected_by_collection(bpy.types.Operator):
    bl_idname = "master_baker.auto_group_selected_by_collection"
    bl_label = "Auto-Build Bake Groups by Collection"
    bl_description = "Create or update bake groups from the selected meshes based on their collections and tags"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"ERROR"}, "Select one or more mesh objects first")
            return {"CANCELLED"}

        project, _created_project = _ensure_active_project(context)
        created_count = 0
        for obj in selected_meshes:
            collection = _primary_collection_for_object(obj)
            group_name = matching.group_key_for_name(collection.name) if collection is not None else "Unassigned"
            group = _get_or_create_group(project, group_name)
            role = _role_from_object_and_collection(obj, collection)
            _evict_object_from_other_groups(project, group, obj)
            _ensure_group_slot(group, role, obj)
            _link_objects_to_group_role_collection(context, project, group, role, [obj])
            created_count += 1

        project.active_group_index = len(project.groups) - 1
        project.last_status_message = f"Created or updated {created_count} bake group object assignment(s) by collection"
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_auto_group_selected_by_name_group(bpy.types.Operator):
    bl_idname = "master_baker.auto_group_selected_by_name_group"
    bl_label = "Auto-Build Bake Groups by Name"
    bl_description = "Create or update bake groups from the selected meshes based on shared object names"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"ERROR"}, "Select one or more mesh objects first")
            return {"CANCELLED"}

        project, _created_project = _ensure_active_project(context)
        created_count = 0
        for obj in selected_meshes:
            group_name = _normalize_group_name(obj.name)
            group = _get_or_create_group(project, group_name)
            # The name is the authority here: a stale role tag from an earlier run
            # otherwise won over a renamed _low / _high suffix.
            try:
                tagging.clear_role_tag(obj)
            except Exception:
                pass
            role = _role_from_object_and_collection(obj)
            _evict_object_from_other_groups(project, group, obj)
            _ensure_group_slot(group, role, obj)
            _link_objects_to_group_role_collection(context, project, group, role, [obj])
            created_count += 1

        project.active_group_index = len(project.groups) - 1
        project.last_status_message = f"Created or updated {created_count} bake group object assignment(s) by name"
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class _WaitCursorBuildMixin:
    """Wait cursor + status line around a blocking scene-wide build (see invoke)."""

    # Scanning a whole scene of high-poly meshes takes long enough to look like a
    # freeze. invoke() paints a "please wait" cursor + status line and lets Blender
    # redraw once before the blocking build runs on the first timer tick, so the
    # user never mistakes the pause for a crash. Programmatic/EXEC calls (tests)
    # skip the modal and run execute() synchronously.
    _wait_timer = None
    _wait_ticks = 0

    _WAIT_MESSAGE = "Please wait..."

    def invoke(self, context, event):
        window = getattr(context, "window", None)
        if window is None:
            return self.execute(context)
        try:
            window.cursor_set("WAIT")
        except Exception:
            pass
        workspace = getattr(context, "workspace", None)
        if workspace is not None:
            try:
                workspace.status_text_set(self._WAIT_MESSAGE)
            except Exception:
                pass
        self._wait_ticks = 0
        wm = context.window_manager
        self._wait_timer = wm.event_timer_add(0.01, window=window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}
        # Skip the first tick so Blender gets a full redraw cycle to paint the
        # wait cursor and status text before we block the main thread.
        self._wait_ticks += 1
        if self._wait_ticks < 2:
            return {"RUNNING_MODAL"}
        try:
            return self.execute(context)
        finally:
            self._finish_wait(context)

    def cancel(self, context):
        # Blender cancels a modal operator without calling modal() on file load or
        # window close; release the timer, wait cursor, and status text here too.
        self._finish_wait(context)

    def _finish_wait(self, context):
        wm = getattr(context, "window_manager", None)
        if wm is not None and self._wait_timer is not None:
            try:
                wm.event_timer_remove(self._wait_timer)
            except Exception:
                pass
        self._wait_timer = None
        window = getattr(context, "window", None)
        if window is not None:
            try:
                window.cursor_set("DEFAULT")
            except Exception:
                pass
        workspace = getattr(context, "workspace", None)
        if workspace is not None:
            try:
                workspace.status_text_set(None)
            except Exception:
                pass


class MASTER_BAKER_OT_auto_group_scene_by_name(_WaitCursorBuildMixin, bpy.types.Operator):
    bl_idname = "master_baker.auto_group_scene_by_name"
    bl_label = "Auto-Build Bake Groups from Names"
    bl_description = (
        "Build bake groups from LP/HP, Low/High, and Cage name suffixes. With meshes "
        "selected, uses the selection and its hidden name partners; otherwise every mesh "
        "in the scene outside hidden collections. Meshes without a suffix are ignored"
    )
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    _WAIT_MESSAGE = "Building bake groups from names -- please wait..."

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        meshes, scope = _name_build_mesh_objects(context)
        if not _group_meshes_by_suffix(
            self,
            context,
            meshes,
            status_message="Built {count} bake group(s) from " + ("selected" if scope == "selected" else "scene") + " names",
            empty_error="No mesh objects in the scene",
            no_match_error="No meshes with LP/HP, Low/High, or Cage suffixes found in the " + scope,
            # Saying which pool was read is the difference between "you named these
            # wrong" and "these were lying around".
            scope_label=scope,
        ):
            return {"CANCELLED"}
        return {"FINISHED"}


def _evaluated_tri_count(obj, depsgraph) -> int:
    """Triangle count of the modifier-evaluated mesh.

    Evaluating matters: a high-poly is often "low mesh + Subdivision", so the
    base polygon count would look identical to its low-poly. loop_triangles also
    normalises ngons/quads to a comparable tri figure for the Low/High split.
    """
    eval_obj = obj.evaluated_get(depsgraph) if depsgraph is not None else obj
    mesh = None
    try:
        mesh = eval_obj.to_mesh()
    except Exception:
        mesh = None
    if mesh is None:
        data = getattr(obj, "data", None)
        return mesh_read.element_count(data, "polygons")
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        try:
            eval_obj.to_mesh_clear()
        except Exception:
            pass


def _proximity_prep_candidates(context):
    """Unlabeled meshes to prep: current selection if any, else the whole scene.

    Prep is a *naming* pass, so the mesh NAME is the source of truth. A mesh is left
    out only when its name already carries a Low/High/Cage role suffix, or it carries
    a *deliberate* role tag (manual / generated / grouping / scaffold). A tag that was
    auto-derived from a name suffix ("suffix" source) is ignored when the name has no
    suffix: such a tag is stale — e.g. left behind after a bake project was removed,
    since removal doesn't strip object tags — and refusing to re-prep would strand the
    meshes with the misleading "nothing to prep" report.
    """
    def _preppable(obj) -> bool:
        if matching.detect_role(getattr(obj, "name", "")) is not None:
            return False
        tag = tagging.read_role_tag(obj)
        if tag is not None and tag.get(tagging.SOURCE_KEY) != "suffix":
            return False
        return True

    selected = _selected_mesh_objects(context)
    pool = selected if selected else _scene_mesh_objects(context)
    candidates = [obj for obj in pool if _preppable(obj)]
    # Complete duplicate pairs from the whole scene: the high-poly partner is
    # typically HIDDEN while the artist works (and hidden objects can't even be
    # selected), so a selection-limited pool strands each low as a singleton and
    # shoves it into the proximity fallback — which then mis-pairs adjacent,
    # unrelated parts (observed live: four low parts of one head clustered into
    # a single group). A mesh sharing a candidate's base name is that
    # candidate's duplicate partner regardless of selection or visibility.
    if candidates:
        candidate_names = {getattr(obj, "name", "") for obj in candidates}
        candidate_bases = {proximity_matching.retain_base(getattr(obj, "name", "")) for obj in candidates}
        for obj in _scene_mesh_objects(context):
            name = getattr(obj, "name", "")
            if name in candidate_names:
                continue
            if proximity_matching.retain_base(name) not in candidate_bases:
                continue
            if _preppable(obj):
                candidates.append(obj)
    return candidates


class MASTER_BAKER_OT_prepare_lowhigh_names(bpy.types.Operator):
    bl_idname = "master_baker.prepare_lowhigh_names"
    bl_label = "Auto-Rename Meshes to _low/_high"
    bl_description = (
        "Rename matching meshes with _low and _high suffixes. Pairs .001 duplicates first, then "
        "overlapping meshes; the mesh with fewer polygons becomes the low-poly. Uses the selection, "
        "or the whole scene when nothing is selected. Does not create bake groups"
    )
    bl_options = {"REGISTER", "UNDO"}

    tolerance: bpy.props.FloatProperty(
        name="Proximity Slack",
        description="For meshes that don't share a base name: how far apart bounding "
        "boxes may be and still pair, as a fraction of each mesh's size",
        default=0.05,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    def execute(self, context):
        candidates = _proximity_prep_candidates(context)
        if not candidates:
            self.report({"ERROR"}, "No unlabeled meshes to prep (already suffixed, or none in scene)")
            return {"CANCELLED"}

        plan, renamed_objects = _apply_lowhigh_prep(context, candidates, float(self.tolerance))
        if not plan.renames:
            hint = "no low/high pairs found"
            if plan.skipped_ambiguous:
                hint = f"{len(plan.skipped_ambiguous)} pair(s) had poly counts too close to tell apart"
            self.report({"WARNING"}, f"Nothing renamed: {hint}")
            return {"CANCELLED"}

        skipped = len(plan.skipped_singletons) + len(plan.skipped_ambiguous)
        message = f"Prepped {plan.pair_count} pair(s), renamed {len(renamed_objects)} mesh(es)"
        # A leftover selection silently narrows the prep to one pair and reads
        # as "it ignored my scene" — say so when the selection set the scope.
        if _selected_mesh_objects(context):
            message += " from the selection"
        if skipped:
            message += f"; skipped {skipped} unpaired/ambiguous"
        message += " -- now run Auto-Build Bake Groups from Names"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


def _apply_lowhigh_prep(context, candidates, tolerance_ratio: float):
    """Pair `candidates` (.001 duplicates, then overlapping bounds) and stamp _low/_high.

    The fewer-polygon mesh of each pair becomes the low. Returns ``(plan, renamed)``:
    the proximity plan (for its skip counts) and the objects actually renamed.
    """
    depsgraph = context.evaluated_depsgraph_get()
    samples = []
    for obj in candidates:
        bounds = _world_bounds_for_objects([obj])
        if bounds is None:
            continue
        samples.append(
            proximity_matching.MeshSample(
                name=obj.name,
                tri_count=_evaluated_tri_count(obj, depsgraph),
                bounds_min=bounds[0],
                bounds_max=bounds[1],
            )
        )

    plan = proximity_matching.plan_lowhigh_prep(samples, tolerance_ratio=tolerance_ratio)
    objects = context.scene.objects
    renamed = []
    for entry in plan.renames:
        obj = objects.get(entry.object_name)
        if obj is None or obj.name == entry.new_name:
            continue
        # Drop any stale suffix-derived role tag so the fresh _low/_high name is the
        # single source of truth; a leftover HIGH/LOW tag from a removed project would
        # otherwise contradict the new suffix until Auto-Build from Names reruns.
        existing = tagging.read_role_tag(obj)
        if existing is not None and existing.get(tagging.SOURCE_KEY) == "suffix":
            tagging.clear_role_tag(obj)
        obj.name = entry.new_name  # Blender auto-suffixes .001 on collisions
        renamed.append(obj)
    return plan, renamed


class MASTER_BAKER_OT_auto_setup(_WaitCursorBuildMixin, bpy.types.Operator):
    bl_idname = "master_baker.auto_setup"
    bl_label = "Auto Setup"
    bl_description = (
        "Pair meshes without _low/_high names (.001 duplicates first, then overlapping "
        "bounds; fewer polygons becomes the low), rename them, and build bake groups. "
        "Uses the selection, or the whole scene when nothing is selected"
    )
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    tolerance: bpy.props.FloatProperty(
        name="Proximity Slack",
        description="For meshes that don't share a base name: how far apart bounding "
        "boxes may be and still pair, as a fraction of each mesh's size",
        default=0.05,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    _WAIT_MESSAGE = "Setting up bake groups -- please wait..."

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        # Read the scope before renaming: the prep may pull a hidden duplicate partner
        # in from outside the selection, and that partner must be grouped as well.
        selected = _selected_mesh_objects(context)
        candidates = _proximity_prep_candidates(context)
        renamed = []
        if candidates:
            _plan, renamed = _apply_lowhigh_prep(context, candidates, float(self.tolerance))
        if selected:
            pool = list(selected)
            pool_names = {obj.name for obj in pool}
            pool.extend(obj for obj in renamed if obj.name not in pool_names)
            scope_label = "selected"
        else:
            pool = _scene_mesh_objects(context)
            scope_label = "scene"
        built = "Renamed {} mesh(es), built".format(len(renamed)) if renamed else "Built"
        if not _group_meshes_by_suffix(
            self,
            context,
            pool,
            status_message=built + " {count} bake group(s)",
            empty_error="Select meshes, or deselect all to set up the whole scene",
            no_match_error=(
                "No low/high pairs found. Pairs need overlapping bounds, a .001 duplicate, "
                "or _low/_high names. Use Add as Low / Add as High instead"
            ),
            scope_label=scope_label,
        ):
            return {"CANCELLED"}
        return {"FINISHED"}


def _collection_parent_names(context) -> dict[str, str]:
    """Map every collection's name to its parent's name ("" at the scene root).

    Blender collections know their children, not their parent, so the tree is walked
    once from the scene root. The parent is what groups meshes into one bake set, so
    a selection spanning several assets renames each against its own base.
    """
    scene = getattr(context, "scene", None)
    root = getattr(scene, "collection", None) if scene is not None else None
    parents: dict[str, str] = {}
    if root is None:
        return parents
    stack = [(root, "")]
    seen: set[str] = set()
    while stack:
        collection, parent_name = stack.pop()
        name = str(getattr(collection, "name", "") or "")
        if name in seen:
            continue
        seen.add(name)
        parents[name] = parent_name
        for child in getattr(collection, "children", ()) or ():
            # Collections directly under the scene root take the root as their
            # parent, which is the right grouping for a one-asset file: "low" and
            # "high" hang off the root there and must resolve to a single set.
            stack.append((child, name))
    return parents


def _collection_naming_samples(context, meshes) -> list:
    parents = _collection_parent_names(context)
    samples = []
    for obj in meshes:
        collection_names = tuple(
            str(getattr(collection, "name", "") or "")
            for collection in (getattr(obj, "users_collection", ()) or ())
        )
        samples.append(
            collection_naming.CollectionMeshSample(
                name=str(getattr(obj, "name", "") or ""),
                collection_names=collection_names,
                parent_names=tuple(parents.get(name, "") for name in collection_names),
            )
        )
    return samples


def _random_base_name_factory(context, explicit: str, *, digits: int = 3):
    """Bases for `collection_naming.plan_collection_names`.

    An explicit base is used verbatim for the first set and suffixed for any further
    one. Otherwise each set gets a random fixed-width number, which is the point of
    the convention: the base carries no meaning, so it can never contradict a name
    the artist chose -- it only has to be unique. Uniqueness is tested against the
    whole scene, not the selection, so a rerun never lands on a live prefix.
    """
    taken = {str(getattr(obj, "name", "") or "") for obj in _scene_mesh_objects(context)}
    issued: list[str] = []

    def _free(candidate: str) -> bool:
        if candidate in issued:
            return False
        return not any(name.startswith(f"{candidate}_") for name in taken)

    def factory(index: int) -> str:
        if explicit:
            candidate = explicit if index == 0 else f"{explicit}{index + 1:02d}"
            issued.append(candidate)
            return candidate
        width = digits
        for attempt in range(4000):
            # Widen rather than spin forever once the namespace is genuinely full.
            if attempt and attempt % 1000 == 0:
                width += 1
            candidate = f"{random.randrange(10 ** width):0{width}d}"
            if _free(candidate):
                issued.append(candidate)
                return candidate
        fallback = f"Set{index + 1:02d}"
        issued.append(fallback)
        return fallback

    return factory


class MASTER_BAKER_OT_name_from_collections(bpy.types.Operator):
    bl_idname = "master_baker.name_from_collections"
    bl_label = "Auto-Name from Collections"
    bl_description = (
        "Rename meshes from the collections they sit in: a mesh in a 'low' (or LP) "
        "collection becomes <base>_low, meshes in a 'high' (or HP) collection become "
        "<base>_high01, <base>_high02... Each parent collection gets its own shared "
        "base name. Uses the selection, or the whole scene when nothing is selected. "
        "Does not create bake groups"
    )
    bl_options = {"REGISTER", "UNDO"}

    base_name: bpy.props.StringProperty(
        name="Base Name",
        description="Shared base for the renamed meshes. Leave empty for a random "
        "number, which is unique in the scene and carries no meaning of its own",
        default="",
    )
    number_pad: bpy.props.IntProperty(
        name="Index Digits",
        description="Width of the index written after the suffix (_high01 vs _high001)",
        default=2,
        min=1,
        max=4,
    )

    def execute(self, context):
        selected = _selected_mesh_objects(context)
        pool = selected if selected else _scene_mesh_objects(context)
        if not pool:
            self.report({"ERROR"}, "No mesh objects to name")
            return {"CANCELLED"}

        plan = collection_naming.plan_collection_names(
            _collection_naming_samples(context, pool),
            base_name_factory=_random_base_name_factory(
                context, str(self.base_name or "").strip()
            ),
            pad=int(self.number_pad),
        )
        if not plan.renames:
            hint = "no meshes sit in a low/high/cage collection"
            if plan.skipped_ambiguous:
                hint = f"{len(plan.skipped_ambiguous)} mesh(es) are in a collection naming two roles"
            elif not plan.skipped_unclassified:
                hint = "every mesh already carries the name its collection asks for"
            self.report({"WARNING"}, f"Nothing renamed: {hint}")
            return {"CANCELLED"}

        objects = context.scene.objects
        targets = [(objects.get(entry.object_name), entry) for entry in plan.renames]
        targets = [(obj, entry) for obj, entry in targets if obj is not None]

        # Two passes through a parked name. A planned target can be the CURRENT name
        # of another planned mesh (swapping _high01 and _high02 is the ordinary case),
        # and renaming straight into an occupied name makes Blender append ".001" --
        # which would then read as a duplicate suffix and silently survive into the
        # bake groups. Parking every mesh first means each final name is free.
        for index, (obj, _entry) in enumerate(targets):
            obj.name = f"__mb_naming_{index:04d}"
        renamed = 0
        for obj, entry in targets:
            # Drop a stale suffix-derived role tag so the fresh name is the single
            # source of truth, exactly as the proximity prep pass does.
            existing = tagging.read_role_tag(obj)
            if existing is not None and existing.get(tagging.SOURCE_KEY) == "suffix":
                tagging.clear_role_tag(obj)
            obj.name = entry.new_name
            renamed += 1

        set_word = "set" if plan.set_count == 1 else "sets"
        message = (
            f"Named {renamed} mesh(es) across {plan.set_count} {set_word} "
            f"({', '.join(plan.base_names)})"
        )
        if selected:
            message += " from the selection"
        skipped = len(plan.skipped_unclassified) + len(plan.skipped_ambiguous)
        if skipped:
            message += f"; skipped {skipped} outside a role collection"
        message += " -- now run Auto-Build Bake Groups from Names"
        _sync_tag_status(context, message)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


def _uv_optimizer_assignments(project):
    """Return one writable assignment per mesh datablock/UV/domain combination."""
    by_object = {}
    conflicts = set()
    for group in sorted(getattr(project, "groups", []), key=lambda item: str(getattr(item, "name", ""))):
        role_state = properties.group_role_assignments_state(group)
        projection_state = properties.group_projection_settings_state(group)
        requested_layer = str(getattr(projection_state, "uv_layer_name", "") or "").strip()
        texture_set = str(getattr(group, "texture_set_name", "") or "").strip()
        domain = texture_set or f"group:{str(getattr(group, 'name', '') or '')}"
        for slot in getattr(role_state, "low_meshes", []):
            obj = getattr(slot, "object_ref", None)
            if obj is None or getattr(obj, "type", None) != "MESH":
                continue
            mesh = getattr(obj, "data", None)
            layers = getattr(mesh, "uv_layers", None)
            active = getattr(layers, "active", None) if layers is not None else None
            layer_name = requested_layer or str(getattr(active, "name", "") or "")
            key = (layer_name, domain)
            previous = by_object.get(obj.name_full)
            if previous is not None and previous[:2] != key:
                conflicts.add(obj.name_full)
                continue
            by_object[obj.name_full] = (layer_name, domain, obj)

    grouped = {}
    skipped = []
    for object_name in sorted(by_object):
        layer_name, domain, obj = by_object[object_name]
        if object_name in conflicts:
            skipped.append(f"{object_name}: conflicting project UV assignment")
            continue
        mesh = obj.data
        if (
            getattr(obj, "library", None) is not None
            or getattr(mesh, "library", None) is not None
            or not bool(getattr(mesh, "is_editable", True))
        ):
            skipped.append(f"{object_name}: linked/read-only data")
            continue
        if not layer_name or mesh.uv_layers.get(layer_name) is None:
            skipped.append(f"{object_name}: bake UV layer unavailable")
            continue
        group_key = (mesh.as_pointer(), layer_name, domain)
        record = grouped.setdefault(group_key, {
            "objects": [], "layer_name": layer_name, "domain": domain, "source_data": mesh,
        })
        record["objects"].append(obj)
    return [grouped[key] for key in sorted(grouped, key=lambda item: (item[1], item[2], item[0]))], skipped


def _uv_optimizer_skip_summary(skipped_meshes, plan) -> str:
    parts = []
    if plan.skipped_partial_overlaps:
        parts.append(f"{plan.skipped_partial_overlaps} islands overlap other islands")
    if getattr(plan, "skipped_degenerate", 0):
        parts.append(f"{plan.skipped_degenerate} islands locked (sub-texel triangle)")
    if plan.skipped_unsafe:
        # Name the rule that stopped the move: "could not move" alone sent the
        # artist looking at their layout when the real cause was a sliver.
        reasons = []
        for entry in getattr(plan, "skipped_reasons", ()) or ():
            reason = str(entry).split(": ", 1)[-1]
            if reason not in reasons:
                reasons.append(reason)
        detail = f" ({'; '.join(reasons[:3])})" if reasons else ""
        parts.append(f"{plan.skipped_unsafe} islands could not move without hurting the layout{detail}")
    if skipped_meshes:
        parts.append(f"{len(skipped_meshes)} meshes skipped")
    return ", ".join(parts)


def _write_uv_layer(layer, values):
    flat = [coordinate for uv in values for coordinate in uv]
    try:
        layer.data.foreach_set("uv", flat)
    except Exception:
        if len(layer.data) != len(values):
            raise RuntimeError("UV loop count changed during optimization")
        for item, uv in zip(layer.data, values):
            item.uv = uv


_UV_TOOL_MODES = {"OBJECT", "EDIT_MESH"}


def _uv_tool_mode_ok(context):
    return getattr(context, "mode", "OBJECT") in _UV_TOOL_MODES


def _set_object_interaction_mode(context, mode):
    """Run object.mode_set with a 3D viewport in context when one exists.

    The UV tools are launched from the Image Editor sidebar, where mode_set
    still polls, but a viewport override keeps the switch identical to the
    Tab key path (multi-object edit re-entry, cage/overlay refresh)."""
    area, region = _find_view3d_area_region(context)
    if area is not None:
        with context.temp_override(area=area, region=region):
            bpy.ops.object.mode_set(mode=mode)
    else:
        bpy.ops.object.mode_set(mode=mode)


class _object_mode_scope:
    """Flush Edit Mode geometry to the mesh datablock for the duration of a UV tool.

    In Edit Mode ``obj.data`` (and the evaluated depsgraph) hold the geometry
    from the moment Edit Mode was entered, and UV writes through ``uv_layers``
    are overwritten when Edit Mode ends. Switching to Object Mode flushes the
    edit mesh both ways; the previous mode is restored on exit, including on
    exceptions, so the artist stays in Edit Mode with selection intact."""

    def __init__(self, context):
        self._context = context
        self._restore = None

    def __enter__(self):
        if getattr(self._context, "mode", "OBJECT") == "EDIT_MESH":
            obj = getattr(self._context, "active_object", None)
            previous = str(getattr(obj, "mode", "EDIT") or "EDIT")
            _set_object_interaction_mode(self._context, "OBJECT")
            self._restore = previous
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._restore is not None:
            try:
                _set_object_interaction_mode(self._context, self._restore)
            except Exception:
                traceback.print_exc()
            # The two mode switches fire geometry updates on every edited object
            # after this operator returns. They are not edits: without this, an
            # Optimize UV Seams run that changed nothing still re-committed every
            # Live Reproject texture. UV writes announce themselves explicitly via
            # texture_reprojection.notify_uv_change.
            dirty_tracker.set_post_bake_cooldown(0.5)
        return False


def _active_snapshot_mesh_or_report(operator, context):
    obj = getattr(context, "active_object", None)
    if obj is None or getattr(obj, "type", None) != "MESH" or getattr(obj, "data", None) is None:
        operator.report({"ERROR"}, "Select an active mesh object")
        return None
    if not _uv_tool_mode_ok(context):
        operator.report({"ERROR"}, "UV Snapshot requires Object Mode or mesh Edit Mode")
        return None
    if getattr(obj, "library", None) is not None or getattr(obj.data, "library", None) is not None:
        operator.report({"ERROR"}, "Linked or read-only mesh data cannot be modified")
        return None
    return obj


def _snapshot_for_active_object(context):
    obj = getattr(context, "active_object", None)
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    if obj is None or settings is None:
        return None
    return uv_snapshot.find_snapshot(settings, obj)


def _dirty_projects_using_object(obj):
    touched = 0
    for _scene, _settings, project in _iter_scene_project_records():
        found = False
        for group in getattr(project, "groups", []):
            role_state = properties.group_role_assignments_state(group)
            if any(getattr(slot, "object_ref", None) == obj for slot in getattr(role_state, "low_meshes", [])):
                found = True
                break
        if found:
            dirty_tracker.mark_all_dirty(project)
            touched += 1
    return touched


class MASTER_BAKER_OT_capture_uv_snapshot(bpy.types.Operator):
    bl_idname = "master_baker.capture_uv_snapshot"
    bl_label = "Capture UV Snapshot"
    bl_description = "Save the active mesh's surface and UV map in the blend file so the UVs can be restored after later edits"
    # No UNDO: capturing ADDS a row to settings.uv_snapshots, resizing the same
    # fyr_baker_settings IDProperty the sidebar's retained name fields point into
    # (see add_project on T74067). Re-capturing replaces the row, so nothing is lost.
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "active_object", None)
        return _uv_tool_mode_ok(context) and obj is not None and getattr(obj, "type", None) == "MESH"

    def invoke(self, context, _event):
        if _snapshot_for_active_object(context) is not None:
            return context.window_manager.invoke_confirm(
                self,
                _event,
                title="Replace UV Snapshot?",
                message="The current snapshot for this object will be replaced.",
                confirm_text="Replace Snapshot",
                icon="QUESTION",
            )
        return self.execute(context)

    def execute(self, context):
        with _object_mode_scope(context):
            return self._execute_in_object_mode(context)

    def _execute_in_object_mode(self, context):
        obj = _active_snapshot_mesh_or_report(self, context)
        if obj is None:
            return {"CANCELLED"}
        settings = context.scene.fyr_baker_settings
        try:
            from . import bl_info as addon_bl_info
            version = ".".join(str(value) for value in addon_bl_info.get("version", ()))
            _snapshot, replaced = uv_snapshot.capture_snapshot(
                settings,
                obj,
                captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                blender_version=str(bpy.app.version_string),
                addon_version=version,
            )
        except (ValueError, RuntimeError, MemoryError) as exc:
            self.report({"ERROR"}, f"UV snapshot blocked: {exc}")
            return {"CANCELLED"}
        except Exception as exc:
            # Anything else is an unexpected API/data failure. Print the full
            # traceback for a support bundle, but still report a copyable
            # type + message so a tester never has to reproduce it from a
            # bare Python error popup.
            traceback.print_exc()
            self.report({"ERROR"}, f"UV snapshot failed: {type(exc).__name__}: {exc}")
            return {"CANCELLED"}
        action = "Updated" if replaced else "Captured"
        message = f"{action} UV snapshot for {obj.name} ({len(obj.data.polygons)} faces)"
        settings.status_message = message
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_restore_uv_snapshot(bpy.types.Operator):
    bl_idname = "master_baker.restore_uv_snapshot"
    bl_label = "Restore UVs"
    bl_description = "Restore UVs exactly when topology matches, or transfer them from the stored surface when topology has changed"
    bl_options = {"REGISTER", "UNDO"}

    replace_current: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    max_distance: bpy.props.FloatProperty(
        name="Maximum Transfer Distance",
        description="Set the maximum surface distance for UV transfer. 0 chooses a safe value from the mesh size",
        default=0.0,
        min=0.0,
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "active_object", None)
        return (
            _uv_tool_mode_ok(context)
            and obj is not None
            and getattr(obj, "type", None) == "MESH"
            and _snapshot_for_active_object(context) is not None
        )

    def execute(self, context):
        with _object_mode_scope(context):
            return self._execute_in_object_mode(context)

    def _execute_in_object_mode(self, context):
        obj = _active_snapshot_mesh_or_report(self, context)
        if obj is None:
            return {"CANCELLED"}
        snapshot = _snapshot_for_active_object(context)
        if snapshot is None:
            self.report({"ERROR"}, "Capture a UV snapshot for the active object first")
            return {"CANCELLED"}

        try:
            uv_snapshot.validate_snapshot(snapshot, obj)
        except (ValueError, ReferenceError, RuntimeError) as exc:
            self.report({"ERROR"}, f"UV restore blocked: {exc}. Capture a new snapshot from a mesh with the UVs you want to restore.")
            return {"CANCELLED"}

        diagnostics = None
        try:
            exact = uv_snapshot.topology_fingerprint(obj.data) == str(snapshot.topology_fingerprint)
            if exact:
                values = uv_snapshot.exact_restore_plan(snapshot, obj).values
            else:
                transfer = uv_transfer.surface_transfer(
                    snapshot,
                    obj,
                    context.evaluated_depsgraph_get(),
                    max_distance=float(self.max_distance) if self.max_distance > 0 else None,
                )
                values, diagnostics = transfer.values, transfer.diagnostics
                if self.replace_current and diagnostics.confidence != "HIGH":
                    raise ValueError("Review-level surface transfers cannot replace the current UV map")
        except (ValueError, RuntimeError, MemoryError) as exc:
            self.report({"ERROR"}, f"UV restore blocked: {exc}")
            return {"CANCELLED"}

        mesh = obj.data
        original_mesh = mesh
        isolated_mesh = None
        created_layer = None
        replaced_values = None
        target_layer = getattr(mesh.uv_layers, "active", None) if self.replace_current else None
        if self.replace_current and target_layer is None:
            self.report({"ERROR"}, "There is no current UV map to replace")
            return {"CANCELLED"}
        try:
            _suppress_bg_prepare(3.0)
            with dirty_tracker.suppress():
                mesh_users = [candidate for candidate in bpy.data.objects if getattr(candidate, "data", None) == mesh]
                if len(mesh_users) > 1:
                    isolated_mesh = mesh.copy()
                    obj.data = isolated_mesh
                    mesh = isolated_mesh
                    target_layer = getattr(mesh.uv_layers, "active", None) if self.replace_current else None
                if target_layer is None:
                    target_layer = mesh.uv_layers.new(
                        name=uv_snapshot.unique_restore_layer_name(mesh, str(snapshot.uv_layer_name)),
                    )
                    created_layer = target_layer
                else:
                    replaced_values = [(float(item.uv[0]), float(item.uv[1])) for item in target_layer.data]
                if len(target_layer.data) != len(values):
                    raise RuntimeError("Restore result loop count does not match the destination mesh")
                _write_uv_layer(target_layer, values)
                mesh.uv_layers.active = target_layer
                target_layer.active_render = bool(getattr(snapshot, "active_render", False))
                mesh.update()
            context.view_layer.update()
        except Exception as exc:
            if created_layer is not None and mesh.uv_layers.get(created_layer.name) is not None:
                mesh.uv_layers.remove(created_layer)
            elif replaced_values is not None and target_layer is not None:
                try:
                    _write_uv_layer(target_layer, replaced_values)
                except Exception:
                    pass
            if isolated_mesh is not None:
                try:
                    obj.data = original_mesh
                    if isolated_mesh.users == 0:
                        bpy.data.meshes.remove(isolated_mesh)
                except Exception:
                    pass
            self.report({"ERROR"}, f"UV restore rolled back: {exc}")
            return {"CANCELLED"}

        touched_projects = _dirty_projects_using_object(obj)
        if touched_projects:
            runtime.schedule_speculative_prepare(delay=0.1, restart=True)
        texture_reprojection.notify_uv_change(properties.peek_active_project(context.scene))
        if exact:
            message = "UVs restored exactly"
        elif diagnostics is not None and diagnostics.confidence == "REVIEW":
            message = (
                f"UV transfer needs review ({diagnostics.coverage:.1%} coverage; "
                f"{diagnostics.ambiguous_faces} seam-ambiguous faces)"
            )
        else:
            message = "UVs transferred to changed topology"
        context.scene.fyr_baker_settings.status_message = message
        self.report({"WARNING"} if diagnostics is not None and diagnostics.confidence == "REVIEW" else {"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_rename_uv_snapshot(bpy.types.Operator):
    bl_idname = "master_baker.rename_uv_snapshot"
    bl_label = "Rename UV Snapshot"
    bl_description = "Rename the UV snapshot stored on the active object"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="Snapshot Name", default="UV Snapshot")

    def invoke(self, context, _event):
        snapshot = _snapshot_for_active_object(context)
        if snapshot is None:
            self.report({"ERROR"}, "The active object has no UV snapshot")
            return {"CANCELLED"}
        self.name = str(getattr(snapshot, "snapshot_name", "UV Snapshot") or "UV Snapshot")
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        snapshot = _snapshot_for_active_object(context)
        name = str(self.name or "").strip()
        if snapshot is None or not name:
            self.report({"ERROR"}, "Enter a snapshot name")
            return {"CANCELLED"}
        snapshot.snapshot_name = name
        return {"FINISHED"}


class MASTER_BAKER_OT_delete_uv_snapshot(bpy.types.Operator):
    bl_idname = "master_baker.delete_uv_snapshot"
    bl_label = "Delete UV Snapshot"
    bl_description = "Delete the active object's stored surface and UV snapshot from the blend file"
    # No UNDO: this REMOVES a row from settings.uv_snapshots (see add_project on
    # T74067). Not stashed like the map/group removals -- the payload is a whole mesh
    # datablock, so holding it in memory to offer an undo is exactly the resident
    # footprint the snapshot delete exists to release. The confirm dialog below is the
    # safety net instead.
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self,
            event,
            title="Delete UV Snapshot?",
            message="The stored source surface and UV data will be removed from this blend file.",
            confirm_text="Delete Snapshot",
            icon="TRASH",
        )

    def execute(self, context):
        snapshot = _snapshot_for_active_object(context)
        if snapshot is None:
            self.report({"ERROR"}, "The active object has no UV snapshot")
            return {"CANCELLED"}
        try:
            uv_snapshot.delete_snapshot(context.scene.fyr_baker_settings, snapshot)
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "UV snapshot deleted")
        return {"FINISHED"}


class MASTER_BAKER_OT_cleanup_orphan_uv_snapshots(bpy.types.Operator):
    bl_idname = "master_baker.cleanup_orphan_uv_snapshots"
    bl_label = "Clean Orphaned UV Snapshots"
    bl_description = "Delete stored UV snapshots whose source objects no longer exist"
    # No UNDO: removes rows from settings.uv_snapshots (see delete_uv_snapshot).
    # Only ever touches snapshots whose source object is already gone.
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self,
            event,
            title="Clean Orphaned UV Snapshots?",
            message="Snapshots whose source objects were deleted will be permanently removed.",
            confirm_text="Clean Snapshots",
            icon="TRASH",
        )

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        orphaned = [
            snapshot for snapshot in settings.uv_snapshots
            if getattr(snapshot, "source_object_ref", None) is None
        ]
        for snapshot in reversed(orphaned):
            uv_snapshot.delete_snapshot(settings, snapshot)
        self.report({"INFO"}, f"Deleted {len(orphaned)} orphaned UV snapshot(s)")
        return {"FINISHED"}


class MASTER_BAKER_OT_optimize_uv_seams(bpy.types.Operator):
    bl_idname = "master_baker.optimize_uv_seams"
    bl_label = "Optimize UV Seams"
    bl_description = "Experimental: align both sides of each UV seam before baking to reduce visible seam artifacts"
    bl_options = {"REGISTER", "UNDO"}

    max_local_adjustment: bpy.props.FloatProperty(name="Maximum Local Adjustment", default=1.0, options={"HIDDEN"})
    max_rotation: bpy.props.FloatProperty(name="Maximum Rigid Island Rotation", default=3.0, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _uv_tool_mode_ok(context) and properties.get_active_project(context.scene) is not None

    def execute(self, context):
        if not _uv_tool_mode_ok(context):
            self.report({"ERROR"}, "Optimize UV Seams requires Object Mode or mesh Edit Mode")
            return {"CANCELLED"}
        with _object_mode_scope(context):
            return self._execute_in_object_mode(context)

    def _execute_in_object_mode(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if runtime.active_bake_snapshot() is not None:
            self.report({"ERROR"}, "Wait for the running bake to finish")
            return {"CANCELLED"}

        assignments, skipped = _uv_optimizer_assignments(project)
        depsgraph = context.evaluated_depsgraph_get()
        mesh_inputs = []
        assignment_by_object_id = {}
        for assignment in assignments:
            representative = sorted(assignment["objects"], key=lambda obj: obj.name_full)[0]
            try:
                mesh_input = uv_seam_optimizer.mesh_input_from_blender_object(
                    representative, assignment["layer_name"], assignment["domain"], depsgraph,
                )
            except (ValueError, RuntimeError) as exc:
                skipped.append(f"{representative.name_full}: {exc}")
                continue
            mesh_inputs.append(mesh_input)
            assignment_by_object_id[mesh_input.object_id] = assignment

        if not mesh_inputs:
            self.report({"ERROR"}, "No writable low-mesh bake UV layers were eligible")
            return {"CANCELLED"}

        width = int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION))
        height = int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION))
        margin = int(getattr(project, "margin", constants.DEFAULT_MARGIN))
        plan = uv_seam_optimizer.plan_uv_seam_optimization(
            mesh_inputs,
            None,
            width,
            height,
            margin,
            uv_seam_optimizer.UvOptimizationLimits(
                max_local_adjustment_px=float(self.max_local_adjustment),
                max_rotation_deg=float(self.max_rotation),
            ),
        )
        max_move_px = 0.0
        inputs_by_id = {mesh_input.object_id: mesh_input for mesh_input in mesh_inputs}
        for object_id, updated in plan.updated_uvs.items():
            source = inputs_by_id.get(object_id)
            if source is None or len(source.uvs) != len(updated):
                continue
            for before, after in zip(source.uvs, updated):
                move = max(abs(after[0] - before[0]) * width, abs(after[1] - before[1]) * height)
                if move > max_move_px:
                    max_move_px = move
        breakdown = _uv_optimizer_skip_summary(skipped, plan)
        if not plan.changed or max_move_px < 0.01:
            # The solver can report an "improvement" that is pure float noise. Do not
            # write UVs, dirty the bake, or claim a change the artist cannot see.
            if plan.skipped_unsafe or plan.skipped_partial_overlaps:
                # Nothing moved because a rule stopped it, not because the seams
                # were fine. Say so, or the artist stops looking for the cause.
                message = "No safe UV seam adjustment found"
            else:
                message = "UV seams are already aligned within the 1 texel limit"
            if breakdown:
                message += "; " + breakdown
            project.last_status_message = message
            context.scene.fyr_baker_settings.status_message = message
            self.report({"INFO"}, message)
            return {"CANCELLED"}

        original_data = {obj: obj.data for assignment in assignments for obj in assignment["objects"]}
        direct_snapshots = []
        created_meshes = []
        try:
            _suppress_bg_prepare(3.0)
            with dirty_tracker.suppress():
                for object_id in sorted(plan.updated_uvs):
                    assignment = assignment_by_object_id.get(object_id)
                    if assignment is None:
                        continue
                    source_data = assignment["source_data"]
                    objects = assignment["objects"]
                    all_users = [obj for obj in bpy.data.objects if getattr(obj, "data", None) is source_data]
                    external_users = [obj for obj in all_users if obj not in objects]
                    target_data = source_data
                    if external_users:
                        target_data = source_data.copy()
                        created_meshes.append(target_data)
                        for obj in objects:
                            obj.data = target_data
                    layer = target_data.uv_layers.get(assignment["layer_name"])
                    if layer is None:
                        raise RuntimeError(f"UV layer disappeared from {target_data.name}")
                    if target_data is source_data:
                        direct_snapshots.append((layer, [(float(item.uv[0]), float(item.uv[1])) for item in layer.data]))
                    _write_uv_layer(layer, plan.updated_uvs[object_id])
                    target_data.update()
            context.view_layer.update()
        except Exception as exc:
            for layer, values in reversed(direct_snapshots):
                try:
                    _write_uv_layer(layer, values)
                except Exception:
                    pass
            for obj, data in original_data.items():
                try:
                    obj.data = data
                except Exception:
                    pass
            for mesh in created_meshes:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            self.report({"ERROR"}, f"UV optimization rolled back: {exc}")
            return {"CANCELLED"}

        dirty_tracker.mark_all_dirty(project)
        runtime.schedule_speculative_prepare(delay=0.1, restart=True)
        texture_reprojection.notify_uv_change(project)
        message = (
            f"Optimized {plan.optimized_components} seam networks across "
            f"{plan.optimized_islands} islands (largest move {max_move_px:.2f} px)"
        )
        if plan.preserved_stacks:
            message += f"; preserved {plan.preserved_stacks} stacks"
        if breakdown:
            message += "; " + breakdown
        project.last_status_message = message
        context.scene.fyr_baker_settings.status_message = message
        self.report({"INFO"}, message)
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_export_workspace(bpy.types.Operator):
    bl_idname = "master_baker.export_workspace"
    bl_label = "Export Bake Workspace"
    bl_description = "Export the project's prepared meshes and bake settings without starting a bake"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        issues = validation.validate_bake_project(project)
        errors, warnings, primary_message = _report_validation_issues(self, issues)
        if errors:
            project.last_status_message = primary_message or "Fix validation errors before export"
            context.scene.fyr_baker_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}
        if warnings:
            project.last_status_message = primary_message or f"Exporting with {len(warnings)} warning(s)"
        try:
            prepared = export.prepare_bake_job(
                context,
                project,
                preserve_latest_outputs=True,
                cancel_check=_capture_cancel_requested,
            )
        except InterruptedError:
            project.last_status_message = constants.STATUS_CANCELLED
            context.scene.fyr_baker_settings.status_message = constants.STATUS_CANCELLED
            self.report({"INFO"}, constants.STATUS_CANCELLED)
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            project.last_status_message = constants.STATUS_FAILED
            context.scene.fyr_baker_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}

        _issues, errors, warnings = _validate_prepared_job(self, prepared, project, context.scene.fyr_baker_settings)
        if errors:
            context.scene.fyr_baker_settings.status_message = constants.STATUS_FAILED
            return {"CANCELLED"}
        if warnings:
            project.last_status_message = f"Exported with {len(warnings)} job warning(s)"

        context.scene.fyr_baker_settings.status_message = f"Exported {prepared.job.job_id}"
        self.report({"INFO"}, f"Exported bake workspace: {prepared.job_path}")
        return {"FINISHED"}


class MASTER_BAKER_OT_bake_project(bpy.types.Operator):
    bl_idname = "master_baker.bake_project"
    bl_label = "Bake Project"
    bl_description = "Bake every enabled map of the active bake project and write the textures to the output folder"

    def invoke(self, context, event):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        missing_uvs = [
            issue
            for issue in validation.validate_bake_project(project, check_topology=False).errors
            if issue.code in _MISSING_UV_ERROR_CODES
        ]
        if missing_uvs:
            return bpy.ops.master_baker.confirm_bake_without_uvs("INVOKE_DEFAULT")
        duplicates = export.find_duplicate_output_map_settings(project)
        if duplicates:
            _set_pending_bake_state(
                context,
                project,
                "bake_project",
                duplicates,
            )
            return bpy.ops.master_baker.handle_duplicate_map_outputs("INVOKE_DEFAULT")
        return self.execute(context)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        return _run_bake(self, context, project, start_message="Bake started")


class MASTER_BAKER_OT_confirm_bake_without_uvs(bpy.types.Operator):
    bl_idname = "master_baker.confirm_bake_without_uvs"
    bl_label = "Missing UVs"
    bl_description = "Bake the rest of the project, skipping low-poly meshes that have no usable UV map"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self,
            width=520,
            title="Missing UVs",
            confirm_text="Skip Them and Bake",
            cancel_default=True,
        )

    def draw(self, context):
        project = properties.get_active_project(getattr(context, "scene", None))
        issues = validation.validate_bake_project(project, check_topology=False) if project is not None else None
        missing_uvs = [
            issue
            for issue in getattr(issues, "errors", [])
            if issue.code in _MISSING_UV_ERROR_CODES
        ]
        layout = self.layout
        layout.label(text="The bake has no UV space to write these meshes into:", icon="ERROR")
        names = []
        for issue in missing_uvs:
            name = str(issue.object_name or issue.group_name or issue.subject or "Low mesh")
            if name and name not in names:
                names.append(name)
        for name in names[:8]:
            layout.label(text=name, icon="MESH_DATA")
        if len(names) > 8:
            layout.label(text=f"+{len(names) - 8} more")
        layout.separator()
        note = layout.column(align=True)
        note.label(text="These meshes will be skipped. Everything else bakes normally.")
        note.label(text="Add a UV map to them and bake again to include them.")

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        duplicates = export.find_duplicate_output_map_settings(project)
        if duplicates:
            _set_pending_bake_state(
                context,
                project,
                "bake_project",
                duplicates,
                allow_missing_uvs=True,
            )
            return bpy.ops.master_baker.handle_duplicate_map_outputs("INVOKE_DEFAULT")
        return _run_bake(
            self,
            context,
            project,
            start_message="Bake started, skipping meshes without UVs",
            allow_missing_uvs=True,
        )


class MASTER_BAKER_OT_toggle_live_bake(bpy.types.Operator):
    bl_idname = "master_baker.toggle_live_bake"
    bl_label = "Live Bake"
    bl_description = "Turn automatic rebaking on or off after the first bake completes"

    def invoke(self, context, event):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        # Only check duplicates when turning live bake ON (not when toggling it off).
        if not _live_bake_is_active(settings, project):
            duplicates = export.find_duplicate_output_map_settings(project)
            if duplicates:
                _set_pending_bake_state(context, project, "toggle_live_bake", duplicates, live_bake_mode="enable")
                return bpy.ops.master_baker.handle_duplicate_map_outputs("INVOKE_DEFAULT")
        return self.execute(context)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if _live_bake_is_active(settings, project):
            _deactivate_live_bake(context.scene)
            project.last_status_message = "Live Bake off"
            if settings is not None:
                settings.status_message = project.last_status_message
            overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
            self.report({"INFO"}, "Live Bake off")
            return {"FINISHED"}

        active_snapshot = runtime.active_bake_snapshot()
        if active_snapshot is not None and active_snapshot.running:
            self.report({"ERROR"}, "Wait for the current bake to finish")
            return {"CANCELLED"}

        return _run_bake(
            self,
            context,
            project,
            start_message="Live Bake started",
            live_bake_mode="enable",
        )


class MASTER_BAKER_OT_restart_backend(bpy.types.Operator):
    bl_idname = "master_baker.restart_backend"
    bl_label = "Restart Backend"
    bl_description = (
        "Restart the bake worker and prepare the scene caches again. "
        "Useful for comparing cold and warm performance"
    )
    # No UNDO: this touches no blend data, and undo pushes from panel operators
    # have bitten us before (memfile-undo panel crash).
    bl_options = {"REGISTER"}

    def execute(self, context):
        snapshot = runtime.active_bake_snapshot()
        if snapshot is not None and getattr(snapshot, "running", False):
            # Restarting kills the resident worker mid-job; the next poll would
            # report it exited unexpectedly and fail the bake.
            self.report({"ERROR"}, "Stop the active bake before restarting the backend")
            return {"CANCELLED"}
        try:
            runtime.restart_backend_worker()
        except Exception as exc:  # noqa: BLE001 - surface any failure to the user
            self.report({"ERROR"}, f"Backend restart failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Backend restarted - prewarming scene cache")
        return {"FINISHED"}


def _bake_state_message(context) -> str:
    """The active project's status message, as shown in the readiness tooltip."""
    scene = getattr(context, "scene", None)
    project = properties.get_active_project(scene) if scene is not None else None
    project_state = str(getattr(project, "last_status_message", "") or "").strip() if project is not None else ""
    if project_state:
        return project_state
    settings = getattr(scene, "fyr_baker_settings", None)
    settings_state = str(getattr(settings, "status_message", "") or "").strip() if settings is not None else ""
    return settings_state or constants.STATUS_IDLE


class MASTER_BAKER_OT_show_bake_state(bpy.types.Operator):
    """Flat readiness label in the Bake panel. Exists so the state message is a
    tooltip on "Bake Ready" instead of its own clipped "State:" row."""
    bl_idname = "master_baker.show_bake_state"
    bl_label = "Bake State"
    bl_description = "Current bake state"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, _properties):
        return _bake_state_message(context)

    def execute(self, context):
        self.report({"INFO"}, _bake_state_message(context))
        return {"FINISHED"}


class MASTER_BAKER_OT_run_preflight(bpy.types.Operator):
    bl_idname = "master_baker.run_preflight"
    bl_label = "Validate Project"
    bl_description = "Check the active bake project for problems before baking, including topology and file permissions"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        
        try:
            depsgraph = context.evaluated_depsgraph_get()
            udim_occupancy = export.collect_udim_occupancy(project, depsgraph)
        except Exception:
            depsgraph = None
            udim_occupancy = None
        issues = validation.validate_bake_project(
            project,
            check_topology=True,
            udim_occupancy=udim_occupancy,
            # Same tile-aware view of the OTHER projects, or an Automatic-mode set
            # there resolves to no tiles and its real overlap with ours is missed.
            other_udim_occupancy_for=(
                (lambda other: export.collect_udim_occupancy(other, depsgraph))
                if depsgraph is not None else None
            ),
        )
        issues.extend(validation.validate_scene_lighting(project, context.scene))
        errors, warnings, primary_message = _report_validation_issues(self, issues)

        # Surface the output-file collisions the actual bake would stop on. These
        # aren't modelled as project validation errors because groups sharing a
        # texture set collide on purpose, so preflight would otherwise give a
        # false all-clear while the bake pops the duplicate-resolution dialog.
        duplicate_groups = export.find_duplicate_output_map_settings(project)
        duplicate_message = ""
        if duplicate_groups:
            labels = list(dict.fromkeys(
                naming.map_label(getattr(group[0][0], "map_type", "")) for group in duplicate_groups
            ))
            duplicate_message = (
                f"{len(duplicate_groups)} map output(s) collide on the same file "
                f"({', '.join(labels)}). Give them distinct suffixes before baking."
            )
            self.report({"ERROR"}, duplicate_message)

        # Warnings the BAKE raises but project validation never modelled, so Check and
        # Bake stop disagreeing about whether a project is ready.
        extra_warnings: list[str] = []
        try:
            extra_warnings.extend(_preflight_cycles_route_warnings(project))
        except Exception:
            pass
        try:
            orphan_message = _preflight_ungrouped_mesh_warning(context, project)
        except Exception:
            orphan_message = ""
        if orphan_message:
            extra_warnings.append(orphan_message)
        for message in extra_warnings:
            self.report({"WARNING"}, message)

        total_errors = len(errors) + len(duplicate_groups)
        total_warnings = len(warnings) + len(extra_warnings)

        # Persist counts/summaries so the panel's validation state reflects this run
        # (previously only a real bake wrote these, so the badge stayed at 0).
        project.last_error_count = total_errors
        project.last_warning_count = total_warnings
        # Don't fall back to primary_message here: it returns the first *warning*
        # when there are no errors, which would leak warning text into the error
        # summary on a passes-with-warnings run.
        project.last_error_summary = duplicate_message or (errors[0].message if errors else "")
        project.last_warning_summary = (
            warnings[0].message if warnings else (extra_warnings[0] if extra_warnings else "")
        )

        if total_errors:
            final_message = f"Validation failed: {duplicate_message or primary_message or f'{total_errors} error(s)'}"
            self.report({"ERROR"}, final_message)
        elif total_warnings:
            summary_text = primary_message or (extra_warnings[0] if extra_warnings else "")
            final_message = f"Validation passed with {total_warnings} warning(s): {summary_text}"
            self.report({"WARNING"}, final_message)
        elif high_mesh_cache.is_mesh_prewarm_pending() or runtime.is_prepare_in_flight():
            final_message = _preflight_success_message(caches_pending=True)
            self.report({"INFO"}, final_message)
        else:
            final_message = _preflight_success_message(caches_pending=False)
            self.report({"INFO"}, final_message)

        project.last_status_message = final_message
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = final_message

        return {"FINISHED"}


class MASTER_BAKER_OT_focus_validation_object(bpy.types.Operator):
    """Click target for a preflight row that names a mesh: select it and frame it."""

    bl_idname = "master_baker.focus_validation_object"
    bl_label = "Select and Frame"
    bl_description = "Select this mesh and frame it in the 3D viewport"
    bl_options = {"REGISTER", "UNDO"}

    object_name: bpy.props.StringProperty(name="Object", default="", options={"HIDDEN"})

    def execute(self, context):
        name = str(self.object_name or "").strip()
        scene = getattr(context, "scene", None)
        target = _scene_object_getter(scene)(name) if scene is not None else None
        if target is None:
            self.report({"ERROR"}, f"{name or 'The mesh'} is not in this scene")
            return {"CANCELLED"}
        if not _select_objects_in_view_layer(context, [target], active_object=target):
            self.report({"ERROR"}, f"Unable to select {target.name}")
            return {"CANCELLED"}
        _frame_selected_in_view3d(context)
        self.report({"INFO"}, f"Selected {target.name}")
        return {"FINISHED"}


def _frame_selected_in_view3d(context) -> None:
    """view_selected in every 3D viewport of the window; a missing viewport is not an error."""
    window = getattr(context, "window", None)
    screen = getattr(window, "screen", None)
    for area in getattr(screen, "areas", None) or ():
        if getattr(area, "type", "") != "VIEW_3D":
            continue
        region = next((r for r in area.regions if getattr(r, "type", "") == "WINDOW"), None)
        if region is None:
            continue
        try:
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.view3d.view_selected(use_all_regions=False)
        except Exception:
            continue


def _preflight_cycles_route_warnings(project) -> list[str]:
    """Material rows this project will bake through Cycles rather than natively.

    Preflight used to say "ready to bake" and then the bake itself raised this as a
    warning — two different systems with no overlap. It matters more than a cosmetic
    inconsistency: a Cycles material row is the single largest term in a bake's
    wall-clock, so the artist wants to know before they start, not at 82%.
    """
    from . import bakeability_ui

    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for map_item in getattr(project, "maps", []):
        if getattr(map_item, "is_add_phantom", False) or not bool(getattr(map_item, "enabled", False)):
            continue
        if str(getattr(map_item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        channel = str(getattr(map_item, "material_channel", "") or "").strip().upper()
        route = str(getattr(map_item, "execution_route", constants.EXECUTION_ROUTE_AUTO) or "")
        forced_blender = route == constants.EXECUTION_ROUTE_BLENDER
        for group in getattr(project, "groups", []):
            group_name = str(getattr(group, "name", "") or "")
            for obj in properties.effective_high_mesh_objects(group):
                for slot in getattr(obj, "material_slots", []) or []:
                    material = getattr(slot, "material", None)
                    if material is None:
                        continue
                    material_name = str(getattr(material, "name", "") or "")
                    key = (material_name, channel)
                    if key in seen:
                        continue
                    seen.add(key)
                    if forced_blender:
                        warnings.append(
                            f"'{group_name}' {naming.map_label(map_item.map_type)} {channel.title()} "
                            f"is set to the Blender/Cycles route, expect a slower bake"
                        )
                        continue
                    try:
                        report = bakeability_ui.refresh_report(material)
                    except Exception:
                        report = None
                    if report is None:
                        continue
                    verdict = next(
                        (v for v in report.channels if v.channel == channel), None
                    )
                    if verdict is None:
                        if report.status == bakeability_ui.STATUS_NATIVE:
                            continue
                        reason = report.note or report.summary
                    elif not verdict.is_issue:
                        continue
                    else:
                        reason = verdict.reason or report.summary
                    warnings.append(
                        f"'{group_name}' {channel.title()} falls back to Cycles on material "
                        f"'{material_name}': {reason}"
                    )
    return warnings


def _boolean_operand_names() -> set[str]:
    """Names of objects some Boolean modifier reads as an operand (object or collection)."""
    names: set[str] = set()
    for owner in getattr(bpy.data, "objects", None) or ():
        for modifier in getattr(owner, "modifiers", None) or ():
            if str(getattr(modifier, "type", "") or "") != "BOOLEAN":
                continue
            operand = getattr(modifier, "object", None)
            if operand is not None:
                names.add(str(getattr(operand, "name", "") or ""))
            collection = getattr(modifier, "collection", None)
            for member in getattr(collection, "all_objects", None) or ():
                names.add(str(getattr(member, "name", "") or ""))
    names.discard("")
    return names


def _object_excluded_from_render(obj) -> bool:
    """Whether the object, or every collection holding it, is switched off for render."""
    if bool(getattr(obj, "hide_render", False)):
        return True
    collections = list(getattr(obj, "users_collection", None) or ())
    return bool(collections) and all(bool(getattr(c, "hide_render", False)) for c in collections)


def _preflight_ungrouped_mesh_warning(context, project) -> str:
    """Scene meshes carrying a role suffix that no group in this project claims.

    A leftover `Thing_low` sitting outside the project is exactly what the auto-build
    complains about, and preflight could not see it — so Check passed and Bake then
    warned, which reads as the two disagreeing.
    """
    claimed = set()
    for group in getattr(project, "groups", []):
        for obj in project_structure.group_object_set(group):
            claimed.add(getattr(obj, "name", ""))
    orphans = []
    operands = _boolean_operand_names()
    for obj in _scene_mesh_objects(context):
        name = str(getattr(obj, "name", "") or "")
        if not name or name in claimed:
            continue
        if matching.detect_role(name) is None:
            continue
        # A cutter copied from a high keeps the high's suffix ("Thing_high_03.001"). It
        # is a Boolean operand or hidden from render on purpose, never a forgotten mesh.
        if name in operands or _object_excluded_from_render(obj):
            continue
        orphans.append(name)
    if not orphans:
        return ""
    shown = ", ".join(sorted(orphans)[:3])
    if len(orphans) > 3:
        shown += f", +{len(orphans) - 3} more"
    return (
        f"{len(orphans)} scene mesh(es) carry a Low/High/Cage suffix but belong to no "
        f"bake group: {shown}"
    )


def _preflight_success_message(*, caches_pending: bool) -> str:
    if caches_pending:
        return "Validation passed; preparing scene caches before baking"
    return "Pre-flight validation passed! Your project is ready to bake."



class MASTER_BAKER_OT_rebuild_changed_maps(bpy.types.Operator):
    bl_idname = "master_baker.rebuild_changed_maps"
    bl_label = "Rebake Changed Maps"
    bl_description = "Rebake only the enabled output maps whose settings changed since the last successful bake"

    def invoke(self, context, event):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        changed_map_types = map_rebuild.resolve_changed_map_types(project)
        if changed_map_types:
            duplicates = export.find_duplicate_output_map_settings(
                project, selected_map_types=set(changed_map_types)
            )
            if duplicates:
                _set_pending_bake_state(context, project, "rebuild_changed_maps", duplicates)
                return bpy.ops.master_baker.handle_duplicate_map_outputs("INVOKE_DEFAULT")
        return self.execute(context)

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        changed_map_types = map_rebuild.resolve_changed_map_types(project)
        if not changed_map_types:
            message = "No changed maps to rebake"
            project.last_status_message = message
            context.scene.fyr_baker_settings.status_message = message
            self.report({"INFO"}, message)
            return {"FINISHED"}
        changed_group_names = map_rebuild.resolve_changed_group_names(project)

        label_list = ", ".join(naming.map_label(map_type) for map_type in changed_map_types[:3])
        if len(changed_map_types) > 3:
            label_list = f"{label_list}, +{len(changed_map_types) - 3} more"
        group_label = ""
        if changed_group_names and len(changed_group_names) < len(getattr(project, "groups", [])):
            preview_names = ", ".join(changed_group_names[:2])
            if len(changed_group_names) > 2:
                preview_names = f"{preview_names}, +{len(changed_group_names) - 2} more"
            group_label = f" / {preview_names}"
        project.last_status_message = f"Rebaking: {label_list}{group_label}"
        return _run_bake(
            self,
            context,
            project,
            map_types=changed_map_types,
            group_names=changed_group_names or None,
            start_message="Rebake started",
        )


class MASTER_BAKER_OT_mark_all_dirty(bpy.types.Operator):
    bl_idname = "master_baker.mark_all_dirty"
    bl_label = "Mark All Dirty"
    bl_description = "Force the next automatic rebake to rebuild every enabled bake group and map"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if not _live_bake_is_active(settings, project):
            self.report({"ERROR"}, "Enable Live Bake first")
            return {"CANCELLED"}

        active_bake = runtime.active_bake_snapshot()
        if active_bake is not None and active_bake.running:
            self.report({"ERROR"}, "Wait for the current bake to finish")
            return {"CANCELLED"}

        if not dirty_tracker.is_session_active():
            _start_dirty_tracker_session(project)
        dirty_tracker.mark_all_dirty(project)
        dirty_group_count = len(dirty_tracker.get_pending_dirty())
        message = f"Marked {dirty_group_count} bake group(s) dirty"
        project.last_status_message = message
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = message
        overlays.tag_redraw_all_view3d(scene=getattr(context, "scene", None), window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_dirty(bpy.types.Operator):
    bl_idname = "master_baker.clear_dirty"
    bl_label = "Clear Dirty"
    bl_description = "Clear all pending automatic rebake changes without baking them"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        dirty_tracker.clear_all_dirty()
        message = "Cleared dirty rebake queue"
        project.last_status_message = message
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = message
        overlays.tag_redraw_all_view3d(scene=getattr(context, "scene", None), window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


def _next_power_of_two_step(value: int, direction: int) -> int:
    """Nearest power of two strictly above (direction>0) or below (direction<0)
    the current value; values already on a power of two move one octave."""
    value = max(1, int(value))
    if direction > 0:
        result = 1
        while result <= value:
            result <<= 1
        return result
    result = 1
    while (result << 1) < value:
        result <<= 1
    return result


class MASTER_BAKER_OT_step_map_row_samples(bpy.types.Operator):
    bl_idname = "master_baker.step_map_row_samples"
    bl_label = "Step Rays"
    bl_description = "Move this map's sample count to the next power of two. Click the number to enter an exact value"
    bl_options = {"INTERNAL", "UNDO"}

    map_uuid: bpy.props.StringProperty(name="Map UUID", default="", options={"HIDDEN"})
    prop_name: bpy.props.StringProperty(name="Property", default="samples", options={"HIDDEN"})
    direction: bpy.props.IntProperty(name="Direction", default=1, options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        item = properties.find_map_setting_by_uuid(project, str(self.map_uuid or "").strip())
        if item is None:
            return {"CANCELLED"}
        prop_name = str(self.prop_name or "samples")
        if prop_name not in {"samples", "lighting_direct_samples"}:
            return {"CANCELLED"}
        current = int(getattr(item, prop_name, 0) or 0)
        stepped = _next_power_of_two_step(current, int(self.direction))
        # Assigning through the property runs its normal update chain (dirty
        # marking + speculative prepare), same as editing the field directly.
        # Blender clamps to the property's min/max on assignment.
        setattr(item, prop_name, stepped)
        return {"FINISHED"}


class MASTER_BAKER_OT_fit_attribute_range(bpy.types.Operator):
    bl_idname = "master_baker.fit_attribute_range"
    bl_label = "Fit Range"
    bl_description = "Set Min and Max to the lowest and highest value of this attribute across the project's high meshes"
    bl_options = {"INTERNAL", "UNDO"}

    map_uuid: bpy.props.StringProperty(name="Map UUID", default="", options={"HIDDEN"})

    def execute(self, context):
        from . import color_stream, mesh_read

        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        item = properties.find_map_setting_by_uuid(project, str(self.map_uuid or "").strip())
        if item is None:
            return {"CANCELLED"}
        name = str(getattr(item, "attribute_name", "") or "").strip()
        if not name:
            self.report({"WARNING"}, "Choose an attribute first")
            return {"CANCELLED"}
        depsgraph = context.evaluated_depsgraph_get()
        low = high = None
        for obj in properties.project_high_objects(project):
            # A cache-detached copy: reading attribute values from the evaluated mesh
            # itself would un-share its arrays for the rest of the session.
            with mesh_read.evaluated_mesh_copy(obj, depsgraph) as (_obj_eval, mesh):
                if mesh is None:
                    continue
                found = color_stream.attribute_value_range([mesh], name)
            if found is None:
                continue
            low = found[0] if low is None else min(low, found[0])
            high = found[1] if high is None else max(high, found[1])
        if low is None or high is None:
            self.report({"WARNING"}, f"No high mesh in this project has an attribute named '{name}'")
            return {"CANCELLED"}
        if high <= low:
            high = low + 1.0
        item.attribute_range_min = low
        item.attribute_range_max = high
        return {"FINISHED"}


class MASTER_BAKER_OT_bake_map(bpy.types.Operator):
    bl_idname = "master_baker.bake_map"
    bl_label = "Bake Map"
    bl_description = "Bake one output map for the active bake project"

    map_type: bpy.props.StringProperty(name="Map Type", default="")
    map_uuid: bpy.props.StringProperty(name="Map UUID", default="")

    @classmethod
    def description(cls, context, properties):
        scene = getattr(context, "scene", None)
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        from . import properties as _properties

        project = _properties.get_active_project(scene) if scene is not None else None
        map_uuid = str(getattr(properties, "map_uuid", "") or "").strip()
        if project is not None and map_uuid:
            map_setting = _properties.find_map_setting_by_uuid(project, map_uuid)
            if map_setting is not None:
                return f"Bake only the {naming.map_label(str(getattr(map_setting, 'map_type', '') or ''))} map for the active bake project"
        map_type = str(getattr(properties, "map_type", "") or "").strip().upper()
        if not map_type:
            map_type = str(getattr(settings, "preview_map_type", "") or "").strip().upper()
        if map_type:
            return f"Bake only the {naming.map_label(map_type)} map for the active bake project"
        return cls.bl_description

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        map_setting = None
        map_uuid = str(getattr(self, "map_uuid", "") or "").strip()
        if map_uuid:
            map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        if map_setting is None:
            map_type = str(self.map_type or getattr(settings, "preview_map_type", "") or "").strip().upper()
            if not map_type:
                self.report({"ERROR"}, "Choose a map to bake")
                return {"CANCELLED"}
            active_map = properties.peek_active_map(project)
            if active_map is not None and str(getattr(active_map, "map_type", "") or "").strip().upper() == map_type:
                map_setting = active_map
            else:
                map_setting = properties.find_map_setting(project, map_type)
        map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper() if map_setting is not None else ""
        if map_setting is None:
            self.report({"ERROR"}, f"Could not resolve the {naming.map_label(map_type)} map")
            return {"CANCELLED"}
        map_uuid = properties.ensure_map_setting_uuid(map_setting)
        effective_label_type = export.effective_map_type_for_setting(map_setting)
        label = naming.map_label(effective_label_type)
        return _run_bake(
            self,
            context,
            project,
            map_types=[map_type],
            map_uuids=[map_uuid],
            start_message=f"{label} bake started",
            initial_status=f"Baking {label}",
        )


class MASTER_BAKER_OT_cycles_bake_step(bpy.types.Operator):
    """Modal driver for a Cycles-primary bake — one Cycles bake pass per timer tick.

    Not user-invoked: `_run_cycles_primary_bake` (Route = Cycles) and
    `_start_cycles_handoff_async` (the automatic retry after a GPU failure) seed
    `_CYCLES_ASYNC_STATE` and launch this. Every event except TIMER passes through so
    Blender stays usable between passes, and ESC cancels either kind of run (a map
    stopped between its passes is discarded, never written half-composed).
    """

    bl_idname = "master_baker.cycles_bake_step"
    bl_label = "Bake via Cycles"
    bl_options = {"INTERNAL"}

    _timer = None

    def invoke(self, context, _event):
        if _CYCLES_ASYNC_STATE is None:
            return {"CANCELLED"}
        wm = context.window_manager
        # A recovery is launched from the bake poll timer, whose context does not always
        # carry a window even though one exists. Fall back to the manager's first window
        # rather than failing the retry.
        window = getattr(context, "window", None)
        if window is None:
            windows = list(getattr(wm, "windows", None) or [])
            window = windows[0] if windows else None
        if window is None:
            return {"CANCELLED"}
        self._timer = wm.event_timer_add(_CYCLES_ASYNC_TIMER_INTERVAL, window=window)
        # Without a handler the timer would tick into nothing and the run would sit at 0%
        # forever, so a refused handler has to fail the launch rather than look started.
        if wm.modal_handler_add(self) is False:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        state = _CYCLES_ASYNC_STATE
        if state is None:
            return self._teardown(context, None)
        if event.type == "ESC":
            state["cancel_requested"] = True
            export.cancel_material_bakes(_cycles_state_job_id(state))
            return self._teardown(context, state)
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        if state.get("cancel_requested"):
            # The material queue runs on its own timer; a cancel has to reach it, and
            # the driver must not tear down while it is still holding bake nodes and
            # unhidden objects.
            if state.get("material_pending"):
                export.cancel_material_bakes(_cycles_state_job_id(state))
                return {"RUNNING_MODAL"}
            return self._teardown(context, state)

        # Stage 1: the material queue. Started here rather than in
        # _run_cycles_primary_bake so its first Blender bake is invoked from a modal
        # context that actually has a window.
        if state.get("material_pending"):
            if not state.get("material_started"):
                _start_cycles_material_stage(context, state)
            return {"RUNNING_MODAL"}

        plan = state["plan"]
        index = int(state.get("index", 0))
        if index >= len(plan.steps):
            return self._teardown(context, state)

        # Two-phase tick, one Cycles bake PASS per run tick. A pass blocks the main
        # thread, and Blender only redraws once modal() returns, so publishing
        # progress and baking in the same tick left the bar on the PREVIOUS unit (0%
        # for the whole first map). Progress for a pass is therefore published in one
        # tick and the pass runs in the next, so the frame naming it is drawn before
        # it blocks. A multi-pass map (Height, Bent Normal) keeps its CyclesMapJob in
        # state["active_job"] across ticks, which is also what lets ESC land between
        # its passes.
        step = plan.steps[index]
        job = state.get("active_job")
        pass_index = int(getattr(job, "passes_done", 0) or 0) if job is not None else 0
        if state.get("announced") != (index, pass_index):
            self._announce_pass(state, index, pass_index)
            return {"RUNNING_MODAL"}

        map_done = _cycles_run_one_pass(state, step, plan.device)
        if map_done:
            state["index"] = index + 1
        # Announce the next pass on the way out, so it is on screen before the next
        # tick bakes it without spending an idle tick per pass.
        if state.get("cancel_requested"):
            return {"RUNNING_MODAL"}
        if not map_done:
            self._announce_pass(state, index, int(state["active_job"].passes_done))
        elif index + 1 < len(plan.steps):
            self._announce_pass(state, index + 1, 0)
        return {"RUNNING_MODAL"}

    @staticmethod
    def _announce_pass(state: dict, index: int, pass_index: int) -> None:
        _cycles_step_progress(state, state["plan"].steps[index], index, pass_index)
        state["announced"] = (index, pass_index)

    def cancel(self, context):
        """Blender-side cancel (file load, window close, an exception in modal()).

        Blender does not call modal() on that path, so without this hook the wm timer
        and _CYCLES_ASYNC_STATE both outlive the run and every later Cycles bake is
        refused with "A Cycles bake is already running" for the rest of the session.
        """
        global _CYCLES_ASYNC_STATE
        state = _CYCLES_ASYNC_STATE
        if state is not None:
            state["cancel_requested"] = True
            # A map paused between its passes still holds temp images and a UV
            # offset; nothing else will ever release them on this path.
            _abort_cycles_active_job(state)
            try:
                export.cancel_material_bakes(_cycles_state_job_id(state))
            except Exception:
                pass
            try:
                _clear_pending_material_phase()
            except Exception:
                pass
        wm = context.window_manager
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        _CYCLES_ASYNC_STATE = None

    def _teardown(self, context, state):
        global _CYCLES_ASYNC_STATE
        wm = context.window_manager
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        _CYCLES_ASYNC_STATE = None
        if state is None:
            return {"CANCELLED"}
        # ESC / Stop between two passes of a map: release its temporaries before the
        # finalizer reports, and write nothing for it (the output is only saved after
        # the map's last pass). A no-op when no map is in flight.
        _abort_cycles_active_job(state)
        # A Cycles-primary bake owns its whole job and finalizes it; a recovery is the
        # tail of a failed GPU bake and hands its outcome back to that bake's caller.
        finalize = state.get("finalize")
        if not callable(finalize):
            finalize = _finalize_cycles_primary_bake
        return finalize(self, context, state)


class MASTER_BAKER_OT_dismiss_progress_overlay(bpy.types.Operator):
    """Hide the bottom-center viewport progress card.

    Separate from Cancel on purpose: this only removes the card, it does not touch
    the bake. It exists because the card is derived state — a worker that dies
    without publishing a final progress write, or a setup path that raises between
    begin() and end(), leaves it on screen with nothing left to take it down.
    """

    bl_idname = "master_baker.dismiss_progress_overlay"
    bl_label = "Hide Progress Overlay"
    bl_description = (
        "Hide the progress card in the viewport. Does not stop the bake. "
        "Use Stop for that. The card returns on the next bake"
    )
    # No UNDO: touches no blend data (see add_project on the memfile-undo crash).
    bl_options = {"REGISTER"}

    def execute(self, context):
        from . import setup_progress

        if not setup_progress.force_dismiss():
            self.report({"INFO"}, "No progress overlay is showing")
            return {"CANCELLED"}
        overlays.tag_redraw_all_view3d(scene=getattr(context, "scene", None))
        self.report({"INFO"}, "Progress overlay hidden")
        return {"FINISHED"}


class MASTER_BAKER_OT_cancel_bake(bpy.types.Operator):
    bl_idname = "master_baker.cancel_bake"
    bl_label = "Cancel Bake"
    bl_description = "Stop the bake that is currently running"
    # No UNDO: stopping a bake is not an edit, so it must not push an undo step the
    # artist can Ctrl+Z back into (there is nothing to undo -- the worker is already
    # stopping). It also writes project status fields, and a memfile-undo step over
    # those reallocs fyr_baker_settings mid-bake (see add_project on T74067).
    bl_options = {"REGISTER"}

    def execute(self, context):
        global _DEFERRED_BAKE_STATE
        _dismiss_setup_progress()
        if request_cycles_async_cancel():
            project = properties.peek_active_project(context.scene)
            if project is not None:
                project.last_status_message = constants.STATUS_CANCELLING
            context.scene.fyr_baker_settings.status_message = constants.STATUS_CANCELLING
            self.report({"INFO"}, "Stopping after the current pass (Cycles)")
            return {"FINISHED"}
        if _DEFERRED_BAKE_STATE is not None:
            _DEFERRED_BAKE_STATE["cancel_requested"] = True
            _DEFERRED_BAKE_STATE = None
            _end_deferred_bake_feedback()
            project = properties.peek_active_project(context.scene)
            if project is not None:
                project.last_status_message = constants.STATUS_CANCELLED
            context.scene.fyr_baker_settings.status_message = constants.STATUS_CANCELLED
            self.report({"INFO"}, constants.STATUS_CANCELLED)
            return {"FINISHED"}
        snapshot = runtime.active_bake_snapshot()
        if snapshot is None or not snapshot.running:
            # The backend can finish while Blender's material queue is still running;
            # that queue is part of the same bake, so Stop has to reach it too.
            material_status = export.active_material_bake_status()
            if material_status is None:
                self.report({"ERROR"}, "No background bake is running")
                return {"CANCELLED"}
            export.cancel_material_bakes(material_status.job_id)
            scene, settings, project = _find_project_record_by_job_id(material_status.job_id)
            if project is not None:
                project.last_status_message = constants.STATUS_CANCELLING
                settings.status_message = constants.STATUS_CANCELLING
                overlays.tag_redraw_all_view3d(scene=scene, window=getattr(context, "window", None))
            self.report({"INFO"}, "Requested material bake cancellation")
            return {"FINISHED"}

        # A cancel lands at the worker's next checkpoint. That is usually seconds, but
        # on a slow machine it is long enough that Stop reads as broken and the user
        # presses it again. Take the second press literally: stop the worker now.
        already_pending = runtime.bake_cancel_is_pending()
        runtime.cancel_active_bake(force=already_pending)
        export.cancel_material_bakes(snapshot.job_id)
        scene, settings, project = _find_project_record_by_job_id(snapshot.job_id)
        if project is not None:
            project.last_status_message = constants.STATUS_CANCELLING
            settings.status_message = constants.STATUS_CANCELLING
            overlays.tag_redraw_all_view3d(scene=scene, window=getattr(context, "window", None))
        if already_pending:
            self.report({"WARNING"}, "Force stopping the bake worker")
        else:
            self.report({"INFO"}, "Requested bake cancellation")
        return {"FINISHED"}


def _available_map_type_items(_self, context):
    items = list(constants.MAP_TYPE_ITEMS)
    items.append(None)  # separator
    for shortcut_id, channel in constants.MATERIAL_SHORTCUT_TO_CHANNEL.items():
        label = constants.MAP_LABELS.get(shortcut_id, shortcut_id)
        items.append((shortcut_id, label, f"Add a Material map baking {label}"))
    items.append((
        constants.SHORTCUT_DERIVATIVE,
        constants.MAP_LABELS[constants.SHORTCUT_DERIVATIVE],
        "Add a tangent Normal row that writes a derivative map",
    ))
    return items



class MASTER_BAKER_OT_add_map(bpy.types.Operator):
    bl_idname = "master_baker.add_map"
    bl_label = "Add Output Map"
    bl_description = "Add a new output map entry to the active bake project"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    map_type: bpy.props.EnumProperty(name="Map", items=_available_map_type_items)

    def draw(self, context):

        self.layout.prop(self, "map_type", text="Map")

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        map_type_id = self.map_type
        material_channel = None
        derivative = map_type_id == constants.SHORTCUT_DERIVATIVE
        if derivative:
            map_type_id = constants.MAP_NORMAL

        # Translate material shortcut identifiers (_MAT_*) ? MAP_MATERIAL + channel
        if str(map_type_id or "").startswith(constants.MATERIAL_SHORTCUT_PREFIX):
            channel = constants.MATERIAL_SHORTCUT_TO_CHANNEL.get(map_type_id)
            if channel is None:
                self.report({"ERROR"}, "Unknown material shortcut")
                return {"CANCELLED"}
            map_type_id = constants.MAP_MATERIAL
            material_channel = channel

        valid_map_types = {item[0] for item in constants.MAP_TYPE_ITEMS}
        if map_type_id not in valid_map_types:
            self.report({"ERROR"}, "Select a valid output map")
            return {"CANCELLED"}

        item = properties.add_map_setting(project, map_type_id)
        if material_channel is not None:
            item.material_channel = material_channel
        if derivative:
            item.normal_space = constants.MAP_NORMAL_SPACE_TANGENT
            item.normal_encoding = constants.NORMAL_ENCODING_DERIVATIVE

        item.enabled = True  # fires _map_enabled_update ? marks dirty for live bake
        project.active_map_index = max(len(project.maps) - 1, 0)
        channel_label = naming.map_label(material_channel) if material_channel else ""
        display_label = f"{naming.map_label(item.map_type)}: {channel_label}" if channel_label else naming.map_label(
            naming.effective_map_type_for_setting(item)
        )
        project.last_status_message = f"Added {display_label} to the map stack"
        context.scene.fyr_baker_settings.status_message = "Updated map stack"
        return {"FINISHED"}


class MASTER_BAKER_OT_remove_map(bpy.types.Operator):
    bl_idname = "master_baker.remove_map"
    bl_label = "Remove Output Map"
    bl_description = "Remove this map from the stack. Restore is offered until the next change"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    map_index: bpy.props.IntProperty(name="Map Index", default=-1)

    def execute(self, context):
        project = _active_project_or_report(self, context)

        if project is None:
            return {"CANCELLED"}

        if self.map_index >= 0:
            project.active_map_index = self.map_index

        # remove_active_map() strips phantom rows first, which can shift the active
        # index. Do it up front so the index we stash is the one the restored row
        # has to come back to.
        properties.remove_phantom_map_items(project)
        map_item = properties.peek_active_map(project)

        if map_item is None:
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}
        map_label = naming.map_label(map_item.map_type)
        # The whole row travels, uuid included, so the restored map keeps its tracked
        # outputs and its position in the stack rather than reappearing at the bottom
        # with default settings.
        _stash_removed_item(
            runtime.STASH_KIND_MAP,
            lambda: preset_store.map_row_to_payload(map_item),
            label=f"Undo Remove '{map_label}'" if map_label else "Undo Remove Map",
            location={
                "project_name": str(getattr(project, "name", "") or ""),
                "index": int(properties.resolve_active_index(getattr(project, "active_map_index", 0), len(project.maps)) or 0),
            },
        )
        if not properties.remove_active_map(project):
            runtime.clear_removed_item_stash()
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}
        project.last_status_message = f"Removed {map_label} map. Use Undo Remove to restore"
        context.scene.fyr_baker_settings.status_message = "Updated map stack"
        _tag_redraw_every_area(context)
        return {"FINISHED"}


class MASTER_BAKER_OT_duplicate_map(bpy.types.Operator):
    bl_idname = "master_baker.duplicate_map"
    bl_label = "Duplicate Output Map"
    bl_description = "Add a copy of this map directly below it with a unique output name"
    bl_options = {"REGISTER"}  # see add_project: avoid memfile-undo realloc crash (T74067)

    map_index: bpy.props.IntProperty(name="Map Index", default=-1)

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        index = int(self.map_index) if int(self.map_index) >= 0 else int(getattr(project, "active_map_index", 0) or 0)
        maps = getattr(project, "maps", [])
        if index < 0 or index >= len(maps):
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}

        source = maps[index]
        if getattr(source, "is_add_phantom", False):
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}

        copy = properties.duplicate_map_setting(project, source)
        if copy is None:
            self.report({"ERROR"}, "Could not duplicate the selected output map")
            return {"CANCELLED"}

        map_label = naming.map_label(getattr(copy, "map_type", ""))
        project.last_status_message = f"Duplicated {map_label}"
        context.scene.fyr_baker_settings.status_message = "Updated map stack"
        return {"FINISHED"}


class MASTER_BAKER_OT_move_map(bpy.types.Operator):
    bl_idname = "master_baker.move_map"
    bl_label = "Move Map"
    bl_description = "Move the selected output map up or down in the stack"
    # No UNDO: this REORDERS project.maps, and a memfile-undo step over a resized /
    # reshuffled fyr_baker_settings collection dangles retained panel buttons bound to
    # its rows (see add_project on T74067). Moving a row back is one click anyway.
    bl_options = {"REGISTER"}

    map_index: bpy.props.IntProperty(name="Map Index", default=-1, options={"HIDDEN"})
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
        default="UP",
        options={"HIDDEN"},
    )

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        index = self.map_index if self.map_index >= 0 else project.active_map_index
        count = len(project.maps)
        if count < 2:
            return {"CANCELLED"}
        if self.direction == "UP":
            neighbor = index - 1
        else:
            neighbor = index + 1
        if neighbor < 0 or neighbor >= count:
            return {"CANCELLED"}
        project.maps.move(index, neighbor)
        project.active_map_index = neighbor
        return {"FINISHED"}


class MASTER_BAKER_OT_restore_map_defaults(bpy.types.Operator):
    bl_idname = "master_baker.restore_map_defaults"
    bl_label = "Restore Map Defaults"
    bl_description = "Restore the selected map entry to its default settings for this project"
    bl_options = {"REGISTER", "UNDO"}

    map_type: bpy.props.StringProperty(name="Map Type", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        normalized_map_type = str(getattr(self, "map_type", "") or "").strip().upper()
        map_item = properties.find_map_setting(project, normalized_map_type) if normalized_map_type else properties.peek_active_map(project)
        if map_item is None:
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}

        properties.reset_map_setting(project, map_item)
        _sync_preview_material_for_project(context.scene, project)
        label = naming.map_label(getattr(map_item, "map_type", ""))
        project.last_status_message = f"Restored {label} defaults"
        context.scene.fyr_baker_settings.status_message = project.last_status_message
        self.report({"INFO"}, project.last_status_message)
        return {"FINISHED"}


def _map_setting_property_label(property_name: str) -> str:
    labels = {
        "ao_mode": "Method",
        "ao_distance": "Max Distance",
        "ao_min_distance": "Min Distance",
        "ao_ignore_groups": "Ignore Groups",
        "ao_ignore_backface": "Ignore Backface",
        "ao_two_sided": "Two-Sided",
        "ao_bevel_normal": "Use Bevel Normal",
        "curvature_bevel_mask": "Bevel Mask",
        "ao_use_ground_plane": "Ground Plane",
        "ao_ground_plane_offset": "Ground Offset",
        "ao_diffusion_quality": "Quality",
        "ao_diffusion_clearance_scale": "Clearance Scale",
        "ao_diffusion_clearance_exponent": "Clearance Exponent",
        "curvature_relative_to_bounding_box": "Relative to Bounds",
        "curvature_detect_folds": "Detect Folds",
        "curvature_self_intersection": "Self Intersection",
        "curvature_secondary_rays": "Secondary Rays",
        "curvature_auto_tonemapping": "Auto Tonemapping",
        "curvature_value_min": "Value Bounds Min",
        "curvature_value_max": "Value Bounds Max",
        "curvature_method": "Method",
        "curvature_soften": "Soften",
        "soften_override": "Override Soften",
        "denoising_enabled": "Denoising",
        "env_light_up_axis": "Up Axis",
        "id_source": "Source",
        "normal_format": "Normal Format",
        "normal_space": "Normal Space",
        "output_suffix": "Output Suffix",
        "position_normalization": "Method",
        "position_mode": "Mode",
        "position_axis": "Axis",
        "samples": "Rays",
        "thickness_ignore_groups": "Ignore Groups",
        "thickness_min_distance": "Thickness Min Distance",
    }
    normalized_property_name = str(property_name or "").strip()
    if normalized_property_name in labels:
        return labels[normalized_property_name]
    return normalized_property_name.replace("_", " ").title() or "Setting"


class MASTER_BAKER_OT_reset_map_setting(bpy.types.Operator):
    bl_idname = "master_baker.reset_map_setting"
    bl_label = "Reset Map Setting"
    bl_description = "Reset this map setting to its default value"
    bl_options = {"REGISTER", "UNDO"}

    map_type: bpy.props.StringProperty(name="Map Type", default="", options={"HIDDEN"})
    property_name: bpy.props.StringProperty(name="Property Name", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties_):
        property_label = _map_setting_property_label(getattr(properties_, "property_name", ""))
        map_type = str(getattr(properties_, "map_type", "") or "").strip().upper()
        map_label = naming.map_label(map_type) if map_type else "map"
        return f"Reset {property_label} on {map_label} to its default value"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        normalized_map_type = str(getattr(self, "map_type", "") or "").strip().upper()
        property_name = str(getattr(self, "property_name", "") or "").strip()
        map_item = properties.find_map_setting(project, normalized_map_type) if normalized_map_type else properties.peek_active_map(project)
        if map_item is None:
            self.report({"ERROR"}, "No output map is selected")
            return {"CANCELLED"}
        if not property_name:
            self.report({"ERROR"}, "No map setting was specified")
            return {"CANCELLED"}
        if not properties.reset_map_setting_value(project, map_item, property_name):
            self.report({"ERROR"}, f"Could not reset {_map_setting_property_label(property_name)}")
            return {"CANCELLED"}

        _sync_preview_material_for_project(context.scene, project)
        label = naming.map_label(getattr(map_item, "map_type", ""))
        project.last_status_message = f"Reset {_map_setting_property_label(property_name)} on {label}"
        context.scene.fyr_baker_settings.status_message = project.last_status_message
        return {"FINISHED"}


_LOW_SAMPLE_WARNING_DIALOG_ACTIVE = False


def _find_map_setting_in_scenes(map_uuid: str):
    normalized_uuid = str(map_uuid or "").strip()
    if not normalized_uuid:
        return None
    for scene in getattr(getattr(bpy, "data", None), "scenes", []):
        settings = getattr(scene, "fyr_baker_settings", None)
        for project in getattr(settings, "projects", []):
            map_item = properties.find_map_setting_by_uuid(project, normalized_uuid)
            if map_item is not None:
                return map_item
    return None


def _low_sample_warning_timer():
    if _LOW_SAMPLE_WARNING_DIALOG_ACTIVE:
        return 0.1

    context = getattr(bpy, "context", None)
    window_manager = getattr(context, "window_manager", None)
    windows = list(getattr(window_manager, "windows", []) or [])
    if not windows:
        return 0.5

    request = properties.pop_low_sample_warning_request()
    if request is None:
        return 0.1

    map_uuid, proposed_samples, previous_samples = request
    map_item = _find_map_setting_in_scenes(map_uuid)
    if map_item is None:
        return 0.1

    prefs = preferences.get_preferences()
    if prefs is not None and not bool(getattr(prefs, "warn_low_sample_count", True)):
        properties.confirm_low_sample_count(map_item, proposed_samples)
        return 0.1

    try:
        with context.temp_override(window=windows[0]):
            bpy.ops.master_baker.confirm_low_sample_count(
                "INVOKE_DEFAULT",
                map_uuid=map_uuid,
                proposed_samples=proposed_samples,
                previous_samples=previous_samples,
            )
    except Exception:
        properties.set_map_samples_without_warning(map_item, previous_samples)
    return 0.1


class MASTER_BAKER_OT_confirm_low_sample_count(bpy.types.Operator):
    bl_idname = "master_baker.confirm_low_sample_count"
    bl_label = "Low Sample Count"
    bl_description = "Confirm a sample count that may produce noisy output"
    bl_options = {"INTERNAL"}

    map_uuid: bpy.props.StringProperty(name="Map UUID", default="", options={"HIDDEN"})
    proposed_samples: bpy.props.IntProperty(name="Proposed Samples", default=1, options={"HIDDEN"})
    previous_samples: bpy.props.IntProperty(
        name="Previous Samples",
        default=constants.MAP_RECOMMENDED_SAMPLES,
        options={"HIDDEN"},
    )
    choice: bpy.props.EnumProperty(
        name="Action",
        items=(
            ("KEEP", "Keep Current Count", "Use the selected low sample count"),
            (
                "RESET",
                f"Restore Recommended ({constants.MAP_RECOMMENDED_SAMPLES})",
                "Return to the recommended default sample count",
            ),
        ),
        default="RESET",
    )
    dont_show_again: bpy.props.BoolProperty(name="Don't show this warning again", default=False)

    def invoke(self, context, event):
        global _LOW_SAMPLE_WARNING_DIALOG_ACTIVE
        _LOW_SAMPLE_WARNING_DIALOG_ACTIVE = True
        try:
            return context.window_manager.invoke_props_dialog(
                self,
                width=430,
                title="Low Sample Count",
                confirm_text="Apply Choice",
            )
        except Exception:
            _LOW_SAMPLE_WARNING_DIALOG_ACTIVE = False
            raise

    def draw(self, context):
        layout = self.layout
        warning = layout.column(align=True)
        warning.label(
            text=f"Sample counts below {constants.MAP_LOW_SAMPLE_WARNING_THRESHOLD} can produce visibly noisy results.",
            icon="ERROR",
        )
        warning.label(text=f"Current count: {self.proposed_samples}")
        layout.separator()
        layout.prop(self, "choice", expand=True)
        layout.separator()
        layout.prop(self, "dont_show_again")

    def execute(self, context):
        global _LOW_SAMPLE_WARNING_DIALOG_ACTIVE
        map_item = _find_map_setting_in_scenes(self.map_uuid)
        if map_item is None:
            properties.cancel_low_sample_count_warning(self.map_uuid)
            _LOW_SAMPLE_WARNING_DIALOG_ACTIVE = False
            self.report({"ERROR"}, "The map setting is no longer available")
            return {"CANCELLED"}

        if self.choice == "RESET":
            properties.set_map_samples_without_warning(map_item, constants.MAP_RECOMMENDED_SAMPLES)
        else:
            properties.confirm_low_sample_count(map_item, self.proposed_samples)

        if self.dont_show_again:
            prefs = preferences.get_preferences()
            if prefs is not None:
                prefs.warn_low_sample_count = False
        _LOW_SAMPLE_WARNING_DIALOG_ACTIVE = False
        return {"FINISHED"}

    def cancel(self, context):
        global _LOW_SAMPLE_WARNING_DIALOG_ACTIVE
        map_item = _find_map_setting_in_scenes(self.map_uuid)
        if map_item is not None:
            properties.set_map_samples_without_warning(map_item, self.previous_samples)
        else:
            properties.cancel_low_sample_count_warning(self.map_uuid)
        _LOW_SAMPLE_WARNING_DIALOG_ACTIVE = False


class MASTER_BAKER_OT_apply_map_stack_preset(bpy.types.Operator):
    bl_idname = "master_baker.apply_map_stack_preset"
    bl_label = "Apply Map Stack Preset"
    # No UNDO: applying a stack ADDS the map rows the preset names (ensure_default_maps
    # + _ensure_map_setting), so it is structural churn of project.maps, not a scalar
    # edit (see add_project on T74067).
    bl_options = {"REGISTER"}

    preset: bpy.props.EnumProperty(name="Map Stack Preset", items=constants.MAP_STACK_ITEMS)

    @classmethod
    def description(cls, _context, properties):
        preset = getattr(properties, "preset", "")
        return f"Enable the maps used by the {preset.replace('_', ' ').title()} preset"

    def execute(self, context):
        # The artist has moved past any pending removal, so retire the Undo Remove
        # offer (see add_project: leaving it armed restores next to a live item).
        runtime.clear_removed_item_stash()
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        # Guard the same case the popover hides (ui.MASTER_BAKER_PT_configure_maps):
        # these stacks name geometry map types, and applying one to a material
        # project would disable its MATERIAL channel rows.
        if str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL:
            self.report({"ERROR"}, "Map stack presets do not apply to a material bake project")
            return {"CANCELLED"}
        properties.ensure_default_maps(project)
        try:
            with properties.suppress_low_sample_warning():
                label = quality.apply_map_stack_preset(project, self.preset)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        project.last_status_message = f"Applied {label}"
        context.scene.fyr_baker_settings.status_message = f"{label} map stack ready"
        return {"FINISHED"}


class MASTER_BAKER_OT_refresh_outputs(bpy.types.Operator):
    bl_idname = "master_baker.refresh_outputs"
    bl_label = "Refresh Outputs"
    bl_description = "Reload the outputs recorded by the most recent bake"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        # last_workspace_path is stamped by EVERY prepare, speculative background
        # ones included, so after any settings change it points at a prepare-only
        # workspace whose progress.json says "Bake workspace exported" (and which
        # the workspace prune may already have swept). The bake pointer is the one
        # that holds outputs; fall back to the prepare pointer only without it.
        workspace_path = str(getattr(project, "last_bake_workspace_path", "") or "").strip() or str(
            project.last_workspace_path or ""
        ).strip()
        if not workspace_path:
            self.report({"ERROR"}, "No prior workspace found for this project")
            return {"CANCELLED"}
        progress_path = Path(workspace_path) / "progress.json"
        if not progress_path.exists():
            self.report({"ERROR"}, f"Progress file was not found: {progress_path}")
            return {"CANCELLED"}

        progress = load_progress(progress_path)
        export.apply_progress_to_project(project, progress, merge_existing=bool(project.latest_outputs))
        runtime.refresh_project_output_images(project)
        _sync_preview_material_for_project(context.scene, project)
        context.scene.fyr_baker_settings.status_message = progress.message or progress.status
        self.report({"INFO"}, "Refreshed latest output list")
        return {"FINISHED"}


class MASTER_BAKER_OT_open_output_folder(bpy.types.Operator):
    bl_idname = "master_baker.open_output_folder"
    bl_label = "Open Output Folder"
    bl_description = "Open the current output folder for the active bake project"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        target = str(project.last_output_dir or "").strip()
        if not target or not os.path.isdir(target):
            # The recorded folder was moved or deleted after the bake; the resolved
            # root is created on demand, so it always opens.
            target = str(export.resolve_output_root(project)[0])
        try:
            bpy.ops.wm.path_open(filepath=target)
        except Exception as exc:
            self.report({"ERROR"}, f"Could not open the output folder: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_copy_output_path(bpy.types.Operator):
    bl_idname = "master_baker.copy_output_path"
    bl_label = "Copy Output Path"

    filepath: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        path = str(getattr(properties, "filepath", "") or "")
        return f"Copy the resolved output folder to the clipboard:\n{path}"

    def execute(self, context):
        path = str(self.filepath or "").strip()
        if not path:
            self.report({"ERROR"}, "The resolved output folder is unavailable")
            return {"CANCELLED"}
        context.window_manager.clipboard = path
        self.report({"INFO"}, "Copied resolved output folder")
        return {"FINISHED"}


def _export_external_handoff_package(context, project, *, target):
    # The mesh export below swaps each low object's mesh datablock for a stripped
    # copy, which Blender refuses while that object is in Edit Mode, and Send To
    # lives in the Image Editor sidebar where the artist usually still is. Flush
    # Edit Mode for the export and restore it afterwards.
    with _object_mode_scope(context):
        return _export_external_handoff_package_in_object_mode(context, project, target=target)


def _handoff_group_texture_sets(project) -> dict:
    group_texture_sets = {}
    for group in getattr(project, "groups", []):
        metadata = properties.group_metadata_state(group)
        set_key = str(getattr(metadata, "texture_set_name", "") or "").strip()
        texture_set = properties.resolve_texture_set_output_name(project, set_key) if set_key else None
        texture_set = texture_set or str(getattr(group, "name", "") or "TextureSet")
        group_texture_sets[str(getattr(group, "name", "") or "")] = texture_set
    return group_texture_sets


def _export_external_handoff_package_in_object_mode(context, project, *, target):
    if not getattr(project, "latest_outputs", None):
        raise RuntimeError("No baked outputs are available. Bake or refresh outputs first")

    low_objects = []
    object_texture_sets = {}
    group_texture_sets = _handoff_group_texture_sets(project)
    for group in getattr(project, "groups", []):
        texture_set = group_texture_sets.get(str(getattr(group, "name", "") or "")) or str(getattr(group, "name", "") or "TextureSet")
        for slot in getattr(properties.group_role_assignments_state(group), "low_meshes", []):
            obj = getattr(slot, "object_ref", None)
            if obj is None or any(existing is obj for existing in low_objects):
                continue
            low_objects.append(obj)
            object_texture_sets[obj.name] = texture_set
    if not low_objects:
        raise RuntimeError("No low-poly meshes are assigned to this bake project")

    output_root = Path(str(getattr(project, "last_output_dir", "") or export.resolved_project_output_dir(project)))
    handoff_root = (
        output_root
        / "handoff"
        / external_handoff.sanitize_name(project.name, "asset")
        / external_handoff.sanitize_name(target, "external").lower()
    )
    handoff_root.mkdir(parents=True, exist_ok=True)
    # Designer and Mari need a mesh resource with texture-set materials. 3DCoat's
    # AppLink example is an OBJ opened straight into the paint room.
    mesh_extension = ".obj" if target in {"toolbag", "3dcoat"} else ".fbx"
    mesh_path = handoff_root / f"{external_handoff.sanitize_name(project.name, 'asset')}_low{mesh_extension}"

    selected_before = list(getattr(context, "selected_objects", []) or [])
    active_before = getattr(context.view_layer.objects, "active", None)
    try:
        # select_all polls only in Object Mode; Send To is offered from the Image
        # Editor sidebar where the artist is usually still in Edit Mode.
        _select_objects_in_view_layer(context, low_objects, active_object=low_objects[0])
        if target not in {"toolbag", "3dcoat"}:
            data_snapshots = []
            temporary_materials = []
            for obj in low_objects:
                original_data = obj.data
                export_data = original_data.copy()
                obj.data = export_data
                export_data.materials.clear()
                material_name = external_handoff.sanitize_name(object_texture_sets[obj.name])
                material = bpy.data.materials.get(material_name)
                if material is None:
                    material = bpy.data.materials.new(material_name)
                    temporary_materials.append(material)
                export_data.materials.append(material)
                for polygon in export_data.polygons:
                    polygon.material_index = 0
                data_snapshots.append((obj, original_data, export_data))
            try:
                bpy.ops.export_scene.fbx(
                    filepath=str(mesh_path),
                    use_selection=True,
                    use_mesh_modifiers=True,
                    object_types={"MESH"},
                    add_leaf_bones=False,
                    bake_anim=False,
                    path_mode="AUTO",
                )
            finally:
                for obj, original_data, export_data in data_snapshots:
                    obj.data = original_data
                    bpy.data.meshes.remove(export_data)
                for material in temporary_materials:
                    if material.users == 0:
                        bpy.data.materials.remove(material)
        else:
            bpy.ops.wm.obj_export(
                filepath=str(mesh_path),
                export_selected_objects=True,
                apply_modifiers=True,
                export_materials=False,
            )
    finally:
        _deselect_all_in_view_layer(context)
        for obj in selected_before:
            try:
                obj.select_set(True)
            except ReferenceError:
                pass
        context.view_layer.objects.active = active_before

    normal_row = properties.find_map_setting(project, constants.MAP_NORMAL)
    package = external_handoff.build_package(
        root=handoff_root,
        mesh_path=mesh_path,
        outputs=project.latest_outputs,
        group_texture_sets=group_texture_sets,
        # Painter decodes the baked Normal through its project-level format, so the
        # created project must match the row (an explicit OpenGL choice included).
        normal_map_format=(
            properties.effective_normal_format(normal_row)
            if normal_row is not None
            else constants.default_normal_format_for_map(constants.MAP_NORMAL)
        ),
        # Painter and Marmoset need copies beside the mesh. The editing apps link
        # the bake files where they already are.
        stage_maps=target in {"painter", "toolbag"},
    )
    if target == "toolbag":
        mtl_path = external_handoff.write_toolbag_mtl(package)
        external_handoff.rewrite_obj_materials(mesh_path, object_texture_sets, mtl_path)
    return package


def _external_handoff_status_reporter(context):
    """Report a deferred handoff outcome to the panel status line.

    The Painter launch finishes on an app timer, long after the operator returned,
    so there is no ``self.report`` left to write to. The panel status message is
    the artist's feedback channel at that point.
    """
    scene_name = str(getattr(getattr(context, "scene", None), "name", "") or "")

    def _set_status(message, ok):
        text = str(message or "")
        try:
            scene = bpy.data.scenes.get(scene_name) if scene_name else None
            settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
            if settings is not None:
                settings.status_message = text
            overlays.tag_redraw_all_view3d(scene=scene)
        except Exception:
            pass
        print(f"[Fyr Baker] {text}")

    return _set_status


class MASTER_BAKER_OT_send_to_painter(bpy.types.Operator):
    bl_idname = "master_baker.send_to_painter"
    bl_label = "Send to Painter"
    bl_description = "Open the low-poly mesh in Substance 3D Painter and assign baked mesh maps to their matching texture sets"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        prefs = preferences.get_preferences()
        executable = external_handoff.resolve_application_executable(getattr(prefs, "painter_executable", ""), "painter")
        if executable is None:
            self.report({"ERROR"}, "Set the Substance 3D Painter executable in Fyr Baker preferences")
            return {"CANCELLED"}
        try:
            package = _export_external_handoff_package(context, project, target="painter")
            outcome = external_handoff.send_package_to_painter(
                executable,
                package,
                on_status=_external_handoff_status_reporter(context),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Painter handoff failed: {exc}")
            return {"CANCELLED"}
        if outcome == external_handoff.PAINTER_HANDOFF_LAUNCHING:
            # Painter needs seconds to come up; the maps are sent from a timer once
            # it answers, so the operator returns instead of freezing the UI.
            self.report({"INFO"}, "Starting Substance Painter")
        else:
            self.report({"INFO"}, f"Sent {len(package.maps)} baked map(s) to Painter")
        return {"FINISHED"}


class MASTER_BAKER_OT_update_in_painter(bpy.types.Operator):
    bl_idname = "master_baker.update_in_painter"
    bl_label = "Update in Painter"
    bl_description = "Reload the mesh in the open Painter project, preserve strokes, and refresh its baked mesh maps"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        prefs = preferences.get_preferences()
        executable = external_handoff.resolve_application_executable(getattr(prefs, "painter_executable", ""), "painter")
        if executable is None:
            self.report({"ERROR"}, "Set the Substance 3D Painter executable in Fyr Baker preferences")
            return {"CANCELLED"}
        try:
            package = _export_external_handoff_package(context, project, target="painter")
            # With Painter closed, Update launches it and sends from a timer like Send.
            outcome = external_handoff.send_package_to_painter(
                executable,
                package,
                update_existing=True,
                on_status=_external_handoff_status_reporter(context),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Painter update failed: {exc}")
            return {"CANCELLED"}
        if outcome == external_handoff.PAINTER_HANDOFF_LAUNCHING:
            self.report({"INFO"}, "Painter was not open. Starting Substance Painter")
        else:
            self.report({"INFO"}, "Updated baked maps in Painter and requested a mesh reload")
        return {"FINISHED"}


class MASTER_BAKER_OT_send_to_toolbag(bpy.types.Operator):
    bl_idname = "master_baker.send_to_toolbag"
    bl_label = "Send to Marmoset"
    bl_description = "Open the low-poly mesh in Marmoset Toolbag with baked PBR textures assigned to texture-set materials"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        prefs = preferences.get_preferences()
        executable = external_handoff.resolve_application_executable(getattr(prefs, "toolbag_executable", ""), "toolbag")
        if executable is None:
            self.report({"ERROR"}, "Set the Marmoset Toolbag executable in Fyr Baker preferences")
            return {"CANCELLED"}
        try:
            package = _export_external_handoff_package(context, project, target="toolbag")
            external_handoff.send_package_to_toolbag(executable, package)
        except Exception as exc:
            self.report({"ERROR"}, f"Marmoset handoff failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Sent mesh and {len(package.maps)} baked map(s) to Marmoset")
        return {"FINISHED"}


class MASTER_BAKER_OT_update_in_toolbag(bpy.types.Operator):
    bl_idname = "master_baker.update_in_toolbag"
    bl_label = "Update in Marmoset"
    bl_description = "Replace the open Toolbag mesh with the current Low and refresh assigned maps, without opening another Toolbag"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        prefs = preferences.get_preferences()
        executable = external_handoff.resolve_application_executable(getattr(prefs, "toolbag_executable", ""), "toolbag")
        if executable is None:
            self.report({"ERROR"}, "Set the Marmoset Toolbag executable in Fyr Baker preferences")
            return {"CANCELLED"}
        try:
            package = _export_external_handoff_package(context, project, target="toolbag")
            outcome = external_handoff.send_package_to_toolbag(executable, package, update_existing=True)
        except Exception as exc:
            self.report({"ERROR"}, f"Marmoset update failed: {exc}")
            return {"CANCELLED"}
        if outcome == external_handoff.TOOLBAG_HANDOFF_LAUNCHED:
            self.report({"INFO"}, f"Toolbag was not open. Opened it with the mesh and {len(package.maps)} baked map(s)")
        else:
            self.report({"INFO"}, f"Replaced the open Marmoset mesh and {len(package.maps)} texture file(s)")
        return {"FINISHED"}


class MASTER_BAKER_OT_send_to_photoshop(bpy.types.Operator):
    bl_idname = "master_baker.send_to_photoshop"
    bl_label = "Send to Photoshop"
    bl_description = "Open every baked map as a layer in one Photoshop document. Sending again replaces that document"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if not getattr(project, "latest_outputs", None):
            self.report({"ERROR"}, "No baked outputs are available. Bake or refresh outputs first")
            return {"CANCELLED"}
        prefs = preferences.get_preferences()
        executable = external_handoff.resolve_application_executable(getattr(prefs, "photoshop_executable", ""), "photoshop")
        if executable is None:
            self.report({"ERROR"}, "Set the Photoshop executable in Fyr Baker preferences")
            return {"CANCELLED"}
        output_root = Path(str(getattr(project, "last_output_dir", "") or export.resolved_project_output_dir(project)))
        asset_name = external_handoff.sanitize_name(getattr(project, "name", "") or "asset", "asset")
        psd_path = output_root / "handoff" / asset_name / "photoshop" / f"{asset_name}.psd"
        try:
            document = external_handoff.build_photoshop_document(
                project.latest_outputs,
                _handoff_group_texture_sets(project),
                document_name=str(getattr(project, "name", "") or "Bake"),
                psd_path=psd_path,
            )
            outcome = external_handoff.send_document_to_photoshop(
                executable,
                document,
                on_status=_external_handoff_status_reporter(context),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Photoshop handoff failed: {exc}")
            return {"CANCELLED"}
        count = len(document.layers)
        if outcome == external_handoff.PHOTOSHOP_HANDOFF_LAUNCHING:
            self.report({"INFO"}, f"Opening {count} baked map(s) in Photoshop")
        else:
            self.report({"INFO"}, f"Opened {count} baked map(s) in Photoshop")
        return {"FINISHED"}


def _send_editor_package(operator, context, *, target, application, preference_name, missing_message):
    project = _active_project_or_report(operator, context)
    if project is None:
        return None, None
    prefs = preferences.get_preferences()
    executable = external_handoff.resolve_application_executable(getattr(prefs, preference_name, ""), application)
    if executable is None:
        operator.report({"ERROR"}, missing_message)
        return None, None
    try:
        package = _export_external_handoff_package(context, project, target=target)
    except Exception as exc:
        operator.report({"ERROR"}, str(exc))
        return None, None
    return executable, package


class MASTER_BAKER_OT_send_to_designer(bpy.types.Operator):
    bl_idname = "master_baker.send_to_designer"
    bl_label = "Send to Designer"
    bl_description = "Add the baked maps and the low-poly mesh to the open Substance Designer project, or create a project when none is open"

    def execute(self, context):
        executable, package = _send_editor_package(
            self,
            context,
            target="designer",
            application="designer",
            preference_name="designer_executable",
            missing_message="Set the Substance Designer executable in Fyr Baker preferences",
        )
        if package is None:
            return {"CANCELLED"}
        try:
            outcome = editor_handoff.send_package_to_designer(
                executable,
                package,
                on_status=_external_handoff_status_reporter(context),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Designer handoff failed: {exc}")
            return {"CANCELLED"}
        count = len(package.maps)
        if outcome == external_handoff.PHOTOSHOP_HANDOFF_LAUNCHING:
            self.report({"INFO"}, f"Opening {count} baked map(s) in Substance Designer")
        else:
            self.report({"INFO"}, f"Sent {count} baked map(s) and the low-poly mesh to Substance Designer")
        return {"FINISHED"}


class MASTER_BAKER_OT_update_in_designer(bpy.types.Operator):
    bl_idname = "master_baker.update_in_designer"
    bl_label = "Update in Designer"
    bl_description = "Refresh the linked low-poly mesh and baked maps in the open Substance Designer project, without adding another copy"

    def execute(self, context):
        executable, package = _send_editor_package(
            self,
            context,
            target="designer",
            application="designer",
            preference_name="designer_executable",
            missing_message="Set the Substance Designer executable in Fyr Baker preferences",
        )
        if package is None:
            return {"CANCELLED"}
        try:
            editor_handoff.send_package_to_designer(
                executable,
                package,
                update_existing=True,
                on_status=_external_handoff_status_reporter(context),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Designer update failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Updated the low-poly mesh and {len(package.maps)} baked map(s) in Substance Designer")
        return {"FINISHED"}


class MASTER_BAKER_OT_send_to_3dcoat(bpy.types.Operator):
    bl_idname = "master_baker.send_to_3dcoat"
    bl_label = "Send to 3DCoat"
    bl_description = "Open the low-poly mesh in 3DCoat's paint room and assign the baked maps that 3DCoat has slots for"

    def execute(self, context):
        executable, package = _send_editor_package(
            self,
            context,
            target="3dcoat",
            application="3dcoat",
            preference_name="coat_executable",
            missing_message="Set the 3DCoat executable in Fyr Baker preferences",
        )
        if package is None:
            return {"CANCELLED"}
        try:
            editor_handoff.send_package_to_3dcoat(executable, package)
        except Exception as exc:
            self.report({"ERROR"}, f"3DCoat handoff failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Sent the low-poly mesh and {len(package.maps)} baked map(s) to 3DCoat")
        return {"FINISHED"}


class MASTER_BAKER_OT_send_to_mari(bpy.types.Operator):
    bl_idname = "master_baker.send_to_mari"
    bl_label = "Send to Mari"
    bl_description = "Open the low-poly mesh in Mari and import each baked map into a channel. An open Mari project receives the mesh"

    def execute(self, context):
        executable, package = _send_editor_package(
            self,
            context,
            target="mari",
            application="mari",
            preference_name="mari_executable",
            missing_message="Set the Mari executable in Fyr Baker preferences",
        )
        if package is None:
            return {"CANCELLED"}
        try:
            editor_handoff.send_package_to_mari(executable, package)
        except Exception as exc:
            self.report({"ERROR"}, f"Mari handoff failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Sent the low-poly mesh and {len(package.maps)} baked map(s) to Mari")
        return {"FINISHED"}


class MASTER_BAKER_OT_open_backend_log(bpy.types.Operator):
    bl_idname = "master_baker.open_backend_log"
    bl_label = "Open Backend Log"
    bl_description = "Open the current backend log in a copyable external window"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        log_path = runtime.project_backend_log_path(project, prefer_live=True, scene=context.scene)
        if log_path is None:
            self.report({"ERROR"}, "No backend log is available for this project")
            return {"CANCELLED"}

        opened = runtime.open_backend_log_window(
            log_path,
            title=f"Fyr Baker Backend Log: {project.name}",
            follow=bool(getattr(runtime.active_bake_snapshot(), "running", False) or runtime.debug_overlay_refresh_pending()),
        )
        if not opened:
            self.report({"ERROR"}, f"Could not open backend log window: {log_path}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Opened backend log: {log_path}")
        return {"FINISHED"}


class MASTER_BAKER_OT_open_gpu_diagnostics(bpy.types.Operator):
    bl_idname = "master_baker.open_gpu_diagnostics"
    bl_label = "Open GPU Diagnostics"
    bl_description = "Open the folder containing the GPU diagnostics log from the last bake"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        raw_workspace_path = str(getattr(project, "last_workspace_path", "") or "").strip()
        if not raw_workspace_path:
            self.report({"ERROR"}, "No bake workspace is available for this project")
            return {"CANCELLED"}
        logs_dir = Path(raw_workspace_path).expanduser() / "logs"
        if not logs_dir.exists():
            self.report({"ERROR"}, f"GPU diagnostics log directory not found: {logs_dir}")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=str(logs_dir))
        self.report({"INFO"}, f"Opened GPU diagnostics folder: {logs_dir}")
        return {"FINISHED"}


class MASTER_BAKER_OT_copy_failure_summary(bpy.types.Operator):
    bl_idname = "master_baker.copy_failure_summary"
    bl_label = "Copy Failure Summary"
    bl_description = "Copy details about the latest bake failure to the clipboard"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        state_text = str(getattr(project, "last_status_message", "") or constants.STATUS_IDLE)
        if state_text != constants.STATUS_FAILED and not int(getattr(project, "last_error_count", 0) or 0):
            self.report({"WARNING"}, "No recorded failure is available for this project")
            return {"CANCELLED"}

        log_path = runtime.project_backend_log_path(project, prefer_live=False, scene=context.scene)
        lines = [
            f"Project: {getattr(project, 'name', '')}",
            f"State: {state_text}",
            f"Job: {getattr(project, 'last_job_id', '') or 'None'}",
            f"Workspace: {getattr(project, 'last_workspace_path', '') or 'None'}",
            f"Outputs: {getattr(project, 'last_output_dir', '') or 'None'}",
            f"Errors: {int(getattr(project, 'last_error_count', 0) or 0)}",
            f"Warnings: {int(getattr(project, 'last_warning_count', 0) or 0)}",
        ]
        error_summary = str(getattr(project, "last_error_summary", "") or "").strip()
        warning_summary = str(getattr(project, "last_warning_summary", "") or "").strip()
        if error_summary:
            lines.append(f"Error Summary: {error_summary}")
        if warning_summary:
            lines.append(f"Warning Summary: {warning_summary}")
        if log_path is not None:
            lines.append(f"Backend Log: {log_path}")

        context.window_manager.clipboard = "\n".join(lines)
        self.report({"INFO"}, "Copied failure summary to clipboard")
        return {"FINISHED"}


def _write_bundle_blend_copy():
    """Save a throwaway copy of the current scene for the support bundle.

    The copy is taken from memory rather than reusing the file on disk, because the
    scene that reproduces a bug is the one the user is looking at, which is routinely
    ahead of the last save (or has never been saved at all). ``copy=True`` leaves the
    open file, its path and its dirty flag alone.

    Returns ``(temp_dir, blend_path, failure_message)``; ``blend_path`` is None when
    the save failed, and the caller still writes the rest of the bundle.
    """
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="mb_support_blend_"))
        source_name = Path(bpy.data.filepath).name or "untitled.blend"
        if not source_name.lower().endswith(".blend"):
            source_name = f"{source_name}.blend"
        blend_path = temp_dir / source_name
        bpy.ops.wm.save_as_mainfile(
            filepath=str(blend_path),
            copy=True,
            compress=True,
            # Keep relative texture paths pointing at the same files they do now, so
            # the copy still resolves its images from wherever the original lived.
            relative_remap=True,
        )
        if not blend_path.exists():
            return temp_dir, None, "Blender did not write the file"
        return temp_dir, blend_path, ""
    except Exception as exc:  # noqa: BLE001 - never lose the diagnostics over the extra file
        return temp_dir, None, str(exc) or exc.__class__.__name__


class MASTER_BAKER_OT_create_support_bundle(bpy.types.Operator):
    bl_idname = "master_baker.create_support_bundle"
    bl_label = "Create Support Bundle"
    bl_description = "Create a ZIP file containing the latest bake diagnostics and project information"
    bl_options = {"REGISTER"}

    include_blend_file: bpy.props.BoolProperty(
        name="Include .blend File",
        description=(
            "Add a copy of the current .blend file to the bundle. "
            "Some problems can only be reproduced from the scene itself. "
            "The bundle gets much larger, and the scene is shared with whoever you send it to"
        ),
        # Off by default: the scene is the user's work, and a bundle should never
        # carry it anywhere without the user having said so on this dialog.
        default=False,
    )

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, _context):
        layout = self.layout
        column = layout.column(align=True)
        column.prop(self, "include_blend_file")
        # The note stays readable whether or not the box is ticked: it is what the
        # user reads to decide, so greying it out would hide it exactly when needed.
        note = column.column(align=True)
        note.scale_y = 0.85
        note.label(text="A copy of the scene as it is right now, saved into the zip.")
        note.label(text="Your open file is not modified.")

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        if not (project.last_workspace_path or str(getattr(project, "last_bake_workspace_path", "") or "")):
            self.report({"ERROR"}, "No prior workspace found for this project")
            return {"CANCELLED"}

        extra_artifacts = []
        blend_temp_dir = None
        blend_failure = ""
        if self.include_blend_file:
            blend_temp_dir, blend_copy_path, blend_failure = _write_bundle_blend_copy()
            if blend_copy_path is not None:
                extra_artifacts.append((f"blend/{blend_copy_path.name}", blend_copy_path))

        try:
            bundle_path = runtime.write_support_bundle(project, extra_artifacts=extra_artifacts)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if blend_temp_dir is not None:
                shutil.rmtree(blend_temp_dir, ignore_errors=True)

        if blend_failure:
            self.report({"WARNING"}, f"Bundle written without the .blend file: {blend_failure}")

        # Say so when the bundle documents no bake, rather than letting the user send
        # a superficially complete zip that cannot answer the question they were asked.
        documents_a_bake = True
        try:
            import json as _json
            import zipfile as _zipfile

            with _zipfile.ZipFile(bundle_path) as archive:
                manifest = _json.loads(archive.read("support_bundle.json"))
            documents_a_bake = bool(manifest.get("bake_evidence", {}).get("documents_a_bake", True))
        except Exception:
            pass
        if not documents_a_bake:
            self.report(
                {"WARNING"},
                "This bundle has no bake in it. Run a bake, then create the bundle again.",
            )

        # Say how big it is. A bundle with the scene in it can run to hundreds of MB,
        # and the user is about to try to send it somewhere.
        try:
            size_bytes = bundle_path.stat().st_size
            size_label = (
                f" ({size_bytes / (1024 * 1024):.0f} MB)"
                if size_bytes >= 1024 * 1024
                else f" ({max(size_bytes // 1024, 1)} KB)"
            )
        except OSError:
            size_label = ""
        project.last_status_message = f"Wrote support bundle: {bundle_path.name}{size_label}"
        context.scene.fyr_baker_settings.status_message = project.last_status_message
        self.report({"INFO"}, f"Wrote support bundle{size_label}: {bundle_path}")
        # Reveal it. The bundle lands beside the job workspace, which is a path no user
        # would think to go looking in, and the only reason to write one is to send it
        # to us — so finish the job and put the folder on screen.
        try:
            bpy.ops.wm.path_open(filepath=str(bundle_path.parent))
        except Exception:
            pass
        return {"FINISHED"}


class MASTER_BAKER_OT_load_output_image(bpy.types.Operator):
    bl_idname = "master_baker.load_output_image"
    bl_label = "Load Output Image"

    map_type: bpy.props.StringProperty(name="Map Type", default="")
    map_uuid: bpy.props.StringProperty(name="Map UUID", default="")
    group_name: bpy.props.StringProperty(name="Bake Group Name", default="")
    output_index: bpy.props.IntProperty(name="Output Index", default=-1)

    @classmethod
    def description(cls, _context, properties):
        map_type = getattr(properties, "map_type", "")
        output_index = getattr(properties, "output_index", -1)
        if map_type:
            return f"Load the assigned image or tracked output that matches the {naming.map_label(map_type)} map"
        if output_index >= 0:
            return f"Load tracked output {output_index + 1} into the Image Editor"
        return "Load the active tracked output into the Image Editor"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        map_type = str(getattr(self, "map_type", "") or "").strip().upper()
        map_uuid = str(getattr(self, "map_uuid", "") or "").strip()
        group_name = str(getattr(self, "group_name", "") or "").strip()
        if map_type:
            source = _resolve_map_source(
                project,
                map_uuid=map_uuid,
                map_type=map_type,
                group_name=group_name or _active_group_name(project),
                scene=context.scene,
            )
            if source is None:
                self.report({"ERROR"}, f"Could not resolve an image source for {naming.map_label(map_type)}")
                return {"CANCELLED"}
            _load_map_source(context, project, source)
            if map_uuid:
                for i, m in enumerate(getattr(project, "maps", [])):
                    if properties.ensure_map_setting_uuid(m) == map_uuid:
                        project.active_map_index = i
                        break
            self.report({"INFO"}, f"Loaded {source['display_name']}")
            return {"FINISHED"}
        if not project.latest_outputs:
            self.report({"ERROR"}, "No baked outputs are tracked yet")
            return {"CANCELLED"}

        resolved_index = properties.resolve_output_selection_index(
            project,
            output_index=self.output_index,
            map_type=self.map_type,
            group_name=self.group_name,
        )
        if resolved_index is None:
            self.report({"ERROR"}, "Could not resolve an output image to load")
            return {"CANCELLED"}

        target = properties.peek_latest_output(project, resolved_index)
        if target is None:
            self.report({"ERROR"}, "Could not resolve an output image to load")
            return {"CANCELLED"}

        _load_output_target(context, project, target, index=resolved_index)
        self.report({"INFO"}, f"Loaded {Path(target.file_path).name}")
        return {"FINISHED"}


class MASTER_BAKER_OT_open_map_output_image(bpy.types.Operator):
    bl_idname = "master_baker.open_map_output_image"
    bl_label = "Open Map Texture"
    bl_description = "Open this map's assigned image or latest baked texture in Blender's Image Editor"
    bl_options = {"REGISTER", "UNDO"}

    map_type: bpy.props.StringProperty(name="Map Type", default="")
    map_uuid: bpy.props.StringProperty(name="Map UUID", default="")
    group_name: bpy.props.StringProperty(name="Bake Group Name", default="")
    output_suffix: bpy.props.StringProperty(name="Output Suffix", default="")

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        map_type = str(getattr(self, "map_type", "") or "").strip().upper()
        map_uuid = str(getattr(self, "map_uuid", "") or "").strip()
        group_name = str(getattr(self, "group_name", "") or "").strip()
        output_suffix = str(getattr(self, "output_suffix", "") or "")
        source = _resolve_map_source(
            project,
            map_uuid=map_uuid,
            map_type=map_type,
            group_name=group_name or _active_group_name(project),
            output_suffix=output_suffix,
            scene=context.scene,
        )
        if source is None:
            self.report({"ERROR"}, f"No image source is available yet for {naming.map_label(map_type)}")
            return {"CANCELLED"}
        image = source["image"]
        if not _show_image_in_editor(context, image):
            self.report({"WARNING"}, "Loaded the image, but could not open an Image Editor window automatically")
        editor_state = properties.image_editor_state(context.scene.fyr_baker_settings)
        _apply_image_editor_display_channels(
            context,
            getattr(editor_state, "channel_mode", constants.IMAGE_CHANNEL_COLOR),
        )
        _apply_image_editor_mip_level(
            context,
            getattr(editor_state, "mip_level", 0),
        )
        properties.set_preview_map_type(
            context.scene.fyr_baker_settings,
            getattr(source["target"], "map_type", ""),
            fallback=self.map_type,
        )
        if source["resolved_index"] is not None:
            project.active_output_index = int(source["resolved_index"])
        self.report({"INFO"}, f"Opened {source['display_name']}")
        return {"FINISHED"}


class MASTER_BAKER_OT_preview_map_output(bpy.types.Operator):
    bl_idname = "master_baker.preview_map_output"
    bl_label = "Show Map On Low"
    bl_description = "Show or hide this texture on the active bake group's low-poly meshes"
    # No REGISTER/UNDO: redo/undo bookkeeping around multi-million-triangle highs
    # contributes to momentary Not Responding on toggle. Preview is ephemeral UI state.
    bl_options = set()

    # Targeting plumbing set by the UI buttons, not user-facing settings —
    # hidden so the redo panel doesn't show e.g. a group name on a preview
    # that applies to all groups.
    map_type: bpy.props.StringProperty(name="Map Type", default="", options={"HIDDEN"})
    group_name: bpy.props.StringProperty(name="Bake Group Name", default="", options={"HIDDEN"})
    map_uuid: bpy.props.StringProperty(name="Map UUID", default="", options={"HIDDEN"})
    output_suffix: bpy.props.StringProperty(name="Output Suffix", default="", options={"HIDDEN"})
    map_stack_index: bpy.props.IntProperty(name="Map Stack Index", default=-1, options={"HIDDEN"})
    scope: bpy.props.StringProperty(name="Scope", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        map_type = str(getattr(properties, "map_type", "") or "")
        if map_type:
            return f"Show or hide {naming.map_label(map_type)} on the low-poly preview material"
        return cls.bl_description

    def execute(self, context):
        result = _execute_preview_map_output_impl(
            self,
            context,
            active_project_or_report_fn=_active_project_or_report,
            resolve_map_source_fn=_resolve_map_source,
            active_group_name_fn=_active_group_name,
            preview_on_low_is_active_fn=_preview_on_low_is_active,
            deactivate_preview_on_low_fn=_deactivate_preview_on_low,
            activate_preview_on_low_fn=_activate_preview_on_low,
            activate_preview_on_low_all_groups_fn=_activate_preview_on_low_all_groups,
            map_label_fn=naming.map_label,
        )
        if "FINISHED" in result:
            settings = getattr(context.scene, "fyr_baker_settings", None)
            if settings is not None:
                session = properties.preview_session_state(settings)
                if session is not None and bool(getattr(session, "preview_on_low_active", False)):
                    session.preview_on_low_map_uuid = str(getattr(self, "map_uuid", "") or "")
        return result


#: Scene key: the Preview Baked Material group ("" = every group) that a map preview
#: from the picker replaced, so picking Off brings it back.
PBR_PREVIEW_RESUME_KEY = "_fyr_pbr_preview_resume"


class MASTER_BAKER_OT_set_preview_map(bpy.types.Operator):
    """Picker entry for the header's Preview Map menu.

    Unlike preview_map_output this never toggles: picking the map already on show
    keeps it, and OFF is the only way the picker ends a preview."""

    bl_idname = "master_baker.set_preview_map"
    bl_label = "Preview Map"
    bl_description = "Show this baked map on the low-poly meshes, or Off to restore their materials"
    # No REGISTER/UNDO -- preview material swapping is view state (see preview_map_output).
    bl_options = set()

    map_type: bpy.props.StringProperty(name="Map Type", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        map_type = str(getattr(properties, "map_type", "") or "").strip().upper()
        if map_type == "OFF":
            return "Stop the preview and restore the low-poly meshes' original materials"
        if map_type:
            return f"Show {naming.map_label(map_type)} on the low-poly meshes"
        return cls.bl_description

    def execute(self, context):
        scene = context.scene
        settings = getattr(scene, "fyr_baker_settings", None)
        session = _preview_session_state(settings)
        map_type = str(self.map_type or "").strip().upper()
        if map_type == "OFF":
            resume_group = scene.get(PBR_PREVIEW_RESUME_KEY)
            if resume_group is not None:
                del scene[PBR_PREVIEW_RESUME_KEY]
            if _any_preview_on_low_is_active(settings):
                _deactivate_preview_on_low(context)
            if resume_group is not None:
                # The map preview had replaced Preview Baked Material: Off goes back to
                # it instead of dropping every preview (customer: "going back to off
                # disables the material preview").
                bpy.ops.master_baker.preview_pbr_output("EXEC_DEFAULT", group_name=str(resume_group))
            return {"FINISHED"}
        if (
            session is not None
            and bool(getattr(session, "preview_on_low_active", False))
            and constants.base_map_type(getattr(session, "preview_on_low_map_type", "")) == map_type
        ):
            return {"FINISHED"}
        project = properties.get_active_project(scene)
        if (
            project is not None
            and PBR_PREVIEW_RESUME_KEY not in scene
            and _preview_pbr_on_low_is_active(settings, project)
        ):
            scene[PBR_PREVIEW_RESUME_KEY] = str(getattr(session, "preview_pbr_on_low_group_name", "") or "")
        return bpy.ops.master_baker.preview_map_output("EXEC_DEFAULT", map_type=map_type)


class MASTER_BAKER_OT_preview_pbr_output(bpy.types.Operator):
    bl_idname = "master_baker.preview_pbr_output"
    bl_label = "Preview Baked Material"
    bl_description = "Show or hide a PBR preview on the low-poly meshes using the available baked textures"
    # No REGISTER/UNDO — same reason as preview_map_output.
    bl_options = set()

    group_name: bpy.props.StringProperty(name="Bake Group Name", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        group_name = str(getattr(properties, "group_name", "") or "")
        if group_name:
            return f"Show or hide the baked PBR preview for {group_name}"
        return cls.bl_description

    def execute(self, context):
        # An explicit click decides the material preview; forget any pending resume.
        if PBR_PREVIEW_RESUME_KEY in context.scene:
            del context.scene[PBR_PREVIEW_RESUME_KEY]
        return _execute_preview_pbr_output_impl(
            self,
            context,
            active_project_or_report_fn=_active_project_or_report,
            active_group_name_fn=_active_group_name,
            preview_pbr_on_low_is_active_fn=_preview_pbr_on_low_is_active,
            deactivate_preview_on_low_fn=_deactivate_preview_on_low,
            resolve_pbr_preview_inputs_fn=_resolve_pbr_preview_inputs,
            activate_preview_pbr_on_low_fn=_activate_preview_pbr_on_low,
            activate_preview_pbr_on_low_all_groups_fn=_activate_preview_pbr_on_low_all_groups,
        )


class MASTER_BAKER_OT_toggle_material_ab_compare(bpy.types.Operator):
    bl_idname = "master_baker.toggle_material_ab_compare"
    bl_label = "A/B Material Compare"
    bl_description = (
        "Developer: cycle High source material → Low baked preview → off. "
        "Temporarily swaps high/low visibility for bake QA"
    )
    bl_options = set()

    @classmethod
    def poll(cls, context):
        if not preferences.developer_mode_enabled():
            return False
        scene = getattr(context, "scene", None)
        if scene is None or getattr(scene, "fyr_baker_settings", None) is None:
            return False
        return properties.peek_active_project(scene) is not None

    def execute(self, context):
        from . import preview_ab_compare

        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        message, side = preview_ab_compare.cycle_material_ab_compare(
            context,
            project,
            activate_preview_on_low_fn=_activate_preview_on_low,
            resolve_map_source_fn=_resolve_map_source,
            active_group_name_fn=_active_group_name,
            deactivate_preview_on_low_fn=_deactivate_preview_on_low,
            suppress_bg_prepare_fn=_suppress_bg_prepare,
        )
        settings = getattr(context.scene, "fyr_baker_settings", None)
        if settings is not None:
            settings.status_message = message
        overlays.tag_redraw_all_view3d(scene=context.scene, window=getattr(context, "window", None))
        self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_set_pbr_preview_normal_source(bpy.types.Operator):
    bl_idname = "master_baker.set_pbr_preview_normal_source"
    bl_label = "Set PBR Preview Normal Source"
    bl_description = "Choose which baked normal map drives the combined material preview"
    # Preview material swapping is VIEW STATE, not a document edit, so it must not push
    # an undo step. The operators that APPLY a preview (preview_map_output,
    # preview_pbr_output) already register none, so a registered step here recorded only
    # half the swap: the memfile snapshot never described the preview assignments that
    # actually existed. Rewinding past it restored a state where the addon's preview
    # materials were gone while something still referenced them, and the first depsgraph
    # tick afterwards crashed Blender building a Python wrapper for the freed Material
    # (bakeability_ui._depsgraph_update_post is the only handler that type-checks
    # bpy.types.Material; EXCEPTION_ACCESS_VIOLATION in PyType_GenericNew, 2026-09-09).
    # Nothing in Python can guard that -- a dangling ID faults before any try can see it.
    # Same reasoning that dropped UNDO from the project and paint operators.
    bl_options = {"REGISTER"}

    source: bpy.props.EnumProperty(
        name="Normal Source",
        items=constants.PBR_PREVIEW_NORMAL_SOURCE_ITEMS,
        default=constants.PBR_PREVIEW_NORMAL_TANGENT,
    )

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        settings = getattr(context.scene, "fyr_baker_settings", None)
        session_state = _preview_session_state(settings)
        if session_state is None:
            return {"CANCELLED"}

        normalized_source = str(self.source or constants.PBR_PREVIEW_NORMAL_TANGENT).strip().upper()
        if normalized_source not in {
            constants.PBR_PREVIEW_NORMAL_TANGENT,
            constants.PBR_PREVIEW_NORMAL_BENT,
        }:
            normalized_source = constants.PBR_PREVIEW_NORMAL_TANGENT

        pbr_was_active = _preview_pbr_on_low_is_active(settings, project)
        active_group_name = str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "")
        session_state.pbr_preview_normal_source = normalized_source

        if not pbr_was_active:
            return {"FINISHED"}

        _deactivate_preview_on_low(context)
        if active_group_name:
            applied_count, has_inputs = _activate_preview_pbr_on_low(
                context,
                project,
                group_name=active_group_name,
            )
        else:
            applied_count, has_inputs = _activate_preview_pbr_on_low_all_groups(context, project)
        if not has_inputs or applied_count <= 0:
            self.report({"WARNING"}, "The selected normal source is not available for preview")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_restore_preview_materials(bpy.types.Operator):
    bl_idname = "master_baker.restore_preview_materials"
    bl_label = "Restore Original Materials"
    bl_description = "Stop the active preview and restore the low-poly meshes' original materials"
    # Preview material swapping is VIEW STATE, not a document edit, so it must not push
    # an undo step. The operators that APPLY a preview (preview_map_output,
    # preview_pbr_output) already register none, so a registered step here recorded only
    # half the swap: the memfile snapshot never described the preview assignments that
    # actually existed. Rewinding past it restored a state where the addon's preview
    # materials were gone while something still referenced them, and the first depsgraph
    # tick afterwards crashed Blender building a Python wrapper for the freed Material
    # (bakeability_ui._depsgraph_update_post is the only handler that type-checks
    # bpy.types.Material; EXCEPTION_ACCESS_VIOLATION in PyType_GenericNew, 2026-09-09).
    # Nothing in Python can guard that -- a dangling ID faults before any try can see it.
    # Same reasoning that dropped UNDO from the project and paint operators.
    bl_options = {"REGISTER"}

    def execute(self, context):
        restored_count = _deactivate_preview_on_low(context)
        self.report({"INFO"}, f"Restored original materials on {restored_count} mesh(es)")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_live_normal_preview(bpy.types.Operator):
    bl_idname = "master_baker.toggle_live_normal_preview"
    bl_label = "Live Normal"
    bl_description = "Start or stop a reduced-resolution live normal preview for the active bake group"
    # Preview material swapping is VIEW STATE, not a document edit, so it must not push
    # an undo step. The operators that APPLY a preview (preview_map_output,
    # preview_pbr_output) already register none, so a registered step here recorded only
    # half the swap: the memfile snapshot never described the preview assignments that
    # actually existed. Rewinding past it restored a state where the addon's preview
    # materials were gone while something still referenced them, and the first depsgraph
    # tick afterwards crashed Blender building a Python wrapper for the freed Material
    # (bakeability_ui._depsgraph_update_post is the only handler that type-checks
    # bpy.types.Material; EXCEPTION_ACCESS_VIOLATION in PyType_GenericNew, 2026-09-09).
    # Nothing in Python can guard that -- a dangling ID faults before any try can see it.
    # Same reasoning that dropped UNDO from the project and paint operators.
    bl_options = {"REGISTER"}

    group_name: bpy.props.StringProperty(default="")

    @classmethod
    def description(cls, context, _properties):
        scene = getattr(context, "scene", None)
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        session_state = _preview_session_state(settings)
        if session_state is not None and bool(getattr(session_state, "live_normal_preview_active", False)):
            return "Stop live normal preview and restore the original low-mesh materials"
        return cls.bl_description

    def execute(self, context):
        target_group_name = str(self.group_name or "")
        if target_group_name:
            def _resolve_by_name(operator, context):
                project = _active_project_or_report(operator, context)
                if project is None:
                    return None, None
                group = next(
                    (g for g in getattr(project, "groups", []) if str(getattr(g, "name", "") or "") == target_group_name),
                    None,
                )
                if group is None:
                    operator.report({"ERROR"}, f"Bake group '{target_group_name}' not found")
                    return None, None
                return project, group
            cage_fn = _resolve_by_name
        else:
            cage_fn = _cage_target_project_group_or_report
        return _execute_toggle_live_normal_preview_impl(
            self,
            context,
            cage_target_project_group_or_report_fn=cage_fn,
            live_normal_preview_is_active_fn=_live_normal_preview_is_active,
            deactivate_preview_on_low_fn=_deactivate_preview_on_low,
            activate_live_normal_preview_fn=_activate_live_normal_preview,
        )


class MASTER_BAKER_OT_external_edit_map_output(bpy.types.Operator):
    bl_idname = "master_baker.external_edit_map_output"
    bl_label = "Edit Map Externally"
    bl_description = "Open this map's assigned image or latest baked texture in the configured external editor, then reload it when saved"
    bl_options = {"REGISTER", "UNDO"}

    map_type: bpy.props.StringProperty(name="Map Type", default="")
    map_uuid: bpy.props.StringProperty(name="Map UUID", default="")
    group_name: bpy.props.StringProperty(name="Bake Group Name", default="")
    output_suffix: bpy.props.StringProperty(name="Output Suffix", default="")

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        map_type = str(getattr(self, "map_type", "") or "").strip().upper()
        map_uuid = str(getattr(self, "map_uuid", "") or "").strip()
        group_name = str(getattr(self, "group_name", "") or "").strip()
        output_suffix = str(getattr(self, "output_suffix", "") or "")
        source = _resolve_map_source(
            project,
            map_uuid=map_uuid,
            map_type=map_type,
            group_name=group_name or _active_group_name(project),
            output_suffix=output_suffix,
            scene=context.scene,
        )
        if source is None:
            self.report({"ERROR"}, f"No image source is available yet for {naming.map_label(map_type)}")
            return {"CANCELLED"}
        resolved_path = Path(str(source["file_path"] or "").strip())
        if not str(resolved_path):
            self.report({"ERROR"}, f"The assigned {naming.map_label(map_type)} image is not file-backed")
            return {"CANCELLED"}
        if not resolved_path.exists():
            self.report({"ERROR"}, f"Output file not found: {resolved_path}")
            return {"CANCELLED"}

        runtime.load_managed_output_image(resolved_path)
        try:
            bpy.ops.image.external_edit(filepath=str(resolved_path))
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        _EXTERNAL_EDIT_WATCHER.start(resolved_path)
        properties.set_preview_map_type(
            context.scene.fyr_baker_settings,
            getattr(source["target"], "map_type", ""),
            fallback=self.map_type,
        )
        if source["resolved_index"] is not None:
            project.active_output_index = int(source["resolved_index"])
        self.report({"INFO"}, f"Opened {resolved_path.name} in the external editor")
        return {"FINISHED"}


class MASTER_BAKER_OT_previous_output(bpy.types.Operator):
    bl_idname = "master_baker.previous_output"
    bl_label = "Previous Output"
    bl_description = "Load the previous tracked output"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        resolved_index = properties.cycle_latest_output_index(project, -1)
        if resolved_index is None:
            self.report({"ERROR"}, "No baked outputs are tracked yet")
            return {"CANCELLED"}
        target = properties.peek_latest_output(project, resolved_index)
        if target is None:
            self.report({"ERROR"}, "Could not resolve the previous output")
            return {"CANCELLED"}
        _load_output_target(context, project, target, index=resolved_index)
        self.report({"INFO"}, f"Loaded {Path(target.file_path).name}")
        return {"FINISHED"}


class MASTER_BAKER_OT_next_output(bpy.types.Operator):
    bl_idname = "master_baker.next_output"
    bl_label = "Next Output"
    bl_description = "Load the next tracked output"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        resolved_index = properties.cycle_latest_output_index(project, 1)
        if resolved_index is None:
            self.report({"ERROR"}, "No baked outputs are tracked yet")
            return {"CANCELLED"}
        target = properties.peek_latest_output(project, resolved_index)
        if target is None:
            self.report({"ERROR"}, "Could not resolve the next output")
            return {"CANCELLED"}
        _load_output_target(context, project, target, index=resolved_index)
        self.report({"INFO"}, f"Loaded {Path(target.file_path).name}")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_compare_mode(bpy.types.Operator):
    bl_idname = "master_baker.toggle_compare_mode"
    bl_label = "Toggle Compare Mode"
    bl_description = "Turn A/B comparison on or off for tracked outputs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        editor_state.compare_enabled = not editor_state.compare_enabled
        settings.status_message = "Compare mode on" if editor_state.compare_enabled else "Compare mode off"
        return {"FINISHED"}


class MASTER_BAKER_OT_set_image_editor_channel_mode(bpy.types.Operator):
    bl_idname = "master_baker.set_image_editor_channel_mode"
    bl_label = "Set Image Editor Channels"
    bl_options = {"REGISTER", "UNDO"}

    channel_mode: bpy.props.EnumProperty(
        name="Channels",
        items=constants.IMAGE_CHANNEL_MODE_ITEMS,
        default=constants.IMAGE_CHANNEL_COLOR,
    )

    @classmethod
    def description(cls, _context, properties):
        mode = getattr(properties, "channel_mode", constants.IMAGE_CHANNEL_COLOR)
        label = next((item[1] for item in constants.IMAGE_CHANNEL_MODE_ITEMS if item[0] == mode), mode)
        return f"Show {label} channels in the Image Editor"

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        editor_state.channel_mode = self.channel_mode
        _apply_image_editor_display_channels(context, self.channel_mode)
        settings.status_message = f"Image channels: {next((item[1] for item in constants.IMAGE_CHANNEL_MODE_ITEMS if item[0] == self.channel_mode), self.channel_mode)}"
        return {"FINISHED"}


class MASTER_BAKER_OT_set_image_editor_mip_level(bpy.types.Operator):
    bl_idname = "master_baker.set_image_editor_mip_level"
    bl_label = "Set Image Editor Mip Level"
    bl_options = {"REGISTER", "UNDO"}

    mip_level: bpy.props.IntProperty(name="Mip Level", default=0, min=0, max=constants.IMAGE_EDITOR_MAX_MIP_LEVEL)

    @classmethod
    def description(cls, _context, properties):
        level = image_inspection.clamp_mip_level(getattr(properties, "mip_level", 0))
        return f"Show Image Editor mip preview level {level}"

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        editor_state.mip_level = image_inspection.clamp_mip_level(self.mip_level)
        _apply_image_editor_mip_level(context, editor_state.mip_level)
        settings.status_message = f"Image mip level: {editor_state.mip_level}"
        return {"FINISHED"}


class MASTER_BAKER_OT_set_compare_slot(bpy.types.Operator):
    bl_idname = "master_baker.set_compare_slot"
    bl_label = "Store Compare Output"
    bl_options = {"REGISTER", "UNDO"}

    slot: bpy.props.EnumProperty(
        name="Slot",
        items=(
            ("A", "A", "Primary compare output"),
            ("B", "B", "Secondary compare output"),
        ),
        default="A",
    )

    @classmethod
    def description(cls, _context, properties):
        slot = getattr(properties, "slot", "A")
        return f"Set the active output as comparison slot {slot}"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        index = properties.resolve_latest_output_index(project)
        if index is None:
            self.report({"ERROR"}, "No baked outputs are tracked yet")
            return {"CANCELLED"}
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        properties.set_compare_slot_index(settings, self.slot, index)
        editor_state.compare_active_slot = self.slot
        editor_state.compare_enabled = True
        project.last_status_message = f"Stored output {index + 1} as compare {self.slot}"
        return {"FINISHED"}


class MASTER_BAKER_OT_load_compare_slot(bpy.types.Operator):
    bl_idname = "master_baker.load_compare_slot"
    bl_label = "Load Compare Output"
    bl_options = {"REGISTER", "UNDO"}

    slot: bpy.props.EnumProperty(
        name="Slot",
        items=(
            ("A", "A", "Primary compare output"),
            ("B", "B", "Secondary compare output"),
        ),
        default="A",
    )

    @classmethod
    def description(cls, _context, properties):
        slot = getattr(properties, "slot", "A")
        return f"Load comparison slot {slot}"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}
        settings = context.scene.fyr_baker_settings
        index = properties.compare_slot_index(settings, self.slot)
        if index < 0:
            self.report({"ERROR"}, f"Compare output {self.slot} is empty")
            return {"CANCELLED"}
        target = properties.peek_latest_output(project, index)
        if target is None:
            self.report({"ERROR"}, f"Compare output {self.slot} points to a missing file")
            return {"CANCELLED"}
        properties.set_compare_slot_index(settings, self.slot, index)
        editor_state = properties.image_editor_state(settings)
        editor_state.compare_active_slot = self.slot
        editor_state.compare_enabled = True
        _load_output_target(context, project, target, index=index)
        self.report({"INFO"}, f"Loaded compare output {self.slot}")
        return {"FINISHED"}


class MASTER_BAKER_OT_swap_compare_slots(bpy.types.Operator):
    bl_idname = "master_baker.swap_compare_slots"
    bl_label = "Swap Compare Outputs"
    bl_description = "Swap compare outputs A and B"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        properties.swap_compare_slots(settings)
        editor_state.compare_enabled = True
        editor_state.compare_active_slot = "A"
        return {"FINISHED"}


class MASTER_BAKER_OT_isolate_active_group(bpy.types.Operator):
    bl_idname = "master_baker.isolate_active_group"
    bl_label = "Toggle Bake Group Isolation"
    bl_description = "Hide all objects outside the active bake group, or restore the previous viewport visibility"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        isolation_result = _toggle_isolation_targets(context.scene, _group_object_set(group))
        if isolation_result is None:
            self.report({"ERROR"}, "No objects are assigned to the active bake group")
            return {"CANCELLED"}
        if not isolation_result:
            group.isolate_in_viewport = False
            self.report({"INFO"}, "Restored viewport visibility")
            return {"FINISHED"}

        group.isolate_in_viewport = True
        self.report({"INFO"}, "Isolated active bake group")
        return {"FINISHED"}


class MASTER_BAKER_OT_select_active_group(bpy.types.Operator):
    bl_idname = "master_baker.select_active_group"
    bl_label = "Select Bake Group Objects"
    bl_description = "Select all objects assigned to the active bake group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        if not _select_objects_in_view_layer(context, list(_group_object_set(group))):
            self.report({"ERROR"}, "No objects are assigned to the active bake group")
            return {"CANCELLED"}
        self.report({"INFO"}, "Selected active bake group objects")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_active_group_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_active_group_visibility"
    bl_label = "Toggle Bake Group Visibility"
    bl_options = {"REGISTER", "UNDO"}

    isolate: bpy.props.BoolProperty(name="Isolate", default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.isolate = bool(getattr(event, "shift", False))
        return self.execute(context)

    @classmethod
    def description(cls, _context, properties):
        if bool(getattr(properties, "isolate", False)):
            return "Isolate the active bake group, or restore visibility if it is already isolated"
        return "Hide the active bake group's low-poly meshes if visible, or show them if hidden. Shift-click to isolate the whole group"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        # Isolate operates on the whole group (low + high + cage); a plain show/hide acts only
        # on the low-poly so it doesn't pull the high-poly back into the viewport.
        all_targets = list(_group_object_set(group))
        if not all_targets:
            self.report({"ERROR"}, "No objects are assigned to the active bake group")
            return {"CANCELLED"}

        if self.isolate:
            isolation_result = _toggle_isolation_targets(context.scene, all_targets)
            if isolation_result is None:
                self.report({"ERROR"}, "No objects are assigned to the active bake group")
                return {"CANCELLED"}
            group.isolate_in_viewport = bool(isolation_result)
            message = "Isolated active bake group" if isolation_result else "Restored viewport visibility"
            self.report({"INFO"}, message)
            overlays.tag_redraw_all_view3d()
            return {"FINISHED"}

        role_state = properties.group_role_assignments_state(group)
        low_targets = [
            obj
            for slot in getattr(role_state, "low_meshes", [])
            for obj in (getattr(slot, "object_ref", None),)
            if obj is not None
        ]
        if not low_targets:
            self.report({"ERROR"}, "No low-poly meshes are assigned to the active bake group")
            return {"CANCELLED"}

        all_hidden = all(bool(obj.hide_get()) for obj in low_targets)
        new_hidden = not all_hidden
        group.isolate_in_viewport = False
        _set_hidden_state_for_objects(low_targets, new_hidden)
        action = "Hid" if new_hidden else "Showed"
        self.report({"INFO"}, f"{action} active bake group low-poly meshes")
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


class MASTER_BAKER_OT_select_group_role_objects(bpy.types.Operator):
    bl_idname = "master_baker.select_group_role_objects"
    bl_label = "Select Meshes"
    bl_options = {"REGISTER", "UNDO"}

    role: bpy.props.EnumProperty(
        name="Role",
        items=(
            (constants.OBJECT_ROLE_LOW, "Low", "Select the low-poly meshes in the active bake group"),
            (constants.OBJECT_ROLE_HIGH, "High", "Select the high-poly meshes in the active bake group"),
            (constants.OBJECT_ROLE_CAGE, "Cage", "Select the custom cage in the active bake group"),
        ),
        default=constants.OBJECT_ROLE_LOW,
    )

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        if role == constants.OBJECT_ROLE_CAGE:
            return "Select this bake group's custom cage"
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
        return f"Select all {role_label} meshes in this bake group"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        targets = [obj for obj in _group_role_targets(group, self.role) if obj is not None]
        if not targets:
            role_label = "low" if self.role == constants.OBJECT_ROLE_LOW else "high" if self.role == constants.OBJECT_ROLE_HIGH else self.role.lower()
            self.report({"ERROR"}, f"No {role_label} meshes are assigned to this bake group")
            return {"CANCELLED"}

        if not _select_objects_in_view_layer(context, targets, active_object=targets[0]):
            role_label = "low" if self.role == constants.OBJECT_ROLE_LOW else "high" if self.role == constants.OBJECT_ROLE_HIGH else self.role.lower()
            self.report({"ERROR"}, f"Unable to select this bake group's {role_label} meshes")
            return {"CANCELLED"}
        role_label = "low" if self.role == constants.OBJECT_ROLE_LOW else "high" if self.role == constants.OBJECT_ROLE_HIGH else self.role.lower()
        self.report({"INFO"}, f"Selected {role_label} meshes in this bake group")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_group_role_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_group_role_visibility"
    bl_label = "Toggle Bake Group Role Visibility"
    bl_options = {"REGISTER", "UNDO"}

    role: bpy.props.EnumProperty(
        name="Role",
        items=constants.OBJECT_ROLE_ITEMS,
        default=constants.OBJECT_ROLE_LOW,
    )
    isolate: bpy.props.BoolProperty(name="Isolate", default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.isolate = bool(getattr(event, "shift", False))
        return self.execute(context)

    @classmethod
    def description(cls, _context, properties):
        role = getattr(properties, "role", constants.OBJECT_ROLE_LOW)
        role_label = "low-poly" if role == constants.OBJECT_ROLE_LOW else "high-poly"
        if bool(getattr(properties, "isolate", False)):
            return f"Isolate the active bake group's {role_label} meshes, or restore visibility if they are already isolated"
        return f"Hide the active bake group's {role_label} meshes if visible, or show them if hidden"

    def execute(self, context):
        project, group = _cage_target_project_group_or_report(self, context)
        if project is None or group is None:
            return {"CANCELLED"}

        targets = [obj for obj in _group_role_targets(group, self.role) if obj is not None]
        if not targets:
            self.report({"ERROR"}, f"No {self.role.lower()} objects are assigned to the active bake group")
            return {"CANCELLED"}

        if self.isolate:
            isolation_result = _toggle_isolation_targets(context.scene, targets)
            if isolation_result is None:
                self.report({"ERROR"}, f"No {self.role.lower()} objects are assigned to the active bake group")
                return {"CANCELLED"}
            message = (
                f"Isolated active bake group's {self.role.lower()} objects"
                if isolation_result
                else "Restored viewport visibility"
            )
            self.report({"INFO"}, message)
            overlays.tag_redraw_all_view3d()
            return {"FINISHED"}

        all_hidden = all(bool(obj.hide_get()) for obj in targets)
        new_hidden = not all_hidden
        _set_hidden_state_for_objects(targets, new_hidden)

        action = "Hid" if new_hidden else "Showed"
        self.report({"INFO"}, f"{action} active bake group's {self.role.lower()} objects")
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


def project_role_reference_targets(project, role: str) -> list:
    """Every unique mesh assigned to *role* across all of *project*'s groups."""
    targets: list = []
    for group in getattr(project, "groups", []):
        for obj in _group_role_targets(group, role):
            if obj is None or any(existing is obj for existing in targets):
                continue
            targets.append(obj)
    return targets


def project_role_reference_all_visible(project, role: str) -> bool:
    """True when the project has *role* meshes and every one is visible."""
    targets = project_role_reference_targets(project, role)
    return bool(targets) and all(not bool(obj.hide_get()) for obj in targets)


class MASTER_BAKER_OT_toggle_reference_visibility(bpy.types.Operator):
    bl_idname = "master_baker.toggle_reference_visibility"
    bl_label = "Toggle Reference Visibility"
    bl_options = {"REGISTER", "UNDO"}

    role: bpy.props.EnumProperty(
        name="Role",
        items=constants.OBJECT_ROLE_ITEMS,
        default=constants.OBJECT_ROLE_HIGH,
    )

    @classmethod
    def description(cls, _context, properties):
        label = "high" if getattr(properties, "role", constants.OBJECT_ROLE_HIGH) == constants.OBJECT_ROLE_HIGH else "low"
        return f"Show or hide every {label}-poly mesh in the bake project"

    def execute(self, context):
        project = _active_project_or_report(self, context)
        if project is None:
            return {"CANCELLED"}

        targets = project_role_reference_targets(project, self.role)
        label = "high" if self.role == constants.OBJECT_ROLE_HIGH else "low"
        if not targets:
            self.report({"ERROR"}, f"No {label}-poly meshes are assigned in this project")
            return {"CANCELLED"}

        # Toggle relative to the aggregate state: if everything is visible, hide it;
        # otherwise reveal the whole set so a mixed state resolves to fully shown.
        all_visible = all(not bool(obj.hide_get()) for obj in targets)
        _set_hidden_state_for_objects(targets, all_visible)
        action = "Hid" if all_visible else "Showed"
        self.report({"INFO"}, f"{action} {len(targets)} {label}-poly mesh(es)")
        overlays.tag_redraw_all_view3d()
        return {"FINISHED"}


def _iter_loaded_scenes():
    yield from _iter_loaded_scenes_impl(
        data_scenes=getattr(getattr(bpy, "data", None), "scenes", None),
        context_scene=getattr(getattr(bpy, "context", None), "scene", None),
    )


_persistent_handler = getattr(getattr(getattr(bpy, "app", None), "handlers", None), "persistent", lambda fn: fn)


@_persistent_handler
def _load_pre(_dummy):
    # Everything prewarm-related that is queued or running now belongs to the file
    # being closed. Stop it here, before Blender spends time reading the new file:
    # a closed SvAT.blend's PREPARE otherwise kept the worker busy and made the next
    # file's first bake wait ~133s behind it (2026-09-26). Only background prepare
    # is touched; a running bake is load_post's business. No waits: this blocks the
    # file open.
    try:
        _cancel_pending_bg_prepare()
    except Exception:
        pass
    try:
        runtime.cancel_speculative_prepare()
    except Exception:
        pass
    try:
        runtime.cancel_prepare_for_closing_file()
    except Exception:
        pass


@_persistent_handler
def _load_post(_dummy):
    # Failsafe: a file opened mid-bake abandons the low-impact snapshot. Re-add the
    # overlay draw handlers (safe here — the addon stays registered) and clear the flag
    # so overlays work in the freshly loaded file. No-op when not engaged.
    try:
        _bake_low_impact_restore()
    except Exception:
        pass
    _load_post_impl(
        _dummy,
        reset_live_bake_runtime_on_load_fn=_reset_live_bake_runtime_on_load,
        restore_preview_materials_fn=preview_materials.restore_preview_materials,
        context=getattr(bpy, "context", None),
        data_scenes=getattr(getattr(bpy, "data", None), "scenes", None),
        clear_live_bake_state_fn=_clear_live_bake_state,
        remove_phantom_map_items_fn=properties.remove_phantom_map_items,
        capture_view3d_shading_state_fn=_capture_view3d_shading_state,
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        sync_preview_material_for_project_fn=_sync_preview_material_for_project,
        clear_preview_on_low_state_fn=_clear_preview_on_low_state,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )
    _subscribe_workspace_switch()


@_persistent_handler
def _undo_post(*_args):
    handle_undo_or_redo_post()


@_persistent_handler
def _redo_post(*_args):
    handle_undo_or_redo_post()


@_persistent_handler
def _save_pre(_dummy):
    _save_pre_impl(
        _dummy,
        context=getattr(bpy, "context", None),
        data_scenes=getattr(getattr(bpy, "data", None), "scenes", None),
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        has_overridden_preview_materials_fn=preview_materials.has_overridden_preview_materials,
        clear_preview_on_low_state_fn=_clear_preview_on_low_state,
        restore_preview_on_low_overlay_state_fn=_restore_preview_on_low_overlay_state,
        restore_preview_on_low_viewport_state_fn=_restore_preview_on_low_viewport_state,
        restore_preview_materials_fn=preview_materials.restore_preview_materials,
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


@_persistent_handler
def _save_post(_dummy):
    _save_post_impl(
        _dummy,
        context=getattr(bpy, "context", None),
        data_scenes=getattr(getattr(bpy, "data", None), "scenes", None),
        any_preview_on_low_is_active_fn=_any_preview_on_low_is_active,
        apply_runtime_preview_overlay_state_fn=_apply_runtime_preview_overlay_state,
        apply_preview_on_low_viewport_state_fn=_apply_preview_on_low_viewport_state,
        sync_preview_material_for_project_fn=_sync_preview_material_for_project,
        tag_redraw_all_view3d_fn=overlays.tag_redraw_all_view3d,
    )


class MASTER_BAKER_OT_handle_duplicate_map_outputs(bpy.types.Operator):
    """Dialog shown when two or more enabled maps would write to the same output file.
    Offers to auto-assign unique suffixes so the bake can proceed without data loss."""

    bl_idname = "master_baker.handle_duplicate_map_outputs"
    bl_label = "Duplicate Map Outputs"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, event):
        if not _PENDING_BAKE_STATE.get("conflict_groups"):
            # Nothing to resolve — just proceed.
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        conflict_groups = _PENDING_BAKE_STATE.get("conflict_groups", [])

        col = layout.column(align=True)
        col.label(text="Multiple maps share the same output filename:", icon="ERROR")
        col.separator(factor=0.5)

        for group in conflict_groups:
            label = group.get("label", "")
            suffix = group.get("effective_suffix", "")
            # uuids contains ALL maps in the group (including first), so len is correct.
            count = len(group.get("uuids", []))
            display = label + (f'  "{suffix}"' if suffix else "")
            col.label(text=f"{count}\u00d7  {display}", icon="FILE_BLANK")

        col.separator(factor=0.5)
        col.label(text='Click "OK" to auto-rename the extra copies and proceed with the bake.')
        col.label(text="You can edit the suffixes manually in the Maps list afterwards.")

    def execute(self, context):
        conflict_groups = _PENDING_BAKE_STATE.get("conflict_groups", [])
        scene_name = _PENDING_BAKE_STATE.get("scene_name", "")
        operator_name = _PENDING_BAKE_STATE.get("operator_name", "")
        allow_missing_uvs = bool(_PENDING_BAKE_STATE.get("allow_missing_uvs", False))

        # Locate the project.
        scene = next(
            (s for s in bpy.data.scenes if s.name == scene_name),
            getattr(context, "scene", None),
        )
        project = properties.get_active_project(scene)
        if project is None:
            self.report({"ERROR"}, "Could not find the bake project")
            return {"CANCELLED"}

        # Auto-rename: keep the first map in each conflict group unchanged,
        # assign unique explicit suffixes to all subsequent duplicates.
        for group in conflict_groups:
            uuids = group.get("uuids", [])
            effective_type = group.get("effective_type", "")
            map_label = group.get("label", "") or naming.map_label(effective_type) or "Map"

            maps_in_group = [
                ms for uuid in uuids
                for ms in [properties.find_map_setting_by_uuid(project, uuid)]
                if ms is not None
            ]
            if len(maps_in_group) <= 1:
                continue

            # Compare the FILE each row writes, casefolded, not the raw suffix: the
            # collision this resolves can come from two rows whose suffixes differ only
            # in case, or whose empty suffixes both fall back to the same map label
            # (geometry Normal vs Material -> Normal). Comparing suffixes let exactly
            # those pairs through the rename and back into the hard validator error.
            # See MATERIAL_BAKE_QA_2026_08_19_PASS2, G9.
            first_group_name = ""
            for bake_group in getattr(project, "groups", []) or []:
                first_group_name = str(getattr(bake_group, "name", "") or "")
                if first_group_name:
                    break

            def _written_file(map_setting, group_name=first_group_name):
                if not group_name:
                    return (properties.effective_map_output_suffix(project, map_setting) or "").casefold()
                return export._current_output_file_name(project, group_name, map_setting).casefold()

            # The first map is left untouched; everything already enabled is off limits.
            used_files = {
                _written_file(ms)
                for ms in getattr(project, "maps", [])
                if ms == maps_in_group[0]  # `is` never matches an RNA wrapper
                or (bool(getattr(ms, "enabled", False)) and ms not in maps_in_group)
            }

            for ms in maps_in_group[1:]:
                # Base the new suffix on the map's current effective suffix (or map label).
                base = properties.effective_map_output_suffix(project, ms) or map_label
                original_suffix = ms.output_suffix
                candidate = base
                counter = 2
                ms.output_suffix = candidate
                while _written_file(ms) in used_files:
                    candidate = f"{base} {counter}"
                    counter += 1
                    ms.output_suffix = candidate
                    if counter > 64:  # pathological stack; leave it for the validator
                        ms.output_suffix = original_suffix
                        break
                used_files.add(_written_file(ms))

        _PENDING_BAKE_STATE.clear()

        # Re-invoke the original bake.  Using INVOKE_DEFAULT so the new invoke()
        # on each operator re-checks for duplicates (safeguard against edge cases).
        if operator_name == "bake_project":
            if allow_missing_uvs:
                return _run_bake(
                    self,
                    context,
                    project,
                    start_message="Bake started, skipping meshes without UVs",
                    allow_missing_uvs=True,
                )
            return bpy.ops.master_baker.bake_project("INVOKE_DEFAULT")
        if operator_name == "rebuild_changed_maps":
            return bpy.ops.master_baker.rebuild_changed_maps("INVOKE_DEFAULT")
        if operator_name == "toggle_live_bake":
            return bpy.ops.master_baker.toggle_live_bake("INVOKE_DEFAULT")

        return {"FINISHED"}


def _clear_hang_watchdog_logs() -> None:
    """Delete the watchdog traceback log and its rollover. Best-effort.

    The live handle is closed first so Windows lets the file go; the watchdog reopens
    (and re-arms) on its next heartbeat.
    """
    try:
        path = hang_watchdog.log_path()
    except Exception:
        return
    try:
        hang_watchdog.close_log()
    except Exception:
        pass
    for candidate in (path, path.with_suffix(path.suffix + ".1")):
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            continue


class MASTER_BAKER_OT_clear_all_caches(bpy.types.Operator):
    bl_idname = "master_baker.clear_all_caches"
    bl_label = "Clear Cache"
    bl_description = "Delete all reusable bake caches so the next bake starts from scratch"
    bl_options = {"REGISTER"}

    def execute(self, context):
        del context
        snapshot = runtime.active_bake_snapshot()
        if snapshot is not None and getattr(snapshot, "running", False):
            self.report({"ERROR"}, "Stop the active bake before clearing cache")
            return {"CANCELLED"}
        if preferences.clean_caches_in_progress():
            self.report({"INFO"}, "Cache clean-up is already running")
            return {"CANCELLED"}
        try:
            # Main-thread half: worker shutdown, in-memory state, the watchdog's open
            # log handle. The multi-GB tree delete follows on a worker thread; inline
            # it held WM_main for as long as ~18 000 files took to unlink.
            runtime.shutdown_workers_for_cache_clear()
            export.invalidate_debug_overlay_export_cache()
            export.invalidate_live_preview_export_cache()
            high_mesh_cache.clear_persistent_cache_state()
            # The hang-watchdog traceback log sits as a loose file in the cache root, so
            # the family sweep never saw it and Clear Cache left it behind (91.5 MB on
            # one machine). It is diagnostic-only and regenerates on the next arm.
            _clear_hang_watchdog_logs()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        high_exports_root = high_mesh_cache.persistent_cache_root_path()

        def _work():
            import shutil as _shutil

            _shutil.rmtree(high_exports_root, ignore_errors=True)
            storage_cleanup.clear_known_cache_entries()
            return "Cache cleared"

        if not preferences.launch_cache_task(
            _work, fallback_summary="Cache cleared", thread_name="fyr-baker-clear-cache"
        ):
            self.report({"ERROR"}, "Could not start the cache clear")
            return {"CANCELLED"}
        self.report({"INFO"}, "Clearing caches in the background")
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_logs(bpy.types.Operator):
    bl_idname = "master_baker.clear_logs"
    bl_label = "Clear Logs"
    bl_description = (
        "Delete the bake logs of this project's job folders and the worker diagnostics "
        "logs. Running jobs are kept"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        import shutil
        from pathlib import Path

        cleared_count = 0
        # What an artist means by "the logs": every finished job's backend logs under
        # the project's output root, plus the machine-wide worker diagnostics. The
        # old list only knew developer-repo paths (Testing/, backend/build/, test_*
        # folders) that no tester install has, so the button deleted nothing.
        project = properties.peek_active_project(getattr(context, "scene", None))
        if project is not None:
            try:
                output_root, _ = export.resolve_output_root_path(project)
                cleared_count += storage_cleanup.clear_job_workspace_logs(output_root)
            except Exception:
                pass
        cleared_count += storage_cleanup.clear_global_diagnostic_logs()
        _clear_hang_watchdog_logs()

        if not preferences.developer_mode_enabled():
            self.report({"INFO"}, f"Cleared {cleared_count} log file(s)")
            return {"FINISHED"}

        # Developer extras: the repository's own test and benchmark logs.
        repo_root = runtime.repo_root()
        log_patterns = [
            repo_root / "Testing" / "*.log",
            repo_root / "backend" / "build" / "Release" / "test_*.log",
            repo_root / "backend" / "build" / "Testing" / "Temporary" / "LastTest.log",
            repo_root / "test_ao_gpu_routing" / "logs" / "gpu_diagnostics.log",
            repo_root / "test_tdr_output" / "logs" / "gpu_diagnostics.log",
            repo_root / "test_texset_output" / "logs" / "gpu_diagnostics.log",
        ]

        for pattern in log_patterns:
            for log_file in Path(pattern.parent).glob(pattern.name):
                try:
                    if log_file.is_file():
                        log_file.unlink()
                        cleared_count += 1
                except Exception:
                    pass

        debug_output = repo_root / "debug_output"
        if debug_output.exists() and debug_output.is_dir():
            try:
                shutil.rmtree(debug_output, ignore_errors=True)
                cleared_count += 1
            except Exception:
                pass

        self.report({"INFO"}, f"Cleared {cleared_count} log files/directories")
        return {"FINISHED"}


def _finish_backend_prewarm_configuration():
    """Persist and apply first-run prewarm settings after the dialog is gone.

    Blender 5.1 refreshes an operator dialog once more while accepting it. Running
    another window-manager operator (notably ``wm.save_userpref``) from execute()
    can invalidate the dialog's operator RNA pointer before that refresh, causing
    an access violation in ``uiTemplateOperatorPropertyButs``. This timer runs on
    the main thread after the popup has been destroyed and deliberately retains no
    reference to the short-lived operator instance.
    """
    try:
        bpy.ops.wm.save_userpref()
    except Exception:
        pass
    try:
        from . import runtime as _runtime

        _runtime.schedule_backend_prewarm(reason="first_run_dialog")
    except Exception:
        pass
    return None


_FIRST_RUN_SETTING_HELP = {
    "UPDATE_CHECKS": (
        "Choose whether Fyr Baker checks for new versions when Blender starts, every 30 minutes, "
        "only when you request it, or never. Update checks connect to the internet to look for "
        "new versions"
    ),
    "BACKEND_PREWARM": (
        "Choose when Fyr Baker starts its bake worker. Starting it before Bake makes the first bake faster, "
        "but keeps memory and GPU resources in use"
    ),
    "MESH_CACHES": (
        "Prepare high-poly mesh data in advance so the first bake starts faster. "
        "Available when the bake worker starts before baking"
    ),
}


class MASTER_BAKER_OT_first_run_setting_help(bpy.types.Operator):
    """Show help for a setting in the first-run dialog."""

    bl_idname = "master_baker.first_run_setting_help"
    bl_label = "Setting Help"
    bl_options = {"INTERNAL"}

    topic: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        del cls, context
        return _FIRST_RUN_SETTING_HELP.get(getattr(properties, "topic", ""), "More information about this setting")

    def execute(self, context):
        del context
        self.report({"INFO"}, _FIRST_RUN_SETTING_HELP.get(self.topic, "More information about this setting"))
        return {"FINISHED"}


def _copy_enum_items(items):
    """Return fresh enum tuples so RNA never holds pointers into a reloaded module."""
    copied = []
    for item in items:
        if not item:
            continue
        identifier = str(item[0])
        name = str(item[1]) if len(item) > 1 else identifier
        description = str(item[2]) if len(item) > 2 else ""
        if len(item) >= 5:
            copied.append((identifier, name, description, item[3], int(item[4])))
        elif len(item) == 4:
            copied.append((identifier, name, description, item[3]))
        else:
            copied.append((identifier, name, description))
    return copied


def _backend_prewarm_mode_items(_self, _context):
    return _copy_enum_items(constants.BACKEND_PREWARM_MODE_ITEMS)


def _update_check_mode_items(_self, _context):
    return _copy_enum_items(update_policy.update_mode_items())


def _update_check_mode_default_index() -> int:
    """Index of the shared update-mode default within UPDATE_MODE_ITEMS.

    EnumProperty with a dynamic items callback takes an integer default, and
    Blender numbers callback items by position. Deriving the index keeps the
    dialog's default tied to ``update_policy.UPDATE_MODE_DEFAULT`` instead of a
    hand-maintained number that silently rots when the item order changes.
    """
    default = update_policy.UPDATE_MODE_DEFAULT
    for index, item in enumerate(update_policy.update_mode_items()):
        if item and item[0] == default:
            return index
    return 0


_UPDATE_CHECK_MODE_DEFAULT_INDEX = _update_check_mode_default_index()


_PREWARM_DIALOG_SESSION_KEY = "fyr_baker_prewarm_dialog_offered"
_PREWARM_DIALOG_OFFERED_THIS_SESSION = False


def _prewarm_dialog_offered_this_session() -> bool:
    """True when the first-run dialog was already offered in this Blender process.

    Stored in ``bpy.app.driver_namespace`` so a disable/purge/enable reload does not
    forget the offer and re-open a props dialog against torn-down operator RNA.
    """
    global _PREWARM_DIALOG_OFFERED_THIS_SESSION
    ns = getattr(getattr(bpy, "app", None), "driver_namespace", None)
    if isinstance(ns, dict) and ns.get(_PREWARM_DIALOG_SESSION_KEY):
        _PREWARM_DIALOG_OFFERED_THIS_SESSION = True
        return True
    return bool(_PREWARM_DIALOG_OFFERED_THIS_SESSION)


def _mark_prewarm_dialog_offered_this_session() -> None:
    global _PREWARM_DIALOG_OFFERED_THIS_SESSION
    _PREWARM_DIALOG_OFFERED_THIS_SESSION = True
    ns = getattr(getattr(bpy, "app", None), "driver_namespace", None)
    if isinstance(ns, dict):
        ns[_PREWARM_DIALOG_SESSION_KEY] = True


def _clear_prewarm_dialog_offered_this_session_for_tests() -> None:
    global _PREWARM_DIALOG_OFFERED_THIS_SESSION
    _PREWARM_DIALOG_OFFERED_THIS_SESSION = False
    _reset_first_run_dialog_wait()
    ns = getattr(getattr(bpy, "app", None), "driver_namespace", None)
    if isinstance(ns, dict):
        ns.pop(_PREWARM_DIALOG_SESSION_KEY, None)


# Blender opens Preferences (and render, drivers, ...) as separate top-level windows
# that float above the main window. A props dialog invoked from a timer is built in
# the timer's context window, so installing the add-on from the Preferences window
# put the first-run dialog in the main window *underneath* Preferences, where the
# tester never saw it. Wait for the temporary window to close, then open the dialog
# with an explicit override onto the main window's editor region.
_FIRST_RUN_DIALOG_RETRY_SECONDS = 1.0
_FIRST_RUN_DIALOG_MAX_WAIT_SECONDS = 90.0
_FIRST_RUN_DIALOG_WAITED_SECONDS = 0.0


def _reset_first_run_dialog_wait() -> None:
    global _FIRST_RUN_DIALOG_WAITED_SECONDS
    _FIRST_RUN_DIALOG_WAITED_SECONDS = 0.0


# Areas that make a poor popup anchor: the topbar and status bar are slivers, and a
# Preferences editor is the one place the user is already reading settings.
_FIRST_RUN_DIALOG_SKIP_AREAS = frozenset({"PREFERENCES", "TOPBAR", "STATUSBAR"})


def _window_is_temporary(window) -> bool:
    """True for Blender's temporary top-level windows (Preferences, render, ...)."""
    if window is None:
        return False
    if getattr(window, "parent", None) is not None:
        return True
    screen = getattr(window, "screen", None)
    return bool(getattr(screen, "is_temporary", False))


def _main_blender_window(window_manager):
    """The window the user's Blender session lives in, never a temporary one."""
    windows = list(getattr(window_manager, "windows", None) or ())
    if not windows:
        return None
    for window in windows:
        if not _window_is_temporary(window):
            return window
    return windows[0]


def _temporary_window_is_open(window_manager) -> bool:
    return any(_window_is_temporary(window) for window in (getattr(window_manager, "windows", None) or ()))


def _dialog_anchor_region(window):
    """Pick an (area, region) inside ``window`` to anchor the popup on."""
    screen = getattr(window, "screen", None)
    preferred = None
    fallback = None
    for area in (getattr(screen, "areas", None) or ()):
        area_type = str(getattr(area, "type", "") or "")
        if area_type in _FIRST_RUN_DIALOG_SKIP_AREAS:
            continue
        region = None
        for candidate in (getattr(area, "regions", None) or ()):
            if str(getattr(candidate, "type", "") or "") == "WINDOW":
                region = candidate
                break
        if region is None:
            continue
        if area_type == "VIEW_3D":
            if preferred is None:
                preferred = (area, region)
        elif fallback is None:
            fallback = (area, region)
    return preferred or fallback or (None, None)


def _acknowledge_first_run_dialog() -> None:
    """Record that the dialog was offered, and persist that to disk right away.

    Written before the dialog opens rather than in ``execute()``: closing the
    popup with Cancel, Esc, or a click outside it never reaches ``execute()``,
    so an acknowledgment stored only there let the dialog come back on every
    single Blender launch. The dialog is informational and its defaults are the
    shipped ones, so a dismissed dialog is still an answered dialog.

    Saving is safe here because no popup exists yet. The same call made from
    ``execute()`` has to be deferred to a timer instead (see
    ``_finish_backend_prewarm_configuration``).
    """
    prefs = preferences.get_preferences()
    if prefs is None:
        return
    try:
        prefs.backend_prewarm_first_run_acknowledged = True
    except Exception:
        return
    try:
        bpy.ops.wm.save_userpref()
    except Exception:
        pass


def _center_cursor_in_window(window) -> None:
    """Move the pointer to the middle of *window* before a popup opens.

    ``invoke_props_dialog`` places its popup at the mouse and takes no
    placement argument, so a startup dialog otherwise appears wherever the
    pointer happens to rest, including a screen corner. Warping the cursor
    first is the supported way to get a centered popup, and it also leaves the
    pointer on the dialog the user now has to answer.
    """
    cursor_warp = getattr(window, "cursor_warp", None)
    if not callable(cursor_warp):
        return
    try:
        width = int(getattr(window, "width", 0) or 0)
        height = int(getattr(window, "height", 0) or 0)
    except Exception:
        return
    if width <= 0 or height <= 0:
        return
    try:
        cursor_warp(width // 2, height // 2)
    except Exception:
        pass


def _invoke_first_run_dialog(window) -> None:
    """Open the first-run dialog inside ``window`` so it cannot land behind another window."""
    invoke = bpy.ops.master_baker.configure_backend_prewarm
    _center_cursor_in_window(window)
    context = getattr(bpy, "context", None)
    temp_override = getattr(context, "temp_override", None)
    override_ctx = None
    if window is not None and callable(temp_override):
        override = {"window": window}
        screen = getattr(window, "screen", None)
        if screen is not None:
            override["screen"] = screen
        area, region = _dialog_anchor_region(window)
        if area is not None:
            override["area"] = area
        if region is not None:
            override["region"] = region
        try:
            override_ctx = temp_override(**override)
        except Exception:
            override_ctx = None
    if override_ctx is None:
        invoke("INVOKE_DEFAULT")
        return
    with override_ctx:
        invoke("INVOKE_DEFAULT")


class MASTER_BAKER_OT_configure_backend_prewarm(bpy.types.Operator):
    """First-run dialog that lets the user choose how aggressive backend prewarm should be."""

    bl_idname = "master_baker.configure_backend_prewarm"
    bl_label = "Fyr Baker Settings"
    bl_description = (
        "Choose when Fyr Baker starts its bake worker. "
        "Starting it early makes the first bake of a session begin faster"
    )
    # INTERNAL only: REGISTER makes Blender stringify enum labels for the info
    # report after OK. After an add-on reload those RNA item pointers can be NULL,
    # which crashes in Macro_bl_label_length / RNA_property_as_string.
    bl_options = {"INTERNAL"}

    mode: bpy.props.EnumProperty(
        name="Bake Worker Startup",
        items=_backend_prewarm_mode_items,
        # Dynamic items require an integer default (index into the callback result).
        default=1,  # BACKEND_PREWARM_ON_PROJECT_DETECTED
        description=(
            "Choose when to start the bake worker. Starting it early makes the first bake of a session start much faster"
        ),
    )
    prepare_meshes: bpy.props.BoolProperty(
        name="Prepare Meshes Early",
        default=True,
        description=(
            "Prepare high-poly mesh data in advance so the first bake starts faster. "
            "Disable this if a problematic mesh prevents preparation from completing"
        ),
    )
    update_check_mode: bpy.props.EnumProperty(
        name="Update Checks",
        items=_update_check_mode_items,
        # Defaults to Never: nothing contacts the network unless the user opts in here.
        default=_UPDATE_CHECK_MODE_DEFAULT_INDEX,
        description=(
            "Choose how often Fyr Baker checks for updates automatically. "
            "Update checks connect to the internet to look for new versions. "
            "You can also check at any time from the add-on preferences"
        ),
    )

    def invoke(self, context, event):
        del event
        # Refuse to open against a stale RNA type left over from a mid-dialog reload.
        registered = getattr(bpy.types, type(self).__name__, None)
        if registered is not None and registered is not type(self):
            return {"CANCELLED"}
        if not startup_dialogs.acquire(startup_dialogs.FIRST_RUN_SETTINGS):
            return {"CANCELLED"}
        _mark_prewarm_dialog_offered_this_session()
        prefs = preferences.get_preferences()
        if prefs is not None:
            self.mode = preferences.normalize_backend_prewarm_mode(getattr(prefs, "backend_prewarm_mode", None))
            self.prepare_meshes = bool(getattr(prefs, "backend_prewarm_prepare_meshes", True))
            self.update_check_mode = update_policy.get_update_mode(prefs)
        return context.window_manager.invoke_props_dialog(self, width=460)

    def cancel(self, context):
        del context
        startup_dialogs.release(startup_dialogs.FIRST_RUN_SETTINGS)
        return None

    def draw(self, context):
        del context
        layout = self.layout
        try:
            col = layout.column()
            col.use_property_split = True
            col.use_property_decorate = False

            col.label(text="You can change these settings later in Add-on Preferences.", icon="INFO")
            col.separator()

            # Omitted entirely on a build packaged without the updater: the
            # first thing a new customer sees should not be a choice that has
            # exactly one option.
            if update_policy.updater_available():
                row = col.row(align=True)
                row.prop(self, "update_check_mode")
                help_button = row.operator(
                    "master_baker.first_run_setting_help",
                    text="",
                    icon="QUESTION",
                    emboss=False,
                )
                help_button.topic = "UPDATE_CHECKS"

                disclosure = col.column(align=True)
                disclosure.enabled = False
                disclosure.label(text="Update checks connect to the internet to look for new versions.")

                col.separator()
            col.label(text="Fyr Baker can spawn its backend bake worker before you press Bake.")
            col.label(text="The first bake of a session is otherwise much slower because the backend")
            col.label(text="must start, initialize the GPU, compile pipelines, and load mesh caches.")
            col.separator()

            row = col.row(align=True)
            row.prop(self, "mode")
            help_button = row.operator(
                "master_baker.first_run_setting_help",
                text="",
                icon="QUESTION",
                emboss=False,
            )
            help_button.topic = "BACKEND_PREWARM"

            row = col.row(align=True)
            setting = row.row(align=True)
            setting.enabled = self.mode != constants.BACKEND_PREWARM_OFF
            setting.prop(self, "prepare_meshes")
            help_button = row.operator(
                "master_baker.first_run_setting_help",
                text="",
                icon="QUESTION",
                emboss=False,
            )
            help_button.topic = "MESH_CACHES"
        except Exception:
            # Never let draw fail open into Blender's automatic property layout:
            # that path shows raw identifiers as ints and can crash on OK.
            layout.label(text="Could not draw settings. Use Edit → Preferences → Add-ons → Fyr Baker.", icon="ERROR")

    def execute(self, context):
        del context
        startup_dialogs.release(startup_dialogs.FIRST_RUN_SETTINGS)
        prefs = preferences.get_preferences()
        if prefs is None:
            self.report({"ERROR"}, "Fyr Baker preferences are unavailable")
            return {"CANCELLED"}
        prefs.backend_prewarm_mode = preferences.normalize_backend_prewarm_mode(self.mode)
        prefs.backend_prewarm_prepare_meshes = bool(self.prepare_meshes)
        if update_policy.updater_available():
            prefs.update_check_mode = self.update_check_mode
        prefs.backend_prewarm_first_run_acknowledged = True
        # Do not invoke another window-manager operator while Blender is still
        # accepting and tearing down this property dialog. Blender 5.1 performs a
        # final automatic-property redraw after execute(), and save_userpref can
        # leave that redraw holding an invalid operator RNA pointer.
        timers = getattr(getattr(bpy, "app", None), "timers", None)
        try:
            if timers is not None and hasattr(timers, "register"):
                timers.register(_finish_backend_prewarm_configuration, first_interval=0.1)
            else:
                _finish_backend_prewarm_configuration()
        except Exception:
            _finish_backend_prewarm_configuration()
        return {"FINISHED"}


CLASSES = (
    MASTER_BAKER_OT_handle_duplicate_map_outputs,
    MASTER_BAKER_OT_clear_all_caches,
    MASTER_BAKER_OT_clear_logs,
    MASTER_BAKER_OT_first_run_setting_help,
    MASTER_BAKER_OT_configure_backend_prewarm,
    MASTER_BAKER_OT_add_project,
    MASTER_BAKER_OT_bake_selected_materials,
    MASTER_BAKER_OT_rescan_materials,
    MASTER_BAKER_OT_set_output_size_preset,
    MASTER_BAKER_OT_clear_group_uv_override,
    MASTER_BAKER_OT_set_group_uv_override,
    MASTER_BAKER_OT_assign_texture_set,
    MASTER_BAKER_OT_set_active_group,
    MASTER_BAKER_OT_set_active_group_by_index,
    MASTER_BAKER_OT_set_active_project_by_index,
    MASTER_BAKER_OT_select_all_groups,
    MASTER_BAKER_OT_toggle_all_cage_overlays,
    MASTER_BAKER_OT_toggle_group_cage_overlay,
    MASTER_BAKER_OT_toggle_group_cage_coverage,
    MASTER_BAKER_OT_toggle_all_cage_coverage,
    MASTER_BAKER_OT_toggle_project_visibility,
    MASTER_BAKER_OT_toggle_cage_menu_expansion,
    MASTER_BAKER_OT_select_cage_object,
    MASTER_BAKER_OT_rename_group_meshes,
    MASTER_BAKER_OT_toggle_cage_object_visibility,
    MASTER_BAKER_OT_toggle_cage_overlay,
    MASTER_BAKER_OT_combine_groups_into_texture_set,
    MASTER_BAKER_OT_migrate_texture_sets,
    MASTER_BAKER_OT_new_texture_set,
    MASTER_BAKER_OT_clear_texture_set,
    MASTER_BAKER_OT_rename_texture_set,
    MASTER_BAKER_OT_show_texture_set_picker,
    MASTER_BAKER_OT_show_assign_texture_set_menu,
    MASTER_BAKER_OT_show_texture_set_row_menu,
    MASTER_BAKER_OT_dissolve_texture_set,
    MASTER_BAKER_OT_toggle_texture_set_expansion,
    MASTER_BAKER_OT_set_active_texture_set,
    MASTER_BAKER_OT_toggle_texture_set_visibility,
    MASTER_BAKER_OT_toggle_group_visibility,
    MASTER_BAKER_OT_toggle_texture_set_cage_overlay,
    MASTER_BAKER_OT_select_sidebar_meshes,
    MASTER_BAKER_OT_select_sidebar_cage,
    MASTER_BAKER_OT_select_sidebar_maps,
    MASTER_BAKER_OT_select_sidebar_output,
    MASTER_BAKER_OT_select_sidebar_preview,
    MASTER_BAKER_OT_select_bake_panel_section,
    MASTER_BAKER_OT_toggle_settings_section,
    MASTER_BAKER_OT_reset_mm_calibration,
    MASTER_BAKER_OT_save_project_preset,
    MASTER_BAKER_OT_load_project_preset,
    MASTER_BAKER_OT_duplicate_project,
    MASTER_BAKER_OT_remove_project,
    MASTER_BAKER_OT_restore_removed_project,
    MASTER_BAKER_OT_restore_removed_item,
    MASTER_BAKER_OT_add_group,
    MASTER_BAKER_OT_create_group_from_selection,
    MASTER_BAKER_OT_remove_group,
    MASTER_BAKER_OT_add_selected_to_role,
    MASTER_BAKER_OT_add_selected_split_by_role,
    MASTER_BAKER_OT_auto_setup,
    MASTER_BAKER_OT_clear_role_slot,
    MASTER_BAKER_OT_select_group_slot_object,
    MASTER_BAKER_OT_toggle_group_slot_visibility,
    MASTER_BAKER_OT_sync_group_metadata,
    MASTER_BAKER_OT_apply_group_metadata_to_target,
    MASTER_BAKER_OT_set_custom_cage_from_selection,
    MASTER_BAKER_OT_diagnose_cage_check,
    MASTER_BAKER_OT_create_custom_cage_from_low,
    MASTER_BAKER_OT_auto_fit_cage,
    MASTER_BAKER_OT_estimate_cage_offset,
    MASTER_BAKER_OT_adjust_cage_offset,
    MASTER_BAKER_OT_reset_cage_offset,
    MASTER_BAKER_OT_estimate_selected_group_cage_offset,
    MASTER_BAKER_OT_reset_selected_group_cage_offset,
    MASTER_BAKER_OT_create_paint_offset_image,
    MASTER_BAKER_OT_create_paint_skew_image,
    MASTER_BAKER_OT_toggle_paint_isolate,
    MASTER_BAKER_OT_clear_paint_image,
    MASTER_BAKER_OT_estimate_object_cage_offset,
    MASTER_BAKER_OT_reset_object_cage_offset,
    MASTER_BAKER_OT_estimate_selected_low_cage_offset,
    MASTER_BAKER_OT_estimate_scoped_cage_offset,
    MASTER_BAKER_OT_reset_scoped_cage_offset,
    MASTER_BAKER_OT_reset_rear_distance,
    MASTER_BAKER_OT_reset_selected_low_cage_offset,
    MASTER_BAKER_OT_adjust_custom_cage_mesh,
    MASTER_BAKER_OT_smooth_custom_cage_mesh,
    MASTER_BAKER_OT_cleanup_custom_cage_spikes,
    MASTER_BAKER_OT_auto_group_selected_by_suffix,
    MASTER_BAKER_OT_auto_group_selected_by_collection,
    MASTER_BAKER_OT_auto_group_selected_by_name_group,
    MASTER_BAKER_OT_auto_group_scene_by_name,
    MASTER_BAKER_OT_prepare_lowhigh_names,
    MASTER_BAKER_OT_name_from_collections,
    MASTER_BAKER_OT_capture_uv_snapshot,
    MASTER_BAKER_OT_restore_uv_snapshot,
    MASTER_BAKER_OT_rename_uv_snapshot,
    MASTER_BAKER_OT_delete_uv_snapshot,
    MASTER_BAKER_OT_cleanup_orphan_uv_snapshots,
    MASTER_BAKER_OT_optimize_uv_seams,
    MASTER_BAKER_OT_export_workspace,
    MASTER_BAKER_OT_run_preflight,
    MASTER_BAKER_OT_show_bake_state,
    MASTER_BAKER_OT_focus_validation_object,
    MASTER_BAKER_OT_restart_backend,
    MASTER_BAKER_OT_bake_project,
    MASTER_BAKER_OT_confirm_bake_without_uvs,
    MASTER_BAKER_OT_toggle_live_bake,

    MASTER_BAKER_OT_rebuild_changed_maps,
    MASTER_BAKER_OT_mark_all_dirty,
    MASTER_BAKER_OT_clear_dirty,
    MASTER_BAKER_OT_step_map_row_samples,
    MASTER_BAKER_OT_fit_attribute_range,
    MASTER_BAKER_OT_bake_map,
    MASTER_BAKER_OT_cycles_bake_step,
    MASTER_BAKER_OT_cancel_bake,
    MASTER_BAKER_OT_dismiss_progress_overlay,
    MASTER_BAKER_OT_add_map,
    MASTER_BAKER_OT_remove_map,
    MASTER_BAKER_OT_duplicate_map,
    MASTER_BAKER_OT_move_map,
    MASTER_BAKER_OT_restore_map_defaults,
    MASTER_BAKER_OT_reset_map_setting,
    MASTER_BAKER_OT_confirm_low_sample_count,
    MASTER_BAKER_OT_apply_map_stack_preset,
    MASTER_BAKER_OT_refresh_outputs,
    MASTER_BAKER_OT_open_output_folder,
    MASTER_BAKER_OT_copy_output_path,
    MASTER_BAKER_OT_send_to_painter,
    MASTER_BAKER_OT_combine_placeholder_texture_sets,
    MASTER_BAKER_OT_update_in_painter,
    MASTER_BAKER_OT_send_to_toolbag,
    MASTER_BAKER_OT_update_in_toolbag,
    MASTER_BAKER_OT_send_to_photoshop,
    MASTER_BAKER_OT_send_to_designer,
    MASTER_BAKER_OT_update_in_designer,
    MASTER_BAKER_OT_send_to_3dcoat,
    MASTER_BAKER_OT_send_to_mari,
    MASTER_BAKER_OT_open_backend_log,
    MASTER_BAKER_OT_open_gpu_diagnostics,
    MASTER_BAKER_OT_copy_failure_summary,
    MASTER_BAKER_OT_create_support_bundle,
    MASTER_BAKER_OT_load_output_image,
    MASTER_BAKER_OT_open_map_output_image,
    MASTER_BAKER_OT_preview_map_output,
    MASTER_BAKER_OT_set_preview_map,
    MASTER_BAKER_OT_preview_pbr_output,
    MASTER_BAKER_OT_toggle_material_ab_compare,
    MASTER_BAKER_OT_set_pbr_preview_normal_source,
    MASTER_BAKER_OT_restore_preview_materials,
    MASTER_BAKER_OT_toggle_live_normal_preview,
    MASTER_BAKER_OT_external_edit_map_output,
    MASTER_BAKER_OT_previous_output,
    MASTER_BAKER_OT_next_output,
    MASTER_BAKER_OT_toggle_compare_mode,
    MASTER_BAKER_OT_set_image_editor_channel_mode,
    MASTER_BAKER_OT_set_image_editor_mip_level,
    MASTER_BAKER_OT_set_compare_slot,
    MASTER_BAKER_OT_load_compare_slot,
    MASTER_BAKER_OT_swap_compare_slots,
    MASTER_BAKER_OT_isolate_active_group,
    MASTER_BAKER_OT_select_active_group,
    MASTER_BAKER_OT_toggle_active_group_visibility,
    MASTER_BAKER_OT_select_group_role_objects,
    MASTER_BAKER_OT_toggle_group_role_visibility,
    MASTER_BAKER_OT_toggle_reference_visibility,
)


def _maybe_show_first_run_prewarm_dialog():
    """Show the prewarm explainer dialog once per install if not yet acknowledged."""
    try:
        if _prewarm_dialog_offered_this_session():
            return None
        prefs = preferences.get_preferences()
        if prefs is None:
            return None
        if bool(getattr(prefs, "backend_prewarm_first_run_acknowledged", False)):
            _mark_prewarm_dialog_offered_this_session()
            return None
        try:
            from . import bake_backends

            if not bake_backends.fyr_native_lifecycle_enabled(prefs):
                _mark_prewarm_dialog_offered_this_session()
                return None
        except Exception:
            pass
        # Window manager + UI must be ready. invoke_props_dialog needs an active window.
        wm = getattr(bpy, "context", None)
        wm = getattr(wm, "window_manager", None) if wm is not None else None
        if wm is None or not getattr(wm, "windows", None):
            return 1.0  # Try again shortly.
        if startup_dialogs.is_busy(startup_dialogs.FIRST_RUN_SETTINGS):
            return 2.0  # Another startup popup owns the screen; wait for it.
        # Installing from the Preferences window is the common first-run path, and that
        # window floats above the main one. Opening now would bury the dialog, so wait
        # for the temporary window to close. The cap keeps a user who parks Preferences
        # open from losing the dialog for the whole session.
        global _FIRST_RUN_DIALOG_WAITED_SECONDS
        if (
            _temporary_window_is_open(wm)
            and _FIRST_RUN_DIALOG_WAITED_SECONDS < _FIRST_RUN_DIALOG_MAX_WAIT_SECONDS
        ):
            _FIRST_RUN_DIALOG_WAITED_SECONDS += _FIRST_RUN_DIALOG_RETRY_SECONDS
            return _FIRST_RUN_DIALOG_RETRY_SECONDS
        # Mark before invoke so a reload mid-dialog cannot schedule a second copy
        # against torn-down operator RNA (raw property names + crash on OK), and
        # persist the acknowledgment now so dismissing the dialog without
        # pressing OK still counts as having seen it.
        _mark_prewarm_dialog_offered_this_session()
        _acknowledge_first_run_dialog()
        _invoke_first_run_dialog(_main_blender_window(wm))
    except Exception:
        # If the dialog can't be shown for any reason, don't keep retrying;
        # the user can still toggle the preference manually.
        _mark_prewarm_dialog_offered_this_session()
        try:
            prefs = preferences.get_preferences()
            if prefs is not None:
                prefs.backend_prewarm_first_run_acknowledged = True
        except Exception:
            pass
    return None


def _unregister_first_run_prewarm_dialog_timer():
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "unregister"):
        return
    try:
        if not hasattr(timers, "is_registered") or timers.is_registered(_maybe_show_first_run_prewarm_dialog):
            timers.unregister(_maybe_show_first_run_prewarm_dialog)
    except Exception:
        pass
    try:
        if hasattr(timers, "is_registered") and timers.is_registered(_finish_backend_prewarm_configuration):
            timers.unregister(_finish_backend_prewarm_configuration)
    except Exception:
        pass


def register():
    startup_dialogs.reset()
    for cls in CLASSES:
        safe_register_class(cls)
    try:
        from . import setup_progress
        setup_progress.register()
    except ModuleNotFoundError:
        # Headless unit-test environments do not provide Blender's blf/gpu
        # modules. Interactive Blender always does.
        pass
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "register"):
        try:
            if not hasattr(timers, "is_registered") or not timers.is_registered(_low_sample_warning_timer):
                timers.register(_low_sample_warning_timer, first_interval=0.1, persistent=True)
        except Exception:
            pass
    runtime.set_speculative_prepare_callback(_do_speculative_prepare)
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    load_pre = getattr(handlers, "load_pre", None)
    if load_pre is not None and _load_pre not in load_pre:
        load_pre.append(_load_pre)
    load_post = getattr(handlers, "load_post", None)
    if load_post is not None and _load_post not in load_post:
        load_post.append(_load_post)
    save_pre = getattr(handlers, "save_pre", None)
    if save_pre is not None and _save_pre not in save_pre:
        save_pre.append(_save_pre)
    save_post = getattr(handlers, "save_post", None)
    if save_post is not None and _save_post not in save_post:
        save_post.append(_save_post)
    undo_post = getattr(handlers, "undo_post", None)
    if undo_post is not None and _undo_post not in undo_post:
        undo_post.append(_undo_post)
    redo_post = getattr(handlers, "redo_post", None)
    if redo_post is not None and _redo_post not in redo_post:
        redo_post.append(_redo_post)
    depsgraph_post = getattr(handlers, "depsgraph_update_post", None)
    if depsgraph_post is not None and _on_bg_prepare_depsgraph_update not in depsgraph_post:
        depsgraph_post.append(_on_bg_prepare_depsgraph_update)
    _subscribe_workspace_switch()
    # Drop any leftover timer from a previous enable before scheduling a new one.
    _unregister_first_run_prewarm_dialog_timer()
    if not _prewarm_dialog_offered_this_session():
        _reset_first_run_dialog_wait()
        timers = getattr(getattr(bpy, "app", None), "timers", None)
        if timers is not None and hasattr(timers, "register"):
            try:
                timers.register(_maybe_show_first_run_prewarm_dialog, first_interval=1.5)
            except Exception:
                pass


def unregister():
    # Failsafe: if a bake was interrupted by this reload/disable, clear the low-impact
    # flag. Do NOT re-add the overlay handlers here — overlays.unregister drops them and
    # overlays.register re-installs them on the next enable, so re-adding now could leak a
    # handler past teardown.
    try:
        _bake_low_impact_restore(readd_overlays=False)
    except Exception:
        pass
    _reset_prepare_feedback_runtime()
    # Never leak the setup-progress draw handler across reloads (a reload
    # mid-setup previously left overlay handlers alive; see the cage-check
    # GPU-leak incident).
    try:
        from . import setup_progress

        setup_progress.unregister()
    except Exception:
        pass
    _unregister_first_run_prewarm_dialog_timer()
    # If a first-run props dialog is still on screen, mark the session offered so
    # re-enable does not open a second copy against the dying RNA type.
    if startup_dialogs.active_owner() == startup_dialogs.FIRST_RUN_SETTINGS:
        _mark_prewarm_dialog_offered_this_session()
        startup_dialogs.release(startup_dialogs.FIRST_RUN_SETTINGS)
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister"):
        try:
            if not hasattr(timers, "is_registered") or timers.is_registered(_low_sample_warning_timer):
                timers.unregister(_low_sample_warning_timer)
        except Exception:
            pass
    runtime.set_speculative_prepare_callback(None)
    _cancel_live_normal_preview_runtime()
    _stop_dirty_tracker_session()
    _EXTERNAL_EDIT_WATCHER.stop_all()
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    load_pre = getattr(handlers, "load_pre", None)
    if load_pre is not None and _load_pre in load_pre:
        load_pre.remove(_load_pre)
    load_post = getattr(handlers, "load_post", None)
    if load_post is not None and _load_post in load_post:
        load_post.remove(_load_post)
    save_pre = getattr(handlers, "save_pre", None)
    if save_pre is not None and _save_pre in save_pre:
        save_pre.remove(_save_pre)
    save_post = getattr(handlers, "save_post", None)
    if save_post is not None and _save_post in save_post:
        save_post.remove(_save_post)
    undo_post = getattr(handlers, "undo_post", None)
    if undo_post is not None and _undo_post in undo_post:
        undo_post.remove(_undo_post)
    redo_post = getattr(handlers, "redo_post", None)
    if redo_post is not None and _redo_post in redo_post:
        redo_post.remove(_redo_post)
    _unsubscribe_workspace_switch()
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister"):
        try:
            if not hasattr(timers, "is_registered") or timers.is_registered(_reconcile_paint_session_timer):
                timers.unregister(_reconcile_paint_session_timer)
        except Exception:
            pass
    depsgraph_post = getattr(handlers, "depsgraph_update_post", None)
    if depsgraph_post is not None:
        try:
            depsgraph_post.remove(_on_bg_prepare_depsgraph_update)
        except (ValueError, AttributeError):
            pass
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None:
        try:
            if hasattr(timers, "is_registered") and timers.is_registered(_bg_prepare_debounce_fired):
                timers.unregister(_bg_prepare_debounce_fired)
        except Exception:
            pass
        try:
            timers.unregister(_live_normal_preview_timer)
        except Exception:
            pass
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
