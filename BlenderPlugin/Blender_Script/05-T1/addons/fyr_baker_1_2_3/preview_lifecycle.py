from __future__ import annotations

from . import properties


def iter_loaded_scenes(*, data_scenes, context_scene):
    if data_scenes is not None:
        for scene in data_scenes:
            if scene is not None:
                yield scene
        return
    if context_scene is not None:
        yield context_scene


def resolve_preview_material_target(scene, project, *, preview_on_low_is_active_fn, resolve_map_source_fn):
    settings = getattr(scene, "fyr_baker_settings", None)
    if not preview_on_low_is_active_fn(settings, project):
        return None
    session_state = properties.preview_session_state(settings)
    group_name = str(getattr(session_state, "preview_on_low_group_name", "") or "")
    if not group_name:
        return None  # All-groups mode — let caller handle per-group resolution
    return resolve_map_source_fn(
        project,
        map_uuid=str(getattr(session_state, "preview_on_low_map_uuid", "") or ""),
        map_type=str(getattr(session_state, "preview_on_low_map_type", "") or ""),
        group_name=group_name,
        output_suffix=str(getattr(session_state, "preview_on_low_output_suffix", "") or ""),
    )


def resolve_live_normal_preview_state(scene, project, *, live_normal_preview_is_active_fn, resolve_live_normal_preview_source_fn):
    settings = getattr(scene, "fyr_baker_settings", None)
    if not live_normal_preview_is_active_fn(settings, project):
        return None
    return resolve_live_normal_preview_source_fn(scene, project)


def resolve_pbr_preview_state(scene, project, *, preview_pbr_on_low_is_active_fn, resolve_pbr_preview_inputs_fn):
    settings = getattr(scene, "fyr_baker_settings", None)
    if not preview_pbr_on_low_is_active_fn(settings, project):
        return None
    session_state = properties.preview_session_state(settings)
    group_name = str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "")
    if group_name:
        return resolve_pbr_preview_inputs_fn(project, group_name)
    # All-groups mode: return a list of per-group inputs
    groups = list(getattr(project, "groups", []))
    if not groups:
        return None
    per_group = []
    for group in groups:
        gn = str(getattr(group, "name", "") or "")
        if not gn:
            continue
        inputs = resolve_pbr_preview_inputs_fn(project, gn)
        if (
            inputs["normal_source"] is None
            and inputs["ao_source"] is None
            and inputs["curvature_source"] is None
            and not any(dict(inputs.get("material_images", {}) or {}).values())
        ):
            continue
        per_group.append(inputs)
    if not per_group:
        return None
    return per_group


