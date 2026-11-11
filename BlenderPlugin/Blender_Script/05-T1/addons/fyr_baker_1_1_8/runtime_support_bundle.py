from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile


def project_support_metadata(project, *, constants) -> dict:
    project_ignore_backface = bool(
        getattr(
            project,
            "ignore_backface",
            any(bool(getattr(group, "ignore_backface", False)) for group in getattr(project, "groups", [])),
        )
    )
    groups = []
    for group in getattr(project, "groups", []):
        metadata_state = _group_metadata_state(group)
        low_meshes = []
        for slot in getattr(group, "low_meshes", []):
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                low_meshes.append(getattr(obj, "name", ""))
        configured_high_meshes = []
        for slot in getattr(group, "high_meshes", []):
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                configured_high_meshes.append(getattr(obj, "name", ""))
        effective_high_meshes = []
        for slot in _effective_high_mesh_slots(group):
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                effective_high_meshes.append(getattr(obj, "name", ""))
        custom_cage = getattr(group, "custom_cage", None)
        groups.append(
            {
                "name": getattr(metadata_state, "name", ""),
                "texture_set_name": getattr(metadata_state, "texture_set_name", ""),
                "cage_mode": getattr(group, "cage_mode", ""),
                "cage_offset": float(getattr(group, "cage_offset", 0.0)),
                "average_normals": bool(getattr(group, "average_normals", True)),
                "ignore_backface": project_ignore_backface,
                "match_by_isolation": bool(getattr(group, "match_by_isolation", False)),
                "id_collection_name": (getattr(metadata_state, "id_collection_name", "") or "").strip(),
                "id_color_set_name": (getattr(metadata_state, "id_color_set_name", "") or "").strip(),
                "uv_layer_name": (getattr(group, "uv_layer_name", "") or "").strip(),
                "low_meshes": low_meshes,
                "use_low_as_high": _group_uses_low_as_high(group),
                "high_meshes": configured_high_meshes,
                "effective_high_meshes": effective_high_meshes,
                "custom_cage_name": getattr(custom_cage, "name", "") if custom_cage is not None else "",
            }
        )

    maps = []
    for map_setting in getattr(project, "maps", []):
        map_type = getattr(map_setting, "map_type", "")
        maps.append(
            {
                "map_type": map_type,
                "enabled": bool(getattr(map_setting, "enabled", True)),
                "samples": int(getattr(map_setting, "samples", 1)),
                "output_suffix": (getattr(map_setting, "output_suffix", "") or "").strip(),
                # Without these a bundle's MATERIAL rows are indistinguishable except
                # by output_suffix, so there is no way to tell which channel took
                # which route -- the exact question the 2026-08-19 tester bundles
                # could not answer about a bake that stalled on Metallic.
                "material_channel": str(getattr(map_setting, "material_channel", "") or ""),
                "material_origin": str(getattr(map_setting, "material_origin", "") or ""),
                "material_custom_name": (getattr(map_setting, "material_custom_name", "") or "").strip(),
                "execution_route": str(getattr(map_setting, "execution_route", "") or ""),
                "material_status_message": (
                    getattr(map_setting, "material_status_message", "") or ""
                ).strip(),
                "material_detail_mode": str(getattr(map_setting, "material_detail_mode", "") or ""),
                "denoising_enabled": bool(getattr(map_setting, "denoising_enabled", False)),
                "normal_space": getattr(map_setting, "normal_space", ""),
                "normal_format": getattr(map_setting, "normal_format", ""),
                "flip_green": bool(getattr(map_setting, "flip_green", False)),
                "ao_mode": str(getattr(map_setting, "ao_mode", constants.MAP_AO_MODE_RAYCAST)),
                "ao_distance": float(getattr(map_setting, "ao_distance", 0.0)),
                "ao_min_distance": float(getattr(map_setting, "ao_min_distance", 0.0)),
                "ao_two_sided": bool(getattr(map_setting, "ao_two_sided", False)),
                "ao_ignore_groups": bool(getattr(map_setting, "ao_ignore_groups", False)),
                "ao_bevel_normal": str(getattr(map_setting, "ao_bevel_normal", constants.AO_BEVEL_NORMAL_AUTO)),
                "curvature_bevel_mask": bool(getattr(map_setting, "curvature_bevel_mask", True)),
                "ao_cavity_weight": float(
                    getattr(
                        map_setting,
                        "ao_cavity_weight",
                        constants.default_ao_cavity_weight_for_map(map_type),
                    )
                ),
                "ao_output_min": float(getattr(map_setting, "ao_output_min", constants.DEFAULT_AO_OUTPUT_MIN)),
                "ao_output_max": float(getattr(map_setting, "ao_output_max", 1.0)),
                "ao_diffusion_quality": str(
                    getattr(map_setting, "ao_diffusion_quality", constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM)
                ),
                "ao_diffusion_clearance_scale": float(getattr(map_setting, "ao_diffusion_clearance_scale", 0.2)),
                "ao_diffusion_clearance_exponent": float(getattr(map_setting, "ao_diffusion_clearance_exponent", 2.0)),
                "curvature_scale": float(getattr(map_setting, "curvature_scale", 1.0)),
                "curvature_tonemapping_min": float(getattr(map_setting, "curvature_tonemapping_min", 0.0)),
                "curvature_tonemapping_max": float(getattr(map_setting, "curvature_tonemapping_max", 1.0)),
                "curvature_distance": float(getattr(map_setting, "curvature_distance", 0.0)),
                "curvature_relative_to_bounding_box": bool(
                    getattr(map_setting, "curvature_relative_to_bounding_box", False)
                ),
                "curvature_secondary_rays": int(getattr(map_setting, "curvature_secondary_rays", 64)),
                "curvature_detect_folds": bool(getattr(map_setting, "curvature_detect_folds", False)),
                "curvature_self_intersection": str(
                    getattr(map_setting, "curvature_self_intersection", "GROUP")
                ),
                "curvature_auto_tonemapping": bool(
                    getattr(map_setting, "curvature_auto_tonemapping", False)
                ),
                "curvature_value_min": float(getattr(map_setting, "curvature_value_min", -1.0)),
                "curvature_value_max": float(getattr(map_setting, "curvature_value_max", 1.0)),
                "thickness_distance": float(getattr(map_setting, "thickness_distance", 0.0)),
                "thickness_min_distance": float(getattr(map_setting, "thickness_min_distance", -1.0)),
                "thickness_scale": float(getattr(map_setting, "thickness_scale", 1.0)),
                "thickness_gamma": float(getattr(map_setting, "thickness_gamma", 1.0)),
                "thickness_dither": bool(getattr(map_setting, "thickness_dither", False)),
                "thickness_ignore_groups": bool(getattr(map_setting, "thickness_ignore_groups", False)),
                "id_source": getattr(map_setting, "id_source", ""),
                "position_normalization": getattr(map_setting, "position_normalization", ""),
                "relative_to_bounding_box": bool(getattr(map_setting, "relative_to_bounding_box", True)),
                "height_inner_distance": float(getattr(map_setting, "height_inner_distance", 0.0)),
                "height_outer_distance": float(getattr(map_setting, "height_outer_distance", 0.0)),
                "height_dither": bool(getattr(map_setting, "height_dither", False)),
            }
        )

    return {
        "name": getattr(project, "name", ""),
        "output_root": getattr(project, "output_root", ""),
        "resolution_preset": getattr(project, "resolution_preset", ""),
        "lock_resolution": bool(getattr(project, "lock_resolution", True)),
        "resolution_x": int(getattr(project, "resolution_x", 0)),
        "resolution_y": int(getattr(project, "resolution_y", 0)),
        "bit_depth": getattr(project, "bit_depth", ""),
        "anti_aliasing": getattr(project, "anti_aliasing", constants.DEFAULT_ANTI_ALIASING),
        "aa_samples": int(getattr(project, "aa_samples", constants.DEFAULT_AA_SAMPLES) or constants.DEFAULT_AA_SAMPLES),
        "margin": int(getattr(project, "margin", 0)),
        "tangent_basis": getattr(project, "tangent_basis", ""),
        "ignore_backface": project_ignore_backface,
        "bake_mode": getattr(project, "bake_mode", ""),
        "active_map_index": int(getattr(project, "active_map_index", 0)),
        "active_group_index": int(getattr(project, "active_group_index", 0)),
        "last_job_id": getattr(project, "last_job_id", ""),
        "last_workspace_path": getattr(project, "last_workspace_path", ""),
        "last_output_dir": getattr(project, "last_output_dir", ""),
        "last_progress_percent": float(getattr(project, "last_progress_percent", 0.0)),
        "last_active_group": getattr(project, "last_active_group", ""),
        "last_active_map": getattr(project, "last_active_map", ""),
        "last_warning_count": int(getattr(project, "last_warning_count", 0)),
        "last_error_count": int(getattr(project, "last_error_count", 0)),
        "last_warning_summary": getattr(project, "last_warning_summary", ""),
        "last_error_summary": getattr(project, "last_error_summary", ""),
        "last_status_message": getattr(project, "last_status_message", constants.STATUS_IDLE),
        "groups": groups,
        "maps": maps,
    }


