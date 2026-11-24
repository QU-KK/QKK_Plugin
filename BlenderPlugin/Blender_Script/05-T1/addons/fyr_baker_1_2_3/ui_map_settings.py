from __future__ import annotations

from . import bake_backends, constants, naming, preferences, properties, sidebar_icons
from .ui_utils import duplicate_warning_icon_kwargs


def _enum_item_label(items, value: str) -> str | None:
    normalized_value = str(value or "").strip().upper()
    for identifier, label, *_rest in items:
        if str(identifier or "").strip().upper() == normalized_value:
            return str(label or "").strip() or None
    return None


def _map_settings_icon(map_type: str) -> str:
    normalized = str(map_type or "").strip().upper()
    if normalized in {constants.MAP_NORMAL, constants.MAP_OBJECT_NORMAL, constants.MAP_WORLD_NORMAL, constants.MAP_BENT_NORMAL}:
        return "NORMALS_FACE"
    if normalized in {constants.MAP_AO, constants.MAP_CURVATURE, constants.MAP_THICKNESS, constants.MAP_DENSITY, constants.MAP_CAVITY, constants.MAP_CONCAVE, constants.MAP_CONVEX, constants.MAP_ENV_LIGHT}:
        return "MOD_BEVEL"
    if normalized == constants.MAP_MATERIAL:
        return "NODE_MATERIAL"
    return "PROPERTIES"


def _map_section_box(layout, title: str, *, icon: str = "NONE"):
    box = layout.box()
    box.use_property_split = False
    box.use_property_decorate = False
    box.label(text=title, icon=icon)
    return box


def _map_stack_mode_label(map_item) -> str | None:
    normalized_map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()
    if naming.normal_row_is_derivative(map_item):
        return "Derivative"
    if normalized_map_type in {constants.MAP_NORMAL, constants.MAP_BENT_NORMAL}:
        return _enum_item_label(
            constants.MAP_NORMAL_SPACE_ITEMS,
            getattr(map_item, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT),
        )
    if normalized_map_type == constants.MAP_AO:
        return _enum_item_label(
            constants.MAP_AO_MODE_ITEMS,
            getattr(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST),
        )
    if normalized_map_type == constants.MAP_CURVATURE:
        return _enum_item_label(
            (
                ("SIGNED", "Signed"),
                ("PRINCIPAL", "Principal"),
                ("DIRECTION", "Direction"),
            ),
            getattr(map_item, "curvature_output_mode", "SIGNED"),
        )
    if normalized_map_type in {
        constants.MAP_CAVITY,
        constants.MAP_CONCAVE,
        constants.MAP_CONVEX,
    }:
        return _enum_item_label(
            (
                ("THICKNESS", "Geometric"),
                ("NORMAL_DERIVATIVE", "Normal Derivative"),
                ("MESH_RAYS", "Mesh Rays"),
            ),
            getattr(map_item, "curvature_method", "THICKNESS"),
        )
    if normalized_map_type == constants.MAP_POSITION:
        return _enum_item_label(
            (
                ("ABSOLUTE", "Absolute"),
                ("RELATIVE", "Relative"),
            ),
            getattr(map_item, "position_mode", "ABSOLUTE"),
        )
    if normalized_map_type == constants.MAP_ATTRIBUTE:
        return str(getattr(map_item, "attribute_name", "") or "").strip() or None
    if normalized_map_type == constants.MAP_ID:
        return _enum_item_label(
            constants.MAP_ID_SOURCE_ITEMS,
            getattr(map_item, "id_source", constants.MAP_ID_SOURCE_OBJECT),
        )
    if normalized_map_type == constants.MAP_MATERIAL:
        return _enum_item_label(
            constants.MATERIAL_CHANNEL_ITEMS,
            getattr(map_item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO),
        )
    if normalized_map_type == constants.MAP_SCENE_LIGHTING:
        return _enum_item_label(
            constants.LIGHTING_OUTPUT_ITEMS,
            getattr(map_item, "lighting_output", constants.LIGHTING_OUTPUT_LIGHTING),
        )
    return None


def _output_suffix_is_duplicate(project, map_item) -> bool:
    """Return True if another enabled map in the stack resolves to the same output key."""
    effective_suffix = properties.effective_map_output_suffix(project, map_item)
    target_ptr = getattr(map_item, "as_pointer", lambda: None)()
    target_uuid = str(getattr(map_item, "uuid", "") or "").strip()
    from . import export as _export
    effective_type = _export.effective_map_type_for_setting(map_item)
    for ms in getattr(project, "maps", []):
        if getattr(ms, "is_add_phantom", False):
            continue
        if not bool(getattr(ms, "enabled", False)):
            continue
        # Skip map_item itself
        is_self = ms is map_item
        if not is_self and target_ptr is not None:
            ms_ptr = getattr(ms, "as_pointer", lambda: None)()
            is_self = ms_ptr is not None and ms_ptr == target_ptr
        if not is_self and target_uuid:
            is_self = str(getattr(ms, "uuid", "") or "").strip() == target_uuid
        if is_self:
            continue
        ms_effective_type = _export.effective_map_type_for_setting(ms)
        ms_effective_suffix = properties.effective_map_output_suffix(project, ms)
        if ms_effective_type == effective_type and ms_effective_suffix == effective_suffix:
            return True
    return False


def _map_stack_type_short_label(map_item) -> str:
    map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()
    return constants.MAP_FILE_LABELS.get(
        map_type,
        naming.map_label(getattr(map_item, "map_type", "")),
    )


