from __future__ import annotations

import functools
import textwrap
import time
from pathlib import Path

import bpy

from . import bake_backends, collection_membership, constants, dirty_tracker, export, external_handoff, floater_faces, high_mesh_cache, image_inspection, naming, output_thumbnails, preferences, project_structure, properties, runtime, sidebar_icons, sidebar_state, texture_reprojection, uv_snapshot, validation
from .registration import safe_register_class, safe_unregister_class
from .ui_utils import _begin_collapsible_section, _object_hidden, _hide_icon_for_objects, _icon_kwargs, _ui_list_rows, duplicate_warning_icon_kwargs
from .ui_map_settings import _map_stack_item_label, draw_active_map_settings, exact_duplicate_warning_message
from .ui_group_editor import _draw_group_role_slot_list, draw_group_editor
from .ui_sidebar_viewport import (
    draw_cage_offset_controls,
    draw_rear_distance_control,
    draw_cage_viewport_overlay_controls,
    draw_sidebar_viewport_controls,
    draw_skew_needle_controls,
)
from .ui_image_editor import draw_image_editor_controls


# ---------------------------------------------------------------------------
# Draw-path caches
#
# Blender re-runs every panel draw callback on any redraw, and during a bake the
# region redraws at the progress-poll cadence. Anything a draw callback does that
# touches the filesystem therefore runs several times a second, per panel, per
# visible row. These memos keep the *draw* path off the disk without hiding real
# changes: every entry carries a short TTL, so a file deleted or replaced outside
# Blender is still noticed within about a second, and the cache keys fold in a
# cheap revision of the project so a bake or an edit invalidates immediately.
#
# Nothing here caches a bpy struct pointer. Only plain values (bools, strings,
# counts, small tuples) are stored, so a collection that is rebuilt underneath us
# can never leave a dangling reference behind.
# ---------------------------------------------------------------------------

#: Seconds a cached filesystem answer stays good for.
_DRAW_CACHE_TTL_S = 1.0
#: Entries kept before the stale ones are swept. Well above the number of distinct
#: output paths a single panel draw can ask about.
_DRAW_CACHE_MAX_ENTRIES = 512

_PATH_IS_FILE_CACHE: dict[str, tuple[float, bool]] = {}
_OUTPUT_LOOKUP_CACHE: dict[tuple, tuple[float, bool]] = {}
_PREFLIGHT_SUMMARY_CACHE: dict[tuple, tuple[float, object, list, list, list]] = {}


def _sweep_draw_cache(cache: dict, now: float) -> None:
    if len(cache) <= _DRAW_CACHE_MAX_ENTRIES:
        return
    for key in [key for key, entry in cache.items() if (now - entry[0]) >= _DRAW_CACHE_TTL_S]:
        cache.pop(key, None)
    if len(cache) > _DRAW_CACHE_MAX_ENTRIES:
        cache.clear()


def clear_draw_caches() -> None:
    """Drop every draw-path memo. Cheap; safe to call from anywhere."""
    _PATH_IS_FILE_CACHE.clear()
    _OUTPUT_LOOKUP_CACHE.clear()
    _PREFLIGHT_SUMMARY_CACHE.clear()


def _cached_path_is_file(path_text: str) -> bool:
    """``Path(path_text).is_file()`` with one stat per path per TTL window.

    The map stack asks the same question from several callers on one redraw
    (the row icon, the preview gate, the "has source" flag); without this each
    caller paid its own stat.
    """
    if not path_text:
        return False
    now = time.monotonic()
    cached = _PATH_IS_FILE_CACHE.get(path_text)
    if cached is not None and (now - cached[0]) < _DRAW_CACHE_TTL_S:
        return cached[1]
    try:
        exists = Path(path_text).is_file()
    except OSError:
        exists = False
    _sweep_draw_cache(_PATH_IS_FILE_CACHE, now)
    _PATH_IS_FILE_CACHE[path_text] = (now, exists)
    return exists


def _project_output_revision(project) -> tuple:
    """Cheap identity of "which outputs does this project currently have".

    Uses only values already in memory: the project's own pointer, the job id of
    the last run, and the size plus final entry of ``latest_outputs``. A bake
    flips ``last_job_id`` at start, and any add/remove/rewrite of outputs moves
    the count or the last file path, so a stale answer cannot outlive the TTL.
    """
    try:
        pointer = int(project.as_pointer())
    except Exception:
        pointer = id(project)
    outputs = getattr(project, "latest_outputs", None) or ()
    try:
        count = len(outputs)
    except Exception:
        count = 0
    last_file_path = ""
    if count:
        try:
            last_file_path = str(getattr(outputs[count - 1], "file_path", "") or "")
        except Exception:
            last_file_path = ""
    return (
        pointer,
        str(getattr(project, "last_job_id", "") or ""),
        count,
        last_file_path,
    )


def _cached_output_flag(key: tuple, compute) -> bool:
    now = time.monotonic()
    cached = _OUTPUT_LOOKUP_CACHE.get(key)
    if cached is not None and (now - cached[0]) < _DRAW_CACHE_TTL_S:
        return cached[1]
    try:
        value = bool(compute())
    except Exception:
        value = False
    _sweep_draw_cache(_OUTPUT_LOOKUP_CACHE, now)
    _OUTPUT_LOOKUP_CACHE[key] = (now, value)
    return value


# Meshes holds the hierarchy. Maps is the map stack. Output is folder, size, and format.
# Preview stays until it has a new home.
SIDEBAR_NAV_ITEMS = (
    (constants.SIDEBAR_MESHES, "Meshes", "OUTLINER_OB_MESH", "", "master_baker.select_sidebar_meshes"),
    (constants.SIDEBAR_CAGE, "Cage", "MOD_SHRINKWRAP", "cage", "master_baker.select_sidebar_cage"),
    (constants.SIDEBAR_MAPS, "Maps", "TEXTURE_DATA", "maps", "master_baker.select_sidebar_maps"),
    (constants.SIDEBAR_OUTPUT, "Output", "FILE_FOLDER", "output", "master_baker.select_sidebar_output"),
    (constants.SIDEBAR_PREVIEW, "Preview", "MATERIAL", "preview", "master_baker.select_sidebar_preview"),
)

MAP_CATEGORY_GROUPS = (
    ("Geometry & Surface", "NORMALS_FACE", (constants.MAP_NORMAL, constants.SHORTCUT_DERIVATIVE, constants.MAP_OBJECT_NORMAL, constants.MAP_WORLD_NORMAL, constants.MAP_BENT_NORMAL, constants.MAP_HEIGHT)),
    ("Occlusion & Cavity", "MOD_BEVEL", (constants.MAP_AO, constants.MAP_CURVATURE, constants.MAP_THICKNESS, constants.MAP_DENSITY, constants.MAP_CAVITY, constants.MAP_CONCAVE, constants.MAP_CONVEX)),
    ("Utility & Data", "PROPERTIES", (constants.MAP_ID, constants.MAP_POSITION, constants.MAP_OPACITY, constants.MAP_VERTEX_COLOR, constants.MAP_ATTRIBUTE, constants.MAP_WIREFRAME, constants.MAP_ENV_LIGHT)),
    ("Material", "NODE_MATERIAL", (
        constants.MATERIAL_SHORTCUT_ALBEDO,
        constants.MATERIAL_SHORTCUT_ROUGHNESS,
        constants.MATERIAL_SHORTCUT_METALNESS,
        constants.MATERIAL_SHORTCUT_EMISSION,
        constants.MATERIAL_SHORTCUT_OPACITY,
        constants.MATERIAL_SHORTCUT_SPECULAR,
        constants.MATERIAL_SHORTCUT_TRANSMISSION,
        constants.MATERIAL_SHORTCUT_NORMAL,
    )),
)

# Scene Lighting: Lighting, Lit Color, Direct and Indirect Lighting (one picker entry).
_LIGHTING_MAP_CATEGORY_GROUP = (
    "Lighting", "LIGHT", (constants.MAP_SCENE_LIGHTING,),
)


def _resolved_renderer_for_ui():
    """Return preferences plus a draw-safe resolved renderer snapshot."""
    prefs = preferences.get_preferences()
    try:
        resolved = bake_backends.resolve_active_render_backend(prefs)
    except Exception:
        resolved = None
    return prefs, resolved


def _draw_renderer_quick_controls(layout):
    """Compact, editable renderer controls for the main quick-settings surface."""
    prefs, resolved = _resolved_renderer_for_ui()
    caps = resolved.capabilities if resolved is not None else bake_backends.active_capabilities(prefs)

    renderer_col = layout.column(align=True)
    renderer_col.label(text="Bake Renderer", icon="RENDER_STILL")
    if prefs is not None:
        renderer_col.prop(prefs, "render_backend", text="")
    active_label = resolved.label if resolved is not None else caps.label
    active_row = renderer_col.row(align=True)
    active_row.enabled = False
    active_row.label(text=f"Active: {active_label}")
    # AUTO landed on Cycles: say why in one line (no DXR on this GPU, no backend
    # exe on this platform) so the artist is not left guessing why the Fyr-only
    # controls vanished.
    fallback_reason = bake_backends.auto_fallback_reason(prefs) if resolved is not None else ""
    if fallback_reason:
        reason_row = renderer_col.row(align=True)
        reason_row.enabled = False
        reason_row.label(text=fallback_reason, icon="INFO")

    if prefs is not None and caps.backend_id == "cycles":
        renderer_col.prop(prefs, "cycles_device", text="Device")
        if preferences.normalize_cycles_device(getattr(prefs, "cycles_device", None)) == constants.CYCLES_DEVICE_GPU:
            available, reason = preferences.cycles_gpu_compute_available()
            if not available:
                warning = renderer_col.row(align=True)
                warning.alert = True
                warning.label(text=reason, icon="ERROR")
    elif prefs is not None:
        renderer_col.prop(prefs, "bake_device", text="Device")
    return caps


def _map_category_groups() -> tuple:
    """The map-picker categories."""
    return MAP_CATEGORY_GROUPS + (_LIGHTING_MAP_CATEGORY_GROUP,)

# Preserve the legacy helper name while the implementation lives in ui_map_settings.
_draw_active_map_settings = draw_active_map_settings


# Label for the height field while the aspect lock drives it from X. Kept as a compact
# field label (never a popup or an extra info row) so the panel stays quiet, but the
# override stops being silent: without it, typing a height that snaps straight back to the
# width reads as a bug rather than as the lock doing its job.
_RESOLUTION_Y_LOCKED_LABEL = "Y (linked)"


def _resolution_preset_button_label(project) -> str:
    preset = getattr(project, "resolution_preset", constants.OUTPUT_SIZE_CUSTOM)
    if preset == constants.OUTPUT_SIZE_1024:
        return "1K"
    if preset == constants.OUTPUT_SIZE_2048:
        return "2K"
    if preset == constants.OUTPUT_SIZE_4096:
        return "4K"
    if preset == constants.OUTPUT_SIZE_8192:
        return "8K"
    if preset == constants.OUTPUT_SIZE_512:
        return "512"
    return "Custom"


def _abspath(path_value: str) -> str:
    value = str(path_value or "").strip()
    if not value:
        return ""
    abspath = getattr(getattr(bpy, "path", None), "abspath", None)
    if callable(abspath):
        try:
            return str(abspath(value) or "").strip()
        except Exception:
            pass
    return value


def _image_icon_value(image) -> int:
    if image is None:
        return 0
    image_path = _abspath(str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or ""))
    if image_path:
        return output_thumbnails.get_output_icon_value(image_path)
    preview = getattr(image, "preview", None)
    try:
        return int(getattr(preview, "icon_id", 0) or 0)
    except Exception:
        return 0



def _group_collection_name(group) -> str:
    collection = getattr(properties.group_collections_state(group), "group_collection", None)
    if collection is None:
        return ""
    try:
        return str(collection.name or "").strip()
    except ReferenceError:
        return ""


def _group_uv_summary(group) -> tuple[str, str]:
    active_low_slot = properties.peek_active_low_slot(group)
    active_low = getattr(active_low_slot, "object_ref", None) if active_low_slot is not None else None
    active_low_data = getattr(active_low, "data", None) if active_low is not None else None
    requested_uv = str(getattr(group, "uv_layer_name", "") or "").strip()

    if active_low is None or getattr(active_low, "type", None) != "MESH" or active_low_data is None:
        return "UV: No Low Mesh", "ERROR"

    uv_layers = getattr(active_low_data, "uv_layers", None)
    if not uv_layers:
        return "UV: Missing", "ERROR"

    available_uvs = {layer.name for layer in uv_layers}
    if requested_uv:
        if requested_uv in available_uvs:
            return f"UV: {requested_uv}", "GROUP_UVS"
        return f"UV: Missing ({requested_uv})", "ERROR"

    active_uv = getattr(uv_layers, "active", None)
    if active_uv is not None:
        return f"UV: {active_uv.name}", "GROUP_UVS"
    return "UV: Missing", "ERROR"


def _group_setup_status(group) -> tuple[str, str]:
    summary = properties.summarize_group_roles(group)
    if summary["low_count"] <= 0:
        return "Missing Low", "ERROR"
    if summary["high_count"] <= 0:
        return "Missing High", "ERROR"
    if summary["cage_mode"] == constants.CAGE_MODE_CUSTOM and not summary["has_custom_cage"]:
        return "Missing Cage", "ERROR"
    uv_text, uv_icon = _group_uv_summary(group)
    if uv_icon == "ERROR":
        return uv_text, uv_icon
    return "Ready", "CHECKMARK"


def _project_issue_summary(project) -> tuple[object, list[object], list[object]]:
    issues = validation.validate_bake_project(project, check_topology=False)
    errors, warnings = validation.summarize_issues(issues)
    return issues, errors, warnings


def _project_has_meshes(project) -> bool:
    """True once any bake group has at least one low or high mesh assigned.

    Drives progressive disclosure: before this holds the project is still in the
    "add meshes" staging step, so texture-set, cage, and bake controls are hidden.
    """
    if project is None:
        return False
    for g in getattr(project, "groups", []):
        summary = properties.summarize_group_roles(g)
        if summary["low_count"] > 0 or summary["high_count"] > 0:
            return True
    return False


def _project_ready_to_bake(project) -> bool:
    """True once a group has a low mesh and at least one map is enabled."""
    if project is None:
        return False
    has_low = any(
        properties.summarize_group_roles(g)["low_count"] > 0 for g in getattr(project, "groups", [])
    )
    if not has_low:
        return False
    return any(
        item.enabled and not getattr(item, "is_add_phantom", False)
        for item in getattr(project, "maps", [])
    )


def _bake_state(project) -> tuple[object | None, bool, bool]:
    """Active-bake snapshot plus global/project busy flags.

    Blender's addon-side Cycles material queue keeps running after the backend
    process exits, so it counts as a running bake here. Otherwise the panel would
    restore the Bake button, unlock the output settings, and show the previous run's
    "Last bake" time while Blender is still baking material detail.
    """
    active_bake = runtime.active_bake_snapshot()
    backend_running = active_bake is not None and bool(getattr(active_bake, "running", False))
    # Match the bake-only id too: `last_job_id` is stamped by every prepare, so a
    # prepare landing mid-run would make the project stop recognising its own bake
    # and swap the Stop button back to a greyed-out Bake while the bake carried on.
    project_job_ids = {
        str(getattr(project, attribute, "") or "").strip()
        for attribute in ("last_bake_job_id", "last_job_id")
    }
    project_job_ids.discard("")
    material_status = export.active_material_bake_status()
    bake_running = backend_running or material_status is not None
    project_bake_running = bool(
        (backend_running and str(getattr(active_bake, "job_id", "") or "").strip() in project_job_ids)
        or (material_status is not None and str(material_status.job_id or "").strip() in project_job_ids)
    )
    return active_bake, bake_running, project_bake_running


def _cycles_material_map_count(project) -> int:
    """Enabled Material maps that will actually run through Blender/Cycles.

    Native Material IR maps use the backend; counting every MATERIAL row here
    falsely warned \"Cycles — slower\" even when IR was active.
    """
    count = 0
    for item in getattr(project, "maps", []):
        if not getattr(item, "enabled", False) or getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "") or "") != constants.MAP_MATERIAL:
            continue
        route = str(getattr(item, "execution_route", "") or constants.EXECUTION_ROUTE_AUTO).strip().upper()
        if route == constants.EXECUTION_ROUTE_BACKEND:
            continue
        if route == constants.EXECUTION_ROUTE_BLENDER:
            count += 1
            continue
        status = str(getattr(item, "material_status_message", "") or "")
        status_l = status.lower()
        if "cycles" in status_l or "fallback" in status_l:
            count += 1
            continue
        if not status or "fyr" in status_l:
            # Empty = happy Auto→Fyr (or not baked yet). Prefer IR; don't cry wolf.
            continue
    return count


def _draw_cycles_material_hint(layout, project) -> None:
    """Warn only when Material maps are actually queued for Cycles."""
    count = _cycles_material_map_count(project)
    if count <= 0:
        return
    row = layout.row(align=True)
    row.active = False
    row.label(
        text=f"{count} Material map{'s' if count != 1 else ''} bake in Cycles (slower)",
        icon="TIME",
    )


def _project_high_triangle_count(project) -> int:
    """Triangles across every high mesh in the project, from the base mesh data.

    sum(n - 2) over the polygons is loops - 2 * polygons, so this is O(1) per mesh and
    safe to run on every redraw. Modifiers are not evaluated (a draw must stay cheap).
    """
    seen = set()
    total = 0
    for group in getattr(project, "groups", None) or ():
        try:
            highs = project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH)
        except Exception:  # noqa: BLE001 - a hint must never break the panel
            continue
        for obj in highs:
            mesh = getattr(obj, "data", None)
            if mesh is None or getattr(obj, "type", "") != "MESH" or mesh.name_full in seen:
                continue
            seen.add(mesh.name_full)
            total += max(0, len(mesh.loops) - 2 * len(mesh.polygons))
    return total


def _draw_cycles_heavy_high_hint(layout, project, *, cycles_active: bool) -> None:
    """Warn when Cycles will load a very dense high poly.

    Cycles keeps the whole high in memory as its own BVH; an 87M-triangle sculpt ran
    an OptiX render out of GPU and shared memory (2026-10-14). Shown only when this
    bake actually goes through Cycles: the Cycles renderer, or Material maps queued
    for the Cycles path. The FYR renderer streams the high and is not affected.
    """
    if not cycles_active and _cycles_material_map_count(project) <= 0:
        return
    triangles = _project_high_triangle_count(project)
    if triangles <= constants.CYCLES_AUTO_RECOVERY_MAX_TRIANGLES:
        return
    col = layout.column(align=True)
    head = col.row(align=True)
    head.alert = True
    head.label(text=f"High poly: {triangles / 1e6:.1f}M triangles", icon="ERROR")
    for line in ("Cycles may run out of memory or take", "very long on this. Decimate the high", "poly if you can."):
        row = col.row(align=True)
        row.active = False
        row.label(text=line, icon="BLANK1")


def _progress_factor(project) -> float:
    try:
        percent = float(getattr(project, "last_progress_percent", 0.0) or 0.0)
    except Exception:
        percent = 0.0
    return max(0.0, min(percent / 100.0, 1.0))


def _progress_text(project, *, bake_running: bool = False) -> str:
    try:
        percent = float(getattr(project, "last_progress_percent", 0.0) or 0.0)
    except Exception:
        percent = 0.0
    if bake_running and percent <= 0.0:
        percent = 0.0
    return f"{percent:.1f}%"


def _live_bake_elapsed_seconds() -> float:
    """Wall-clock seconds since the active bake launched, or 0.0 if none is running.

    Reads the running snapshot's monotonic start_time so the panel can tick a live
    timer; it advances at the bake poll cadence (each poll tags a redraw)."""
    snapshot = runtime.active_bake_snapshot()
    if snapshot is None or not bool(getattr(snapshot, "running", False)):
        return 0.0
    start = float(getattr(snapshot, "start_time", 0.0) or 0.0)
    if start <= 0.0:
        return 0.0
    import time as _time
    return max(0.0, _time.monotonic() - start)


def _warming_up_label(elapsed: str) -> str:
    """Label for the scene-cache prewarm wait. When the prewarm is an out-of-memory
    recovery (backend restarted after a 'bad allocation' failure), say so — otherwise
    a re-prewarm right after a failed bake looks like a mystery to the user."""
    oom = getattr(runtime, "prewarm_is_oom_recovery", lambda: False)()
    base = "Recovering from out of memory, rebuilding scene cache…" if oom else "Warming up scene cache…"
    return f"{base} ({elapsed})" if elapsed else base


#: Percent at or above which the overall bar is full but the backend is still
#: working (denoise, dilation, image encode, file writes). Reported by testers as
#: "100% but it keeps baking" — the bar was truthful about the map loop and silent
#: about everything after it.
_PROGRESS_FINALIZING_THRESHOLD = 99.5


#: Map names to show before collapsing the rest into "+N more".
_STEP_LABEL_MAX_MAPS = 2


def _condense_map_list(message: str) -> str:
    """Collapse the backend's comma-separated map list to something a row can hold.

    The fused shading window works every map of a batch at once and names them all:
    "Shading Pottery / Normal,OBJECT_NORMAL,WORLD_NORMAL,AO,CURVATURE,..." runs well
    past the panel width. Keep the first couple and count the rest.
    """
    head, separator, tail = message.rpartition(" / ")
    if not separator or "," not in tail:
        return message
    names = [part.strip() for part in tail.split(",") if part.strip()]
    if len(names) <= _STEP_LABEL_MAX_MAPS + 1:
        return message
    shown = ", ".join(naming.map_label(name) for name in names[:_STEP_LABEL_MAX_MAPS])
    return f"{head}{separator}{shown} +{len(names) - _STEP_LABEL_MAX_MAPS} more"


def _cancelling_label() -> str:
    """Label for a cancel that has been requested but not yet taken effect.

    A cancel is honoured at the worker's next checkpoint, so the bar legitimately
    keeps moving for a few seconds afterwards. Saying only "Cancelling bake" while
    progress advances reads as the button having done nothing, so say how long it has
    been pending and what it is waiting for.
    """
    import time as _time

    from . import operators as _operators

    # Cycles cannot be interrupted inside a map, so its wait is a hard floor and there
    # is nothing to escalate to; say what it is waiting for and leave it alone.
    if _operators.cycles_async_cancel_pending():
        waited = _operators.cycles_async_cancel_elapsed()
        suffix = f" ({waited:.0f}s)" if waited > 0.0 else ""
        return f"Cancelling, finishing the current pass{suffix}"

    snapshot = runtime.active_bake_snapshot()
    if snapshot is None or not getattr(snapshot, "cancel_requested", False):
        return ""
    requested_at = float(getattr(snapshot, "cancel_requested_at", 0.0) or 0.0)
    label = "Cancelling, finishing the current batch"
    if requested_at > 0.0:
        waited = max(0.0, _time.monotonic() - requested_at)
        label = f"{label} ({waited:.0f}s)"
    return f"{label}. Press Stop again to force it."


def _current_step_label(project) -> str:
    """What the bake is working on right now, as a short human phrase.

    Prefers the backend's own message ("Baking AO for Barrel"); falls back to the
    active map name so the panel never goes silent mid-bake.
    """
    cancelling = _cancelling_label()
    if cancelling:
        return cancelling
    message = str(getattr(project, "last_status_message", "") or "").strip()
    if message:
        return _condense_map_list(message)
    active_map = str(getattr(project, "last_active_map", "") or "").strip()
    if active_map:
        label = naming.map_label(active_map)
        active_group = str(getattr(project, "last_active_group", "") or "").strip()
        return f"Baking {label}" + (f" ({active_group})" if active_group else "")
    return ""


def _draw_progress_bar(layout, project, *, bake_running: bool = False) -> None:
    factor = _progress_factor(project)
    # When the bake's RUN is queued behind the background prewarm, it sits at ~0% until the
    # high-scene BVH + GPU resources finish building. Label that wait as warming-up on the bar so
    # it reads as prep, not a stuck/slow bake.
    if bake_running and factor <= 0.001 and runtime.is_bake_started_during_prewarm():
        elapsed = runtime.prewarm_elapsed_str()
        text = _warming_up_label(elapsed)
    else:
        text = _progress_text(project, bake_running=bake_running)
        # Append a live elapsed timer so the bar reports real wall-clock time.
        # No ETA: backend percent advances in coarse per-group steps, not
        # linearly with time, so any extrapolated "time left" is unreliable.
        if bake_running:
            try:
                percent = float(getattr(project, "last_progress_percent", 0.0) or 0.0)
            except Exception:
                percent = 0.0
            if percent >= _PROGRESS_FINALIZING_THRESHOLD:
                # The map loop is done but the job is not: denoise, dilation, encode
                # and the file writes all live past the last percent tick.
                text = "Finalizing outputs…"
            elapsed_seconds = _live_bake_elapsed_seconds()
            elapsed_text = runtime.format_duration(elapsed_seconds)
            if elapsed_text:
                text = f"{text}  ·  {elapsed_text}"
    progress_fn = getattr(layout, "progress", None)
    if callable(progress_fn):
        try:
            progress_fn(factor=factor, type="BAR", text=text)
            # Second bar: current step progress (-1 = indeterminate/not shown).
            try:
                stage_percent = float(getattr(project, "last_stage_progress_percent", -1.0) or -1.0)
            except Exception:
                stage_percent = -1.0
            step_label = _current_step_label(project) if bake_running else ""
            if bake_running and stage_percent >= 0.0:
                stage_text = f"{step_label}: {stage_percent:.0f}%" if step_label else f"Step: {stage_percent:.0f}%"
                progress_fn(factor=max(0.0, min(stage_percent / 100.0, 1.0)), type="BAR", text=stage_text)
            elif step_label:
                # No per-step percentage from this route/stage — still say WHAT is
                # running. Without this the panel showed a bare percentage for the
                # whole bake and went nameless exactly when a user wonders why it is
                # taking so long.
                step_row = layout.row(align=True)
                step_row.active = False
                step_row.label(text=step_label, icon="RENDER_STILL")
            return
        except Exception:
            pass
    row = layout.row(align=True)
    row.label(text=f"Progress: {text}")


def _find_baking_project():
    """Return the project that owns the currently running bake, or None.

    The status bar is a global (window-level) region, so it cannot rely on the active
    scene's active project — it must resolve the project whose job the backend is baking
    by matching the running snapshot's job_id across every scene."""
    snapshot = runtime.active_bake_snapshot()
    if snapshot is None or not getattr(snapshot, "running", False):
        return None
    job_id = str(getattr(snapshot, "job_id", "") or "").strip()
    if not job_id:
        return None
    for scene in getattr(bpy.data, "scenes", []):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []):
            if str(getattr(project, "last_job_id", "") or "").strip() == job_id:
                return project
    return None


def _statusbar_bake_progress_draw(self, context):
    """STATUSBAR_HT_header append handler: draw a compact bake progress bar in the footer
    while a bake runs, next to the scene statistics, and nothing when idle.

    Wrapped in a bare except: an exception raised from a header draw callback breaks the
    entire status bar for the session, so a stray failure must never propagate."""
    try:
        prefs = preferences.get_preferences()
        if prefs is not None and not getattr(prefs, "show_statusbar_progress", True):
            return
        project = _find_baking_project()
        if project is None:
            return
        factor = _progress_factor(project)
        if factor <= 0.001 and runtime.is_bake_started_during_prewarm():
            elapsed = runtime.prewarm_elapsed_str()
            oom = getattr(runtime, "prewarm_is_oom_recovery", lambda: False)()
            base = "Baking: recovering from out of memory…" if oom else "Baking: warming up…"
            text = f"{base} ({elapsed})" if elapsed else base
        else:
            parts = []
            status = _current_step_label(project)
            if factor * 100.0 >= _PROGRESS_FINALIZING_THRESHOLD:
                # Map loop finished; denoise/dilate/encode/write still to go.
                status = "Finalizing outputs…"
            if status:
                parts.append(status)
            parts.append(f"{factor * 100.0:.0f}%")
            elapsed_text = runtime.format_duration(_live_bake_elapsed_seconds())
            if elapsed_text:
                parts.append(elapsed_text)
            text = "  ·  ".join(parts)
        layout = self.layout
        layout.separator_spacer()
        row = layout.row(align=True)
        progress_fn = getattr(row, "progress", None)
        if callable(progress_fn):
            row.progress(factor=factor, type="BAR", text=text)
        else:
            row.label(text=f"Bake  {text}", icon="RENDER_STILL")
    except Exception:
        pass


def _register_statusbar_progress():
    """Append the footer progress handler. The live handler is stashed on the type so it
    survives addon reloads (which purge this module and its globals) and the stale copy
    from a previous session can be removed before re-appending."""
    prior = getattr(bpy.types.STATUSBAR_HT_header, "_master_baker_statusbar_fn", None)
    if prior is not None:
        try:
            bpy.types.STATUSBAR_HT_header.remove(prior)
        except Exception:
            pass
    bpy.types.STATUSBAR_HT_header.append(_statusbar_bake_progress_draw)
    bpy.types.STATUSBAR_HT_header._master_baker_statusbar_fn = _statusbar_bake_progress_draw


def _unregister_statusbar_progress():
    fn = getattr(bpy.types.STATUSBAR_HT_header, "_master_baker_statusbar_fn", None)
    if fn is not None:
        try:
            bpy.types.STATUSBAR_HT_header.remove(fn)
        except Exception:
            pass
        try:
            del bpy.types.STATUSBAR_HT_header._master_baker_statusbar_fn
        except Exception:
            pass



def _active_group_name_for_maps(project) -> str:
    group = _active_group(project)
    return str(getattr(group, "name", "") or "")


def _candidate_output_group_names(project, group_name: str) -> list[str]:
    normalized_group_name = str(group_name or "").strip()
    if not normalized_group_name:
        return [""]

    candidates = [normalized_group_name]
    texture_set_name = ""
    for group in getattr(project, "groups", []):
        current_group_name = str(getattr(group, "name", "") or "").strip()
        if current_group_name.casefold() != normalized_group_name.casefold():
            continue
        metadata_state = properties.group_metadata_state(group)
        texture_set_name = str(getattr(metadata_state, "texture_set_name", "") or "").strip()
        if texture_set_name and texture_set_name.casefold() != current_group_name.casefold():
            candidates.append(texture_set_name)
        break
    if texture_set_name:
        known_candidates = {candidate.casefold() for candidate in candidates}
        for group in getattr(project, "groups", []):
            current_group_name = str(getattr(group, "name", "") or "").strip()
            if not current_group_name or current_group_name.casefold() == normalized_group_name.casefold():
                continue
            metadata_state = properties.group_metadata_state(group)
            current_texture_set_name = str(getattr(metadata_state, "texture_set_name", "") or "").strip()
            if current_texture_set_name.casefold() != texture_set_name.casefold():
                continue
            if current_group_name.casefold() in known_candidates:
                continue
            candidates.append(current_group_name)
            known_candidates.add(current_group_name.casefold())
    return candidates


def _resolve_map_output_target(project, *, map_uuid: str = "", map_type: str = "", group_name: str = "", output_suffix: str = ""):
    for candidate_group_name in _candidate_output_group_names(project, group_name):
        output_index = properties.resolve_output_selection_index(
            project,
            map_uuid=map_uuid,
            map_type=map_type,
            group_name=candidate_group_name,
            output_suffix=output_suffix,
            strict=bool(candidate_group_name),
        )
        if output_index is None:
            continue
        output_target = properties.peek_latest_output(project, output_index)
        if output_target is None:
            continue
        if candidate_group_name:
            target_group_name = str(getattr(output_target, "group_name", "") or "").strip().casefold()
            if target_group_name != candidate_group_name.casefold():
                continue
        source_file_path = _abspath(str(getattr(output_target, "file_path", "") or ""))
        if not _cached_path_is_file(source_file_path):
            continue
        return output_target, source_file_path
    return None, ""