def _group_metadata_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "metadata", None) or group
    return _properties.group_metadata_state(group)


def _group_uses_low_as_high(group) -> bool:
    try:
        from . import properties as _properties
    except Exception:
        return bool(getattr(group, "use_low_as_high", False))
    resolver = getattr(_properties, "group_uses_low_as_high", None)
    if callable(resolver):
        return resolver(group)
    role_state = getattr(group, "role_assignments", None) or group
    return bool(getattr(role_state, "use_low_as_high", getattr(group, "use_low_as_high", False)))


def _effective_high_mesh_slots(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "low_meshes" if _group_uses_low_as_high(group) else "high_meshes", [])
    resolver = getattr(_properties, "effective_high_mesh_slots", None)
    if callable(resolver):
        return resolver(group)
    role_state = getattr(group, "role_assignments", None) or group
    return getattr(role_state, "low_meshes" if _group_uses_low_as_high(group) else "high_meshes", [])


def support_bundle_manifest(
    project,
    *,
    job_path: Path,
    progress_path: Path,
    backend_log_path: Path,
    constants,
    repo_root_fn,
    bpy_module,
) -> dict:
    artifact_specs = [
        (job_path.name, job_path),
        ("progress.json", progress_path),
        ("logs/backend_run.log", backend_log_path),
        ("logs/gpu_diagnostics.log", progress_path.parent / "logs" / "gpu_diagnostics.log"),
    ]
    artifacts = []
    missing = []
    for archive_path, source_path in artifact_specs:
        exists = source_path.exists()
        artifact = {
            "archive_path": archive_path,
            "source_path": str(source_path),
            "exists": exists,
        }
        if exists:
            artifact["size_bytes"] = source_path.stat().st_size
        else:
            missing.append(archive_path)
        artifacts.append(artifact)

    return {
        "schema": "master_baker_support_bundle",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "addon": {
            "protocol": constants.PROTOCOL_VERSION,
            "repo_root": str(repo_root_fn()),
        },
        "blender": {
            "version_string": getattr(bpy_module.app, "version_string", ""),
            "version": list(getattr(bpy_module.app, "version", ())),
        },
        "project": project_support_metadata(project, constants=constants),
        "artifacts": artifacts,
        "missing_artifacts": missing,
    }


