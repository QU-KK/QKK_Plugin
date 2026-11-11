from __future__ import annotations

from . import constants


def _safe_set_preview_map_type(settings, map_type) -> None:
    """Assign the preview dropdown's map type without crashing.

    ``preview_map_type`` is a dynamic enum whose items are only the *baked*
    output types, so values like ``""``, ``MATERIAL`` or ``ID`` (which bake to
    per-channel/other effective types) are never valid members. Assigning one
    raised an unhandled ``TypeError``. The preview itself still works — this only
    keeps the dropdown label in sync — so a rejected value is silently ignored.
    """
    if settings is None:
        return
    try:
        settings.preview_map_type = map_type
    except (TypeError, ValueError):
        pass


def execute_preview_map_output(
    operator,
    context,
    *,
    active_project_or_report_fn,
    resolve_map_source_fn,
    active_group_name_fn,
    preview_on_low_is_active_fn,
    deactivate_preview_on_low_fn,
    activate_preview_on_low_fn,
    activate_preview_on_low_all_groups_fn,
    map_label_fn,
):
    project = active_project_or_report_fn(operator, context)
    if project is None:
        return {"CANCELLED"}

    map_uuid = str(getattr(operator, "map_uuid", "") or "").strip()
    map_type = str(operator.map_type or "").strip().upper()
    output_suffix = str(getattr(operator, "output_suffix", "") or "")

    settings = getattr(context.scene, "fyr_baker_settings", None)

    # Toggle off if already showing this map type across all groups.
    if preview_on_low_is_active_fn(
        settings,
        project,
        map_uuid=map_uuid,
        map_type=map_type,
    ):
        deactivate_preview_on_low_fn(context)
        operator.report({"INFO"}, "Restored low-mesh material preview")
        return {"FINISHED"}

    # Determine scope — operator property overrides session state.
    from . import properties as _properties
    scope = str(getattr(operator, "scope", "") or "").strip().upper()
    if not scope:
        session_state = _properties.preview_session_state(settings) if settings is not None else None
        scope = str(getattr(session_state, "preview_on_low_scope", "") or "").strip().upper()
    if scope == constants.PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP:
        # Active-group-only mode.
        active_gn = str(getattr(operator, "group_name", "") or "").strip() or active_group_name_fn(project)
        if not active_gn:
            operator.report({"ERROR"}, "No active bake group")
            return {"CANCELLED"}
        source = resolve_map_source_fn(
            project,
            map_uuid=map_uuid,
            map_type=map_type,
            group_name=active_gn,
            output_suffix=output_suffix,
            scene=context.scene,
        )
        if source is None or source.get("image") is None:
            operator.report({"ERROR"}, f"No image source is available yet for {map_label_fn(operator.map_type)}")
            return {"CANCELLED"}
        _safe_set_preview_map_type(settings, map_type)
        applied_count = activate_preview_on_low_fn(context, project, source)
        if applied_count <= 0:
            operator.report({"WARNING"}, "No low meshes were available for preview")
            return {"CANCELLED"}
        label = map_label_fn(operator.map_type)
        operator.report({"INFO"}, f"Showing {label} on {applied_count} low mesh(es) (active group)")
        return {"FINISHED"}

    # Default: all-groups mode.
    # Collect all group names first, then resolve images.
    all_group_names = [
        str(getattr(g, "name", "") or "")
        for g in getattr(project, "groups", [])
        if str(getattr(g, "name", "") or "")
    ]
    resolved_images: dict[str, object] = {}  # group_name -> image
    resolved_targets: dict[str, object] = {}  # group_name -> tracked output target
    for gn in all_group_names:
        source = resolve_map_source_fn(
            project,
            map_uuid=map_uuid,
            map_type=map_type,
            group_name=gn,
            output_suffix=output_suffix,
            scene=context.scene,
        )
        if source is not None and source.get("image") is not None:
            resolved_images[gn] = source["image"]
            resolved_targets[gn] = source.get("target")

    # Only groups that resolved an image of their own are previewed. A group whose
    # output genuinely lives under a shared texture-set stem already resolves through
    # `_candidate_output_group_names`, which walks the group's own texture set and its
    # siblings. There used to be a blanket fallback here that handed the FIRST resolved
    # image to every group that failed — that painted model A's albedo/metalness onto
    # model B's low mesh whenever B had not baked that map yet, which reads as "the
    # preview showed the wrong material on the wrong object".
    per_group_sources = []
    for gn in all_group_names:
        image = resolved_images.get(gn)
        if image is None:
            continue
        # The resolved target carries the EFFECTIVE type (MATERIAL_ALBEDO for a
        # Material row whose base type is MATERIAL). The preview material derives
        # the image colorspace from this string, and MATERIAL alone reads as
        # Non-Color, so an Albedo preview rendered washed out on every low.
        per_group_sources.append({
            "group_name": gn,
            "image": image,
            "map_type": str(getattr(resolved_targets.get(gn), "map_type", "") or map_type),
        })

    if not per_group_sources:
        operator.report({"ERROR"}, f"No image source is available yet for {map_label_fn(operator.map_type)}")
        return {"CANCELLED"}

    _safe_set_preview_map_type(settings, map_type)
    applied_count, _has_sources = activate_preview_on_low_all_groups_fn(
        context,
        project,
        map_uuid=map_uuid,
        map_type=map_type,
        per_group_sources=per_group_sources,
    )
    if applied_count <= 0:
        operator.report({"WARNING"}, "No low meshes were available for preview")
        return {"CANCELLED"}

    label = map_label_fn(operator.map_type)
    skipped = len(all_group_names) - len(per_group_sources)
    message = f"Showing {label} on {applied_count} low mesh(es)"
    if skipped > 0:
        # Say so rather than borrowing another group's image for them.
        message += f" ({skipped} group(s) have no {label} baked yet)"
    operator.report({"INFO"}, message)
    return {"FINISHED"}