def map_stack_index_label(map_type: str, variant: int, count: int) -> str:
    """Short map-stack label for one occurrence: ``AO``, ``AO #2``, ``AO #3``.

    ``variant`` is 0-based (map-stack order among same-type rows). The first
    occurrence omits the number; later ones use ``#2``, ``#3``, matching the
    map stack UI.
    """
    short = constants.MAP_FILE_LABELS.get(
        str(map_type or "").strip().upper(),
        naming.map_label(map_type),
    )
    if int(count or 0) <= 1:
        return short
    ordinal = max(0, int(variant or 0))
    if ordinal <= 0:
        return short
    return f"{short} #{ordinal + 1}"


def _map_stack_item_label(project, map_item) -> str:
    short = _map_stack_type_short_label(map_item)
    mode_label = _map_stack_mode_label(map_item)
    if mode_label:
        short = f"{short} [{mode_label}]"
    if project is None:
        return short
    map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()
    map_item_ptr = getattr(map_item, "as_pointer", lambda: None)()
    map_item_uuid = str(getattr(map_item, "uuid", "") or "").strip()
    matching_indices = []
    current_index = None
    for index, candidate in enumerate(getattr(project, "maps", [])):
        if getattr(candidate, "is_add_phantom", False):
            continue
        is_current = candidate is map_item
        if not is_current and map_item_ptr is not None:
            cand_ptr = getattr(candidate, "as_pointer", lambda: None)()
            is_current = cand_ptr is not None and cand_ptr == map_item_ptr
        if not is_current and map_item_uuid:
            is_current = str(getattr(candidate, "uuid", "") or "").strip() == map_item_uuid
        if is_current:
            current_index = index
        cand_type = str(getattr(candidate, "map_type", "") or "").strip().upper()
        candidate_label = _map_stack_type_short_label(candidate)
        candidate_mode = _map_stack_mode_label(candidate)
        if candidate_mode:
            candidate_label = f"{candidate_label} [{candidate_mode}]"
        if cand_type == map_type and candidate_label == short:
            matching_indices.append(index)
    if len(matching_indices) <= 1:
        return short
    if current_index is None or current_index not in matching_indices:
        return f"{short} #2"
    position = matching_indices.index(current_index)
    if position <= 0:
        return short
    return f"{short} #{position + 1}"


def exact_duplicate_warning_message(project, map_item) -> str:
    duplicates = properties.exact_duplicate_map_settings(project, map_item)
    if not duplicates:
        return ""
    labels = []
    for duplicate in duplicates:
        label = _map_stack_item_label(project, duplicate)
        suffix = properties.effective_map_output_suffix(project, duplicate)
        labels.append(f"{label} ({suffix})" if suffix else label)
    duplicate_names = ", ".join(labels)
    related_maps = [map_item, *duplicates]
    if any(bool(getattr(related, "enabled", False)) for related in related_maps):
        bake_note = "It will repeat the same bake and increase bake time."
    else:
        bake_note = "Enabling more than one will repeat the same bake."
    return f"Exact duplicate of {duplicate_names}. {bake_note}"


def _draw_scene_blockers(layout, map_item) -> None:
    """The project's Scene Blockers, drawn in a lighting row (they shade every lighting row
    that includes other groups)."""
    import bpy

    project = properties.get_active_project(getattr(bpy.context, "scene", None))
    if project is None:
        return
    box = _map_section_box(layout, "Scene Blockers", icon="MESH_PLANE")
    row = box.row(align=True)
    row.prop(project, "use_scene_blockers", text="")
    sub = row.row(align=True)
    sub.active = bool(project.use_scene_blockers)
    sub.prop(project, "scene_blockers", text="")
    toggles = box.row(align=True)
    toggles.active = bool(project.use_scene_blockers and project.scene_blockers)
    toggles.prop(project, "scene_blockers_cast_shadows", toggle=True)
    toggles.prop(project, "scene_blockers_bounce_light", toggle=True)
    if not bool(getattr(map_item, "lighting_occlude_other_groups", True)) and project.scene_blockers:
        box.label(text="Turn on Include Other Groups to use them", icon="INFO")


def _draw_map_property(
    layout,
    map_item,
    property_name: str,
    *,
    text: str | None = None,
    expand: bool = False,
    toggle: bool = False,
    placeholder: str | None = None,
    property_enabled: bool = True,
):
    """Draw a single map property without reset button."""
    prop_row = layout.row(align=True)
    prop_row.enabled = property_enabled
    kwargs: dict[str, object] = {}
    if text is not None:
        kwargs["text"] = text
    if expand:
        kwargs["expand"] = True
    if toggle:
        kwargs["toggle"] = True
    if placeholder is not None:
        kwargs["placeholder"] = placeholder
    prop_row.prop(map_item, property_name, **kwargs)
    return prop_row


def _draw_map_property_pair(
    layout,
    map_item,
    property_name_a: str,
    property_name_b: str,
    *,
    text_a: str | None = None,
    text_b: str | None = None,
    property_enabled: bool = True,
):
    """Draw two float properties side-by-side in a single row without reset buttons."""
    row = layout.row(align=True)
    for prop_name, text in ((property_name_a, text_a), (property_name_b, text_b)):
        col = row.column(align=True)
        col.enabled = property_enabled
        kwargs: dict[str, object] = {}
        if text is not None:
            kwargs["text"] = text
        col.prop(map_item, prop_name, **kwargs)
    return row


