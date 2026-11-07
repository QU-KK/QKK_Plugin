from __future__ import annotations

from pathlib import Path
import types

import bpy

from . import constants, properties, runtime


def abspath(path_value: str) -> str:
    value = str(path_value or "").strip()
    if not value:
        return ""
    bpy_abspath = getattr(getattr(bpy, "path", None), "abspath", None)
    if callable(bpy_abspath):
        try:
            return str(bpy_abspath(value) or "").strip()
        except Exception:
            pass
    return value


def image_source_path(image, *, abspath_fn=abspath) -> str:
    if image is None:
        return ""
    return abspath_fn(str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or ""))


def image_source_label(image, *, image_source_path_fn=image_source_path) -> str:
    if image is None:
        return ""
    resolved_path = image_source_path_fn(image)
    if resolved_path:
        return Path(resolved_path).name
    return str(getattr(image, "name", "") or "Image")


def refresh_source_image(image, *, image_source_path_fn=image_source_path):
    if image is None:
        return None
    resolved_path = image_source_path_fn(image)
    if resolved_path and hasattr(image, "reload"):
        try:
            image.reload()
        except Exception:
            pass
    return image


def resolve_output_target(
    project,
    *,
    output_index: int = -1,
    map_uuid: str = "",
    map_type: str = "",
    group_name: str = "",
    output_suffix: str = "",
    strict: bool = False,
):
    resolved_index = properties.resolve_output_selection_index(
        project,
        output_index=output_index,
        map_uuid=map_uuid,
        map_type=map_type,
        group_name=group_name,
        output_suffix=output_suffix,
        strict=strict,
    )
    if resolved_index is None:
        return None, None
    target = properties.peek_latest_output(project, resolved_index)
    if target is None:
        return None, None
    normalized_group_name = str(group_name or "").strip().casefold()
    if strict and normalized_group_name:
        target_group_name = str(getattr(target, "group_name", "") or "").strip().casefold()
        if target_group_name != normalized_group_name:
            return None, None
    return target, resolved_index


def resolve_live_normal_preview_source(scene, project, *, live_normal_preview_is_active_fn):
    settings = getattr(scene, "fyr_baker_settings", None)
    if not live_normal_preview_is_active_fn(settings, project):
        return None
    session_state = properties.preview_session_state(settings)
    raw_output_path = str(getattr(session_state, "live_normal_preview_output_path", "") or "").strip()
    if not raw_output_path:
        return None
    output_path = Path(raw_output_path)
    if not output_path.exists() or not output_path.is_file():
        return None
    group_name = str(getattr(session_state, "live_normal_preview_group_name", "") or "")
    target = types.SimpleNamespace(
        group_name=group_name,
        map_type=constants.MAP_NORMAL,
        file_path=str(output_path),
        display_name=output_path.name,
    )
    return {
        "source_kind": "live_preview",
        "target": target,
        "resolved_index": None,
        "image": runtime.load_managed_output_image(output_path),
        "display_name": output_path.name,
        "file_path": str(output_path),
    }


def _group_texture_set_name(project, group_name: str) -> str:
    target_name = str(group_name or "").strip().casefold()
    if not target_name:
        return ""
    for group in getattr(project, "groups", []):
        current_name = str(getattr(group, "name", "") or "").strip().casefold()
        if current_name != target_name:
            continue
        metadata_state = properties.group_metadata_state(group)
        return str(getattr(metadata_state, "texture_set_name", "") or "").strip()
    return ""


def _texture_set_sibling_group_names(project, group_name: str) -> list[str]:
    normalized_group_name = str(group_name or "").strip()
    if not normalized_group_name:
        return []

    texture_set_name = _group_texture_set_name(project, normalized_group_name)
    if not texture_set_name:
        return []

    siblings: list[str] = []
    for group in getattr(project, "groups", []):
        current_group_name = str(getattr(group, "name", "") or "").strip()
        if not current_group_name or current_group_name.casefold() == normalized_group_name.casefold():
            continue
        metadata_state = properties.group_metadata_state(group)
        current_texture_set_name = str(getattr(metadata_state, "texture_set_name", "") or "").strip()
        if current_texture_set_name.casefold() != texture_set_name.casefold():
            continue
        siblings.append(current_group_name)
    return siblings


