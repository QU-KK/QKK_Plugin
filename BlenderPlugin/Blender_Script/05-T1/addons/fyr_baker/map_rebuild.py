from __future__ import annotations

import json

from . import mesh_read
from . import constants, dirty_rules, mesh_digest, naming

#: 17: resolved high-poly opacity (image, constant, address, filter) is
#: fingerprinted. State recorded before it cannot answer "did a high material's
#: Alpha change", so the bump retires it.
#: 16: the material-detail fast path's resolved source (strength, flip, UV
#: transform) is fingerprinted. State recorded before it cannot answer "did the
#: high material's Normal Map change", so the bump retires it.
#: 15: object state gained a vertex-coordinate digest. Recorded state without it
#: cannot answer "did the geometry move", so the bump retires it rather than
#: comparing a new state against a blind one.
_STATE_VERSION = 17

# (property name, default) for the seven Marmoset curvature calibration knobs. Mirrors
# properties.MM_CALIBRATION_KNOBS for the bpy-less case; _mm_calibration_knobs() prefers
# the real tuple so a knob added there is fingerprinted without touching this file.
_MM_CALIBRATION_KNOB_DEFAULTS = (
    ("mm_power_gamma", 1.792),
    ("mm_power_amplitude", 9.2),
    ("mm_power_linear_floor", 3.2),
    ("mm_power_faint", 1.75),
    ("mm_convex_boost", 1.7),
    ("mm_linear_bias", 1.0),
    ("mm_aa_jitter_scale", 2.0),
)


def _group_uses_low_as_high(group) -> bool:
    role_state = getattr(group, "role_assignments", None)
    return bool(getattr(role_state, "use_low_as_high", getattr(group, "use_low_as_high", False)))


def _effective_high_mesh_slots(group):
    role_state = getattr(group, "role_assignments", None) or group
    attr_name = "low_meshes" if _group_uses_low_as_high(group) else "high_meshes"
    return getattr(role_state, attr_name, getattr(group, attr_name, []))


def _normalized_normal_space(value) -> str:
    return str(value or "").strip().upper()


def _normalize_state(value):
    if isinstance(value, dict):
        return {str(key): _normalize_state(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_state(item) for item in value]
    return value


def enabled_map_types(project) -> list[str]:
    return [
        str(getattr(item, "map_type", "") or "")
        for item in getattr(project, "maps", [])
        if bool(getattr(item, "enabled", False)) and str(getattr(item, "map_type", "") or "").strip()
    ]


def _map_uuid(map_setting) -> str:
    try:
        from . import properties as _properties
    except Exception:
        return str(getattr(map_setting, "uuid", "") or "").strip()
    return _properties.ensure_map_setting_uuid(map_setting)


def enabled_map_uuids(project) -> list[str]:
    return [
        _map_uuid(item)
        for item in getattr(project, "maps", [])
        if bool(getattr(item, "enabled", False)) and str(getattr(item, "map_type", "") or "").strip()
    ]


def _object_name(obj) -> str:
    return str(getattr(obj, "name", "") or "")


def _group_metadata_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "metadata", None) or group
    return _properties.group_metadata_state(group)


def _group_paint_projection_settings_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "paint_projection_settings", None) or group
    try:
        return _properties.group_paint_projection_settings_state(group)
    except Exception:
        return getattr(group, "paint_projection_settings", None) or group


def _group_projection_settings_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "projection_settings", None) or group
    return _properties.group_projection_settings_state(group)


def _matrix_state(matrix) -> tuple[float, ...]:
    if matrix is None:
        return ()
    values: list[float] = []
    try:
        row_count = len(matrix)
    except Exception:
        row_count = 0
    if row_count <= 0:
        return ()
    for row_index in range(row_count):
        try:
            row = matrix[row_index]
        except Exception:
            return ()
        try:
            column_count = len(row)
        except Exception:
            column_count = 0
        for column_index in range(column_count):
            try:
                values.append(round(float(row[column_index]), 6))
            except Exception:
                values.append(0.0)
    return tuple(values)


def _bounds_state(obj) -> tuple[tuple[float, float, float], ...]:
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


def _uv_digest(obj) -> str:
    """Lazy: dirty_tracker imports bpy-heavy modules; map_rebuild loads earlier."""
    if obj is None:
        return ""
    try:
        from . import dirty_tracker as _dirty_tracker

        return _dirty_tracker.mesh_uv_digest(obj)
    except Exception:
        return ""


def _shape_digest(obj) -> str:
    """The shared exact/strided coordinate digest.

    Imported directly, not lazily through dirty_tracker like _uv_digest: that module
    imports bpy at module scope, so the lazy import can never resolve here. mesh_digest
    is deliberately bpy-free for exactly this.
    """
    if obj is None:
        return ""
    try:
        return mesh_digest.mesh_shape_digest(obj)
    except Exception:
        return ""


def _mesh_state_fields(obj) -> dict:
    """The terms of an object's state that read its mesh datablock."""
    data = getattr(obj, "data", None) if obj is not None else None
    return {
        "data_name": str(getattr(data, "name", "") or ""),
        "vertex_count": mesh_read.element_count(data, "vertices"),
        "edge_count": mesh_read.element_count(data, "edges"),
        "polygon_count": mesh_read.element_count(data, "polygons"),
        "bound_box": _bounds_state(obj) if obj is not None else (),
        # Counts, matrix and a 6-decimal bounding box all survive an edit that moves
        # geometry in the interior: sculpt a recess into the middle of a high, or nudge
        # one interior vertex of a low, and this state compared EQUAL -- Rebuild Changed
        # Maps answered "No changed maps to rebuild" and the stale Normal/AO/Curvature
        # stayed on disk. This is the same coordinate term the live tracker was given
        # for the identical failure (dirty_tracker._mesh_shape_digest), exact under the
        # vertex cap and strided above it. It runs on a button press, not per tick.
        "shape_digest": _shape_digest(obj),
    }


def mesh_state_fields(obj) -> dict:
    """Public name of :func:`_mesh_state_fields` (high_poly_park snapshots it before a swap)."""
    return _mesh_state_fields(obj)


def _parked_mesh_state_fields(obj):
    """The mesh terms captured when high_poly_park emptied ``obj``'s mesh, else None. A
    parked high reads as an empty placeholder until its slice of the restore runs; the
    state a bake records must describe the real mesh."""
    if obj is None:
        return None
    try:
        from . import high_poly_park

        return high_poly_park.parked_mesh_state_fields(obj)
    except Exception:
        return None


def _object_state(obj, *, include_uvs: bool = False) -> dict:
    fields = _parked_mesh_state_fields(obj)
    if fields is None:
        fields = _mesh_state_fields(obj)
    state = {
        "object_name": _object_name(obj),
        "matrix_world": _matrix_state(getattr(obj, "matrix_world", None) if obj is not None else None),
        **fields,
    }
    if include_uvs:
        # Counts, matrix, and bounds all survive a re-unwrap; the projected maps do
        # not. Low meshes only: highs bake FROM their surface, their UVs are inert.
        state["uv_digest"] = _uv_digest(obj)
    return state


def _slot_state(slot, *, include_uvs: bool = False) -> dict:
    return {
        "object": _object_state(getattr(slot, "object_ref", None), include_uvs=include_uvs),
        "cage_offset_delta": round(float(getattr(slot, "cage_offset_delta", 0.0) or 0.0), 6),
    }