def _has_nonzero_distance(map_item, *property_names: str) -> bool:
    """Whether any of the named distance fields is set to something other than 0.

    0 means "no limit" / "pick it automatically" on every one of these fields, and
    a "Relative to Bounds" flag only multiplies them by the model size. With all of
    them at 0 the flag scales nothing, so the checkbox cannot change the bake.
    """
    for property_name in property_names:
        try:
            value = float(getattr(map_item, property_name, 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if value != 0.0:
            return True
    return False


def ao_relative_to_bounds_applies(map_item) -> bool:
    """Whether AO's "Relative to Bounds" has a distance to scale.

    The flag is consumed addon-side (export.prepare_bake_job) by multiplying
    ao_distance and ao_min_distance by the low-poly bounds diagonal. Both at 0 and
    it is a no-op, so the row is hidden rather than drawn dead -- greyed controls
    read as broken, an absent one reads as "not applicable here".
    """
    return _has_nonzero_distance(map_item, "ao_distance", "ao_min_distance")


def curvature_relative_to_bounds_applies(map_item) -> bool:
    """Same rule for the curvature family: the flag scales Radius only."""
    return _has_nonzero_distance(map_item, "curvature_distance")


def _draw_mm_calibration_panel(layout, map_item, *, panel_id: str) -> None:
    """Developer-only calibration for the Marmoset normal-derivative curvature
    response. Hidden unless the Developer Mode preference is on: these are internal
    calibration values, not artist controls, and the shipped defaults are the ones we
    calibrated against Marmoset. Also requires Method == Normal Derivative, the only
    path these knobs affect. The seven values are GLOBAL scene props
    (properties.MM_CALIBRATION_KNOBS) shared by the curvature family. The values flow
    per-bake through the job payload (export.prepare_bake_job), so a change applies on
    the next bake with no worker restart (properties._mm_calibration_update)."""
    if not preferences.developer_mode_enabled():
        return
    method = str(getattr(map_item, "curvature_method", "THICKNESS") or "").strip().upper()
    if method != "NORMAL_DERIVATIVE":
        return
    import bpy

    scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        return
    if hasattr(layout, "panel"):
        header, body = layout.panel(panel_id, default_closed=True)
        header.label(text="Curvature Response", icon="TOOL_SETTINGS")
        if body is None:
            return
    else:
        body = _map_section_box(layout, "Curvature Response", icon="TOOL_SETTINGS")
    body.use_property_split = False
    body.use_property_decorate = False
    knobs = body.column(align=True)
    for prop_name, _env, _default, _lo, _hi in properties.MM_CALIBRATION_KNOBS:
        knobs.prop(settings, prop_name, slider=True)
    body.operator("master_baker.reset_mm_calibration", icon="LOOP_BACK")


def _is_user_facing_material_status(message: str) -> bool:
    """Return True when *message* should appear under the material Channel row.

    Happy-path route notes and leaked IR kinds stay out of the panel; the Route
    enum already says Auto / Fyr / Cycles.
    """
    text = str(message or "").strip()
    if not text:
        return False
    upper = text.upper()
    if upper in {"USING FYR", "USING CYCLES"}:
        return False
    if "EXPRESSION_UV" in upper or "IMAGE_SAMPLE" in upper:
        return False
    if upper.startswith("AUTO:") or upper.startswith("FORCED NATIVE"):
        return False
    return True


def _draw_map_primary_method(layout, map_item, normalized_map_type: str) -> None:
    """Draw the primary algorithm/mode selector at the very top of map settings."""
    if normalized_map_type == constants.MAP_MATERIAL:
        origin = str(getattr(map_item, "material_origin", "") or "")
        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            custom_name = str(getattr(map_item, "material_custom_name", "") or "Custom")
            layout.label(text=custom_name)
            data_type = str(getattr(map_item, "material_data_type", "") or "")
            if data_type == constants.MATERIAL_DATA_VECTOR:
                _draw_map_property(layout, map_item, "material_vector_encoding", text="Encoding")
        else:
            # Dropdown (not an expanded button row): 7 PBR channels are too many buttons to be readable.
            _draw_map_property(layout, map_item, "material_channel", text="Channel")
            if (
                str(getattr(map_item, "material_channel", "") or "").strip().upper()
                == constants.MATERIAL_CHANNEL_ROUGHNESS
            ):
                _draw_map_property(layout, map_item, "roughness_normal_variance")
                if bool(getattr(map_item, "roughness_normal_variance", False)):
                    _draw_map_property(
                        layout, map_item, "roughness_normal_variance_strength", text="Amount"
                    )
        resolve = str(getattr(map_item, "material_resolve_state", "") or "")
        message = str(getattr(map_item, "material_status_message", "") or "").strip()
        if resolve and resolve != constants.MATERIAL_RESOLVE_RESOLVED:
            layout.label(text=message or resolve.title(), icon="INFO")
        elif _is_user_facing_material_status(message):
            layout.label(text=message, icon="INFO")
        _draw_map_property(layout, map_item, "execution_route", text="Route")
    elif normalized_map_type == constants.MAP_SCENE_LIGHTING:
        # Consolidated scene-lighting row: pick the output (Lighting vs Lit Color),
        # mirroring the Material row's channel selector.
        _draw_map_property(layout, map_item, "lighting_output", text="Output", expand=True)
    elif normalized_map_type == constants.MAP_AO:
        _draw_map_property(layout, map_item, "ao_mode", text="Method", expand=True)
    elif normalized_map_type == constants.MAP_NORMAL:
        _draw_map_property(layout, map_item, "normal_space", expand=True)
        if str(getattr(map_item, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT) or "").upper() in {
            "",
            constants.MAP_NORMAL_SPACE_TANGENT,
        }:
            _draw_map_property(layout, map_item, "normal_encoding", expand=True)
        # normal_format (OpenGL / DirectX) now lives in Output settings (over Naming).
    elif normalized_map_type == constants.MAP_CURVATURE:
        _draw_map_property(layout, map_item, "curvature_output_mode", text="Output", expand=True)
        _draw_map_property(layout, map_item, "curvature_method", text="Method")
        output_mode = str(getattr(map_item, "curvature_output_mode", "SIGNED") or "SIGNED").strip().upper()
        if output_mode in {"DIRECTION", "CURVATURE_DIRECTION"}:
            layout.label(text="Direction output: native on Fyr GPU, approximate on Cycles", icon="INFO")
    elif normalized_map_type in {constants.MAP_CONCAVE, constants.MAP_CONVEX}:
        _draw_map_property(layout, map_item, "curvature_method", text="Method")
    elif normalized_map_type == constants.MAP_POSITION:
        _draw_map_property(layout, map_item, "position_mode", text="Method")
    elif normalized_map_type == constants.MAP_ATTRIBUTE:
        _draw_map_property(layout, map_item, "attribute_name", text="Attribute")
    elif normalized_map_type == constants.MAP_WIREFRAME:
        _draw_map_property(layout, map_item, "wireframe_line_width")


def _draw_ao_advanced_settings(layout, map_item, *, panel_id: str) -> None:
    if hasattr(layout, "panel"):
        advanced_header, advanced_body = layout.panel(panel_id, default_closed=True)
        advanced_header.label(text="Advanced", icon="SETTINGS")
        if advanced_body is None:
            return
    else:
        advanced_body = _map_section_box(layout, "Advanced", icon="SETTINGS")
    advanced_body.use_property_split = False
    advanced_body.use_property_decorate = False
    _draw_map_property(advanced_body, map_item, "ao_distribution")
    _draw_map_property(advanced_body, map_item, "ao_spread_angle")
    if ao_relative_to_bounds_applies(map_item):
        _draw_map_property(advanced_body, map_item, "ao_relative_to_bounding_box", text="Relative to Bounds")
    _draw_map_property(advanced_body, map_item, "ao_ignore_backface")
    _draw_map_property(advanced_body, map_item, "ao_self_occlusion")
    _draw_map_property(advanced_body, map_item, "ao_attenuation")
    _draw_map_property(advanced_body, map_item, "ao_use_ground_plane", text="Floor Occlusion")


def _draw_lighting_advanced_settings(layout, map_item, *, panel_id: str) -> None:
    """Advanced panel for scene-lighting maps: contribution toggles, transport
    values (owned by the quality preset unless Custom is selected), and denoise."""
    if hasattr(layout, "panel"):
        advanced_header, advanced_body = layout.panel(panel_id, default_closed=True)
        advanced_header.label(text="Advanced", icon="SETTINGS")
        if advanced_body is None:
            return
    else:
        advanced_body = _map_section_box(layout, "Advanced", icon="SETTINGS")
    advanced_body.use_property_split = False
    advanced_body.use_property_decorate = False

    contrib_row = advanced_body.row(align=True)
    col1 = contrib_row.column(align=True)
    col2 = contrib_row.column(align=True)
    _draw_map_property(col1, map_item, "lighting_direct_enabled")
    _draw_map_property(col2, map_item, "lighting_indirect_enabled")
    contrib_row2 = advanced_body.row(align=True)
    col3 = contrib_row2.column(align=True)
    col4 = contrib_row2.column(align=True)
    _draw_map_property(col3, map_item, "lighting_world_enabled")
    _draw_map_property(col4, map_item, "lighting_emission_enabled")

    # Transport values are owned by the preset unless Quality is Custom.
    # Drawn ENABLED whichever Quality is selected. They used to be disabled unless
    # Quality was Custom, which reads as broken rather than as owned-by-a-preset:
    # Blender mutes a disabled number widget but still lets the click land in some
    # 5.x builds, so the value looked editable, changed, and then snapped back. The
    # preset stays honest because editing any of them promotes Quality to Custom
    # (properties._lighting_transport_update) -- the standard DCC behaviour.
    _draw_map_property(advanced_body, map_item, "lighting_direct_samples")
    _draw_map_property(advanced_body, map_item, "lighting_indirect_paths")
    _draw_map_property(advanced_body, map_item, "lighting_max_bounces")
    _draw_map_property(advanced_body, map_item, "lighting_noise_threshold")

    _draw_map_property(advanced_body, map_item, "denoising_enabled")


def _draw_map_soften(general_box, project, map_item, normalized_map_type: str) -> None:
    """Soften: one project-wide value, per-map override (the Marmoset model).

    The slider shows the PROJECT value, greyed, while the row inherits -- so what the
    panel displays is always what the map bakes at (properties.resolve_map_soften)."""
    if general_box is None or not constants.map_supports_soften(normalized_map_type):
        return
    override = bool(getattr(map_item, "soften_override", False))
    soften_row = general_box.row(align=True)
    toggle_col = soften_row.column(align=True)
    value_col = soften_row.column(align=True)
    toggle_col.prop(map_item, "soften_override", text="Override Soften")
    if override or project is None:
        value_col.enabled = override
        value_col.prop(map_item, "soften", text="")
    else:
        # Inherited: show the project's number rather than this row's stale one.
        value_col.enabled = False
        value_col.prop(project, "soften", text="")


ID_SOURCE_PER_COLLECTION_PLACEHOLDER = "Per Collection"


def _draw_id_source_group_name(map_box, map_item, group) -> None:
    """The bake group's name override for the Collection / Color Set ID sources.

    Empty is valid and the default: the backend then colors each high mesh by its own
    collection (Color Set falls back to the Collection name first). These fields used to
    be drawn only by the unused group editor, so the panel showed an error the user had
    no way to clear. The placeholder shows what an empty field bakes as."""
    if group is None:
        return
    id_source = str(getattr(map_item, "id_source", "") or "")
    collection_name = str(getattr(group, "id_collection_name", "") or "").strip()
    if id_source == constants.MAP_ID_SOURCE_COLLECTION:
        map_box.row(align=True).prop(
            group,
            "id_collection_name",
            text="Collection",
            placeholder=ID_SOURCE_PER_COLLECTION_PLACEHOLDER,
        )
    elif id_source == constants.MAP_ID_SOURCE_COLOR_SET:
        map_box.row(align=True).prop(
            group,
            "id_color_set_name",
            text="Label",
            placeholder=collection_name or ID_SOURCE_PER_COLLECTION_PLACEHOLDER,
        )


def _draw_output_suffix_settings(detail_box, project, map_item, normalized_map_type: str) -> None:
    _draw_map_property(
        detail_box,
        map_item,
        "output_suffix",
        # An Attribute row's file is named after its attribute unless a suffix is typed.
        placeholder=(
            str(getattr(map_item, "attribute_name", "") or "").strip()
            if normalized_map_type == constants.MAP_ATTRIBUTE
            else ""
        )
        # A Derivative row writes <set>_Derivative, not <set>_Normal.
        or naming.map_label(
            constants.MAP_DERIVATIVE if naming.normal_row_is_derivative(map_item) else normalized_map_type
        ),
    )
    if project is not None and _output_suffix_is_duplicate(project, map_item):
        alert_row = detail_box.row(align=True)
        alert_row.alert = True
        alert_row.label(text="Duplicate output name. Maps will overwrite each other.", icon="ERROR")


def _draw_bevel_connected_only(layout, project):
    # One project-wide setting drawn in every map that reads the bevel shader, so
    # toggling it in any of them changes it for all.
    if project is not None:
        layout.row(align=True).prop(project, "bevel_connected_only")


def draw_active_map_settings(layout, project, map_item=None):
    if map_item is None:
        map_item = project
        project = None
    group = properties.peek_active_group(project) if project is not None else None
    normalized_map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()

    detail_box = layout.box()
    detail_box.use_property_split = False
    detail_box.use_property_decorate = False

    header = detail_box.row(align=True)
    header.use_property_split = False
    header.label(text=f"{_map_stack_item_label(project, map_item)} Settings")
    header.operator("master_baker.restore_map_defaults", text="Restore Defaults", icon="LOOP_BACK")

    duplicate_message = exact_duplicate_warning_message(project, map_item)
    if duplicate_message:
        duplicate_row = detail_box.row(align=True)
        duplicate_row.label(text=duplicate_message, **duplicate_warning_icon_kwargs())

    caps = bake_backends.active_capabilities()
    cycles_projection_controls = caps.backend_id == "cycles" and normalized_map_type != constants.MAP_MATERIAL
    if cycles_projection_controls and normalized_map_type == constants.MAP_CURVATURE:
        _draw_map_property(detail_box, map_item, "curvature_output_mode", text="Output", expand=True)
    elif cycles_projection_controls and normalized_map_type == constants.MAP_SCENE_LIGHTING:
        _draw_map_property(detail_box, map_item, "lighting_output", text="Output", expand=True)
    elif not cycles_projection_controls:
        _draw_map_primary_method(detail_box, map_item, normalized_map_type)
    fidelity = caps.map_fidelity.get(normalized_map_type)
    if caps.backend_id == "cycles" and fidelity == "unsupported":
        limit_row = detail_box.row(align=True)
        limit_row.label(text="Not available with Cycles, requires FYR", icon="INFO")
    elif bake_backends.cycles_recovery_unsupported(normalized_map_type):
        # Non-obvious recovery limit: if Fyr GPU fails, these rows cannot hand off to Cycles.
        limit_row = detail_box.row(align=True)
        limit_row.label(text="Requires Fyr GPU, not recoverable via Cycles", icon="INFO")

    ao_mode = str(getattr(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST) or "").strip().upper()
    show_samples = constants.map_uses_samples(normalized_map_type, ao_mode) and bake_backends.control_supported(
        bake_backends.CONTROL_SCOPE_MAP,
        "samples",
        map_type=normalized_map_type,
        capabilities=caps,
    )
    show_material_detail = normalized_map_type in {constants.MAP_NORMAL, constants.MAP_AO} and bake_backends.control_supported(
        bake_backends.CONTROL_SCOPE_MAP,
        "material_detail_mode",
        map_type=normalized_map_type,
        capabilities=caps,
    )
    general_box = (
        _map_section_box(detail_box, "General", icon="PROPERTIES")
        # A Wireframe is drawn, not baked: no rays, denoise or soften to offer.
        if (show_samples or not cycles_projection_controls) and normalized_map_type != constants.MAP_WIREFRAME
        else None
    )
    if show_samples:
        samples_row = general_box.row(align=True)
        samples_row.label(text="", icon_value=sidebar_icons.get_icon_value("ray_count"))
        samples_row.prop(map_item, "samples", text="Rays")

    if show_material_detail:
        material_box = _map_section_box(detail_box, "Material Detail", icon="NODE_MATERIAL")
        material_box.prop(map_item, "material_detail_mode", text="")
        detail_mode = str(
            getattr(map_item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO) or ""
        ).strip().upper()
        if (
            normalized_map_type == constants.MAP_AO
            and detail_mode == constants.MATERIAL_DETAIL_MANUAL
        ):
            material_box.prop(map_item, "material_detail_image", text="Source")
        if normalized_map_type == constants.MAP_NORMAL and detail_mode in {
            constants.MATERIAL_DETAIL_AUTO,
            constants.MATERIAL_DETAIL_MATERIAL_ONLY,
        }:
            material_box.prop(map_item, "normal_relief", text="Relief")

    if cycles_projection_controls:
        _draw_output_suffix_settings(detail_box, project, map_item, normalized_map_type)
        return
    
    # Denoise and Ignore Groups in two-column layout when both present.
    # Scene-lighting maps expose denoise inside their own Advanced panel instead
    # of the compact General row (per the lighting plan's compact-row contract).
    is_lighting_map = normalized_map_type in {constants.MAP_LIGHTING, constants.MAP_LIT_COLOR, constants.MAP_SCENE_LIGHTING}
    has_denoise = normalized_map_type in constants.MAP_DENOISING_SUPPORTED and not is_lighting_map
    if has_denoise and normalized_map_type == constants.MAP_MATERIAL:
        # Encoded-vector material outputs (Normal channel, Vector Custom Output) never
        # denoise — see constants.material_denoise_available.
        has_denoise = constants.material_denoise_available(
            getattr(map_item, "material_channel", ""),
            getattr(map_item, "material_origin", ""),
            getattr(map_item, "material_data_type", ""),
        )
    has_ignore_groups = normalized_map_type in {
        constants.MAP_AO,
        constants.MAP_BENT_NORMAL,
        constants.MAP_CAVITY,
        constants.MAP_THICKNESS,
        constants.MAP_DENSITY,
    }
    if has_denoise and has_ignore_groups:
        checkbox_row = general_box.row(align=True)
        col1 = checkbox_row.column(align=True)
        col2 = checkbox_row.column(align=True)
        _draw_map_property(col1, map_item, "denoising_enabled")
        if normalized_map_type in {constants.MAP_THICKNESS, constants.MAP_DENSITY}:
            _draw_map_property(
                col2,
                map_item,
                "thickness_ignore_groups",
            )
            _draw_map_property(col2, map_item, "ao_occlude_other_groups", text="Include Other Groups")
        else:
            _draw_map_property(col2, map_item, "ao_ignore_groups")
            _draw_map_property(col2, map_item, "ao_occlude_other_groups", text="Occlude Other Groups")
    elif has_denoise:
        _draw_map_property(general_box, map_item, "denoising_enabled")
    elif has_ignore_groups:
        if normalized_map_type in {constants.MAP_THICKNESS, constants.MAP_DENSITY}:
            _draw_map_property(
                general_box,
                map_item,
                "thickness_ignore_groups",
            )
            _draw_map_property(general_box, map_item, "ao_occlude_other_groups", text="Include Other Groups")
        else:
            _draw_map_property(general_box, map_item, "ao_ignore_groups")
            _draw_map_property(general_box, map_item, "ao_occlude_other_groups", text="Occlude Other Groups")

    _draw_map_soften(general_box, project, map_item, normalized_map_type)

    if normalized_map_type == constants.MAP_AO:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        if ao_mode == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE:
            if not bake_backends.active_capabilities().supports_ao_diffusion_solver:
                limit_row = map_box.row(align=True)
                limit_row.label(text="Diffusive AO requires FYR", icon="INFO")
            else:
                distance_box = _map_section_box(map_box, "Distances", icon="DRIVER_DISTANCE")
                _draw_map_property(distance_box, map_item, "ao_distance", text="Radius")
                solver_box = _map_section_box(map_box, "Solver", icon="MOD_FLUIDSIM")
                _draw_map_property(solver_box, map_item, "ao_diffusion_quality")
                _draw_map_property(solver_box, map_item, "ao_diffusion_clearance_scale")
                _draw_map_property(solver_box, map_item, "ao_diffusion_clearance_exponent")
        else:
            _draw_map_property(map_box, map_item, "ao_distribution", text="Distribution", expand=True)
            _draw_map_property_pair(map_box, map_item, "ao_min_distance", "ao_distance", text_b="Max Distance")
            logic_row = map_box.row(align=True)
            col1 = logic_row.column(align=True)
            col2 = logic_row.column(align=True)
            _draw_map_property(col1, map_item, "ao_two_sided")
            _draw_map_property(col2, map_item, "ao_cavity_weight")
            _draw_map_property(map_box, map_item, "ao_bevel_normal")
            _draw_bevel_connected_only(map_box, project)
            _draw_map_property_pair(map_box, map_item, "ao_output_min", "ao_output_max")
            _draw_ao_advanced_settings(map_box, map_item, panel_id=f"MASTER_BAKER_PT_map_ao_advanced_{normalized_map_type}")
    elif normalized_map_type == constants.MAP_BENT_NORMAL:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_map_property(map_box, map_item, "ao_distribution", text="Distribution", expand=True)
        _draw_map_property_pair(map_box, map_item, "ao_min_distance", "ao_distance", text_b="Max Distance")
        logic_row = map_box.row(align=True)
        col1 = logic_row.column(align=True)
        col2 = logic_row.column(align=True)
        _draw_map_property(col1, map_item, "ao_two_sided")
        _draw_map_property(col2, map_item, "ao_cavity_weight")
        _draw_map_property(map_box, map_item, "ao_bevel_normal")
        _draw_bevel_connected_only(map_box, project)
        _draw_ao_advanced_settings(map_box, map_item, panel_id=f"MASTER_BAKER_PT_map_ao_advanced_{normalized_map_type}")
    elif normalized_map_type in {
        constants.MAP_CURVATURE,
        constants.MAP_CONCAVE,
        constants.MAP_CONVEX,
    }:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        response_box = _map_section_box(map_box, "Response", icon="SETTINGS")
        output_mode = str(getattr(map_item, "curvature_output_mode", "SIGNED") or "SIGNED").strip().upper()
        method = str(getattr(map_item, "curvature_method", "NORMAL_DERIVATIVE") or "").strip().upper()
        is_curvature = normalized_map_type == constants.MAP_CURVATURE
        # Painter's "Generate from Mesh" probe. Principal and Direction are ray-probe
        # encodings whichever Method is selected, so the probe controls stay live for
        # them; Geometric and Normal Derivative are texture-space post-processes and
        # ignore them entirely, so they are hidden rather than drawn dead.
        probe_live = method == "MESH_RAYS" or (is_curvature and output_mode in {"PRINCIPAL", "DIRECTION"})
        if probe_live:
            _draw_map_property(response_box, map_item, "curvature_secondary_rays", text="Secondary Rays")
        if curvature_relative_to_bounds_applies(map_item):
            _draw_map_property_pair(
                response_box,
                map_item,
                "curvature_distance",
                "curvature_relative_to_bounding_box",
                text_a="Radius",
                text_b="Relative to Bounds",
            )
        else:
            # Radius 0 picks the distance from the mesh automatically, so there is
            # nothing for Relative to Bounds to scale.
            _draw_map_property(response_box, map_item, "curvature_distance", text="Radius")
        if probe_live:
            # Full-width dropdown: the Painter-style labels ("Only Same Mesh Name") do not
            # fit half a row next to a checkbox.
            _draw_map_property(response_box, map_item, "curvature_self_intersection", text="Self Intersection")
            _draw_map_property(response_box, map_item, "curvature_detect_folds", text="Detect Folds")
        if not is_curvature or output_mode != "DIRECTION":
            _draw_map_property(response_box, map_item, "curvature_scale")
        # Kernel width of the normal-derivative estimate -- NOT the General box's
        # output blur. Geometric derives curvature from hit neighbourhoods and Mesh
        # Rays from the probe, so both ignore it.
        _draw_map_property(
            response_box,
            map_item,
            "curvature_soften",
            property_enabled=method == "NORMAL_DERIVATIVE",
        )
        # Bevel-shader edges at full strength; drawn by the normal-derivative resolve.
        _draw_map_property(
            response_box,
            map_item,
            "curvature_bevel_mask",
            property_enabled=method == "NORMAL_DERIVATIVE" and (not is_curvature or output_mode == "SIGNED"),
        )
        _draw_bevel_connected_only(response_box, project)
        if is_curvature and output_mode == "SIGNED":
            # Signed curvature carries Painter's output range: auto tonemapping fits each
            # UV tile to its own extremes, which makes the fixed bounds inert.
            auto_tonemapping = bool(getattr(map_item, "curvature_auto_tonemapping", False))
            _draw_map_property(response_box, map_item, "curvature_auto_tonemapping")
            _draw_map_property_pair(
                response_box,
                map_item,
                "curvature_value_min",
                "curvature_value_max",
                property_enabled=not auto_tonemapping,
            )
        elif normalized_map_type == constants.MAP_CONCAVE:
            _draw_map_property_pair(response_box, map_item, "curvature_tonemapping_min", "curvature_tonemapping_max")
        _draw_mm_calibration_panel(
            response_box, map_item, panel_id=f"MASTER_BAKER_PT_map_mm_calibration_{normalized_map_type}"
        )
    elif normalized_map_type == constants.MAP_CAVITY:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        response_box = _map_section_box(map_box, "Response", icon="SETTINGS")
        _draw_map_property(response_box, map_item, "curvature_scale")
        # Cavity mask levels. Defaults are
        # neutral (0.0/1.0) so the pass is a no-op until the artist levels the map.
        _draw_map_property_pair(response_box, map_item, "curvature_tonemapping_min", "curvature_tonemapping_max")
        _draw_map_property(response_box, map_item, "curvature_distance", text="Radius")
        if curvature_relative_to_bounds_applies(map_item):
            checkbox_row = response_box.row(align=True)
            col1 = checkbox_row.column(align=True)
            col2 = checkbox_row.column(align=True)
            _draw_map_property(col1, map_item, "curvature_relative_to_bounding_box", text="Relative to Bounds")
            _draw_map_property(col2, map_item, "curvature_detect_folds", text="Detect Folds")
        else:
            # Radius 0 is automatic, so Relative to Bounds has nothing to scale.
            _draw_map_property(response_box, map_item, "curvature_detect_folds", text="Detect Folds")
        # Cavity's probe is always live, so Self Intersection always applies here. Ray
        # Count stays the shared sample control; Cavity has no Secondary Rays of its own.
        _draw_map_property(response_box, map_item, "curvature_self_intersection", text="Self Intersection")
        occlusion_box = _map_section_box(map_box, "Occlusion", icon="MOD_BEVEL")
        _draw_map_property(occlusion_box, map_item, "ao_min_distance")
        _draw_map_property(occlusion_box, map_item, "ao_distance", text="Max Distance")
        _draw_map_property(occlusion_box, map_item, "ao_two_sided")
        _draw_map_property(occlusion_box, map_item, "ao_cavity_weight")
        _draw_ao_advanced_settings(map_box, map_item, panel_id=f"MASTER_BAKER_PT_map_occlusion_advanced_{normalized_map_type}")
    elif normalized_map_type == constants.MAP_THICKNESS:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        distance_box = _map_section_box(map_box, "Distances", icon="DRIVER_DISTANCE")
        _draw_map_property(distance_box, map_item, "thickness_distance")
        _draw_map_property(distance_box, map_item, "thickness_min_distance")
        response_box = _map_section_box(map_box, "Response", icon="SETTINGS")
        _draw_map_property(response_box, map_item, "thickness_scale")
        _draw_map_property(response_box, map_item, "thickness_gamma")
        _draw_map_property(response_box, map_item, "thickness_dither")
        _draw_map_property(response_box, map_item, "thickness_log_response")
        levels_box = _map_section_box(map_box, "Levels", icon="SEQ_HISTOGRAM")
        _draw_map_property(levels_box, map_item, "thickness_normalization")
    elif normalized_map_type == constants.MAP_DENSITY:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        response_box = _map_section_box(map_box, "Response", icon="SETTINGS")
        _draw_map_property(response_box, map_item, "thickness_distance", text="Radius")
        _draw_map_property(response_box, map_item, "thickness_scale", text="Scale")
        _draw_map_property(response_box, map_item, "thickness_gamma", text="Gamma")
        _draw_map_property(response_box, map_item, "thickness_dither")
        levels_box = _map_section_box(map_box, "Levels", icon="SEQ_HISTOGRAM")
        _draw_map_property(levels_box, map_item, "density_auto_levels")
        _draw_map_property(
            levels_box,
            map_item,
            "density_auto_levels_per_group",
            property_enabled=bool(getattr(map_item, "density_auto_levels", False)),
        )
    elif normalized_map_type == constants.MAP_POSITION:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_map_property(map_box, map_item, "position_axis")
        normalization_box = _map_section_box(map_box, "Normalization", icon="PROPERTIES")
        _draw_map_property(normalization_box, map_item, "position_normalization", text="Method")
    elif normalized_map_type == constants.MAP_ENV_LIGHT:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        light_box = _map_section_box(map_box, "Lighting", icon="PROPERTIES")
        _draw_map_property(light_box, map_item, "env_light_intensity")
        _draw_map_property(light_box, map_item, "env_light_contrast")
        _draw_map_property(light_box, map_item, "env_light_up_axis")
        color_box = _map_section_box(map_box, "Colors", icon="PROPERTIES")
        _draw_map_property(color_box, map_item, "env_light_sky_color")
        _draw_map_property(color_box, map_item, "env_light_ground_color")
        occlusion_box = _map_section_box(map_box, "Occlusion", icon="MOD_BEVEL")
        _draw_map_property(occlusion_box, map_item, "ao_min_distance")
        _draw_map_property(occlusion_box, map_item, "ao_distance", text="Max Distance")
        _draw_map_property(occlusion_box, map_item, "env_light_occlusion_strength")
        _draw_ao_advanced_settings(map_box, map_item, panel_id=f"MASTER_BAKER_PT_map_env_advanced_{normalized_map_type}")
    elif normalized_map_type in {constants.MAP_LIGHTING, constants.MAP_LIT_COLOR, constants.MAP_SCENE_LIGHTING}:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_map_property(map_box, map_item, "lighting_quality", text="Quality")
        _draw_map_property(map_box, map_item, "lighting_engine", text="Engine")
        _draw_map_property(map_box, map_item, "lighting_exposure")
        _draw_map_property(map_box, map_item, "lighting_occlude_other_groups")
        _draw_scene_blockers(map_box, map_item)
        _draw_lighting_advanced_settings(map_box, map_item, panel_id=f"MASTER_BAKER_PT_map_lighting_advanced_{normalized_map_type}")
    elif normalized_map_type == constants.MAP_HEIGHT:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        range_box = _map_section_box(map_box, "Range", icon="DRIVER_DISTANCE")
        _draw_map_property(range_box, map_item, "height_inner_distance")
        _draw_map_property(range_box, map_item, "height_outer_distance")
        _draw_map_property(map_box, map_item, "height_dither")
    elif normalized_map_type == constants.MAP_WIREFRAME:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_map_property(map_box, map_item, "wireframe_triangles")
    elif normalized_map_type == constants.MAP_NORMAL:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        if naming.normal_row_is_derivative(map_item):
            _draw_map_property(map_box, map_item, "derivative_max_slope")
        _draw_bevel_connected_only(map_box, project)
    elif normalized_map_type == constants.MAP_OBJECT_NORMAL:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_bevel_connected_only(map_box, project)
    elif normalized_map_type == constants.MAP_ATTRIBUTE:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        range_box = _map_section_box(map_box, "Range", icon="DRIVER_DISTANCE")
        range_row = range_box.row(align=True)
        range_row.prop(map_item, "attribute_range_min", text="Min")
        range_row.prop(map_item, "attribute_range_max", text="Max")
        fit = range_row.operator("master_baker.fit_attribute_range", text="", icon="FULLSCREEN_EXIT")
        fit.map_uuid = str(getattr(map_item, "uuid", "") or "")
    elif normalized_map_type == constants.MAP_ID:
        map_box = _map_section_box(detail_box, "Map Specific", icon=_map_settings_icon(normalized_map_type))
        _draw_map_property(map_box, map_item, "id_source", text="Source")
        _draw_id_source_group_name(map_box, map_item, group)
    # Output Suffix — at the bottom, placeholder shows the default map label.
    _draw_output_suffix_settings(detail_box, project, map_item, normalized_map_type)