def _candidate_output_group_names(project, group_name: str) -> list[str]:
    normalized_group_name = str(group_name or "").strip()
    if not normalized_group_name:
        return [""]

    candidates = [normalized_group_name]
    texture_set_name = _group_texture_set_name(project, normalized_group_name)
    if texture_set_name and texture_set_name.casefold() != normalized_group_name.casefold():
        candidates.append(texture_set_name)
    for sibling_group_name in _texture_set_sibling_group_names(project, normalized_group_name):
        if sibling_group_name.casefold() in {candidate.casefold() for candidate in candidates}:
            continue
        candidates.append(sibling_group_name)
    return candidates


def _filename_case_matches_disk(resolved_path: Path) -> bool:
    """Whether the file on disk is spelled exactly like *resolved_path*."""
    try:
        parent = resolved_path.parent
        if not parent.is_dir():
            return True
        return resolved_path.name in {entry.name for entry in parent.iterdir()}
    except Exception:
        return True


def _path_is_under(candidate: Path, root: Path) -> bool:
    try:
        resolved_candidate = Path(candidate).resolve()
        resolved_root = Path(root).resolve()
    except Exception:
        return False
    if resolved_candidate == resolved_root:
        return True
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError:
        return False
    return True


def preview_output_roots(project, *, abspath_fn=abspath) -> list[Path]:
    """Folders preview may load from: last bake destination, then configured output dir."""
    roots: list[Path] = []
    seen: set[str] = set()

    def _add(raw_path) -> None:
        text = str(raw_path or "").strip()
        if not text:
            return
        try:
            root = Path(abspath_fn(text)).resolve()
        except Exception:
            return
        try:
            if not root.is_dir():
                return
        except Exception:
            return
        key = str(root)
        if key in seen:
            return
        seen.add(key)
        roots.append(root)

    _add(getattr(project, "last_output_dir", "") or "")
    try:
        from . import export

        _add(export.resolved_project_output_dir(project))
    except Exception:
        pass
    return roots


def _any_tracked_output_under_roots(project, roots: list[Path], *, abspath_fn=abspath) -> bool:
    if not roots:
        return False
    for item in getattr(project, "latest_outputs", []) or ():
        raw = str(getattr(item, "file_path", "") or "").strip()
        if not raw:
            continue
        try:
            candidate = Path(abspath_fn(raw)).resolve()
        except Exception:
            continue
        if any(_path_is_under(candidate, root) for root in roots):
            return True
    return False


def resolve_preview_output_path(
    project,
    tracked_path: Path | str,
    *,
    abspath_fn=abspath,
    roots: list[Path] | None = None,
) -> Path | None:
    """Pick the file Show-on-Low should load for a tracked output.

    Prefer a same-named file in the folder this project writes to today. That way a
    leftover ``latest_outputs`` path from an earlier bake folder cannot hide a
    current bake, and cannot mix PBR channels across folders. If the current
    folder has not received any tracked outputs yet, keep using the tracked file
    that still exists — otherwise a redirected output folder greys out a working
    thumbnail and reports "No image source".
    """
    raw = str(tracked_path or "").strip()
    if not raw:
        return None
    try:
        tracked = Path(abspath_fn(raw))
    except Exception:
        tracked = Path(raw)

    if roots is None:
        roots = preview_output_roots(project, abspath_fn=abspath_fn)

    tracked_exists = False
    try:
        tracked_exists = tracked.is_file()
    except Exception:
        tracked_exists = False

    def _accept(candidate: Path) -> Path | None:
        try:
            if not candidate.is_file():
                return None
        except Exception:
            return None
        if not _filename_case_matches_disk(candidate):
            return None
        return candidate

    if roots:
        for root in roots:
            if tracked_exists and _path_is_under(tracked, root):
                accepted = _accept(tracked)
                if accepted is not None:
                    return accepted
                return None
            accepted = _accept(root / tracked.name)
            if accepted is not None:
                return accepted
        if tracked_exists and not _any_tracked_output_under_roots(project, roots, abspath_fn=abspath_fn):
            return _accept(tracked)
        return None

    return _accept(tracked) if tracked_exists else None