def resolve_bundle_workspace(project) -> Path:
    """Workspace the bundle should be collected from.

    ``last_workspace_path`` is stamped by EVERY ``prepare_bake_job`` call, and the
    speculative background prepare fires after edits, reloads and settings changes.
    It therefore routinely points at a workspace where no bake ever ran, whose bundle
    carries no backend_run.log, a progress file still reading "Bake workspace
    exported", and a GPU log with prepare-scope timings only. Prefer the bake-only
    pointer, and fall back to the old one for projects saved before it existed.
    """
    candidates = [
        str(getattr(project, "last_bake_workspace_path", "") or "").strip(),
        str(getattr(project, "last_workspace_path", "") or "").strip(),
    ]
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.exists():
            return candidate
    if not any(candidates):
        raise ValueError("No workspace is available for this project")
    raise FileNotFoundError(f"Workspace was not found: {candidates[0] or candidates[1]}")


def bake_evidence(workspace_path: Path, progress_path: Path, backend_log_path: Path) -> dict:
    """Whether this bundle actually documents a bake, stated up front.

    A bundle collected from a prepare-only workspace looks superficially complete,
    so say plainly whether a bake ran. Without this the reader has to infer it from
    an absent log and guess whether the absence is the bug or the bundle.
    """
    evidence = {
        "has_backend_run_log": backend_log_path.exists(),
        "progress_status": "",
        "produced_file_count": 0,
        "documents_a_bake": False,
    }
    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    if isinstance(payload, dict):
        evidence["progress_status"] = str(payload.get("status", "") or "")
        produced = payload.get("produced_files")
        evidence["produced_file_count"] = len(produced) if isinstance(produced, list) else 0
    evidence["documents_a_bake"] = bool(
        evidence["has_backend_run_log"] or evidence["produced_file_count"]
    )
    if not evidence["documents_a_bake"]:
        evidence["note"] = (
            "No bake ran in this workspace. Run a bake, then create the bundle again."
        )
    return evidence