def _map_source_context(project, map_item, *, group_name: str) -> dict[str, object]:
    output_suffix = properties.effective_map_output_suffix(project, map_item) or "" if project is not None else ""
    map_uuid = properties.ensure_map_setting_uuid(map_item)
    output_target, source_file_path = _resolve_map_output_target(
        project,
        map_uuid=map_uuid,
        map_type=getattr(map_item, "map_type", ""),
        group_name=group_name,
        output_suffix=output_suffix,
    )
    has_source = output_target is not None
    return {
        "output_target": output_target,
        "has_source": has_source,
        "source_file_path": source_file_path,
    }


def _map_item_visualization_available(map_item, *, has_source: bool) -> bool:
    return bool(getattr(map_item, "enabled", False)) or bool(has_source)



# Material-project "+" catalog: PBR channels (via the _MAT_* shortcuts add_map translates
# to MAP_MATERIAL + channel) plus material-space Normal. No geometry/projection maps.
_MATERIAL_CATALOG_ENTRIES = (
    (constants.MATERIAL_SHORTCUT_ALBEDO, "Base Color"),
    (constants.MATERIAL_SHORTCUT_ROUGHNESS, "Roughness"),
    (constants.MATERIAL_SHORTCUT_METALNESS, "Metalness"),
    (constants.MATERIAL_SHORTCUT_EMISSION, "Emission"),
    (constants.MATERIAL_SHORTCUT_OPACITY, "Opacity"),
    (constants.MATERIAL_SHORTCUT_SPECULAR, "Specular"),
    (constants.MATERIAL_SHORTCUT_TRANSMISSION, "Transmission"),
)


def _draw_material_map_catalog(layout, *, search_text: str = "") -> None:
    query = str(search_text or "").strip().casefold()
    entries = list(_MATERIAL_CATALOG_ENTRIES) + [(constants.MAP_NORMAL, "Normal")]
    box = layout.box()
    box.label(text="Material Channels", icon="MATERIAL")
    col = box.column(align=True)
    match_count = 0
    for map_type, label in entries:
        if query and query not in label.casefold():
            continue
        row = col.row(align=True)
        row.label(text=label)
        op = row.operator("master_baker.add_map", text="", icon="ADD")
        op.map_type = map_type
        match_count += 1
    if query and match_count == 0:
        layout.label(text="No matching channels", icon="INFO")


def _draw_map_catalog(layout, *, project=None, search_text: str = "") -> None:
    if project is not None and getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL:
        _draw_material_map_catalog(layout, search_text=search_text)
        return
    query = str(search_text or "").strip().casefold()
    # Maps the active renderer cannot produce stay listed but greyed — a saved project
    # must still show why a row is inert rather than having it silently vanish.
    caps = bake_backends.active_capabilities()
    unsupported_maps = (
        {
            map_type
            for map_type, level in caps.map_fidelity.items()
            if level == "unsupported"
        }
        if caps.backend_id == "cycles"
        else frozenset()
    )
    if unsupported_maps:
        note = layout.row(align=True)
        note.enabled = False
        note.label(text=f"{caps.label} active. Greyed maps need Fyr", icon="INFO")
    match_count = 0
    for title, icon, map_types in _map_category_groups():
        category_matches = bool(query and query in title.casefold())
        visible_map_types = tuple(
            map_type
            for map_type in map_types
            if not query
            or category_matches
            or query in naming.map_label(map_type).casefold()
            or query in str(map_type).replace("_", " ").casefold()
        )
        if not visible_map_types:
            continue
        box = layout.box()
        box.label(text=title, icon=icon)
        col = box.column(align=True)
        for map_type in visible_map_types:
            row = col.row(align=True)
            row.enabled = map_type not in unsupported_maps
            row.label(text=naming.map_label(map_type))
            op = row.operator("master_baker.add_map", text="", icon="ADD")
            op.map_type = map_type
            match_count += 1
    if query and match_count == 0:
        layout.label(text="No matching maps", icon="INFO")



class MASTER_BAKER_MT_resolution_presets(bpy.types.Menu):
    bl_label = "Resolution Presets"
    bl_idname = "MASTER_BAKER_MT_resolution_presets"
    bl_description = "Set the output width and height to a standard texture size"

    def draw(self, _context):
        layout = self.layout
        for preset_id, label in (
            (constants.OUTPUT_SIZE_512, "512"),
            (constants.OUTPUT_SIZE_1024, "1K"),
            (constants.OUTPUT_SIZE_2048, "2K"),
            (constants.OUTPUT_SIZE_4096, "4K"),
            (constants.OUTPUT_SIZE_8192, "8K"),
        ):
            operator = layout.operator("master_baker.set_output_size_preset", text=label)
            operator.preset = preset_id


class MASTER_BAKER_MT_project_presets(bpy.types.Menu):
    bl_label = "Project Presets"
    bl_idname = "MASTER_BAKER_MT_project_presets"
    bl_description = "Save the active bake project as a preset, or load one"

    def draw(self, _context):
        layout = self.layout
        layout.operator("master_baker.save_project_preset", text="Save Preset", icon="FILE_TICK")
        layout.operator("master_baker.load_project_preset", text="Load Preset", icon="FILE_FOLDER")


class MASTER_BAKER_MT_project_prepare(bpy.types.Menu):
    bl_label = "Prepare"
    bl_idname = "MASTER_BAKER_MT_project_prepare"
    bl_description = "Rename meshes, optimize UV seams, and capture or restore UV snapshots"

    def draw(self, context):
        layout = self.layout
        layout.operator("master_baker.prepare_lowhigh_names", text="Auto-Rename Meshes to _low/_high", icon="MOD_MESHDEFORM")
        layout.operator("master_baker.name_from_collections", text="Auto-Name from Collections", icon="OUTLINER_COLLECTION")
        layout.operator("master_baker.optimize_uv_seams", text="Optimize UV Seams (Experimental)", icon="UV")
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        project = properties.get_active_project(getattr(context, "scene", None)) if settings is not None else None
        if project is not None:
            layout.separator()
            # Locked mid-bake like the output settings: the switch relinks the objects
            # the running bake is reading.
            collections_row = layout.row()
            collections_row.enabled = not _bake_state(project)[2]
            collections_row.prop_menu_enum(project, "collection_mode", text="Collections", icon="OUTLINER_COLLECTION")
        layout.separator()
        snapshot = None
        obj = getattr(context, "active_object", None)
        if settings is not None and obj is not None:
            snapshot = uv_snapshot.find_snapshot(settings, obj)
        layout.operator(
            "master_baker.capture_uv_snapshot",
            text="Update UV Snapshot" if snapshot is not None else "Capture UV Snapshot",
            icon="IMPORT",
        )
        restore_row = layout.row()
        restore_row.enabled = snapshot is not None
        restore_row.operator("master_baker.restore_uv_snapshot", text="Restore UVs", icon="RECOVER_LAST")
        if snapshot is not None:
            layout.menu("MASTER_BAKER_MT_uv_snapshot_actions", text="UV Snapshot", icon="DOWNARROW_HLT")
        orphan_count = sum(
            1 for item in getattr(settings, "uv_snapshots", [])
            if getattr(item, "source_object_ref", None) is None
        ) if settings is not None else 0
        if orphan_count:
            layout.operator(
                "master_baker.cleanup_orphan_uv_snapshots",
                text=f"Clean Orphaned UV Snapshots ({orphan_count})",
                icon="TRASH",
            )


class MASTER_BAKER_MT_uv_snapshot_actions(bpy.types.Menu):
    bl_label = "UV Snapshot"
    bl_idname = "MASTER_BAKER_MT_uv_snapshot_actions"
    bl_description = "Restore, rename, or delete the UV snapshot on the active object"

    def draw(self, context):
        layout = self.layout
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        obj = getattr(context, "active_object", None)
        snapshot = uv_snapshot.find_snapshot(settings, obj) if settings is not None and obj is not None else None
        if snapshot is None:
            layout.label(text="No snapshot for active object", icon="INFO")
            return
        details = layout.column(align=True)
        details.enabled = False
        details.label(text=str(getattr(snapshot, "snapshot_name", "UV Snapshot") or "UV Snapshot"))
        details.label(text=f"UV: {getattr(snapshot, 'uv_layer_name', '')}")
        details.label(text=f"{int(getattr(snapshot, 'face_count', 0))} faces · {getattr(snapshot, 'captured_at', '')}")
        layout.separator()
        layout.operator("master_baker.restore_uv_snapshot", text="Restore to New UV Map", icon="ADD")
        if uv_snapshot.topology_matches(snapshot, obj):
            replace = layout.operator("master_baker.restore_uv_snapshot", text="Replace Current UV Map", icon="FILE_REFRESH")
            replace.replace_current = True
        layout.operator("master_baker.rename_uv_snapshot", text="Rename Snapshot", icon="GREASEPENCIL")
        layout.separator()
        layout.operator("master_baker.delete_uv_snapshot", text="Delete Snapshot", icon="TRASH")


class MASTER_BAKER_MT_map_stack_presets(bpy.types.Menu):
    bl_label = "Map Stack Presets"
    bl_idname = "MASTER_BAKER_MT_map_stack_presets"
    bl_description = "Replace the map stack with a preset set of output maps"

    def draw(self, _context):
        layout = self.layout
        for preset_id, label, _description in constants.MAP_STACK_ITEMS:
            operator = layout.operator("master_baker.apply_map_stack_preset", text=label)
            operator.preset = preset_id


def _collect_texture_set_names(project, exclude_group=None):
    """Return a dict mapping texture_set_name → list of group names."""
    sets: dict[str, list[str]] = {}
    for group in getattr(project, "groups", []):
        name = (getattr(group, "texture_set_name", "") or "").strip()
        if not name:
            continue
        if exclude_group is not None and group == exclude_group:
            continue
        sets.setdefault(name, []).append(str(getattr(group, "name", "") or ""))
    return sets


def _groups_outside_texture_set(project, set_key):
    """Return bake groups not currently assigned to `set_key` (standalone or in
    another set) — the "Bake Groups Not in Set" quick-assign pool."""
    key = str(set_key or "").strip()
    return [
        group
        for group in getattr(project, "groups", [])
        if (getattr(group, "texture_set_name", "") or "").strip() != key
    ]


def _ui_targeted_groups(project, context=None):
    """Bake groups named by the header's shift-click selection.

    An empty selection is the active bake group alone. Stand-in projects used by
    layout tests have no active index; those return an empty list so the caller
    can fall back to the group it was given.
    """
    if project is None or not hasattr(project, "active_group_index"):
        return []
    if context is None:
        context = bpy.context
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    names = set(properties.bake_group_target_names(project, settings))
    return [
        group
        for group in getattr(project, "groups", []) or []
        if str(getattr(group, "name", "") or "").strip() in names
    ]


def _move_all_groups_destination(project) -> str:
    """Texture set that 'move all groups' writes into, or '' when there is nothing to move.

    With an active set, groups outside it join that set. With no sets at all, standalone
    groups join a set named after the project. Groups that already share one output stay put.
    """
    groups = list(getattr(project, "groups", []) or [])
    if len(groups) < 2:
        return ""
    active = properties.get_active_texture_set(project)
    active_name = str(getattr(active, "name", "") or "").strip() if active is not None else ""
    if active_name:
        if any((getattr(group, "texture_set_name", "") or "").strip() != active_name for group in groups):
            return active_name
        return ""
    names = {(getattr(group, "texture_set_name", "") or "").strip() for group in groups}
    if len(names) == 1 and "" not in names:
        return ""
    if names == {""} or len(names) > 1:
        return str(getattr(project, "name", "") or "").strip() or "TextureSet"
    return ""


def _texture_set_share_text(project, groups) -> str:
    """One line naming the other bake groups that share this selection's texture set."""
    if not groups:
        return ""
    set_names = {(getattr(group, "texture_set_name", "") or "").strip() for group in groups}
    if len(set_names) != 1:
        return ""
    set_name = next(iter(set_names))
    if not set_name:
        return ""
    selected = {str(getattr(group, "name", "") or "") for group in groups}
    others = []
    for group in getattr(project, "groups", []) or []:
        if (getattr(group, "texture_set_name", "") or "").strip() != set_name:
            continue
        name = str(getattr(group, "name", "") or "")
        if name and name not in selected and name not in others:
            others.append(name)
    if not others:
        return ""
    shown = others[:3]
    extra = len(others) - len(shown)
    listed = ", ".join(shown)
    if extra:
        listed = f"{listed}, and {extra} more"
    return f"Shares {set_name} with {listed}"


def _group_low_active_uv_names(group) -> list[str]:
    """Active UV layer name on each low mesh. An empty string means that mesh has none."""
    role_state = properties.group_role_assignments_state(group)
    names = []
    for slot in getattr(role_state, "low_meshes", []) or []:
        obj = getattr(slot, "object_ref", None)
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        data = getattr(obj, "data", None)
        uv_layers = getattr(data, "uv_layers", None) if data is not None else None
        active = getattr(uv_layers, "active", None) if uv_layers is not None else None
        names.append(str(getattr(active, "name", "") or ""))
    return names


# Target group for the contextual texture set picker menu.
# Set by MASTER_BAKER_OT_show_texture_set_picker before calling the menu.
_texture_set_menu_target_group: str = ""
# The group popover's menu writes every shift-clicked bake group. A group row
# in the set list writes only the group named here.
_texture_set_menu_apply_to_targets: bool = False
# Set whose row menu is open. Dissolve reads this rather than the active index.
_texture_set_row_target: str = ""



def _texture_set_icon_kwargs(ts_name):
    """Icon kwargs for the texture-set picker button.

    Assigned -> custom TextureSetLinked glyph (falls back to the built-in
    LINKED chain if the preview isn't loaded); standalone -> built-in
    UNLINKED broken chain (placeholder until a custom standalone glyph exists).
    """
    if ts_name:
        return _icon_kwargs("texture_set_linked", "LINKED")
    return {"icon": "UNLINKED"}


def _draw_texture_set_menu_button(layout, group):
    """Draw a compact dropdown + clear button for a group's texture set."""
    ts_name = (getattr(group, "texture_set_name", "") or "").strip()
    group_name = str(getattr(group, "name", "") or "")
    dropdown = layout.row(align=True)
    picker = dropdown.operator(
        "master_baker.show_texture_set_picker",
        text=ts_name or "None",
        **_texture_set_icon_kwargs(ts_name),
    )
    picker.group_name = group_name
    if ts_name:
        clear = layout.operator("master_baker.clear_texture_set", text="", icon="X")
        clear.group_name = group_name


class MASTER_BAKER_MT_texture_set_picker(bpy.types.Menu):
    bl_label = "Texture Set"
    bl_idname = "MASTER_BAKER_MT_texture_set_picker"
    bl_description = "Assign this bake group to a texture set, or bake it on its own"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(context.scene)
        if project is None:
            layout.label(text="No project")
            return
        # Resolve target group by NAME (never a live pointer). A pointer into the
        # project.groups CollectionProperty is invalidated when the collection is
        # resized, so carrying one across the popup boundary via context_pointer_set
        # is a use-after-free crash waiting to happen; the picker operator stashes a
        # plain string name instead. Fall back to the active group.
        group = None
        target_name = _texture_set_menu_target_group
        if target_name:
            group = next(
                (g for g in project.groups if str(getattr(g, "name", "") or "") == target_name),
                None,
            )
        if group is None:
            group = properties.peek_active_group(project)
        if group is None:
            layout.label(text="No bake group")
            return
        g_name = str(getattr(group, "name", "") or "")
        existing = _collect_texture_set_names(project, exclude_group=group)
        current = (getattr(group, "texture_set_name", "") or "").strip()

        # Existing texture sets
        if existing:
            for ts_name, members in sorted(existing.items()):
                icon = "CHECKMARK" if ts_name == current else "NONE"
                op = layout.operator(
                    "master_baker.assign_texture_set",
                    text=f"{ts_name}  ({', '.join(members)})",
                    icon=icon,
                )
                op.name = ts_name
                op.group_name = g_name
            layout.separator()

        # New texture set
        op = layout.operator("master_baker.new_texture_set", text="New Texture Set...", icon="ADD")
        op.group_name = g_name

        # Rename current texture set
        if current:
            layout.separator()
            op = layout.operator("master_baker.rename_texture_set", text=f"Rename '{current}'...", icon="TEXT")
            op.old_name = current

        # Clear
        if current:
            layout.separator()
            op = layout.operator("master_baker.clear_texture_set", text="None (Standalone)", icon="X")
            op.group_name = g_name


class MASTER_BAKER_MT_assign_texture_set(bpy.types.Menu):
    """Assign one group, or every group in the header selection, to a texture set."""

    bl_label = "Texture Set"
    bl_idname = "MASTER_BAKER_MT_assign_texture_set"
    bl_description = "Choose the texture set these bake groups write into"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(getattr(context, "scene", None))
        if project is None:
            layout.label(text="No project")
            return
        apply = bool(_texture_set_menu_apply_to_targets)
        target_name = _texture_set_menu_target_group
        if apply:
            groups = _ui_targeted_groups(project, context)
        else:
            groups = [
                group
                for group in getattr(project, "groups", []) or []
                if str(getattr(group, "name", "") or "") == target_name
            ]
            if not groups:
                active = properties.peek_active_group(project)
                groups = [active] if active is not None else []
        if not groups:
            layout.label(text="No bake group")
            return

        exclude = {str(getattr(group, "name", "") or "") for group in groups}
        current_names = {
            (getattr(group, "texture_set_name", "") or "").strip() for group in groups
        }
        shared = next(iter(current_names)) if len(current_names) == 1 else None
        existing = _collect_texture_set_names(project)
        for texture_set in getattr(project, "texture_sets", []) or []:
            name = str(getattr(texture_set, "name", "") or "").strip()
            if name and name not in existing:
                existing[name] = []

        for set_name in sorted(existing):
            members = [name for name in existing[set_name] if name not in exclude]
            label = f"{set_name}  ({', '.join(members)})" if members else set_name
            op = layout.operator(
                "master_baker.assign_texture_set",
                text=label,
                icon="CHECKMARK" if shared == set_name else "NONE",
            )
            op.name = set_name
            op.group_name = "" if apply else target_name
            op.apply_to_targets = apply

        layout.separator()
        standalone = layout.operator(
            "master_baker.clear_texture_set",
            text="Standalone",
            icon="CHECKMARK" if shared == "" else "NONE",
        )
        standalone.group_name = "" if apply else target_name
        standalone.apply_to_targets = apply

        layout.separator()
        layout.operator_context = "INVOKE_DEFAULT"
        new_set = layout.operator("master_baker.new_texture_set", text="New Texture Set", icon="ADD")
        new_set.assign_active_group = not apply
        new_set.apply_to_targets = apply
        new_set.group_name = "" if apply else target_name


class MASTER_BAKER_MT_texture_set_row(bpy.types.Menu):
    bl_label = "Texture Set"
    bl_idname = "MASTER_BAKER_MT_texture_set_row"
    bl_description = "Dissolve this texture set"

    def draw(self, _context):
        dissolve = self.layout.operator("master_baker.dissolve_texture_set", text="Dissolve", icon="TRASH")
        dissolve.set_name = _texture_set_row_target


class MASTER_BAKER_MT_bake_project(bpy.types.Menu):
    bl_label = "Bake Project"
    bl_idname = "MASTER_BAKER_MT_bake_project"
    bl_description = "Switch the active bake project"

    def draw(self, context):
        layout = self.layout
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        projects = list(getattr(settings, "projects", []) or [])
        if not projects:
            layout.label(text="No bake projects")
            return
        active = int(getattr(settings, "active_project_index", 0) or 0)
        for index, project in enumerate(projects):
            name = str(getattr(project, "ui_name", "") or getattr(project, "name", "") or "").strip()
            name = name or f"Project {index + 1}"
            kwargs = {"text": name}
            if index == active:
                kwargs["icon"] = "CHECKMARK"
            operator = layout.operator("master_baker.set_active_project_by_index", **kwargs)
            operator.project_index = index


class MASTER_BAKER_MT_hierarchy_texture_set(bpy.types.Menu):
    bl_label = "Texture Set"
    bl_idname = "MASTER_BAKER_MT_hierarchy_texture_set"
    bl_description = "Choose the active texture set"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(getattr(context, "scene", None))
        if project is None:
            layout.label(text="No project")
            return
        names = _compact_texture_set_names(project)
        current = _compact_texture_set_label(project) if names else ""
        if not names:
            layout.label(text="No texture sets")
        else:
            for name in names:
                operator = layout.operator(
                    "master_baker.set_active_texture_set",
                    text=name,
                    icon="CHECKMARK" if name == current else "NONE",
                )
                operator.set_name = name
        layout.separator()
        layout.operator_context = "INVOKE_DEFAULT"
        add_set = layout.operator("master_baker.new_texture_set", text="New Texture Set", icon="ADD")
        add_set.assign_active_group = False
        add_set.group_name = ""


class MASTER_BAKER_MT_hierarchy_bake_group(bpy.types.Menu):
    bl_label = "Bake Group"
    bl_idname = "MASTER_BAKER_MT_hierarchy_bake_group"
    bl_description = "Choose which bake groups receive setting changes. Shift-click to include more than one"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(getattr(context, "scene", None))
        groups = list(getattr(project, "groups", [])) if project is not None else []
        if not groups:
            layout.label(text="No bake groups")
            layout.separator()
            layout.operator("master_baker.add_group", text="New Bake Group", icon="ADD")
            return
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        targeted = set(properties.bake_group_target_names(project, settings))
        # Don't match groups by id(). Each read of a collection hands back a new
        # Python wrapper, so ids from two passes never compare equal and the
        # menu drew "No bake groups" while the button still showed a name.
        visible_names = {
            str(getattr(group, "name", "") or "").strip()
            for group in (_groups_in_active_texture_set(project) or groups)
        }
        layout.operator_context = "INVOKE_DEFAULT"
        drew_any = False
        for index, group in enumerate(groups):
            name = str(getattr(group, "name", "") or "").strip() or f"Group {index + 1}"
            if visible_names and name not in visible_names:
                continue
            kwargs = {"text": name}
            if name in targeted:
                kwargs["icon"] = "CHECKMARK"
            operator = layout.operator("master_baker.set_active_group_by_index", **kwargs)
            operator.group_index = index
            drew_any = True
        if not drew_any:
            layout.label(text="No bake groups")
        layout.separator()
        layout.operator("master_baker.rename_group_meshes", icon="SORTALPHA")
        layout.operator("master_baker.add_group", text="New Bake Group", icon="ADD")


class MASTER_BAKER_PT_configure_maps(bpy.types.Panel):
    bl_label = "Configure Maps"
    bl_idname = "MASTER_BAKER_PT_configure_maps"
    bl_description = "Add an output map to the stack"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    # Popover-only (the "+" button in the Map Stack header); INSTANCED keeps the map
    # catalog out of the Render-tab panel stack so it isn't a stray floating panel.
    bl_options = {"INSTANCED"}

    def draw(self, context):

        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        settings = getattr(context.scene, "fyr_baker_settings", None)
        ui_state = properties.scene_ui_state(settings) if settings is not None else None
        if ui_state is not None:
            layout.prop(ui_state, "map_catalog_search", text="", icon="VIEWZOOM")
        project = properties.get_active_project(context.scene)
        # The stack presets name geometry map types. A material project's rows are
        # material CHANNELS, so a preset applied there disabled the MATERIAL row and
        # switched on geometry maps the workflow cannot bake -- the catalog below
        # already swaps for that workflow, and this menu never did.
        if getattr(project, "workflow", "") != constants.WORKFLOW_MATERIAL:
            layout.menu("MASTER_BAKER_MT_map_stack_presets", text="Presets", icon="PRESET")
        _draw_map_catalog(
            layout,
            project=project,
            search_text=getattr(ui_state, "map_catalog_search", "") if ui_state is not None else "",
        )