def resolve_map_source(
    project,
    *,
    map_uuid: str = "",
    map_type: str = "",
    group_name: str = "",
    output_suffix: str = "",
    scene=None,
    active_group_name_fn,
    resolve_live_normal_preview_source_fn,
    refresh_source_image_fn,
    resolve_output_target_fn,
    image_source_path_fn,
    image_source_label_fn,
    abspath_fn=abspath,
):
    normalized_map_uuid = str(map_uuid or "").strip()
    normalized_map_type = str(map_type or "").strip().upper()
    normalized_group_name = str(group_name or active_group_name_fn(project) or "")
    normalized_suffix = str(output_suffix or "").strip()
    map_setting = None
    if normalized_map_uuid:
        map_setting = properties.find_map_setting_by_uuid(project, normalized_map_uuid)
        if map_setting is None:
            return None
    elif normalized_suffix:
        map_setting = properties.resolve_map_setting(
            project,
            map_type=normalized_map_type,
            output_suffix=normalized_suffix,
        )

    if map_setting is not None:
        normalized_map_uuid = properties.ensure_map_setting_uuid(map_setting)
        normalized_map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
        normalized_suffix = properties.effective_map_output_suffix(project, map_setting) or ""

    if scene is not None and normalized_map_type == constants.MAP_NORMAL:
        live_preview_source = resolve_live_normal_preview_source_fn(scene, project)
        if (
            live_preview_source is not None
            and str(getattr(live_preview_source["target"], "group_name", "") or "") == normalized_group_name
        ):
            return live_preview_source
    target = None
    resolved_index = None
    resolved_group_name = normalized_group_name
    resolved_file_path = None
    preview_roots = preview_output_roots(project, abspath_fn=abspath_fn)
    for candidate_group_name in _candidate_output_group_names(project, normalized_group_name):
        candidate_target, candidate_resolved_index = resolve_output_target_fn(
            project,
            map_uuid=normalized_map_uuid,
            map_type=normalized_map_type,
            group_name=candidate_group_name,
            output_suffix=normalized_suffix,
            strict=bool(candidate_group_name),
        )
        if candidate_target is None:
            continue
        candidate_file_path = str(getattr(candidate_target, "file_path", "") or "").strip()
        if not candidate_file_path:
            continue
        candidate_preview_path = resolve_preview_output_path(
            project,
            Path(abspath_fn(candidate_file_path)),
            abspath_fn=abspath_fn,
            roots=preview_roots,
        )
        if candidate_preview_path is None:
            continue
        target = candidate_target
        resolved_index = candidate_resolved_index
        resolved_group_name = candidate_group_name
        resolved_file_path = candidate_preview_path
        break
    if target is None or resolved_file_path is None:
        return None
    file_path_str = str(resolved_file_path)
    preview_target = target
    needs_retarget_wrapper = file_path_str != str(getattr(target, "file_path", "") or "").strip()
    needs_group_wrapper = bool(
        normalized_group_name
        and resolved_group_name
        and resolved_group_name.casefold() != normalized_group_name.casefold()
    )
    if needs_retarget_wrapper or needs_group_wrapper:
        preview_target = types.SimpleNamespace(
            group_name=normalized_group_name or str(getattr(target, "group_name", "") or ""),
            map_type=str(getattr(target, "map_type", "") or normalized_map_type),
            file_path=file_path_str,
            display_name=str(getattr(target, "display_name", "") or ""),
            output_suffix=str(getattr(target, "output_suffix", "") or normalized_suffix),
            map_uuid=str(getattr(target, "map_uuid", "") or normalized_map_uuid),
        )
    return {
        "source_kind": "tracked",
        "target": preview_target,
        "resolved_index": resolved_index,
        "image": runtime.load_managed_output_image(file_path_str),
        "map_setting": map_setting,
        "map_uuid": normalized_map_uuid,
        "display_name": resolved_file_path.name,
        "file_path": file_path_str,
    }