def global_log_artifacts(*, cache_root: Path, hang_log_path: Path | None = None) -> list[tuple[str, Path]]:
    """``(archive_path, source_path)`` for the machine-wide diagnostics that exist.

    The per-job logs say what one bake did; a worker crash, a hang, or a GPU
    fallback is recorded in these instead, and without them a tester's bundle for
    exactly those failures carried nothing that explained them.
    """
    cache_root = Path(cache_root)
    candidates = [
        ("logs/worker_diagnostics.log", cache_root / "logs" / "worker_diagnostics.log"),
        ("logs/worker_diagnostics.log.1", cache_root / "logs" / "worker_diagnostics.log.1"),
        ("logs/gpu_fallback.log", cache_root.parent / "gpu_fallback.log"),
    ]
    if hang_log_path is not None:
        candidates.append(("logs/hang_traceback.log", Path(hang_log_path)))
    artifacts: list[tuple[str, Path]] = []
    for archive_path, source_path in candidates:
        try:
            if source_path.is_file():
                artifacts.append((archive_path, source_path))
        except OSError:
            continue
    return artifacts


SYSTEM_INFO_ARCHIVE_PATH = "system/gpu_info.json"


def _system_info_json(system_info_fn=None) -> str:
    """Serialized ``system/gpu_info.json``; an error record instead of raising."""
    try:
        if system_info_fn is None:
            from . import system_diagnostics

            system_info_fn = system_diagnostics.collect_system_info
        payload = system_info_fn()
    except Exception as exc:  # noqa: BLE001 - never lose the bundle over machine facts
        payload = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        return json.dumps(payload, indent=2, sort_keys=True, default=str)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"unserializable system info: {type(exc).__name__}: {exc}"})


def write_support_bundle(
    project,
    *,
    destination_path: str | Path | None = None,
    backend_run_log_path_fn,
    support_bundle_path_fn,
    support_bundle_manifest_fn,
    extra_artifacts=None,
    system_info_fn=None,
) -> Path:
    """Write the diagnostics zip.

    ``extra_artifacts`` is a sequence of ``(archive_path, source_path)`` pairs the
    caller wants carried alongside the workspace artifacts, currently the .blend
    the user opted into including. They go through the same manifest entries as
    everything else so a reader can see what was offered and what was missing.

    ``system_info_fn`` returns the machine facts written to
    ``system/gpu_info.json`` (every display adapter, driver versions, per-app GPU
    preferences, recent display-driver resets); it defaults to
    ``system_diagnostics.collect_system_info``, which is time-bounded and never
    raises. A failure here still never costs the rest of the bundle.
    """
    workspace_path = resolve_bundle_workspace(project)

    job_candidates = (
        workspace_path / "job.mbjob",
        workspace_path / "job.json",
        workspace_path / "job.mbfbs",
    )
    job_path = next((candidate for candidate in job_candidates if candidate.exists()), job_candidates[0])
    progress_path = workspace_path / "progress.json"
    backend_log_path = backend_run_log_path_fn(progress_path)
    destination = Path(destination_path) if destination_path is not None else support_bundle_path_fn(progress_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    manifest = support_bundle_manifest_fn(
        project,
        job_path=job_path,
        progress_path=progress_path,
        backend_log_path=backend_log_path,
    )
    manifest["bake_evidence"] = bake_evidence(workspace_path, progress_path, backend_log_path)

    for archive_path, source_path in extra_artifacts or ():
        source_path = Path(source_path)
        exists = source_path.exists()
        artifact = {
            "archive_path": str(archive_path),
            "source_path": str(source_path),
            "exists": exists,
        }
        if exists:
            artifact["size_bytes"] = source_path.stat().st_size
        else:
            manifest.setdefault("missing_artifacts", []).append(str(archive_path))
        manifest.setdefault("artifacts", []).append(artifact)

    system_info_json = _system_info_json(system_info_fn)
    manifest["generated_files"] = [SYSTEM_INFO_ARCHIVE_PATH]

    with zipfile.ZipFile(destination, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("support_bundle.json", json.dumps(manifest, indent=2, sort_keys=True))
        archive.writestr(SYSTEM_INFO_ARCHIVE_PATH, system_info_json)
        for artifact in manifest["artifacts"]:
            if not artifact["exists"]:
                continue
            source_path = Path(artifact["source_path"])
            # Blender already compresses .blend files, so deflating one again costs
            # seconds of CPU on a large scene and buys back around 1%. Store it.
            compress_type = (
                zipfile.ZIP_STORED if source_path.suffix.lower() == ".blend" else zipfile.ZIP_DEFLATED
            )
            archive.write(
                source_path, arcname=artifact["archive_path"], compress_type=compress_type
            )

    return destination