def sync_preview_material_for_project(
    scene,
    project,
    *,
    any_preview_on_low_is_active_fn,
    preview_on_low_is_active_fn,
    preview_on_low_project_name_fn,
    live_normal_preview_is_active_fn,
    resolve_live_normal_preview_state_fn,
    resolve_pbr_preview_state_fn,
    clear_preview_on_low_state_fn,
    resolve_preview_material_target_fn,
    apply_preview_output_fn,
    apply_preview_output_all_groups_fn=None,
    resolve_map_source_fn=None,
    apply_preview_pbr_output_fn,
    apply_preview_pbr_output_all_groups_fn,
    restore_preview_materials_fn,
    is_bake_running_fn=None,
) -> int:
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is not None and any_preview_on_low_is_active_fn(settings):
        session_state = properties.preview_session_state(settings)
        preview_project_name = str(
            getattr(session_state, "preview_pbr_on_low_project_name", "")
            or getattr(session_state, "preview_on_low_project_name", "")
            or getattr(session_state, "live_normal_preview_project_name", "")
            or ""
        )
        if preview_project_name and preview_project_name != preview_on_low_project_name_fn(project):
            return 0
    live_preview_state = resolve_live_normal_preview_state_fn(scene, project)
    if live_normal_preview_is_active_fn(settings, project):
        if live_preview_state is None:
            return 0
        return apply_preview_output_fn(project, live_preview_state["target"], live_preview_state["image"])
    pbr_state = resolve_pbr_preview_state_fn(scene, project)
    if pbr_state is not None:
        if isinstance(pbr_state, list):
            per_group_inputs = []
            for inputs in pbr_state:
                normal_source = inputs["normal_source"]
                ao_source = inputs["ao_source"]
                curvature_source = inputs["curvature_source"]
                material_images = dict(inputs.get("material_images", {}) or {})
                if normal_source is None and ao_source is None and curvature_source is None and not any(material_images.values()):
                    continue
                per_group_inputs.append({
                    "group_name": str(inputs["group_name"] or ""),
                    "normal_image": normal_source["image"] if normal_source is not None else None,
                    "ao_image": ao_source["image"] if ao_source is not None else None,
                    "curvature_image": curvature_source["image"] if curvature_source is not None else None,
                    **{f"{channel}_image": image for channel, image in material_images.items()},
                    "normal_space": str(inputs["normal_space"] or ""),
                    "normal_format": str(inputs["normal_format"] or ""),
                    "flip_green": bool(inputs["flip_green"]),
                    "ao_strength": float(inputs.get("ao_strength", 1.0)),
                })
            if not per_group_inputs:
                if is_bake_running_fn is not None and is_bake_running_fn():
                    return 0
                clear_preview_on_low_state_fn(settings)
                return restore_preview_materials_fn()
            return apply_preview_pbr_output_all_groups_fn(
                project,
                per_group_inputs=per_group_inputs,
            )
        normal_source = pbr_state["normal_source"]
        ao_source = pbr_state["ao_source"]
        curvature_source = pbr_state["curvature_source"]
        material_images = dict(pbr_state.get("material_images", {}) or {})
        if normal_source is None and ao_source is None and curvature_source is None and not any(material_images.values()):
            if is_bake_running_fn is not None and is_bake_running_fn():
                return 0
            clear_preview_on_low_state_fn(settings)
            return restore_preview_materials_fn()
        return apply_preview_pbr_output_fn(
            project,
            group_name=str(pbr_state["group_name"] or ""),
            normal_image=normal_source["image"] if normal_source is not None else None,
            ao_image=ao_source["image"] if ao_source is not None else None,
            curvature_image=curvature_source["image"] if curvature_source is not None else None,
            **{f"{channel}_image": image for channel, image in material_images.items()},
            normal_space=str(pbr_state["normal_space"] or ""),
            normal_format=str(pbr_state["normal_format"] or ""),
            flip_green=bool(pbr_state["flip_green"]),
            ao_strength=float(pbr_state.get("ao_strength", 1.0)),
        )
    source = resolve_preview_material_target_fn(scene, project)
    if source is None:
        # All-groups mode: stored group_name is empty, resolve for every group.
        if (
            settings is not None
            and preview_on_low_is_active_fn(settings, project)
            and apply_preview_output_all_groups_fn is not None
            and resolve_map_source_fn is not None
        ):
            session_state = properties.preview_session_state(settings)
            stored_group = str(getattr(session_state, "preview_on_low_group_name", "") or "")
            if not stored_group:
                map_uuid = str(getattr(session_state, "preview_on_low_map_uuid", "") or "")
                map_type = str(getattr(session_state, "preview_on_low_map_type", "") or "")
                output_suffix = str(getattr(session_state, "preview_on_low_output_suffix", "") or "")
                all_group_names = [
                    str(getattr(g, "name", "") or "")
                    for g in getattr(project, "groups", [])
                    if str(getattr(g, "name", "") or "")
                ]
                resolved_images: dict[str, object] = {}
                resolved_targets: dict[str, object] = {}
                for gn in all_group_names:
                    src = resolve_map_source_fn(
                        project,
                        map_uuid=map_uuid,
                        map_type=map_type,
                        group_name=gn,
                        output_suffix=output_suffix,
                    )
                    if src is not None and src.get("image") is not None:
                        resolved_images[gn] = src["image"]
                        resolved_targets[gn] = src.get("target")
                # No cross-group fallback: a group that never baked this map keeps its
                # own materials. The operator path already dropped the fallback after
                # it painted model A's albedo onto model B's low mesh; this resync ran
                # after every bake and reintroduced exactly that.
                per_group_sources = []
                for gn in all_group_names:
                    image = resolved_images.get(gn)
                    if image is None:
                        continue
                    per_group_sources.append({
                        "group_name": gn,
                        "image": image,
                        # Effective type (MATERIAL_ALBEDO, not MATERIAL): the colorspace
                        # the preview material applies is derived from it.
                        "map_type": str(getattr(resolved_targets.get(gn), "map_type", "") or map_type),
                    })
                if per_group_sources:
                    return apply_preview_output_all_groups_fn(project, per_group_sources=per_group_sources)
                if is_bake_running_fn is not None and is_bake_running_fn():
                    return 0
                clear_preview_on_low_state_fn(settings)
                return restore_preview_materials_fn()
        if settings is not None and not preview_on_low_is_active_fn(settings, project):
            return restore_preview_materials_fn()
        if is_bake_running_fn is not None and is_bake_running_fn():
            return 0
        clear_preview_on_low_state_fn(settings)
        return restore_preview_materials_fn()
    return apply_preview_output_fn(project, source["target"], source["image"])


