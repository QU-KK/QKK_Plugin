from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
from typing import Any, Iterable, Mapping

from . import constants, naming


SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"

_INVALID_PATH_CHARS = re.compile(r'[<>|?*\x00-\x1F]')

_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    subject: str = ""
    group_name: str = ""
    object_name: str = ""
    field: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == SEVERITY_ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == SEVERITY_WARNING


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        subject: str = "",
        group_name: str = "",
        object_name: str = "",
        field: str = "",
    ) -> ValidationIssue:
        issue = ValidationIssue(
            severity=severity,
            code=code,
            message=message,
            subject=subject,
            group_name=group_name,
            object_name=object_name,
            field=field,
        )
        self.issues.append(issue)
        return issue

    def error(self, code: str, message: str, **kwargs: Any) -> ValidationIssue:
        return self.add(SEVERITY_ERROR, code, message, **kwargs)

    def warning(self, code: str, message: str, **kwargs: Any) -> ValidationIssue:
        return self.add(SEVERITY_WARNING, code, message, **kwargs)

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.is_error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.is_warning]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ValidationIssueGroup:
    label: str
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def issue_count(self) -> int:
        return len(self.errors) + len(self.warnings)


def summarize_issues(issues: ValidationReport | Iterable[ValidationIssue]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    if isinstance(issues, ValidationReport):
        return issues.errors, issues.warnings

    report = ValidationReport()
    report.issues.extend(list(issues))
    return report.errors, report.warnings


def summarize_issues_grouped(issues: ValidationReport | Iterable[ValidationIssue]) -> list[ValidationIssueGroup]:
    if isinstance(issues, ValidationReport):
        iterable = issues.issues
    else:
        iterable = list(issues)

    grouped: dict[str, ValidationIssueGroup] = {}
    order: list[str] = []
    for issue in iterable:
        label = _normalized_label(issue.group_name) or _normalized_label(issue.subject) or _normalized_label(issue.object_name) or "Project"
        bucket = grouped.get(label)
        if bucket is None:
            bucket = ValidationIssueGroup(label=label)
            grouped[label] = bucket
            order.append(label)
        if issue.is_error:
            bucket.errors.append(issue)
        else:
            bucket.warnings.append(issue)

    return [grouped[label] for label in order]


def primary_issue_message(issues: ValidationReport | Iterable[ValidationIssue]) -> str:
    errors, warnings = summarize_issues(issues)
    if errors:
        return errors[0].message
    if warnings:
        return warnings[0].message
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalized_label(value: Any) -> str:
    return _text(value).strip()


def _as_iterable(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, (str, bytes, bytearray)):
        return [value]
    return list(value)


def _get_value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _has_value(source: Any, name: str) -> bool:
    if isinstance(source, Mapping):
        return name in source
    return hasattr(source, name)


def _metadata_value(metadata: Any, *names: str) -> Any:
    if metadata is None:
        return None
    for name in names:
        if isinstance(metadata, Mapping):
            if name in metadata:
                return metadata[name]
        elif hasattr(metadata, name):
            return getattr(metadata, name)
    return None


def _mesh_metadata_candidates(mesh: Any) -> list[str]:
    candidates = []
    for attr in ("object_name", "name", "path"):
        value = _normalized_label(_get_value(mesh, attr, ""))
        if value:
            candidates.append(value)
            if attr == "path":
                candidates.append(Path(value).stem)
                candidates.append(Path(value).name)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _resolve_mesh_metadata(mesh_metadata: Any, mesh: Any) -> Any:
    if mesh_metadata is None:
        return None

    if isinstance(mesh_metadata, Mapping):
        for candidate in _mesh_metadata_candidates(mesh):
            if candidate in mesh_metadata:
                return mesh_metadata[candidate]
    return None


def _topology_count(metadata: Any) -> int | None:
    raw = _metadata_value(
        metadata,
        "triangle_count",
        "face_count",
        "polygon_count",
        "tri_count",
        "triangles",
        "faces",
        "polygons",
    )
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _uv_layer_count(metadata: Any) -> int | None:
    raw = _metadata_value(metadata, "uv_layer_count", "uv_count", "uv_layers")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    has_uvs = _metadata_value(metadata, "has_uvs", "uvs_present")
    if has_uvs is None:
        return None
    return 1 if bool(has_uvs) else 0


def _uv_layer_names(metadata: Any) -> list[str]:
    raw = _metadata_value(metadata, "uv_layer_names", "uv_names")
    if raw is None:
        return []

    names: list[str] = []
    for item in _as_iterable(raw):
        name = _normalized_label(item)
        if name:
            names.append(name)
    return names


def _object_uv_layers(mesh: Any) -> Any:
    data = _get_value(mesh, "data", None)
    if data is None:
        return None
    return getattr(data, "uv_layers", None)


def _object_uv_layer_count(mesh: Any) -> int | None:
    uv_layers = _object_uv_layers(mesh)
    if uv_layers is None:
        return None
    try:
        return int(len(uv_layers))
    except (TypeError, ValueError):
        pass
    try:
        return sum(1 for _item in uv_layers)
    except TypeError:
        return None


def _object_uv_layer_names(mesh: Any) -> list[str]:
    uv_layers = _object_uv_layers(mesh)
    if uv_layers is None:
        return []

    names: list[str] = []
    try:
        iterable = list(uv_layers)
    except TypeError:
        iterable = []

    for item in iterable:
        name = _normalized_label(_get_value(item, "name", ""))
        if name:
            names.append(name)

    keys_method = getattr(uv_layers, "keys", None)
    if callable(keys_method):
        for item in keys_method():
            name = _normalized_label(item)
            if name and name not in names:
                names.append(name)
    return names


def _object_is_manifold(mesh: Any) -> bool | None:
    data = _get_value(mesh, "data", None)
    if data is None:
        return True
    
    try:
        # Check if we have access to the actual Blender mesh data with edges.
        # This property is available on Blender Mesh objects.
        edges = getattr(data, "edges", None)
        if edges is None:
            return True
            
        for edge in edges:
            if not getattr(edge, "is_manifold", True):
                return False
        return True
    except Exception:
        # Fallback to True if we can't access the geometry to avoid blocking bakes on errors
        return True




def _object_material_count(obj: Any) -> int | None:
    """Count non-empty material slots on a real Blender object.

    Returns ``None`` when the object does not expose mesh material data (e.g. an
    abstract test double), so callers can skip the check rather than warn.
    """
    data = _get_value(obj, "data", None)
    if data is None:
        return None
    materials = getattr(data, "materials", None)
    if materials is None:
        return None
    try:
        return sum(1 for mat in materials if mat is not None)
    except TypeError:
        return None


def _enabled_maps(source: Any) -> list[Any]:
    maps = _get_value(source, "maps", None)
    if maps is None:
        return []
    return [
        item
        for item in _as_iterable(maps)
        if not bool(_get_value(item, "is_add_phantom", False)) and bool(_get_value(item, "enabled", True))
    ]


def _project_resolution_value(project: Any, axis: str) -> Any:
    if axis == "x":
        return _get_value(project, "resolution_x", _get_value(project, "resolution_width", None))
    return _get_value(project, "resolution_y", _get_value(project, "resolution_height", None))


def _resolved_mesh_assignments(value: Any) -> list[Any]:
    resolved: list[Any] = []
    for item in _as_iterable(value):
        object_ref = _get_value(item, "object_ref", item)
        if object_ref is not None:
            resolved.append(object_ref)
    return resolved


def _mesh_ref_identity(mesh: Any) -> str:
    for field_name in ("object_name", "name", "path"):
        value = _normalized_label(_get_value(mesh, field_name, ""))
        if value:
            return value
    return ""


def _validate_unique_mesh_refs(
    report: ValidationReport,
    meshes: Iterable[Any],
    *,
    group_name: str,
    role: str,
) -> set[str]:
    seen: set[str] = set()
    for mesh in meshes:
        identity = _mesh_ref_identity(mesh)
        if not identity:
            report.error(
                f"group.{role.lower()}_meshes.missing_identifier",
                f"{role.title()} mesh entry is missing an object name or path.",
                subject=group_name,
                group_name=group_name,
                field=f"{role.lower()}_meshes",
            )
            continue

        key = identity.casefold()
        if key in seen:
            report.error(
                f"group.{role.lower()}_meshes.duplicate",
                f"{role.title()} mesh assignment is duplicated in the bake group.",
                subject=group_name,
                group_name=group_name,
                object_name=identity,
                field=f"{role.lower()}_meshes",
            )
            continue
        seen.add(key)
    return seen


def project_requires_high_meshes(project: Any) -> bool:
    """HIGH_TO_LOW groups need a high-poly source; MATERIAL groups self-bake their lows."""
    workflow = str(
        _get_value(project, "workflow", constants.WORKFLOW_HIGH_TO_LOW) or constants.WORKFLOW_HIGH_TO_LOW
    ).strip().upper()
    return workflow != constants.WORKFLOW_MATERIAL


def _group_missing_roles(group: Any, *, require_high: bool) -> tuple[bool, bool]:
    """(missing low, missing high) for one bake group, resolved the way a bake exports it."""
    low_meshes = _resolved_mesh_assignments(_get_value(group, "low_meshes", []))
    if not require_high:
        return not low_meshes, False
    role_state = _get_value(group, "role_assignments", None)
    use_low_as_high = bool(
        _get_value(role_state, "use_low_as_high", _get_value(group, "use_low_as_high", False))
    )
    if use_low_as_high:
        return not low_meshes, not low_meshes
    high_meshes = _resolved_mesh_assignments(_get_value(group, "high_meshes", []))
    return not low_meshes, not high_meshes


def incomplete_group_names(project: Any) -> list[str]:
    """Bake groups that cannot bake yet: no low meshes, or no high source to project from.

    Artists stage groups before filling them (Add Empty Bake Group, a group waiting for
    its low). A bake skips these as long as another group can bake; see
    validate_bake_project.
    """
    require_high = project_requires_high_meshes(project)
    names: list[str] = []
    for group in _as_iterable(_get_value(project, "groups", [])):
        missing_low, missing_high = _group_missing_roles(group, require_high=require_high)
        if missing_low or missing_high:
            names.append(str(_get_value(group, "name", "") or ""))
    return names


def _skipped_group_message(missing_low: bool, missing_high: bool) -> str:
    if missing_low and missing_high:
        return "Bake group is empty, so it is skipped."
    if missing_low:
        return "Bake group has no low meshes, so it is skipped."
    return "Bake group has no high meshes, so it is skipped."


def _missing_mesh_message(role: str, meshes: Iterable[Any]) -> str:
    role_label = role.lower()
    opposite_label = "high" if role_label == "low" else "low"
    mesh_count = len(list(meshes))
    if mesh_count == 0:
        return f"Bake group has no {role_label} meshes."
    mesh_word = "mesh" if mesh_count == 1 else "meshes"
    return f"Bake group has {mesh_count} {opposite_label} {mesh_word}, but no {role_label} meshes."


def _validate_role_overlap(
    report: ValidationReport,
    group_name: str,
    left_role: str,
    left_meshes: Iterable[Any],
    right_role: str,
    right_meshes: Iterable[Any],
    *,
    allow_complete_mirror: bool = False,
) -> None:
    left_ids = {_mesh_ref_identity(mesh).casefold() for mesh in left_meshes if _mesh_ref_identity(mesh)}
    right_ids = {_mesh_ref_identity(mesh).casefold() for mesh in right_meshes if _mesh_ref_identity(mesh)}
    overlap = sorted(left_ids & right_ids)
    if not overlap:
        return
    if allow_complete_mirror and left_ids == right_ids:
        return

    report.error(
        "group.role_overlap",
        f"{left_role.title()} and {right_role.title()} assignments contain the same mesh.",
        subject=group_name,
        group_name=group_name,
        field=f"{left_role.lower()}_meshes",
    )


def _map_type_label(map_type: Any) -> str:
    """Human name for a map type ("Ambient Occlusion"), falling back to the raw id."""
    normalized = str(map_type or "").strip().upper()
    if not normalized:
        return "Map"
    return constants.MAP_LABELS.get(normalized, normalized)


def _validate_output_path_text(report: ValidationReport, path: str, *, subject: str, group_name: str) -> None:
    normalized_path = _normalized_label(path)
    if not normalized_path:
        report.error(
            "group.output.path.missing",
            "Bake output target is missing a file path.",
            subject=subject,
            group_name=group_name,
            field="outputs",
        )
        return

    if re.match(r"^[A-Za-z]:$", normalized_path):
        report.error(
            "group.output.path.invalid_drive_path",
            "Bake output target is an incomplete drive path.",
            subject=subject,
            group_name=group_name,
            field="outputs",
        )
        return

    if _INVALID_PATH_CHARS.search(normalized_path):
        report.error(
            "group.output.path.invalid_chars",
            "Bake output target contains invalid path characters.",
            subject=subject,
            group_name=group_name,
            field="outputs",
        )


def _validate_output_targets(
    report: ValidationReport,
    outputs: Iterable[Any],
    *,
    enabled_map_types: set[str],
    group_name: str,
) -> None:
    enabled_map_types = {item.casefold() for item in enabled_map_types if item}
    # Key is (map_type, output_suffix) so duplicate map types with distinct suffixes are allowed
    seen_map_keys: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()
    seen_type_only: set[str] = set()
    for output in outputs:
        map_type = _normalized_label(_get_value(output, "map_type", ""))
        output_suffix = str(_get_value(output, "output_suffix", "") or "").strip()
        path = _normalized_label(_get_value(output, "path", ""))
        display_name = _normalized_label(_get_value(output, "display_name", ""))

        if not map_type:
            report.error(
                "group.output.map_type.missing",
                "Bake output target is missing a map type.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )
            continue

        normalized_map_type = map_type.casefold()
        # The tile is part of the identity. Under UDIM one map deliberately produces one output
        # target PER TILE -- same map type, same suffix, different tile and path -- so keying on
        # (type, suffix) alone reported every multi-tile bake as a duplicate and blocked it.
        # Untiled targets carry tile 0, so single-tile projects key exactly as before.
        output_udim_tile = int(getattr(output, "udim_tile", 0) or 0)
        map_key = (normalized_map_type, output_suffix.casefold(), output_udim_tile)
        # Material maps (MATERIAL / MATERIAL_ALBEDO / …) are baked addon-side (Cycles or the
        # UV fast-path), so they legitimately never appear in the backend job.maps even when
        # enabled — don't flag their output targets as untracked.
        if normalized_map_type not in enabled_map_types and not normalized_map_type.startswith("material"):
            report.warning(
                "group.output.map_type.untracked",
                f"Bake output target for {_map_type_label(map_type)} does not match any enabled job map.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )

        if map_key in seen_map_keys:
            report.error(
                "group.output.map_type.duplicate",
                "Bake output target repeats a map type for the same group.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )
        else:
            seen_map_keys.add(map_key)
            seen_type_only.add(normalized_map_type)

        _validate_output_path_text(report, path, subject=group_name, group_name=group_name)

        if path and path.casefold() in seen_paths:
            report.error(
                "group.output.path.duplicate",
                "Bake output target repeats an output file path.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )
        else:
            if path:
                seen_paths.add(path.casefold())

        if not display_name:
            report.warning(
                "group.output.display_name.missing",
                "Bake output target is missing a display name.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )

    missing_map_types = sorted(enabled_map_types - seen_type_only)
    for map_type in missing_map_types:
        report.warning(
            "group.output.map_type.missing_enabled_target",
            f"Bake output target is missing for the enabled {_map_type_label(map_type)} map.",
            subject=group_name,
            group_name=group_name,
            field="outputs",
        )


def _resolved_texture_set_output_name(project: Any, set_key: Any) -> str | None:
    """A group's texture-set token as it will appear in the file name, or ``None``.

    A texture set stores a link *key* plus a ``name_mode`` (Custom / .blend file /
    Material). Export never writes the raw key: it resolves the mode through
    ``properties.resolve_texture_set_output_name`` first. Validation compared raw keys,
    so two sets that resolve to the same token -- two sets both on "Blend File", for
    instance -- looked distinct and their identical output files were never flagged.
    The second bake then silently overwrote the first.

    ``properties`` needs ``bpy`` and this module stays bpy-free, so the import is lazy
    and the raw key is the fallback for a plain-data project (tests, protocol dicts).
    """
    key = _normalized_label(set_key)
    if not key:
        return None
    try:
        from . import properties

        resolved = _normalized_label(properties.resolve_texture_set_output_name(project, key))
    except Exception:
        return key
    return resolved or key


def _project_group_output_file_names(
    project: Any,
    group: Any,
    enabled_maps: Iterable[Any],
    *,
    udim_tiles: Iterable[str | int | None] = (None,),
) -> list[str]:
    """Concrete output file names this group writes, one per enabled map per UDIM tile.

    ``udim_tiles`` defaults to ``(None,)`` -- the untiled single-output case, which produces
    exactly the legacy names. A tokenized texture set passes its concrete tile numbers so the
    collision key below is per *physical file* rather than per logical map.
    """
    # No local "BakeGroup" fallback: naming.build_output_file_name owns the
    # set > group > project precedence, so this must resolve exactly like export does.
    group_name = _normalized_label(_get_value(group, "name", ""))
    texture_set_name = _resolved_texture_set_output_name(project, _get_value(group, "texture_set_name", ""))
    bit_depth = str(_get_value(project, "bit_depth", constants.DEFAULT_BIT_DEPTH))
    image_format = str(_get_value(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT)

    tiles = list(udim_tiles) or [None]
    file_names: list[str] = []
    for map_item in enabled_maps:
        raw_map_type = _normalized_label(_get_value(map_item, "map_type", ""))
        if not raw_map_type:
            continue
        # Resolve names exactly like _build_output_targets does: the EFFECTIVE type
        # (a Material row's file label is its channel — "Albedo", not "Material") and
        # the EFFECTIVE suffix (same-identity rows with a blank suffix are
        # auto-disambiguated). Reading the raw fields made two blank Material rows
        # (Albedo + Roughness) look like one file and hard-blocked the bake.
        map_type = naming.effective_map_type_for_setting(map_item) or raw_map_type
        map_label_override = naming.effective_map_output_suffix(project, map_item)
        for udim_tile in tiles:
            try:
                file_names.append(
                    naming.build_output_file_name(
                        group_name=group_name,
                        map_type=map_type,
                        bit_depth=bit_depth,
                        image_format=image_format,
                        texture_set_name=texture_set_name,
                        udim_tile=udim_tile,
                        map_label_override=map_label_override,
                        project_name=_normalized_label(_get_value(project, "name", "")) or None,
                    )
                )
            except naming.InvalidUdimTileError:
                # The tile itself is already reported by the tile-range check; skip the name
                # rather than aborting collision detection for every other tile.
                continue
    return file_names


def _validate_map_item(report: ValidationReport, map_item: Any, *, subject: str = "") -> None:
    map_type = _normalized_label(_get_value(map_item, "map_type", ""))
    map_label = map_type or "Map"
    valid_map_types = constants.MAP_VALID_JOB_TYPES
    if map_type:
        _validate_choice(
            report,
            map_type,
            valid_map_types,
            code="map.type.invalid",
            message="Bake map type is not supported.",
            field="map_type",
            subject=subject or map_label,
        )

    _validate_positive_int(
        report,
        _get_value(map_item, "samples", 1),
        code="map.samples.invalid",
        message="Bake map samples must be a positive integer.",
        field="samples",
        subject=subject or map_label,
    )

    if map_type in {constants.MAP_NORMAL, constants.MAP_AO}:
        material_detail_mode = str(
            _get_value(map_item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
            or constants.MATERIAL_DETAIL_AUTO
        ).strip().upper()
        detail_mode_items = (
            constants.MATERIAL_DETAIL_MODE_ITEMS
            if map_type == constants.MAP_AO
            else constants.MATERIAL_NORMAL_DETAIL_MODE_ITEMS
        )
        # Project UI stores Off/Auto/Manual. Prepared bake jobs replace Auto with a
        # resolved backend composition mode (NORMAL_COMBINE, AO_TEXTURE, …).
        allowed_detail_modes = {item[0] for item in detail_mode_items} | set(
            constants.MATERIAL_DETAIL_BACKEND_MODES
        )
        _validate_choice(
            report,
            material_detail_mode,
            allowed_detail_modes,
            code="map.material_detail_mode.invalid",
            message="Material Detail mode is not supported.",
            field="material_detail_mode",
            subject=subject or map_label,
        )
        if (
            map_type == constants.MAP_AO
            and material_detail_mode == constants.MATERIAL_DETAIL_MANUAL
            and _get_value(map_item, "material_detail_image", None) is None
        ):
            report.error(
                "map.material_detail_image.missing",
                "Manual Material Detail requires an AO source image.",
                field="material_detail_image",
                subject=subject or map_label,
            )

    if map_type == constants.MAP_NORMAL:
        _validate_choice(
            report,
            _get_value(map_item, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT),
            {item[0] for item in constants.MAP_NORMAL_SPACE_ITEMS},
            code="map.normal_space.invalid",
            message="Normal map space is not supported.",
            field="normal_space",
            subject=subject or map_label,
        )

    if map_type == constants.MAP_ID:
        _validate_choice(
            report,
            _get_value(map_item, "id_source", constants.MAP_ID_SOURCE_OBJECT),
            {item[0] for item in constants.MAP_ID_SOURCE_ITEMS},
            code="map.id_source.invalid",
            message="ID map source is not supported.",
            field="id_source",
            subject=subject or map_label,
        )

    # Every project carries a disabled Attribute row from the map catalogue; only a row
    # that will actually bake needs an attribute.
    if map_type == constants.MAP_ATTRIBUTE and bool(_get_value(map_item, "enabled", True)):
        if not str(_get_value(map_item, "attribute_name", "") or "").strip():
            report.error(
                "map.attribute_name.missing",
                "Choose which attribute the Attribute map bakes.",
                subject=subject or map_label,
                field="attribute_name",
            )
        if float(_get_value(map_item, "attribute_range_min", 0.0) or 0.0) == float(
            _get_value(map_item, "attribute_range_max", 1.0)
        ):
            report.error(
                "map.attribute_range.empty",
                "Attribute map Min and Max are equal; set a range to bake.",
                subject=subject or map_label,
                field="attribute_range_max",
            )

    if map_type == constants.MAP_POSITION:
        _validate_choice(
            report,
            _get_value(map_item, "position_normalization", constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX),
            {item[0] for item in constants.MAP_POSITION_NORMALIZATION_ITEMS},
            code="map.position_normalization.invalid",
            message="Position normalization mode is not supported.",
            field="position_normalization",
            subject=subject or map_label,
        )

    if constants.effective_lighting_map_type(map_item) is not None:
        _validate_choice(
            report,
            _get_value(map_item, "lighting_engine", constants.LIGHTING_ENGINE_AUTO),
            {item[0] for item in constants.LIGHTING_ENGINE_ITEMS},
            code="map.lighting_engine.invalid",
            message="Lighting engine profile is not supported.",
            field="lighting_engine",
            subject=subject or map_label,
        )
        _validate_choice(
            report,
            _get_value(map_item, "lighting_quality", constants.LIGHTING_QUALITY_BALANCED),
            {item[0] for item in constants.LIGHTING_QUALITY_ITEMS},
            code="map.lighting_quality.invalid",
            message="Lighting quality preset is not supported.",
            field="lighting_quality",
            subject=subject or map_label,
        )
        _validate_positive_int(
            report,
            _get_value(map_item, "lighting_direct_samples", 1),
            code="map.lighting_direct_samples.invalid",
            message="Lighting direct sample count must be a positive integer.",
            field="lighting_direct_samples",
            subject=subject or map_label,
        )
        _validate_positive_int(
            report,
            _get_value(map_item, "lighting_indirect_paths", 1),
            code="map.lighting_indirect_paths.invalid",
            message="Lighting indirect path count must be a positive integer.",
            field="lighting_indirect_paths",
            subject=subject or map_label,
        )
        try:
            bounces = int(_get_value(map_item, "lighting_max_bounces", 0))
        except (TypeError, ValueError):
            bounces = -1
        if bounces < 0:
            report.error(
                "map.lighting_max_bounces.invalid",
                "Lighting bounce count cannot be negative.",
                subject=subject or map_label,
                field="lighting_max_bounces",
            )
        try:
            noise_threshold = float(_get_value(map_item, "lighting_noise_threshold", 0.0))
        except (TypeError, ValueError):
            noise_threshold = -1.0
        if noise_threshold < 0.0 or noise_threshold > 1.0:
            report.error(
                "map.lighting_noise_threshold.invalid",
                "Lighting noise threshold must be between 0 and 1.",
                subject=subject or map_label,
                field="lighting_noise_threshold",
            )

    if map_type == constants.MAP_AO:
        _validate_choice(
            report,
            _get_value(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST),
            {item[0] for item in constants.MAP_AO_MODE_ITEMS},
            code="map.ao_mode.invalid",
            message="AO method is not supported.",
            field="ao_mode",
            subject=subject or map_label,
        )
        _validate_choice(
            report,
            _get_value(map_item, "ao_diffusion_quality", constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM),
            {item[0] for item in constants.MAP_AO_DIFFUSION_QUALITY_ITEMS},
            code="map.ao_diffusion_quality.invalid",
            message="Diffusive AO quality setting is not supported.",
            field="ao_diffusion_quality",
            subject=subject or map_label,
        )
        if str(_get_value(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST)).strip().upper() == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE:
            try:
                ao_radius = float(_get_value(map_item, "ao_distance", 0.0))
            except (TypeError, ValueError):
                ao_radius = 0.0
            if ao_radius <= 0.0:
                report.error(
                    "map.ao_mode.radius_required",
                    "Diffusive AO requires a positive Radius.",
                    field="ao_distance",
                    subject=subject or map_label,
                )
            if bool(_get_value(map_item, "ao_ignore_groups", False)):
                report.error(
                    "map.ao_mode.ignore_groups_unsupported",
                    "Diffusive AO does not support Ignore Groups.",
                    field="ao_ignore_groups",
                    subject=subject or map_label,
                )
            if bool(_get_value(map_item, "ao_relative_to_bounding_box", False)):
                report.error(
                    "map.ao_mode.relative_to_bounds_unsupported",
                    "Diffusive AO does not support Relative to Bounds.",
                    field="ao_relative_to_bounding_box",
                    subject=subject or map_label,
                )
            if bool(_get_value(map_item, "ao_use_ground_plane", False)):
                report.error(
                    "map.ao_mode.ground_plane_unsupported",
                    "Diffusive AO does not support Ground Plane.",
                    field="ao_use_ground_plane",
                    subject=subject or map_label,
                )

    def _validate_non_negative_number(field_name: str, code: str, message: str) -> None:
        try:
            value = float(_get_value(map_item, field_name, 0.0))
        except (TypeError, ValueError):
            report.error(code, message, field=field_name, subject=subject or map_label)
            return
        if value < 0.0:
            report.error(code, message, field=field_name, subject=subject or map_label)

    _validate_non_negative_number("ao_distance", "map.ao_distance.invalid", "AO distance cannot be negative.")
    _validate_non_negative_number("curvature_distance", "map.curvature_distance.invalid", "Curvature distance cannot be negative.")
    _validate_non_negative_number("thickness_distance", "map.thickness_distance.invalid", "Thickness distance cannot be negative.")

    for field_name, code, message in (
        ("curvature_scale", "map.curvature_scale.invalid", "Curvature scale must be greater than zero."),
        ("thickness_scale", "map.thickness_scale.invalid", "Thickness scale must be greater than zero."),
        ("thickness_gamma", "map.thickness_gamma.invalid", "Thickness gamma must be greater than zero."),
        ("ao_diffusion_clearance_scale", "map.ao_diffusion_clearance_scale.invalid", "Diffusive AO clearance scale must be greater than zero."),
        ("ao_diffusion_clearance_exponent", "map.ao_diffusion_clearance_exponent.invalid", "Diffusive AO clearance exponent must be greater than zero."),
    ):
        try:
            value = float(_get_value(map_item, field_name, 1.0))
        except (TypeError, ValueError):
            report.error(code, message, field=field_name, subject=subject or map_label)
            continue
        if value <= 0.0:
            report.error(code, message, field=field_name, subject=subject or map_label)

    try:
        inner_distance = float(_get_value(map_item, "height_inner_distance", 0.0))
        outer_distance = float(_get_value(map_item, "height_outer_distance", 0.0))
    except (TypeError, ValueError):
        report.error(
            "map.height_distance.invalid",
            "Height map distances must be numeric values.",
            field="height_outer_distance",
            subject=subject or map_label,
        )
    else:
        if (abs(inner_distance) > 1e-6 or abs(outer_distance) > 1e-6) and outer_distance <= inner_distance:
            report.error(
                "map.height_distance.invalid",
                "Height map outer distance must be greater than the inner distance.",
                field="height_outer_distance",
                subject=subject or map_label,
            )


def _validate_choice(
    report: ValidationReport,
    value: Any,
    allowed: Iterable[str],
    *,
    code: str,
    message: str,
    field: str,
    subject: str = "",
) -> None:
    normalized = _normalized_label(value)
    allowed_normalized = {_normalized_label(item) for item in allowed}
    if normalized not in allowed_normalized:
        report.error(code, message, subject=subject, field=field)


def _validate_positive_int(
    report: ValidationReport,
    value: Any,
    *,
    code: str,
    message: str,
    field: str,
    subject: str = "",
) -> None:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        report.error(code, message, subject=subject, field=field)
        return
    if numeric <= 0:
        report.error(code, message, subject=subject, field=field)


def _validate_max_int(
    report: ValidationReport,
    value: Any,
    *,
    maximum: int,
    code: str,
    message: str,
    field: str,
    subject: str = "",
) -> None:
    """Upper-bound companion to :func:`_validate_positive_int`. A non-integer value is left
    alone -- the positive-int check already owns that failure."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return
    if numeric > maximum:
        report.error(code, message, subject=subject, field=field)


def validate_output_root(
    output_root: str | Path | None,
    *,
    subject: str = "",
    probe_filesystem: bool = True,
) -> ValidationReport:
    """Validate an output root.

    ``probe_filesystem`` covers the read-only check at the end, which walks the
    path's parents with ``exists()`` and then calls ``os.access``. Callers that
    run from a UI draw callback pass ``False``: draw callbacks re-run on every
    redraw (several times a second during a bake), and the syntax checks above
    are pure string work. The "Check" button and the pre-bake preflight keep the
    default so a read-only folder is still caught before a bake starts.
    """
    report = ValidationReport()
    text = _normalized_label(output_root)

    if not text:
        report.error(
            "project.output_root.missing",
            "Output root is missing.",
            subject=subject,
            field="output_root",
        )
        return report

    if re.match(r"^[A-Za-z]:$", text):
        report.error(
            "project.output_root.invalid_drive_path",
            "Output root is an incomplete drive path.",
            subject=subject,
            field="output_root",
        )
        return report

    if text.startswith("//") or text.startswith("\\\\"):
        if _INVALID_PATH_CHARS.search(text) or ":" in text:
            report.error(
                "project.output_root.invalid_chars",
                "Output root contains invalid path characters.",
                subject=subject,
                field="output_root",
            )
        return report

    if _WINDOWS_DRIVE_PATH.match(text):
        tail = text[2:]
        if _INVALID_PATH_CHARS.search(tail) or ":" in tail:
            report.error(
                "project.output_root.invalid_chars",
                "Output root contains invalid path characters.",
                subject=subject,
                field="output_root",
            )
        return report

    if ":" in text or _INVALID_PATH_CHARS.search(text):
        report.error(
            "project.output_root.invalid_chars",
            "Output root contains invalid path characters.",
            subject=subject,
            field="output_root",
        )
        return report

    if not probe_filesystem:
        return report

    # Check for write permissions
    try:
        path = Path(text)
        if not path.is_absolute():
            # If relative, we can't easily check permissions here without context,
            # but we assume the project will handle it.
            pass
        else:
            # Find the first existing parent or the path itself
            check_path = path
            while check_path and not check_path.exists():
                if check_path.parent == check_path: # Reached root
                    break
                check_path = check_path.parent
            
            if check_path and check_path.exists():
                if not os.access(str(check_path), os.W_OK):
                    report.error(
                        "project.output_root.readonly",
                        f"Output root or its parent is read-only: {check_path}",
                        subject=subject,
                        field="output_root",
                    )
    except Exception:
        # Avoid crashing validation due to OS/path errors
        pass

    return report



_LIGHTING_SUPPORTED_LIGHT_TYPES = frozenset({"POINT", "SPOT", "SUN", "AREA"})


def project_has_enabled_lighting_maps(project: Any) -> bool:
    return any(
        constants.effective_lighting_map_type(map_item) is not None
        for map_item in _enabled_maps(project)
    )


_MATERIAL_OUTPUT_NODE_TYPE = "OUTPUT_MATERIAL"
_PRINCIPLED_NODE_TYPE = "BSDF_PRINCIPLED"
_EMISSION_NODE_TYPE = "EMISSION"


def _lighting_surface_shader(material: Any) -> Any:
    """Duck-typed mirror of export._material_surface_shader: the shader node
    feeding the active Material Output, or a lone Principled/Emission node."""
    node_tree = _get_value(material, "node_tree", None)
    nodes = _as_iterable(_get_value(node_tree, "nodes", []))
    if not nodes:
        return None
    output_node = None
    for node in nodes:
        if str(_get_value(node, "type", "")) != _MATERIAL_OUTPUT_NODE_TYPE:
            continue
        output_node = node
        if bool(_get_value(node, "is_active_output", False)):
            break
    if output_node is not None:
        inputs = _get_value(output_node, "inputs", None)
        surface = inputs.get("Surface") if hasattr(inputs, "get") else None
        if surface is not None and bool(_get_value(surface, "is_linked", False)):
            links = _get_value(surface, "links", None) or ()
            if links:
                shader = _get_value(links[0], "from_node", None)
                if shader is not None:
                    return shader
        return None
    for node in nodes:
        if str(_get_value(node, "type", "")) in (_PRINCIPLED_NODE_TYPE, _EMISSION_NODE_TYPE):
            return node
    return None


def _socket_is_linked(node: Any, socket_name: str) -> bool:
    inputs = _get_value(node, "inputs", None)
    socket = inputs.get(socket_name) if hasattr(inputs, "get") else None
    if socket is None:
        return False
    return bool(_get_value(socket, "is_linked", False))


def _classify_lighting_material(material: Any) -> tuple[bool, bool, bool]:
    """Return (has_textured_albedo, has_textured_emission, is_unsupported) using
    the same traversal export does, so preflight warnings track what will bake."""
    if not bool(_get_value(material, "use_nodes", False)):
        return False, False, False
    shader = _lighting_surface_shader(material)
    shader_type = str(_get_value(shader, "type", "")) if shader is not None else ""
    if shader_type == _PRINCIPLED_NODE_TYPE:
        textured_albedo = _socket_is_linked(shader, "Base Color")
        textured_emission = _socket_is_linked(shader, "Emission Color") or _socket_is_linked(shader, "Emission Strength")
        return textured_albedo, textured_emission, False
    if shader_type == _EMISSION_NODE_TYPE:
        textured_emission = _socket_is_linked(shader, "Color") or _socket_is_linked(shader, "Strength")
        return False, textured_emission, False
    return False, False, True


def validate_scene_lighting(project: Any, scene: Any) -> ValidationReport:
    """Scene-dependent preflight for LIGHTING/LIT_COLOR maps. `scene` is a
    Blender scene (or a duck-typed stand-in for tests); this module stays
    bpy-free, so callers with real scene access wire this in (preflight op)."""
    report = ValidationReport()
    if not project_has_enabled_lighting_maps(project):
        return report

    project_name = _normalized_label(_get_value(project, "name", ""))
    supported_light_found = False
    for scene_object in _as_iterable(_get_value(scene, "objects", [])):
        if str(_get_value(scene_object, "type", "")) != "LIGHT":
            continue
        if bool(_get_value(scene_object, "hide_render", False)):
            continue
        light_data = _get_value(scene_object, "data", None)
        light_type = str(_get_value(light_data, "type", "") or "").upper()
        object_name = _normalized_label(_get_value(scene_object, "name", "")) or "Light"
        if light_type not in _LIGHTING_SUPPORTED_LIGHT_TYPES:
            report.warning(
                "scene.lighting.unsupported_light_type",
                f"Light type '{light_type}' is not supported by lighting maps and will be ignored.",
                subject=project_name,
                object_name=object_name,
            )
            continue
        try:
            energy = float(_get_value(light_data, "energy", 0.0))
        except (TypeError, ValueError):
            energy = 0.0
        if energy < 0.0:
            report.error(
                "scene.lighting.negative_energy",
                "Negative light energy is not supported for predictable physically based lighting.",
                subject=project_name,
                object_name=object_name,
                field="energy",
            )
            continue
        if energy > 0.0:
            supported_light_found = True

    world = _get_value(scene, "world", None)
    world_contributes = False
    world_is_procedural = False
    if world is not None:
        if bool(_get_value(world, "use_nodes", False)):
            node_tree = _get_value(world, "node_tree", None)
            for node in _as_iterable(_get_value(node_tree, "nodes", [])):
                if str(_get_value(node, "type", "")) != "BACKGROUND":
                    continue
                inputs = _get_value(node, "inputs", None)
                color_input = inputs.get("Color") if hasattr(inputs, "get") else None
                if color_input is not None and bool(_get_value(color_input, "is_linked", False)):
                    # A single Environment Texture image feeding the Background is
                    # supported (exported as a lat-long cache); anything else in the
                    # graph is procedural and unsupported for now.
                    links = _get_value(color_input, "links", None) or ()
                    from_node = _get_value(links[0], "from_node", None) if len(links) == 1 else None
                    is_direct_environment_image = (
                        str(_get_value(from_node, "type", "")) == "TEX_ENVIRONMENT"
                        and _get_value(from_node, "image", None) is not None
                    )
                    world_is_procedural = not is_direct_environment_image
                    world_contributes = True
                else:
                    color_value = tuple(_get_value(color_input, "default_value", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0))[:3]
                    world_contributes = any(float(component) > 0.0 for component in color_value)
                break
        else:
            color_value = tuple(_get_value(world, "color", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))[:3]
            world_contributes = any(float(component) > 0.0 for component in color_value)

    if world_is_procedural:
        report.warning(
            "scene.lighting.world_hdri_unsupported",
            "Procedural world graphs are not supported yet; connect an Environment Texture image directly to the Background node or use a constant color.",
            subject=project_name,
            field="world",
        )

    if not supported_light_found and not world_contributes:
        report.warning(
            "scene.lighting.no_light_sources",
            "No enabled light or world contribution found; lighting maps will bake black. Emissive meshes are not counted by this check yet.",
            subject=project_name,
        )

    # Textured Base Color / Emission need no warning: Lit Color multiplies the baked
    # material channels, and bounces and emissive lights carry their averages.
    seen_materials: set[str] = set()
    for scene_object in _as_iterable(_get_value(scene, "objects", [])):
        if str(_get_value(scene_object, "type", "")) != "MESH":
            continue
        if bool(_get_value(scene_object, "hide_render", False)):
            continue
        for slot in _as_iterable(_get_value(scene_object, "material_slots", [])):
            material = _get_value(slot, "material", None)
            if material is None:
                continue
            name = _normalized_label(_get_value(material, "name", ""))
            if not name or name in seen_materials:
                continue
            # The addon's own preview materials are temporary viewport-only
            # node graphs; export skips them, so preflight must too.
            if name.startswith(constants.PREVIEW_MATERIAL_NAME_PREFIX):
                continue
            seen_materials.add(name)
            _textured_albedo, _textured_emission, unsupported = _classify_lighting_material(material)
            if unsupported:
                report.warning(
                    "scene.lighting.unsupported_material",
                    f"Material '{name}' is not a Principled or Emission shader; scene lighting bakes only its diffuse color.",
                    subject=project_name,
                    object_name=name,
                )

    return report


def _group_has_ao_non_casters(group: Any) -> bool:
    """Whether a high mesh slot of *group* has Casts AO off (Use Low as High ignores it)."""
    role_state = _get_value(group, "role_assignments", None)
    if bool(_get_value(role_state, "use_low_as_high", _get_value(group, "use_low_as_high", False))):
        return False
    for collection in (_get_value(role_state, "high_meshes", None), _get_value(group, "high_meshes", None)):
        for slot in _as_iterable(collection):
            obj = _get_value(slot, "object_ref", None)
            if obj is not None and not bool(_get_value(slot, "casts_ao", True)):
                return True
    return False


def validate_bake_group(
    group: Any,
    *,
    mesh_metadata: Any = None,
    check_topology: bool = False,
    require_high: bool = True,
    allow_complete_mirror: bool = False,
) -> ValidationReport:
    report = ValidationReport()

    group_name = _normalized_label(_get_value(group, "name", ""))

    if not group_name:
        report.error(
            "group.name.missing",
            "Bake group is missing a name.",
            field="name",
        )

    low_meshes = _resolved_mesh_assignments(_get_value(group, "low_meshes", []))
    role_state = _get_value(group, "role_assignments", None)
    use_low_as_high = bool(
        _get_value(role_state, "use_low_as_high", _get_value(group, "use_low_as_high", False))
    )
    configured_high_meshes = _resolved_mesh_assignments(_get_value(group, "high_meshes", []))
    high_meshes = list(low_meshes) if use_low_as_high else configured_high_meshes
    cage_meshes = _resolved_mesh_assignments(_get_value(group, "cage_meshes", []))
    cage_mode = _normalized_label(_get_value(group, "cage_mode", ""))
    requested_uv_layer_name = _normalized_label(_get_value(group, "uv_layer_name", ""))

    if not low_meshes:
        report.error(
            "group.low_meshes.missing",
            _missing_mesh_message("low", high_meshes),
            subject=group_name,
            group_name=group_name,
            field="low_meshes",
        )

    # MATERIAL-workflow projects flatten each object's own materials (SELF_MATERIAL) and
    # never require a high-poly source; only projected (HIGH_TO_LOW) groups do.
    if require_high and not high_meshes:
        report.error(
            "group.high_meshes.missing",
            _missing_mesh_message("high", low_meshes),
            subject=group_name,
            group_name=group_name,
            field="high_meshes",
        )

    low_ids = _validate_unique_mesh_refs(report, low_meshes, group_name=group_name, role="low")
    high_ids = _validate_unique_mesh_refs(report, high_meshes, group_name=group_name, role="high")
    _validate_unique_mesh_refs(report, cage_meshes, group_name=group_name, role="cage")
    complete_low_to_low_mirror = bool(low_ids) and low_ids == high_ids
    _validate_role_overlap(
        report,
        group_name,
        "low",
        low_meshes,
        "high",
        high_meshes,
        allow_complete_mirror=use_low_as_high or (allow_complete_mirror and complete_low_to_low_mirror),
    )
    if low_ids & high_ids and not (use_low_as_high or (allow_complete_mirror and complete_low_to_low_mirror)):
        report.warning(
            "group.role_overlap.duplicate_reference",
            "A mesh is assigned to both low and high roles in the same group.",
            subject=group_name,
            group_name=group_name,
            field="low_meshes",
        )

    if cage_mode == constants.CAGE_MODE_CUSTOM:
        custom_cage = (
            _get_value(group, "custom_cage", None)
            or _get_value(group, "cage_object", None)
            or _get_value(group, "custom_cage_object", None)
        )
        if custom_cage is None and cage_meshes:
            custom_cage = cage_meshes[0]
        if custom_cage is None:
            report.error(
                "group.custom_cage.missing",
                "Custom cage mode requires a custom cage object.",
                subject=group_name,
                group_name=group_name,
                field="custom_cage",
            )
        else:
            custom_cage_metadata = _resolve_mesh_metadata(mesh_metadata, custom_cage)
            cage_count = _topology_count(custom_cage_metadata)
            low_counts = [
                count
                for count in (
                    _topology_count(_resolve_mesh_metadata(mesh_metadata, mesh))
                    for mesh in low_meshes
                )
                if count is not None
            ]
            if cage_count is not None and low_counts:
                if cage_count != sum(low_counts):
                    report.error(
                        "group.custom_cage.topology_mismatch",
                        "Custom cage topology does not match the low mesh topology.",
                        subject=group_name,
                        group_name=group_name,
                        object_name=_normalized_label(_get_value(custom_cage, "object_name", "")),
                        field="custom_cage",
                    )
        if len(cage_meshes) > 1:
            report.warning(
                "group.custom_cage.extra_meshes",
                "Custom cage mode received multiple cage meshes; only the first one is used.",
                subject=group_name,
                group_name=group_name,
                field="cage_meshes",
            )
    elif cage_meshes and cage_mode != constants.CAGE_MODE_AUTOMATIC:
        # AUTOMATIC groups legitimately ship cage meshes: the addon exports its
        # Python-fitted cage with every automatic bake (preview == bake), so only
        # warn when a stray cage reaches a mode that will actually ignore it.
        report.warning(
            "group.cage_meshes.ignored",
            "Cage meshes are present but the group is not in custom cage mode.",
            subject=group_name,
            group_name=group_name,
            field="cage_meshes",
        )

    for mesh in low_meshes:
        metadata = _resolve_mesh_metadata(mesh_metadata, mesh)
        uv_count = _uv_layer_count(metadata)
        if uv_count is None:
            uv_count = _object_uv_layer_count(mesh)
        if uv_count is not None and uv_count <= 0:
            object_name = _normalized_label(_get_value(mesh, "object_name", _get_value(mesh, "name", "")))
            report.error(
                "group.low_mesh.missing_uvs",
                "Low mesh is missing UV layers.",
                subject=group_name,
                group_name=group_name,
                object_name=object_name,
                field="low_meshes",
            )
            continue

        only_material = str(getattr(_get_value(group, "low_material", None), "name", "") or "")
        low_object = _get_value(mesh, "object_ref", None)
        if only_material and low_object is not None:
            from . import low_material_subset

            if not low_material_subset.has_faces(low_object, only_material):
                report.error(
                    "group.low_mesh.no_material_faces",
                    f"Low mesh has no faces using the material '{only_material}'. Assign some, or clear Only Material.",
                    subject=group_name,
                    group_name=group_name,
                    object_name=_normalized_label(getattr(low_object, "name", "")),
                    field="low_material",
                )
                continue

        if check_topology:
            if not _object_is_manifold(mesh):
                object_name = _normalized_label(_get_value(mesh, "object_name", _get_value(mesh, "name", "")))
                report.warning(
                    "group.low_mesh.non_manifold",
                    f"Low mesh '{object_name}' has non-manifold geometry, which may cause artifacts.",
                    subject=group_name,
                    group_name=group_name,
                    object_name=object_name,
                    field="low_meshes",
                )

        if requested_uv_layer_name:

            uv_layer_names = _uv_layer_names(metadata)
            if not uv_layer_names:
                uv_layer_names = _object_uv_layer_names(mesh)
            normalized_names = {name.casefold() for name in uv_layer_names if name}
            if normalized_names and requested_uv_layer_name.casefold() not in normalized_names:
                object_name = _normalized_label(_get_value(mesh, "object_name", _get_value(mesh, "name", "")))
                report.error(
                    "group.low_mesh.uv_layer_missing",
                    f"Low mesh is missing the requested UV set '{requested_uv_layer_name}'.",
                    subject=group_name,
                    group_name=group_name,
                    object_name=object_name,
                    field="uv_layer_name",
                )

    return report


# --------------------------------------------------------------------------------------
# UDIM tiles
# --------------------------------------------------------------------------------------

# Hard ceiling on any single output dimension. The reprojection backend rejects anything
# larger outright (backend/src/backend_texture_reprojection.cpp:1959) and properties.py only
# declares soft_max=16384, which Blender does not enforce -- so an oversized tile has to be a
# blocking preflight error instead of a failure deep in the backend.
#
_TILE_RESOLUTION_MAX = constants.UDIM_TILE_RESOLUTION_MAX


@dataclass(slots=True)
class UdimTileOccupancy:
    """UV-tile detection result for one texture set.

    Built by the caller from :func:`addon.udim.detect_occupied_tiles`, which needs ``bpy``.
    This module stays bpy-free, so occupancy arrives as plain data.
    """

    detected_tiles: tuple[int, ...] = ()
    border_crossing_triangles: int = 0
    errors: tuple[str, ...] = ()


@dataclass(slots=True)
class _UdimScope:
    """One logical output scope: a texture set, or a standalone bake group.

    ``config`` is whatever object carries ``udim_mode`` / ``udim_tiles``. For a standalone
    group (or a legacy ``texture_set_name`` with no matching texture-set entry) it is the
    group itself, which has no UDIM fields -- and :mod:`addon.udim` reads every one of them
    through ``getattr`` defaults, so that resolves to plain Automatic/tile-1001 behaviour.
    """

    label: str
    config: Any
    texture_set_name: str
    occupancy: UdimTileOccupancy
    occupancy_known: bool
    groups: list[Any] = field(default_factory=list)
    tile_tokens: tuple[str | None, ...] = (None,)


def _coerce_udim_occupancy(value: Any) -> UdimTileOccupancy:
    """Accept a :class:`UdimTileOccupancy`, a bare iterable of tile numbers, or a
    ``(tiles, crossing_count, errors)`` triple as returned by ``detect_occupied_tiles``."""
    if value is None:
        return UdimTileOccupancy()
    if isinstance(value, UdimTileOccupancy):
        return value
    if (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], (list, tuple, set, frozenset))
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    ):
        # ``detect_occupied_tiles`` returns (tiles, crossing_count, errors). The shape test is
        # strict so a bare 3-tuple of tile numbers is not mistaken for it.
        tiles, crossing, errors = value
        return UdimTileOccupancy(
            detected_tiles=tuple(_udim_numbers(tiles)),
            border_crossing_triangles=_int_or_zero(crossing),
            errors=tuple(_normalized_label(item) for item in _as_iterable(errors) if _normalized_label(item)),
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return UdimTileOccupancy(detected_tiles=tuple(_udim_numbers(value)))
    return UdimTileOccupancy(
        detected_tiles=tuple(_udim_numbers(_get_value(value, "detected_tiles", ()))),
        border_crossing_triangles=_int_or_zero(_get_value(value, "border_crossing_triangles", 0)),
        errors=tuple(
            _normalized_label(item)
            for item in _as_iterable(_get_value(value, "errors", ()))
            if _normalized_label(item)
        ),
    )


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _udim_numbers(values: Any) -> list[int]:
    numbers: list[int] = []
    try:
        items = _as_iterable(values)
    except TypeError:
        return numbers
    for item in items:
        try:
            numbers.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(numbers))


def _udim_occupancy_lookup(occupancy: Any) -> dict[str, UdimTileOccupancy]:
    if occupancy is None:
        return {}
    if isinstance(occupancy, Mapping):
        items = occupancy.items()
    else:
        items = getattr(occupancy, "items", lambda: [])()
    return {
        _normalized_label(key).casefold(): _coerce_udim_occupancy(value)
        for key, value in items
        if _normalized_label(key)
    }


def _udim_scopes(project: Any, occupancy: Any) -> tuple[list[_UdimScope], list[tuple[Any, _UdimScope]]]:
    """Every logical output scope in the project, plus the group→scope pairing in
    ``project.groups`` order (so collision reporting keeps its existing ordering)."""
    lookup = _udim_occupancy_lookup(occupancy)
    scopes: list[_UdimScope] = []
    # Keyed by KIND plus name. A texture set and an unrelated standalone bake group may
    # legitimately carry the same name, and they are not the same output scope: the set
    # owns the UDIM mode and the tile rows, a standalone group owns neither. Keying on the
    # bare name merged them, so a group called "Metal" silently inherited the tiles of a
    # texture set called "Metal" it was never assigned to.
    by_key: dict[tuple[str, str], _UdimScope] = {}
    ordered: list[tuple[Any, _UdimScope]] = []

    def _make(
        label: str,
        config: Any,
        texture_set_name: str,
        key: tuple[str, str],
        occupancy_key: str,
    ) -> _UdimScope:
        scope = _UdimScope(
            label=label,
            config=config,
            texture_set_name=texture_set_name,
            occupancy=lookup.get(occupancy_key, UdimTileOccupancy()),
            occupancy_known=occupancy_key in lookup,
        )
        by_key[key] = scope
        scopes.append(scope)
        return scope

    for texture_set in _as_iterable(_get_value(project, "texture_sets", [])):
        name = _normalized_label(_get_value(texture_set, "name", ""))
        if not name:
            continue
        key = ("set", name.casefold())
        if key in by_key:
            continue
        _make(name, texture_set, name, key, name.casefold())

    for group in _as_iterable(_get_value(project, "groups", [])):
        set_name = _normalized_label(_get_value(group, "texture_set_name", ""))
        group_name = _normalized_label(_get_value(group, "name", "")) or "BakeGroup"
        label = set_name or group_name
        if set_name:
            key = ("set", set_name.casefold())
            occupancy_key = set_name.casefold()
        else:
            key = ("group", group_name.casefold())
            # Occupancy may be keyed by a standalone group's name, but a same-named
            # texture set owns that entry: export.collect_udim_occupancy only ever keys
            # by set name. Leave this group's occupancy unknown rather than borrow it.
            occupancy_key = "" if ("set", group_name.casefold()) in by_key else group_name.casefold()
        scope = by_key.get(key)
        if scope is None:
            scope = _make(label, group, set_name, key, occupancy_key)
        scope.groups.append(group)
        ordered.append((group, scope))

    return scopes, ordered


def _udim_resolution_problem(value: Any) -> tuple[str, str]:
    """The single per-tile resolution rule: ``("", "")`` when acceptable, otherwise the
    error-code suffix plus a human reason. Shared by the preflight check and the UI table so
    the two cannot drift apart."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return "resolution_invalid", "must be a positive integer"
    if numeric <= 0:
        return "resolution_invalid", "must be a positive integer"
    if numeric > _TILE_RESOLUTION_MAX:
        return (
            "resolution_too_large",
            f"is {numeric}, above the maximum supported {_TILE_RESOLUTION_MAX}",
        )
    return "", ""


def _validate_udim_resolution(
    report: ValidationReport,
    value: Any,
    *,
    label: str,
    udim_tile: Any,
    axis: str,
    field: str,
) -> None:
    suffix, reason = _udim_resolution_problem(value)
    if not suffix:
        return
    report.error(
        f"texture_set.udim_tile.{suffix}",
        f"Texture set '{label}' tile {udim_tile} {axis} {reason}.",
        subject=label,
        field=field,
    )


def _validate_udim_override_resolution(
    report: ValidationReport,
    row: Any,
    *,
    label: str,
    udim_tile: int,
) -> None:
    if row is None:
        return
    _validate_udim_resolution(
        report,
        _get_value(row, "resolution_x", None),
        label=label,
        udim_tile=udim_tile,
        axis="width",
        field="resolution_x",
    )
    _validate_udim_resolution(
        report,
        _get_value(row, "resolution_y", None),
        label=label,
        udim_tile=udim_tile,
        axis="height",
        field="resolution_y",
    )


def _validate_udim_scope(
    report: ValidationReport,
    scope: _UdimScope,
    *,
    project_width: int,
    project_height: int,
    project_resolution_valid: bool,
) -> None:
    from . import udim  # local: keeps the module import graph flat and this file bpy-free

    label = scope.label
    config = scope.config

    # 1 + 4: tile range and duplicate rows. Read the raw rows rather than udim._tile_rows,
    # which silently drops out-of-range numbers -- silently dropping is exactly what must not
    # happen at preflight.
    seen_tiles: set[int] = set()
    authored: dict[int, Any] = {}
    for row in _as_iterable(_get_value(config, "udim_tiles", [])):
        raw = _get_value(row, "number", None)
        try:
            token = naming.normalize_udim_tile(raw)
        except naming.InvalidUdimTileError:
            report.error(
                "texture_set.udim_tile.out_of_range",
                f"Texture set '{label}' lists UDIM tile {raw!r}, which is outside the "
                f"supported range {constants.UDIM_TILE_MIN}-{constants.UDIM_TILE_MAX}.",
                subject=label,
                field="udim_tiles",
            )
            continue
        if token is None:
            report.error(
                "texture_set.udim_tile.missing",
                f"Texture set '{label}' has a tile row with no tile number.",
                subject=label,
                field="udim_tiles",
            )
            continue
        number = int(token)
        if number in seen_tiles:
            report.error(
                "texture_set.udim_tile.duplicate",
                f"Texture set '{label}' lists UDIM tile {number} more than once.",
                subject=label,
                field="udim_tiles",
            )
            continue
        seen_tiles.add(number)
        authored[number] = row

    # Detection failures (non-finite UVs, negative tile space, >64 tiles on one triangle)
    # are blocking: the tile set cannot be trusted.
    for message in scope.occupancy.errors:
        report.error(
            "texture_set.udim_uv.invalid",
            f"Texture set '{label}': {message}",
            subject=label,
            field="udim_tiles",
        )

    try:
        specs, warnings = udim.resolve_effective_tiles(
            config,
            scope.occupancy.detected_tiles,
            project_width,
            project_height,
            occupancy_known=scope.occupancy_known,
        )
    except (TypeError, ValueError):
        # Tile selection could not be resolved (non-numeric override values). Fall back to
        # checking the authored overrides directly so the bad values still block the bake.
        for number, row in authored.items():
            if bool(_get_value(row, "use_resolution_override", False)):
                _validate_udim_override_resolution(report, row, label=label, udim_tile=number)
        return

    # 5: occupied-but-excluded, force-included-empty and empty-Explicit warnings are composed
    # by resolve_effective_tiles. Surfaced verbatim so the selection logic lives in one place.
    for message in warnings:
        report.warning(
            "texture_set.udim_tiles.warning",
            message,
            subject=label,
            field="udim_tiles",
        )

    crossing = scope.occupancy.border_crossing_triangles
    if crossing > 0:
        report.warning(
            "texture_set.udim_tiles.border_crossing",
            f"Texture set '{label}' has {crossing} UV triangle"
            f"{'' if crossing == 1 else 's'} crossing a UDIM tile border; each tile is "
            "filtered as an independent texture, so those seams cannot be made seamless.",
            subject=label,
            field="udim_tiles",
        )

    # 2: the project resolution limits, applied to each tile's *effective* resolution. An
    # overridden tile is checked against its authored value rather than the TileSpec, because
    # resolve_effective_tiles clamps a zero/negative override up to 1 and would hide it. An
    # inherited resolution is skipped when the project value already failed, so one bad
    # project resolution does not repeat itself once per tile.
    for spec in specs:
        if spec.resolution_overridden:
            _validate_udim_override_resolution(
                report, authored.get(spec.udim_tile), label=label, udim_tile=spec.udim_tile
            )
            continue
        if not project_resolution_valid:
            continue
        _validate_udim_resolution(
            report,
            spec.width,
            label=label,
            udim_tile=spec.udim_tile,
            axis="width",
            field="resolution_x",
        )
        _validate_udim_resolution(
            report,
            spec.height,
            label=label,
            udim_tile=spec.udim_tile,
            axis="height",
            field="resolution_y",
        )

    if specs and udim.uses_tokenized_naming(config, specs):
        scope.tile_tokens = tuple(str(spec.udim_tile) for spec in specs)
    else:
        scope.tile_tokens = (None,)


def _validate_udim_output_collisions(
    report: ValidationReport,
    project: Any,
    ordered: Iterable[tuple[Any, _UdimScope]],
) -> None:
    """Two maps that would write the same *concrete* numeric path is an error.

    This is the tile-aware form of the project output-name collision check: the key is the
    physical file name, which now carries the ``.NNNN`` tile segment whenever tokenized
    naming is active. Groups sharing one texture set are exempt -- they intentionally
    composite into the same file. That exemption is strictly *across* groups: a single group
    writing one file twice (two enabled maps with the same output suffix) is always an error,
    because the second bake silently overwrites the first.
    """
    if not _has_value(project, "groups"):
        return
    project_name = _normalized_label(_get_value(project, "name", ""))
    enabled_maps = _enabled_maps(project)
    owners: dict[str, tuple[int, str, str]] = {}
    for group_index, (group, scope) in enumerate(ordered):
        group_name = _normalized_label(_get_value(group, "name", "")) or "BakeGroup"
        group_texture_set = _normalized_label(_get_value(group, "texture_set_name", ""))
        for file_name in _project_group_output_file_names(
            project, group, enabled_maps, udim_tiles=scope.tile_tokens
        ):
            key = file_name.casefold()
            prior = owners.get(key)
            if prior is None:
                owners[key] = (group_index, group_name, group_texture_set)
                continue
            prior_index, prior_owner, prior_ts = prior
            same_group = prior_index == group_index
            # Groups sharing the same explicit texture_set_name intentionally produce the
            # same output file — the backend composites them into one texture. A group is
            # trivially equal to itself, so the exemption must never cover a collision
            # between two maps of the *same* group.
            if (
                not same_group
                and prior_ts
                and group_texture_set
                and prior_ts.casefold() == group_texture_set.casefold()
            ):
                continue
            if same_group:
                message = (
                    f"Bake group '{group_name}' would write '{file_name}' twice. "
                    "Two enabled maps resolve to the same file name."
                )
            else:
                message = f"Bake groups '{prior_owner}' and '{group_name}' would both write '{file_name}'."
            report.error(
                "project.outputs.duplicate_file_name",
                message,
                subject=project_name,
                group_name=group_name,
                field="groups",
            )


def project_output_file_names(project: Any, *, occupancy: Any = None) -> set[str]:
    """Planned bake filenames using the same map, texture-set and tile rules as preflight."""
    from . import udim

    scopes, ordered = _udim_scopes(project, occupancy)
    for scope in scopes:
        try:
            specs, _warnings = udim.resolve_effective_tiles(
                scope.config,
                scope.occupancy.detected_tiles,
                max(1, _int_or_zero(_project_resolution_value(project, "x"))),
                max(1, _int_or_zero(_project_resolution_value(project, "y"))),
                occupancy_known=scope.occupancy_known,
            )
        except (TypeError, ValueError):
            # Invalid tile settings are reported by validate_udim_tiles.
            continue
        if specs and udim.uses_tokenized_naming(scope.config, specs):
            scope.tile_tokens = tuple(str(spec.udim_tile) for spec in specs)
    enabled_maps = _enabled_maps(project)
    return {
        name
        for group, scope in ordered
        for name in _project_group_output_file_names(
            project, group, enabled_maps, udim_tiles=scope.tile_tokens
        )
    }


def validate_udim_tiles(project: Any, *, occupancy: Any = None) -> ValidationReport:
    """Per-tile preflight for every texture set in *project*.

    ``occupancy`` maps a texture-set name (or a standalone bake group's name) to the UV-tile
    detection result for that scope — a :class:`UdimTileOccupancy`, a bare iterable of tile
    numbers, or the ``(tiles, crossing_count, errors)`` triple that
    :func:`addon.udim.detect_occupied_tiles` returns. It is optional because detection needs
    ``bpy`` and this module stays bpy-free: without it the authored tile rows, their
    resolutions and their output paths are still validated, only detected occupancy is
    unknown.

    Errors block the bake; warnings do not.
    """
    report = ValidationReport()

    project_width = _int_or_zero(_project_resolution_value(project, "x"))
    project_height = _int_or_zero(_project_resolution_value(project, "y"))
    project_resolution_valid = (
        0 < project_width <= _TILE_RESOLUTION_MAX and 0 < project_height <= _TILE_RESOLUTION_MAX
    )

    scopes, ordered = _udim_scopes(project, occupancy)
    for scope in scopes:
        _validate_udim_scope(
            report,
            scope,
            project_width=max(1, project_width),
            project_height=max(1, project_height),
            project_resolution_valid=project_resolution_valid,
        )

    _validate_udim_output_collisions(report, project, ordered)
    return report


@dataclass(slots=True)
class UdimTileState:
    """One row of the texture-set tile table.

    Purely descriptive: severity/message repeat what :func:`validate_udim_tiles` would report
    for this tile, so the panel can show a state column without re-deriving the rules.
    """

    udim_tile: int
    width: int
    height: int
    detected: bool = False
    configured: bool = False
    override: str = constants.UDIM_TILE_OVERRIDE_NONE
    resolution_overridden: bool = False
    baked: bool = False
    severity: str = ""
    message: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == SEVERITY_ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == SEVERITY_WARNING

    @property
    def resolution_label(self) -> str:
        return f"{self.width}x{self.height}"


def udim_tile_states(
    texture_set: Any,
    *,
    project_width: int,
    project_height: int,
    detected_tiles: Iterable[int] = (),
) -> list[UdimTileState]:
    """Tile-table rows for *texture_set*, ascending by tile number.

    Covers the union of the artist's tile rows, the detected occupancy and the tiles that
    would actually be baked, so an excluded tile and an undetected-but-included tile both
    still have a row. ``detected_tiles`` comes from :func:`addon.udim.detect_occupied_tiles`;
    an empty value simply means occupancy has not been sampled yet.
    """
    from . import udim

    fallback_width = max(1, _int_or_zero(project_width) or 1)
    fallback_height = max(1, _int_or_zero(project_height) or 1)
    detected = set(_udim_numbers(detected_tiles))

    rows: dict[int, Any] = {}
    invalid_rows: list[UdimTileState] = []
    duplicate_tiles: set[int] = set()
    for row in _as_iterable(_get_value(texture_set, "udim_tiles", [])):
        raw = _get_value(row, "number", None)
        try:
            token = naming.normalize_udim_tile(raw)
        except naming.InvalidUdimTileError:
            invalid_rows.append(
                UdimTileState(
                    udim_tile=_int_or_zero(raw),
                    width=fallback_width,
                    height=fallback_height,
                    configured=True,
                    severity=SEVERITY_ERROR,
                    message=(
                        f"Tile {raw!r} is outside the supported range "
                        f"{constants.UDIM_TILE_MIN}-{constants.UDIM_TILE_MAX}."
                    ),
                )
            )
            continue
        if token is None:
            continue
        number = int(token)
        if number in rows:
            duplicate_tiles.add(number)
            continue
        rows[number] = row

    try:
        specs, _warnings = udim.resolve_effective_tiles(
            texture_set, detected, fallback_width, fallback_height
        )
    except (TypeError, ValueError):
        specs = []
    spec_by_tile = {spec.udim_tile: spec for spec in specs}

    states: list[UdimTileState] = []
    for number in sorted(set(rows) | detected | set(spec_by_tile)):
        row = rows.get(number)
        spec = spec_by_tile.get(number)
        override = str(_get_value(row, "override", constants.UDIM_TILE_OVERRIDE_NONE) or "")
        resolution_overridden = bool(_get_value(row, "use_resolution_override", False))
        if spec is not None:
            width, height = spec.width, spec.height
        elif resolution_overridden:
            width = _int_or_zero(_get_value(row, "resolution_x", fallback_width))
            height = _int_or_zero(_get_value(row, "resolution_y", fallback_height))
        else:
            width, height = fallback_width, fallback_height

        state = UdimTileState(
            udim_tile=number,
            width=width,
            height=height,
            detected=number in detected,
            configured=row is not None,
            override=override or constants.UDIM_TILE_OVERRIDE_NONE,
            resolution_overridden=resolution_overridden,
            baked=spec is not None,
        )

        if number in duplicate_tiles:
            state.severity = SEVERITY_ERROR
            state.message = f"Tile {number} is listed more than once."
        else:
            for axis, value, raw_value in (
                ("Width", width, _get_value(row, "resolution_x", None)),
                ("Height", height, _get_value(row, "resolution_y", None)),
            ):
                checked = raw_value if resolution_overridden else value
                _suffix, reason = _udim_resolution_problem(checked)
                if reason:
                    state.severity = SEVERITY_ERROR
                    state.message = f"{axis} {reason}."
                    break
        if not state.severity:
            if state.override == constants.UDIM_TILE_OVERRIDE_EXCLUDE and state.detected:
                state.severity = SEVERITY_WARNING
                state.message = "Occupied by geometry but excluded; that geometry is not baked."
            elif state.baked and not state.detected:
                state.severity = SEVERITY_WARNING
                state.message = "No geometry occupies this tile; it is written with the default fill."

        states.append(state)

    return invalid_rows + states


def _validate_renderer_map_support(
    report: ValidationReport,
    enabled_maps: Iterable[Any],
    *,
    subject: str = "",
) -> None:
    """Warn when enabled maps cannot be produced by the currently active renderer.

    Fyr bakes every map type, so this only ever fires with Cycles active. Fails
    loudly at preflight rather than letting the user discover it mid-bake.
    """
    try:
        from . import bake_backends

        caps = bake_backends.active_capabilities()
    except Exception:
        return
    if caps.backend_id != "cycles":
        return

    unsupported: list[str] = []
    for map_item in enabled_maps or []:
        map_type = str(_get_value(map_item, "map_type", "")).strip().upper()
        if not map_type or caps.map_fidelity.get(map_type) != "unsupported":
            continue
        label = _map_type_label(map_type)
        if label not in unsupported:
            unsupported.append(label)
    if not unsupported:
        return
    report.warning(
        "project.maps.renderer_unsupported",
        f"{caps.label} cannot bake {', '.join(unsupported)}; "
        "these maps will be skipped. Switch Bake Renderer to Fyr to include them.",
        subject=subject,
        field="maps",
    )


def _validate_objects_belong_to_one_group(report: ValidationReport, project: Any, *, project_name: str) -> None:
    """Flag a mesh assigned to more than one bake group.

    Groups sharing a texture set composite into ONE image by design, so a mesh that
    belongs to two of them is baked twice into the same texture and the two passes
    fight over the same texels. Every downstream surface inherits the ambiguity too:
    showing a map on a group paints every mesh in it, so the mesh shows up wearing
    another group's map, which reads as "the preview went to the wrong object".

    Seen in a real tester project: `Cube2_low` and `Cube2_high` were members of both
    "Cube" and "Cube2", and both groups fed the same texture set.
    """
    owners: dict[str, tuple[str, str]] = {}  # object key -> (display name, first group)
    duplicates: dict[str, tuple[str, list[str]]] = {}
    for group in _as_iterable(_get_value(project, "groups", [])):
        group_name = _normalized_label(_get_value(group, "name", "")) or "BakeGroup"
        for role in ("low_meshes", "high_meshes"):
            # Resolve the slot to its object first, exactly like every other reader of a
            # role collection (_validate_bake_group, the topology pass). A live
            # MasterBakerObjectSlot declares only ``object_ref``; reading identity off the
            # slot itself found no name at all, so this whole check silently did nothing.
            for mesh in _resolved_mesh_assignments(_get_value(group, role, [])):
                identity = _mesh_ref_identity(mesh)
                if not identity:
                    continue
                key = identity.casefold()
                if key not in owners:
                    owners[key] = (identity, group_name)
                    continue
                first_name, first_group = owners[key]
                if first_group == group_name:
                    continue  # already reported per-group by _validate_unique_mesh_refs
                entry = duplicates.setdefault(key, (first_name, [first_group]))
                if group_name not in entry[1]:
                    entry[1].append(group_name)

    for identity, group_names in duplicates.values():
        report.warning(
            "project.groups.object_in_multiple_groups",
            f"'{identity}' is assigned to more than one bake group "
            f"({', '.join(group_names)}). It will be baked once per group into the "
            "same texture set, and showing a map on either group puts it on this mesh.",
            subject=project_name,
            object_name=identity,
            field="groups",
        )


def validate_bake_project(
    project: Any,
    *,
    mesh_metadata: Any = None,
    check_topology: bool = False,
    udim_occupancy: Any = None,
    probe_filesystem: bool = True,
    other_udim_occupancy_for: Any = None,
) -> ValidationReport:
    """Validate a whole bake project.

    ``probe_filesystem=False`` drops the disk-touching checks (currently the
    output-root permission probe) so a UI draw callback can call this on every
    redraw without hitting the filesystem. Everything that decides whether a bake
    can start keeps the default.
    """
    report = ValidationReport()

    project_name = _normalized_label(_get_value(project, "name", ""))

    if not project_name:
        report.error(
            "project.name.missing",
            "Bake project is missing a name.",
            field="name",
        )

    report.extend(
        validate_output_root(
            _get_value(project, "output_root", None),
            subject=project_name,
            probe_filesystem=probe_filesystem,
        )
    )

    _validate_positive_int(
        report,
        _project_resolution_value(project, "x"),
        code="project.resolution_width.invalid",
        message="Bake project width must be a positive integer.",
        field="resolution_width",
        subject=project_name,
    )
    _validate_positive_int(
        report,
        _project_resolution_value(project, "y"),
        code="project.resolution_height.invalid",
        message="Bake project height must be a positive integer.",
        field="resolution_height",
        subject=project_name,
    )
    # Upper bound, same code as the positive-int check above. properties.py only declares
    # soft_max=16384 (unenforced by Blender) while the reprojection backend hard-rejects
    # anything larger, so the two disagreed until this check existed.
    _validate_max_int(
        report,
        _project_resolution_value(project, "x"),
        maximum=_TILE_RESOLUTION_MAX,
        code="project.resolution_width.invalid",
        message=f"Bake project width cannot exceed {_TILE_RESOLUTION_MAX}.",
        field="resolution_width",
        subject=project_name,
    )
    _validate_max_int(
        report,
        _project_resolution_value(project, "y"),
        maximum=_TILE_RESOLUTION_MAX,
        code="project.resolution_height.invalid",
        message=f"Bake project height cannot exceed {_TILE_RESOLUTION_MAX}.",
        field="resolution_height",
        subject=project_name,
    )

    try:
        margin = int(_get_value(project, "margin", 0))
    except (TypeError, ValueError):
        report.error(
            "project.margin.invalid",
            "Bake project dilation must be an integer.",
            subject=project_name,
            field="margin",
        )
    else:
        if margin < 0:
            report.error(
                "project.margin.invalid",
                "Bake project dilation cannot be negative.",
                subject=project_name,
                field="margin",
            )

    _validate_choice(
        report,
        _get_value(project, "bit_depth", None),
        {constants.BIT_DEPTH_8, constants.BIT_DEPTH_16, 8, 16},
        code="project.bit_depth.invalid",
        message="Bake project bit depth is not supported.",
        field="bit_depth",
        subject=project_name,
    )
    # Format/depth compatibility. The backend writer throws mid-bake ("TGA output only
    # supports 8-bit images") at gpu_shading, i.e. after most of the work is done, so an
    # invalid pair has to fail here instead. EXR ignores bit_depth (always float) and is
    # therefore never rejected.
    project_image_format = _normalized_label(
        _get_value(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT
    ).upper()
    project_bit_depth = _get_value(project, "bit_depth", constants.DEFAULT_BIT_DEPTH)
    format_depth_message = constants.bake_image_format_bit_depth_message(
        project_image_format, project_bit_depth
    )
    if format_depth_message:
        report.error(
            "project.image_format.bit_depth_unsupported",
            format_depth_message,
            subject=project_name,
            field="bit_depth",
        )

    _validate_choice(
        report,
        _get_value(project, "tangent_basis", None),
        {constants.TANGENT_MIKKTSPACE, constants.TANGENT_BLENDER},
        code="project.tangent_basis.invalid",
        message="Bake project tangent basis is not supported.",
        field="tangent_basis",
        subject=project_name,
    )
    _validate_choice(
        report,
        _get_value(project, "bake_mode", None),
        {constants.BAKE_MODE_OFFLINE, constants.BAKE_MODE_DRAFT, constants.BAKE_MODE_FINAL},
        code="project.bake_mode.invalid",
        message="Bake project mode is not supported.",
        field="bake_mode",
        subject=project_name,
    )

    enabled_maps = _enabled_maps(project)
    enabled_material_maps = [
        map_item
        for map_item in enabled_maps
        if str(_get_value(map_item, "map_type", "")).strip().upper() == constants.MAP_MATERIAL
    ]
    enabled_lighting_maps = [
        map_item
        for map_item in enabled_maps
        if constants.effective_lighting_map_type(map_item) is not None
    ]
    if enabled_lighting_maps:
        image_format = str(_get_value(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT).strip().upper()
        if image_format != "EXR":
            report.warning(
                "project.lighting.ldr_output",
                f"Lighting maps are HDR; values above 1.0 will be clipped in {image_format}. Use OpenEXR to preserve them.",
                subject=project_name,
                field="image_format",
            )
    _validate_renderer_map_support(report, enabled_maps, subject=project_name)
    if _has_value(project, "maps"):
        if not enabled_maps:
            report.error(
                "project.maps.missing_enabled",
                "Bake project has no enabled maps.",
                subject=project_name,
                field="maps",
            )
        for map_item in _as_iterable(_get_value(project, "maps", [])):
            if bool(_get_value(map_item, "is_add_phantom", False)):
                continue
            _validate_map_item(report, map_item, subject=project_name)

    # HIGH_TO_LOW projects require a high-poly source per group; MATERIAL projects do not
    # (they self-bake the object's own materials). Never relax projected-job validation.
    require_high_meshes = project_requires_high_meshes(project)

    if _has_value(project, "groups"):
        groups = _as_iterable(_get_value(project, "groups", []))
        if not groups:
            report.error(
                "project.groups.missing",
                "Bake project has no bake groups.",
                subject=project_name,
                field="groups",
            )
        # A group still being filled is skipped, not an error, as long as another group
        # can bake. When none can, every group keeps its full error report so the
        # artist sees exactly what is missing.
        missing_roles = [_group_missing_roles(group, require_high=require_high_meshes) for group in groups]
        skip_incomplete = any(not (low or high) for low, high in missing_roles)
        seen_group_names: set[str] = set()
        for group, (missing_low, missing_high) in zip(groups, missing_roles):
            group_name = _normalized_label(_get_value(group, "name", ""))
            if group_name:
                key = group_name.casefold()
                if key in seen_group_names:
                    report.error(
                        "project.groups.duplicate_name",
                        "Bake project contains duplicate bake group names.",
                        subject=project_name,
                        group_name=group_name,
                        field="groups",
                    )
                else:
                    seen_group_names.add(key)
            if skip_incomplete and (missing_low or missing_high):
                report.warning(
                    "group.incomplete.skipped",
                    _skipped_group_message(missing_low, missing_high),
                    subject=group_name,
                    group_name=group_name,
                    field="low_meshes" if missing_low else "high_meshes",
                )
                continue
            report.extend(validate_bake_group(group, mesh_metadata=mesh_metadata, check_topology=check_topology, require_high=require_high_meshes))
            if enabled_material_maps:
                # Which role actually FEEDS the material bake: a projected (HIGH_TO_LOW)
                # group samples the high meshes' materials, so warning about materialless
                # lows there was a false alarm on a bake that writes correctly. Only a
                # MATERIAL-workflow group (self-material flatten) reads the lows.
                low_meshes = _resolved_mesh_assignments(_get_value(group, "low_meshes", []))
                if require_high_meshes:
                    role_state = _get_value(group, "role_assignments", None)
                    use_low_as_high = bool(
                        _get_value(role_state, "use_low_as_high", _get_value(group, "use_low_as_high", False))
                    )
                    source_meshes = (
                        low_meshes
                        if use_low_as_high
                        else _resolved_mesh_assignments(_get_value(group, "high_meshes", []))
                    )
                    source_role, source_field = "high", "high_meshes"
                    if use_low_as_high:
                        source_field = "low_meshes"
                else:
                    source_meshes = low_meshes
                    source_role, source_field = "low", "low_meshes"
                counts = [_object_material_count(mesh) for mesh in source_meshes]
                known = [c for c in counts if c is not None]
                # Warn only when material data is resolvable and every source mesh lacks one.
                if known and all(c == 0 for c in known):
                    report.warning(
                        "group.material_map.no_source_material",
                        f"Material/Albedo map is enabled but the {source_role} meshes have no "
                        "material assigned, so no material map will be written for this group.",
                        subject=group_name,
                        group_name=group_name,
                        field=source_field,
                    )
        if any(
            str(_get_value(map_item, "map_type", "")).strip().upper() == constants.MAP_AO
            and bool(_get_value(map_item, "enabled", True))
            and str(_get_value(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST)).strip().upper() == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE
            for map_item in _as_iterable(_get_value(project, "maps", []))
        ) and any(bool(_get_value(group, "match_by_isolation", False)) for group in groups):
            report.error(
                "project.ao_diffusive.match_by_isolation_unsupported",
                "Diffusive AO does not support Match by Isolation.",
                subject=project_name,
                field="groups",
            )
        if any(
            str(_get_value(map_item, "map_type", "")).strip().upper() == constants.MAP_AO
            and bool(_get_value(map_item, "enabled", True))
            and str(_get_value(map_item, "ao_mode", constants.MAP_AO_MODE_RAYCAST)).strip().upper() == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE
            for map_item in _as_iterable(_get_value(project, "maps", []))
        ) and any(_group_has_ao_non_casters(group) for group in groups):
            # The diffusive field is one volume of every high mesh; it cannot leave a mesh
            # out of the occlusion while keeping it in the projection.
            report.error(
                "project.ao_diffusive.casts_ao_unsupported",
                "Diffusive AO does not support high meshes with Casts AO off. Use Raycast AO or turn Casts AO back on.",
                subject=project_name,
                field="groups",
            )

    _validate_objects_belong_to_one_group(report, project, project_name=project_name)

    # Per-tile preflight, including the tile-aware output-path collision check that
    # superseded the untiled one. Runs unconditionally: without `udim_occupancy` it still
    # validates authored tile rows, and every collision key collapses to the legacy untiled
    # name, so a project with no UDIM configuration reports exactly what it always did.
    report.extend(validate_udim_tiles(project, occupancy=udim_occupancy))

    from . import project_output_validation

    report.extend(project_output_validation.validate_project_output_ownership(
        project,
        udim_occupancy=udim_occupancy,
        probe_filesystem=probe_filesystem,
        other_udim_occupancy_for=other_udim_occupancy_for,
    ))

    return report


def validate_bake_job(
    job: Any,
    *,
    mesh_metadata: Any = None,
    material_bake_spec_count: int = 0,
    derived_output_count: int = 0,
) -> ValidationReport:
    report = ValidationReport()

    version = _normalized_label(_get_value(job, "version", ""))
    if version and version != constants.PROTOCOL_VERSION:
        report.warning(
            "job.version.unexpected",
            "Bake job protocol version does not match the current addon version.",
            field="version",
        )

    project = _get_value(job, "project", None)
    if project is not None:
        report.extend(validate_bake_project(project, mesh_metadata=mesh_metadata))

    maps = _as_iterable(_get_value(job, "maps", []))
    job_project = _get_value(job, "project", None)
    job_workflow = str(_get_value(job_project, "workflow", constants.WORKFLOW_HIGH_TO_LOW) or constants.WORKFLOW_HIGH_TO_LOW).strip().upper()
    if not [item for item in maps if bool(_get_value(item, "enabled", True))]:
        # HIGH_TO_LOW material channels without an image fast path are baked addon-side
        # (Cycles selected-to-active) and intentionally omit backend map configs.
        has_addon_material_work = (
            job_workflow == constants.WORKFLOW_MATERIAL
            or int(material_bake_spec_count or 0) > 0
            # Wireframe rows: drawn by the addon, never part of the backend job.
            or int(derived_output_count or 0) > 0
        )
        if not has_addon_material_work:
            report.error(
                "job.maps.missing_enabled",
                "Bake job has no enabled maps.",
                field="maps",
            )
    for map_item in maps:
        _validate_map_item(report, map_item, subject="BakeJob")

    groups = _as_iterable(_get_value(job, "groups", []))
    output_owners: dict[str, tuple[str, str]] = {}  # path → (group_name, texture_set)
    for group in groups:
        # Exported low-to-low jobs intentionally contain the same resolved mesh refs
        # in both roles; scene validation remains strict unless the explicit toggle is set.
        group_report = validate_bake_group(group, mesh_metadata=mesh_metadata, allow_complete_mirror=True)
        report.extend(group_report)
        enabled_map_types = {
            _normalized_label(_get_value(map_item, "map_type", "")).casefold()
            for map_item in maps
            if bool(_get_value(map_item, "enabled", True))
        }
        _validate_output_targets(
            report,
            _as_iterable(_get_value(group, "outputs", [])),
            enabled_map_types=enabled_map_types,
            group_name=_normalized_label(_get_value(group, "name", "")),
        )
        group_name = _normalized_label(_get_value(group, "name", "")) or "BakeGroup"
        group_texture_set = _normalized_label(_get_value(group, "texture_set", ""))
        for output in _as_iterable(_get_value(group, "outputs", [])):
            path = _normalized_label(_get_value(output, "path", ""))
            if not path:
                continue
            key = path.casefold()
            prior = output_owners.get(key)
            if prior is None:
                output_owners[key] = (group_name, group_texture_set)
                continue
            prior_owner, prior_ts = prior
            # Groups sharing the same texture set intentionally produce the same
            # output file — the backend composites them into one texture.
            if prior_ts and group_texture_set and prior_ts.casefold() == group_texture_set.casefold():
                continue
            report.error(
                "job.outputs.path.duplicate_across_groups",
                f"Bake groups '{prior_owner}' and '{group_name}' share the same output path.",
                subject=group_name,
                group_name=group_name,
                field="outputs",
            )

    return report
