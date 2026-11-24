from __future__ import annotations

import json

from . import properties


# Solid-mode lighting properties the preview owns while a single-map preview is up.
# A baked map must read as raw data, so Solid shading has to stop lighting it: studio
# light / matcap add specular highlights and shading gradients on top of the texture.
_SOLID_LIGHTING_PROPERTIES = (
    "light",
    "show_specular_highlight",
    "show_cavity",
    "show_shadows",
)

# Values that make Solid shading display the texture flat (unlit).
_UNLIT_SOLID_SHADING = {
    "light": "FLAT",
    "show_specular_highlight": False,
    "show_cavity": False,
    "show_shadows": False,
}

# Everything captured on activation and restored on deactivation, beyond
# ``type`` / ``color_type`` which are handled explicitly.
_MANAGED_SHADING_PROPERTIES = _SOLID_LIGHTING_PROPERTIES + (
    "use_scene_world",
    "use_scene_lights",
    "studiolight_rotate_z",
    "studiolight_intensity",
    "studiolight_background_alpha",
    "studiolight_background_blur",
)


def _default_space_key(space) -> int:
    as_pointer = getattr(space, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(space)


def _values_equal(current, value) -> bool:
    try:
        if isinstance(value, bool):
            return bool(current) == bool(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return abs(float(current) - float(value)) < 1e-6
        return current == value
    except Exception:
        return False


def _set_shading_property(shading, property_name: str, value) -> None:
    """Write a shading property only when it differs.

    Reassigning shading state that is already correct still forces viewport
    rebuilds on heavy scenes, which is what previously caused the Not Responding
    hitch when preview mode touched shading.
    """
    if not hasattr(shading, property_name):
        return
    try:
        if _values_equal(getattr(shading, property_name), value):
            return
        setattr(shading, property_name, value)
    except Exception:
        pass


def _pbr_preview_is_active(settings) -> bool:
    if settings is None:
        return False
    try:
        session_state = properties.preview_session_state(settings)
    except Exception:
        return False
    return bool(getattr(session_state, "preview_pbr_on_low_active", False)) if session_state is not None else False


def _single_map_preview_is_unlit(settings) -> bool:
    """True while a single baked map (or the live normal preview) is on the low.

    The combined PBR preview is a *material* preview and stays lit; an individual
    map is raw data and must be shown flat.
    """
    if settings is None:
        return False
    try:
        session_state = properties.preview_session_state(settings)
    except Exception:
        return False
    if session_state is None:
        return False
    if bool(getattr(session_state, "preview_pbr_on_low_active", False)):
        return False
    return bool(
        getattr(session_state, "preview_on_low_active", False)
        or getattr(session_state, "live_normal_preview_active", False)
    )


def _captured_shading_entries(settings) -> dict:
    if settings is None:
        return {}
    try:
        session_state = properties.preview_session_state(settings)
    except Exception:
        return {}
    raw_state = str(getattr(session_state, "preview_on_low_restore_viewport_state", "") or "").strip()
    if not raw_state:
        return {}
    try:
        entries = json.loads(raw_state)
    except json.JSONDecodeError:
        return {}
    if not isinstance(entries, list):
        return {}
    by_key = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            by_key[int(entry.get("space_key", 0) or 0)] = entry
        except Exception:
            continue
    return by_key


def _safe_set_preview_map_type(settings, map_type) -> None:
    """Set the preview dropdown's map type without crashing.

    ``preview_map_type`` is a dynamic enum limited to *baked* output types, so a
    value that isn't currently baked (empty string, ``MATERIAL``, ``ID``, …)
    raises ``TypeError``. It only drives the dropdown label, so a rejected value
    is safely ignored.
    """
    if settings is None:
        return
    try:
        settings.preview_map_type = map_type
    except (TypeError, ValueError):
        pass


def preview_on_low_project_name(project) -> str:
    return str(getattr(project, "name", "") or "")


def any_preview_on_low_is_active(settings) -> bool:
    if settings is None:
        return False
    session_state = properties.preview_session_state(settings)
    return bool(
        getattr(session_state, "preview_on_low_active", False)
        or getattr(session_state, "preview_pbr_on_low_active", False)
        or getattr(session_state, "live_normal_preview_active", False)
    )


def clear_preview_on_low_state(settings) -> None:
    if settings is None:
        return
    session_state = properties.preview_session_state(settings)
    session_state.preview_on_low_active = False
    session_state.preview_on_low_project_name = ""
    session_state.preview_on_low_group_name = ""
    session_state.preview_on_low_map_uuid = ""
    session_state.preview_on_low_map_type = ""
    session_state.preview_on_low_map_index = -1
    session_state.preview_on_low_output_suffix = ""
    session_state.preview_pbr_on_low_active = False
    session_state.preview_pbr_on_low_project_name = ""
    session_state.preview_pbr_on_low_group_name = ""
    session_state.live_normal_preview_active = False
    session_state.live_normal_preview_scene_name = ""
    session_state.live_normal_preview_project_name = ""
    session_state.live_normal_preview_group_name = ""
    session_state.live_normal_preview_output_path = ""
    session_state.preview_on_low_restore_show_cage_overlay = False
    session_state.preview_on_low_restore_show_error_heatmap = False
    session_state.preview_on_low_restore_show_ray_miss_debug = False
    session_state.preview_on_low_restore_viewport_state = ""
    session_state.preview_on_low_restore_high_visibility = ""
    try:
        from . import preview_ab_compare

        # A/B "High" hides the low meshes and remembers what to unhide. Clearing
        # the compare state without replaying that record left the lows hidden
        # with nothing left to bring them back, so restore first.
        preview_ab_compare.restore_material_ab_compare_visibility(session_state)
        preview_ab_compare.clear_material_ab_compare_state(session_state)
    except Exception:
        pass


def _preview_object_hidden(obj) -> bool:
    try:
        if bool(obj.hide_get()):
            return True
    except Exception:
        pass
    return bool(getattr(obj, "hide_viewport", False))


def reveal_preview_low_meshes(project, session_state, group_name: str = "") -> int:
    """Put the meshes a preview is applied to on screen. Returns how many were shown.

    The preview material goes on the LOW meshes. In a file where the lows are hidden and
    the highs are visible -- how a bake scene is very often left -- the preview used to
    report "Showing PBR preview on N low mesh(es)" while the viewport kept showing the
    high with its own material, so a correct bake looked as if nothing had been baked
    (reported on a ZenBBQ bevel bake, 2026-10-02: Material Preview cannot display a
    Bevel node, so the high looked flat and the bake got the blame).

    Only acts when a target low is hidden; a scene with visible lows is left exactly as
    the artist arranged it. The previous visibility of every low and high it touches is
    recorded once and replayed by `restore_high_meshes_after_preview` when the preview
    ends. *group_name* empty means every group of the project.
    """
    if project is None or session_state is None:
        return 0
    wanted = str(group_name or "")
    lows: list = []
    highs: list = []
    for group in getattr(project, "groups", []) or []:
        if wanted and str(getattr(group, "name", "") or "") != wanted:
            continue
        try:
            role_state = properties.group_role_assignments_state(group)
        except Exception:
            continue
        for slot in getattr(role_state, "low_meshes", []) or []:
            obj = getattr(slot, "object_ref", None)
            if obj is not None and getattr(obj, "type", "") == "MESH" and obj not in lows:
                lows.append(obj)
        try:
            group_highs = list(properties.effective_high_mesh_objects(group) or [])
        except Exception:
            group_highs = []
        for obj in group_highs:
            if obj is not None and obj not in highs:
                highs.append(obj)
    hidden_lows = [obj for obj in lows if _preview_object_hidden(obj)]
    if not hidden_lows:
        return 0
    # A self-bake uses the same object as low and high; it has to stay visible.
    highs = [obj for obj in highs if obj not in lows]
    if not str(getattr(session_state, "preview_on_low_restore_high_visibility", "") or "").strip():
        entries = []
        for obj in lows + highs:
            try:
                hide_get = bool(obj.hide_get())
            except Exception:
                continue
            entries.append(
                {
                    "name": str(getattr(obj, "name", "") or ""),
                    "hide_get": hide_get,
                    "hide_viewport": bool(getattr(obj, "hide_viewport", False)),
                }
            )
        session_state.preview_on_low_restore_high_visibility = json.dumps(entries)
    shown = 0
    for obj in hidden_lows:
        try:
            obj.hide_viewport = False
            obj.hide_set(False)
            shown += 1
        except Exception:
            pass
    for obj in highs:
        try:
            obj.hide_set(True)
        except Exception:
            pass
    return shown


def restore_high_meshes_after_preview(session_state) -> None:
    """Restore high display/visibility if an older preview session mutated them."""
    if session_state is None:
        return
    raw = str(getattr(session_state, "preview_on_low_restore_high_visibility", "") or "").strip()
    session_state.preview_on_low_restore_high_visibility = ""
    if not raw:
        return
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return
    import bpy

    for entry in entries or []:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        display_type = str(entry.get("display_type") or "").strip()
        if display_type:
            try:
                obj.display_type = display_type
            except Exception:
                pass
        if "hide_viewport" in entry:
            try:
                obj.hide_viewport = bool(entry.get("hide_viewport", False))
            except Exception:
                pass
        if "hide_get" in entry:
            try:
                obj.hide_set(bool(entry.get("hide_get", False)))
            except Exception:
                pass


def restore_preview_on_low_overlay_state(settings) -> None:
    if settings is None:
        return
    session_state = properties.preview_session_state(settings)
    overlay_state = properties.overlay_settings_state(settings)
    overlay_state.show_cage_overlay = bool(getattr(session_state, "preview_on_low_restore_show_cage_overlay", False))
    overlay_state.show_error_heatmap = bool(getattr(session_state, "preview_on_low_restore_show_error_heatmap", False))
    overlay_state.show_ray_miss_debug = bool(getattr(session_state, "preview_on_low_restore_show_ray_miss_debug", False))


def apply_runtime_preview_overlay_state(settings) -> None:
    if settings is None:
        return
    overlay_state = properties.overlay_settings_state(settings)
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")


def _shading_entry(space, space_key) -> dict | None:
    shading = getattr(space, "shading", None)
    if shading is None:
        return None
    entry = {
        "space_key": space_key,
        "type": str(getattr(shading, "type", "") or ""),
        "color_type": str(getattr(shading, "color_type", "") or ""),
    }
    for property_name in _MANAGED_SHADING_PROPERTIES:
        if hasattr(shading, property_name):
            try:
                entry[property_name] = getattr(shading, property_name)
            except Exception:
                pass
    return entry


def capture_view3d_shading_state(context, *, iter_view3d_spaces_fn, space_key_fn) -> str:
    entries = []
    for space in iter_view3d_spaces_fn(context):
        entry = _shading_entry(space, space_key_fn(space))
        if entry is not None:
            entries.append(entry)
    return json.dumps(entries, separators=(",", ":"))


def adopt_unmanaged_view3d_spaces(context, settings, *, iter_view3d_spaces_fn, space_key_fn) -> int:
    """Bring 3D viewports the preview has never touched under preview shading.

    Activation captures and configures every 3D viewport that exists at that
    moment, across all workspaces. A viewport that appears later (a workspace
    added afterwards, a freshly split area) still draws the low with whatever
    Solid color mode it had, so the baked map is invisible while the panel says
    the preview is on. Runs on workspace switches: capture such spaces so
    deactivation can put them back, then apply preview shading to them alone.
    Viewports already captured keep whatever the artist has since chosen.

    Returns the number of newly adopted spaces.
    """
    if settings is None or not any_preview_on_low_is_active(settings):
        return 0
    key_fn = space_key_fn if callable(space_key_fn) else _default_space_key
    captured = _captured_shading_entries(settings)
    new_spaces = []
    new_entries = []
    for space in iter_view3d_spaces_fn(context):
        key = key_fn(space)
        if key in captured:
            continue
        entry = _shading_entry(space, key)
        if entry is None:
            continue
        captured[key] = entry
        new_spaces.append(space)
        new_entries.append(entry)
    if not new_spaces:
        return 0

    session_state = properties.preview_session_state(settings)
    raw_state = str(getattr(session_state, "preview_on_low_restore_viewport_state", "") or "").strip()
    entries = []
    if raw_state:
        try:
            loaded = json.loads(raw_state)
        except json.JSONDecodeError:
            loaded = []
        if isinstance(loaded, list):
            entries = [entry for entry in loaded if isinstance(entry, dict)]
    entries.extend(new_entries)
    session_state.preview_on_low_restore_viewport_state = json.dumps(entries, separators=(",", ":"))

    apply_preview_on_low_viewport_state(
        context,
        iter_view3d_spaces_fn=lambda _context: iter(new_spaces),
        space_key_fn=key_fn,
    )
    return len(new_spaces)


def apply_preview_on_low_viewport_state(context, *, iter_view3d_spaces_fn, space_key_fn=None) -> None:
    """Ensure the bake preview is visible without forcing a heavy shading rebuild.

    Show-on-low only assigns a preview material on lows. It must not hide highs or
    force Material mode — switching into Material with a multi-million-triangle
    procedural high is what caused the Not Responding hitch.

    - Already Material/Rendered: leave shading alone. The single-map preview
      material is a bare Emission -> Output tree, which is unlit in EEVEE/Cycles.
    - Solid: set color_type to TEXTURE so the preview image texture is visible.
      Solid shading lights whatever it draws, so a *single map* preview also
      forces flat lighting: without it the studio light / matcap paints specular
      highlights and shading gradients over the raw baked data.
    - The combined PBR preview is a material preview and stays lit; when it takes
      over from a single-map preview the captured Solid lighting is put back.
    - Never touch studiolight / scene-world props.
    """
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    unlit = _single_map_preview_is_unlit(settings)
    key_fn = space_key_fn if callable(space_key_fn) else _default_space_key
    captured = {} if unlit else _captured_shading_entries(settings)

    for space in iter_view3d_spaces_fn(context):
        shading = getattr(space, "shading", None)
        if shading is None:
            continue
        shading_type = str(getattr(shading, "type", "") or "")
        if shading_type in {"MATERIAL", "RENDERED"}:
            continue
        if shading_type != "SOLID":
            continue
        pbr_material_preview = not unlit and _pbr_preview_is_active(settings)
        if not pbr_material_preview:
            _set_shading_property(shading, "color_type", "TEXTURE")
        if unlit:
            for property_name, value in _UNLIT_SOLID_SHADING.items():
                _set_shading_property(shading, property_name, value)
            continue
        entry = captured.get(key_fn(space))
        if not entry:
            continue
        # Undo only the flattening we applied ourselves. Anything the artist changed
        # while the preview was up is their choice and stays.
        for property_name, unlit_value in _UNLIT_SOLID_SHADING.items():
            if property_name not in entry or not hasattr(shading, property_name):
                continue
            try:
                if not _values_equal(getattr(shading, property_name), unlit_value):
                    continue
            except Exception:
                continue
            _set_shading_property(shading, property_name, entry[property_name])
    # Solid never applies normal maps and paints only the active image node as flat
    # colour, so a PBR preview there shows the raw Normal texture tinting the mesh.
    # Material Preview is the only workspace mode that renders the material the
    # preview built. Switched after the lighting restore above so a Solid viewport
    # keeps its own lighting when the artist drops back to it; restore undoes the
    # switch while it still reads MATERIAL.
    if not unlit and _pbr_preview_is_active(settings):
        for space in iter_view3d_spaces_fn(context):
            shading = getattr(space, "shading", None)
            if shading is not None and str(getattr(shading, "type", "") or "") == "SOLID":
                _set_shading_property(shading, "type", "MATERIAL")


def _disable_overlay_flag(overlay_state, property_name: str) -> None:
    """Set an overlay bool to False only when it is currently True.

    Overlay properties run expensive update callbacks (preview sync / debug
    refresh). Writing False while already False still risks work on some Blender
    builds, so gate the write.
    """
    if overlay_state is None or not hasattr(overlay_state, property_name):
        return
    try:
        if bool(getattr(overlay_state, property_name)):
            setattr(overlay_state, property_name, False)
    except Exception:
        pass


def clear_group_cage_coverage(project) -> None:
    """Switch every group's Cage Coverage toggle off when a preview starts.

    The preview already hides coverage through the global gate, but the per-group
    toggles kept reading ON while nothing was drawn. Clearing them keeps the buttons
    honest; turning one back on ends the preview (see properties).
    """
    for group in getattr(project, "groups", []) or []:
        try:
            if bool(getattr(group, "show_cage_coverage", False)):
                group.show_cage_coverage = False
        except Exception:
            pass


def restore_preview_on_low_viewport_state(context, settings, *, iter_view3d_spaces_fn, space_key_fn) -> None:
    """Undo the shading the preview applied, and nothing else.

    This runs on preview teardown and on ``save_pre`` (so preview-only shading is
    never written into the .blend). Both fire long after activation, by which time
    the artist may have changed the viewport themselves — so restoring the whole
    captured snapshot would silently revert their choice. The classic symptom:
    activate the preview from Rendered, drop to Solid, Ctrl+S, and the viewport
    jumps back to Rendered.

    ``apply_preview_on_low_viewport_state`` only ever writes ``color_type`` (to
    TEXTURE) and the unlit Solid lighting props, and never ``shading.type`` or the
    studiolight / scene-world props. So only those writes are undone here, and only
    while the value is still the one the preview put there.
    """
    by_key = _captured_shading_entries(settings)
    if not by_key:
        return

    for space in iter_view3d_spaces_fn(context):
        entry = by_key.get(space_key_fn(space))
        if entry is None:
            continue
        shading = getattr(space, "shading", None)
        if shading is None:
            continue
        # The PBR preview moves Solid viewports to Material Preview. Put them back
        # only while they still read MATERIAL; a different mode is the artist's pick.
        if str(entry.get("type", "") or "") == "SOLID":
            try:
                if str(getattr(shading, "type", "") or "") == "MATERIAL":
                    shading.type = "SOLID"
            except Exception:
                pass
        color_type = str(entry.get("color_type", "") or "")
        if color_type and hasattr(shading, "color_type"):
            try:
                # Only ours to put back while it still reads TEXTURE; anything else is
                # the artist's own pick. Skipping equal values also avoids the viewport
                # rebuild a redundant reassignment costs on heavy scenes.
                current_color_type = str(getattr(shading, "color_type", "") or "")
                if current_color_type == "TEXTURE" and current_color_type != color_type:
                    shading.color_type = color_type
            except Exception:
                pass
        for property_name, unlit_value in _UNLIT_SOLID_SHADING.items():
            if property_name not in entry or not hasattr(shading, property_name):
                continue
            try:
                if not _values_equal(getattr(shading, property_name), unlit_value):
                    continue
            except Exception:
                continue
            _set_shading_property(shading, property_name, entry[property_name])


def target_low_mesh_count(project, group_name: str) -> int:
    for group in getattr(project, "groups", []):
        if str(getattr(group, "name", "") or "") != str(group_name or ""):
            continue
        count = 0
        for slot in getattr(group, "low_meshes", []):
            obj = getattr(slot, "object_ref", None)
            if obj is not None and getattr(obj, "type", None) == "MESH":
                count += 1
        return count
    return 0


def activate_live_normal_preview(
    context,
    project,
    group,
    *,
    constants_module,
    target_low_mesh_count_fn,
    any_preview_on_low_is_active_fn,
    capture_view3d_shading_state_fn,
    cancel_live_normal_preview_runtime_fn,
    preview_on_low_project_name_fn,
    apply_preview_on_low_viewport_state_fn,
    resolve_map_source_fn,
    sync_preview_material_for_project_fn,
    request_live_normal_preview_refresh_fn,
    apply_preview_output_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> int:
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
    group_name = str(getattr(group, "name", "") or "")
    low_mesh_count = target_low_mesh_count_fn(project, group_name)
    if low_mesh_count <= 0:
        return 0

    if not any_preview_on_low_is_active_fn(settings):
        session_state.preview_on_low_restore_show_cage_overlay = bool(getattr(overlay_state, "show_cage_overlay", False))
        session_state.preview_on_low_restore_show_error_heatmap = bool(getattr(overlay_state, "show_error_heatmap", False))
        session_state.preview_on_low_restore_show_ray_miss_debug = bool(getattr(overlay_state, "show_ray_miss_debug", False))
        session_state.preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)

    cancel_live_normal_preview_runtime_fn()
    session_state.preview_on_low_active = False
    session_state.preview_on_low_project_name = ""
    session_state.preview_on_low_group_name = ""
    session_state.preview_on_low_map_uuid = ""
    session_state.preview_on_low_map_type = ""
    session_state.preview_on_low_map_index = -1
    session_state.preview_on_low_output_suffix = ""
    session_state.preview_pbr_on_low_active = False
    session_state.preview_pbr_on_low_project_name = ""
    session_state.preview_pbr_on_low_group_name = ""
    session_state.live_normal_preview_active = True
    session_state.live_normal_preview_scene_name = str(getattr(context.scene, "name", "") or "")
    session_state.live_normal_preview_project_name = preview_on_low_project_name_fn(project)
    session_state.live_normal_preview_group_name = group_name
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    clear_group_cage_coverage(project)
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    apply_preview_on_low_viewport_state_fn(context)
    reveal_preview_low_meshes(project, session_state, str(getattr(group, "name", "") or ""))

    applied_count = 0
    source = resolve_map_source_fn(project, map_type=constants_module.MAP_NORMAL, group_name=group_name, scene=context.scene)
    if source is not None:
        applied_count = apply_preview_output_fn(project, source["target"], source["image"])
        properties.set_preview_map_type(
            settings,
            getattr(source["target"], "map_type", ""),
            fallback=constants_module.MAP_NORMAL,
        )
        if source["resolved_index"] is not None:
            project.active_output_index = int(source["resolved_index"])
    else:
        # A material project has no NORMAL member in this enum -- only MATERIAL.
        properties.set_preview_map_type(settings, constants_module.MAP_NORMAL)
        applied_count = sync_preview_material_for_project_fn(context.scene, project)
    request_live_normal_preview_refresh_fn(context, reason="activate_live_normal_preview", delay_seconds=0.05)
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return max(applied_count, low_mesh_count)


def deactivate_preview_on_low(
    context,
    *,
    any_preview_on_low_is_active_fn,
    cancel_live_normal_preview_runtime_fn,
    restore_preview_materials_fn,
    restore_preview_on_low_overlay_state_fn,
    restore_preview_on_low_viewport_state_fn,
    clear_preview_on_low_state_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> int:
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    cancel_live_normal_preview_runtime_fn()
    restored_count = restore_preview_materials_fn()
    if any_preview_on_low_is_active_fn(settings):
        restore_preview_on_low_overlay_state_fn(settings)
        restore_preview_on_low_viewport_state_fn(context, settings)
    restore_high_meshes_after_preview(session_state)
    clear_preview_on_low_state_fn(settings)
    if settings is not None:
        # Point the picker at a still-valid map type. Both assignments go through
        # properties.set_preview_map_type because preview_map_type is a dynamic enum
        # built from the baked outputs of the ACTIVE project -- with no project at all
        # its item list is empty, and then even "" is rejected:
        #     TypeError: bpy_struct: item.attr = val: enum "" not found in ()
        # which is exactly the state left behind after removing a project while the
        # preview is live, i.e. the one case this restore exists to recover from.
        project = properties.get_active_project(context.scene) if context.scene else None
        preferred = ""
        if project is not None:
            for output in getattr(project, "latest_outputs", []) or []:
                map_type = str(getattr(output, "map_type", "") or "").strip().upper()
                if map_type:
                    preferred = map_type
                    break
        properties.set_preview_map_type(settings, preferred)
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return restored_count


def activate_preview_on_low(
    context,
    project,
    source,
    *,
    target_low_mesh_count_fn,
    any_preview_on_low_is_active_fn,
    capture_view3d_shading_state_fn,
    cancel_live_normal_preview_runtime_fn,
    preview_on_low_project_name_fn,
    apply_preview_on_low_viewport_state_fn,
    apply_preview_output_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> int:
    target = source["target"]
    resolved_index = source["resolved_index"]
    image = source["image"]
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
    group_name = str(getattr(target, "group_name", "") or "")
    map_uuid = str(source.get("map_uuid", "") or "")
    map_type = str(getattr(target, "map_type", "") or "")
    low_mesh_count = target_low_mesh_count_fn(project, group_name)
    if low_mesh_count <= 0:
        return 0

    if not any_preview_on_low_is_active_fn(settings):
        session_state.preview_on_low_restore_show_cage_overlay = bool(getattr(overlay_state, "show_cage_overlay", False))
        session_state.preview_on_low_restore_show_error_heatmap = bool(getattr(overlay_state, "show_error_heatmap", False))
        session_state.preview_on_low_restore_show_ray_miss_debug = bool(getattr(overlay_state, "show_ray_miss_debug", False))
        session_state.preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)

    cancel_live_normal_preview_runtime_fn()
    session_state.preview_on_low_active = True
    session_state.preview_on_low_project_name = preview_on_low_project_name_fn(project)
    session_state.preview_on_low_group_name = group_name
    session_state.preview_on_low_map_uuid = map_uuid
    session_state.preview_on_low_map_type = map_type
    session_state.preview_on_low_map_index = -1
    session_state.preview_on_low_output_suffix = ""
    session_state.preview_pbr_on_low_active = False
    session_state.preview_pbr_on_low_project_name = ""
    session_state.preview_pbr_on_low_group_name = ""
    session_state.live_normal_preview_active = False
    session_state.live_normal_preview_scene_name = ""
    session_state.live_normal_preview_project_name = ""
    session_state.live_normal_preview_group_name = ""
    session_state.live_normal_preview_output_path = ""
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    clear_group_cage_coverage(project)
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    apply_preview_on_low_viewport_state_fn(context)
    reveal_preview_low_meshes(project, session_state, str(getattr(target, "group_name", "") or ""))

    applied_count = apply_preview_output_fn(project, target, image)
    _safe_set_preview_map_type(settings, target.map_type)
    if resolved_index is not None:
        project.active_output_index = int(resolved_index)
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return applied_count


def activate_preview_on_low_all_groups(
    context,
    project,
    *,
    map_uuid: str = "",
    map_type: str,
    per_group_sources: list,
    any_preview_on_low_is_active_fn,
    capture_view3d_shading_state_fn,
    cancel_live_normal_preview_runtime_fn,
    preview_on_low_project_name_fn,
    apply_preview_on_low_viewport_state_fn,
    apply_preview_output_all_groups_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> tuple[int, bool]:
    """Activate single-map preview across all groups for *map_type*.

    Returns ``(applied_count, has_sources)``.
    """
    if not per_group_sources:
        return 0, False

    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    overlay_state = properties.overlay_settings_state(settings) if settings is not None else None

    if not any_preview_on_low_is_active_fn(settings):
        session_state.preview_on_low_restore_show_cage_overlay = bool(getattr(overlay_state, "show_cage_overlay", False))
        session_state.preview_on_low_restore_show_error_heatmap = bool(getattr(overlay_state, "show_error_heatmap", False))
        session_state.preview_on_low_restore_show_ray_miss_debug = bool(getattr(overlay_state, "show_ray_miss_debug", False))
        session_state.preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)

    cancel_live_normal_preview_runtime_fn()
    session_state.preview_on_low_active = True
    session_state.preview_on_low_project_name = preview_on_low_project_name_fn(project)
    session_state.preview_on_low_group_name = ""  # empty = all-groups
    session_state.preview_on_low_map_uuid = str(map_uuid or "")
    session_state.preview_on_low_map_type = map_type
    session_state.preview_on_low_map_index = -1
    session_state.preview_on_low_output_suffix = ""
    session_state.preview_pbr_on_low_active = False
    session_state.preview_pbr_on_low_project_name = ""
    session_state.preview_pbr_on_low_group_name = ""
    session_state.live_normal_preview_active = False
    session_state.live_normal_preview_scene_name = ""
    session_state.live_normal_preview_project_name = ""
    session_state.live_normal_preview_group_name = ""
    session_state.live_normal_preview_output_path = ""
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    clear_group_cage_coverage(project)
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    apply_preview_on_low_viewport_state_fn(context)
    reveal_preview_low_meshes(project, session_state, "")

    applied_count = apply_preview_output_all_groups_fn(project, per_group_sources=per_group_sources)
    _safe_set_preview_map_type(settings, map_type)
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return applied_count, True


def activate_preview_pbr_on_low(
    context,
    project,
    *,
    group_name: str,
    preview_inputs: dict | None = None,
    constants_module,
    target_low_mesh_count_fn,
    resolve_pbr_preview_inputs_fn,
    any_preview_on_low_is_active_fn,
    capture_view3d_shading_state_fn,
    cancel_live_normal_preview_runtime_fn,
    preview_on_low_project_name_fn,
    apply_preview_on_low_viewport_state_fn,
    apply_preview_pbr_output_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> tuple[int, bool]:
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
    low_mesh_count = target_low_mesh_count_fn(project, group_name)
    if low_mesh_count <= 0:
        return 0, False

    if preview_inputs is None:
        preview_inputs = resolve_pbr_preview_inputs_fn(project, group_name)
    normal_source = preview_inputs["normal_source"]
    ao_source = preview_inputs["ao_source"]
    material_images = dict(preview_inputs.get("material_images", {}) or {})
    if normal_source is None and ao_source is None and not any(material_images.values()):
        return 0, False

    if not any_preview_on_low_is_active_fn(settings):
        session_state.preview_on_low_restore_show_cage_overlay = bool(getattr(overlay_state, "show_cage_overlay", False))
        session_state.preview_on_low_restore_show_error_heatmap = bool(getattr(overlay_state, "show_error_heatmap", False))
        session_state.preview_on_low_restore_show_ray_miss_debug = bool(getattr(overlay_state, "show_ray_miss_debug", False))
        session_state.preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)

    cancel_live_normal_preview_runtime_fn()
    session_state.preview_on_low_active = False
    session_state.preview_on_low_project_name = ""
    session_state.preview_on_low_group_name = ""
    session_state.preview_on_low_map_uuid = ""
    session_state.preview_on_low_map_type = ""
    session_state.preview_pbr_on_low_active = True
    session_state.preview_pbr_on_low_project_name = preview_on_low_project_name_fn(project)
    session_state.preview_pbr_on_low_group_name = group_name
    session_state.live_normal_preview_active = False
    session_state.live_normal_preview_scene_name = ""
    session_state.live_normal_preview_project_name = ""
    session_state.live_normal_preview_group_name = ""
    session_state.live_normal_preview_output_path = ""
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    clear_group_cage_coverage(project)
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    apply_preview_on_low_viewport_state_fn(context)
    reveal_preview_low_meshes(project, session_state, group_name)

    applied_count = apply_preview_pbr_output_fn(
        project,
        group_name=group_name,
        normal_image=normal_source["image"] if normal_source is not None else None,
        ao_image=ao_source["image"] if ao_source is not None else None,
        curvature_image=(
            preview_inputs["curvature_source"]["image"]
            if preview_inputs.get("curvature_source") is not None
            else None
        ),
        **{f"{channel}_image": image for channel, image in material_images.items()},
        normal_space=str(preview_inputs["normal_space"] or ""),
        normal_format=str(preview_inputs["normal_format"] or ""),
        flip_green=bool(preview_inputs["flip_green"]),
        ao_strength=float(preview_inputs.get("ao_strength", 1.0)),
    )
    # Same base-vs-effective trap as the all-groups path below; see the note there.
    if normal_source is not None:
        properties.set_preview_map_type(
            settings,
            str(
                preview_inputs.get("normal_map_type", constants_module.MAP_NORMAL)
                or constants_module.MAP_NORMAL
            ),
        )
    elif ao_source is not None:
        properties.set_preview_map_type(settings, constants_module.MAP_AO)
    if preview_inputs["normal_index"] is not None:
        project.active_output_index = int(preview_inputs["normal_index"])
    elif preview_inputs["ao_index"] is not None:
        project.active_output_index = int(preview_inputs["ao_index"])
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return applied_count, True


def activate_preview_pbr_on_low_all_groups(
    context,
    project,
    *,
    constants_module,
    resolve_pbr_preview_inputs_fn,
    any_preview_on_low_is_active_fn,
    capture_view3d_shading_state_fn,
    cancel_live_normal_preview_runtime_fn,
    preview_on_low_project_name_fn,
    apply_preview_on_low_viewport_state_fn,
    apply_preview_pbr_output_all_groups_fn,
    cancel_debug_overlay_refresh_fn,
    tag_redraw_all_view3d_fn,
) -> tuple[int, bool]:
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session_state = properties.preview_session_state(settings) if settings is not None else None
    overlay_state = properties.overlay_settings_state(settings) if settings is not None else None

    groups = list(getattr(project, "groups", []))
    if not groups:
        return 0, False

    per_group_inputs = []
    for group in groups:
        gn = str(getattr(group, "name", "") or "")
        if not gn:
            continue
        preview_inputs = resolve_pbr_preview_inputs_fn(project, gn)
        normal_source = preview_inputs["normal_source"]
        ao_source = preview_inputs["ao_source"]
        material_images = dict(preview_inputs.get("material_images", {}) or {})
        if normal_source is None and ao_source is None and not any(material_images.values()):
            continue
        per_group_inputs.append({
            "group_name": gn,
            "normal_image": normal_source["image"] if normal_source else None,
            "ao_image": ao_source["image"] if ao_source else None,
            "curvature_image": (
                preview_inputs["curvature_source"]["image"]
                if preview_inputs.get("curvature_source") is not None
                else None
            ),
            **{f"{channel}_image": image for channel, image in material_images.items()},
            "normal_map_type": str(preview_inputs.get("normal_map_type", constants_module.MAP_NORMAL)),
            "ao_strength": float(preview_inputs.get("ao_strength", 1.0)),
            "normal_space": str(preview_inputs["normal_space"] or ""),
            "normal_format": str(preview_inputs["normal_format"] or ""),
            "flip_green": bool(preview_inputs["flip_green"]),
        })

    if not per_group_inputs:
        return 0, False

    if not any_preview_on_low_is_active_fn(settings):
        session_state.preview_on_low_restore_show_cage_overlay = bool(getattr(overlay_state, "show_cage_overlay", False))
        session_state.preview_on_low_restore_show_error_heatmap = bool(getattr(overlay_state, "show_error_heatmap", False))
        session_state.preview_on_low_restore_show_ray_miss_debug = bool(getattr(overlay_state, "show_ray_miss_debug", False))
        session_state.preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)

    cancel_live_normal_preview_runtime_fn()
    session_state.preview_on_low_active = False
    session_state.preview_on_low_project_name = ""
    session_state.preview_on_low_group_name = ""
    session_state.preview_on_low_map_uuid = ""
    session_state.preview_on_low_map_type = ""
    session_state.preview_pbr_on_low_active = True
    session_state.preview_pbr_on_low_project_name = preview_on_low_project_name_fn(project)
    session_state.preview_pbr_on_low_group_name = ""
    session_state.live_normal_preview_active = False
    session_state.live_normal_preview_scene_name = ""
    session_state.live_normal_preview_project_name = ""
    session_state.live_normal_preview_group_name = ""
    session_state.live_normal_preview_output_path = ""
    _disable_overlay_flag(overlay_state, "show_cage_overlay")
    _disable_overlay_flag(overlay_state, "show_error_heatmap")
    clear_group_cage_coverage(project)
    _disable_overlay_flag(overlay_state, "show_ray_miss_debug")
    if callable(cancel_debug_overlay_refresh_fn):
        cancel_debug_overlay_refresh_fn()
    apply_preview_on_low_viewport_state_fn(context)
    reveal_preview_low_meshes(project, session_state, "")

    applied_count = apply_preview_pbr_output_all_groups_fn(
        project,
        per_group_inputs=per_group_inputs,
    )

    first_normal = next((inp for inp in per_group_inputs if inp["normal_image"] is not None), None)
    first_ao = next((inp for inp in per_group_inputs if inp["ao_image"] is not None), None)
    # Both assignments go through properties.set_preview_map_type rather than
    # touching the enum directly. `normal_map_type` is a BASE type (`NORMAL`), and
    # in a WORKFLOW_MATERIAL project every row's map_type is `MATERIAL` -- the
    # per-channel effective types live on the output, not the row -- so the enum
    # holds only `MATERIAL` and assigning `NORMAL` raised
    # `TypeError: enum "NORMAL" not found in ('MATERIAL')`. That fired on the very
    # first Preview Baked Material in the material workflow, *after* the preview
    # material had already been swapped onto the object, so the artist got an error
    # and a changed scene. The helper normalises to a base type and falls back
    # instead of raising; the deactivate path was routed through it when the same
    # bug was fixed there (pass 3, H10) and this call site was missed.
    if first_normal is not None:
        properties.set_preview_map_type(
            settings,
            str(
                first_normal.get("normal_map_type", constants_module.MAP_NORMAL)
                or constants_module.MAP_NORMAL
            ),
        )
    elif first_ao is not None:
        properties.set_preview_map_type(settings, constants_module.MAP_AO)
    tag_redraw_all_view3d_fn(
        scene=context.scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    return applied_count, True