def load_post(
    _dummy,
    *,
    reset_live_bake_runtime_on_load_fn,
    restore_preview_materials_fn,
    context,
    data_scenes,
    clear_live_bake_state_fn,
    remove_phantom_map_items_fn,
    capture_view3d_shading_state_fn,
    any_preview_on_low_is_active_fn,
    sync_preview_material_for_project_fn,
    clear_preview_on_low_state_fn,
    apply_preview_on_low_viewport_state_fn,
    tag_redraw_all_view3d_fn,
) -> None:
    reset_live_bake_runtime_on_load_fn()
    restore_preview_materials_fn()
    context_scene = getattr(context, "scene", None) if context is not None else None
    active_window = getattr(context, "window", None) if context is not None else None

    for scene in iter_loaded_scenes(data_scenes=data_scenes, context_scene=context_scene):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        clear_live_bake_state_fn(settings)
        for project in getattr(settings, "projects", []):
            remove_phantom_map_items_fn(project)
        if scene is context_scene and context is not None:
            properties.preview_session_state(settings).preview_on_low_restore_viewport_state = capture_view3d_shading_state_fn(context)
        if not any_preview_on_low_is_active_fn(settings):
            continue

        reapplied = 0
        for project in getattr(settings, "projects", []):
            reapplied = sync_preview_material_for_project_fn(scene, project)
            if reapplied > 0:
                break
        if reapplied <= 0:
            clear_preview_on_low_state_fn(settings)
            continue
        if scene is context_scene and context is not None:
            apply_preview_on_low_viewport_state_fn(context)

    tag_redraw_all_view3d_fn(scene=context_scene, window=active_window, sync_preview=False)


def save_pre(
    _dummy,
    *,
    context,
    data_scenes,
    any_preview_on_low_is_active_fn,
    has_overridden_preview_materials_fn,
    clear_preview_on_low_state_fn,
    restore_preview_on_low_overlay_state_fn,
    restore_preview_on_low_viewport_state_fn,
    restore_preview_materials_fn,
    tag_redraw_all_view3d_fn,
) -> None:
    context_scene = getattr(context, "scene", None) if context is not None else None
    preview_was_overridden = has_overridden_preview_materials_fn()
    for scene in iter_loaded_scenes(data_scenes=data_scenes, context_scene=context_scene):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None or not any_preview_on_low_is_active_fn(settings):
            continue
        restore_preview_on_low_overlay_state_fn(settings)
        if scene is context_scene and context is not None:
            restore_preview_on_low_viewport_state_fn(context, settings)
        if preview_was_overridden:
            # A user-selected material wins over stale preview session state.  Without
            # clearing the session, save_post would immediately assign Fyr's material
            # again after Ctrl+S.
            clear_preview_on_low_state_fn(settings)
    restore_preview_materials_fn()
    tag_redraw_all_view3d_fn(
        scene=context_scene,
        window=getattr(context, "window", None) if context is not None else None,
        sync_preview=False,
    )


def save_post(
    _dummy,
    *,
    context,
    data_scenes,
    any_preview_on_low_is_active_fn,
    apply_runtime_preview_overlay_state_fn,
    apply_preview_on_low_viewport_state_fn,
    sync_preview_material_for_project_fn,
    tag_redraw_all_view3d_fn,
) -> None:
    context_scene = getattr(context, "scene", None) if context is not None else None
    active_window = getattr(context, "window", None) if context is not None else None

    for scene in iter_loaded_scenes(data_scenes=data_scenes, context_scene=context_scene):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None or not any_preview_on_low_is_active_fn(settings):
            continue
        apply_runtime_preview_overlay_state_fn(settings)
        if scene is context_scene and context is not None:
            apply_preview_on_low_viewport_state_fn(context)
        for project in getattr(settings, "projects", []):
            sync_preview_material_for_project_fn(scene, project)

    tag_redraw_all_view3d_fn(scene=context_scene, window=active_window, sync_preview=False)