def resolve_pbr_preview_inputs(project, group_name: str, *, resolve_map_source_fn, normal_map_type=None, ao_strength=1.0) -> dict:
    # The PBR preview can use either the tangent Normal or the Bent Normal map as the
    # surface normal (the UI's Tangent/Bent toggle). Resolve the image and its normal
    # settings from the requested type — previously this always pulled the tangent
    # Normal map, so selecting "Bent Normal" only relabelled the preview.
    resolved_normal_map_type = str(normal_map_type or constants.MAP_NORMAL).strip().upper() or constants.MAP_NORMAL
    normal_source = resolve_map_source_fn(project, map_type=resolved_normal_map_type, group_name=group_name)
    if normal_source is None and resolved_normal_map_type == constants.MAP_NORMAL:
        # A material-only project has no geometry Normal map, but it may well have a
        # Material -> Normal channel, which is the surface normal for that texture set.
        # Without this the preview showed no normal at all (and, before the recorded
        # outputs were checked against the current folder, silently wired a normal map
        # from an earlier bake instead).
        material_normal = resolve_map_source_fn(
            project, map_type=constants.MAP_MATERIAL_NORMAL, group_name=group_name
        )
        if material_normal is not None:
            resolved_normal_map_type = constants.MAP_MATERIAL_NORMAL
            normal_source = material_normal
    ao_source = resolve_map_source_fn(project, map_type=constants.MAP_AO, group_name=group_name)
    curvature_source = resolve_map_source_fn(project, map_type=constants.MAP_CURVATURE, group_name=group_name)
    material_map_types = {
        "albedo": constants.MAP_MATERIAL_ALBEDO,
        "roughness": constants.MAP_MATERIAL_ROUGHNESS,
        "metalness": constants.MAP_MATERIAL_METALNESS,
        "emission": constants.MAP_MATERIAL_EMISSION,
        "opacity": constants.MAP_MATERIAL_OPACITY,
        "specular": constants.MAP_MATERIAL_SPECULAR,
        "transmission": constants.MAP_MATERIAL_TRANSMISSION,
    }
    material_sources = {
        channel: resolve_map_source_fn(project, map_type=map_type, group_name=group_name)
        for channel, map_type in material_map_types.items()
    }
    normal_target = normal_source["target"] if normal_source is not None else None
    normal_index = normal_source["resolved_index"] if normal_source is not None else None
    ao_target = ao_source["target"] if ao_source is not None else None
    ao_index = ao_source["resolved_index"] if ao_source is not None else None
    curvature_target = curvature_source["target"] if curvature_source is not None else None
    curvature_index = curvature_source["resolved_index"] if curvature_source is not None else None
    normal_map_setting = properties.find_map_setting(project, resolved_normal_map_type)
    normal_space = str(
        getattr(normal_map_setting, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)
        if normal_map_setting is not None
        else constants.MAP_NORMAL_SPACE_TANGENT
    )
    normal_format = (
        properties.effective_normal_format(normal_map_setting)
        if normal_map_setting is not None
        else constants.NORMAL_FORMAT_OPENGL
    )
    flip_green = properties.map_flip_green(normal_map_setting) if normal_map_setting is not None else False
    return {
        "group_name": group_name,
        "normal_source": normal_source,
        "normal_target": normal_target,
        "normal_index": normal_index,
        "ao_source": ao_source,
        "ao_target": ao_target,
        "ao_index": ao_index,
        "curvature_source": curvature_source,
        "curvature_target": curvature_target,
        "curvature_index": curvature_index,
        "material_sources": material_sources,
        "material_images": {
            channel: source["image"] if source is not None else None
            for channel, source in material_sources.items()
        },
        "normal_space": normal_space,
        "normal_format": normal_format,
        "flip_green": flip_green,
        # The type actually wired, so a Material -> Normal fallback is labelled as such.
        "normal_map_type": resolved_normal_map_type,
        "ao_strength": ao_strength,
    }