def _group_state(group) -> dict:
    metadata_state = _group_metadata_state(group)
    projection_state = _group_projection_settings_state(group)
    return {
        "name": str(getattr(metadata_state, "name", "") or ""),
        "texture_set_name": str(getattr(metadata_state, "texture_set_name", "") or ""),
        "uv_layer_name": str(getattr(projection_state, "uv_layer_name", "") or ""),
        "cage_mode": str(getattr(projection_state, "cage_mode", "") or ""),
        "cage_offset": round(float(getattr(projection_state, "cage_offset", 0.0) or 0.0), 6),
        "projection_rear_distance": round(float(getattr(projection_state, "projection_rear_distance", 0.0) or 0.0), 6),
        "average_normals": bool(getattr(projection_state, "average_normals", True)),
        "match_by_isolation": bool(getattr(projection_state, "match_by_isolation", False)),
        "custom_cage": _object_state(getattr(projection_state, "custom_cage", None)),
        "low_meshes": [_slot_state(slot, include_uvs=True) for slot in getattr(group, "low_meshes", [])],
        "use_low_as_high": _group_uses_low_as_high(group),
        "high_meshes": [_slot_state(slot) for slot in _effective_high_mesh_slots(group)],
        "id_collection_name": str(getattr(metadata_state, "id_collection_name", "") or ""),
        "id_color_set_name": str(getattr(metadata_state, "id_color_set_name", "") or ""),
    }


def _color_state(value, fallback) -> tuple[float, ...]:
    try:
        seq = tuple(value)
    except Exception:
        seq = ()
    if len(seq) < len(fallback):
        seq = tuple(fallback)
    return tuple(round(float(component), 6) for component in seq[: len(fallback)])


def _lighting_scene_state(map_setting) -> str:
    """Scene lights + world digest, for lighting rows only ("" for every other row).

    A SCENE_LIGHTING output is a function of the scene's lights and world, none of which
    live on the map row or the bake group — without this, adding a light left the recorded
    bake state identical and the row reported "no changes"."""
    if str(getattr(map_setting, "map_type", "") or "").strip().upper() not in constants.LIGHTING_FAMILY_MAP_TYPES:
        return ""
    try:
        from . import dirty_tracker as _dirty_tracker

        return _dirty_tracker.lighting_scene_signature()
    except Exception:
        return ""


def _resolved_soften(map_setting, project) -> float:
    """Effective Soften for this row. Lazy import: properties imports bpy-heavy
    modules and map_rebuild is pulled in from places that load earlier."""
    try:
        from . import properties as _properties

        return _properties.resolve_map_soften(project, map_setting)
    except Exception:
        return float(constants.DEFAULT_SOFTEN)


def _opacity_signature(project) -> str:
    """Resolved high-poly opacity, which reaches the job but was in no state.

    With Respect Opacity on, a transparent high material contributes an opacity
    image, constant, address mode and filter per high object, and the backend lets
    that opacity participate in intersections, so it moves AO, thickness and every
    other traced map. Only the project-level ``respect_opacity`` boolean was
    fingerprinted, so dropping a high material's Alpha changed the bake while this
    state stayed byte-identical and "Rebuild Changed Maps" reported no changes.

    Reuses export._material_opacity_source, the same resolver the exporter builds
    its bindings from, so the two cannot drift. That helper reads node trees only;
    the PNG normalisation the exporter does afterwards is not repeated here.
    Returns "" when Respect Opacity is off, because nothing then reaches the job.
    """
    if not bool(getattr(project, "respect_opacity", True)):
        return ""
    try:
        from . import export as _export
        from . import properties as _properties
    except Exception:
        return ""
    entries = []
    for group in getattr(project, "groups", ()) or ():
        try:
            slots = _export._iter_valid_object_slots(_properties.effective_high_mesh_slots(group))
        except Exception:
            continue
        for slot in slots:
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            for material_slot in getattr(obj, "material_slots", ()) or ():
                material = getattr(material_slot, "material", None)
                try:
                    expression = _export._material_opacity_source(material)
                except Exception:
                    expression = None
                if expression is None:
                    continue
                image = expression.get("image")
                entries.append(
                    (
                        str(getattr(obj, "name", "") or ""),
                        str(getattr(material, "name", "") or ""),
                        str(expression.get("identity", "") or ""),
                        round(float(expression.get("constant", 1.0) or 0.0), 7),
                        str(expression.get("address", "") or ""),
                        str(expression.get("filter", "") or ""),
                        str(getattr(image, "name", "") or ""),
                        str(getattr(image, "filepath", "") or ""),
                    )
                )
    if not entries:
        return ""
    return json.dumps(sorted(entries, key=repr), default=str)