def execute_preview_pbr_output(
    operator,
    context,
    *,
    active_project_or_report_fn,
    active_group_name_fn,
    preview_pbr_on_low_is_active_fn,
    deactivate_preview_on_low_fn,
    resolve_pbr_preview_inputs_fn,
    activate_preview_pbr_on_low_fn,
    activate_preview_pbr_on_low_all_groups_fn,
):
    project = active_project_or_report_fn(operator, context)
    if project is None:
        return {"CANCELLED"}

    settings = getattr(context.scene, "fyr_baker_settings", None)
    group_name = str(getattr(operator, "group_name", "") or "").strip()

    if preview_pbr_on_low_is_active_fn(settings, project, group_name=group_name):
        from . import preview_materials

        # The flag can outlive the material: unregistering the addon (an extension
        # update, a reload) puts the artist's materials back but keeps the saved flag.
        # Then this click only cleared the flag and nothing visible happened. Clear
        # it either way, and only stop here when a preview was really on screen.
        was_showing = preview_materials.any_preview_material_applied()
        deactivate_preview_on_low_fn(context)
        if was_showing:
            operator.report({"INFO"}, "Restored low-mesh material preview")
            return {"FINISHED"}

    if group_name:
        applied_count, has_inputs = activate_preview_pbr_on_low_fn(
            context,
            project,
            group_name=group_name,
        )
        if not has_inputs:
            operator.report({"ERROR"}, f"No Normal or AO image sources are available yet for {group_name}")
            return {"CANCELLED"}
        if applied_count <= 0:
            operator.report({"WARNING"}, f"No low meshes were available for {group_name}")
            return {"CANCELLED"}
        operator.report({"INFO"}, f"Showing PBR preview on {applied_count} low mesh(es) ({group_name})")
        return {"FINISHED"}

    applied_count, has_inputs = activate_preview_pbr_on_low_all_groups_fn(
        context,
        project,
    )
    if not has_inputs:
        operator.report({"ERROR"}, "No Normal or AO image sources are available for any group")
        return {"CANCELLED"}
    if applied_count <= 0:
        operator.report({"WARNING"}, "No low meshes were available for PBR preview")
        return {"CANCELLED"}

    operator.report({"INFO"}, f"Showing PBR preview on {applied_count} low mesh(es)")
    return {"FINISHED"}


def execute_toggle_live_normal_preview(
    operator,
    context,
    *,
    cage_target_project_group_or_report_fn,
    live_normal_preview_is_active_fn,
    deactivate_preview_on_low_fn,
    activate_live_normal_preview_fn,
):
    project, group = cage_target_project_group_or_report_fn(operator, context)
    if project is None or group is None:
        return {"CANCELLED"}

    settings = getattr(context.scene, "fyr_baker_settings", None)
    group_name = str(getattr(group, "name", "") or "")
    if live_normal_preview_is_active_fn(settings, project, group_name=group_name):
        deactivate_preview_on_low_fn(context)
        operator.report({"INFO"}, "Restored low-mesh material preview")
        return {"FINISHED"}

    applied_count = activate_live_normal_preview_fn(context, project, group)
    if applied_count <= 0:
        operator.report({"WARNING"}, f"No low meshes were available for {group_name or 'the active group'}")
        return {"CANCELLED"}
    operator.report({"INFO"}, f"Live normal preview active on {applied_count} low mesh(es)")
    return {"FINISHED"}