class MASTER_BAKER_MT_preview_map_dropdown(bpy.types.Menu):
    bl_label = "Show on Low"
    bl_idname = "MASTER_BAKER_MT_preview_map_dropdown"
    bl_description = "Show a baked map on the low-poly meshes"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(context.scene)
        if project is None:
            layout.label(text="No active project")
            return

        settings = getattr(context.scene, "fyr_baker_settings", None)
        session_state = _preview_session_state(settings)

        preview_active = bool(
            session_state is not None
            and getattr(session_state, "preview_on_low_active", False)
            and str(getattr(session_state, "preview_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
        )
        active_map_uuid = ""
        active_map_type = ""
        active_map_index = -1
        if preview_active:
            active_map_uuid = str(getattr(session_state, "preview_on_low_map_uuid", "") or "").strip()
            active_map_type = str(getattr(session_state, "preview_on_low_map_type", "") or "").upper()
            active_map_index = int(getattr(session_state, "preview_on_low_map_index", -1))

        active_group_name = _active_group_name_for_maps(project)
        maps = list(getattr(project, "maps", []))
        for index, item in enumerate(maps):
            map_type = str(getattr(item, "map_type", "") or "").upper()
            map_uuid = properties.ensure_map_setting_uuid(item)
            source_context = _map_source_context(project, item, group_name=active_group_name)
            has_source = bool(source_context["has_source"])
            if not _map_item_visualization_available(item, has_source=has_source):
                continue
            is_active = preview_active and (
                (bool(active_map_uuid) and active_map_uuid == map_uuid)
                or (not active_map_uuid and active_map_type == map_type and (active_map_index < 0 or active_map_index == index))
            )
            effective_suffix = properties.effective_map_output_suffix(project, item) or ""

            row = layout.row(align=True)
            row.enabled = has_source
            preview_map = row.operator("master_baker.preview_map_output", text=naming.map_label(map_type), icon_value=sidebar_icons.get_icon_value("show_on_low") if is_active else 0, depress=is_active)
            preview_map.map_type = getattr(item, "map_type", "")
            preview_map.map_uuid = map_uuid
            preview_map.group_name = active_group_name
            preview_map.output_suffix = effective_suffix
            preview_map.map_stack_index = index
            if session_state is not None:
                preview_map.scope = getattr(session_state, "preview_on_low_scope", "")


class MASTER_BAKER_MT_baked_maps_dropdown(bpy.types.Menu):
    bl_label = "Baked Maps"
    bl_idname = "MASTER_BAKER_MT_baked_maps_dropdown"
    bl_description = "Show a baked map on the low-poly meshes"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(context.scene)
        if project is None:
            layout.label(text="No active project", icon="INFO")
            return

        settings = getattr(context.scene, "fyr_baker_settings", None)
        session_state = _preview_session_state(settings)
        if session_state is None:
            layout.label(text="No preview session", icon="INFO")
            return

        scope = str(
            getattr(session_state, "preview_on_low_scope", constants.PREVIEW_ON_LOW_SCOPE_ALL_GROUPS)
            or constants.PREVIEW_ON_LOW_SCOPE_ALL_GROUPS
        )
        group = properties.peek_active_group(project)
        group_names = _preview_scope_group_names(project, group, scope)
        active_group_scope = scope == constants.PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP
        operator_group_name = str(getattr(group, "name", "") or "") if active_group_scope else ""

        preview_active = bool(
            getattr(session_state, "preview_on_low_active", False)
            and str(getattr(session_state, "preview_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
        )
        active_map_uuid = str(getattr(session_state, "preview_on_low_map_uuid", "") or "")
        active_preview_group = str(getattr(session_state, "preview_on_low_group_name", "") or "")

        baked_map_count = 0
        for index, map_item in enumerate(getattr(project, "maps", [])):
            if getattr(map_item, "is_add_phantom", False):
                continue
            shortcut_group_name = _first_map_preview_source_group(project, map_item, group_names)
            if not shortcut_group_name:
                continue
            baked_map_count += 1
            map_uuid = properties.ensure_map_setting_uuid(map_item)
            is_active = (
                preview_active
                and active_preview_group == operator_group_name
                and bool(active_map_uuid)
                and active_map_uuid == map_uuid
            )
            row = layout.row(align=True)
            label_row = row.row(align=True)
            label_row.label(text=_map_stack_item_label(project, map_item))

            open_op = row.operator("master_baker.open_map_output_image", text="", icon="IMAGE_DATA")
            open_op.map_type = str(getattr(map_item, "map_type", "") or "")
            open_op.map_uuid = map_uuid
            open_op.group_name = shortcut_group_name
            open_op.output_suffix = properties.effective_map_output_suffix(project, map_item) or ""

            edit_op = row.operator("master_baker.external_edit_map_output", text="", icon="GREASEPENCIL")
            edit_op.map_type = str(getattr(map_item, "map_type", "") or "")
            edit_op.map_uuid = map_uuid
            edit_op.group_name = shortcut_group_name
            edit_op.output_suffix = properties.effective_map_output_suffix(project, map_item) or ""

            op = row.operator(
                "master_baker.preview_map_output",
                text="",
                icon_value=sidebar_icons.get_icon_value("show_on_low"),
                depress=is_active,
            )
            op.map_type = str(getattr(map_item, "map_type", "") or "")
            op.map_uuid = map_uuid
            op.group_name = operator_group_name
            op.output_suffix = properties.effective_map_output_suffix(project, map_item) or ""
            op.map_stack_index = index
            op.scope = scope

        if baked_map_count == 0:
            layout.label(text="No baked outputs are available for this scope.", icon="INFO")


class MASTER_BAKER_UL_projects(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        layout.label(text=item.name, icon="SCENE_DATA")


class MASTER_BAKER_UL_texture_sets(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = list(range(len(items)))
        return flt_flags, flt_neworder

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        ts_name = str(getattr(item, "name", "") or "")
        project = data
        member_groups = [g for g in project.groups if (getattr(g, "texture_set_name", "") or "").strip() == ts_name]

        row = layout.row(align=True)
        row.prop(item, "ui_name", text="", emboss=True)
        count_label = row.row(align=True)
        count_label.alignment = "RIGHT"
        count_label.label(text=f"({len(member_groups)})")


class MASTER_BAKER_UL_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        role_state = properties.group_role_assignments_state(item)
        low_count = len(getattr(role_state, "low_meshes", []))
        high_count = len(properties.effective_high_mesh_slots(item))
        group_name = str(getattr(item, "name", "") or "")
        is_dirty = dirty_tracker.is_session_active() and bool(
            dirty_tracker.get_pending_dirty().get(group_name)
        )
        row = layout.row(align=True)

        split = row.split(factor=0.4, align=True)
        name_row = split.row(align=True)
        name_row.label(text="", icon_value=sidebar_icons.get_icon_value("low_poly"))
        name_row.prop(item, "ui_name", text="")
        meta_row = split.row(align=True)
        _draw_texture_set_menu_button(meta_row, item)
        counts = meta_row.row(align=True)
        counts.alignment = "RIGHT"
        counts.label(text=f"L:{low_count} H:{high_count}")
        status_text, status_icon = _group_setup_status(item)
        status_row = counts.row(align=True)
        status_row.alert = status_icon == "ERROR"
        status_row.label(text=status_text, icon=status_icon)
        if is_dirty:
            counts.label(text="", icon="SNAP_MIDPOINT")
        # Live Normal is parked until bake speed can sustain the live workflow.
        # settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        # session_state = _preview_session_state(settings)
        # project_name = str(getattr(data, "name", "") or "")
        # live_normal_active = bool(
        #     session_state is not None
        #     and getattr(session_state, "live_normal_preview_active", False)
        #     and str(getattr(session_state, "live_normal_preview_project_name", "") or "") == project_name
        #     and str(getattr(session_state, "live_normal_preview_group_name", "") or "") == group_name
        # )
        # ln_row = counts.row(align=True)
        # ln_row.alert = live_normal_active
        # ln_op = ln_row.operator("master_baker.toggle_live_normal_preview", text="", icon="SHADING_TEXTURE", depress=live_normal_active)
        # ln_op.group_name = group_name


class MASTER_BAKER_UL_texture_set_members(bpy.types.UIList):
    """Native list of the bake groups belonging to the active texture set.

    Bound to the set's own inert `member_list_active_index`, so highlighting a row
    only marks it within this list — it deliberately does NOT change the project's
    active bake group. Membership is a filter over `project.groups` keyed on
    `texture_set_name`; the row is read-only (name is edited from the group panel).
    """

    def filter_items(self, context, data, propname):
        groups = getattr(data, propname)
        active_set = properties.get_active_texture_set(data)
        set_key = str(getattr(active_set, "name", "") or "").strip()
        flt_flags = [
            self.bitflag_filter_item
            if (getattr(group, "texture_set_name", "") or "").strip() == set_key
            else 0
            for group in groups
        ]
        return flt_flags, list(range(len(groups)))

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        group_name = str(getattr(item, "name", "") or "")
        row = layout.row(align=True)
        row.label(text=group_name, icon_value=sidebar_icons.get_icon_value("bake_group"))
        actions = row.row(align=True)
        actions.alignment = "RIGHT"
        # Explicit "open this group's settings" — the deliberate navigation that used
        # to fire on any row click (which users didn't want).
        goto = actions.operator("master_baker.set_active_group", text="", icon="FORWARD")
        goto.group_name = group_name
        remove = actions.operator("master_baker.clear_texture_set", text="", icon="X")
        remove.group_name = group_name


class MASTER_BAKER_UL_texture_set_nonmembers(bpy.types.UIList):
    """Native list of the bake groups NOT in the active texture set — the quick-assign
    pool. Each row can open that group's settings or move the group into this set.
    Standalone groups and groups currently in another set both appear (the latter are
    annotated so the move is explicit). Bound to the set's inert index; highlighting a
    row never changes the project's active bake group.
    """

    def filter_items(self, context, data, propname):
        groups = getattr(data, propname)
        active_set = properties.get_active_texture_set(data)
        set_key = str(getattr(active_set, "name", "") or "").strip()
        flt_flags = [
            0
            if (getattr(group, "texture_set_name", "") or "").strip() == set_key
            else self.bitflag_filter_item
            for group in groups
        ]
        return flt_flags, list(range(len(groups)))

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        project = data
        active_set = properties.get_active_texture_set(project)
        set_key = str(getattr(active_set, "name", "") or "").strip()
        group_name = str(getattr(item, "name", "") or "")
        current = (getattr(item, "texture_set_name", "") or "").strip()

        row = layout.row(align=True)
        row.label(text=group_name, icon_value=sidebar_icons.get_icon_value("bake_group"))
        if current:
            in_other = row.row(align=True)
            in_other.active = False
            in_other.label(text=f"in {current}")
        actions = row.row(align=True)
        actions.alignment = "RIGHT"
        goto = actions.operator("master_baker.set_active_group", text="", icon="FORWARD")
        goto.group_name = group_name
        # Up-arrow: move this group UP into the set (the list right above). Reads as the
        # inverse of the members list's X, so the two lists form a move-in/move-out pair.
        add = actions.operator("master_baker.assign_texture_set", text="", icon="TRIA_UP")
        add.name = set_key
        add.group_name = group_name


# Detected UV-tile occupancy, keyed by casefolded texture-set name. Detection walks evaluated
# meshes (addon/udim.py), which is far too expensive for a draw callback, so the tile table
# shows the last explicit Detect result and says nothing about occupancy until one exists.
# TODO(properties): the durable home for this is a cached field on MasterBakerTextureSet —
# it lives here because this change does not own properties.py.
_UDIM_DETECTED: dict[str, tuple[tuple[int, ...], int, tuple[str, ...]]] = {}

# Per-tile state for the row callback below, published immediately before template_list() so
# each row costs a dict lookup instead of a fresh validation pass.
_UDIM_ROW_STATES: dict[int, object] = {}
_UDIM_ROW_OCCUPANCY_SAMPLED = False
# Texture sets whose tile editor the user opened. A set with overrides, explicit
# mode, or a tile problem opens on its own.
_UDIM_EDITOR_OPEN: set[str] = set()


def _udim_detected_key(texture_set, set_key: str | None = None) -> str:
    """Cache key scoped to the owning datablock (scene) as well as the set name.

    Keyed by name alone, two projects each holding a set called Body showed each
    other's sampled occupancy; the scene pointer keeps sets of different files and
    scenes apart. A rename still reads as "not sampled", which is the safe miss.
    """
    name = str(set_key if set_key is not None else getattr(texture_set, "name", "") or "").strip().casefold()
    owner = getattr(texture_set, "id_data", None)
    pointer = getattr(owner, "as_pointer", None)
    try:
        owner_key = str(int(pointer())) if callable(pointer) else ""
    except Exception:
        owner_key = ""
    return f"{owner_key}:{name}"


def _udim_detected_entry(texture_set) -> tuple[tuple[int, ...], int, tuple[str, ...]]:
    return _UDIM_DETECTED.get(_udim_detected_key(texture_set), ((), 0, ()))


class MASTER_BAKER_UL_udim_tiles(bpy.types.UIList):
    """Compact UDIM tile table: number, configured override, occupancy + effective size,
    validation state. Reads `_UDIM_ROW_STATES`, published by the drawing panel."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        try:
            number = int(getattr(item, "number", 0) or 0)
        except (TypeError, ValueError):
            number = 0
        state = _UDIM_ROW_STATES.get(number)

        row = layout.row(align=True)
        tile_field = row.row(align=True)
        tile_field.ui_units_x = 3.2
        tile_field.prop(item, "number", text="")

        override_field = row.row(align=True)
        override_field.ui_units_x = 4.0
        override_field.prop(item, "override", text="")

        meta = row.row(align=True)
        meta.active = False
        if state is not None:
            parts = []
            if _UDIM_ROW_OCCUPANCY_SAMPLED:
                parts.append("occupied" if getattr(state, "detected", False) else "empty")
            parts.append(str(getattr(state, "resolution_label", "")))
            meta.label(text=" · ".join(part for part in parts if part))

        status = row.row(align=True)
        status.alignment = "RIGHT"
        status_icon = _udim_status_icon(state)
        if status_icon is None:
            status.label(text="", icon="BLANK1")
        else:
            # label() cannot carry a tooltip, so the validation message on this
            # tile never appeared on hover.
            status.alert = bool(getattr(state, "is_error", False))
            status_tip = status.operator(
                "master_baker.udim_tile_status",
                text="",
                icon=status_icon,
                emboss=False,
            )
            status_tip.tile_number = number


# The three operators below belong in operators.py alongside the other texture-set verbs
# (new_texture_set / assign_texture_set / dissolve_texture_set); they are defined here because
# this change does not own that file. Move them when convenient — the idnames are final.
class MASTER_BAKER_OT_add_udim_tile(bpy.types.Operator):
    bl_idname = "master_baker.add_udim_tile"
    bl_label = "Add UV Tile"
    bl_description = (
        "Add a UDIM tile row to the active texture set. Configuring any tile switches this "
        "set's outputs to numbered .NNNN tile filenames"
    )
    # No UNDO: every structural op on these collections in operators.py drops it to avoid
    # the memfile-undo realloc crash (T74067). These two were written outside that file
    # and missed the rule -- add a tile, hover the row, Ctrl+Z, access violation.
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        project = properties.get_active_project(context.scene)
        texture_set = properties.get_active_texture_set(project) if project is not None else None
        if texture_set is None:
            self.report({"WARNING"}, "No active texture set")
            return {"CANCELLED"}
        used = set()
        for existing in texture_set.udim_tiles:
            try:
                used.add(int(getattr(existing, "number", 0) or 0))
            except (TypeError, ValueError):
                continue
        number = constants.UDIM_TILE_MIN
        while number in used and number < constants.UDIM_TILE_MAX:
            number += 1
        if number in used:
            self.report({"WARNING"}, "Every supported UDIM tile is already listed")
            return {"CANCELLED"}
        row = texture_set.udim_tiles.add()
        row.number = number
        texture_set.udim_tile_active_index = len(texture_set.udim_tiles) - 1
        return {"FINISHED"}


class MASTER_BAKER_OT_remove_udim_tile(bpy.types.Operator):
    bl_idname = "master_baker.remove_udim_tile"
    bl_label = "Remove UV Tile"
    bl_description = "Remove the highlighted UDIM tile row from the active texture set"
    # No UNDO: see MASTER_BAKER_OT_add_udim_tile above (memfile-undo realloc crash).
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        project = properties.get_active_project(context.scene)
        texture_set = properties.get_active_texture_set(project) if project is not None else None
        if texture_set is None:
            self.report({"WARNING"}, "No active texture set")
            return {"CANCELLED"}
        tiles = texture_set.udim_tiles
        try:
            index = int(getattr(texture_set, "udim_tile_active_index", 0) or 0)
        except (TypeError, ValueError):
            index = 0
        if not 0 <= index < len(tiles):
            return {"CANCELLED"}
        tiles.remove(index)
        texture_set.udim_tile_active_index = max(0, min(index, len(tiles) - 1))
        return {"FINISHED"}


class MASTER_BAKER_OT_detect_udim_tiles(bpy.types.Operator):
    bl_idname = "master_baker.detect_udim_tiles"
    bl_label = "Detect UV Tiles"
    bl_description = (
        "Scan the low meshes in this texture set and report which UV tiles they occupy"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        from . import udim

        project = properties.get_active_project(context.scene)
        texture_set = properties.get_active_texture_set(project) if project is not None else None
        if texture_set is None:
            self.report({"WARNING"}, "No active texture set")
            return {"CANCELLED"}

        set_key = str(getattr(texture_set, "name", "") or "").strip()
        depsgraph = context.evaluated_depsgraph_get()
        tiles: set[int] = set()
        crossing = 0
        errors: list[str] = []
        for group in getattr(project, "groups", []):
            if (getattr(group, "texture_set_name", "") or "").strip() != set_key:
                continue
            role_state = properties.group_role_assignments_state(group)
            objects = [
                getattr(slot, "object_ref", None)
                for slot in getattr(role_state, "low_meshes", [])
            ]
            objects = [obj for obj in objects if obj is not None]
            if not objects:
                continue
            # Per group, because uv_layer_name is a per-group choice.
            group_tiles, group_crossing, group_errors = udim.detect_occupied_tiles(
                objects,
                str(getattr(group, "uv_layer_name", "") or "") or None,
                depsgraph=depsgraph,
            )
            tiles.update(group_tiles)
            crossing += group_crossing
            errors.extend(group_errors)

        _UDIM_DETECTED[_udim_detected_key(texture_set, set_key)] = (
            tuple(sorted(tiles)),
            crossing,
            tuple(errors),
        )
        if errors:
            self.report({"WARNING"}, errors[0])
        elif tiles:
            self.report({"INFO"}, f"{len(tiles)} UV tile{'' if len(tiles) == 1 else 's'} occupied")
        else:
            self.report({"WARNING"}, "No low-mesh UVs found in this texture set")
        return {"FINISHED"}


class MASTER_BAKER_OT_toggle_udim_editor(bpy.types.Operator):
    bl_idname = "master_baker.toggle_udim_editor"
    bl_label = "UV Tiles"
    bl_description = "Show or hide the tile list for this texture set"
    bl_options = {"INTERNAL"}

    set_name: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, _context):
        key = str(self.set_name or "").strip().casefold()
        if not key:
            return {"CANCELLED"}
        if key in _UDIM_EDITOR_OPEN:
            _UDIM_EDITOR_OPEN.discard(key)
        else:
            _UDIM_EDITOR_OPEN.add(key)
        return {"FINISHED"}


def _draw_texture_set_udim_settings(layout, project, texture_set):
    """One tile row. The tile list opens when this set has something to manage."""
    global _UDIM_ROW_STATES, _UDIM_ROW_OCCUPANCY_SAMPLED

    detected, crossing, errors = _udim_detected_entry(texture_set)
    _UDIM_ROW_OCCUPANCY_SAMPLED = _udim_detected_key(texture_set) in _UDIM_DETECTED
    try:
        project_width = int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION))
        project_height = int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION))
    except (TypeError, ValueError):
        project_width = project_height = constants.DEFAULT_RESOLUTION
    states = validation.udim_tile_states(
        texture_set,
        project_width=project_width,
        project_height=project_height,
        detected_tiles=detected,
    )
    _UDIM_ROW_STATES = {int(getattr(state, "udim_tile", 0)): state for state in states}

    from . import udim_images

    stale_paths = udim_images._active_project_stale_tiles(bpy.context)
    tiles = texture_set.udim_tiles
    mode = str(getattr(texture_set, "udim_mode", constants.UDIM_MODE_AUTOMATIC) or "")
    set_name = str(getattr(texture_set, "name", "") or "").strip()
    forced = bool(
        mode == constants.UDIM_MODE_EXPLICIT
        or len(tiles)
        or crossing
        or errors
        or stale_paths
    )
    opened = forced or set_name.casefold() in _UDIM_EDITOR_OPEN

    baked = [state for state in states if getattr(state, "baked", False)]
    summary_bits = [f"{len(baked)} baked"]
    if _UDIM_ROW_OCCUPANCY_SAMPLED:
        summary_bits.append(f"{len(detected)} occupied")
    if crossing:
        summary_bits.append(f"{crossing} crossing")

    row = layout.row(align=True)
    row.label(text="Tiles")
    row.prop(texture_set, "udim_mode", text="")
    summary = row.row(align=True)
    summary.active = False
    summary.label(text=" · ".join(summary_bits))
    row.operator("master_baker.detect_udim_tiles", text="", icon="FILE_REFRESH")
    if not forced:
        toggle = row.operator(
            "master_baker.toggle_udim_editor",
            text="",
            icon="TRIA_DOWN" if opened else "TRIA_RIGHT",
        )
        toggle.set_name = set_name
    if not opened:
        return

    detail = layout.column(align=True)
    if errors:
        error_row = detail.row(align=True)
        error_row.alert = True
        error_row.label(text=errors[0], icon="ERROR")

    # Files left behind by tiles that are no longer occupied. Fyr never deletes them on
    # its own, and this operator was drawn nowhere, so they accumulated silently.
    if stale_paths:
        stale_row = detail.row(align=True)
        stale_row.operator(
            "master_baker.cleanup_stale_udim_tiles",
            text=f"Clean Up {len(stale_paths)} Stale Tile File{'' if len(stale_paths) == 1 else 's'}",
            icon="TRASH",
        )

    if not len(tiles) and mode != constants.UDIM_MODE_EXPLICIT:
        detail.operator("master_baker.add_udim_tile", text="Add Tile Override", icon="ADD")
        return

    list_row = detail.row(align=True)
    list_row.template_list(
        "MASTER_BAKER_UL_udim_tiles",
        "udim_tiles",
        texture_set,
        "udim_tiles",
        texture_set,
        "udim_tile_active_index",
        rows=_ui_list_rows(tiles, empty_rows=1, max_rows=6),
    )
    side = list_row.column(align=True)
    side.operator("master_baker.add_udim_tile", text="", icon="ADD")
    side.operator("master_baker.remove_udim_tile", text="", icon="REMOVE")

    try:
        active_index = int(getattr(texture_set, "udim_tile_active_index", 0) or 0)
    except (TypeError, ValueError):
        active_index = 0
    if not 0 <= active_index < len(tiles):
        return
    active_tile = tiles[active_index]
    res_col = detail.column(align=True)
    res_col.prop(active_tile, "use_resolution_override", text="Custom Resolution")
    if getattr(active_tile, "use_resolution_override", False):
        res_row = res_col.row(align=True)
        res_row.prop(active_tile, "resolution_x", text="W")
        res_row.prop(active_tile, "resolution_y", text="H")

    # Conditional diagnostic, not standing copy: shown only while the highlighted tile has a
    # problem, because the row icon alone would not say what to fix.
    active_state = _UDIM_ROW_STATES.get(int(getattr(active_tile, "number", 0) or 0))
    message = str(getattr(active_state, "message", "") or "") if active_state is not None else ""
    if message:
        note = detail.row(align=True)
        note.alert = bool(getattr(active_state, "is_error", False))
        note.label(text=message, icon="ERROR" if note.alert else "INFO")


class MASTER_BAKER_MT_map_item_actions(bpy.types.Menu):
    bl_label = "Map Actions"
    bl_idname = "MASTER_BAKER_MT_map_item_actions"
    bl_description = "Open, edit, duplicate, or remove this output map"

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(context.scene)
        item = getattr(context, "master_baker_map_item", None)
        if project is None or item is None or bool(getattr(item, "is_add_phantom", False)):
            layout.label(text="No map selected", icon="INFO")
            return

        active_group_name = _active_group_name_for_maps(project)
        item_uuid = properties.ensure_map_setting_uuid(item)
        output_suffix = properties.effective_map_output_suffix(project, item) or ""
        source_context = _map_source_context(project, item, group_name=active_group_name)

        open_row = layout.row(align=True)
        open_row.enabled = bool(source_context["has_source"])
        open_op = open_row.operator("master_baker.open_map_output_image", text="Open Map Texture", icon="IMAGE_DATA")
        open_op.map_type = str(getattr(item, "map_type", "") or "")
        open_op.map_uuid = item_uuid
        open_op.group_name = active_group_name
        open_op.output_suffix = output_suffix

        edit_row = layout.row(align=True)
        edit_row.enabled = bool(source_context["source_file_path"])
        edit_op = edit_row.operator("master_baker.external_edit_map_output", text="Edit Map Externally", icon="GREASEPENCIL")
        edit_op.map_type = str(getattr(item, "map_type", "") or "")
        edit_op.map_uuid = item_uuid
        edit_op.group_name = active_group_name
        edit_op.output_suffix = output_suffix

        layout.separator()
        remove_index = -1
        for candidate_index, candidate in enumerate(getattr(project, "maps", [])):
            if properties.ensure_map_setting_uuid(candidate) == item_uuid:
                remove_index = candidate_index
                break
        duplicate_row = layout.row(align=True)
        duplicate_row.enabled = remove_index >= 0
        duplicate_op = duplicate_row.operator(
            "master_baker.duplicate_map",
            text="Duplicate Output Map",
            icon="DUPLICATE",
        )
        duplicate_op.map_index = int(remove_index)

        layout.separator()
        remove_row = layout.row(align=True)
        remove_row.enabled = remove_index >= 0
        remove_op = remove_row.operator("master_baker.remove_map", text="Remove Output Map", icon="X")
        remove_op.map_index = int(remove_index)


def bake_warning_headline(project) -> str:
    """Short, always-readable label for the last bake's warning row."""
    summary = str(getattr(project, "last_warning_summary", "") or "").strip()
    count = int(getattr(project, "last_warning_count", 0) or 0)
    subject = summary.split(":", 1)[0].strip() if ":" in summary[:80] else ""
    noun = "warning" if count <= 1 else f"{count} warnings"
    if subject:
        return f"{subject}: {noun} (click to read)"
    return f"Bake finished with {noun if count > 1 else 'a warning'} (click to read)"


def wrap_warning_text(text: str, width: int = 64) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    return lines


class MASTER_BAKER_OT_show_bake_warnings(bpy.types.Operator):
    bl_idname = "master_baker.show_bake_warnings"
    bl_label = "Bake Warnings"
    bl_description = "Read the full warning from the last bake"
    bl_options = {"INTERNAL"}

    def invoke(self, context, _event):
        return context.window_manager.invoke_popup(self, width=460)

    def draw(self, context):
        layout = self.layout
        project = properties.get_active_project(context.scene)
        summary = str(getattr(project, "last_warning_summary", "") or "") if project is not None else ""
        count = int(getattr(project, "last_warning_count", 0) or 0) if project is not None else 0
        col = layout.column(align=True)
        col.label(text="Bake Warning" if count <= 1 else f"Bake Warnings ({count})", icon="INFO")
        col.separator()
        for line in wrap_warning_text(summary or "No warning text was recorded."):
            col.label(text=line)
        if count > 1:
            col.separator()
            col.label(text=f"{count - 1} more in the bake log.")
            col.operator("master_baker.open_backend_log", text="Open Log", icon="TEXT")

    def execute(self, _context):
        return {"FINISHED"}


class MASTER_BAKER_OT_duplicate_map_warning(bpy.types.Operator):
    bl_idname = "master_baker.duplicate_map_warning"
    bl_label = "Duplicate Map Warning"
    bl_description = "Show which other map in the stack has these exact bake settings"
    bl_options = {"INTERNAL"}

    message: bpy.props.StringProperty(name="Message", default="")

    def invoke(self, context, _event):
        return context.window_manager.invoke_popup(self, width=360)

    def draw(self, _context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Exact duplicate bake settings", **duplicate_warning_icon_kwargs())
        col.separator()
        col.label(text=str(self.message or ""))

    def execute(self, _context):
        return {"FINISHED"}


class MASTER_BAKER_UL_maps(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        # Returning flt_neworder enables native drag-to-reorder grip handles;
        # Blender calls collection.move() automatically on drop.
        flt_neworder = list(range(len(items)))
        return flt_flags, flt_neworder

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        active_group_name = _active_group_name_for_maps(data)
        source_context = _map_source_context(data, item, group_name=active_group_name)
        has_source = bool(source_context["has_source"])
        thumbnail_icon_value = 0
        if source_context["output_target"] is not None:
            thumbnail_icon_value = output_thumbnails.get_output_icon_value(getattr(source_context["output_target"], "file_path", ""))
        effective_output_suffix = properties.effective_map_output_suffix(data, item) or ""
        item_uuid = properties.ensure_map_setting_uuid(item)
        scene_settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        preview_state = _preview_session_state(scene_settings)
        stored_map_uuid = str(getattr(preview_state, "preview_on_low_map_uuid", "") or "").strip()
        stored_map_index = int(getattr(preview_state, "preview_on_low_map_index", -1))
        stored_group = str(getattr(preview_state, "preview_on_low_group_name", "") or "")
        preview_active = bool(
            getattr(preview_state, "preview_on_low_active", False)
            and str(getattr(preview_state, "preview_on_low_project_name", "") or "") == str(getattr(data, "name", "") or "")
            and (not stored_group or stored_group == active_group_name)
            and (
                (bool(stored_map_uuid) and stored_map_uuid == item_uuid)
                or (
                    not stored_map_uuid
                    and str(getattr(preview_state, "preview_on_low_map_type", "") or "").upper() == str(getattr(item, "map_type", "") or "").upper()
                    and (stored_map_index < 0 or stored_map_index == index)
                )
            )
        )

        row = layout.row(align=True)
        enabled = bool(getattr(item, "enabled", False))
        toggle_row = row.row(align=True)
        toggle_row.prop(item, "enabled", text="")
        resolve_state = str(getattr(item, "material_resolve_state", "") or "")
        if resolve_state and resolve_state != constants.MATERIAL_RESOLVE_RESOLVED:
            status_icon = {
                constants.MATERIAL_RESOLVE_PARTIAL: "ERROR",
                constants.MATERIAL_RESOLVE_MISSING: "CANCEL",
                constants.MATERIAL_RESOLVE_INVALID: "ERROR",
                constants.MATERIAL_RESOLVE_APPROXIMATE: "INFO",
            }.get(resolve_state, "INFO")
            status_row = row.row(align=True)
            status_row.alert = resolve_state in {
                constants.MATERIAL_RESOLVE_MISSING,
                constants.MATERIAL_RESOLVE_INVALID,
                constants.MATERIAL_RESOLVE_PARTIAL,
            }
            status_tip = status_row.operator(
                "master_baker.map_material_status",
                text="",
                icon=status_icon,
                emboss=False,
            )
            status_tip.message = _material_resolve_hover_text(item, resolve_state)
        # Keep the content and action regions visually separate. When a compact
        # sample field reaches the split boundary, an aligned split makes Blender
        # join it to the Bake button and shifts the Bake glyph off center.
        split = row.split(factor=0.84, align=False)
        content_row = split.row(align=True)
        content_row.active = enabled
        item_label = _map_stack_item_label(data, item)
        same_type_count = sum(
            1
            for candidate in getattr(data, "maps", [])
            if not getattr(candidate, "is_add_phantom", False)
            and str(getattr(candidate, "map_type", "") or "").strip().upper()
            == str(getattr(item, "map_type", "") or "").strip().upper()
        )
        if same_type_count > 1 and effective_output_suffix:
            item_label = f"{item_label} → {effective_output_suffix}"
        # A label cannot carry a tooltip, so hovering the map name said nothing
        # about what that row bakes.
        icon_value = thumbnail_icon_value or sidebar_icons.get_icon_value("texture_missing")
        map_kwargs = {"text": item_label, "emboss": False}
        if icon_value:
            map_kwargs["icon_value"] = icon_value
        map_info = content_row.operator("master_baker.map_row_info", **map_kwargs)
        map_info.map_type = str(getattr(item, "map_type", "") or "")
        map_info.output_suffix = effective_output_suffix if same_type_count > 1 else ""
        # The name is a button so it can show a tooltip. Buttons swallow the list
        # click, so the button itself has to select the row or the settings below
        # never follow the map the artist clicked.
        map_info.map_index = index

        duplicate_message = exact_duplicate_warning_message(data, item)
        if duplicate_message:
            duplicate_row = content_row.row(align=True)
            duplicate_warning = duplicate_row.operator(
                "master_baker.duplicate_map_warning",
                text="",
                emboss=False,
                **duplicate_warning_icon_kwargs(),
            )
            duplicate_warning.message = duplicate_message

        # Responsive layout: hide less critical elements when width is constrained.
        # The sample slot is reserved on every row whenever it is shown at all.
        # The name is a centered button; drawing the number only on some rows made
        # that button narrower and slid those names off the common center.
        region = context.region
        available_width = getattr(region, "width", 0) if region else 0
        show_samples = available_width > 300
        sample_prop = ""
        if enabled and show_samples:
            if constants.map_uses_samples(
                getattr(item, "map_type", ""),
                getattr(item, "ao_mode", constants.MAP_AO_MODE_RAYCAST),
            ):
                sample_prop = "samples"
            elif constants.effective_lighting_map_type(item) is not None:
                # Scene-lighting rows budget rays via lighting_direct_samples (the generic
                # `samples` field is unused for them).
                sample_prop = "lighting_direct_samples"
        if show_samples:
            sample_slot = content_row.row(align=True)
            sample_slot.ui_units_x = 3.5
            if sample_prop:
                sample_slot.prop(item, sample_prop, text="")
            else:
                sample_slot.label(text="")
        action_row = split.row(align=True)
        action_row.alignment = "RIGHT"
        bake_row = action_row.row(align=True)
        bake_row.enabled = enabled
        bake_map = bake_row.operator("master_baker.bake_map", text="", **_icon_kwargs("bake", "RENDER_STILL"))
        bake_map.map_type = getattr(item, "map_type", "")
        bake_map.map_uuid = item_uuid

        preview_row = action_row.row(align=True)
        preview_row.enabled = has_source
        preview_map = preview_row.operator("master_baker.preview_map_output", text="", icon_value=sidebar_icons.get_icon_value("show_on_low"), depress=preview_active)
        preview_map.map_type = getattr(item, "map_type", "")
        preview_map.map_uuid = item_uuid
        preview_map.group_name = active_group_name
        preview_map.output_suffix = effective_output_suffix
        preview_map.map_stack_index = index
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        if settings is not None:
            session_state = _preview_session_state(settings)
            if session_state is not None:
                preview_map.scope = getattr(session_state, "preview_on_low_scope", "")

        action_row.context_pointer_set("master_baker_map_item", item)
        action_row.menu("MASTER_BAKER_MT_map_item_actions", text="", icon="DOWNARROW_HLT")



class MASTER_BAKER_UL_object_slots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        obj = item.object_ref
        if obj is None:
            layout.label(text="Missing Object", icon="ERROR")
            return
        role = constants.OBJECT_ROLE_LOW
        if active_propname == "high_mesh_index":
            role = constants.OBJECT_ROLE_HIGH

        row = layout.row(align=True)
        active_index = int(getattr(active_data, active_propname, -1) or 0)
        # Per-row LP/HP glyph (matching the list header) so the role reads at a
        # glance and teaches the icon; emboss=False keeps the rows flat like the
        # groups list above rather than raised buttons. The template_list still
        # draws its own active-row highlight (the select op sets the index).
        role_icon = "high_poly" if role == constants.OBJECT_ROLE_HIGH else "low_poly"
        select_object = row.operator(
            "master_baker.select_group_slot_object",
            text=obj.name,
            icon_value=sidebar_icons.get_icon_value(role_icon),
            emboss=False,
            depress=index == active_index,
        )
        select_object.role = role
        select_object.slot_index = index
        if role == constants.OBJECT_ROLE_HIGH:
            # Casts AO: a ghost marks a mesh other meshes' AO looks straight through. An
            # _ignorebf name decides it, so the toggle shows the ghost and greys out.
            ghost = row.row(align=True)
            ghost.prop(
                item,
                "casts_ao",
                text="",
                icon="GHOST_DISABLED" if properties.slot_casts_ao(item) else "GHOST_ENABLED",
                emboss=False,
            )
        hide_object = row.operator(
            "master_baker.toggle_group_slot_visibility",
            text="",
            icon="HIDE_ON" if _object_hidden(obj) else "HIDE_OFF",
            emboss=False,
        )
        hide_object.role = role
        hide_object.slot_index = index


def _unique_output_count(project) -> int:
    """Number of distinct output files, deduping the per-group entries a combined
    texture set records for the same shared atlas file."""
    seen: set[str] = set()
    for out in getattr(project, "latest_outputs", []):
        key = str(getattr(out, "file_path", "") or "").strip().casefold()
        if key:
            seen.add(key)
    return len(seen) or len(getattr(project, "latest_outputs", []))


class MASTER_BAKER_UL_outputs(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        # A combined texture set records one output entry per (group × map) but
        # every group in the set writes the *same* atlas file, so the raw list
        # shows each file N_groups times as indistinguishable rows.  Hide the
        # duplicates, keeping the first entry per unique file path.
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        seen_paths: set[str] = set()
        for i, item in enumerate(items):
            key = str(getattr(item, "file_path", "") or "").strip().casefold()
            if not key:
                continue
            if key in seen_paths:
                flt_flags[i] &= ~self.bitflag_filter_item
            else:
                seen_paths.add(key)
        return flt_flags, []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        layout.label(text=item.display_name or item.file_path, icon="IMAGE_DATA")


def _active_project(scene):
    return properties.peek_active_project(scene)


def _preview_session_state(settings):
    if settings is None:
        return None
    return properties.preview_session_state(settings)


def _any_preview_session_active(session_state) -> bool:
    return bool(
        session_state is not None
        and (
            getattr(session_state, "preview_on_low_active", False)
            or getattr(session_state, "preview_pbr_on_low_active", False)
            or getattr(session_state, "live_normal_preview_active", False)
        )
    )



def _active_group(project):
    if project is None:
        return None
    return properties.peek_active_group(project)


def _project_state_label(project, settings=None) -> str:
    project_state = str(getattr(project, "last_status_message", "") or "").strip() if project is not None else ""
    settings_state = str(getattr(settings, "status_message", "") or "").strip() if settings is not None else ""
    if project_state:
        return project_state
    if settings_state:
        return settings_state
    return constants.STATUS_IDLE


def _active_map(project):
    if project is None:
        return None
    return properties.peek_active_map(project)


def _sidebar_nav_meta(section_id):
    for item_id, label, icon, custom_icon, _operator_id in SIDEBAR_NAV_ITEMS:
        if item_id == section_id:
            return label, icon, custom_icon
    return "Meshes", "OUTLINER_OB_MESH", "bake_group"


def _draw_sidebar_nav(layout, settings, skip_sections=()):
    """Horizontal icon+text tabs for the sidebar sections.

    Drawn in the hierarchy panel body, under the compact bake header, so the
    area corner grip does not cover the last tab. Shift-click multi-select is
    handled by the section operators.
    """
    selected_sections = set(sidebar_state.get_selected_sections(settings))
    tab_row = layout.row(align=True)
    for section_id, label, fallback_icon, custom_icon, operator_id in SIDEBAR_NAV_ITEMS:
        if section_id in skip_sections:
            continue
        kwargs = {"text": label, "depress": section_id in selected_sections}
        icon_value = sidebar_icons.get_icon_value(custom_icon)
        if icon_value:
            kwargs["icon_value"] = icon_value
        else:
            kwargs["icon"] = fallback_icon
        tab_row.operator(operator_id, **kwargs)


def _draw_sidebar_dev_ab_compare(layout, settings):
    """Developer-only A/B compare kept from the removed action strip; it has
    no other home yet."""
    if not preferences.developer_mode_enabled():
        return
    project = _active_project(bpy.context.scene)
    if project is None:
        return
    from . import preview_ab_compare

    session_state = _preview_session_state(settings)
    ab_active = preview_ab_compare.material_ab_compare_is_active(session_state)
    ab_side = preview_ab_compare.material_ab_compare_side(session_state)
    ab_row = layout.row(align=True)
    ab_row.scale_y = 1.15
    ab_label = "A/B"
    if ab_side == preview_ab_compare.AB_SIDE_HIGH:
        ab_label = "A"
    elif ab_side == preview_ab_compare.AB_SIDE_LOW:
        ab_label = "B"
    ab_row.operator(
        "master_baker.toggle_material_ab_compare",
        text=ab_label,
        icon="UV_SYNC_SELECT",
        depress=ab_active,
    )


class MASTER_BAKER_PT_cage_quick_settings(bpy.types.Panel):
    bl_label = "Cage Settings"
    bl_idname = "MASTER_BAKER_PT_cage_quick_settings"
    bl_description = "Cage mode, smoothing, and distance offset for the active bake group"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        project = _active_project(context.scene)
        group = _active_group(project)
        if group is None:
            return

        layout = self.layout
        # Split layout so labels and values pick up the theme's high-contrast text.
        # Without it these rows sit on charcoal in muted grey and read as disabled,
        # which is what a tester reported -- they are editable, and the offsets below
        # are the controls they were trying to read.
        layout.use_property_split = True
        layout.use_property_decorate = False
        row = layout.row()
        row.use_property_split = False
        row.prop(group, "cage_mode", expand=True)
        layout.separator()
        # Mirrors the N-panel Cage section; see ui_sidebar_viewport.
        flags = layout.row(align=True)
        flags.use_property_split = False
        flags.prop(group, "average_normals", text="Smooth Cage")
        flags.prop(group, "match_by_isolation")
        if group.cage_mode == constants.CAGE_MODE_DISTANCE:
            layout.separator()
            draw_cage_offset_controls(layout, group)
        draw_rear_distance_control(layout, group)


class MASTER_BAKER_PT_cage_coverage_settings(bpy.types.Panel):
    bl_label = "Cage Coverage Settings"
    bl_idname = "MASTER_BAKER_PT_cage_coverage_settings"
    bl_description = "Colors for surfaces inside and outside the cage"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        settings = context.scene.fyr_baker_settings
        overlay_state = properties.overlay_settings_state(settings)
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        layout.prop(overlay_state, "heatmap_inside_color", text="Inside")
        layout.prop(overlay_state, "heatmap_outside_color", text="Outside")
        layout.separator()
        layout.operator("master_baker.diagnose_cage_check", text="Diagnose", icon="CONSOLE")


class MASTER_BAKER_PT_cage_viewport_overlays(bpy.types.Panel):
    bl_label = "Viewport Overlays"
    bl_idname = "MASTER_BAKER_PT_cage_viewport_overlays"
    bl_description = "Cage surface and wireframe color and opacity"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 22

    def draw(self, context):
        settings = context.scene.fyr_baker_settings
        overlay_state = properties.overlay_settings_state(settings)
        draw_cage_viewport_overlay_controls(self.layout, overlay_state)


class MASTER_BAKER_PT_skew_needle_settings(bpy.types.Panel):
    bl_label = "Skew Needles"
    bl_idname = "MASTER_BAKER_PT_skew_needle_settings"
    bl_description = "Size of the skew needles, and whether that size stays constant on screen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 22

    def draw(self, context):
        settings = context.scene.fyr_baker_settings
        overlay_state = properties.overlay_settings_state(settings)
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        draw_skew_needle_controls(layout, overlay_state)


def _draw_progress_overlay_dismiss(layout, *, bake_running: bool) -> None:
    """Escape hatch for the viewport progress card.

    The card is derived state: a worker that dies without a final progress write
    leaves it up with nothing left to take it down, and there was no way to get rid
    of it short of restarting Blender. Only drawn while it is actually showing, and
    worded so it is never mistaken for Stop — with a bake genuinely running it is the
    quieter of the two, so it sits below the Stop button rather than beside it.
    """
    # Imported lazily, matching operators.py: setup_progress pulls in Blender's
    # drawing modules and this panel draws on every redraw whether it is up or not.
    try:
        from . import setup_progress

        if not setup_progress.is_showing():
            return
    except Exception:
        return
    row = layout.row(align=True)
    row.active = False
    row.operator(
        "master_baker.dismiss_progress_overlay",
        text="Hide Progress Overlay" if bake_running else "Hide Stuck Progress Overlay",
        icon="PANEL_CLOSE",
    )


def _draw_bake_project_button(layout, project, *, bake_running: bool, project_bake_running: bool, scale_y: float = 2.0) -> None:
    """Bake Project across the full row, with Rebake Changed as a square icon on the right.

    The icon lives in its own fixed slot. Without scale_x the operator stays at
    the icon's own width and the rest of that slot shows up as a gap.
    """
    row = layout.row(align=True)
    row.scale_y = scale_y
    # Drawn under the button, before and during the first bake of a new backend build.
    if runtime.first_bake_after_update_pending():
        _draw_shader_compile_notice(layout)
    if project_bake_running:
        row.alert = True
        row.operator("master_baker.cancel_bake", text="Stop", **_icon_kwargs("bake_stop", "CANCEL"))
        return
    row.enabled = not bake_running
    row.operator("master_baker.bake_project", text="Bake Project", **_icon_kwargs("bake", "RENDER_STILL"))
    changed = row.row(align=True)
    changed.ui_units_x = scale_y
    changed.scale_x = scale_y
    changed.enabled = not bake_running
    changed.operator("master_baker.rebuild_changed_maps", text="", icon="FILE_REFRESH")


def _draw_shader_compile_notice(layout) -> None:
    """runtime.SHADER_COMPILE_NOTICE, so a long first bake after an update does not read as
    a hang."""
    box = layout.box()
    col = box.column(align=True)
    col.scale_y = 0.8
    col.label(text="First bake after an update", icon="INFO")
    col.label(text="Fyr compiles its GPU shaders once.")
    col.label(text="It takes a minute or two; later bakes are fast.")


def _compact_texture_set_label(project) -> str:
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    if focus == constants.HIERARCHY_FOCUS_TEXTURE_SET:
        active_set = properties.get_active_texture_set(project)
        set_name = str(getattr(active_set, "name", "") or "").strip() if active_set is not None else ""
        if set_name:
            return set_name
    group = properties.peek_active_group(project)
    set_name = (getattr(group, "texture_set_name", "") or "").strip() if group is not None else ""
    return set_name or "No Texture Set"


def _groups_in_active_texture_set(project) -> list:
    """Bake groups that belong to the texture set the header is showing."""
    groups = list(getattr(project, "groups", []) or [])
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    if focus == constants.HIERARCHY_FOCUS_TEXTURE_SET:
        active_set = properties.get_active_texture_set(project)
        set_name = str(getattr(active_set, "name", "") or "").strip() if active_set is not None else ""
        return [
            group
            for group in groups
            if (getattr(group, "texture_set_name", "") or "").strip() == set_name
        ]
    active = properties.peek_active_group(project)
    set_name = (getattr(active, "texture_set_name", "") or "").strip() if active is not None else ""
    matched = [
        group
        for group in groups
        if (getattr(group, "texture_set_name", "") or "").strip() == set_name
    ]
    return matched or groups


def _compact_bake_group_label(project) -> str:
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    group = properties.peek_active_group(project)
    if focus == constants.HIERARCHY_FOCUS_TEXTURE_SET:
        active_set = properties.get_active_texture_set(project)
        set_name = str(getattr(active_set, "name", "") or "").strip() if active_set is not None else ""
        group_set = (getattr(group, "texture_set_name", "") or "").strip() if group is not None else ""
        if group is None or group_set != set_name:
            return "No Bake Group"
    if group is None:
        return "No Bake Group"
    name = str(getattr(group, "name", "") or "").strip() or "Bake Group"
    try:
        settings = getattr(getattr(bpy.context, "scene", None), "fyr_baker_settings", None)
    except Exception:
        settings = None
    targeted = properties.bake_group_target_names(project, settings)
    extra = len(targeted) - 1
    if extra > 0:
        return f"{name} +{extra}"
    return name


def _compact_texture_set_names(project) -> list[str]:
    names = []
    seen = set()
    for texture_set in getattr(project, "texture_sets", []):
        name = str(getattr(texture_set, "name", "") or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    for group in getattr(project, "groups", []):
        name = (getattr(group, "texture_set_name", "") or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    return names


def _draw_compact_bake_header(layout, project) -> None:
    """Texture set, bake group, renderer, and device above the hierarchy tree."""
    if project is None or not getattr(project, "groups", None):
        return
    # The texture set name opens the set list. The bake group keeps a dropdown for
    # switching (shift-click adds to the selection) and a gear for that group's settings.
    picker_row = layout.row(align=True)
    set_row = picker_row.row(align=True)
    set_name = _compact_texture_set_label(project)
    set_icon = sidebar_icons.get_icon_value("texture_set")
    set_kwargs = {"text": set_name}
    if set_icon:
        set_kwargs["icon_value"] = set_icon
    else:
        set_kwargs["icon"] = "OUTLINER_COLLECTION"
    set_row.popover("MASTER_BAKER_PT_texture_set_settings", **set_kwargs)
    group_row = picker_row.row(align=True)
    group_icon = sidebar_icons.get_icon_value("cage_item")
    group_kwargs = {"text": _compact_bake_group_label(project)}
    if group_icon:
        group_kwargs["icon_value"] = group_icon
    else:
        group_kwargs["icon"] = "OBJECT_DATA"
    group_row.menu("MASTER_BAKER_MT_hierarchy_bake_group", **group_kwargs)
    group_row.popover("MASTER_BAKER_PT_bake_group_settings", text="", icon="PREFERENCES")

    prefs, resolved = _resolved_renderer_for_ui()
    cycles_active = False
    if prefs is not None:
        device_row = layout.row(align=True)
        device_row.prop(prefs, "render_backend", text="")
        caps = resolved.capabilities if resolved is not None else bake_backends.active_capabilities(prefs)
        cycles_active = getattr(caps, "backend_id", "") == "cycles"
        if cycles_active:
            device_row.prop(prefs, "cycles_device", text="")
        else:
            device_row.prop(prefs, "bake_device", text="")

    _active_bake, bake_running, project_bake_running = _bake_state(project)
    _draw_bake_project_button(
        layout,
        project,
        bake_running=bake_running,
        project_bake_running=project_bake_running,
        scale_y=1.6,
    )
    _draw_progress_overlay_dismiss(layout, bake_running=project_bake_running)
    if not project_bake_running:
        _draw_cycles_material_hint(layout, project)
        _draw_cycles_heavy_high_hint(layout, project, cycles_active=cycles_active)
    if bake_running:
        hint_row = layout.row(align=True)
        hint_row.label(text="Some actions are disabled while a bake is running.", icon="INFO")
    _draw_bake_readiness(layout, project)


def _draw_export_send_row(layout, project, *, project_bake_running: bool) -> None:
    """Export Textures and Send To.

    On the N-panel this is the last row, under the section content. The properties
    Bake panel draws the same row under its Bake button.
    """
    has_outputs = bool(project is not None and getattr(project, "latest_outputs", None))
    export_row = layout.row(align=True)
    export_row.scale_y = 1.4
    export_row.enabled = not project_bake_running
    # One click exports with the project's saved export settings (template, format, folder,
    # texture sets); the cog beside it opens them. A customer spent 20 minutes looking for
    # those settings behind "Export Textures...". Existing files still ask before replacing.
    export_now = export_row.row(align=True)
    export_now.operator_context = "EXEC_DEFAULT"
    export_now.operator("master_baker.export_textures", text="Export Textures", icon="EXPORT")
    export_row.operator("master_baker.export_settings", text="", icon="PREFERENCES")
    send_sub = export_row.row(align=True)
    send_sub.scale_x = 0.6
    send_sub.enabled = has_outputs and external_handoff.any_send_to_destination_enabled(
        preferences.get_preferences(migrate=False)
    )
    send_sub.menu("MASTER_BAKER_MT_send_to", text="Send To", icon="FORWARD")


def _last_bake_label(project, *, project_bake_running: bool) -> str:
    if project is None or project_bake_running:
        return ""
    seconds = float(getattr(project, "last_bake_duration_seconds", 0.0) or 0.0)
    text = runtime.format_duration(seconds) if seconds > 0.0 else ""
    return f"Last bake: {text}" if text else ""


def _draw_support_bundle_button(layout, project) -> None:
    bundle_row = layout.row(align=True)
    bundle_row.enabled = bool(str(getattr(project, "last_workspace_path", "") or "").strip()) if project is not None else False
    bundle_row.operator("master_baker.create_support_bundle", text="Support Bundle", icon="PACKAGE")


def _draw_bake_readiness(layout, project) -> None:
    """Status, Check, inline issues, and the last bake's warning.

    Support Bundle lives in the header gear. Last bake time lives beside that gear.
    """
    if project is None:
        return
    _draw_preflight_summary(layout, project)
    _active_bake, bake_running, project_bake_running = _bake_state(project)
    if bake_running and not project_bake_running:
        layout.label(text="Another project bake is running.", icon="INFO")
    if (
        not project_bake_running
        and getattr(project, "last_warning_count", 0)
        and getattr(project, "last_warning_summary", "")
    ):
        warn_row = layout.row(align=True)
        warn_row.alert = True
        warn_row.operator(
            "master_baker.show_bake_warnings",
            text=bake_warning_headline(project),
            icon="INFO",
        )


def _draw_sidebar_global_actions(layout, settings, project, group):
    overlay_state = properties.overlay_settings_state(settings)
    session_state = _preview_session_state(settings)
    project_name = str(getattr(project, "name", "") or "")
    pbr_active = bool(
        project is not None
        and getattr(session_state, "preview_pbr_on_low_active", False)
        and str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") == project_name
    )

    active_bake, bake_running, project_bake_running = _bake_state(project)

    # Bake row. Changed maps is the small icon on the right of Bake Project.
    _draw_bake_project_button(
        layout,
        project,
        bake_running=bake_running,
        project_bake_running=project_bake_running,
        scale_y=2.0,
    )

    _draw_progress_overlay_dismiss(layout, bake_running=project_bake_running)

    if not project_bake_running:
        _draw_cycles_material_hint(layout, project)

    # Properties Bake panel. The N-panel draws this same row under its Bake Project button.
    _draw_export_send_row(layout, project, project_bake_running=project_bake_running)

    # Preview / cage row
    row = layout.row(align=True)
    row.scale_y = 1.2

    cage_row = row.row(align=True)
    cage_row.enabled = project is not None and group is not None
    is_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
    cage_row.operator("master_baker.toggle_cage_overlay", text="Hide Cage" if is_cage_visible else "Show Cage", icon_value=sidebar_icons.get_icon_value("cage_ui"), depress=is_cage_visible)
    cage_row.popover(
        "MASTER_BAKER_PT_cage_quick_settings",
        text="",
        icon="DOWNARROW_HLT",
    )

    pbr_row = row.row(align=True)
    pbr_row.enabled = project is not None and _pbr_preview_available(project, "")
    pbr_row.alert = pbr_active
    pbr_row.operator(
        "master_baker.preview_pbr_output",
        text="Preview Baked Material",
        icon="SHADING_TEXTURE",
        depress=pbr_active,
    )



def _pbr_preview_shown(settings, project) -> bool:
    """Whether the group-less Preview Baked Material button would turn the preview OFF.

    Same test as the operator (_preview_pbr_on_low_is_active with no group), so the
    icon-only buttons light up exactly when a click stops the preview.
    """
    session_state = _preview_session_state(settings)
    return bool(
        project is not None
        and getattr(session_state, "preview_pbr_on_low_active", False)
        and str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
    )


def _draw_create_group_actions(layout):
    layout.operator("master_baker.add_group", text="Create Bake Group", **_icon_kwargs("add_group", "ADD"))
    layout.operator(
        "master_baker.create_group_from_selection",
        text="Create Bake Group From Selection",
        icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
    )


def _draw_sidebar_active_group_assignments(layout, project, group):
    """The whole bake group block: its settings, then its meshes."""
    _draw_bake_group_settings(layout, project, group)
    if group is not None:
        _draw_bake_group_meshes(layout, project, group)


def _draw_bake_group_settings(layout, project, group):
    """Bake group settings: name, visibility, texture set, UV layer.

    Drawn in the popover beside the bake group dropdown. The Meshes tab shows
    only which meshes are in the group (_draw_bake_group_meshes).
    """
    selected_box = layout.box()

    # Compact group toolbar: create actions on the left, the editable group name
    # filling the middle, and select/hide for the active group pinned right.
    tools = selected_box.row(align=True)
    tools_left = tools.row(align=True)
    tools_left.alignment = "LEFT"
    tools_left.operator("master_baker.add_group", text="", **_icon_kwargs("add_group", "ADD"))
    tools_left.operator("master_baker.create_group_from_selection", text="", icon_value=sidebar_icons.get_icon_value("add_selected_mesh"))
    remove_grp = tools_left.row(align=True)
    remove_grp.enabled = group is not None
    remove_grp.operator("master_baker.remove_group", text="", **_icon_kwargs("remove_group", "REMOVE"))

    if group is None:
        tools_left.label(text="No bake groups yet")
        return

    # Editable name fills the toolbar's middle — the field reads as the group title,
    # so no separate "Name" row/label is needed.
    tools.prop(group, "ui_name", text="")

    role_state = properties.group_role_assignments_state(group)
    tools_right = tools.row(align=True)
    tools_right.alignment = "RIGHT"
    tools_right.operator("master_baker.select_active_group", text="", icon="RESTRICT_SELECT_OFF")
    # Plain click toggles the low-poly (shift-click isolates the whole group), so the icon
    # tracks low-poly visibility.
    group_hide = tools_right.operator(
        "master_baker.toggle_active_group_visibility",
        text="",
        icon=_hide_icon_for_objects(
            [slot.object_ref for slot in getattr(role_state, "low_meshes", [])]
        ),
    )
    group_hide.isolate = False

    # Texture set assignment follows the header selection. Rename, dissolve, and
    # "move all groups" live on the texture set popover.
    targets = _ui_targeted_groups(project) or [group]
    set_names = {(getattr(item, "texture_set_name", "") or "").strip() for item in targets}
    if len(set_names) > 1:
        ts_text = "Mixed"
        icon_kwargs = {}
    else:
        ts_text = next(iter(set_names)) or "Standalone"
        icon_kwargs = _texture_set_icon_kwargs(next(iter(set_names)))
    ts_row = selected_box.row(align=True)
    ts_row.label(text="Texture Set")
    picker = ts_row.operator(
        "master_baker.show_assign_texture_set_menu",
        text=ts_text,
        **icon_kwargs,
    )
    picker.group_name = ""
    picker.apply_to_targets = True
    share_text = _texture_set_share_text(project, targets)
    if share_text:
        share_row = selected_box.row(align=True)
        share_row.active = False
        share_row.label(text=share_text)

    _draw_group_uv_override(selected_box, project, group)


def _draw_bake_group_meshes(layout, project, group):
    """Which meshes are in the bake group: the low and high lists (Meshes tab)."""
    selected_box = layout.box()
    if getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL:
        # Material projects flatten each object's own materials: show a single Objects list,
        # no high-poly assignment column.
        selected_box.label(text="Objects", icon_value=sidebar_icons.get_icon_value("low_poly"))
        _draw_group_role_slot_list(selected_box.column(), group, role=constants.OBJECT_ROLE_LOW, list_id="sidebar_low", rows=3)
    else:
        # One low mesh can feed one texture set per material; only worth a row when a low
        # actually has several slots or the group is already restricted.
        low_role_state = properties.group_role_assignments_state(group)
        if getattr(group, "low_material", None) is not None or any(
            len(getattr(getattr(slot, "object_ref", None), "material_slots", ()) or ()) > 1
            for slot in getattr(low_role_state, "low_meshes", [])
        ):
            selected_box.row(align=True).prop_search(group, "low_material", bpy.data, "materials", text="Only Material")
        # Fills both lists from one selection, by each mesh's own suffix (see
        # ui_group_editor: the per-role buttons below cannot do this, and used to
        # share their label with the group-list button that can).
        selected_box.row(align=True).operator(
            "master_baker.add_selected_split_by_role",
            text="Add Selected (Auto Low/High)",
            icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
        )
        split = selected_box.split(factor=0.5)
        _draw_group_role_slot_list(split.column(), group, role=constants.OBJECT_ROLE_LOW, list_id="sidebar_low", rows=2)
        _draw_group_role_slot_list(split.column(), group, role=constants.OBJECT_ROLE_HIGH, list_id="sidebar_high", rows=2)


def _draw_texture_set_group_row(layout, group, *, is_active: bool) -> None:
    """One bake group under its texture set. The name activates it; the menu moves it."""
    group_name = str(getattr(group, "name", "") or "")
    row = layout.row(align=True)
    split = row.split(factor=0.06, align=True)
    split.label(text="")
    body = split.row(align=True)
    icon = sidebar_icons.get_icon_value("bake_group")
    kwargs = {"text": group_name, "depress": is_active}
    if icon:
        kwargs["icon_value"] = icon
    goto = body.operator("master_baker.set_active_group", **kwargs)
    goto.group_name = group_name
    move = body.operator("master_baker.show_assign_texture_set_menu", text="", icon="DOWNARROW_HLT")
    move.group_name = group_name
    move.apply_to_targets = False


def _draw_texture_set_output_row(layout, project, texture_set) -> None:
    """Output token, with the naming mode as the menu on the right.

    Custom Name edits the texture set name, which is the token written to disk.
    The other modes show the derived token and do not accept typing.
    """
    set_key = str(getattr(texture_set, "name", "") or "").strip()
    effective = (properties.texture_set_effective_name(project, texture_set) or "").strip()
    mode = str(getattr(texture_set, "name_mode", constants.TEXTURE_SET_NAME_CUSTOM) or "")
    row = layout.row(align=True)
    row.label(text="Output")
    if mode == constants.TEXTURE_SET_NAME_CUSTOM:
        row.prop(texture_set, "ui_name", text="")
    else:
        token = row.row(align=True)
        token.active = False
        token.label(text=effective or set_key)
    row.prop(texture_set, "name_mode", text="")

    if mode == constants.TEXTURE_SET_NAME_CUSTOM:
        return
    # texture_set_effective_name falls back to the stored key, so an empty/stored-equal
    # result means the real source (unsaved .blend / no material) isn't available yet.
    if effective and effective != set_key:
        return
    warn = layout.row(align=True)
    warn.alert = True
    if mode == constants.TEXTURE_SET_NAME_BLEND_FILE:
        warn.label(text="Save the .blend file to name outputs after it", icon="ERROR")
    else:
        warn.label(text="Assign a material to the low meshes", icon="ERROR")


def _draw_texture_set_settings(layout, context, project, texture_set):
    """Every texture set, the groups under it, then the active set's output and tiles."""
    del context
    groups = list(getattr(project, "groups", []) or [])
    active_name = str(getattr(texture_set, "name", "") or "").strip() if texture_set is not None else ""
    active_group = properties.peek_active_group(project)
    active_group_name = str(getattr(active_group, "name", "") or "") if active_group is not None else ""
    set_icon = sidebar_icons.get_icon_value("texture_set")

    for candidate in getattr(project, "texture_sets", []) or []:
        set_name = str(getattr(candidate, "name", "") or "").strip()
        if not set_name:
            continue
        is_active_set = set_name == active_name
        row = layout.row(align=True)
        if is_active_set:
            if set_icon:
                row.label(text="", icon_value=set_icon)
            else:
                row.label(text="", icon="OUTLINER_COLLECTION")
            row.prop(candidate, "ui_name", text="")
        else:
            kwargs = {"text": set_name}
            if set_icon:
                kwargs["icon_value"] = set_icon
            else:
                kwargs["icon"] = "OUTLINER_COLLECTION"
            select = row.operator("master_baker.set_active_texture_set", **kwargs)
            select.set_name = set_name
        actions = row.operator("master_baker.show_texture_set_row_menu", text="", icon="DOWNARROW_HLT")
        actions.set_name = set_name
        for group in groups:
            if (getattr(group, "texture_set_name", "") or "").strip() != set_name:
                continue
            _draw_texture_set_group_row(
                layout,
                group,
                is_active=str(getattr(group, "name", "") or "") == active_group_name,
            )

    # A group can name a set that has no collection entry yet (auto-build). Show it
    # so the group is not invisible. Activating the row creates the entry.
    known_sets = {
        str(getattr(candidate, "name", "") or "").strip()
        for candidate in getattr(project, "texture_sets", []) or []
    }
    missing_names = []
    for group in groups:
        name = (getattr(group, "texture_set_name", "") or "").strip()
        if name and name not in known_sets and name not in missing_names:
            missing_names.append(name)
    for set_name in missing_names:
        kwargs = {"text": set_name}
        if set_icon:
            kwargs["icon_value"] = set_icon
        else:
            kwargs["icon"] = "OUTLINER_COLLECTION"
        select = layout.operator("master_baker.set_active_texture_set", **kwargs)
        select.set_name = set_name
        for group in groups:
            if (getattr(group, "texture_set_name", "") or "").strip() != set_name:
                continue
            _draw_texture_set_group_row(
                layout,
                group,
                is_active=str(getattr(group, "name", "") or "") == active_group_name,
            )

    standalone = [group for group in groups if not (getattr(group, "texture_set_name", "") or "").strip()]
    if standalone:
        caption = layout.row(align=True)
        caption.active = False
        caption.label(text="Standalone")
        for group in standalone:
            _draw_texture_set_group_row(
                layout,
                group,
                is_active=str(getattr(group, "name", "") or "") == active_group_name,
            )

    layout.operator_context = "INVOKE_DEFAULT"
    add_set = layout.operator("master_baker.new_texture_set", text="New Texture Set", icon="ADD")
    add_set.assign_active_group = False
    add_set.apply_to_targets = False
    add_set.group_name = ""

    if texture_set is not None:
        layout.separator()
        _draw_texture_set_output_row(layout, project, texture_set)
        _draw_texture_set_udim_settings(layout, project, texture_set)

    destination = _move_all_groups_destination(project)
    if destination:
        layout.separator()
        move_all = layout.operator(
            "master_baker.combine_groups_into_texture_set",
            text=f"Move all groups into {destination}",
        )
        move_all.name = destination


def _draw_sidebar_cage_section(layout, context, settings, project, group):
    if project is None:
        layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
        return

    draw_sidebar_viewport_controls(layout, settings, project, group)


def _has_preppable_meshes(context) -> bool:
    """True when Auto-Rename would actually rename something.

    The prep operator refuses with "No unlabeled meshes to prep" once every mesh already
    carries a Low/High/Cage suffix, so offering it there advertises a button that can only
    error (RC sweep 2026-08-29, finding 1).
    """
    try:
        from . import operators as _operators

        return bool(_operators._proximity_prep_candidates(context))
    except Exception:
        # Never let onboarding copy break a panel draw; showing the route is the safe side.
        return True


def _has_role_named_collections(context) -> bool:
    """True when some mesh sits in a collection whose name declares a bake role.

    Gates the collection-driven namer the same way `_has_preppable_meshes` gates the
    proximity one: a scene organised by name rather than by collection should not be
    offered a button that can only report "no meshes sit in a low/high/cage collection".
    """
    try:
        from . import collection_naming

        scene = getattr(context, "scene", None)
        for obj in getattr(scene, "objects", []) or []:
            if getattr(obj, "type", "") != "MESH":
                continue
            for collection in getattr(obj, "users_collection", ()) or ():
                if collection_naming.role_from_collection_name(getattr(collection, "name", "")):
                    return True
        return False
    except Exception:
        # Never let onboarding copy break a panel draw; showing the route is the safe side.
        return True


def _collection_name_button_text(context) -> str:
    selected_mesh_count = sum(
        1 for obj in getattr(context, "selected_objects", []) if getattr(obj, "type", "") == "MESH"
    )
    return (
        "Name Selected from Collections" if selected_mesh_count else "Name Scene from Collections"
    )


def _name_prep_button_text(context) -> str:
    # Outcome-first label: testers didn't know what "pair" meant, so the button
    # says exactly what it does — rename meshes to the _low/_high convention.
    selected_mesh_count = sum(
        1 for obj in getattr(context, "selected_objects", []) if getattr(obj, "type", "") == "MESH"
    )
    return "Auto-Rename Selected to _low/_high" if selected_mesh_count else "Auto-Rename Scene to _low/_high"


def _draw_add_selected_as_role_row(layout, context) -> None:
    """Add as Low | Add as High: assign the selection to a role directly, no names needed.

    The suffix-driven "Add Selected Meshes" errors on unsuffixed meshes, and the per-role
    buttons used to live only inside an existing group's mesh lists, so a quick test bake
    looked like it required renaming first (customer report 2026-10-12). The operator
    creates the project and group on first use, so select -> Add as Low, select -> Add as
    High, Bake works from an empty scene.
    """
    row = layout.row(align=True)
    row.enabled = any(
        getattr(obj, "type", "") == "MESH" for obj in getattr(context, "selected_objects", None) or ()
    )
    for role in (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH):
        add_role = row.operator(
            "master_baker.add_selected_to_role",
            text=f"Add as {role.title()}",
            icon_value=sidebar_icons.get_icon_value("low_poly" if role == constants.OBJECT_ROLE_LOW else "high_poly"),
        )
        add_role.role = role


def _draw_auto_build_button(layout, context, preppable: bool | None = None) -> None:
    """The emphasised one-click build: Auto Setup when unlabeled meshes exist, else from names.

    Auto Setup is the bounding-box rename followed by the name build, so on a scene with
    nothing left to rename it IS the name build; showing both would offer two buttons
    that do the same thing. Auto-Rename stays a separate button for artists who want to
    review and fix the names before any group is built.
    """
    build = layout.row(align=True)
    build.scale_y = 1.3
    if preppable is None:
        preppable = _has_preppable_meshes(context)
    if preppable:
        build.operator("master_baker.auto_setup", text="Auto Setup", icon="PIVOT_BOUNDBOX")
    else:
        build.operator(
            "master_baker.auto_group_scene_by_name",
            text="Auto-Build Bake Groups from Names",
            icon="SORTALPHA",
        )


def _draw_hierarchy_empty_state(box, settings=None, context=None):
    """First-run onboarding: present two explicit routes into a bake project.

    An Automatic path (scan mesh names and pair Low/High by shared prefix in one
    click, recommended) and a Manual path (build a group from the current
    selection, or add an empty group to fill slot-by-slot). A centered, dimmed
    "or add manually" divider separates the two so a new user instantly sees
    there are two ways in and which one is recommended.
    """
    ui_state = properties.scene_ui_state(settings) if settings is not None else None

    outer = box.column(align=True)

    # -- AUTOMATIC (recommended) -------------------------------------------
    # One-click route: scan the whole scene and pair LP/HP, Low/High, Cage by
    # shared name prefix -- no selection needed. A nested box() groups it as its
    # own path.
    auto = outer.box().column(align=True)
    head = auto.row(align=True)
    head.label(text="Automatic", icon="SORTALPHA")
    tag = head.row(align=True)
    tag.alignment = "RIGHT"
    tag.active = False  # dim so "recommended" reads as a passive label, not a button
    tag.label(text="recommended")
    hint = auto.row(align=True)
    hint.active = False  # dimmed helper line, matches the passive-text idiom
    # Optional prep step for scenes whose meshes have no _low/_high suffixes yet:
    # pair each mesh with its high-poly duplicate and stamp clean suffixes so the
    # name-based build above can then pick them up. Renames only -- no project/groups.
    preppable = _has_preppable_meshes(context or bpy.context)
    hint.label(text="Pairs meshes by name, or by overlap." if preppable else "Pairs meshes by shared name prefix.")
    if preppable:
        prep = auto.row(align=True)
        prep.operator(
            "master_baker.prepare_lowhigh_names",
            text=_name_prep_button_text(context or bpy.context),
            icon="MOD_MESHDEFORM",
        )
    # Second naming route, for scenes organised by collection rather than by name:
    # the role comes from the container, so no polycount or proximity guess is needed.
    if _has_role_named_collections(context or bpy.context):
        from_collections = auto.row(align=True)
        from_collections.operator(
            "master_baker.name_from_collections",
            text=_collection_name_button_text(context or bpy.context),
            icon="OUTLINER_COLLECTION",
        )

    # Texture-set grouping mode, surfaced as an explicit 3-way segmented control so
    # the choice is visible up front rather than hidden behind a chevron. Each mode
    # ships its own icon; prop_enum can't take a custom icon_value, so the toggles are
    # drawn as set_ui_enum operators (icon + depress for the active one) pointed at
    # the ui_state enum. wm.context_set_enum only ever tooltips "Set a context value".
    # Drives both auto-build and add-from-selection.
    if ui_state is not None:
        # Bake-group granularity: one group per part (the default, the Painter/Marmoset
        # convention) or one per first-token name prefix. A prefix too large for one GPU scene is split into parts either way.
        gran_cap = auto.row(align=True)
        gran_cap.active = False
        gran_cap.label(text="Bake Groups")
        current_granularity = str(getattr(ui_state, "auto_group_granularity", "") or "")
        granularities = auto.row(align=True)
        for value, label, icon in (
            (constants.AUTO_GROUP_GRANULARITY_PART, "Per Part", "OUTLINER_OB_MESH"),
            (constants.AUTO_GROUP_GRANULARITY_PREFIX, "Per Name Prefix", "OUTLINER_COLLECTION"),
        ):
            set_granularity = granularities.operator(
                "master_baker.set_ui_enum",
                text=label,
                icon=icon,
                depress=(current_granularity == value),
            )
            set_granularity.data_path = "scene.fyr_baker_settings.ui_state.auto_group_granularity"
            set_granularity.value = value

        cap = auto.row(align=True)
        cap.active = False
        cap.label(text="Texture Sets")
        current_mode = str(getattr(ui_state, "auto_texture_set_mode", "") or "")
        modes = auto.row(align=True)
        for value, label, icon_name in (
            (constants.AUTO_TEXTURE_SET_PER_GROUP, "Per Bake Group", "ts_per_group"),
            (constants.AUTO_TEXTURE_SET_COMBINED, "Combined", "ts_combined"),
            (constants.AUTO_TEXTURE_SET_PER_MATERIAL, "Per Material", "ts_per_material"),
        ):
            set_mode = modes.operator(
                "master_baker.set_ui_enum",
                text=label,
                icon_value=sidebar_icons.get_icon_value(icon_name),
                depress=(current_mode == value),
            )
            set_mode.data_path = "scene.fyr_baker_settings.ui_state.auto_texture_set_mode"
            set_mode.value = value

    # Whether the build organizes the meshes into Fyr's own collections or leaves them
    # in the artist's. A project setting, so it is written on the active project.
    project = properties.get_active_project(getattr(context, "scene", None)) if context is not None else None
    if project is not None:
        collections_cap = auto.row(align=True)
        collections_cap.active = False
        collections_cap.label(text="Collections")
        collection_modes = auto.row(align=True)
        collection_modes.prop_enum(
            project, "collection_mode", constants.COLLECTION_MODE_FYR, text="Fyr Collections", icon="OUTLINER_COLLECTION"
        )
        collection_modes.prop_enum(
            project, "collection_mode", constants.COLLECTION_MODE_EXISTING, text="My Collections", icon="GROUP"
        )

    # Emphasised primary button; runs the auto-build with the mode selected above.
    _draw_auto_build_button(auto, context or bpy.context, preppable)

    # -- labeled divider ---------------------------------------------------
    divider = outer.row(align=True)
    divider.alignment = "CENTER"
    divider.active = False  # dim so it reads as a soft separator, not an action
    divider.label(text="or add manually")

    # -- MANUAL ------------------------------------------------------------
    # Fallback route: make a group from the current viewport selection, or add
    # an empty group to assign meshes slot-by-slot afterwards.
    manual = outer.box().column(align=True)
    manual.label(text="Manual", icon="RESTRICT_SELECT_OFF")
    if getattr(project, "workflow", "") != constants.WORKFLOW_MATERIAL:
        _draw_add_selected_as_role_row(manual, context or bpy.context)
    add_row = manual.row(align=True)
    add_row.operator(
        "master_baker.create_group_from_selection",
        text="Add Selected Meshes",
        icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
    )
    add_row.operator("master_baker.add_group", text="Add Empty Bake Group", **_icon_kwargs("add_group", "ADD"))


def _draw_undo_remove_project(layout) -> None:
    """One-click restore for the most recently removed project, when one is stashed.

    A crash-free stand-in for native Ctrl+Z on remove_project (structural project
    ops can't carry {"UNDO"} without the T74067 memfile-realloc crash)."""
    if not runtime.has_removed_project():
        return
    removed_name = runtime.peek_removed_project_name()
    undo_row = layout.row(align=True)
    label = f"Undo Remove '{removed_name}'" if removed_name else "Undo Remove Project"
    undo_row.operator("master_baker.restore_removed_project", text=label, icon="LOOP_BACK")


def _draw_undo_removed_item(layout, *kinds, **location_match) -> None:
    """One-click restore for the last removed group / map / texture set / mesh slot.

    The stash is a single slot, so at most one of these rows can ever be armed --
    that is what keeps the sidebar from stacking several competing "Undo Remove"
    offers. ``kinds`` scopes a row to the panel the removal happened in, and
    ``location_match`` narrows further (the low and high mesh lists each only offer
    the undo that belongs to their own role).
    """
    for kind in kinds:
        label = runtime.removed_item_undo_label(kind, **location_match)
        if not label:
            continue
        undo_row = layout.row(align=True)
        undo_row.operator("master_baker.restore_removed_item", text=label, icon="LOOP_BACK")
        return


def _collect_hierarchy_tree_rows(project, settings) -> list[dict]:
    """Visible hierarchy lines, top to bottom, including expanded children.

    One dict per row. The scrolling list and the non-list fallback both draw
    from this so the tree cannot drift between the two.
    """
    groups = list(getattr(project, "groups", []))
    is_material_workflow = getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL
    # Every bake group gets a row, so a newly added group shows up next to the others
    # (customer report 2026-10-13: adding one made the rest vanish from the tree).
    # Each group opens and closes with its own arrow, like the Outliner. Selecting a
    # group never opens or closes one: rows moving under the cursor broke the
    # double-click rename on the row the first click had just shifted.
    rows = []

    def _append_children(group_index, child_prefix):
        group = groups[group_index]
        child_objects = _hierarchy_child_objects(group, is_material_workflow=is_material_workflow)
        if not child_objects:
            rows.append({
                "kind": "mesh_empty",
                "group_index": group_index,
                "prefix": child_prefix,
                "is_last": is_material_workflow,
            })
        else:
            for mesh_idx, (_obj, role_icon, role, slot_index) in enumerate(child_objects):
                mesh_is_last = is_material_workflow and (mesh_idx == len(child_objects) - 1)
                rows.append({
                    "kind": "mesh",
                    "group_index": group_index,
                    "role": role,
                    "role_icon": role_icon,
                    "slot_index": slot_index,
                    "prefix": child_prefix,
                    "is_last": mesh_is_last,
                })
        if is_material_workflow:
            return
        rows.append({
            "kind": "aspect",
            "group_index": group_index,
            "prefix": child_prefix,
            "is_last": False,
            "glyph": "cage_ui",
            "operator_id": "master_baker.toggle_group_cage_overlay",
            "aspect": "cage",
        })
        rows.append({
            "kind": "aspect",
            "group_index": group_index,
            "prefix": child_prefix,
            "is_last": True,
            "glyph": "cage_coverage",
            "operator_id": "master_baker.toggle_group_cage_coverage",
            "aspect": "coverage",
        })

    for group_index, group in enumerate(groups):
        is_last = group_index == len(groups) - 1
        is_expanded = bool(getattr(group, "cage_menu_expanded", True))
        rows.append({
            "kind": "group",
            "group_index": group_index,
            "prefix": (),
            "is_last": is_last,
            "is_expanded": is_expanded,
        })
        if is_expanded:
            _append_children(group_index, (not is_last,))
    return rows


def _hierarchy_focus_key(project) -> str:
    project_name = str(getattr(project, "name", "") or "")
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    if focus == constants.HIERARCHY_FOCUS_TEXTURE_SET:
        texture_sets = list(getattr(project, "texture_sets", []))
        set_index = int(getattr(project, "active_texture_set_index", -1))
        set_name = ""
        if 0 <= set_index < len(texture_sets):
            set_name = str(getattr(texture_sets[set_index], "name", "") or "")
        return f"{project_name}|set|{set_name}"
    return f"{project_name}|group|{int(getattr(project, 'active_group_index', -1))}"


def _hierarchy_focused_row_index(rows, project) -> int:
    """Row the list highlight should sit on: the focused texture set or bake group."""
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    if focus == constants.HIERARCHY_FOCUS_TEXTURE_SET:
        texture_sets = list(getattr(project, "texture_sets", []))
        set_index = int(getattr(project, "active_texture_set_index", -1))
        set_name = ""
        if 0 <= set_index < len(texture_sets):
            set_name = str(getattr(texture_sets[set_index], "name", "") or "")
        for index, row in enumerate(rows):
            if row.get("kind") == "set" and row.get("set_name") == set_name:
                return index
        # The tree lists bake groups only; with a texture set focused no group row
        # is the active one, so nothing is highlighted.
        return -1
    group_index = int(getattr(project, "active_group_index", -1))
    for index, row in enumerate(rows):
        if row.get("kind") == "group" and row.get("group_index") == group_index:
            return index
    return 0


def _hierarchy_member_mesh_visible(groups, indices) -> bool:
    for idx in indices:
        role_state = properties.group_role_assignments_state(groups[idx])
        for slot in list(getattr(role_state, "low_meshes", [])) + list(getattr(role_state, "high_meshes", [])):
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            try:
                obj_hidden = bool(obj.hide_get())
            except Exception:
                obj_hidden = bool(getattr(obj, "hide_viewport", False))
            if not obj_hidden:
                return True
    return False


def _hierarchy_mesh_slot(groups, spec):
    group_index = int(spec.get("group_index", -1))
    if group_index < 0 or group_index >= len(groups):
        return None
    role_state = properties.group_role_assignments_state(groups[group_index])
    attr = "low_meshes" if spec.get("role") == "low" else "high_meshes"
    slots = list(getattr(role_state, attr, []))
    slot_index = int(spec.get("slot_index", -1))
    if slot_index < 0 or slot_index >= len(slots):
        return None
    return slots[slot_index]


def _hierarchy_mesh_object(groups, spec):
    return getattr(_hierarchy_mesh_slot(groups, spec), "object_ref", None)


def _hierarchy_casts_ao_slot(groups, spec):
    """The High slot whose Casts AO toggle this row shows, or None (Low rows, Use Low as High)."""
    if spec.get("role") == "low":
        return None
    group_index = int(spec.get("group_index", -1))
    if group_index < 0 or group_index >= len(groups) or properties.group_uses_low_as_high(groups[group_index]):
        return None
    return _hierarchy_mesh_slot(groups, spec)


def _draw_hierarchy_set_row(layout, groups, spec, *, global_cage_visible, active_set_name):
    set_name = spec["set_name"]
    member_indices = spec["member_indices"]
    is_expanded = bool(spec["is_expanded"])
    set_left, set_right = _hierarchy_edge_row(layout)
    _draw_tree_pole_cells(set_left, spec["prefix"], spec["is_last"])
    expander = set_left.operator(
        "master_baker.toggle_texture_set_expansion",
        text="",
        icon="DOWNARROW_HLT" if is_expanded else "RIGHTARROW",
        emboss=False,
    )
    expander.set_name = set_name
    is_active_set = set_name == active_set_name
    select_set = set_left.operator(
        "master_baker.set_active_texture_set",
        text=set_name,
        icon_value=sidebar_icons.get_icon_value("texture_set"),
        emboss=is_active_set,
        depress=is_active_set,
    )
    select_set.set_name = set_name

    member_groups = [groups[idx] for idx in member_indices if 0 <= idx < len(groups)]
    set_cage_visible = global_cage_visible and any(
        not bool(getattr(group, "cage_overlay_hidden", False)) for group in member_groups
    )
    set_right.label(text=str(len(member_indices)))
    cage_op = set_right.operator(
        "master_baker.toggle_texture_set_cage_overlay",
        text="",
        icon_value=sidebar_icons.get_icon_value("cage_on" if set_cage_visible else "cage_off"),
        emboss=False,
    )
    cage_op.set_name = set_name
    eye_op = set_right.operator(
        "master_baker.toggle_texture_set_visibility",
        text="",
        icon="HIDE_OFF" if _hierarchy_member_mesh_visible(groups, member_indices) else "HIDE_ON",
        emboss=False,
    )
    eye_op.set_name = set_name


def _draw_hierarchy_set_empty_row(layout, spec):
    empty_row = layout.row(align=True)
    empty_left = empty_row.row(align=True)
    empty_left.alignment = "LEFT"
    _draw_tree_pole_cells(empty_left, spec["prefix"], True)
    empty_left.label(text="No bake groups")


def _draw_hierarchy_tree_row(layout, spec, project, groups, *, global_cage_visible, coverage_visible, is_material_workflow, active_index, active_set_name, targeted_indices=frozenset(), in_list=False):
    kind = spec.get("kind")
    if kind == "set":
        _draw_hierarchy_set_row(
            layout,
            groups,
            spec,
            global_cage_visible=global_cage_visible,
            active_set_name=active_set_name,
        )
        return
    if kind == "set_empty":
        _draw_hierarchy_set_empty_row(layout, spec)
        return
    if kind == "group":
        group_index = int(spec["group_index"])
        if group_index < 0 or group_index >= len(groups):
            return
        _draw_cage_group_tree_item(
            layout,
            groups[group_index],
            group_index,
            is_active=(group_index == active_index),
            is_targeted=(group_index in targeted_indices),
            global_cage_visible=global_cage_visible,
            coverage_visible=coverage_visible,
            prefix=spec["prefix"],
            is_last=bool(spec["is_last"]),
            is_material_workflow=is_material_workflow,
            draw_children=False,
            name_editable=in_list,
        )
        return
    if kind == "mesh_empty":
        _draw_hierarchy_mesh_empty_row(layout, spec["prefix"], bool(spec["is_last"]))
        return
    if kind == "mesh":
        obj = _hierarchy_mesh_object(groups, spec)
        if obj is None:
            return
        _draw_hierarchy_mesh_row(
            layout, obj, spec["role_icon"], spec["prefix"], bool(spec["is_last"]),
            casts_ao_slot=None if is_material_workflow else _hierarchy_casts_ao_slot(groups, spec),
            name_editable=in_list,
        )
        return
    if kind == "aspect":
        group_index = int(spec["group_index"])
        if group_index < 0 or group_index >= len(groups):
            return
        group = groups[group_index]
        group_name = str(getattr(group, "name", "") or "")
        if spec.get("aspect") == "cage":
            cage_hidden = bool(getattr(group, "cage_overlay_hidden", False))
            active = global_cage_visible and not cage_hidden
            label = f"{group_name} Cage" if group_name else "Cage"
        else:
            active = bool(getattr(group, "show_cage_coverage", False))
            label = f"{group_name} Cage Coverage" if group_name else "Cage Coverage"
        _draw_group_aspect_row(
            layout,
            spec["prefix"],
            is_last=bool(spec["is_last"]),
            glyph=spec["glyph"],
            label=label,
            operator_id=spec["operator_id"],
            group_index=group_index,
            active=active,
        )


def _hierarchy_row_signature(rows) -> str:
    parts = []
    for row in rows:
        prefix = "".join("1" if flag else "0" for flag in row.get("prefix", ()))
        members = ",".join(str(index) for index in row.get("member_indices", ()))
        parts.append(
            "\t".join(
                (
                    str(row.get("kind") or ""),
                    str(row.get("set_name") or ""),
                    str(row.get("group_index", "")),
                    "1" if row.get("is_expanded") else "0",
                    "1" if row.get("is_last") else "0",
                    prefix,
                    str(row.get("role") or ""),
                    str(row.get("role_icon") or ""),
                    str(row.get("slot_index", "")),
                    str(row.get("glyph") or ""),
                    str(row.get("operator_id") or ""),
                    str(row.get("aspect") or ""),
                    members,
                )
            )
        )
    return "\n".join(parts)


def _hierarchy_spec_from_slot(item) -> dict:
    members = tuple(
        int(part)
        for part in str(getattr(item, "member_indices", "") or "").split(",")
        if part.strip()
    )
    prefix = tuple(flag == "1" for flag in str(getattr(item, "prefix", "") or ""))
    return {
        "kind": str(getattr(item, "kind", "") or ""),
        "set_name": str(getattr(item, "set_name", "") or ""),
        "group_index": int(getattr(item, "group_index", -1)),
        "member_indices": members,
        "is_expanded": bool(getattr(item, "is_expanded", False)),
        "is_last": bool(getattr(item, "is_last", True)),
        "prefix": prefix,
        "role": str(getattr(item, "role", "") or ""),
        "role_icon": str(getattr(item, "role_icon", "") or ""),
        "slot_index": int(getattr(item, "slot_index", -1)),
        "glyph": str(getattr(item, "glyph", "") or ""),
        "operator_id": str(getattr(item, "operator_id", "") or ""),
        "aspect": str(getattr(item, "aspect", "") or ""),
    }


def _write_hierarchy_slot(item, row) -> None:
    item.kind = str(row.get("kind") or "")
    item.set_name = str(row.get("set_name") or "")
    item.group_index = int(row.get("group_index", -1))
    item.member_indices = ",".join(str(index) for index in row.get("member_indices", ()))
    item.is_expanded = bool(row.get("is_expanded", False))
    item.is_last = bool(row.get("is_last", True))
    item.prefix = "".join("1" if flag else "0" for flag in row.get("prefix", ()))
    item.role = str(row.get("role") or "")
    item.role_icon = str(row.get("role_icon") or "")
    item.slot_index = int(row.get("slot_index", -1))
    item.glyph = str(row.get("glyph") or "")
    item.operator_id = str(row.get("operator_id") or "")
    item.aspect = str(row.get("aspect") or "")


def _ui_unit_px() -> float:
    """Blender's UI_UNIT_X in pixels. 20px at unit scale, then DPI and interface scale."""
    try:
        system = bpy.context.preferences.system
        view = bpy.context.preferences.view
    except Exception:
        return 0.0
    dpi_fac = float(getattr(system, "dpi", 72) or 72) / 72.0
    pixel_size = float(getattr(system, "pixel_size", 1.0) or 1.0)
    view_scale = float(getattr(view, "ui_scale", 1.0) or 1.0)
    return 20.0 * dpi_fac * pixel_size * view_scale


def _hierarchy_list_row_units(context) -> float:
    """Width of one hierarchy row, in UI units, so it meets the scrollbar.

    A UIList sizes the row from its contents. Short names leave the eye and
    remove icons stranded on the left and a gap in front of the scrollbar.
    The sidebar width is fixed by the artist, so claim that width minus the
    tab strip, box padding, and the scrollbar itself.
    """
    region = getattr(context, "region", None)
    width = float(getattr(region, "width", 0) or 0)
    unit = _ui_unit_px()
    if width <= 0.0 or unit <= 0.0:
        return 0.0
    return max(width / unit - 2.5, 8.0)


# Set while a list row draws. Zero on the inline tree, which is already the box width.
_HIERARCHY_ROW_UNITS = 0.0


def _hierarchy_edge_row(layout):
    """A tree row whose trailing icons sit on the right edge of the list.

    A spacer does not expand inside a UIList row, so the row is split: names
    stay on the left, the eye and remove icons stay in the right-hand slice.
    """
    split = layout.split(factor=0.68, align=True)
    if _HIERARCHY_ROW_UNITS > 0.0:
        split.ui_units_x = _HIERARCHY_ROW_UNITS
    left = split.row(align=True)
    left.alignment = "LEFT"
    right = split.row(align=True)
    right.alignment = "RIGHT"
    return left, right


class MASTER_BAKER_UL_hierarchy(bpy.types.UIList):
    """Scrolling viewport for the bake-project tree.

    Each slot is written by a timer. Panel draw only reads them, because adding
    collection items while drawing leaves the list empty.
    """

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        return [self.bitflag_filter_item] * len(items), []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        global _HIERARCHY_ROW_UNITS
        _HIERARCHY_ROW_UNITS = _hierarchy_list_row_units(context)
        scene = getattr(context, "scene", None)
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        project = _active_project(scene) if scene is not None else None
        if project is None or not str(getattr(item, "kind", "") or ""):
            return
        groups = list(getattr(project, "groups", []))
        overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
        _draw_hierarchy_tree_row(
            layout,
            _hierarchy_spec_from_slot(item),
            **_hierarchy_draw_state(
                project,
                groups,
                global_cage_visible=bool(getattr(overlay_state, "show_cage_overlay", False)),
                coverage_visible=bool(getattr(overlay_state, "show_error_heatmap", False)),
                settings=settings,
                in_list=True,
            ),
        )


# Last focused row we pointed the list highlight at. Wheel-scrolling must not
# rewrite the index, or Blender scrolls the focused row back into view.
_HIERARCHY_LIST_FOCUS_KEY = ""
_HIERARCHY_SYNC_QUEUED = False


def _hierarchy_draw_state(project, groups, *, global_cage_visible, coverage_visible, settings=None, in_list=False):
    focus = str(getattr(project, "hierarchy_focus", constants.HIERARCHY_FOCUS_GROUP) or "")
    group_focused = focus != constants.HIERARCHY_FOCUS_TEXTURE_SET
    active_index = int(getattr(project, "active_group_index", -1)) if group_focused else -1
    # Every group the header dropdown is editing, so shift-selected groups read as
    # selected next to the active one.
    target_names = set(properties.bake_group_target_names(project, settings)) if group_focused else set()
    targeted_indices = frozenset(
        index
        for index, group in enumerate(groups)
        if str(getattr(group, "name", "") or "").strip() in target_names
    )
    collection_names = [str(getattr(texture_set, "name", "") or "") for texture_set in getattr(project, "texture_sets", [])]
    active_set_index = int(getattr(project, "active_texture_set_index", -1))
    active_set_name = collection_names[active_set_index] if 0 <= active_set_index < len(collection_names) else ""
    if group_focused:
        active_set_name = ""
    return {
        "project": project,
        "groups": groups,
        "global_cage_visible": global_cage_visible,
        "coverage_visible": coverage_visible,
        "is_material_workflow": getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL,
        "active_index": active_index,
        "active_set_name": active_set_name,
        "targeted_indices": targeted_indices,
        "in_list": in_list,
    }


def _queue_hierarchy_slot_sync() -> None:
    """Rebuild the scroll list between redraws. Collection edits during draw do not stick."""
    global _HIERARCHY_SYNC_QUEUED
    if _HIERARCHY_SYNC_QUEUED:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    register = getattr(timers, "register", None)
    if not callable(register):
        return
    _HIERARCHY_SYNC_QUEUED = True

    def _run():
        global _HIERARCHY_SYNC_QUEUED, _HIERARCHY_LIST_FOCUS_KEY
        _HIERARCHY_SYNC_QUEUED = False
        try:
            scene = bpy.context.scene
            settings = getattr(scene, "fyr_baker_settings", None)
            project = _active_project(scene)
            ui_state = properties.scene_ui_state(settings) if settings is not None else None
            if project is None or ui_state is None or not hasattr(ui_state, "hierarchy_rows"):
                return None
            rows = _collect_hierarchy_tree_rows(project, settings)
            signature = _hierarchy_row_signature(rows)
            slots = ui_state.hierarchy_rows
            if signature != str(getattr(ui_state, "hierarchy_row_signature", "") or "") or len(slots) != len(rows):
                while len(slots) > len(rows):
                    slots.remove(len(slots) - 1)
                while len(slots) < len(rows):
                    slots.add()
                for item, row in zip(slots, rows):
                    _write_hierarchy_slot(item, row)
                ui_state.hierarchy_row_signature = signature
            focus_key = _hierarchy_focus_key(project)
            _HIERARCHY_LIST_FOCUS_KEY = focus_key
            properties.set_hierarchy_row_index_quietly(ui_state, _hierarchy_focused_row_index(rows, project))
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:
            return None
        return None

    register(_run, first_interval=0.0)


def _hierarchy_list_ready(ui_state, rows) -> bool:
    slots = getattr(ui_state, "hierarchy_rows", None) if ui_state is not None else None
    if slots is None or not hasattr(ui_state, "hierarchy_row_signature"):
        return False
    if len(slots) != len(rows):
        return False
    return str(getattr(ui_state, "hierarchy_row_signature", "") or "") == _hierarchy_row_signature(rows)


def _draw_hierarchy_tree(layout, settings, project, groups, *, global_cage_visible, coverage_visible):
    """Texture sets, bake groups, and meshes. Scrolls once the tree is taller than the viewport."""
    global _HIERARCHY_LIST_FOCUS_KEY, _HIERARCHY_ROW_UNITS
    rows = _collect_hierarchy_tree_rows(project, settings)
    if not rows:
        return
    state = _hierarchy_draw_state(
        project,
        groups,
        global_cage_visible=global_cage_visible,
        coverage_visible=coverage_visible,
        settings=settings,
    )
    ui_state = properties.scene_ui_state(settings) if settings is not None else None
    # Until the timer has copied these rows onto the list, draw them in place.
    # An empty UIList is what showed up when the copy happened during draw.
    if not _hierarchy_list_ready(ui_state, rows):
        _HIERARCHY_ROW_UNITS = 0.0
        tree = layout.column(align=True)
        tree.scale_y = _HIERARCHY_TREE_SCALE_Y
        _queue_hierarchy_slot_sync()
        for row in rows:
            _draw_hierarchy_tree_row(tree, row, **state)
        return
    # Do not scale the list's parent. A scaled column collapses UIList rows to nothing.
    tree = layout.column(align=True)
    focus_key = _hierarchy_focus_key(project)
    if focus_key != _HIERARCHY_LIST_FOCUS_KEY:
        _HIERARCHY_LIST_FOCUS_KEY = focus_key
        _queue_hierarchy_slot_sync()
    visible_rows = min(_HIERARCHY_VISIBLE_ROWS, max(len(rows), 1))
    tree.template_list(
        "MASTER_BAKER_UL_hierarchy",
        "hierarchy_tree",
        ui_state,
        "hierarchy_rows",
        ui_state,
        "hierarchy_row_index",
        rows=visible_rows,
        maxrows=visible_rows,
        sort_lock=True,
    )


def _project_banner_state(project, settings):
    """Visibility used by the project-name row's eye and cage toggles."""
    groups = list(getattr(project, "groups", []) or [])
    overlay_state = properties.overlay_settings_state(settings)
    global_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
    coverage_visible = bool(getattr(overlay_state, "show_error_heatmap", False))
    all_visible = global_cage_visible and not any(bool(getattr(group, "cage_overlay_hidden", False)) for group in groups)
    any_mesh_visible = False
    for group in groups:
        role_state = properties.group_role_assignments_state(group)
        for slot in list(getattr(role_state, "low_meshes", [])) + list(getattr(role_state, "high_meshes", [])):
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            try:
                obj_hidden = bool(obj.hide_get())
            except Exception:
                obj_hidden = bool(getattr(obj, "hide_viewport", False))
            if not obj_hidden:
                any_mesh_visible = True
                break
        if any_mesh_visible:
            break
    project_visible = any_mesh_visible or global_cage_visible or coverage_visible
    return all_visible, coverage_visible, project_visible


def _draw_project_banner(layout, context, settings, project) -> None:
    """Project name and its actions. Sits under the N-panel header on every tab."""
    del context
    if project is None:
        return
    _draw_undo_remove_project(layout)
    groups = list(getattr(project, "groups", []) or [])
    is_material_workflow = getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL
    all_visible, coverage_visible, project_visible = _project_banner_state(project, settings)
    has_meshes = _project_has_meshes(project)
    proj_row = layout.row(align=True)
    proj_row.use_property_decorate = False
    project_icon = sidebar_icons.get_icon_value("bake_project")
    if project_icon:
        proj_row.label(text="", icon_value=project_icon)
    proj_row.prop(project, "ui_name", text="")
    switch = proj_row.row(align=True)
    switch.ui_units_x = 1.0
    switch.menu("MASTER_BAKER_MT_bake_project", text="", icon="DOWNARROW_HLT")
    proj_row.menu("MASTER_BAKER_MT_project_prepare", text="", icon="TOOL_SETTINGS")
    if has_meshes and groups:
        if not is_material_workflow:
            # Same icons and order as the viewport header: cage, then coverage.
            proj_row.operator(
                "master_baker.toggle_all_cage_overlays",
                text="",
                icon_value=sidebar_icons.get_icon_value("cage_ui"),
                depress=all_visible,
            )
            coverage_on = any(bool(getattr(group, "show_cage_coverage", False)) for group in groups)
            proj_row.operator(
                "master_baker.toggle_all_cage_coverage",
                text="",
                icon_value=sidebar_icons.get_icon_value("cage_coverage"),
                depress=coverage_on,
            )
        proj_row.operator(
            "master_baker.toggle_project_visibility",
            text="",
            icon="HIDE_OFF" if project_visible else "HIDE_ON",
        )
    proj_row.operator("master_baker.add_project", text="", **_icon_kwargs("add", "ADD"))
    proj_row.operator("master_baker.duplicate_project", text="", icon="DUPLICATE")
    proj_row.operator("master_baker.remove_project", text="", icon="TRASH")


def _draw_hierarchy_panel(layout, context, settings, project, *, include_compact_header=True, include_project_header=True):
    """Project hierarchy: texture sets > bake groups > meshes."""
    if project is None:
        _draw_undo_remove_project(layout)
        # Two explicit pre-project routes (docs/MATERIAL_BAKING_WORKFLOW_PLAN.md sec 3.1).
        # High -> Low keeps the mesh-prep / suffix / auto-group tooling; Bake Selected
        # Materials must not present those as prerequisites.
        high_box = layout.box()
        high_box.label(text="High to Low Bake", icon="MOD_MESHDEFORM")
        # Optional pre-project prep: pair unlabeled meshes by bounding-box proximity
        # and stamp clean _low/_high names so the name-based auto-build picks them up.
        prep_hint = high_box.column(align=True)
        prep_hint.active = False
        prep_hint.label(text="Meshes pair by name: Body_low bakes from Body_high (_LP/_HP too).")
        # Only offer the rename when there is something to rename. On an already-suffixed
        # scene the old copy asserted "No suffixes yet?" -- false -- and the button it
        # advertised could only raise "No unlabeled meshes to prep".
        preppable = _has_preppable_meshes(context)
        if preppable:
            prep_hint.label(text="No suffixes yet? Auto Setup pairs meshes by overlap.")
        else:
            prep_hint.label(text="Your meshes are already named for pairing.")
        _draw_auto_build_button(high_box, context, preppable)
        if preppable:
            high_box.operator(
                "master_baker.prepare_lowhigh_names",
                text=_name_prep_button_text(context),
                icon="MOD_MESHDEFORM",
            )
        # Meshes sorted into low/high collections can be named from those directly.
        if _has_role_named_collections(context):
            high_box.operator(
                "master_baker.name_from_collections",
                text=_collection_name_button_text(context),
                icon="OUTLINER_COLLECTION",
            )
        _draw_add_selected_as_role_row(high_box, context)
        high_box.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))

        # Bake Selected Materials: flatten the selected objects' own materials, no high poly.
        mat_box = layout.box()
        mat_box.label(text="Material Bake", icon="MATERIAL")
        mat_hint = mat_box.column(align=True)
        mat_hint.active = False
        mat_hint.label(text="Flattens the selected objects' own materials. No high poly needed.")
        mat_box.operator(
            "master_baker.bake_selected_materials",
            text="Bake Selected Materials",
            icon="MATERIAL",
        )
        return

    groups = list(getattr(project, "groups", []))
    if groups and include_compact_header:
        _draw_compact_bake_header(layout, project)
    if include_project_header:
        _draw_project_banner(layout, context, settings, project)
    layout.operator("master_baker.bake_selected_materials", text="Bake Selected Materials", icon="MATERIAL")
    group_box = layout.box()
    # Group and texture-set removals are undone next to the mesh list.
    _draw_undo_removed_item(group_box, runtime.STASH_KIND_GROUP, runtime.STASH_KIND_TEXTURE_SET)

    overlay_state = properties.overlay_settings_state(settings)
    global_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
    coverage_visible = bool(getattr(overlay_state, "show_error_heatmap", False))

    collection_membership.request_sync_from_draw()
    has_meshes = _project_has_meshes(project)
    if not has_meshes:
        _draw_hierarchy_empty_state(group_box, settings, context)

    if groups:
        # Flat, tightened column so the per-row guide icons meet into continuous
        # poles (a nested box() per set would break the vertical lines). The list
        # scrolls once the tree is taller than _HIERARCHY_VISIBLE_ROWS; the header
        # above and the add-mesh footer below stay put.
        _draw_hierarchy_tree(
            group_box,
            settings,
            project,
            groups,
            global_cage_visible=global_cage_visible,
            coverage_visible=coverage_visible,
        )

        # Add as Low/High assigns the selection to the active group (Shift or Ctrl
        # puts it in a new group). The footer adds groups right under the tree, so
        # nobody has to go through the header menu to make one.
        if getattr(project, "workflow", "") != constants.WORKFLOW_MATERIAL:
            _draw_add_selected_as_role_row(group_box, context)
        footer = group_box.row(align=True)
        footer.operator(
            "master_baker.create_group_from_selection",
            text="Add Selected Meshes",
            icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
        )
        footer.operator("master_baker.add_group", text="Add Bake Group", **_icon_kwargs("add_group", "ADD"))

    return


class MASTER_BAKER_MT_group_uv_layer_picker(bpy.types.Menu):
    bl_label = "Bake UV Layer"
    bl_idname = "MASTER_BAKER_MT_group_uv_layer_picker"
    bl_description = "Choose the UV layer this bake group bakes with"

    def draw(self, context):
        layout = self.layout
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        project = properties.get_active_project(getattr(context, "scene", None)) if settings is not None else None
        group = properties.peek_active_group(project) if project is not None else None
        active_low_slot = properties.peek_active_low_slot(group) if group is not None else None
        active_low = getattr(active_low_slot, "object_ref", None) if active_low_slot is not None else None
        active_low_data = getattr(active_low, "data", None) if active_low is not None else None
        active_uv = getattr(getattr(active_low_data, "uv_layers", None), "active", None) if active_low_data is not None else None
        targets = _ui_targeted_groups(project, context) if project is not None else []
        if not targets and group is not None:
            targets = [group]
        requested = {
            (getattr(item, "uv_layer_name", "") or "").strip() for item in targets
        }
        mixed = len(requested) > 1
        agreed = "" if mixed else (next(iter(requested)) if requested else "")

        active_label = f"Active ({active_uv.name})" if active_uv is not None else "Active UV Layer"
        use_active = layout.operator(
            "master_baker.set_group_uv_override",
            text=active_label,
            icon="CHECKMARK" if not mixed and not agreed else "BLANK1",
        )
        use_active.layer_name = ""
        layout.separator()
        for layer in getattr(active_low_data, "uv_layers", []) if active_low_data is not None else []:
            pick = layout.operator(
                "master_baker.set_group_uv_override",
                text=layer.name,
                icon="CHECKMARK" if not mixed and agreed == layer.name else "GROUP_UVS",
            )
            pick.layer_name = layer.name


def _draw_group_uv_override(layout, project, group):
    """UV layer for the selected bake groups.

    The dropdown itself states what will be used ("Using active: UVMap" when no
    override is set). "Mixed" means the selection does not share one override.
    """
    targets = _ui_targeted_groups(project) or [group]
    requested = {(getattr(item, "uv_layer_name", "") or "").strip() for item in targets}
    mixed = len(requested) > 1
    agreed = "" if mixed else (next(iter(requested)) if requested else "")

    active_low_slot = properties.peek_active_low_slot(group)
    active_low = getattr(active_low_slot, "object_ref", None) if active_low_slot is not None else None
    active_low_data = getattr(active_low, "data", None) if active_low is not None else None
    if active_low is None or getattr(active_low, "type", None) != "MESH" or active_low_data is None:
        layout.label(text="No low mesh selected", icon="INFO")
        return
    active_uv = getattr(getattr(active_low_data, "uv_layers", None), "active", None)
    available_uvs = {layer.name for layer in getattr(active_low_data, "uv_layers", [])}
    if mixed:
        dropdown_text = "Mixed"
    elif agreed:
        dropdown_text = agreed
    elif active_uv is not None:
        dropdown_text = f"Using active: {active_uv.name}"
    else:
        dropdown_text = "No UV layers found"
    uv_row = layout.row(align=True)
    uv_row.label(text="UV")
    uv_row.menu(MASTER_BAKER_MT_group_uv_layer_picker.bl_idname, text=dropdown_text, icon="GROUP_UVS")
    if agreed and not mixed:
        uv_row.operator("master_baker.clear_group_uv_override", text="", icon="X")
    # Only add a second line for a real problem: an override naming a missing layer,
    # lows that do not share one active map, or a mesh with no UV layers at all.
    active_names = []
    for item in targets:
        active_names.extend(_group_low_active_uv_names(item))
    if agreed and not mixed and agreed not in available_uvs:
        layout.label(text=f"'{agreed}' not on {active_low.name}", icon="ERROR")
    elif not agreed and len(set(active_names)) > 1:
        warn = layout.row(align=True)
        warn.alert = True
        warn.label(text="Low meshes use different active UV maps", icon="ERROR")
    elif not mixed and not agreed and active_uv is None:
        layout.label(text="Add a UV map to this mesh before baking", icon="ERROR")


# Row height for the hierarchy tree. Tightened below 1.0 so the per-row guide-line
# icons (tree_pipe/tee/elbow) meet edge-to-edge and read as continuous poles; kept
# high enough that text and the right-side toggles stay comfortable and legible.
_HIERARCHY_TREE_SCALE_Y = 0.8

# Visible rows before a list grows a scrollbar. The map stack matches the compact
# stack in the reference recording (six name rows). The hierarchy uses eight
# because those rows are drawn at _HIERARCHY_TREE_SCALE_Y, so the block is about
# the same height. Mouse-wheel scrolling is Blender's UIList behavior once the
# list is taller than this.
_MAP_STACK_VISIBLE_ROWS = 6
_HIERARCHY_VISIBLE_ROWS = 8


def _draw_tree_pole_cells(left, prefix, is_last):
    """Draw the tree guide-line cells at the start of one hierarchy row.

    prefix: iterable of bools, one per ANCESTOR level, True where that ancestor
      still has a sibling below it (so its vertical pole passes through this row).
    is_last: True when this row is the last child of its parent (drawn as an elbow),
      otherwise a tee. Together these render continuous Outliner-style connectors.
    Replaces the old flat BLANK1 spacers; each cell is one icon wide, matching the
    previous per-depth indentation.

    The cells are drawn in a dedicated active=False sub-row so every guide line is
    uniformly dimmed -- they read as passive structure, not clickable controls, and
    do NOT pick up the row's hidden/disabled greying (callers keep any enabled state
    on the content they draw afterwards, not on the guides).
    """
    poles = left.row(align=True)
    poles.active = False
    for continues in prefix:
        poles.label(text="", icon_value=sidebar_icons.get_icon_value("tree_pipe" if continues else "tree_blank"))
    poles.label(text="", icon_value=sidebar_icons.get_icon_value("tree_elbow" if is_last else "tree_tee"))


def _draw_cage_group_tree_item(layout, group, index, *, is_active, is_targeted=False, global_cage_visible=True, coverage_visible=False, prefix=(), is_last=True, is_material_workflow=False, draw_children=True, name_editable=False):
    group_name = str(getattr(group, "name", "") or "")
    is_expanded = bool(getattr(group, "cage_menu_expanded", False))
    prefix = tuple(prefix)

    left, right = _hierarchy_edge_row(layout)
    _draw_tree_pole_cells(left, prefix, is_last)
    # Outliner-style disclosure arrow. It sits in the expander column that the
    # mesh rows fill with a blank, so names stay aligned one level apart.
    expander = left.operator(
        "master_baker.toggle_cage_menu_expansion",
        text="",
        icon="DISCLOSURE_TRI_DOWN" if is_expanded else "DISCLOSURE_TRI_RIGHT",
        emboss=False,
    )
    expander.group_index = index
    # emboss=is_active so the active group draws a highlighted (selected) button;
    # emboss=False would hide the depress highlight entirely.
    selected = is_active or is_targeted
    select_icon = left.operator(
        "master_baker.set_active_group_by_index",
        text="",
        icon_value=sidebar_icons.get_icon_value("cage_item"),
        emboss=selected,
        depress=selected,
    )
    select_icon.group_index = index
    if name_editable:
        # Inside the scrolling list the name is the row's own text field: a click
        # falls through to the list row (ui_state.hierarchy_row_index selects the
        # group), and double-click or Ctrl+click renames it in place like any
        # Blender list. ui_name runs the rename side effects (collections follow).
        left.prop(group, "ui_name", text="", emboss=False)
    else:
        select_op = left.operator(
            "master_baker.set_active_group_by_index",
            text=group_name,
            emboss=is_active,
            depress=is_active,
        )
        select_op.group_index = index

    # Right side: cage visibility + cage coverage toggles pinned to the right edge.
    # The cage toggle shows Cage_On when this group's cage is visible (global master
    # switch on and per-group not hidden), Cage_Off otherwise. The coverage toggle
    # shows CageCoverage_On when this group is the active group and the coverage
    # heatmap is enabled, CageCoverage_Off otherwise.
    ts_name = (getattr(group, "texture_set_name", "") or "").strip()
    ts_menu = right.row(align=True)
    picker = ts_menu.operator(
        "master_baker.show_texture_set_picker",
        text="",
        **_texture_set_icon_kwargs(ts_name),
    )
    picker.group_name = group_name
    # The per-group cage + cage-coverage toggles used to sit here on the collapsed row,
    # crowding the right cluster. They now live as "aspect" child rows inside the
    # expanded group (drawn below, alongside the low/high meshes). Quick global toggles
    # remain in the project header / viewport sidebar.
    # Per-group mesh visibility (eye). The plain-click toggle acts on the low-poly meshes
    # (the working geometry), so the eye reflects low-poly visibility; the high-poly has its
    # own eye in the expanded rows and is only pulled in via shift-click.
    vis_role_state = properties.group_role_assignments_state(group)
    group_mesh_visible = False
    for slot in getattr(vis_role_state, "low_meshes", []):
        obj = getattr(slot, "object_ref", None)
        if obj is None:
            continue
        try:
            obj_hidden = bool(obj.hide_get())
        except Exception:
            obj_hidden = bool(getattr(obj, "hide_viewport", False))
        if not obj_hidden:
            group_mesh_visible = True
            break
    eye_op = right.operator(
        "master_baker.toggle_group_visibility",
        text="",
        icon="HIDE_OFF" if group_mesh_visible else "HIDE_ON",
        emboss=False,
    )
    eye_op.group_index = index
    # Per-group remove, to the right of the cage toggle.
    remove_op = right.operator(
        "master_baker.remove_group",
        text="",
        emboss=False,
        **_icon_kwargs("remove_group", "X"),
    )
    remove_op.group_index = index

    # The scrolling hierarchy list draws each child as its own row. Callers that
    # still want the expanded block in one shot pass draw_children=True.
    if not is_expanded or not draw_children:
        return

    _draw_expanded_group_children(
        layout,
        group,
        index,
        prefix=prefix,
        is_last=is_last,
        is_material_workflow=is_material_workflow,
        global_cage_visible=global_cage_visible,
    )


def _draw_hierarchy_mesh_row(layout, obj, role_icon, prefix, is_last, *, casts_ao_slot=None, name_editable=False):
    """One low-poly or high-poly child under an expanded bake group."""
    try:
        obj_hidden = bool(obj.hide_get())
    except Exception:
        obj_hidden = bool(getattr(obj, "hide_viewport", False))
    try:
        is_selected = bool(obj.select_get())
    except Exception:
        is_selected = False
    child_left, child_right = _hierarchy_edge_row(layout)
    _draw_tree_pole_cells(child_left, prefix, is_last)
    # Leaf meshes have no expander of their own, so occupy the expander column with
    # a blank. Without it the mesh icon lands at the SAME offset as the parent
    # group's icon (the group's expander pushes its icon over by one), so the mesh
    # doesn't read as nested; this blank steps it one level deeper, matching the
    # set -> group indent.
    expander_spacer = child_left.row(align=True)
    expander_spacer.active = False
    expander_spacer.label(text="", icon_value=sidebar_icons.get_icon_value("tree_blank"))
    # Only the name greys out for a hidden object; the guide poles above stay
    # uniformly muted (they are not gated on obj_hidden anymore).
    name_row = child_left.row(align=True)
    # LEFT-align so the role glyph and name pack tightly (like the group rows). The
    # bare nested row defaults to EXPAND, which spreads the two buttons and strands
    # the name off to the right.
    name_row.alignment = "LEFT"
    name_row.active = not obj_hidden
    # Hidden meshes can still be renamed. Only selection is disabled while hidden.
    glyph_row = name_row.row(align=True)
    glyph_row.enabled = not obj_hidden
    select_icon = glyph_row.operator(
        "master_baker.select_cage_object",
        text="",
        icon_value=sidebar_icons.get_icon_value(role_icon),
        emboss=is_selected,
        depress=is_selected,
    )
    select_icon.object_name = obj.name
    if name_editable:
        name_row.prop(obj, "name", text="", emboss=False)
    else:
        name_row.enabled = not obj_hidden
        select_name = name_row.operator(
            "master_baker.select_cage_object",
            text=obj.name,
            emboss=is_selected,
            depress=is_selected,
        )
        select_name.object_name = obj.name
    floater_count = floater_faces.marked_face_count(obj) if casts_ao_slot is not None else 0
    if floater_count:
        # Floater faces marked in Edit Mode bake with Casts AO off (floater_faces.py).
        floaters = child_right.row(align=True)
        floaters.active = False
        floaters.label(text=f"{floater_count} floater", icon="MOD_SOLIDIFY")
    if casts_ao_slot is not None:
        # Casts AO (see MASTER_BAKER_UL_object_slots): the ghost marks a see-through mesh.
        ghost = child_right.row(align=True)
        ghost.prop(
            casts_ao_slot,
            "casts_ao",
            text="",
            icon="GHOST_DISABLED" if properties.slot_casts_ao(casts_ao_slot) else "GHOST_ENABLED",
            emboss=False,
        )
    eye_op = child_right.operator(
        "master_baker.toggle_cage_object_visibility",
        text="",
        icon="HIDE_ON" if obj_hidden else "HIDE_OFF",
        emboss=False,
    )
    eye_op.object_name = obj.name


def _draw_hierarchy_mesh_empty_row(layout, prefix, is_last):
    empty_row = layout.row(align=True)
    empty_left = empty_row.row(align=True)
    empty_left.alignment = "LEFT"
    # With cage aspects hidden (material workflow), the placeholder is the terminal child.
    _draw_tree_pole_cells(empty_left, prefix, is_last)
    # Match the mesh rows' expander-column blank so the placeholder lines up.
    empty_spacer = empty_left.row(align=True)
    empty_spacer.active = False
    empty_spacer.label(text="", icon_value=sidebar_icons.get_icon_value("tree_blank"))
    empty_left.label(text="No meshes")


def _hierarchy_child_objects(group, *, is_material_workflow):
    role_state = properties.group_role_assignments_state(group)
    child_objects = []
    for slot_index, slot in enumerate(list(getattr(role_state, "low_meshes", []))):
        obj = getattr(slot, "object_ref", None)
        if obj is not None:
            child_objects.append((obj, "hierarchy_low_poly", "low", slot_index))
    # Material (self-bake) projects have no high-poly source and no cage aspects.
    if not is_material_workflow and not properties.group_uses_low_as_high(group):
        for slot_index, slot in enumerate(list(getattr(role_state, "high_meshes", []))):
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                child_objects.append((obj, "hierarchy_high_poly", "high", slot_index))
    return child_objects


def _draw_expanded_group_children(layout, group, index, *, prefix, is_last, is_material_workflow, global_cage_visible):
    """Meshes and cage aspects under one expanded bake group, drawn in place."""
    group_name = str(getattr(group, "name", "") or "")
    child_objects = _hierarchy_child_objects(group, is_material_workflow=is_material_workflow)
    # This group's own column continues past its mesh rows only if the group itself
    # has a sibling below it; append that flag so the meshes indent one level deeper.
    child_prefix = tuple(prefix) + (not is_last,)
    # The Cage + Cage Coverage aspect rows are always drawn last, so the mesh rows (or
    # the "No meshes" placeholder) are never the final child — their pole is never a
    # terminal corner.
    if not child_objects:
        _draw_hierarchy_mesh_empty_row(layout, child_prefix, is_material_workflow)
    for mesh_idx, (obj, role_icon, _role, _slot_index) in enumerate(child_objects):
        # In a material project (no cage aspects follow), the last mesh row is terminal.
        mesh_is_last = is_material_workflow and (mesh_idx == len(child_objects) - 1)
        _draw_hierarchy_mesh_row(layout, obj, role_icon, child_prefix, mesh_is_last)

    # Material (self-bake) projects never project through a cage, so the cage aspect
    # rows are omitted entirely.
    if is_material_workflow:
        return

    cage_hidden = bool(getattr(group, "cage_overlay_hidden", False))
    cage_visible = global_cage_visible and not cage_hidden
    _draw_group_aspect_row(
        layout,
        child_prefix,
        is_last=False,
        glyph="cage_ui",
        label=f"{group_name} Cage" if group_name else "Cage",
        operator_id="master_baker.toggle_group_cage_overlay",
        group_index=index,
        active=cage_visible,
    )
    coverage_on = bool(getattr(group, "show_cage_coverage", False))
    _draw_group_aspect_row(
        layout,
        child_prefix,
        is_last=True,
        glyph="cage_coverage",
        label=f"{group_name} Cage Coverage" if group_name else "Cage Coverage",
        operator_id="master_baker.toggle_group_cage_coverage",
        group_index=index,
        active=coverage_on,
    )


def _draw_group_aspect_row(layout, child_prefix, *, is_last, glyph, label, operator_id, group_index, active):
    """Draw a non-mesh "aspect" child row (Cage / Cage Coverage) under a bake group.

    Mirrors the mesh-child layout so the glyph, label, and right-pinned toggle line up
    with the low/high mesh rows above it. The label greys out when the aspect is off.
    """
    left, right = _hierarchy_edge_row(layout)
    _draw_tree_pole_cells(left, child_prefix, is_last)
    # Occupy the expander column with a blank so the glyph nests one level deeper,
    # matching the mesh rows (leaf children have no expander of their own).
    expander_spacer = left.row(align=True)
    expander_spacer.active = False
    expander_spacer.label(text="", icon_value=sidebar_icons.get_icon_value("tree_blank"))
    name_row = left.row(align=True)
    name_row.alignment = "LEFT"
    name_row.enabled = active
    # Draw the glyph and label as operator buttons (matching the mesh rows) so the text
    # lands at the same offset as the LP/HP names; plain labels pack too tightly and the
    # name creeps left. Clicking selects the group, like the parent row.
    glyph_op = name_row.operator(
        "master_baker.set_active_group_by_index",
        text="",
        icon_value=sidebar_icons.get_icon_value(glyph),
        emboss=False,
    )
    glyph_op.group_index = group_index
    name_op = name_row.operator(
        "master_baker.set_active_group_by_index",
        text=label,
        emboss=False,
    )
    name_op.group_index = group_index
    # Use the same eye icon as the mesh rows for a consistent visibility column,
    # rather than the cage/coverage-specific on/off glyphs.
    toggle_op = right.operator(
        operator_id,
        text="",
        icon="HIDE_OFF" if active else "HIDE_ON",
        emboss=False,
    )
    toggle_op.group_index = group_index


def _draw_format_depth_warning(layout, project) -> None:
    """Flag a format/depth pair the bake writer cannot encode (e.g. TGA + 16-bit).

    Drawn, never auto-corrected: silently rewriting the artist's stored Depth or Format
    would hide which of the two they need to change. Preflight blocks the bake."""
    image_format = str(
        getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT
    ).strip().upper()
    bit_depth = getattr(project, "bit_depth", constants.BIT_DEPTH_8)
    if constants.bake_image_format_supports_bit_depth(image_format, bit_depth):
        return
    supported = constants.BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT.get(image_format, ())
    warning_row = layout.row(align=True)
    warning_row.alert = True
    warning_row.label(
        text=f"{image_format} supports {'/'.join(supported)}-bit only",
        icon="ERROR",
    )


def _draw_sidebar_output_settings(layout, project):
    caps = bake_backends.active_capabilities()
    output_box = layout.box().column(align=False)
    # Lock output settings (resolution / format / folder / map stack) while this
    # project is baking — edits can't apply to the in-flight job and only trigger
    # dirty/re-warm churn. Mirrors the Bake button / Changed Maps being disabled.
    _active_bake, _bake_running, project_bake_running = _bake_state(project)
    output_box.enabled = not project_bake_running

    root_row = output_box.row(align=True)
    root_row.prop(project, "output_root", text="Folder")
    root_row.operator("master_baker.open_output_folder", text="", icon_value=sidebar_icons.get_icon_value("open_folder"))
    # No resolved-path readout or copy button here (Glow: duplicate info and
    # clutter — the open-folder button covers it). Only the temporary-output
    # warning survives, since that is a warning rather than a folder readout.
    try:
        temporary_output = export.project_output_is_temporary(project)
    except Exception:
        temporary_output = False
    if temporary_output:
        temp_row = output_box.row(align=True)
        temp_row.alert = True
        try:
            recovered_autosave = export.blend_session_is_recovered_autosave()
        except Exception:
            recovered_autosave = False
        if recovered_autosave:
            # Recovered autosave: baking is refused until the file is saved,
            # so the row states that instead of the softer scratch-file hint.
            temp_row.label(text=export.RECOVERED_AUTOSAVE_STATUS, icon="ERROR")
        else:
            temp_row.label(text="Temporary output: save the blend or set a folder", icon="ERROR")

    # Folder above, image size/format below: the blank line keeps breathing
    # room between the groups (tester feedback: densest UI in the addon).
    output_box.separator()

    resolution_locked = bool(getattr(project, "lock_resolution", True))
    size_row = output_box.row(align=True)
    x_row = size_row.row(align=True)
    x_row.prop(project, "resolution_x", text="X")
    x_row.menu("MASTER_BAKER_MT_resolution_presets", text="", icon='DOWNARROW_HLT')
    lock_row = size_row.row(align=True)
    lock_row.ui_units_x = 1.1
    lock_row.prop(
        project,
        "lock_resolution",
        text="",
        icon="LINKED" if resolution_locked else "UNLINKED",
        toggle=True,
    )
    y_row = size_row.row(align=True)
    y_row.enabled = not resolution_locked
    # Compact label rather than a warning row: greying alone left the aspect lock silent,
    # so an edit to Y that snapped straight back to X read as a bug (live QA 2026-08-17).
    y_row.prop(project, "resolution_y", text=_RESOLUTION_Y_LOCKED_LABEL if resolution_locked else "Y")
    y_row.menu("MASTER_BAKER_MT_resolution_presets", text="", icon='DOWNARROW_HLT')

    detail_row = output_box.row(align=True)
    # The mode used to be a labeled enum beside the pixel count, which pushed the
    # "Dilation" label off a normal N-panel. The count stays a value field; the mode
    # is an icon menu the width of one button. Infinite keeps the count visible but
    # inactive, since that distance is not used.
    dilation_row = detail_row.row(align=True)
    infinite_dilation = (
        str(getattr(project, "margin_mode", constants.DILATION_DISTANCE) or constants.DILATION_DISTANCE)
        == constants.DILATION_INFINITE
    )
    value_row = dilation_row.row(align=True)
    value_row.enabled = not infinite_dilation
    value_row.prop(project, "margin", text="Dilation")
    # icon_only keeps the current mode glyph and the menu arrow, without the
    # "Distance" / "Infinite" words that were crowding the label off the row.
    mode_row = dilation_row.row(align=True)
    mode_row.ui_units_x = 2.2
    mode_row.prop(project, "margin_mode", text="", icon_only=True)
    # Depth and Format stay a tight pair on the right. Their buttons are only as
    # wide as "16-bit" and "TIFF"; the rest of the row belongs to Dilation.
    tail = detail_row.row(align=True)
    depth_label = tail.row(align=True)
    depth_label.alignment = "RIGHT"
    depth_label.label(text="Depth:")
    tail.prop(project, "bit_depth", text="")
    format_label = tail.row(align=True)
    format_label.alignment = "RIGHT"
    format_label.label(text="Format:")
    tail.prop(project, "image_format", text="")
    _draw_format_depth_warning(output_box, project)

    # OpenGL / DirectX green-channel convention for the tangent Normal map, surfaced
    # here as a project-wide output choice (moved out of the per-map Normal settings).
    normal_rows = [
        m for m in getattr(project, "maps", [])
        if getattr(m, "map_type", "") == constants.MAP_NORMAL
        and not getattr(m, "is_add_phantom", False)
    ]
    # Prefer an enabled row: with duplicate Normal rows the control must edit the
    # one that bakes (its update mirrors the pick to the other Normal rows).
    normal_map = next((m for m in normal_rows if getattr(m, "enabled", True)), normal_rows[0] if normal_rows else None)
    if normal_map is not None:
        # expand=True makes Blender drop the `text=` label, so the label is drawn by hand.
        # The expanded enum must sit in a ROW: dropped straight into the split it lands in
        # a column slot and renders as two stacked, unlabeled buttons (Glow, 2026-09-02).
        nf_split = output_box.row(align=True).split(factor=0.36, align=True)
        nf_label = nf_split.row(align=True)
        nf_label.alignment = "RIGHT"
        nf_label.label(text="Normal Format")
        nf_split.row(align=True).prop(normal_map, "normal_format", expand=True)

    # No Tangents row: MikkTSpace is the only basis (Blender, Painter, Marmoset and
    # the engines all use it). The property stays for the job format and cache keys.

    # Projection-quality group. Anti-aliasing and denoise each get a full row
    # instead of sharing one with the backface/opacity toggles (tester feedback).
    def _project_control_supported(property_name):
        return bake_backends.control_supported(
            bake_backends.CONTROL_SCOPE_PROJECT,
            property_name,
            capabilities=caps,
        )

    quality_props = [name for name in ("aa_samples", "ignore_backface", "respect_opacity") if _project_control_supported(name)]
    if quality_props or caps.supports_denoise:
        output_box.separator()
    if "aa_samples" in quality_props:
        aa_row = output_box.row(align=True)
        aa_row.prop(project, "aa_samples", text="Anti-Aliasing")
    # Project-wide Soften. Individual map rows inherit this unless they tick
    # Override Soften (see ui_map_settings._draw_map_soften).
    soften_row = output_box.row(align=True)
    soften_row.prop(project, "soften", text="Soften")
    # Independent checkboxes on one row. Toggle buttons on a shared row read as a
    # single either/or control; plain checkboxes stay two separate flags.
    if "ignore_backface" in quality_props or "respect_opacity" in quality_props:
        flag_row = output_box.row(align=True)
        if "ignore_backface" in quality_props:
            flag_row.prop(project, "ignore_backface", text="Ignore Backface")
        if "respect_opacity" in quality_props:
            flag_row.prop(project, "respect_opacity", text="Respect Opacity")

    if caps.supports_denoise:
        denoise_row = output_box.row(align=True)
        denoise_row.prop(project, "denoise_quality", text="Denoise")
        denoise_row.prop(project, "denoise_strength", text="Strength")


def _draw_sidebar_maps_section(layout, context, settings, project, group):
    del context, settings, group
    if project is None:
        layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
        return
    _draw_map_stack_editor(layout, project)


def _draw_sidebar_output_section(layout, context, settings, project, group):
    del context, settings, group
    if project is None:
        layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
        return
    _draw_sidebar_output_settings(layout, project)


def _draw_live_normal_preview_action(layout, settings, project, group, *, bake_running: bool):
    if project is None or group is None:
        return
    session_state = _preview_session_state(settings)
    live_active = bool(
        getattr(session_state, "live_normal_preview_active", False)
        and str(getattr(session_state, "live_normal_preview_project_name", "") or "") == str(getattr(project, "name", "") or "")
        and str(getattr(session_state, "live_normal_preview_group_name", "") or "") == str(getattr(group, "name", "") or "")
    )
    row = layout.row(align=True)
    row.enabled = live_active or not bake_running
    row.alert = live_active
    row.operator(
        "master_baker.toggle_live_normal_preview",
        text="Live Normal",
        icon="SHADING_TEXTURE",
        depress=live_active,
    )


def _live_bake_is_active(settings, project) -> bool:
    session_state = _preview_session_state(settings)
    if session_state is None or project is None or not bool(getattr(session_state, "live_bake_active", False)):
        return False
    projects = getattr(settings, "projects", [])
    project_index = int(getattr(session_state, "live_bake_project_index", -1))
    if 0 <= project_index < len(projects) and projects[project_index] == project:
        return True
    return str(getattr(session_state, "live_bake_project_name", "") or "") == str(getattr(project, "name", "") or "")


def _map_source_available(project, map_type: str, group_name: str) -> bool:
    if project is None:
        return False
    # Nothing has been baked yet: there is no output to resolve and no file to stat.
    if not getattr(project, "latest_outputs", None):
        return False

    def _resolve() -> bool:
        output_target, _source_file_path = _resolve_map_output_target(
            project,
            map_type=map_type,
            group_name=group_name,
        )
        return output_target is not None

    return _cached_output_flag(
        ("map_source", _project_output_revision(project), str(map_type or ""), str(group_name or "")),
        _resolve,
    )


def _pbr_preview_available(project, group_name: str) -> bool:
    """Is there at least one baked file the "Preview Baked Material" button can use?

    Drawn as the enabled state of a button, so this used to run a full output
    resolve (up to eleven map types, each ending in a stat) for every group on
    every redraw, including the common case of a project that has never baked.
    The answer only moves when the outputs move, so it is memoised on the
    project's output revision behind a one second TTL.
    """
    if project is None:
        return False
    # Before the first bake there is nothing to look for: skip the whole resolve.
    if not getattr(project, "latest_outputs", None):
        return False

    def _resolve() -> bool:
        return _pbr_preview_available_uncached(project, group_name)

    return _cached_output_flag(
        ("pbr_preview", _project_output_revision(project), str(group_name or "")),
        _resolve,
    )


def _pbr_preview_available_uncached(project, group_name: str) -> bool:
    preview_map_types = (
        constants.MAP_NORMAL,
        constants.MAP_BENT_NORMAL,
        constants.MAP_AO,
        constants.MAP_CURVATURE,
        constants.MAP_MATERIAL_ALBEDO,
        constants.MAP_MATERIAL_ROUGHNESS,
        constants.MAP_MATERIAL_METALNESS,
        constants.MAP_MATERIAL_EMISSION,
        constants.MAP_MATERIAL_OPACITY,
        constants.MAP_MATERIAL_SPECULAR,
        constants.MAP_MATERIAL_TRANSMISSION,
    )
    requested_group_name = str(group_name or "").strip()
    if requested_group_name:
        return any(_map_source_available(project, map_type, requested_group_name) for map_type in preview_map_types)
    for group in getattr(project, "groups", []):
        gn = str(getattr(group, "name", "") or "")
        if not gn:
            continue
        if any(_map_source_available(project, map_type, gn) for map_type in preview_map_types):
            return True
    return False


def _preview_scope_group_names(project, group, scope: str) -> list[str]:
    normalized_scope = str(scope or "").strip().upper()
    if normalized_scope == constants.PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP:
        group_name = str(getattr(group, "name", "") or "")
        return [group_name] if group_name else []
    return [
        str(getattr(candidate, "name", "") or "")
        for candidate in getattr(project, "groups", [])
        if str(getattr(candidate, "name", "") or "")
    ]


def _map_has_preview_source(project, map_item, group_names: list[str]) -> bool:
    return bool(_first_map_preview_source_group(project, map_item, group_names))


def _first_map_preview_source_group(project, map_item, group_names: list[str]) -> str:
    for group_name in group_names:
        source_context = _map_source_context(project, map_item, group_name=group_name)
        if source_context["output_target"] is not None and source_context["source_file_path"]:
            return group_name
    return ""


def _map_type_has_preview_source(project, map_type: str, group_names: list[str]) -> bool:
    return any(_map_source_available(project, map_type, group_name) for group_name in group_names)


def _draw_sidebar_preview_section(layout, context, settings, project, group):
    if project is None:
        layout.label(text="Create a bake project before previewing outputs.", icon="INFO")
        return

    session_state = _preview_session_state(settings)
    if session_state is None:
        return

    scope_box = layout.box()
    scope_box.label(text="Preview Scope")
    scope_box.prop(session_state, "preview_on_low_scope", expand=True)
    scope = str(
        getattr(session_state, "preview_on_low_scope", constants.PREVIEW_ON_LOW_SCOPE_ALL_GROUPS)
        or constants.PREVIEW_ON_LOW_SCOPE_ALL_GROUPS
    )
    group_names = _preview_scope_group_names(project, group, scope)
    active_group_scope = scope == constants.PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP
    operator_group_name = str(getattr(group, "name", "") or "") if active_group_scope else ""
    solo_row = scope_box.row(align=True)
    solo_row.enabled = group is not None
    solo_row.operator(
        "master_baker.isolate_active_group",
        text="Restore Visibility" if bool(getattr(group, "isolate_in_viewport", False)) else "Solo Active Bake Group",
        icon="HIDE_OFF" if bool(getattr(group, "isolate_in_viewport", False)) else "HIDE_ON",
    )

    pbr_box = layout.box()
    pbr_box.label(text="Preview Baked Material", icon="NODE_MATERIAL")
    selected_normal_source = str(
        getattr(session_state, "pbr_preview_normal_source", constants.PBR_PREVIEW_NORMAL_TANGENT)
        or constants.PBR_PREVIEW_NORMAL_TANGENT
    )
    tangent_available = _map_type_has_preview_source(project, constants.MAP_NORMAL, group_names)
    bent_available = _map_type_has_preview_source(project, constants.MAP_BENT_NORMAL, group_names)
    source_row = pbr_box.row(align=True)
    tangent_row = source_row.row(align=True)
    tangent_row.enabled = tangent_available
    tangent = tangent_row.operator(
        "master_baker.set_pbr_preview_normal_source",
        text="Tangent Normal",
        depress=selected_normal_source == constants.PBR_PREVIEW_NORMAL_TANGENT,
    )
    tangent.source = constants.PBR_PREVIEW_NORMAL_TANGENT
    bent_row = source_row.row(align=True)
    bent_row.enabled = bent_available
    bent = bent_row.operator(
        "master_baker.set_pbr_preview_normal_source",
        text="Bent Normal",
        depress=selected_normal_source == constants.PBR_PREVIEW_NORMAL_BENT,
    )
    bent.source = constants.PBR_PREVIEW_NORMAL_BENT
    pbr_box.prop(session_state, "pbr_preview_ao_strength", text="AO Strength", slider=True)

    pbr_active = bool(
        getattr(session_state, "preview_pbr_on_low_active", False)
        and str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
        and str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "") == operator_group_name
    )
    pbr_row = pbr_box.row(align=True)
    selected_normal_available = (
        bent_available
        if selected_normal_source == constants.PBR_PREVIEW_NORMAL_BENT
        else tangent_available
    )
    ao_available = _map_type_has_preview_source(project, constants.MAP_AO, group_names)
    pbr_row.enabled = selected_normal_available or ao_available
    pbr_row.alert = pbr_active
    pbr_op = pbr_row.operator(
        "master_baker.preview_pbr_output",
        text="Stop Material Preview" if pbr_active else "Preview Baked Material",
        icon="SHADING_TEXTURE",
        depress=pbr_active,
    )
    pbr_op.group_name = operator_group_name

    environment_box = layout.box()
    environment_box.label(text="Environment", icon="WORLD")
    env_col = environment_box.column(align=True)
    env_col.enabled = pbr_active
    env_col.prop(session_state, "preview_environment_rotation", text="Rotation")
    env_col.prop(session_state, "preview_environment_strength", text="Strength", slider=True)
    env_col.prop(session_state, "preview_environment_show_background", text="Show Background")
    if not pbr_active:
        env_col.label(text="Enable Preview Baked Material to adjust", icon="INFO")

    baked_maps_row = layout.row(align=True)
    baked_maps_row.label(text="Baked Maps", icon="TEXTURE_DATA")
    baked_maps_row.menu("MASTER_BAKER_MT_baked_maps_dropdown", text="", icon="DOWNARROW_HLT")

    if _any_preview_session_active(session_state):
        layout.operator(
            "master_baker.restore_preview_materials",
            text="Restore Original Materials",
            icon="LOOP_BACK",
        )


def _preflight_summary_revision(project) -> tuple:
    """Cheap key for "would the draw-path validation report change?".

    Everything in it is already in memory. Any edit that can move the report -
    renaming, adding or removing a map or a group, retargeting the output folder,
    or finishing a bake - moves one of these values."""
    try:
        pointer = int(project.as_pointer())
    except Exception:
        pointer = id(project)
    try:
        map_count = len(getattr(project, "maps", ()) or ())
    except Exception:
        map_count = 0
    try:
        group_count = len(getattr(project, "groups", ()) or ())
    except Exception:
        group_count = 0
    return (
        pointer,
        str(getattr(project, "last_job_id", "") or ""),
        map_count,
        group_count,
        str(getattr(project, "output_root", "") or ""),
    )


def _cached_preflight_summary(project):
    """Draw-path validation report, memoised on a cheap revision plus a TTL.

    This ran in full on every redraw, and during a bake the region redraws at the
    progress-poll cadence. ``probe_filesystem=False`` keeps the draw path off the
    disk entirely; the "Check" button and the pre-bake preflight still probe."""
    key = _preflight_summary_revision(project)
    now = time.monotonic()
    cached = _PREFLIGHT_SUMMARY_CACHE.get(key)
    if cached is not None and (now - cached[0]) < _DRAW_CACHE_TTL_S:
        return cached[1], cached[2], cached[3], cached[4]
    issues = validation.validate_bake_project(project, check_topology=False, probe_filesystem=False)
    errors, warnings = validation.summarize_issues(issues)
    grouped = list(validation.summarize_issues_grouped(issues))
    _sweep_draw_cache(_PREFLIGHT_SUMMARY_CACHE, now)
    _PREFLIGHT_SUMMARY_CACHE[key] = (now, issues, errors, warnings, grouped)
    return issues, errors, warnings, grouped


def _draw_preflight_summary(layout, project):
    # Lightweight validation check for immediate UI feedback (no topology check here for
    # performance, and no filesystem probe: this runs on every redraw).
    _issues, errors, warnings, grouped_issues = _cached_preflight_summary(project)

    row = layout.row(align=True)
    row.scale_y = 0.95
    if errors:
        state_text, state_icon = f"{len(errors)} Error(s)", "ERROR"
    elif warnings:
        state_text, state_icon = f"{len(warnings)} Warning(s)", "INFO"
    elif high_mesh_cache.is_mesh_prewarm_pending() or runtime.is_prepare_in_flight():
        elapsed = runtime.prewarm_elapsed_str()
        state_text, state_icon = _warming_up_label(elapsed), "FILE_REFRESH"
    elif int(getattr(project, "last_warning_count", 0) or 0):
        # The project validates, but the last run left a warning on the next row.
        # Last bake time lives in the panel header, so this line points at the warning.
        state_text, state_icon = "Ready. See warning below", "CHECKMARK"
    elif int(getattr(project, "last_error_count", 0) or 0):
        state_text, state_icon = "Ready. Last bake had errors", "CHECKMARK"
    else:
        state_text, state_icon = "Bake Ready", "CHECKMARK"
    # Drawn as a flat operator, not a label, so hovering it shows the full state
    # message ("Pre-flight validation passed! ...") as a tooltip. That message used
    # to sit on its own "State:" row below and was clipped at any sane panel width.
    row.operator("master_baker.show_bake_state", text=state_text, icon=state_icon, emboss=False)

    # Validation action. Support Bundle is in the header gear, not this row.
    row.operator("master_baker.run_preflight", text="Check", icon="VIEWZOOM")

    # Surface the actual problems inline (not just the count) so the user can see
    # what's wrong without running a separate check. Grouped by subject; top few,
    # first message each. The full topology-aware report still lives behind "Check".
    if errors or warnings:
        detail = layout.column(align=True)
        detail.scale_y = 0.9
        for bucket in grouped_issues[:3]:
            if bucket.errors:
                issue, bucket_icon, is_error = bucket.errors[0], "ERROR", True
            elif bucket.warnings:
                issue, bucket_icon, is_error = bucket.warnings[0], "INFO", False
            else:
                continue
            detail_row = detail.row(align=True)
            detail_row.alert = is_error
            text = f"{bucket.label}: {issue.message}"
            # A row that names a mesh is a click target: select it and frame it,
            # so "missing UVs on Wheel_low" takes the artist to Wheel_low.
            object_name = _preflight_issue_object_name(issue)
            if object_name:
                focus = detail_row.operator(
                    "master_baker.focus_validation_object", text=text, icon=bucket_icon, emboss=False
                )
                focus.object_name = object_name
            else:
                detail_row.label(text=text, icon=bucket_icon)


def _preflight_issue_object_name(issue) -> str:
    """The scene object a validation issue points at, or "" when it names none."""
    name = str(getattr(issue, "object_name", "") or "").strip()
    if not name:
        return ""
    objects = getattr(getattr(bpy, "data", None), "objects", None)
    getter = getattr(objects, "get", None)
    if not callable(getter):
        return ""
    try:
        return name if getter(name) is not None else ""
    except Exception:
        return ""


def _map_type_hover_text(map_type: str) -> str:
    key = str(map_type or "").strip().upper()
    for item in constants.MAP_TYPE_ITEMS:
        if item[0] == key:
            detail = item[2] if len(item) > 2 else ""
            return str(detail or item[1])
    label = naming.map_label(key)
    return label or "Output map"


def _material_resolve_hover_text(item, resolve_state: str) -> str:
    message = str(getattr(item, "material_status_message", "") or "").strip()
    if message:
        return message
    for identifier, _name, description in constants.MATERIAL_RESOLVE_ITEMS:
        if identifier == resolve_state and description:
            return str(description)
    return "Material source status"


def _udim_status_icon(state) -> str | None:
    if state is None:
        return None
    if getattr(state, "is_error", False):
        return "ERROR"
    if getattr(state, "is_warning", False):
        return "INFO"
    if getattr(state, "baked", False):
        return "CHECKMARK"
    return None


_UI_ENUM_ITEM_SOURCES = {
    "cage_settings_scope": constants.CAGE_SETTINGS_SCOPE_ITEMS,
    "auto_group_granularity": constants.AUTO_GROUP_GRANULARITY_ITEMS,
    "auto_texture_set_mode": constants.AUTO_TEXTURE_SET_MODE_ITEMS,
}


def _ui_enum_item_description(data_path: str, value: str) -> str:
    prop_name = str(data_path or "").rsplit(".", 1)[-1]
    for item in _UI_ENUM_ITEM_SOURCES.get(prop_name, ()):
        if item[0] == str(value or ""):
            detail = item[2] if len(item) > 2 else ""
            return str(detail or item[1])
    return ""


class MASTER_BAKER_OT_export_settings(bpy.types.Operator):
    bl_idname = "master_baker.export_settings"
    bl_label = "Export Settings"
    bl_description = (
        "Choose the output template, file format, output folder and texture sets for Export "
        "Textures, then export"
    )
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        return settings is not None and len(getattr(settings, "projects", ())) > 0

    def invoke(self, context, event):
        return bpy.ops.master_baker.export_textures("INVOKE_DEFAULT")

    def execute(self, context):
        return bpy.ops.master_baker.export_textures("INVOKE_DEFAULT")


class MASTER_BAKER_OT_set_ui_enum(bpy.types.Operator):
    """Segmented N-panel choice.

    Drawn instead of ``wm.context_set_enum``, whose tooltip is only "Set a
    context value" and hides the enum item's own description.
    """

    bl_idname = "master_baker.set_ui_enum"
    bl_label = "Set Option"
    bl_description = "Choose this option"
    bl_options = {"REGISTER", "UNDO"}

    data_path: bpy.props.StringProperty(name="Data Path", options={"HIDDEN"})
    value: bpy.props.StringProperty(name="Value", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        return _ui_enum_item_description(
            getattr(properties, "data_path", ""),
            getattr(properties, "value", ""),
        ) or cls.bl_description

    def execute(self, context):
        path = str(self.data_path or "").strip()
        if not path.startswith("scene.fyr_baker_settings."):
            return {"CANCELLED"}
        scene = getattr(context, "scene", None)
        if scene is None:
            return {"CANCELLED"}
        obj = scene
        parts = path.split(".")
        try:
            for part in parts[1:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], self.value)
        except Exception:
            self.report({"WARNING"}, "Could not set that option")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_udim_tile_status(bpy.types.Operator):
    """Hover target for a UDIM tile's status icon. Clicking does nothing."""

    bl_idname = "master_baker.udim_tile_status"
    bl_label = "UDIM Tile Status"
    bl_options = {"INTERNAL"}

    tile_number: bpy.props.IntProperty(name="Tile", default=0, options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        number = int(getattr(properties, "tile_number", 0) or 0)
        state = _UDIM_ROW_STATES.get(number)
        message = str(getattr(state, "message", "") or "").strip() if state is not None else ""
        if message:
            return message
        if state is not None and getattr(state, "baked", False):
            return "This tile was included in the last bake"
        if state is not None and getattr(state, "is_error", False):
            return "This tile has a problem"
        if state is not None and getattr(state, "is_warning", False):
            return "This tile has a warning"
        return "UDIM tile status"

    def execute(self, _context):
        return {"CANCELLED"}


class MASTER_BAKER_OT_map_material_status(bpy.types.Operator):
    """Hover target for a map row's material-source icon. Clicking does nothing."""

    bl_idname = "master_baker.map_material_status"
    bl_label = "Material Status"
    bl_options = {"INTERNAL"}

    message: bpy.props.StringProperty(name="Message", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        return str(getattr(properties, "message", "") or "").strip() or "Material source status"

    def execute(self, _context):
        return {"CANCELLED"}


def _select_map_stack_row(context, map_index: int) -> None:
    """Make one stack row the active map, so its settings draw underneath."""
    scene = getattr(context, "scene", None)
    project = properties.get_active_project(scene) if scene is not None else None
    if project is None or not hasattr(project, "active_map_index"):
        return
    count = len(getattr(project, "maps", []) or [])
    if count <= 0:
        return
    project.active_map_index = max(0, min(int(map_index), count - 1))


class MASTER_BAKER_OT_map_row_info(bpy.types.Operator):
    """Hover target for a map-stack row name. Clicking selects that map.

    The row name used to be a label, and labels cannot carry a tooltip. A label
    click falls through to the list and selects the row; this button has to do
    that selection itself.
    """

    bl_idname = "master_baker.map_row_info"
    bl_label = "Map"
    bl_options = {"INTERNAL"}

    map_type: bpy.props.StringProperty(name="Map Type", default="", options={"HIDDEN"})
    output_suffix: bpy.props.StringProperty(name="Output Suffix", default="", options={"HIDDEN"})
    map_index: bpy.props.IntProperty(name="Map Index", default=0, options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        text = _map_type_hover_text(getattr(properties, "map_type", ""))
        suffix = str(getattr(properties, "output_suffix", "") or "").strip()
        if suffix:
            return f"{text}. Writes {suffix}"
        return text

    def execute(self, context):
        _select_map_stack_row(context, int(self.map_index))
        return {"FINISHED"}


def _backend_prewarm_status_icon(_prefs):
    if high_mesh_cache.is_mesh_prewarm_pending() or runtime.is_prepare_in_flight():
        elapsed = runtime.prewarm_elapsed_str()
        label = _warming_up_label(elapsed)
        return ("FILE_REFRESH", label)
    if runtime.is_bake_worker_warm():
        return ("CHECKMARK", "Scene cache ready")
    return ("RADIOBUT_OFF", "Backend not ready")


class MASTER_BAKER_OT_backend_status(bpy.types.Operator):
    """Hover target for the prewarm status icon that sits next to Bake.

    ``UILayout.label()`` cannot carry a tooltip, so the icon's status text was
    computed and then thrown away: users saw a dot or a spinner with nothing
    explaining it. Drawing the same icon as a flat (``emboss=False``) operator
    button keeps the look and gives it a hover tooltip that reads live state.
    Clicking is deliberately a no-op.
    """

    bl_idname = "master_baker.backend_status"
    bl_label = "Backend Status"
    # No UNDO: this changes nothing. INTERNAL keeps it out of operator search.
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, _context, _properties):
        try:
            _icon, tooltip = _backend_prewarm_status_icon(preferences.get_preferences())
        except Exception:
            return "Backend status"
        return str(tooltip or "Backend status")

    def execute(self, _context):
        return {"CANCELLED"}


def _draw_bake_panel_header(layout, settings, project) -> tuple[object | None, bool, bool]:

    active_bake, bake_running, project_bake_running = _bake_state(project)
    header_box = layout.box()

    # Actions Row. "Bake Changed Maps" moved up next to the main Bake button
    # (tester feedback: down here it read as a toggle, not a bake action).
    # Backend eject/restart is a developer tool: it kills the resident worker and
    # prewarms fresh, which only ever helps when debugging the backend. Artists got
    # an unlabelled button directly above Bake that threw away their warm scene, so
    # the whole row is built only in developer mode (no empty row is drawn).
    if preferences.developer_mode_enabled():
        action_row = header_box.row(align=True)
        action_row.scale_y = 1.2
        restart_row = action_row.row(align=True)
        restart_row.enabled = not bake_running
        restart_row.operator("master_baker.restart_backend", text="", icon="RECOVER_LAST")
    # Dirty-tracking and Live Normal are parked until bake speed can sustain
    # the live workflow — restore alongside Live Bake.
    # live_bake_active = _live_bake_is_active(settings, project)
    # group = _active_group(project)
    # dirty_row = action_row.row(align=True)
    # dirty_row.enabled = not bake_running and live_bake_active
    # dirty_row.operator("master_baker.mark_all_dirty", text="Mark Dirty", icon="SNAP_MIDPOINT")
    # clear_dirty_row = dirty_row.row(align=True)
    # clear_dirty_row.enabled = live_bake_active and dirty_tracker.is_session_active() and bool(dirty_tracker.get_pending_dirty())
    # clear_dirty_row.operator("master_baker.clear_dirty", text="Clear Dirty", icon="X")
    # _draw_live_normal_preview_action(action_row, settings, project, group, bake_running=bake_running)

    if bake_running:
        hint_row = header_box.row(align=True)
        hint_row.label(text="Some actions are disabled while a bake is running.", icon="INFO")
    # elif not live_bake_active:
    #     hint_row = header_box.row(align=True)
    #     hint_row.label(text="Enable Live Bake to use Mark Dirty.", icon="INFO")

    _draw_bake_readiness(header_box, project)

    # The N-panel shows this beside the header gear. The properties Bake panel
    # has no gear, so the time stays here.
    last_bake_text = _last_bake_label(project, project_bake_running=project_bake_running)
    if last_bake_text:
        last_row = header_box.row(align=True)
        last_row.alignment = "RIGHT"
        last_row.label(text=last_bake_text, icon="TIME")
    _draw_support_bundle_button(header_box, project)
    return active_bake, bake_running, project_bake_running


def _draw_hierarchy_context_section(layout, context, settings, project):
    """Mesh lists for the active bake group, always open in the Meshes menu."""
    if project is None or not getattr(project, "groups", None):
        return
    group = _active_group(project)
    _draw_hierarchy_context_panel(layout, context, settings, project, group)


def _draw_hierarchy_context_panel(layout, context, settings, project, group):
    """Context panel rendered directly below the hierarchy tree.

    Only which meshes are in the active bake group. Texture sets open from the
    set name in the header. Bake group settings open from the gear beside the
    group dropdown.
    """
    del context, settings
    if project is None or not project.groups or group is None:
        return
    _draw_bake_group_meshes(layout, project, group)


def _draw_export_panel_content(layout, context, settings, project):
    if project is None:
        layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
        return
    _draw_sidebar_global_actions(layout, settings, project, _active_group(project))
    layout.separator()
    _draw_bake_panel_header(layout, settings, project)



def _sidebar_skip_sections(project):
    # Material projects have no cage/projection concept: hide the Cage section.
    if getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL:
        return {constants.SIDEBAR_CAGE}
    return set()


def _section_tabs_ready(project) -> bool:
    """Tabs replace the always-visible tree once a real project has meshes.

    Unit-test stand-ins are plain namespaces, not PropertyGroups, so they keep
    the pre-tab draw path.
    """
    if project is None:
        return False
    groups = getattr(project, "groups", None)
    if not groups:
        return False
    first = groups[0]
    if not hasattr(first, "bl_rna"):
        return False
    return _project_has_meshes(project)


def _draw_sidebar_section_content(layout, context, settings, project, group, section_id):
    if section_id == constants.SIDEBAR_MESHES:
        _draw_hierarchy_panel(
            layout,
            context,
            settings,
            project,
            include_compact_header=False,
            include_project_header=False,
        )
        _draw_hierarchy_context_section(layout, context, settings, project)
    elif section_id == constants.SIDEBAR_MAPS:
        _draw_sidebar_maps_section(layout, context, settings, project, group)
    elif section_id == constants.SIDEBAR_OUTPUT:
        _draw_sidebar_output_section(layout, context, settings, project, group)
    elif section_id == constants.SIDEBAR_PREVIEW:
        _draw_sidebar_preview_section(layout, context, settings, project, group)
    else:
        _draw_sidebar_cage_section(layout, context, settings, project, group)


def _draw_active_sidebar_sections(layout, context, settings, project, group, skip_sections=()):
    _draw_sidebar_dev_ab_compare(layout, settings)
    content_col = layout.column()
    visible_sections = tuple(
        section_id
        for section_id in sidebar_state.ordered_visible_sections(settings)
        if section_id not in skip_sections
    )
    # Only when several sections are shift-selected does a dimmed heading mark
    # where one section ends and the next begins.
    multiple_sections = len(visible_sections) > 1
    for index, section_id in enumerate(visible_sections):
        if multiple_sections:
            section_label, fallback_icon, custom_icon = _sidebar_nav_meta(section_id)
            icon_value = sidebar_icons.get_icon_value(custom_icon)
            heading = content_col.row(align=True)
            heading.enabled = False
            if icon_value:
                heading.label(text=section_label, icon_value=icon_value)
            else:
                heading.label(text=section_label, icon=fallback_icon)
        _draw_sidebar_section_content(content_col, context, settings, project, group, section_id)
        if index < len(visible_sections) - 1:
            content_col.separator()


def _draw_projects(layout, settings, project):
    if project is None:
        quick_start = layout.box()
        quick_start.label(text="Quick Start")
        _draw_undo_remove_project(quick_start)
        # Mirror the two pre-project routes shown in the N-panel hierarchy.
        quick_start.operator("master_baker.add_project", text="High to Low Bake", **_icon_kwargs("add", "ADD"))
        quick_start.operator("master_baker.bake_selected_materials", text="Bake Selected Materials", icon="MATERIAL")
    else:
        _draw_undo_remove_project(layout)
        layout.operator("master_baker.bake_selected_materials", text="Bake Selected Materials", icon="MATERIAL")

    row = layout.row()
    row.template_list(
        "MASTER_BAKER_UL_projects",
        "",
        settings,
        "projects",
        settings,
        "active_project_index",
        rows=2,
    )
    column = row.column(align=True)
    column.operator("master_baker.add_project", text="", **_icon_kwargs("add", "ADD"))
    column.operator("master_baker.duplicate_project", text="", icon="DUPLICATE")
    column.operator("master_baker.remove_project", text="", icon="TRASH")

    if project is None:
        return

    layout.prop(project, "ui_name")
    collections_row = layout.row()
    collections_row.enabled = not _bake_state(project)[2]
    collections_row.prop(project, "collection_mode")
    layout.label(text=f"State: {_project_state_label(project, settings)}")


def _draw_runtime_status(layout, project, *, title="Job Status"):
    if title:
        status_box = layout.box()
        status_box.label(text=title)
    else:
        status_box = layout
    if project is None:
        status_box.label(text="No active project.", icon="INFO")
        return

    backend_failed = _project_state_label(project) == constants.STATUS_FAILED
    status_box.label(text=f"State: {_project_state_label(project)}")
    if backend_failed:
        status_box.label(text="Bake failed", icon="ERROR")

    cache_state = getattr(project, "last_bake_cache_state", "") or ""
    if cache_state:
        cache_label, cache_icon = runtime.bake_cache_state_display(cache_state)
        if cache_label:
            status_box.label(text=f"Cache: {cache_label}", icon=cache_icon)

    status_box.label(text=f"Job: {project.last_job_id or 'None'}")
    _active_bake, _bake_running, _project_bake_running = _bake_state(project)
    if project.last_active_group:
        map_label = naming.map_label(project.last_active_map) if project.last_active_map else "Idle"
        status_box.label(text=f"Active Bake Group: {project.last_active_group} / {map_label}")
    if project.last_workspace_path:
        status_box.label(text=f"Workspace: {project.last_workspace_path}")
    if project.last_output_dir:
        status_box.label(text=f"Outputs: {project.last_output_dir}")
    if project.last_error_count:
        if not backend_failed:
            status_box.label(text=f"Errors: {project.last_error_count}", icon="ERROR")
        if project.last_error_summary:
            status_box.label(text=project.last_error_summary, icon="ERROR")
    if project.last_warning_count:
        status_box.label(text=f"Warnings: {project.last_warning_count}", icon="INFO")
        if project.last_warning_summary:
            status_box.label(text=project.last_warning_summary, icon="INFO")
    if project.latest_outputs:
        status_box.label(text=f"Tracked Outputs: {_unique_output_count(project)}")
        first_output = project.latest_outputs[0]
        status_box.label(text=f"First: {first_output.display_name or first_output.file_path}")
    if project.last_workspace_path or (runtime.active_bake_snapshot() is not None):
        row = status_box.row(align=True)
        row.operator("master_baker.open_backend_log", text="Log", icon="TEXT")
        row.operator("master_baker.open_gpu_diagnostics", text="GPU Log", icon="CONSOLE")
        if backend_failed:
            row.operator("master_baker.copy_failure_summary", text="Copy Failure", icon="COPYDOWN")
            if project.last_output_dir:
                row.operator("master_baker.open_output_folder", text="Outputs", icon_value=sidebar_icons.get_icon_value("open_folder"))


def _draw_group_focus(layout, project, group):
    focus_box = layout.box()
    focus_box.label(text="Active Bake Group")
    if group is None:
        focus_box.label(text="Create a bake group or assign selected meshes first.", icon="INFO")
        _draw_create_group_actions(focus_box)
        return

    summary = properties.summarize_group_roles(group)
    focus_box.prop(group, "ui_name")
    _ts_row = focus_box.row(align=True)
    _ts_row.label(text="Texture Set")
    _draw_texture_set_menu_button(_ts_row, group)
    group_collection = getattr(properties.group_collections_state(group), "group_collection", None)
    if group_collection is not None:
        try:
            focus_box.label(text=f"Collection: {group_collection.name}", icon="OUTLINER_COLLECTION")
        except ReferenceError:
            pass
    row = focus_box.row(align=True)
    if getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL:
        # Material projects present Objects, not Low/High roles, and have no cage mode.
        row.label(text=f"Objects: {summary['low_count']}")
    else:
        row.label(text=f"Low: {summary['low_count']}")
        row.label(text=f"High: {summary['high_count']}")
        _cage_mode_labels = {constants.CAGE_MODE_CUSTOM: "Custom", constants.CAGE_MODE_AUTOMATIC: "Automatic", constants.CAGE_MODE_DISTANCE: "Distance"}
        row.label(text=_cage_mode_labels.get(summary["cage_mode"], summary["cage_mode"]))



def _draw_map_stack_editor(layout, project):
    stack_box = layout.box()
    # Locked while this project bakes — same rationale as the output settings box.
    _active_bake, _bake_running, project_bake_running = _bake_state(project)
    stack_box.enabled = not project_bake_running
    header_row = stack_box.row(align=True)
    header_row.label(text="Map Stack")
    # Renderer and device live in the compact header above the section tabs.
    header_row.operator("master_baker.insert_material_capture", text="", icon="NODE_MATERIAL")
    header_row.operator("master_baker.restore_detected_outputs", text="", icon="LOOP_BACK")
    # Material projects can re-detect newly meaningful channels without touching existing rows.
    if getattr(project, "workflow", "") == constants.WORKFLOW_MATERIAL:
        header_row.operator("master_baker.rescan_materials", text="", icon="FILE_REFRESH")
    if hasattr(header_row, "popover"):
        header_row.popover("MASTER_BAKER_PT_configure_maps", text="", icon="ADD")
    # Material Profile is not drawn while "Extended Principled" is a no-op:
    # material_graph.extract_material() takes the profile and discards it
    # ("coat/sheen land with Phase 4/extended UI"), and its only consumer is the
    # Material Capture sync, so in every other project the dropdown promised
    # "coat, sheen, subsurface" and did nothing at all. The property is untouched --
    # restore this row with the feature. See MATERIAL_BAKE_QA_2026_08_19_PASS2, G10.
    # Fixed viewport. A taller stack scrolls inside the list (mouse wheel while
    # the pointer is over it) instead of stretching the rest of the panel.
    # `rows` is also the minimum, so a short stack still reserves this height.
    stack_box.template_list(
        "MASTER_BAKER_UL_maps",
        "",
        project,
        "maps",
        project,
        "active_map_index",
        rows=_MAP_STACK_VISIBLE_ROWS,
        maxrows=_MAP_STACK_VISIBLE_ROWS,
    )
    # Directly under the stack a removed row came out of.
    _draw_undo_removed_item(stack_box, runtime.STASH_KIND_MAP)


    map_item = _active_map(project)
    if map_item is None:
        info_box = layout.box()
        info_box.label(text="No output maps are configured.", icon="INFO")
        return

    layout.separator()
    draw_active_map_settings(layout, project, map_item)


def _draw_outputs(layout, context, project):
    if not project.latest_outputs:
        box = layout.box()
        box.label(text="No tracked outputs yet.")
        box.label(text="Bake or refresh outputs to inspect results.")
        return

    settings = getattr(context.scene, "fyr_baker_settings", None)
    _active_bake, _bake_running, project_bake_running = _bake_state(project)
    active_group = properties.peek_active_group(project)
    active_group_name = str(getattr(active_group, "name", "") or "")
    session_state = _preview_session_state(settings)
    stored_pbr_group = str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "")
    preview_pbr_active = bool(
        getattr(session_state, "preview_pbr_on_low_active", False)
        and str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
        and (not stored_pbr_group or stored_pbr_group == active_group_name)
    )

    row = layout.row()
    row.template_list(
        "MASTER_BAKER_UL_outputs",
        "render",
        project,
        "latest_outputs",
        project,
        "active_output_index",
        rows=5,
    )
    col = row.column(align=True)
    col.operator("master_baker.load_output_image", text="", icon="IMAGE_DATA")
    col.operator("master_baker.refresh_outputs", text="", icon="FILE_REFRESH")
    col.operator("master_baker.open_output_folder", text="", icon_value=sidebar_icons.get_icon_value("open_folder"))

    action_row = layout.row(align=True)
    action_row.operator("master_baker.previous_output", text="", icon="TRIA_LEFT")
    action_row.operator("master_baker.next_output", text="", icon="TRIA_RIGHT")
    action_row.operator("master_baker.load_output_image", text="Load Active Output", icon="CHECKMARK")
    pbr_row = action_row.row(align=True)
    pbr_row.alert = preview_pbr_active
    pbr_row.operator("master_baker.preview_pbr_output", text="Material Preview", icon="SHADING_TEXTURE", depress=preview_pbr_active)
    reproject_row = layout.row(align=True)
    reproject_row.enabled = not project_bake_running
    if bake_backends.control_supported(bake_backends.CONTROL_SCOPE_PROJECT, "live_reproject"):
        reproject_row.prop(project, "live_reproject", text="Live Reproject", toggle=True, icon="UV_SYNC_SELECT")
        texture_reprojection.draw_status_icon(reproject_row, project)
    reproject_row.operator("master_baker.restore_last_bake_outputs", text="Restore Textures", icon="RECOVER_LAST")


def _draw_output_context(layout, context, project, *, title="Output Context"):
    settings = context.scene.fyr_baker_settings
    context_box = layout.box()
    context_box.label(text=title)
    if not project.latest_outputs:
        context_box.label(text="No tracked outputs yet.", icon="INFO")
        return

    active_index = properties.resolve_latest_output_index(project)
    if active_index is None:
        context_box.label(text="Active Output: None", icon="INFO")
    else:
        context_box.label(text=f"Active Output: {properties.summarize_latest_output(project, active_index)}")
    context_box.label(text=properties.summarize_compare_state(project, settings))
    context_box.label(text=f"Preview Map: {naming.map_label(settings.preview_map_type)}")
    context_box.label(text=f"Tracked Outputs: {_unique_output_count(project)}")



def _draw_panel_header_label(layout, title, icon_key, *, fallback="NONE"):
    """Draw an icon + title in a panel header so the Render-tab panels read the same
    way as the N-panel section boxes (icon on the left of the label)."""
    icon_value = sidebar_icons.get_icon_value(icon_key) if icon_key else 0
    if icon_value:
        layout.label(text=title, icon_value=icon_value)
    else:
        layout.label(text=title, icon=fallback)


# The Render-Properties panels intentionally mirror the N-panel: a "Fyr Baker" root
# with Meshes / Cage / Maps / Output / Preview / Bake sub-panels drawn from the
# exact same helpers the sidebar uses, so the two surfaces can never drift apart.
class MASTER_BAKER_PT_render_root(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Fyr Baker", "fyr_baker", fallback="RENDER_STILL")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        _draw_projects(layout, settings, project)


class MASTER_BAKER_PT_render_meshes(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_meshes"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Meshes", "bake_group", fallback="OUTLINER_OB_MESH")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        # Same hierarchy tree + focused-item context the N-panel puts at its top.
        _draw_hierarchy_panel(layout, context, settings, project)
        _draw_hierarchy_context_panel(layout, context, settings, project, _active_group(project))


class MASTER_BAKER_PT_render_cage(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_cage"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        # Material (self-bake) projects have no cage/projection concept: hide this panel.
        project = _active_project(context.scene)
        return project is None or getattr(project, "workflow", "") != constants.WORKFLOW_MATERIAL

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Cage", "cage", fallback="MOD_SHRINKWRAP")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        _draw_sidebar_cage_section(layout, context, settings, project, _active_group(project))


class MASTER_BAKER_PT_render_maps(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_maps"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Maps", "maps", fallback="TEXTURE_DATA")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        _draw_sidebar_maps_section(layout, context, settings, project, _active_group(project))


class MASTER_BAKER_PT_render_output(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_output"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Output", "output", fallback="FILE_FOLDER")

    def draw_header_preset(self, _context):
        self.layout.menu("MASTER_BAKER_MT_project_presets", text="", icon="PRESET")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        _draw_sidebar_output_section(layout, context, settings, project, _active_group(project))


class MASTER_BAKER_PT_render_preview(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_preview"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Preview", "preview", fallback="MATERIAL")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        _draw_sidebar_preview_section(layout, context, settings, project, _active_group(project))


class MASTER_BAKER_PT_render_bake(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_render_bake"
    bl_parent_id = "MASTER_BAKER_PT_render_root"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw_header(self, _context):
        _draw_panel_header_label(self.layout, "Bake", "bake", fallback="RENDER_STILL")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fyr_baker_settings
        project = _active_project(context.scene)
        _draw_export_panel_content(layout, context, settings, project)


def _draw_quick_settings(layout, context, project):
    """Baker-behavior popover (the gear in the panel header).

    Project output settings (size, format, folder, samples, denoise) are NOT
    drawn here — they all live in the Output section and duplicating them
    made this popover read as a second, competing settings panel. What earns a
    slot instead is the addon-level behavior that is otherwise buried in
    Addon Preferences: renderer/device, bake-worker warmup, and what the
    viewport does while a bake runs.
    """
    del context  # addon-level settings; the bundle still needs the active project

    _draw_renderer_quick_controls(layout)
    layout.separator()
    _draw_support_bundle_button(layout, project)

    prefs = preferences.get_preferences()
    if prefs is not None:
        layout.separator()
        worker_col = layout.column(align=True)
        worker_col.label(text="Bake Worker", icon="GHOST_ENABLED")
        worker_col.prop(prefs, "backend_prewarm_mode", text="Startup")
        worker_col.prop(prefs, "backend_prewarm_prepare_meshes")

        during_col = layout.column(align=True)
        during_col.label(text="During Bake", icon="TIME")
        during_col.prop(prefs, "bake_low_impact_viewport", text="Quiet Viewport")
        live_row = during_col.row(align=True)
        live_row.enabled = bool(getattr(prefs, "bake_low_impact_viewport", True))
        live_row.prop(prefs, "bake_keep_viewport_live", text="Keep Viewport Live")
        during_col.prop(prefs, "show_statusbar_progress", text="Status Bar Progress")

        placement_col = layout.column(align=True)
        placement_col.label(text="Viewport Controls", icon="WINDOW")
        placement_col.prop(prefs, "viewport_controls_placement", text="")

    layout.separator()
    docs_op = layout.operator("wm.url_open", text="Open Documentation", icon="HELP")
    docs_op.url = constants.DOCUMENTATION_URL
    prefs_op = layout.operator("preferences.addon_show", text="Addon Preferences", icon="PREFERENCES")
    prefs_op.module = __package__


class MASTER_BAKER_PT_texture_set_settings(bpy.types.Panel):
    """Popover opened from the texture set name in the header."""

    bl_label = "Texture Set"
    bl_idname = "MASTER_BAKER_PT_texture_set_settings"
    bl_description = "Texture sets, the bake groups in each one, and how that set is named"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_options = {"INSTANCED"}
    bl_ui_units_x = 18

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        project = _active_project(context.scene)
        if project is None:
            layout.label(text="No bake project", icon="INFO")
            return
        active_set = properties.get_active_texture_set(project)
        layout.operator_context = "INVOKE_DEFAULT"
        _draw_texture_set_settings(layout, context, project, active_set)


class MASTER_BAKER_PT_bake_group_settings(bpy.types.Panel):
    """Popover behind the gear beside the bake group dropdown."""

    bl_label = "Bake Group Settings"
    bl_idname = "MASTER_BAKER_PT_bake_group_settings"
    bl_description = "Settings of the bake group chosen in the dropdown"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_options = {"INSTANCED"}
    bl_ui_units_x = 16

    def draw(self, context):
        project = _active_project(context.scene)
        if project is None:
            self.layout.label(text="No bake project", icon="INFO")
            return
        _draw_bake_group_settings(self.layout, project, _active_group(project))


class MASTER_BAKER_PT_quick_settings(bpy.types.Panel):
    bl_label = "Quick Settings"
    bl_idname = "MASTER_BAKER_PT_quick_settings"
    bl_description = "Renderer, bake worker, and what the viewport does while a bake runs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_options = {"INSTANCED"}

    def draw(self, context):
        project = _active_project(context.scene)
        _draw_quick_settings(self.layout, context, project)


@functools.lru_cache(maxsize=1)
def _sidebar_title() -> str:
    # bl_info is the version the bump script edits; resolved once per addon load.
    from . import system_diagnostics

    version = system_diagnostics.addon_version()
    return f"Fyr Baker - {version}" if version else "Fyr Baker"


class MASTER_BAKER_PT_view3d_hierarchy(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_view3d_hierarchy"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_order = 0

    def draw_header(self, context):
        del context
        layout = self.layout
        icon_value = sidebar_icons.get_icon_value("fyr_baker")
        if icon_value:
            layout.label(text="", icon_value=icon_value)
        else:
            layout.label(text="", icon="RENDER_STILL")
        layout.label(text=_sidebar_title())

    def draw_header_preset(self, context):
        # Preset slot is the header's right side. Stretching the header with
        # HEADER_LAYOUT_EXPAND shifted the whole panel body right, under the tabs.
        layout = self.layout
        project = _active_project(context.scene)
        _active_bake, bake_running, project_bake_running = (
            _bake_state(project) if project is not None else (None, False, False)
        )
        if project is not None and _project_has_meshes(project):
            bake = layout.row(align=True)
            if project_bake_running:
                bake.alert = True
                bake.operator("master_baker.cancel_bake", text="Stop", **_icon_kwargs("bake_stop", "CANCEL"))
            else:
                bake.enabled = not bake_running and _project_ready_to_bake(project)
                bake.operator("master_baker.bake_project", text="Bake", **_icon_kwargs("bake", "RENDER_STILL"))
        last_bake = _last_bake_label(project, project_bake_running=project_bake_running)
        if last_bake:
            layout.label(text=last_bake, icon="TIME")
        layout.popover("MASTER_BAKER_PT_quick_settings", text="", icon="PREFERENCES")

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False
        scene = context.scene
        settings = scene.fyr_baker_settings
        project = _active_project(scene)
        if not _section_tabs_ready(project):
            _draw_hierarchy_panel(layout, context, settings, project)
            _draw_hierarchy_context_section(layout, context, settings, project)
            return
        _draw_project_banner(layout, context, settings, project)
        if getattr(project, "groups", None):
            _draw_compact_bake_header(layout, project)
        skip_sections = _sidebar_skip_sections(project)
        _draw_sidebar_nav(layout, settings, skip_sections=skip_sections)
        _draw_active_sidebar_sections(
            layout,
            context,
            settings,
            project,
            _active_group(project),
            skip_sections=skip_sections,
        )
        layout.separator(factor=2.4)
        _active_bake, _bake_running, project_bake_running = _bake_state(project)
        _draw_export_send_row(layout, project, project_bake_running=project_bake_running)
        preview_line = layout.row()
        preview_line.enabled = bool(getattr(project, "latest_outputs", None))
        preview_line.label(text="Map Preview")
        preview_row = preview_line.row(align=True)
        preview_row.prop(settings, "preview_picker", text="")
        preview_row.operator("master_baker.preview_pbr_output", text="", icon="SHADING_TEXTURE", depress=_pbr_preview_shown(settings, project))


class MASTER_BAKER_PT_view3d_sidebar(bpy.types.Panel):
    bl_label = "Settings"
    bl_idname = "MASTER_BAKER_PT_view3d_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_order = 10

    @classmethod
    def poll(cls, context):
        # Section tabs live in the hierarchy panel now (Meshes, Cage, Maps, Output, Preview).
        del context
        return False

    def draw(self, context):
        del context


class MASTER_BAKER_PT_view3d_bake(bpy.types.Panel):
    bl_label = "Bake"
    bl_idname = "MASTER_BAKER_PT_view3d_bake"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME
    bl_order = 20

    @classmethod
    def poll(cls, context):
        # Bake, readiness, and export now live in the hierarchy panel, on every section.
        del context
        return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.fyr_baker_settings
        project = _active_project(scene)
        _draw_export_panel_content(layout, context, settings, project)


class MASTER_BAKER_PT_image_editor(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MASTER_BAKER_PT_image_editor"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME

    def draw_header(self, context):
        row = self.layout.row(align=True)
        row.popover("MASTER_BAKER_PT_quick_settings", text="", icon="PREFERENCES")
        row.separator(factor=0.5)
        row.label(text=_sidebar_title())

    def draw(self, context):
        layout = self.layout
        project = _active_project(context.scene)
        if project is None:
            layout.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
            return
        draw_image_editor_controls(layout, context, project)
        settings = context.scene.fyr_baker_settings
        editor_state = properties.image_editor_state(settings)
        job_box = _begin_collapsible_section(layout, editor_state, "job_status_expanded", "Current Job", icon="INFO")
        if job_box is not None:
            _draw_runtime_status(job_box, project, title="")


CLASSES = (
    MASTER_BAKER_OT_export_settings,
    MASTER_BAKER_MT_resolution_presets,
    MASTER_BAKER_MT_project_presets,
    MASTER_BAKER_MT_project_prepare,
    MASTER_BAKER_MT_bake_project,
    MASTER_BAKER_MT_uv_snapshot_actions,
    MASTER_BAKER_MT_map_stack_presets,
    MASTER_BAKER_MT_texture_set_picker,
    MASTER_BAKER_MT_assign_texture_set,
    MASTER_BAKER_MT_texture_set_row,
    MASTER_BAKER_MT_hierarchy_texture_set,
    MASTER_BAKER_MT_hierarchy_bake_group,
    MASTER_BAKER_MT_group_uv_layer_picker,
    MASTER_BAKER_MT_preview_map_dropdown,
    MASTER_BAKER_MT_baked_maps_dropdown,
    MASTER_BAKER_PT_configure_maps,
    MASTER_BAKER_PT_cage_quick_settings,
    MASTER_BAKER_PT_cage_coverage_settings,
    MASTER_BAKER_PT_cage_viewport_overlays,
    MASTER_BAKER_PT_skew_needle_settings,
    MASTER_BAKER_UL_projects,

    MASTER_BAKER_UL_texture_sets,
    MASTER_BAKER_UL_texture_set_members,
    MASTER_BAKER_UL_texture_set_nonmembers,
    MASTER_BAKER_UL_udim_tiles,
    MASTER_BAKER_OT_set_ui_enum,
    MASTER_BAKER_OT_udim_tile_status,
    MASTER_BAKER_OT_map_material_status,
    MASTER_BAKER_OT_map_row_info,
    MASTER_BAKER_OT_backend_status,
    MASTER_BAKER_OT_add_udim_tile,
    MASTER_BAKER_OT_remove_udim_tile,
    MASTER_BAKER_OT_detect_udim_tiles,
    MASTER_BAKER_OT_toggle_udim_editor,
    MASTER_BAKER_UL_groups,
    MASTER_BAKER_UL_hierarchy,
    MASTER_BAKER_MT_map_item_actions,
    MASTER_BAKER_OT_duplicate_map_warning,
    MASTER_BAKER_OT_show_bake_warnings,
    MASTER_BAKER_UL_maps,
    MASTER_BAKER_UL_object_slots,
    MASTER_BAKER_UL_outputs,
    MASTER_BAKER_PT_render_root,
    MASTER_BAKER_PT_render_meshes,
    MASTER_BAKER_PT_render_cage,
    MASTER_BAKER_PT_render_maps,
    MASTER_BAKER_PT_render_output,
    MASTER_BAKER_PT_render_preview,
    MASTER_BAKER_PT_render_bake,
    MASTER_BAKER_PT_quick_settings,
    MASTER_BAKER_PT_texture_set_settings,
    MASTER_BAKER_PT_bake_group_settings,
    MASTER_BAKER_PT_view3d_hierarchy,
    MASTER_BAKER_PT_view3d_sidebar,
    MASTER_BAKER_PT_view3d_bake,
    MASTER_BAKER_PT_image_editor,
)


def _project_role_meshes_all_visible(project, role_attr: str) -> bool:
    """True when the project has meshes for *role_attr* and every one is visible.

    Drives the header LP/HP button depress state so it reflects the actual viewport
    visibility of the low/high meshes, not a stored toggle that can drift out of sync.
    """
    seen = []
    for group in getattr(project, "groups", []):
        role_state = properties.group_role_assignments_state(group)
        for slot in getattr(role_state, role_attr, []):
            obj = getattr(slot, "object_ref", None)
            if obj is None or any(existing is obj for existing in seen):
                continue
            seen.append(obj)
    if not seen:
        return False
    for obj in seen:
        try:
            if obj.hide_get():
                return False
        except (ReferenceError, RuntimeError):
            return False
    return True


def _viewport_controls_placement() -> str:
    """Where the overlay-style controls live: HEADER, OVERLAYS, BOTH, or NPANEL.

    Covers only the overlay-flavored subset (cage overlay, LP/HP visibility,
    map preview); bake actions and the Send menu ignore it. Stored in the addon
    preferences so it survives per user, not per file. Read with a fallback so
    drawing keeps working on preference sets saved before the option existed."""
    prefs = preferences.get_preferences()
    return str(getattr(prefs, "viewport_controls_placement", "HEADER") or "HEADER")


def draw_master_baker_header_controls(layout, settings, project):
    """Compact control cluster for the right side of the 3D viewport header.

    Tester feedback: these are not tool settings, so they no longer live in
    (or patch) the tool header. Appended to VIEW3D_HT_header instead, which
    places them next to Blender's own overlay and shading widgets."""
    row = layout.row(align=True)

    _active_bake, bake_running, project_bake_running = _bake_state(project)

    if bake_running:
        if project_bake_running:
            cancel_row = row.row(align=True)
            cancel_row.alert = True
            cancel_row.operator("master_baker.cancel_bake", text="", **_icon_kwargs("bake_stop", "CANCEL"))
        else:
            row.label(text="Baking...", icon="INFO")
        return

    # Folded: icon + name so the collapsed cluster stays identifiable.
    # Expanded: icon only — the controls next to it speak for themselves.
    # Icon and text are separate widgets on purpose: a single unembossed prop
    # with a custom icon_value and text intermittently drops the icon width in
    # menu-row layouts, drawing the icon on top of the label.
    if settings.header_menu_fold:
        row.prop(
            settings,
            "header_menu_fold",
            text="",
            emboss=False,
            **_icon_kwargs("fyr_baker", "RENDER_STILL"),
        )
        row.prop(
            settings,
            "header_menu_fold",
            text="Fyr Baker",
            emboss=False,
        )
        return

    row.prop(
        settings,
        "header_menu_fold",
        text="",
        emboss=False,
        **_icon_kwargs("fyr_baker", "RENDER_STILL"),
    )

    # The expanded header must expose a real next action before bake controls are
    # available; otherwise expanding it changes only the arrow and looks broken.
    if project is None:
        row.operator("master_baker.add_project", text="Create Bake Project", **_icon_kwargs("add", "ADD"))
        return

    if not _project_has_meshes(project):
        row.operator(
            "master_baker.auto_group_scene_by_name",
            text="Auto-Build Bake Groups",
            icon="SORTALPHA",
        )
        return

    row.operator("master_baker.bake_project", text="Bake", **_icon_kwargs("bake", "RENDER_STILL"))

    # Only the overlay-flavored subset (cage/LP/HP visibility + map preview)
    # obeys the placement preference; the bake action and Send menu are not
    # overlays and stay in the header no matter where that subset lives.
    show_overlay_controls = _viewport_controls_placement() in {"HEADER", "BOTH"}

    # Meshes are guaranteed here (we returned early otherwise); the cage/reference
    # overlays act on them.
    overlay_state = properties.overlay_settings_state(settings)
    if show_overlay_controls and overlay_state:
        is_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
        row.operator("master_baker.toggle_cage_overlay", text="", icon_value=sidebar_icons.get_icon_value("cage_ui"), depress=is_cage_visible)
        # Same per-group flag as the sidebar's Show Cage Coverage button.
        coverage_group = _active_group(project)
        if coverage_group is not None:
            row.prop(
                coverage_group,
                "show_cage_coverage",
                text="",
                toggle=True,
                icon_value=sidebar_icons.get_icon_value("cage_coverage"),
            )
        low_op = row.operator("master_baker.toggle_reference_visibility", text="", icon_value=sidebar_icons.get_icon_value("low_poly"), depress=_project_role_meshes_all_visible(project, "low_meshes"))
        low_op.role = constants.OBJECT_ROLE_LOW
        high_op = row.operator("master_baker.toggle_reference_visibility", text="", icon_value=sidebar_icons.get_icon_value("high_poly"), depress=_project_role_meshes_all_visible(project, "high_meshes"))
        high_op.role = constants.OBJECT_ROLE_HIGH

    # Preview-map dropdown + PBR preview only mean something once maps are baked.
    # Without outputs the dropdown is just an empty "No Maps" button, so hide both.
    # The header stays one Send menu; preferences choose which destinations are in it.
    if getattr(project, "latest_outputs", None):
        if show_overlay_controls:
            row.separator()
            row.prop(settings, "preview_picker", text="")
            row.operator("master_baker.preview_pbr_output", text="", icon="SHADING_TEXTURE", depress=_pbr_preview_shown(settings, project))
        if external_handoff.any_send_to_destination_enabled(preferences.get_preferences(migrate=False)):
            row.separator()
            row.menu("MASTER_BAKER_MT_send_to", text="", icon="EXPORT")


class MASTER_BAKER_MT_send_to(bpy.types.Menu):
    bl_label = "Send To"
    bl_idname = "MASTER_BAKER_MT_send_to"
    bl_description = "Send the bake to an external editor"

    def draw(self, context):
        layout = self.layout
        prefs = preferences.get_preferences(migrate=False)
        drawn = 0

        def section():
            nonlocal drawn
            if drawn:
                layout.separator()
            drawn += 1

        if external_handoff.send_to_destination_enabled(prefs, "painter"):
            section()
            layout.operator("master_baker.send_to_painter", text="Send to Painter", icon_value=sidebar_icons.get_icon_value("send_to_painter"))
            layout.operator("master_baker.update_in_painter", text="Update in Painter", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "toolbag"):
            section()
            layout.operator("master_baker.send_to_toolbag", text="Send to Marmoset", icon_value=sidebar_icons.get_icon_value("send_to_marmoset"))
            layout.operator("master_baker.update_in_toolbag", text="Update in Marmoset", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "photoshop"):
            section()
            layout.operator("master_baker.send_to_photoshop", text="Send to Photoshop", icon="IMAGE_DATA")
        if external_handoff.send_to_destination_enabled(prefs, "designer"):
            section()
            layout.operator("master_baker.send_to_designer", text="Send to Designer", icon="NODETREE")
            layout.operator("master_baker.update_in_designer", text="Update in Designer", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "3dcoat"):
            section()
            layout.operator("master_baker.send_to_3dcoat", text="Send to 3DCoat", icon="SCULPTMODE_HLT")
        if external_handoff.send_to_destination_enabled(prefs, "mari"):
            section()
            layout.operator("master_baker.send_to_mari", text="Send to Mari", icon="MATERIAL")


def master_baker_view3d_header_draw(self, context):
    """Appended to VIEW3D_MT_editor_menus (never replaces a draw, unlike the
    old tool-header patch), which places the cluster directly after the
    View / Select / Add / Object menus. Always drawn — the placement
    preference relocates only the overlay-flavored subset inside it."""
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        return
    project = properties.peek_active_project(scene)
    draw_master_baker_header_controls(self.layout, settings, project)


def master_baker_overlay_panel_draw(self, context):
    """Appended to the Viewport Overlays popover (VIEW3D_PT_overlay).

    Carries the overlay-flavored subset only — LP/HP/cage visibility and the
    baked-map preview — since that is what belongs next to Blender's own
    overlay toggles. Bake actions stay in the header and N-panel."""
    if _viewport_controls_placement() not in {"OVERLAYS", "BOTH"}:
        return
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        return
    project = properties.peek_active_project(scene)
    if project is None or not _project_has_meshes(project):
        return

    layout = self.layout
    layout.separator()
    col = layout.column()
    col.label(text="Fyr Baker")

    overlay_state = properties.overlay_settings_state(settings)
    if overlay_state:
        is_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
        row = col.row(align=True)
        row.operator("master_baker.toggle_cage_overlay", text="Cage", icon_value=sidebar_icons.get_icon_value("cage_ui"), depress=is_cage_visible)
        coverage_group = _active_group(project)
        if coverage_group is not None:
            row.prop(coverage_group, "show_cage_coverage", text="Coverage", toggle=True, icon_value=sidebar_icons.get_icon_value("cage_coverage"))
        low_op = row.operator("master_baker.toggle_reference_visibility", text="Low", icon_value=sidebar_icons.get_icon_value("low_poly"), depress=_project_role_meshes_all_visible(project, "low_meshes"))
        low_op.role = constants.OBJECT_ROLE_LOW
        high_op = row.operator("master_baker.toggle_reference_visibility", text="High", icon_value=sidebar_icons.get_icon_value("high_poly"), depress=_project_role_meshes_all_visible(project, "high_meshes"))
        high_op.role = constants.OBJECT_ROLE_HIGH

    if getattr(project, "latest_outputs", None):
        preview_row = col.row(align=True)
        preview_row.prop(settings, "preview_picker", text="")
        preview_row.operator("master_baker.preview_pbr_output", text="", icon="SHADING_TEXTURE", depress=_pbr_preview_shown(settings, project))


def master_baker_add_menu_draw(self, _context):
    """Appended to VIEW3D_MT_add, the 3D Viewport Add menu (Shift+A)."""
    layout = self.layout
    layout.separator()
    layout.operator(
        "master_baker.add_project",
        text="Create Bake Project",
        **_icon_kwargs("fyr_baker", "RENDER_STILL"),
    )


def register():
    for cls in CLASSES:
        safe_register_class(cls)
    # Defined below the CLASSES tuple, so registered separately.
    safe_register_class(MASTER_BAKER_MT_send_to)

    bpy.types.VIEW3D_MT_editor_menus.append(master_baker_view3d_header_draw)
    bpy.types.VIEW3D_MT_add.append(master_baker_add_menu_draw)
    bpy.types.VIEW3D_PT_overlay.append(master_baker_overlay_panel_draw)

    # The footer progress bar. unregister() has always removed it, but nothing appended
    # it any more, so "Show Bake Progress in Status Bar" (default ON, still drawn in
    # Preferences and in the panel) was a control that did nothing in every session.
    # The draw callback itself reads that preference and returns early when it is off,
    # so appending unconditionally here is what honours the toggle.
    _register_statusbar_progress()


def unregister():
    _unregister_statusbar_progress()
    # Dev reload swaps the whole addon out; nothing memoised about the old scene's
    # outputs should survive into the new one.
    clear_draw_caches()

    for target, draw_fn in (
        (bpy.types.VIEW3D_MT_editor_menus, master_baker_view3d_header_draw),
        (bpy.types.VIEW3D_MT_add, master_baker_add_menu_draw),
        (bpy.types.VIEW3D_PT_overlay, master_baker_overlay_panel_draw),
    ):
        try:
            target.remove(draw_fn)
        except Exception:
            pass

    safe_unregister_class(MASTER_BAKER_MT_send_to)
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