def _material_detail_signature(map_setting, project) -> str:
    """Pixel-affecting inputs of the material-detail fast path, for rows that use it.

    An AO or Normal row (and a Roughness row on normal variance) reprojects a detail
    texture resolved from the HIGH materials, and the job carries that source's
    strength, flip and UV transform. None of those is a property of the map row, and
    the project material signature above is deliberately added to MATERIAL rows only,
    so editing a high material's Normal Map Strength changed the bake while this
    state stayed byte-identical and "Rebuild Changed Maps" reported no changes.

    Reuses export._material_detail_source, the same resolver the exporter picks the
    source with, so the two cannot drift apart. That helper reads node trees only:
    no image normalization, no workspace, nothing written to disk. Only the operator
    paths build this state, never a UI draw.
    """
    try:
        from . import export as _export
    except Exception:
        return ""
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    try:
        if _export._map_wants_normal_variance(map_setting):
            map_type = constants.MAP_NORMAL
    except Exception:
        pass
    if map_type not in {constants.MAP_AO, constants.MAP_NORMAL}:
        return ""
    mode = str(
        getattr(map_setting, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
        or constants.MATERIAL_DETAIL_AUTO
    ).strip().upper()
    if mode == constants.MATERIAL_DETAIL_OFF:
        return ""
    if mode == constants.MATERIAL_DETAIL_MANUAL and map_type == constants.MAP_AO:
        # The resolver takes the chosen image and never reads a material; the
        # "material_detail_image" key already carries that choice.
        if getattr(map_setting, "material_detail_image", None) is not None:
            return ""
    sources = []
    for group in getattr(project, "groups", []) or ():
        for material in _export._iter_group_high_materials(group) or ():
            name = str(getattr(material, "name", "") or "")
            try:
                source = _export._material_detail_source(material, map_type)
            except Exception:
                source = None
            if source is None:
                sources.append((name, None))
                continue
            image, backend_mode, strength, flip_green, uv_transform = source
            sources.append(
                (
                    name,
                    str(getattr(image, "name", "") or ""),
                    str(getattr(image, "filepath", "") or ""),
                    str(backend_mode or ""),
                    round(float(strength), 7),
                    bool(flip_green),
                    [round(float(value), 7) for value in (uv_transform or ())],
                )
            )
    if not sources:
        return ""
    return json.dumps(sorted(sources, key=repr), default=str)


def _project_material_signature(project) -> str:
    """Content hash of every material a MATERIAL row bakes from.

    "Bake Changed" compares per-map settings, and for a WORKFLOW_MATERIAL project the
    material node graph IS the input -- nothing else changes between iterations. It was
    not captured, so editing a Color Ramp and pressing Bake Changed reported "No changed
    maps to rebuild" while a full Bake picked the same edit up
    (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P11).

    Reuses `bakeability_ui.graph_signature`, which already recurses node groups and
    covers unlinked socket values, image assignments and links -- the same signature the
    Bakeability panel caches its verdicts on, so the two agree by construction.
    """
    try:
        from . import bakeability_ui
    except Exception:
        return ""
    signatures: list[str] = []
    seen: set[str] = set()
    for group in getattr(project, "groups", []) or []:
        for collection_name in ("low_meshes", "high_meshes"):
            for slot in getattr(group, collection_name, []) or []:
                obj = getattr(slot, "object_ref", None)
                if obj is None:
                    continue
                for material_slot in getattr(obj, "material_slots", []) or []:
                    material = getattr(material_slot, "material", None)
                    name = str(getattr(material, "name", "") or "")
                    if material is None or name in seen:
                        continue
                    seen.add(name)
                    try:
                        signatures.append(f"{name}={bakeability_ui.graph_signature(material)}")
                    except Exception:
                        signatures.append(f"{name}=?")
    return "|".join(sorted(signatures))


def _project_id_material_signature(project) -> str:
    """Resolved ID colour of every material on the project's high objects.

    Same rule the bake uses (id_material_color.material_id_color), so the detector sees
    exactly the inputs that reach the ID map and nothing else.
    """
    try:
        from . import id_material_color
    except Exception:
        return ""
    entries: set[str] = set()
    for group in getattr(project, "groups", []) or []:
        for slot in getattr(group, "high_meshes", []) or []:
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            for material_slot in getattr(obj, "material_slots", []) or []:
                material = getattr(material_slot, "material", None)
                if material is None:
                    continue
                try:
                    color = id_material_color.material_id_color(material)
                except Exception:
                    continue
                entries.add(
                    f"{getattr(material, 'name', '')}="
                    + ",".join(f"{component:.5f}" for component in color)
                )
    return "|".join(sorted(entries))


def _effective_flip_green(map_setting) -> bool:
    normal_format = str(getattr(map_setting, "normal_format", "") or "").strip().upper()
    if normal_format == constants.NORMAL_FORMAT_DIRECTX:
        return True
    if normal_format == constants.NORMAL_FORMAT_OPENGL:
        return False
    return bool(getattr(map_setting, "flip_green", False))


def _map_depends_on_tangent_basis(map_setting) -> bool:
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if map_type == constants.MAP_NORMAL:
        return True
    if map_type == constants.MAP_BENT_NORMAL:
        return _normalized_normal_space(getattr(map_setting, "normal_space", "")) in {"", "TANGENT"}
    return False


def _map_state(map_setting, project) -> dict:
    # IMPORTANT: this must capture EVERY per-map property that export.py sends to
    # protocol.BakeMapConfig. Any bake-affecting field omitted here is invisible to
    # the "Rebuild Changed Maps" detector, so changing it silently reports "no
    # changes". When adding a field to the bake job, add it here and bump
    # _STATE_VERSION.
    map_type = str(getattr(map_setting, "map_type", "") or "")
    default_cavity = constants.default_ao_cavity_weight_for_map(map_type)
    # Only MATERIAL rows bake from a node graph; adding it unconditionally would make
    # every mesh-map project re-bake whenever an unrelated material was touched.
    material_signature = (
        _project_material_signature(project)
        if map_type.strip().upper() == constants.MAP_MATERIAL
        else ""
    )
    # An ID row on the Material Color source bakes each high face in its material's
    # resolved colour (MBBJOB35), so a Base Color / viewport colour edit moves its pixels
    # and must count as a change. Only that row opts in, for the same reason as above.
    if (
        map_type.strip().upper() == constants.MAP_ID
        and str(getattr(map_setting, "id_source", "") or "") == constants.MAP_ID_SOURCE_MATERIAL
    ):
        material_signature = _project_id_material_signature(project)
    return {
        "map_type": map_type,
        "material_graph": material_signature,
        "enabled": bool(getattr(map_setting, "enabled", False)),
        "samples": int(getattr(map_setting, "samples", 1) or 1),
        "output_suffix": str(getattr(map_setting, "output_suffix", "") or ""),
        "normal_space": str(getattr(map_setting, "normal_space", "") or ""),
        "normal_format": str(getattr(map_setting, "normal_format", "") or ""),
        # What the job actually carries (properties.map_flip_green): the format
        # decides, the stored flip_green is only a legacy mirror. Comparing the raw
        # mirror re-baked Normal after a format toggle-and-revert whenever the
        # mirror had drifted from the format (2026-09-06, BakeTester3).
        "flip_green": _effective_flip_green(map_setting),
        # --- AO family ---
        "ao_mode": str(getattr(map_setting, "ao_mode", constants.MAP_AO_MODE_RAYCAST) or constants.MAP_AO_MODE_RAYCAST),
        "ao_distance": round(float(getattr(map_setting, "ao_distance", 0.0) or 0.0), 6),
        "ao_min_distance": round(float(getattr(map_setting, "ao_min_distance", 0.0) or 0.0), 6),
        "ao_two_sided": bool(getattr(map_setting, "ao_two_sided", False)),
        "ao_ignore_groups": bool(getattr(map_setting, "ao_ignore_groups", False)),
        "ao_bevel_normal": str(getattr(map_setting, "ao_bevel_normal", constants.AO_BEVEL_NORMAL_AUTO)),
        "curvature_bevel_mask": bool(getattr(map_setting, "curvature_bevel_mask", True)),
        "ao_cavity_weight": round(float(getattr(map_setting, "ao_cavity_weight", default_cavity)), 6),
        "ao_output_min": round(float(getattr(map_setting, "ao_output_min", constants.DEFAULT_AO_OUTPUT_MIN)), 6),
        "ao_output_max": round(float(getattr(map_setting, "ao_output_max", 1.0)), 6),
        "ao_floor_occlusion": bool(getattr(map_setting, "ao_floor_occlusion", False)),
        "ao_relative_to_bounding_box": bool(getattr(map_setting, "ao_relative_to_bounding_box", False)),
        "ao_spread_angle": round(float(getattr(map_setting, "ao_spread_angle", 180.0) or 180.0), 6),
        "ao_distribution": str(getattr(map_setting, "ao_distribution", "COSINE") or "COSINE"),
        "ao_ignore_backface": bool(getattr(map_setting, "ao_ignore_backface", False)),
        "ao_self_occlusion": round(float(getattr(map_setting, "ao_self_occlusion", 1.0) or 1.0), 6),
        "ao_attenuation": round(float(getattr(map_setting, "ao_attenuation", 1.0) or 1.0), 6),
        "ao_use_ground_plane": bool(getattr(map_setting, "ao_use_ground_plane", False)),
        "ao_ground_plane_offset": round(float(getattr(map_setting, "ao_ground_plane_offset", 0.0) or 0.0), 6),
        "ao_diffusion_quality": str(getattr(map_setting, "ao_diffusion_quality", constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM) or constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM),
        "ao_diffusion_clearance_scale": round(float(getattr(map_setting, "ao_diffusion_clearance_scale", 0.2) or 0.2), 6),
        "ao_diffusion_clearance_exponent": round(float(getattr(map_setting, "ao_diffusion_clearance_exponent", 2.0) or 2.0), 6),
        # --- Environment light ---
        "env_light_intensity": round(float(getattr(map_setting, "env_light_intensity", 1.0) or 1.0), 6),
        "env_light_occlusion_strength": round(float(getattr(map_setting, "env_light_occlusion_strength", 0.6) or 0.6), 6),
        "env_light_contrast": round(float(getattr(map_setting, "env_light_contrast", 1.0) or 1.0), 6),
        "env_light_up_axis": str(getattr(map_setting, "env_light_up_axis", "Z") or "Z"),
        "env_light_sky_color": _color_state(getattr(map_setting, "env_light_sky_color", None), (0.55, 0.70, 1.00)),
        "env_light_ground_color": _color_state(getattr(map_setting, "env_light_ground_color", None), (0.18, 0.16, 0.14)),
        # --- Curvature ---
        "curvature_scale": round(float(getattr(map_setting, "curvature_scale", 1.0) or 1.0), 6),
        "curvature_distance": round(float(getattr(map_setting, "curvature_distance", 0.0) or 0.0), 6),
        "curvature_relative_to_bounding_box": bool(getattr(map_setting, "curvature_relative_to_bounding_box", False)),
        "curvature_method": str(getattr(map_setting, "curvature_method", "THICKNESS") or "THICKNESS"),
        "curvature_secondary_rays": int(getattr(map_setting, "curvature_secondary_rays", 64) or 64),
        # Painter-style "Generate from Mesh" probe controls. All four are bake-affecting:
        # they change which geometry the probe rays may hit and how the signed result is
        # ranged, so a change must re-bake rather than serve the cached map.
        "curvature_detect_folds": bool(getattr(map_setting, "curvature_detect_folds", False)),
        "curvature_self_intersection": str(getattr(map_setting, "curvature_self_intersection", "GROUP") or "GROUP"),
        "curvature_auto_tonemapping": bool(getattr(map_setting, "curvature_auto_tonemapping", False)),
        "curvature_value_min": round(float(getattr(map_setting, "curvature_value_min", -1.0)), 6),
        "curvature_value_max": round(float(getattr(map_setting, "curvature_value_max", 1.0)), 6),
        # Signed/Principal/Direction. This does not reach the backend as a field -- it
        # rewrites the effective map_type (export.effective_map_type_for_setting), so
        # the raw "map_type" above never moves when the tester flips the tab and the
        # row looked unchanged.
        "curvature_output_mode": str(getattr(map_setting, "curvature_output_mode", "SIGNED") or "SIGNED"),
        # Detail Smoothing (the normal-derivative kernel width). Distinct from the
        # output blur below, and bake-affecting, so it needs its own key.
        "curvature_soften": round(float(getattr(map_setting, "curvature_soften", 0.5)), 6),
        "curvature_tonemapping_min": round(float(getattr(map_setting, "curvature_tonemapping_min", 0.0)), 6),
        "curvature_tonemapping_max": round(float(getattr(map_setting, "curvature_tonemapping_max", 1.0)), 6),
        # --- Thickness ---
        "thickness_distance": round(float(getattr(map_setting, "thickness_distance", 0.0) or 0.0), 6),
        "thickness_min_distance": round(float(getattr(map_setting, "thickness_min_distance", -1.0)), 6),
        "thickness_scale": round(float(getattr(map_setting, "thickness_scale", 1.0) or 1.0), 6),
        "thickness_gamma": round(float(getattr(map_setting, "thickness_gamma", 1.0) or 1.0), 6),
        "thickness_dither": bool(getattr(map_setting, "thickness_dither", False)),
        "thickness_ignore_groups": bool(getattr(map_setting, "thickness_ignore_groups", False)),
        "thickness_normalization": bool(getattr(map_setting, "thickness_normalization", False)),
        "thickness_log_response": bool(getattr(map_setting, "thickness_log_response", False)),
        "density_auto_levels": bool(getattr(map_setting, "density_auto_levels", False)),
        "density_auto_levels_per_group": bool(getattr(map_setting, "density_auto_levels_per_group", True)),
        # --- ID ---
        "id_source": str(getattr(map_setting, "id_source", "") or ""),
        # --- Attribute ---
        "attribute_name": str(getattr(map_setting, "attribute_name", "") or ""),
        "attribute_range_min": round(float(getattr(map_setting, "attribute_range_min", 0.0) or 0.0), 6),
        "attribute_range_max": round(float(getattr(map_setting, "attribute_range_max", 1.0)), 6),
        # --- Derivative (a Normal row's Output) / Wireframe ---
        "normal_encoding": str(getattr(map_setting, "normal_encoding", "") or ""),
        "derivative_max_slope": round(float(getattr(map_setting, "derivative_max_slope", 2.0) or 2.0), 6),
        "wireframe_line_width": round(float(getattr(map_setting, "wireframe_line_width", 1.5) or 1.5), 6),
        "wireframe_triangles": bool(getattr(map_setting, "wireframe_triangles", False)),
        # --- Position ---
        "position_mode": str(getattr(map_setting, "position_mode", "ABSOLUTE") or "ABSOLUTE"),
        "position_axis": str(getattr(map_setting, "position_axis", "XYZ") or "XYZ"),
        "position_normalization": str(getattr(map_setting, "position_normalization", "") or ""),
        "relative_to_bounding_box": bool(getattr(map_setting, "relative_to_bounding_box", True)),
        # --- Height ---
        "height_inner_distance": round(float(getattr(map_setting, "height_inner_distance", 0.0) or 0.0), 6),
        "height_outer_distance": round(float(getattr(map_setting, "height_outer_distance", 0.0) or 0.0), 6),
        "height_dither": bool(getattr(map_setting, "height_dither", False)),
        # --- Post-processing ---
        "denoising_enabled": bool(getattr(map_setting, "denoising_enabled", False)),
        # RESOLVED soften, so a project-level Soften change and a per-row override
        # both land in this fingerprint through one key.
        "soften": round(_resolved_soften(map_setting, project), 6),
        "denoise_strength": round(float(getattr(project, "denoise_strength", 1.0) or 1.0), 6),
        "denoise_quality": str(getattr(project, "denoise_quality", "HIGH") or "HIGH"),
        "diffusion_dilation_enabled": bool(getattr(map_setting, "diffusion_dilation_enabled", False)),
        "diffusion_dilation_iterations": int(getattr(map_setting, "diffusion_dilation_iterations", 3) or 3),
        # --- Material ---
        "material_channel": str(getattr(map_setting, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or constants.MATERIAL_CHANNEL_ALBEDO),
        # Manual vs Custom rewrites the effective map_type the same way the curvature
        # tabs do; the detail source picks which image the AO fast path reprojects.
        "material_origin": str(getattr(map_setting, "material_origin", "") or ""),
        "material_detail_mode": str(getattr(map_setting, "material_detail_mode", "") or ""),
        # The detail SOURCE, not just the mode: strength/flip/UV come from the high
        # materials and reach the job, so a Normal Map Strength edit has to land here.
        "material_detail_source": _material_detail_signature(map_setting, project),
        # The detail SOURCE, not just the mode: strength/flip/UV come from the high
        # materials and reach the job, so a Normal Map Strength edit has to land here.
        # --- Fields that reach BakeMapConfig but were missing here (v12) ---
        "ao_occlude_other_groups": bool(getattr(map_setting, "ao_occlude_other_groups", False)),
        "lighting_quality": str(getattr(map_setting, "lighting_quality", "") or ""),
        "lighting_engine": str(getattr(map_setting, "lighting_engine", "") or ""),
        "lighting_direct_enabled": bool(getattr(map_setting, "lighting_direct_enabled", True)),
        "lighting_direct_samples": int(getattr(map_setting, "lighting_direct_samples", 0) or 0),
        "lighting_indirect_enabled": bool(getattr(map_setting, "lighting_indirect_enabled", True)),
        "lighting_indirect_paths": int(getattr(map_setting, "lighting_indirect_paths", 0) or 0),
        "lighting_world_enabled": bool(getattr(map_setting, "lighting_world_enabled", True)),
        "lighting_emission_enabled": bool(getattr(map_setting, "lighting_emission_enabled", True)),
        "lighting_max_bounces": int(getattr(map_setting, "lighting_max_bounces", 0) or 0),
        "lighting_noise_threshold": round(float(getattr(map_setting, "lighting_noise_threshold", 0.0) or 0.0), 6),
        # Complete Lighting controls: keyed on lighting rows only, so no other row's
        # recorded state changes with them.
        **(
            {
                "lighting_occlude_other_groups": bool(getattr(map_setting, "lighting_occlude_other_groups", True)),
                "lighting_exposure": round(float(getattr(map_setting, "lighting_exposure", 1.0)), 6),
                "lighting_output": str(getattr(map_setting, "lighting_output", "") or ""),
            }
            if constants.effective_lighting_map_type(map_setting) is not None
            else {}
        ),
        "roughness_normal_variance": bool(getattr(map_setting, "roughness_normal_variance", False)),
        "roughness_normal_variance_strength": round(float(getattr(map_setting, "roughness_normal_variance_strength", 0.0) or 0.0), 6),
        "normal_relief": round(float(getattr(map_setting, "normal_relief", 0.5) or 0.5), 6),
        # Per-map copy of the render/tangent state the map was last baked with. The
        # project-wide copies are stamped current after ANY partial bake, so a
        # resolution change followed by a Normal-only bake left AO reported clean
        # at the old size; this per-map copy keeps flagging it.
        "render": _project_render_state(project),
        # Only tangent-space maps depend on the tangent basis (mirrors
        # resolve_changed_map_types): object/world bent normals must not re-bake
        # when the basis changes.
        "tangent": _project_tangent_state(project) if _map_depends_on_tangent_basis(map_setting) else {},
        "material_detail_image": str(getattr(getattr(map_setting, "material_detail_image", None), "name", "") or ""),
        # --- Scene lighting ---
        "lighting_output": str(getattr(map_setting, "lighting_output", "") or ""),
        "lighting_scene": _lighting_scene_state(map_setting),
    }


def _mm_calibration_knobs() -> tuple[tuple[str, float], ...]:
    """(name, default) per calibration knob. Lazy import: properties pulls in bpy-heavy
    modules and map_rebuild is imported from places that load earlier."""
    try:
        from . import properties as _properties

        knobs = tuple((str(entry[0]), float(entry[2])) for entry in _properties.MM_CALIBRATION_KNOBS)
    except Exception:
        return _MM_CALIBRATION_KNOB_DEFAULTS
    return knobs or _MM_CALIBRATION_KNOB_DEFAULTS


def _scene_settings(project):
    """The scene settings block that owns `project`.

    Job-global settings do not all live on the project: export reads the calibration
    knobs off `context.scene.fyr_baker_settings`. The project is a PropertyGroup inside
    that same block, so `project.id_data` IS its scene -- more exact than bpy.context,
    which can be pointing at another window's scene while this project is fingerprinted.
    bpy.context is only the fallback (and there is none outside Blender)."""
    scene = getattr(project, "id_data", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is not None:
        return settings
    try:
        import bpy

        return getattr(getattr(bpy.context, "scene", None), "fyr_baker_settings", None)
    except Exception:
        return None


def _mm_calibration_state(project) -> dict:
    """The seven Marmoset curvature calibration knobs, which are bake-affecting.

    They are scene-global (properties.MM_CALIBRATION_KNOBS) and flow per-bake through the
    job payload: six are stamped onto EVERY BakeMapConfig and mm_aa_jitter_scale onto the
    job block (export.prepare_bake_job). Nothing recorded them here, so dragging "Convex
    Boost" and pressing Rebuild Changed Maps answered "No changed maps to rebuild" and the
    stale curvature output stood -- while a full Bake picked the new value up."""
    settings = _scene_settings(project)
    state: dict[str, float] = {}
    for prop_name, default in _mm_calibration_knobs():
        try:
            value = float(getattr(settings, prop_name, default))
        except (TypeError, ValueError):
            value = float(default)
        state[prop_name] = round(value, 6)
    return state


def _project_udim_state(project) -> list[dict]:
    """The UDIM tile plan of every texture set: mode plus each artist tile row.

    udim.resolve_effective_tiles turns these rows into the tiles that are written and the
    size each one is written at, and nothing about them lives on the project or a bake
    group. So giving a tile a custom resolution (or excluding it) left the recorded state
    identical and Rebuild Changed Maps answered "No changed maps" while the old files
    stayed on disk at the old size.

    Sorted by set name and tile number: reordering rows in the UI list changes no output,
    and an order-sensitive fingerprint would rebake the project for a drag.
    """
    sets_state: list[dict] = []
    for texture_set in getattr(project, "texture_sets", []) or []:
        tiles = [
            {
                "number": int(getattr(tile, "number", 0) or 0),
                "override": str(getattr(tile, "override", "") or ""),
                "use_resolution_override": bool(getattr(tile, "use_resolution_override", False)),
                "resolution_x": int(getattr(tile, "resolution_x", 0) or 0),
                "resolution_y": int(getattr(tile, "resolution_y", 0) or 0),
            }
            for tile in getattr(texture_set, "udim_tiles", []) or []
        ]
        sets_state.append(
            {
                "name": str(getattr(texture_set, "name", "") or ""),
                # Automatic layers the rows over detected occupancy, Explicit makes them
                # the whole tile list, so the mode alone changes which tiles are baked.
                "udim_mode": str(getattr(texture_set, "udim_mode", "") or ""),
                "tiles": sorted(tiles, key=lambda item: item["number"]),
            }
        )
    return sorted(sets_state, key=lambda item: item["name"])


def _project_render_state(project) -> dict:
    project_ignore_backface = bool(
        getattr(
            project,
            "ignore_backface",
            any(bool(getattr(_group_projection_settings_state(group), "ignore_backface", False)) for group in getattr(project, "groups", [])),
        )
    )
    return {
        "output_root": str(getattr(project, "output_root", "") or ""),
        "resolution_x": int(getattr(project, "resolution_x", 0) or 0),
        "resolution_y": int(getattr(project, "resolution_y", 0) or 0),
        "bit_depth": str(getattr(project, "bit_depth", "") or ""),
        # Sent in BakeProjectInfo next to bit_depth, and it decides the extension and
        # encoder of every written file. Without it, switching PNG -> TGA reported "No
        # changed maps" and the previously written files stayed.
        "image_format": str(getattr(project, "image_format", "") or ""),
        "anti_aliasing": str(getattr(project, "anti_aliasing", "") or ""),
        "aa_samples": int(getattr(project, "aa_samples", 0) or 0),
        "margin": int(getattr(project, "margin", 0) or 0),
        "margin_mode": str(getattr(project, "margin_mode", constants.DILATION_DISTANCE) or constants.DILATION_DISTANCE),
        "ignore_backface": project_ignore_backface,
        "respect_opacity": bool(getattr(project, "respect_opacity", True)),
        # The resolved opacity itself, not just the toggle: a transparent high
        # material's alpha reaches the job and moves every traced map.
        "opacity_sources": _opacity_signature(project),
        "bake_mode": str(getattr(project, "bake_mode", "") or ""),
        # Scene-global, not project-owned -- see _mm_calibration_state.
        "mm_calibration": _mm_calibration_state(project),
        # Per-texture-set tile plan -- see _project_udim_state.
        "udim": _project_udim_state(project),
    }


def _project_tangent_state(project) -> dict:
    return {
        "tangent_basis": str(getattr(project, "tangent_basis", "") or ""),
    }


def _group_projection_state(group) -> dict:
    group_state = _group_state(group)
    return {
        "name": group_state["name"],
        "texture_set_name": group_state["texture_set_name"],
        "uv_layer_name": group_state["uv_layer_name"],
        "cage_mode": group_state["cage_mode"],
        "cage_offset": group_state["cage_offset"],
        "projection_rear_distance": group_state["projection_rear_distance"],
        "average_normals": group_state["average_normals"],
        "match_by_isolation": group_state["match_by_isolation"],
        "custom_cage": group_state["custom_cage"],
        "low_meshes": group_state["low_meshes"],
        "use_low_as_high": group_state["use_low_as_high"],
        "high_meshes": group_state["high_meshes"],
        # Paint Offset / Skew change the exported cage; they were invisible here.
        "paint": _group_paint_state(group),
    } | _group_floater_faces_state(group)


def _group_floater_faces_state(group) -> dict:
    """Floater faces marked on the group's highs (floater_faces.py). A mark is a mesh
    attribute edit, which no shape term sees, and it changes AO and the Automatic cage.
    Empty without marks, so states recorded before floater faces existed compare equal."""
    from . import floater_faces

    marks = set()
    role_state = getattr(group, "role_assignments", None)
    collections = [getattr(role_state, "high_meshes", None), getattr(group, "high_meshes", None)]
    if _group_uses_low_as_high(group):
        collections = [getattr(role_state, "low_meshes", None), getattr(group, "low_meshes", None)]
    for collection in collections:
        for slot in collection or []:
            obj = getattr(slot, "object_ref", None)
            signature = floater_faces.signature(obj) if obj is not None else ()
            if signature:
                marks.add(f"{_object_name(obj)}:{signature[1]}:{signature[2]}")
    return {"floater_faces": sorted(marks)} if marks else {}


# One build of the project state hashes every paint image it meets; the operator builds
# the state four times per press (invoke + execute resolve, the group resolve, and the
# record afterwards). Both the digests and the float32 read-back buffer are scoped to one
# build: the cache stops a mask shared by several groups from being read back once per
# group, and the scratch buffer stops every image from allocating its own. Both are
# dropped when the build ends -- an image's pixels cannot change during a build, but they
# certainly can between two presses, and a digest that outlived the build would miss the
# next paint stroke (the failure 367dea29 fixed).
_PAINT_DIGEST_SCOPE_DEPTH = 0
_PAINT_DIGEST_CACHE: dict | None = None
_PAINT_DIGEST_SCRATCH = None


def _begin_paint_digest_scope() -> None:
    global _PAINT_DIGEST_SCOPE_DEPTH, _PAINT_DIGEST_CACHE

    if _PAINT_DIGEST_SCOPE_DEPTH == 0:
        _PAINT_DIGEST_CACHE = {}
    _PAINT_DIGEST_SCOPE_DEPTH += 1


def _end_paint_digest_scope() -> None:
    global _PAINT_DIGEST_SCOPE_DEPTH, _PAINT_DIGEST_CACHE, _PAINT_DIGEST_SCRATCH

    _PAINT_DIGEST_SCOPE_DEPTH = max(0, _PAINT_DIGEST_SCOPE_DEPTH - 1)
    if _PAINT_DIGEST_SCOPE_DEPTH == 0:
        _PAINT_DIGEST_CACHE = None
        # Released with the scope: a 4K RGBA mask is 268 MB, which must not sit resident
        # between bakes (the project's standing ~1 GB-in-every-state goal).
        _PAINT_DIGEST_SCRATCH = None


def _paint_digest_scratch(length: int):
    """A float32 read-back buffer of exactly `length`, reused across one build."""
    global _PAINT_DIGEST_SCRATCH

    import numpy as np

    buffer = _PAINT_DIGEST_SCRATCH
    if buffer is None or buffer.size < length:
        buffer = np.empty(length, dtype=np.float32)
        # Only retained while a build owns the scope, so a direct call cannot strand it.
        if _PAINT_DIGEST_SCOPE_DEPTH > 0:
            _PAINT_DIGEST_SCRATCH = buffer
    return buffer[:length]


def _paint_image_signature(image) -> str:
    """Identity of a paint image's CONTENT, not just its name.

    Paint strokes write pixels only: no depsgraph update, no rename, and the
    image name the old state carried never changed. So a group painted after
    its last bake compared equal and "Rebuild Changed Maps" answered "No
    changed maps" while the full Bake re-exported the strokes. Hash the pixels
    (a 1024x1024 mask is ~16 MB, a few ms) and fold them into the identity.
    Falls back to the name if the pixels cannot be read, which errs toward a
    rebuild only when the name itself changed, exactly as before.

    The read-back and the hash both run straight off one reusable buffer: the old
    `tobytes()` doubled a 4K RGBA mask's 268 MB transient for no gain.
    """
    if image is None:
        return ""
    name = str(getattr(image, "name", "") or "")
    try:
        import hashlib

        width, height = (int(v) for v in getattr(image, "size", (0, 0)))
        channels = int(getattr(image, "channels", 4) or 4)
        pixels = getattr(image, "pixels", None)
        if width <= 0 or height <= 0 or pixels is None or not hasattr(pixels, "foreach_get"):
            return name
        # session_uid and is_dirty are in the key so a reloaded or freshly painted image
        # is never served a digest recorded for the previous one.
        cache_key = (
            name,
            int(getattr(image, "session_uid", 0) or 0),
            bool(getattr(image, "is_dirty", False)),
            width,
            height,
            channels,
        )
        cache = _PAINT_DIGEST_CACHE
        if cache is not None and cache_key in cache:
            return cache[cache_key]
        buffer = _paint_digest_scratch(width * height * channels)
        pixels.foreach_get(buffer)
        digest = hashlib.blake2b(buffer.data, digest_size=16).hexdigest()
        signature = f"{name}:{width}x{height}:{digest}"
        if cache is not None:
            cache[cache_key] = signature
        return signature
    except Exception:
        return name


def _group_paint_state(group) -> dict:
    paint_state = _group_paint_projection_settings_state(group)
    state = {
        "paint_offset_scale": round(float(getattr(paint_state, "paint_offset_scale", 1.0) or 1.0), 6),
        "paint_skew": round(float(getattr(paint_state, "paint_skew", 0.0) or 0.0), 6),
        "paint_offset_image": _paint_image_signature(getattr(paint_state, "paint_offset_image", None)),
        "paint_skew_image": _paint_image_signature(getattr(paint_state, "paint_skew_image", None)),
    }
    # Only when some low carries a layer, so states recorded before paint layers existed
    # still compare equal for unpainted groups.
    layers = _group_paint_layer_signature(group)
    if layers:
        state["paint_layers"] = layers
    from .paint_sampling import skew_correction_digest

    try:
        correction = skew_correction_digest(group)
    except Exception:
        correction = ""
    if correction:
        state["skew_correction"] = correction
    return state


def _group_paint_layer_signature(group) -> list:
    """Paint layer content per low mesh: a brush stroke writes a mesh attribute only, which
    no shape, UV or modifier term above sees."""
    from .paint_sampling import paint_layer_digest

    signature = []
    for slot in getattr(group, "low_meshes", []) or []:
        obj = getattr(slot, "object_ref", None)
        if obj is None:
            continue
        try:
            digest = paint_layer_digest(getattr(obj, "data", None))
        except Exception:
            digest = ""
        if digest:
            signature.append(f"{getattr(obj, 'name', '')}:{digest}")
    return signature


def _group_ao_occluder_state(group) -> dict:
    """High meshes with Casts AO off (mirrors properties.group_ao_non_caster_objects)."""
    names: set[str] = set()
    if not _group_uses_low_as_high(group):
        role_state = getattr(group, "role_assignments", None)
        for collection in (getattr(role_state, "high_meshes", None), getattr(group, "high_meshes", None)):
            for slot in collection or []:
                obj = getattr(slot, "object_ref", None)
                if obj is not None and (
                    not bool(getattr(slot, "casts_ao", True))
                ):
                    names.add(_object_name(obj))
    return {
        "name": str(getattr(_group_metadata_state(group), "name", "") or ""),
        "ao_non_casters": sorted(names),
    }


def _group_id_state(group) -> dict:
    group_state = _group_state(group)
    return {
        "name": group_state["name"],
        "texture_set_name": group_state["texture_set_name"],
        "id_collection_name": group_state["id_collection_name"],
        "id_color_set_name": group_state["id_color_set_name"],
        "use_low_as_high": group_state["use_low_as_high"],
        "high_meshes": group_state["high_meshes"],
    }


def build_project_state(project) -> dict:
    # The scope owns the paint-digest cache and read-back buffer for this build only.
    _begin_paint_digest_scope()
    try:
        maps = {
            _map_uuid(item): _map_state(item, project)
            for item in getattr(project, "maps", [])
            if str(getattr(item, "map_type", "") or "").strip() and _map_uuid(item)
        }
        return _normalize_state({
            "version": _STATE_VERSION,
            "render": _project_render_state(project),
            "tangent": _project_tangent_state(project),
            "projection_groups": [_group_projection_state(group) for group in getattr(project, "groups", [])],
            "id_groups": [_group_id_state(group) for group in getattr(project, "groups", [])],
            "ao_occluder_groups": [_group_ao_occluder_state(group) for group in getattr(project, "groups", [])],
            "maps": maps,
        })
    finally:
        _end_paint_digest_scope()


def serialize_project_state(project) -> str:
    return json.dumps(build_project_state(project), sort_keys=True, separators=(",", ":"))


def group_names(project) -> list[str]:
    return [
        str(getattr(group, "name", "") or "")
        for group in getattr(project, "groups", [])
        if str(getattr(group, "name", "") or "").strip()
    ]


def _state_groups_by_name(groups_state) -> dict[str, dict]:
    return {
        str(getattr(item, "get", lambda _key, _default=None: item["name"])("name", "") if hasattr(item, "get") else item["name"] or ""): item
        for item in (groups_state or [])
        if str((item.get("name", "") if hasattr(item, "get") else item["name"]) or "").strip()
    }


def _deserialize_state(raw_state: str) -> dict | None:
    if not str(raw_state or "").strip():
        return None
    try:
        payload = json.loads(raw_state)
    except (TypeError, json.JSONDecodeError):
        return None
    return _normalize_state(payload) if isinstance(payload, dict) else None


def record_bake_state(project) -> str:
    if active_bake_is_partial(project):
        return update_partial_bake_state(
            project,
            active_bake_group_names(project),
            active_bake_map_types(project),
            active_bake_map_uuids(project),
        )
    serialized = serialize_project_state(project)
    project.last_baked_maps_state = serialized
    clear_last_incremental_bake_groups(project)
    return serialized


def resolve_changed_map_types(project) -> list[str]:
    current_enabled = enabled_map_types(project)
    if not current_enabled:
        return []

    previous_state = _deserialize_state(getattr(project, "last_baked_maps_state", ""))
    if previous_state is None:
        return current_enabled

    current_state = build_project_state(project)
    if int(previous_state.get("version", 0) or 0) != _STATE_VERSION:
        return current_enabled
    if previous_state.get("render") != current_state["render"]:
        return current_enabled

    changed_map_types: set[str] = set()

    if previous_state.get("projection_groups") != current_state["projection_groups"]:
        return current_enabled

    if previous_state.get("tangent") != current_state["tangent"]:
        if constants.MAP_NORMAL in current_enabled:
            changed_map_types.add(constants.MAP_NORMAL)
        if constants.MAP_BENT_NORMAL in current_enabled:
            # Only tangent-space bent normals depend on the tangent basis; object/world
            # space ones are unaffected. current_state["maps"] is keyed by map UUID, so
            # resolve each bent-normal map's state via its UUID — the previous map_type
            # lookup always missed and needlessly rebaked every bent normal.
            for item in getattr(project, "maps", []):
                if getattr(item, "is_add_phantom", False) or not bool(getattr(item, "enabled", False)):
                    continue
                if str(getattr(item, "map_type", "") or "") != constants.MAP_BENT_NORMAL:
                    continue
                map_state = current_state["maps"].get(_map_uuid(item), {})
                if _normalized_normal_space(map_state.get("normal_space")) in {"", "TANGENT"}:
                    changed_map_types.add(constants.MAP_BENT_NORMAL)
                    break

    if previous_state.get("id_groups") != current_state["id_groups"]:
        if constants.MAP_ID in current_enabled:
            changed_map_types.add(constants.MAP_ID)

    # A state recorded before Casts AO existed has no entry; every high cast then.
    previous_occluders = previous_state.get("ao_occluder_groups")
    if previous_occluders is None:
        previous_occluders = [
            {"name": entry["name"], "ao_non_casters": []} for entry in current_state["ao_occluder_groups"]
        ]
    if previous_occluders != current_state["ao_occluder_groups"]:
        changed_map_types.update(
            map_type for map_type in current_enabled if map_type in constants.AO_OCCLUDER_MAP_TYPES
        )

    previous_maps = previous_state.get("maps", {})
    current_maps = current_state["maps"]
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False) or not bool(getattr(item, "enabled", False)):
            continue
        map_type = str(getattr(item, "map_type", "") or "")
        if not map_type:
            continue
        map_uuid = _map_uuid(item)
        if not map_uuid:
            changed_map_types.add(map_type)
            continue
        if previous_maps.get(map_uuid) != current_maps.get(map_uuid):
            changed_map_types.add(map_type)

    return [map_type for map_type in current_enabled if map_type in changed_map_types]


def resolve_changed_group_names(project) -> list[str]:
    current_group_names = group_names(project)
    if not current_group_names:
        return []

    previous_state = _deserialize_state(getattr(project, "last_baked_maps_state", ""))
    if previous_state is None:
        return current_group_names

    current_state = build_project_state(project)
    if int(previous_state.get("version", 0) or 0) != _STATE_VERSION:
        return current_group_names
    if previous_state.get("render") != current_state["render"]:
        return current_group_names
    if previous_state.get("tangent") != current_state["tangent"]:
        return current_group_names

    previous_projection = _state_groups_by_name(previous_state.get("projection_groups", []))
    current_projection = _state_groups_by_name(current_state["projection_groups"])
    previous_id = _state_groups_by_name(previous_state.get("id_groups", []))
    current_id = _state_groups_by_name(current_state["id_groups"])
    if set(previous_projection) != set(current_projection) or set(previous_id) != set(current_id):
        return current_group_names
    # Casts AO can shadow other groups too (Occlude Other Groups), so any change rebakes
    # every group's AO rows. A state recorded before the toggle existed counts as all-cast.
    previous_occluders = previous_state.get("ao_occluder_groups")
    if previous_occluders is None:
        previous_occluders = [
            {"name": entry["name"], "ao_non_casters": []} for entry in current_state["ao_occluder_groups"]
        ]
    if previous_occluders != current_state["ao_occluder_groups"]:
        return current_group_names

    changed_group_names: list[str] = []
    for group_name in current_group_names:
        if previous_projection.get(group_name) != current_projection.get(group_name):
            changed_group_names.append(group_name)
            continue
        if previous_id.get(group_name) != current_id.get(group_name):
            changed_group_names.append(group_name)
    # Occlude Other Groups: a changed high darkens the other groups' AO too, and a job
    # holding only the changed group would bake its AO without the rest of the scene.
    if changed_group_names and dirty_rules.world_occlusion_dirty_map_types(getattr(project, "maps", [])):
        return current_group_names
    return changed_group_names


def _serialize_string_list(values) -> str:
    normalized = sorted({str(value or "") for value in (values or []) if str(value or "").strip()})
    return json.dumps(normalized, separators=(",", ":"))


def _deserialize_string_list(raw_value: str) -> list[str]:
    if not str(raw_value or "").strip():
        return []
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [str(item or "") for item in payload if str(item or "").strip()]


def record_active_bake_map_types(project, map_types) -> list[str]:
    normalized = _deserialize_string_list(_serialize_string_list(map_types))
    project.active_bake_map_types = _serialize_string_list(normalized)
    return normalized


def active_bake_map_types(project) -> list[str]:
    return _deserialize_string_list(getattr(project, "active_bake_map_types", ""))


def record_active_bake_map_uuids(project, map_uuids) -> list[str]:
    normalized = _deserialize_string_list(_serialize_string_list(map_uuids))
    project.active_bake_map_uuids = _serialize_string_list(normalized)
    return normalized


def active_bake_map_uuids(project) -> list[str]:
    return _deserialize_string_list(getattr(project, "active_bake_map_uuids", ""))


def record_active_bake_group_names(project, group_names_value) -> list[str]:
    normalized = _deserialize_string_list(_serialize_string_list(group_names_value))
    project.active_bake_group_names = _serialize_string_list(normalized)
    return normalized


def active_bake_group_names(project) -> list[str]:
    return _deserialize_string_list(getattr(project, "active_bake_group_names", ""))


def record_last_incremental_bake_groups(project, group_names_value) -> list[str]:
    normalized = _deserialize_string_list(_serialize_string_list(group_names_value))
    project.last_incremental_bake_groups = _serialize_string_list(normalized)
    return normalized


def extend_last_incremental_bake_groups(project, group_names_value) -> list[str]:
    merged = set(last_incremental_bake_groups(project))
    merged.update(_deserialize_string_list(_serialize_string_list(group_names_value)))
    return record_last_incremental_bake_groups(project, merged)


def last_incremental_bake_groups(project) -> list[str]:
    return _deserialize_string_list(getattr(project, "last_incremental_bake_groups", ""))


def clear_last_incremental_bake_groups(project) -> None:
    project.last_incremental_bake_groups = ""


def active_bake_is_partial(project) -> bool:
    selected = set(active_bake_map_types(project))
    selected_uuids = set(active_bake_map_uuids(project))
    selected_groups = set(active_bake_group_names(project))
    all_enabled = set(enabled_map_types(project))
    all_enabled_uuids = set(enabled_map_uuids(project))
    all_groups = set(group_names(project))
    maps_partial = (
        bool(selected_uuids) and selected_uuids != all_enabled_uuids
        if all_enabled_uuids
        else bool(selected) and selected != all_enabled
    )
    groups_partial = bool(selected_groups) and selected_groups != all_groups
    return maps_partial or groups_partial


def clear_active_bake_map_types(project) -> None:
    project.active_bake_map_types = ""
    project.active_bake_map_uuids = ""
    project.active_bake_group_names = ""


def update_partial_bake_state(project, group_names_value, map_types, map_uuids=None) -> str:
    previous_state = _deserialize_state(getattr(project, "last_baked_maps_state", "")) or {}
    current_state = build_project_state(project)
    rebaked_groups = _deserialize_string_list(_serialize_string_list(group_names_value))
    rebaked_maps = _deserialize_string_list(_serialize_string_list(map_types))
    rebaked_map_uuids = _deserialize_string_list(_serialize_string_list(map_uuids))

    previous_state["version"] = current_state.get("version", _STATE_VERSION)
    previous_state["render"] = current_state["render"]
    previous_state["tangent"] = current_state["tangent"]

    def _merge_groups(state_key: str) -> list[dict]:
        current_groups = current_state.get(state_key, [])
        current_by_name = {item["name"]: item for item in current_groups if item.get("name")}
        existing_groups = previous_state.get(state_key, [])
        existing_by_name = {item["name"]: item for item in existing_groups if item.get("name")}
        for group_name in rebaked_groups:
            if group_name in current_by_name:
                existing_by_name[group_name] = current_by_name[group_name]
        merged: list[dict] = []
        merged_names: set[str] = set()
        for item in current_groups:
            group_name = str(item.get("name", "") or "")
            if not group_name or group_name not in existing_by_name:
                continue
            merged.append(existing_by_name[group_name])
            merged_names.add(group_name)
        for group_name, item in existing_by_name.items():
            if group_name in merged_names:
                continue
            merged.append(item)
        return merged

    previous_state["projection_groups"] = _merge_groups("projection_groups")
    previous_state["id_groups"] = _merge_groups("id_groups")

    current_maps = current_state.get("maps", {})
    existing_maps = dict(previous_state.get("maps", {}) or {})
    if rebaked_map_uuids:
        for map_uuid in rebaked_map_uuids:
            if map_uuid in current_maps:
                existing_maps[map_uuid] = current_maps[map_uuid]
    else:
        for map_uuid, map_state in current_maps.items():
            if str(map_state.get("map_type", "") or "") in rebaked_maps:
                existing_maps[map_uuid] = map_state
    previous_state["maps"] = existing_maps

    serialized = json.dumps(_normalize_state(previous_state), sort_keys=True, separators=(",", ":"))
    project.last_baked_maps_state = serialized
    extend_last_incremental_bake_groups(project, rebaked_groups)
    return serialized
