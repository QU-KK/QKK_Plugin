from __future__ import annotations

import collections
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import math
import shutil
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
from typing import Iterable, NamedTuple
import uuid

import bpy

from . import bake_dependencies, cage_fit_store, distance_offset_queue, color_stream, derived_outputs, floater_faces, paint_sampling
from . import collection_index, low_material_subset, native_mesh_write, rna_buffers
from . import cage, cage_offset_estimator, cage_soup, constants, high_mesh_cache, image_cleanup, indexed_geometry, mesh_read, mesh_transport, modifier_signature, naming, preferences, project_structure, protocol, properties, storage_cleanup, tagging, workspace


@dataclass(slots=True)
class MaterialBakeSpec:
    """Specification for one material channel bake (pre-backend, addon-side)."""
    low_obj_names: tuple[str, ...]
    high_obj_names: tuple[str, ...]
    channel: str
    output_path: str
    width: int
    height: int
    margin: int
    cage_extrusion: float
    group_name: str
    map_uuid: str
    post_action: str = ""
    final_output_path: str = ""
    source_image_name: str = ""
    flip_green: bool = False
    uv_offset_u: float = 0.0
    uv_offset_v: float = 0.0
    custom_output_name: str = ""
    udim_tile: int = 0
    #: Per-target source lists, parallel to `low_obj_names`. Empty means "use
    #: high_obj_names for every target", which is every spec until two groups sharing
    #: one texture set are merged into one bake -- see `_merge_material_specs_by_output`.
    #: Each low keeps its OWN group's highs: merging the sources instead would let a
    #: neighbouring high win the projection where the two objects touch in 3D.
    source_groups: tuple[tuple[str, ...], ...] = ()
    #: Per-map Relief (0–1) for emit_normal finalize. Default matches RNA 0.5.
    normal_relief: float = 0.5
    #: The row's Normal Format is DirectX: the finished tangent map's green is inverted.
    #: Not ``flip_green``, which describes a detail source for post_action.
    normal_flip_green: bool = False
    #: The group's UV Set: the layout the bake writes into. Empty = each target's
    #: active render layer. Materials keep sampling their own UVs either way.
    uv_layer_name: str = ""
    #: The material this bake writes (group.low_material); other materials' faces are left out.
    only_material: str = ""
    #: The Automatic cage the export fitted for each low that has one
    #: (cycles_projection.FittedCage). A selected-to-active bake traces from it, as the
    #: GPU does, instead of from the hidden Distance offset in ``cage_extrusion``.
    fitted_cages: tuple = ()
    # (low name, distance) pairs once specs of groups with different distances share a file.
    cage_extrusions: tuple = ()


def _map_normal_relief(map_setting) -> float:
    """Clamp a map row's Relief control to 0–1 (RNA default 0.5)."""
    try:
        return min(max(float(getattr(map_setting, "normal_relief", 0.5) or 0.5), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.5


def _material_spec_cage(projection_state, group_config, low_obj_names, high_obj_names, memo) -> tuple[float, tuple]:
    """``(cage_extrusion, fitted_cages)`` for a material spec, traced as the GPU traces.

    A spec with highs under an Automatic cage gets the cage the export fitted for each
    low, with the fit's widest reach as the uniform fallback. Everything else keeps
    the group's Distance (``cage_offset``).
    """
    distance = max(0.0, float(getattr(projection_state, "cage_offset", 0.0) or 0.0))
    if not high_obj_names or group_config is None:
        return distance, ()
    key = (str(getattr(group_config, "name", "") or ""), tuple(low_obj_names))
    fitted = memo.get(key)
    if fitted is None:
        from . import cycles_projection

        lows = [obj for obj in (bpy.data.objects.get(name) for name in low_obj_names) if obj is not None]
        fitted = cycles_projection._group_fitted_cages(group_config, lows)  # noqa: SLF001
        memo[key] = fitted
    if not fitted:
        return distance, ()
    return max(cage.max_offset for cage in fitted), tuple(fitted)


def resolve_job_bake_margin(project, groups) -> int:
    """Use the largest tile's full-image radius for a shared backend job."""
    widths_heights = [(project.resolution_x, project.resolution_y)]
    widths_heights.extend(
        (target.resolution_width or project.resolution_x,
         target.resolution_height or project.resolution_y)
        for group in groups for target in group.outputs
    )
    return max(properties.effective_bake_margin(project, width, height)
               for width, height in widths_heights)


@dataclass(slots=True)
class PreparedJob:
    job: protocol.BakeJob
    job_path: Path
    progress_path: Path
    workspace_path: Path
    output_dir: Path
    effective_map_types: list[str]
    material_bake_specs: list[MaterialBakeSpec] = field(default_factory=list)
    material_detail_entries: list[dict[str, object]] = field(default_factory=list)
    #: Plain-language notes about things the prepared job quietly does NOT include,
    #: surfaced to the user when the bake starts. Currently: material normal/AO
    #: detail that could not be shared across the selected groups' materials.
    warnings: list[str] = field(default_factory=list)
    #: MATERIAL rows whose only blocker was the multi-group MATSLOT sidecar: each
    #: selected group compiles its own native program, so the bake operator runs
    #: them as per-group follow-up bakes on the backend instead of Cycles.
    deferred_multi_group_material_uuids: list[str] = field(default_factory=list)
    #: Normal row uuid -> groups whose material normal detail bakes natively in a
    #: follow-up phase of its own (prepare_bake_job ``native_normal_group_phases``). Those
    #: groups carry the geometry Normal in this job and no Cycles detail layer.
    deferred_native_normal_groups: dict[str, list[str]] = field(default_factory=dict)
    #: Rows left out because they read a different corner colour stream than this job
    #: (two Attribute rows, or Attribute plus Vertex Color): one uuid list per follow-up
    #: stage, in stack order. See color_stream.partition_rows.
    deferred_color_stream_stages: list[list[str]] = field(default_factory=list)
    #: Derivative / Wireframe outputs the addon finishes after the bake (see
    #: derived_outputs; also written to the workspace sidecar).
    derived_outputs: list[dict] = field(default_factory=list)
    #: Each exported group's UV Set override (group name -> layer, "" = none). The job
    #: format carries no UV Set, and the Cycles projection route rasterizes into it.
    group_bake_uv_layers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PreparedLivePreviewJob:
    job: protocol.BakeJob
    job_path: Path
    progress_path: Path
    workspace_path: Path
    output_path: Path
    group_name: str


@dataclass(slots=True)
class PreparedDebugOverlayJob:
    job: protocol.BakeJob
    job_path: Path
    workspace_path: Path
    result_path: Path
    group_name: str
    input_signature: tuple


@dataclass(slots=True)
class _DebugOverlayExportCacheEntry:
    workspace_path: Path
    group_root: Path
    static_signature: tuple
    dynamic_signature: tuple
    low_meshes: list[protocol.ExportedMeshRef]
    high_meshes: list[protocol.ExportedMeshRef]
    cage_meshes: list[protocol.ExportedMeshRef]


_DEBUG_OVERLAY_EXPORT_CACHE: dict[tuple, _DebugOverlayExportCacheEntry] = {}
_LIVE_PREVIEW_EXPORT_CACHE: dict[tuple, _DebugOverlayExportCacheEntry] = {}


def _group_projection_settings_state(group):
    resolver = getattr(properties, "group_projection_settings_state", None)
    if callable(resolver):
        return resolver(group)
    # Lightweight export tests and older serialized stubs may not have the current
    # properties adapter. Reading the group's nested state preserves their defaults.
    return getattr(group, "projection_settings", group)


def _group_paint_projection_settings_state(group):
    return properties.group_paint_projection_settings_state(group)


def _resolve_execution_backend() -> str:
    """Return the internal execution backend string from user preferences."""
    prefs = preferences.get_preferences()
    return preferences.resolve_execution_backend_preference(prefs)


def _iter_valid_object_slots(slot_collection) -> Iterable:
    for slot in slot_collection:
        obj = getattr(slot, "object_ref", None)
        if obj is not None:
            yield slot


def slot_object_has_uv_layers(slot) -> bool:
    """True when the slot's object owns at least one UV layer."""
    mesh = getattr(getattr(slot, "object_ref", None), "data", None)
    layers = getattr(mesh, "uv_layers", None)
    if layers is None:
        return False
    try:
        return len(layers) > 0
    except TypeError:
        return False


def _iter_bakeable_low_slots(slot_collection) -> Iterable:
    """Low slots that can actually receive output.

    A low mesh with no UV layer has no texture space to write into. Ordinary bakes
    never reach here with one: validation raises ``group.low_mesh.missing_uvs`` and
    refuses. The single path that does is "Bake Anyway" on the Missing UVs dialog,
    whose own copy promises "No texture output will be produced for meshes without
    UVs". Before this filter that promise was false -- the mesh was exported like any
    other, picked up a fabricated default unwrap, and overwrote whatever else shared
    its texture set (a UV-less cube stamped a cube-cross of spheres across 27.7% of a
    skull normal map, RC sweep 2026-08-29 finding 18).

    High and cage slots deliberately keep ``_iter_valid_object_slots``: you bake *from*
    a high mesh, so it has no need of UVs.
    """
    for slot in _iter_valid_object_slots(slot_collection):
        if slot_object_has_uv_layers(slot):
            yield slot


def _live_reproject_store_tokens_for_output_root(output_root) -> set[str]:
    """Store tokens of every project (any scene) whose output root is ``output_root``."""
    tokens: set[str] = set()
    try:
        target = os.path.normcase(str(Path(output_root).resolve()))
    except Exception:
        return tokens
    for scene in getattr(bpy.data, "scenes", []) or []:
        settings = getattr(scene, "fyr_baker_settings", None)
        for candidate in getattr(settings, "projects", []) or []:
            try:
                root, _ = resolve_output_root_path(candidate)
                if os.path.normcase(str(root.resolve())) != target:
                    continue
            except Exception:
                continue
            tokens.add(storage_cleanup.reproject_store_token(str(getattr(candidate, "name", "") or "")))
    return tokens


def resolve_output_root_path(project) -> tuple[Path, bool]:
    """Resolve the configured root without creating it; safe for UI redraws."""
    raw_output_root = (project.output_root or "").strip() or "//FyrBaker"
    is_default = raw_output_root == "//FyrBaker"
    if raw_output_root.startswith("//") and not bpy.data.filepath:
        return Path(bpy.app.tempdir or Path.cwd()) / raw_output_root[2:], is_default
    return Path(bpy.path.abspath(raw_output_root)), is_default


def resolve_output_root(project) -> tuple[Path, bool]:
    output_root, is_default = resolve_output_root_path(project)
    return workspace.ensure_directory(output_root), is_default


def resolved_project_output_dir(project) -> Path:
    """Return the exact directory a bake will write, not the possibly-relative UI value."""
    output_root, is_default_root = resolve_output_root_path(project)
    blend_file_name = Path(bpy.data.filepath).stem if bpy.data.filepath else None
    return workspace.build_project_output_dir(
        output_root,
        project.name,
        blend_file_name if is_default_root else None,
    )


def project_output_is_temporary(project) -> bool:
    """Whether the resolved destination lives under Blender's or the OS temporary directory."""
    temp_roots = {
        str(getattr(bpy.app, "tempdir", "") or "").strip(),
        str(tempfile.gettempdir() or "").strip(),
    }
    try:
        output = resolved_project_output_dir(project).resolve()
        for temp_root in temp_roots:
            if not temp_root:
                continue
            temporary = Path(temp_root).resolve()
            if output == temporary or temporary in output.parents:
                return True
        return False
    except (OSError, RuntimeError, ValueError):
        return False


def blend_session_is_recovered_autosave() -> bool:
    """Whether the open .blend is a recovered autosave living in a temporary folder.

    After File > Recover > Auto Save the session's filepath points at the
    autosave copy under the OS (or Blender) temp directory, so a relative
    output root like "//FyrBaker" silently resolves into a folder that the
    scratch cleanup sweeps. Bakes look successful while every output lands
    somewhere the artist never looks and previews keep showing older files.
    """
    blend_path = str(getattr(bpy.data, "filepath", "") or "").strip()
    if not blend_path:
        return False
    temp_roots = {
        str(getattr(bpy.app, "tempdir", "") or "").strip(),
        str(tempfile.gettempdir() or "").strip(),
    }
    try:
        blend_dir = Path(blend_path).expanduser().resolve(strict=False).parent
    except (OSError, RuntimeError, ValueError):
        return False
    for temp_root in temp_roots:
        if not temp_root:
            continue
        try:
            temporary = Path(temp_root).resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            continue
        if blend_dir == temporary or temporary in blend_dir.parents:
            return True
    return False


#: One-line reasons shown when a bake is refused because it would write into a
#: temporary folder. Kept here so the bake operators and the sidebar warning
#: row stay word-for-word in sync.
RECOVERED_AUTOSAVE_BAKE_ERROR = (
    "This file is a recovered autosave. Save it with Save As, or set an "
    "absolute output Folder, so baked maps are not written to the temporary folder."
)
RECOVERED_AUTOSAVE_STATUS = "Recovered autosave: save the file before baking"


def refuse_temporary_output_bake(project) -> str:
    """Return the refusal message when baking must not proceed, else an empty string.

    Only the recovered-autosave case refuses: a deliberately unsaved scratch
    file keeps the existing temporary-output warning row and may still bake.
    """
    try:
        if blend_session_is_recovered_autosave() and project_output_is_temporary(project):
            return RECOVERED_AUTOSAVE_BAKE_ERROR
    except Exception:
        return ""
    return ""


_PREVIEW_MATERIAL_NAME_PREFIX = constants.PREVIEW_MATERIAL_NAME_PREFIX


def _resolve_object_material_name(obj) -> str:
    active_material = getattr(obj, "active_material", None)
    if active_material is not None:
        return getattr(active_material, "name", "") or ""
    material_slots = getattr(obj, "material_slots", None)
    if material_slots:
        for slot in material_slots:
            material = getattr(slot, "material", None)
            if material is not None:
                return getattr(material, "name", "") or ""
    data_materials = getattr(getattr(obj, "data", None), "materials", None)
    if data_materials:
        for material in data_materials:
            if material is not None:
                return getattr(material, "name", "") or ""
    return ""


def _resolve_stable_material_name(obj) -> str:
    """Material name for bake cache keys — strips transient preview materials."""
    name = _resolve_object_material_name(obj)
    if name.startswith(_PREVIEW_MATERIAL_NAME_PREFIX):
        return ""
    return name


def _clamp_color_component(value, fallback: float = 1.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = fallback
    return max(0.0, min(1.0, numeric))


def _resolve_rgb_triplet(value, fallback=(1.0, 1.0, 1.0)) -> list[float]:
    if value is None:
        return [float(component) for component in fallback]
    try:
        components = list(value)
    except Exception:
        components = []
    if len(components) < 3:
        components.extend(list(fallback)[len(components):3])
    return [
        _clamp_color_component(components[0], fallback[0]),
        _clamp_color_component(components[1], fallback[1]),
        _clamp_color_component(components[2], fallback[2]),
    ]


def _resolve_object_material_color(obj) -> list[float]:
    active_material = getattr(obj, "active_material", None)
    if active_material is not None:
        return _resolve_rgb_triplet(getattr(active_material, "diffuse_color", None))
    material_slots = getattr(obj, "material_slots", None)
    if material_slots:
        for slot in material_slots:
            material = getattr(slot, "material", None)
            if material is not None:
                return _resolve_rgb_triplet(getattr(material, "diffuse_color", None))
    data_materials = getattr(getattr(obj, "data", None), "materials", None)
    if data_materials:
        for material in data_materials:
            if material is not None:
                return _resolve_rgb_triplet(getattr(material, "diffuse_color", None))
    return _resolve_rgb_triplet(getattr(obj, "color", None))


def _resolve_object_collection_name(obj) -> str:
    named = [
        collection
        for collection in collection_index.users_collection(obj)
        if (getattr(collection, "name", "") or "").strip()
    ]
    if not named:
        return ""
    # Prefer a collection carrying MasterBaker role/group metadata (e.g. "Jaw_High") over
    # an untagged generic one (Blender's default "Collection"). Objects usually belong to
    # both; returning the shared generic collection gives every mesh the same name, which
    # flattens a collection-source ID map to a single colour and pollutes the export cache
    # key. Mirrors metadata_sync._primary_collection.
    for collection in named:
        if (
            tagging.is_tagged(collection)
            or (tagging.get_metadata_group_name(collection) or "").strip()
            or (tagging.get_metadata_collection_name(collection) or "").strip()
        ):
            return str(getattr(collection, "name", "") or "").strip()
    return str(getattr(named[0], "name", "") or "").strip()


def _resolve_object_file_id_key(obj) -> str:
    data = getattr(obj, "data", None)
    if data is not None:
        data_name = str(getattr(data, "name", "") or "").strip()
        library = getattr(data, "library", None)
        library_path = str(getattr(library, "filepath", "") or "").strip()
        if library_path:
            try:
                library_path = str(bpy.path.abspath(library_path))
            except Exception:
                pass
            return f"LIB:{library_path}::{data_name}"
        if data_name:
            return f"MESH:{data_name}"
    object_library = getattr(obj, "library", None)
    object_library_path = str(getattr(object_library, "filepath", "") or "").strip()
    if object_library_path:
        try:
            object_library_path = str(bpy.path.abspath(object_library_path))
        except Exception:
            pass
        object_name = str(getattr(obj, "name", "") or "").strip()
        return f"OBJLIB:{object_library_path}::{object_name}"
    object_name = str(getattr(obj, "name", "") or "").strip()
    if object_name:
        return f"OBJECT:{object_name}"
    return ""


def _transformed_normal(matrix, vector):
    normal = matrix.to_3x3() @ vector
    if normal.length_squared != 0.0:
        normal.normalize()
    return normal


def _flatten_matrix(matrix) -> list[float]:
    return [float(matrix[row][col]) for row in range(4) for col in range(4)]


_IDENTITY_MATRIX_16 = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]


def _matrix_world_values(obj) -> list[float]:
    """Return the 4×4 row-major matrix_world as 16 floats, or identity if unavailable."""
    matrix_world = getattr(obj, "matrix_world", None)
    if matrix_world is None:
        return list(_IDENTITY_MATRIX_16)
    return _flatten_matrix(matrix_world)


def _world_to_object_matrix_values(obj) -> list[float]:
    matrix_world = getattr(obj, "matrix_world", None)
    if matrix_world is None:
        return list(_IDENTITY_MATRIX_16)
    return _flatten_matrix(matrix_world.inverted_safe())


def _object_bounds_signature(obj) -> tuple:
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


def _id_update_signature(id_data) -> tuple[bool, bool]:
    if id_data is None:
        return (False, False)
    return (
        bool(getattr(id_data, "is_updated", False)),
        bool(getattr(id_data, "is_updated_data", False)),
    )


def _object_signature(obj) -> tuple:
    data = getattr(obj, "data", None)
    matrix_world = getattr(obj, "matrix_world", None)
    matrix_values = tuple(
        round(float(value), 6)
        for row in matrix_world
        for value in row
    ) if matrix_world is not None else ()
    topology_signature = ()
    if data is not None:
        topology_signature = (
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "edges"),
            mesh_read.element_count(data, "polygons"),
            bool(getattr(data, "is_editmode", False)),
        )
    return (
        getattr(obj, "name", ""),
        getattr(data, "name", "") if data is not None else "",
        matrix_values,
        topology_signature,
        _object_bounds_signature(obj),
        # The payload is built from the EVALUATED mesh, and the session payload cache
        # is never invalidated by the depsgraph. Without a modifier term a Weighted
        # Normal weight, a UVWarp offset or a Triangulate method change (bounds and
        # base counts unchanged) served the previous payload.
        modifier_signature.modifier_stack_signature(obj),
        # Deformation the stack's own properties do not carry: an Armature modifier
        # contributes only the rig's pointer, unchanged when the rig is POSED, and
        # shape-key values are not in it at all. Bounds move with a big pose, but a
        # re-pose inside the same bounds (or a shape-key slider) matched everything
        # above, so a posed character re-baked from the REST-pose payload: rays cast
        # from the old geometry, misprojected or black maps, and no cache miss.
        modifier_signature.deform_signature(obj),
        # NOTE: intentionally NOT including obj.as_pointer()/data.as_pointer() here.
        # They are runtime memory addresses that change every time the .blend is
        # reopened (and on depsgraph re-evaluation), NOT content identity. The
        # prewarm replays the previous session's persisted job while the bake
        # fresh-exports the current session, so the pointers never matched ->
        # prepared-group cache miss -> the whole prewarm thrown away on the first
        # bake of every session. Object+mesh datablock NAMES are the stable unique
        # identity (Blender enforces unique names per type); real geometry changes
        # are caught by topology/bounds/matrix here and the backend's xxh3 token.
        # NOTE: intentionally NOT including _id_update_signature here either —
        # is_updated/is_updated_data are transient depsgraph flags (the preview
        # material assigned at bake time flips them), not content identity.
    ) + _floater_signature_term(obj) + low_material_subset.signature_term(obj)


def _floater_signature_term(obj) -> tuple:
    # Floater faces (marks plus the part an export writes). Empty without marked faces, so
    # every existing signature keeps its exact value.
    token = floater_faces.cache_token(obj)
    return (token,) if token else ()


def _object_local_signature(obj) -> tuple:
    """Like _object_signature but excludes matrix_world — stable across pure transforms.

    Used as the cache key for high-mesh exports so that moving a high-poly object
    in the viewport does not invalidate the per-mesh BLAS or its persistent cache.
    """
    data = getattr(obj, "data", None)
    topology_signature = ()
    if data is not None:
        topology_signature = (
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "edges"),
            mesh_read.element_count(data, "polygons"),
            bool(getattr(data, "is_editmode", False)),
        )
    return (
        getattr(obj, "name", ""),
        obj.as_pointer() if hasattr(obj, "as_pointer") else 0,
        data.as_pointer() if data is not None and hasattr(data, "as_pointer") else 0,
        topology_signature,
        _id_update_signature(obj),
        _id_update_signature(data),
        # A posed rig or a moved shape-key slider changes the evaluated high mesh this
        # key stands for while leaving every term above alone. See _object_signature.
        modifier_signature.deform_signature(obj),
    )


def _high_mesh_local_export_cache_key(obj) -> str:
    """Cache key for high-mesh exports — does NOT include matrix_world.

    The transform is sent separately as ExportedMeshRef.matrix_world so the
    BLAS (keyed by this value) can be reused across transform-only changes.
    """
    return _signature_cache_key(
        "HIGH_OBJECT_LOCAL_EXPORT",
        _object_local_signature(obj),
        _resolve_object_material_name(obj),
        _resolve_object_collection_name(obj),
        *_floater_signature_term(obj),
    )


#: RNA identifiers that change without the prepared work changing: per-bake
#: bookkeeping (``last_*``), UI cursors (``active_*``), reproject status and the
#: panel-expansion booleans. Including them would make every bake, selection or
#: disclosure-triangle click look like a scene change and re-fire the prewarm.
_PREPARE_SIGNATURE_VOLATILE_PREFIXES = ("last_", "active_", "reproject_")
_PREPARE_SIGNATURE_VOLATILE_NAMES = frozenset(
    {
        "rna_type",
        "latest_outputs",
        "cage_menu_expanded",
        "cage_overlay_hidden",
        "show_cage_coverage",
        "hierarchy_focus",
        "isolate_in_viewport",
    }
)


def _prepare_signature_value(value):
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        return value
    try:
        return tuple(_prepare_signature_value(item) for item in value)
    except TypeError:
        return repr(value)


def _rna_block_signature(block, *, depth: int = 2) -> tuple:
    """Scalar RNA fingerprint of a PropertyGroup, minus volatile bookkeeping.

    Swept from ``bl_rna`` rather than a hand-written field list so a settings
    property added later is covered automatically — a missed field would let a
    real settings change reuse a stale prewarm and make the next bake pay the
    prepare inside RUN.
    """
    rna = getattr(block, "bl_rna", None)
    if rna is None:
        return ()
    signature = []
    for prop in getattr(rna, "properties", ()) or ():
        identifier = str(getattr(prop, "identifier", "") or "")
        if not identifier:
            continue
        if identifier in _PREPARE_SIGNATURE_VOLATILE_NAMES:
            continue
        if identifier.startswith(_PREPARE_SIGNATURE_VOLATILE_PREFIXES):
            continue
        prop_type = str(getattr(prop, "type", "") or "")
        # Collections are walked by the caller (object slots, map rows, groups):
        # they need the per-item content signatures, not an RNA sweep.
        if prop_type == "COLLECTION":
            continue
        try:
            value = getattr(block, identifier)
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        if prop_type == "POINTER":
            id_type = getattr(bpy.types, "ID", None)
            if value is None:
                signature.append((identifier, ""))
            elif id_type is not None and isinstance(value, id_type):
                # Datablock reference: name is the stable identity (see the note
                # in _object_signature about as_pointer() churn across reloads).
                signature.append((identifier, str(getattr(value, "name", "") or "")))
            elif depth > 0 and hasattr(value, "bl_rna"):
                # Nested settings group (projection settings, group metadata).
                signature.append((identifier, _rna_block_signature(value, depth=depth - 1)))
            else:
                signature.append((identifier, str(getattr(value, "name", "") or "")))
            continue
        signature.append((identifier, _prepare_signature_value(value)))
    return tuple(signature)


def speculative_prepare_signature(project) -> str:
    """Content identity of everything a speculative PREPARE would hand the worker.

    Two calls returning the same key mean a fresh export would produce the same
    geometry, cages and bake settings the resident worker is already primed for,
    so re-running the prepare is pure cost: a multi-second main-thread export
    plus a "Warming up scene cache" the artist reads as the addon being stuck.

    Built from the exporter's own change predicates (`_object_signature`,
    `map_bake_settings_signature`) so it agrees with what actually invalidates a
    cached export. Returns "" when the fingerprint cannot be taken, which callers
    must treat as "unknown" and prepare anyway.
    """
    if project is None:
        return ""
    try:
        parts: list = ["SPECULATIVE_PREPARE_V1", _rna_block_signature(project)]
        for map_setting in getattr(project, "maps", []) or ():
            if bool(getattr(map_setting, "is_add_phantom", False)):
                continue
            parts.append(
                (
                    str(getattr(map_setting, "uuid", "") or ""),
                    # map_bake_settings_signature deliberately drops `enabled`
                    # (two rows can want the same pixels); for the prewarm it is
                    # the difference between a map being baked at all.
                    bool(getattr(map_setting, "enabled", False)),
                    str(getattr(map_setting, "map_type", "") or ""),
                    properties.map_bake_settings_signature(map_setting),
                )
            )
        for texture_set in getattr(project, "texture_sets", []) or ():
            parts.append(_rna_block_signature(texture_set))
        for group in getattr(project, "groups", []) or ():
            parts.append(
                (
                    str(getattr(group, "name", "") or ""),
                    _rna_block_signature(group),
                    low_material_subset.group_material_name(group),
                    _group_low_slot_signature(group),
                    _slot_collection_signature(properties.effective_high_mesh_slots(group)),
                )
            )
        return _signature_cache_key(*parts)
    except Exception:
        return ""


def _group_low_slot_signature(group) -> tuple:
    with low_material_subset.group_scope(group):
        return _slot_collection_signature(getattr(group, "low_meshes", []))


def _slot_collection_signature(slot_collection) -> tuple:
    return tuple(
        _object_signature(slot.object_ref)
        for slot in _iter_valid_object_slots(slot_collection)
    )


def _resolve_uv_layer_data(mesh, uv_layer_name: str | None, *, object_name: str = ""):
    uv_layers = getattr(mesh, "uv_layers", None)
    if uv_layers is None:
        return None
    if uv_layer_name:
        target_layer = uv_layers.get(uv_layer_name) if hasattr(uv_layers, "get") else None
        if target_layer is not None:
            return target_layer.data
        owner = object_name or "Mesh"
        raise ValueError(f"{owner} is missing the requested UV set '{uv_layer_name}'")
    active_layer = getattr(uv_layers, "active", None)
    if active_layer is not None:
        return active_layer.data
    return None


def _clamp_uv01(value: float) -> float:
    if value != value:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _uv_component(uv, axis_name: str, index: int) -> float:
    value = getattr(uv, axis_name, None)
    if value is not None:
        return float(value)
    try:
        return float(uv[index])
    except Exception:
        return 0.0


def _expanded_dirty_uv_bounds_for_tile(
    project,
    bounds: tuple[float, float, float, float],
    udim_tile: int,
    tile_width: int,
    tile_height: int,
) -> tuple[float, float, float, float] | None:
    """Localise a global-UV island rect to one tile, expanded by that tile's margin.

    Returns ``None`` when the island does not reach the tile, so callers emit nothing rather
    than a degenerate rect. Padding uses the TILE's resolution, not the project's: a 16px
    margin is a different UV distance on a 2048 tile than on a 4096 one, and the rect has to
    cover the pixels the bake will actually touch.
    """
    from . import udim as _udim

    tile_u, tile_v = _udim.tile_origin(udim_tile) if udim_tile else (0, 0)
    min_u, min_v, max_u, max_v = bounds
    # Global -> tile-local.
    min_u -= float(tile_u)
    max_u -= float(tile_u)
    min_v -= float(tile_v)
    max_v -= float(tile_v)

    # Reject islands entirely outside this tile BEFORE padding, so a neighbouring tile's
    # island does not get dragged in by the margin alone.
    if max_u <= 0.0 or min_u >= 1.0 or max_v <= 0.0 or min_v >= 1.0:
        return None

    width = max(1, int(tile_width))
    height = max(1, int(tile_height))
    margin = properties.effective_bake_margin(project, width, height)
    pad_u = (float(margin) + 0.5) / float(width)
    pad_v = (float(margin) + 0.5) / float(height)
    return (
        _clamp_uv01(min_u - pad_u),
        _clamp_uv01(min_v - pad_v),
        _clamp_uv01(max_u + pad_u),
        _clamp_uv01(max_v + pad_v),
    )


def _expanded_dirty_uv_bounds(project, bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    width = max(1, int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    height = max(1, int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    margin = properties.effective_bake_margin(project, width, height)
    pad_u = (float(margin) + 0.5) / float(width)
    pad_v = (float(margin) + 0.5) / float(height)
    min_u, min_v, max_u, max_v = bounds
    return (
        _clamp_uv01(min_u - pad_u),
        _clamp_uv01(min_v - pad_v),
        _clamp_uv01(max_u + pad_u),
        _clamp_uv01(max_v + pad_v),
    )


def _uv_island_key(u_value: float, v_value: float) -> tuple[int, int]:
    return (int(round(float(u_value) * 1_000_000.0)), int(round(float(v_value) * 1_000_000.0)))


def _bounds_from_triangle_uv_islands(triangle_uvs: list[list[tuple[float, float]]]) -> list[tuple[float, float, float, float]]:
    if not triangle_uvs:
        return []

    parent = list(range(len(triangle_uvs)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    uv_owner: dict[tuple[int, int], int] = {}
    for triangle_index, corners in enumerate(triangle_uvs):
        for u_value, v_value in corners:
            key = _uv_island_key(u_value, v_value)
            owner = uv_owner.get(key)
            if owner is None:
                uv_owner[key] = triangle_index
            else:
                union(triangle_index, owner)

    bounds_by_root: dict[int, tuple[float, float, float, float]] = {}
    for triangle_index, corners in enumerate(triangle_uvs):
        root = find(triangle_index)
        # GLOBAL UV, deliberately unclamped: _build_dirty_uv_rects_for_group
        # localises per output tile and clamps there. Clamping here collapsed every
        # island above tile 1001 onto u=1.0, so an incremental rebake of a mesh
        # whose UVs live in 1002 emitted no rect for 1002 and that tile kept its
        # stale pixels while the bake reported success.
        min_u = min(float(u_value) for u_value, _v_value in corners)
        min_v = min(float(v_value) for _u_value, v_value in corners)
        max_u = max(float(u_value) for u_value, _v_value in corners)
        max_v = max(float(v_value) for _u_value, v_value in corners)
        current = bounds_by_root.get(root)
        if current is None:
            bounds_by_root[root] = (min_u, min_v, max_u, max_v)
        else:
            bounds_by_root[root] = (
                min(current[0], min_u),
                min(current[1], min_v),
                max(current[2], max_u),
                max(current[3], max_v),
            )
    return list(bounds_by_root.values())


def _compute_object_uv_island_bounds(obj, depsgraph, uv_layer_name: str | None) -> list[tuple[float, float, float, float]]:
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=True)
    if mesh is None:
        return []

    try:
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()
        loop_triangles = getattr(mesh, "loop_triangles", None)
        if loop_triangles is None or len(loop_triangles) <= 0:
            return []
        uv_layer = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=getattr(obj, "name", ""))
        if uv_layer is None:
            return [(0.0, 0.0, 1.0, 1.0)]

        if hasattr(loop_triangles, "foreach_get") and hasattr(uv_layer, "foreach_get"):
            import numpy as np

            triangle_loop_indices = rna_buffers.empty_u32_for_rna(len(loop_triangles) * 3)
            loop_triangles.foreach_get("loops", triangle_loop_indices)
            triangle_loop_indices = rna_buffers.as_i32(triangle_loop_indices)
            uv_flat = np.empty(len(uv_layer) * 2, dtype=np.float32)
            uv_layer.foreach_get("uv", uv_flat)
            corner_uvs = uv_flat.reshape(len(uv_layer), 2)[triangle_loop_indices]
            triangle_uvs: list[list[tuple[float, float]]] = []
            for triangle_index in range(len(loop_triangles)):
                corners = corner_uvs[triangle_index * 3 : triangle_index * 3 + 3]
                if not np.isfinite(corners).all():
                    continue
                triangle_uvs.append([(float(u_value), float(v_value)) for u_value, v_value in corners])
            return _bounds_from_triangle_uv_islands(triangle_uvs)

        triangle_uvs: list[list[tuple[float, float]]] = []
        for tri in loop_triangles:
            corners: list[tuple[float, float]] = []
            for loop_index in getattr(tri, "loops", ()):
                uv = getattr(uv_layer[int(loop_index)], "uv", None)
                if uv is None:
                    continue
                corners.append((_uv_component(uv, "x", 0), _uv_component(uv, "y", 1)))
            if len(corners) == 3:
                triangle_uvs.append(corners)
        return _bounds_from_triangle_uv_islands(triangle_uvs)
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _build_dirty_uv_rects_for_group(
    project,
    group,
    depsgraph,
    outputs: list[protocol.OutputTarget],
    dirty_object_names: set[str] | None,
) -> list[protocol.DirtyUvRect]:
    if not outputs:
        return []

    low_slots = list(_iter_bakeable_low_slots(getattr(group, "low_meshes", [])))
    if not low_slots:
        return []

    clean_dirty_names = {
        str(name or "").strip()
        for name in (dirty_object_names or set())
        if str(name or "").strip()
    }
    if not clean_dirty_names:
        return []
    low_names = {
        str(getattr(getattr(slot, "object_ref", None), "name", "") or "").strip()
        for slot in low_slots
    }
    low_dirty_slots = [
        slot
        for slot in low_slots
        if str(getattr(getattr(slot, "object_ref", None), "name", "") or "").strip() in clean_dirty_names
    ]
    if clean_dirty_names - low_names:
        # A high (or cage) edit changes the projection over EVERY low of the group, but
        # the dirty set records it by object name like any other edit. Scissoring to the
        # islands of whichever low happened to be edited in the same window left the rest
        # of the group holding pre-sculpt texels on a bake that reported success.
        #
        # No rects at all, which the backend reads as "rebake this group whole". Emitting
        # rects for every low of the group instead looked tighter but broke
        # incremental-vs-full parity on a shared texture set (measured: AO 12, ID 158,
        # NORMAL 7 max byte difference on the multi-group fixture), because those rects
        # reach texels another member of the set owns.
        return []
    if low_dirty_slots:
        candidate_slots = low_dirty_slots
    else:
        return []
    projection_state = _group_projection_settings_state(group)
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None

    island_bounds: list[tuple[float, float, float, float]] = []
    for slot in candidate_slots:
        obj = getattr(slot, "object_ref", None)
        if obj is None:
            continue
        island_bounds.extend(_compute_object_uv_island_bounds(obj, depsgraph, uv_layer_name))

    if not island_bounds:
        return []

    project_width = max(1, int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    project_height = max(1, int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))

    rects: list[protocol.DirtyUvRect] = []
    for bounds in island_bounds:
        # island_bounds are GLOBAL UV. Each output knows its tile, so a rect is emitted per
        # (island, output) only where the island actually reaches that output's tile, in that
        # tile's local coordinates. An island straddling a border yields one clipped rect per
        # tile it touches; an island in a different tile yields nothing here.
        for output in outputs:
            udim_tile = int(getattr(output, "udim_tile", 0) or 0)
            if udim_tile:
                localised = _expanded_dirty_uv_bounds_for_tile(
                    project,
                    bounds,
                    udim_tile,
                    int(getattr(output, "resolution_width", 0) or 0) or project_width,
                    int(getattr(output, "resolution_height", 0) or 0) or project_height,
                )
                if localised is None:
                    continue
                min_u, min_v, max_u, max_v = localised
            else:
                min_u, min_v, max_u, max_v = _expanded_dirty_uv_bounds(project, bounds)
            rects.append(
                protocol.DirtyUvRect(
                    map_type=output.map_type,
                    map_uuid=output.map_uuid,
                    min_u=min_u,
                    min_v=min_v,
                    max_u=max_u,
                    max_v=max_v,
                    udim_tile=udim_tile,
                )
            )
    return rects


def _resolve_active_color_attribute(mesh):
    color_attributes = getattr(mesh, "color_attributes", None)
    if color_attributes is None:
        return None
    active = getattr(color_attributes, "active_color", None)
    if active is None:
        active = getattr(color_attributes, "active", None)
    if active is None:
        return None
    # The active slot can reference a NON-color attribute (seen live: a
    # Short2Attribute), whose elements have no .color. That silently broke the
    # numpy fast export for EVERY mesh of the scene (the fast path raised on
    # foreach_get("color") and fell back to the ~10x slower per-corner path),
    # so only accept real color data types here.
    data_type = str(getattr(active, "data_type", "") or "").upper()
    if data_type not in {"FLOAT_COLOR", "BYTE_COLOR"}:
        return None
    data = getattr(active, "data", None)
    if data is None:
        return None
    domain = str(getattr(active, "domain", "CORNER") or "CORNER").upper()
    return (domain, data)


def _resolve_corner_color_attribute(mesh, color_source=None):
    """(domain, data) filling the corner colour stream, or None for neutral white.

    The active colour attribute (Vertex Color rows) comes back exactly as before; an
    Attribute row's source comes back as a ready (n, 3) float32 array in 0..1.
    """
    if color_source is None or color_source.is_active_color:
        return _resolve_active_color_attribute(mesh)
    return color_stream.attribute_stream_rows(mesh, color_source)


def _color_attribute_value(color_attribute, loop_index: int, vertex_index: int) -> tuple[float, float, float]:
    if color_attribute is None:
        return (1.0, 1.0, 1.0)
    domain, data = color_attribute
    element_index = int(vertex_index) if domain == "POINT" else int(loop_index)
    if element_index < 0 or element_index >= len(data):
        return (1.0, 1.0, 1.0)
    if not hasattr(data[element_index], "color"):
        # Attribute rows: data is already an (n, 3) array of stream values.
        value = data[element_index]
        return (float(value[0]), float(value[1]), float(value[2]))
    value = getattr(data[element_index], "color", None)
    if value is None:
        return (1.0, 1.0, 1.0)
    return (
        max(0.0, min(1.0, float(value[0]))),
        max(0.0, min(1.0, float(value[1]))),
        max(0.0, min(1.0, float(value[2]))),
    )
def _clear_export_cache(cache: dict[tuple, _DebugOverlayExportCacheEntry]) -> None:
    workspace_paths = {
        str(Path(entry.workspace_path).resolve(strict=False))
        for entry in cache.values()
        if getattr(entry, "workspace_path", None) is not None
    }
    for workspace_path in workspace_paths:
        indexed_geometry.wait_for_workspace_canonical_writes(workspace_path)
        high_mesh_cache.finalize_pending_canonical_aliases()
        mesh_transport.release_workspace_shared_memory(workspace_path)
    storage_cleanup.delete_workspaces(workspace_paths)
    cache.clear()


def invalidate_debug_overlay_export_cache() -> None:
    _clear_export_cache(_DEBUG_OVERLAY_EXPORT_CACHE)


def invalidate_live_preview_export_cache() -> None:
    _clear_export_cache(_LIVE_PREVIEW_EXPORT_CACHE)


def _iter_view3d_regions(context) -> Iterable[tuple[object, object, object]]:
    seen: set[tuple[int, int, int]] = set()
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    if (
        getattr(area, "type", "") == "VIEW_3D"
        and getattr(region, "type", "") == "WINDOW"
        and region_data is not None
    ):
        key = (id(area), id(region), id(region_data))
        seen.add(key)
        yield area, region, region_data

    window = getattr(context, "window", None)
    screen = getattr(window, "screen", None)
    if screen is None:
        return
    for candidate_area in getattr(screen, "areas", []):
        if getattr(candidate_area, "type", "") != "VIEW_3D":
            continue
        candidate_space = getattr(getattr(candidate_area, "spaces", None), "active", None)
        candidate_region_data = getattr(candidate_space, "region_3d", None)
        candidate_region = next((item for item in getattr(candidate_area, "regions", []) if getattr(item, "type", "") == "WINDOW"), None)
        if candidate_region is None or candidate_region_data is None:
            continue
        key = (id(candidate_area), id(candidate_region), id(candidate_region_data))
        if key in seen:
            continue
        seen.add(key)
        yield candidate_area, candidate_region, candidate_region_data


def resolve_debug_view(context) -> protocol.DebugViewConfig | None:
    for _area, region, region_data in _iter_view3d_regions(context):
        debug_view = build_debug_view(region, region_data)
        if debug_view is not None:
            return debug_view
    return None


def build_debug_view(region, region_data) -> protocol.DebugViewConfig | None:
    width = int(max(1, getattr(region, "width", 0)))
    height = int(max(1, getattr(region, "height", 0)))
    perspective_matrix = getattr(region_data, "perspective_matrix", None)
    if perspective_matrix is None:
        return None
    matrix_values = _flatten_matrix(perspective_matrix)
    digest = hashlib.sha1()
    digest.update(f"{width}x{height}|".encode("utf-8"))
    digest.update(",".join(f"{value:.6f}" for value in matrix_values).encode("utf-8"))
    return protocol.DebugViewConfig(
        viewport_width=width,
        viewport_height=height,
        view_projection=matrix_values,
        view_signature=digest.hexdigest(),
    )


def _signature_cache_key(*parts) -> str:
    # blake2b with digest_size=8 (64-bit) is ~3x faster than SHA-1 for short
    # inputs and is more than sufficient collision-resistance for a local cache key.
    digest = hashlib.blake2b(digest_size=8)
    digest.update(repr(tuple(parts)).encode("utf-8"))
    return digest.hexdigest()


# Mesh reads straight from the attribute layers the RNA properties are views of. Blender
# 4.0+ stores positions as the "position" POINT attribute, Shade Flat as the "sharp_face"
# FACE bool and Mark Sharp as the "sharp_edge" EDGE bool (absent = all smooth / none
# sharp), and MeshVertex.co / MeshPolygon.use_smooth / MeshEdge.use_edge_sharp read
# exactly those. Going through the per-element RNA properties instead cost (BakeTester3
# Jaw high, 2.8M verts / 5.6M edges) 174 vs 17 ms for positions and 1272 vs 3 ms for
# sharp edges, on every bake launch's export cache key. Same values; anything that does
# not look like the expected layer falls back to the RNA read.
def _attribute_layer(mesh, name: str, data_type: str, domain: str, length: int):
    """(found, layer): found=False when no attribute is named ``name``; layer=None when
    one is but it is not the expected type/domain/length (caller must take the RNA path)."""
    attributes = getattr(mesh, "attributes", None)
    getter = getattr(attributes, "get", None) if attributes is not None else None
    if getter is None:
        return True, None
    try:
        layer = getter(name)
    except Exception:
        return True, None
    if layer is None:
        return False, None
    try:
        if (
            str(getattr(layer, "data_type", "")) != data_type
            or str(getattr(layer, "domain", "")) != domain
            or len(layer.data) != length
            or not hasattr(layer.data, "foreach_get")
        ):
            return True, None
    except Exception:
        return True, None
    return True, layer


def read_vertex_positions(mesh, vertices, out) -> None:
    """Fill float32 ``out`` (len 3*N) with the vertex coordinates of ``vertices``."""
    found, layer = _attribute_layer(mesh, "position", "FLOAT_VECTOR", "POINT", len(vertices))
    if layer is not None:
        try:
            layer.data.foreach_get("vector", out)
            return
        except Exception:
            pass
    vertices.foreach_get("co", out)


def _read_face_smooth(mesh, polygons):
    import numpy as np

    count = len(polygons)
    found, layer = _attribute_layer(mesh, "sharp_face", "BOOLEAN", "FACE", count)
    if layer is not None:
        try:
            sharp = np.empty(count, dtype=bool)
            layer.data.foreach_get("value", sharp)
            return ~sharp
        except Exception:
            pass
    elif not found and _blender_stores_shading_as_attributes(mesh):
        return np.ones(count, dtype=bool)
    smooth = np.empty(count, dtype=bool)
    polygons.foreach_get("use_smooth", smooth)
    return smooth


def _read_edge_sharp(mesh, edges):
    import numpy as np

    count = len(edges)
    found, layer = _attribute_layer(mesh, "sharp_edge", "BOOLEAN", "EDGE", count)
    if layer is not None:
        try:
            sharp = np.empty(count, dtype=bool)
            layer.data.foreach_get("value", sharp)
            return sharp
        except Exception:
            pass
    elif not found and _blender_stores_shading_as_attributes(mesh):
        return np.zeros(count, dtype=bool)
    sharp = np.empty(count, dtype=bool)
    edges.foreach_get("use_edge_sharp", sharp)
    return sharp


def _blender_stores_shading_as_attributes(mesh) -> bool:
    """True on a real Blender 4.0+ mesh, where an absent sharp_face / sharp_edge layer
    means all-smooth / none-sharp. Anything else (test fakes) takes the RNA read."""
    if getattr(mesh, "attributes", None) is None or not hasattr(mesh, "as_pointer"):
        return False
    try:
        return tuple(bpy.app.version) >= (4, 0, 0)
    except Exception:
        return False


def _mesh_content_token(obj, uv_layer_name: str | None) -> str:
    """64-bit hash of raw-mesh content that feeds the exported payload but is
    invisible to _object_signature: vertex positions and the bake UV layer.

    _object_signature only sees topology COUNTS, bounds and the transform, so a
    UV-only edit (Optimize UV Seams, manual UV editing) or a vertex edit that
    stays inside the bounds produced an unchanged export cache key. The payload
    cache then reused the previously written .mbmesh, the backend's revision
    token never saw the new bytes, and the bake served stale outputs.
    """
    data = getattr(obj, "data", None)
    vertices = getattr(data, "vertices", None) if data is not None else None
    if vertices is None:
        return ""
    import numpy as np

    digest = hashlib.blake2b(digest_size=8)
    vertex_count = len(vertices)
    if vertex_count:
        if hasattr(vertices, "foreach_get"):
            buffer = np.empty(vertex_count * 3, dtype=np.float32)
            read_vertex_positions(data, vertices, buffer)
            # The array's own buffer: tobytes() copied every array once more just to hash it.
            digest.update(buffer)
        else:  # unit-test fakes use plain lists, sometimes of placeholder items
            coords = [tuple(v.co) for v in vertices if hasattr(v, "co")]
            if coords:
                digest.update(np.asarray(coords, dtype=np.float32).tobytes())
    try:
        uv_data = _resolve_uv_layer_data(data, uv_layer_name, object_name=getattr(obj, "name", ""))
    except ValueError:
        uv_data = None
    if uv_data is not None and len(uv_data):
        if hasattr(uv_data, "foreach_get"):
            buffer = np.empty(len(uv_data) * 2, dtype=np.float32)
            uv_data.foreach_get("uv", buffer)
        else:
            buffer = np.ascontiguousarray([tuple(item.uv) for item in uv_data], dtype=np.float32)
        digest.update(buffer)
    # Shading feeds the exported corner normals (and through them every map): Shade
    # Flat/Smooth, Mark Sharp and custom split normals left this key unchanged, so the
    # bake re-served the previous normals.
    polygons = getattr(data, "polygons", None)
    if polygons is not None and len(polygons) and hasattr(polygons, "foreach_get"):
        smooth = _read_face_smooth(data, polygons)
        digest.update(b"smooth")
        digest.update(smooth)
    edges = getattr(data, "edges", None)
    if edges is not None and len(edges) and hasattr(edges, "foreach_get"):
        sharp = _read_edge_sharp(data, edges)
        digest.update(b"sharp")
        digest.update(sharp)
    if bool(getattr(data, "has_custom_normals", False)):
        corner_normals = getattr(data, "corner_normals", None)
        if corner_normals is not None and len(corner_normals) and hasattr(corner_normals, "foreach_get"):
            normals = np.empty(len(corner_normals) * 3, dtype=np.float32)
            corner_normals.foreach_get("vector", normals)
            digest.update(b"custom")
            digest.update(normals)
    return digest.hexdigest()


def _object_export_cache_key(
    obj,
    *,
    uv_layer_name: str | None = None,
    average_split_normals: bool = False,
) -> str:
    # NOTE: intentionally NOT including the object's active material name here.
    # This is the EXPORTED-GEOMETRY cache key; the low-poly's material does not
    # affect the exported mesh bytes (verts/normals/uvs/topology — verified
    # byte-identical via the backend's xxh3 revision token regardless of
    # material). Baking assigns a transient PREVIEW material to the low-poly,
    # so including the material name made the prewarm's key (real material) and
    # the bake's key (preview material) diverge for identical geometry → the
    # prepared-group cache missed → the bake re-prepared everything and the
    # ~20s prewarm was thrown away. Same class of bug as the is_updated removal
    # in _object_signature. The material name still rides on ExportedMeshRef
    # (material_name=...) for anything that genuinely needs it.
    parts = [
        "OBJECT_EXPORT",
        _object_signature(obj),
        _mesh_content_token(obj, uv_layer_name),
        str(uv_layer_name or ""),
        bool(average_split_normals),
        _resolve_object_collection_name(obj),
    ]
    matrix_world = getattr(obj, "matrix_world", None)
    if matrix_world is not None and not cage.is_conformal_3x3(matrix_world):
        # Non-uniformly scaled objects export their normals through the inverse
        # transpose now; their old cached payloads carried tilted normals.
        parts.append("normal_covector")
    key = _signature_cache_key(*parts)
    _dump_object_export_cache_key_inputs(obj, uv_layer_name, average_split_normals, key)
    return key


def _dump_object_export_cache_key_inputs(obj, uv_layer_name, average_split_normals, key) -> None:
    # Diagnostic (env-gated): log every candidate input that feeds the low-mesh
    # export cache key, so a single prewarm+bake reveals exactly which field
    # differs between them by NAME (instead of inferring it from the hash).
    import os
    dump_dir = os.environ.get("FYR_BAKER_DUMP_PREPARED_KEY")
    if not dump_dir:
        return
    try:
        data = getattr(obj, "data", None)
        topo = ()
        if data is not None:
            topo = (
                mesh_read.element_count(data, "vertices"),
                mesh_read.element_count(data, "edges"),
                mesh_read.element_count(data, "polygons"),
            )
        fields = {
            "obj_name": getattr(obj, "name", ""),
            "data_name": getattr(data, "name", "") if data is not None else "",
            "obj_ptr": obj.as_pointer() if hasattr(obj, "as_pointer") else 0,
            "data_ptr": data.as_pointer() if data is not None and hasattr(data, "as_pointer") else 0,
            "topology": topo,
            "active_material": _resolve_object_material_name(obj),
            "collection": _resolve_object_collection_name(obj),
            "uv_layer": str(uv_layer_name or ""),
            "avg_split_normals": bool(average_split_normals),
            "key": key,
        }
        line = "OBJ_EXPORT_KEY_INPUTS " + " | ".join(f"{k}={v}" for k, v in fields.items())
        path = os.path.join(dump_dir, "mb_object_export_key_inputs.log")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _auto_cage_export_cache_key(
    obj,
    *,
    uv_layer_name: str | None = None,
    offset: float = 0.0,
    smooth_normals: bool = False,
) -> str:
    return _signature_cache_key(
        # V3: Smooth Cage off bridges by smooth fans (backend v16). V2: convex hard edges
        # bridged (backend v15). Older entries are a different cage.
        "AUTO_CAGE_EXPORT_V3",
        _object_signature(obj),
        str(uv_layer_name or ""),
        round(float(offset), 6),
        bool(smooth_normals),
    )


def _make_image_sampler(image):
    """Return a callable (u, v) -> float that bilinearly samples the red channel of image, or None if image is None / empty."""
    if image is None:
        return None
    w, h = image.size[0], image.size[1]
    if w <= 0 or h <= 0:
        return None
    pixels_flat = [0.0] * (w * h * 4)
    image.pixels.foreach_get(pixels_flat)
    red = pixels_flat[0::4]

    def _sample(u: float, v: float) -> float:
        fx = (u % 1.0) * (w - 1)
        fy = (v % 1.0) * (h - 1)
        x0 = int(fx)
        y0 = int(fy)
        x1 = min(x0 + 1, w - 1)
        y1 = min(y0 + 1, h - 1)
        tx = fx - x0
        ty = fy - y0
        val = (
            red[y0 * w + x0] * (1 - tx) * (1 - ty)
            + red[y0 * w + x1] * tx * (1 - ty)
            + red[y1 * w + x0] * (1 - tx) * ty
            + red[y1 * w + x1] * tx * ty
        )
        return float(val)

    return _sample


def _acquire_evaluated_mesh(obj, depsgraph, *, preserve_all_data_layers: bool):
    obj_eval = obj.evaluated_get(depsgraph)
    if getattr(obj_eval, "type", None) == "MESH" and getattr(obj_eval, "data", None) is not None:
        # A plain copy of the evaluated mesh (every layer, implicitly shared, no modifier
        # re-evaluation), so what the export reads dies with it -- see mesh_read.
        mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    else:
        mesh = obj_eval.to_mesh(preserve_all_data_layers=preserve_all_data_layers, depsgraph=depsgraph)
    if mesh is not None:
        mesh_read.detach_mesh_runtime_caches(mesh)
        floater_faces.filter_export_mesh(obj, mesh)
        low_material_subset.filter_export_mesh(obj, mesh)
    return obj_eval, mesh, True


def _average_split_normal_rows_numpy(mesh, loop_vertex_indices, loop_normals, vertex_positions) -> object | None:
    import numpy as np

    try:
        vertex_position_keys = np.rint(vertex_positions * 1_000_000.0).astype(np.int64, copy=False)
        view_dtype = np.dtype((np.void, vertex_position_keys.dtype.itemsize * 3))
        structured_keys = np.ascontiguousarray(vertex_position_keys).view(view_dtype).ravel()
        _unique_keys, vertex_group_indices = np.unique(structured_keys, return_inverse=True)
        
        loop_group_indices = vertex_group_indices[loop_vertex_indices]
        grouped_normals = np.zeros((int(_unique_keys.shape[0]), 3), dtype=np.float64)
        np.add.at(grouped_normals, loop_group_indices, loop_normals.astype(np.float64, copy=False))
        
        lengths = np.sqrt(np.einsum('ij,ij->i', grouped_normals, grouped_normals))[:, None]
        safe_lengths = np.where(lengths > 1.0e-10, lengths, 1.0)
        normalized = grouped_normals / safe_lengths
        averaged = np.where(lengths > 1.0e-10, normalized, grouped_normals)
        return averaged[vertex_group_indices].astype(np.float32, copy=False)
    except Exception:
        return None


def _build_evaluated_obj_payload_fast_python(
    obj,
    depsgraph,
    uv_layer_name: str | None = None,
    *,
    average_split_normals: bool = False,
    paint_offset_image=None,
    paint_skew_image=None,
    paint_offset_scale_fallback: float = 1.0,
    paint_skew_fallback: float = 0.0,
    paint_offset_layer_mode: bool = False,
    # Which mesh data fills the corner colour stream (None = the active colour attribute).
    color_source: color_stream.ColorStreamSource | None = None,
    # HIGH-POLY MESHES MUST BE EXPORTED IN LOCAL SPACE. The backend's contract for a high
    # mesh is "local-space geometry + ExportedMeshRef.matrix_world as the TLAS instance
    # transform" -- see write_evaluated_high_obj, which says so explicitly and is the path
    # every non-vertex-colour bake takes. Baking the transform into the payload and leaving
    # matrix_world unset instead makes the ray and the BLAS disagree, and the projection
    # resolves misses on EVERY covered texel: the bake then falls back to low-poly
    # interpolated normals, which is the large-facet corruption that hit Normal,
    # ObjectNormal, WorldNormal, AO, Thickness, Curvature, Cavity, Concave and Convex
    # together on any bake with VERTEX_COLOR enabled.
    local_space: bool = False,
) -> bytes | None:
    if average_split_normals:
        return None
    if paint_offset_layer_mode:
        # Paint layers are read with numpy; without it the slow writer takes over.
        return None

    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=True)
    if mesh is None:
        return None
    try:
        class _ForeachList(list):
            def __setitem__(self, key, value):
                if key is Ellipsis:
                    self[:] = value
                    return
                super().__setitem__(key, value)

        calc_normals_split = getattr(mesh, "calc_normals_split", None)
        if callable(calc_normals_split):
            calc_normals_split()
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()

        loop_triangles = getattr(mesh, "loop_triangles", None)
        loops = getattr(mesh, "loops", None)
        vertices = getattr(mesh, "vertices", None)
        if loop_triangles is None or loops is None or vertices is None:
            return None
        if not (
            hasattr(loop_triangles, "foreach_get")
            and hasattr(loops, "foreach_get")
            and hasattr(vertices, "foreach_get")
        ):
            return None

        triangle_count = len(loop_triangles)
        loop_count = len(loops)
        vertex_count = len(vertices)
        if triangle_count <= 0 or loop_count <= 0 or vertex_count <= 0:
            return None

        triangle_loop_indices = _ForeachList([0] * (triangle_count * 3))
        loop_triangles.foreach_get("loops", triangle_loop_indices)
        loop_vertex_indices = _ForeachList([0] * loop_count)
        corner_verts_cached = getattr(mesh, "corner_verts", None)
        if corner_verts_cached is not None and hasattr(corner_verts_cached, "foreach_get"):
            corner_verts_cached.foreach_get("vertex", loop_vertex_indices)
        else:
            loops.foreach_get("vertex_index", loop_vertex_indices)

        vertex_positions_flat = _ForeachList([0.0] * (vertex_count * 3))
        read_vertex_positions(mesh, vertices, vertex_positions_flat)
        loop_normals_flat = _ForeachList([0.0] * (loop_count * 3))
        corner_normals_cached = getattr(mesh, "corner_normals", None)
        if corner_normals_cached is not None and hasattr(corner_normals_cached, "foreach_get"):
            corner_normals_cached.foreach_get("vector", loop_normals_flat)
        else:
            loops.foreach_get("normal", loop_normals_flat)

        uv_layer = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name)
        uv_flat = None
        if uv_layer is not None:
            if not hasattr(uv_layer, "foreach_get"):
                return None
            uv_flat = _ForeachList([0.0] * (loop_count * 2))
            uv_layer.foreach_get("uv", uv_flat)

        color_attribute = _resolve_corner_color_attribute(mesh, color_source)
        paint_offset_sampler = _make_image_sampler(paint_offset_image)
        paint_skew_sampler = _make_image_sampler(paint_skew_image)
        matrix_world = getattr(obj_eval, "matrix_world", None)
        if matrix_world is None:
            return None
        # Normals: inverse transpose under non-uniform scale (see cage.normal_matrix_3x3).
        normal_matrix = matrix_world if cage.is_conformal_3x3(matrix_world) else cage.normal_matrix_3x3(matrix_world)

        def _position(vertex_index: int) -> tuple[float, float, float]:
            base = int(vertex_index) * 3
            x = float(vertex_positions_flat[base])
            y = float(vertex_positions_flat[base + 1])
            z = float(vertex_positions_flat[base + 2])
            if local_space:
                return (x, y, z)
            return (
                float(matrix_world[0][0]) * x + float(matrix_world[0][1]) * y + float(matrix_world[0][2]) * z + float(matrix_world[0][3]),
                float(matrix_world[1][0]) * x + float(matrix_world[1][1]) * y + float(matrix_world[1][2]) * z + float(matrix_world[1][3]),
                float(matrix_world[2][0]) * x + float(matrix_world[2][1]) * y + float(matrix_world[2][2]) * z + float(matrix_world[2][3]),
            )

        def _normal(loop_index: int) -> tuple[float, float, float]:
            base = int(loop_index) * 3
            x = float(loop_normals_flat[base])
            y = float(loop_normals_flat[base + 1])
            z = float(loop_normals_flat[base + 2])
            if local_space:
                length = (x * x + y * y + z * z) ** 0.5
                if length <= 1.0e-10:
                    return (x, y, z)
                inv = 1.0 / length
                return (x * inv, y * inv, z * inv)
            nm = normal_matrix
            nx = float(nm[0][0]) * x + float(nm[0][1]) * y + float(nm[0][2]) * z
            ny = float(nm[1][0]) * x + float(nm[1][1]) * y + float(nm[1][2]) * z
            nz = float(nm[2][0]) * x + float(nm[2][1]) * y + float(nm[2][2]) * z
            length = (nx * nx + ny * ny + nz * nz) ** 0.5
            if length <= 1.0e-10:
                return (nx, ny, nz)
            inv_length = 1.0 / length
            return (nx * inv_length, ny * inv_length, nz * inv_length)

        triangles = []
        for tri_index in range(triangle_count):
            corners = []
            for local_corner in range(3):
                loop_index = int(triangle_loop_indices[tri_index * 3 + local_corner])
                if loop_index < 0 or loop_index >= loop_count:
                    return None
                vertex_index = int(loop_vertex_indices[loop_index])
                if vertex_index < 0 or vertex_index >= vertex_count:
                    return None
                if uv_flat is None:
                    u_value = 0.0
                    v_value = 0.0
                else:
                    uv_base = loop_index * 2
                    u_value = float(uv_flat[uv_base])
                    v_value = float(uv_flat[uv_base + 1])
                corners.append(
                    (
                        _position(vertex_index),
                        _normal(loop_index),
                        (u_value, v_value),
                        _color_attribute_value(color_attribute, loop_index, vertex_index),
                        (
                            paint_offset_sampler(u_value, v_value) * float(paint_offset_scale_fallback)
                            if paint_offset_sampler is not None
                            else float(paint_offset_scale_fallback)
                        ),
                        (
                            paint_skew_sampler(u_value, v_value) * float(paint_skew_fallback)
                            if paint_skew_sampler is not None
                            else float(paint_skew_fallback)
                        ),
                    )
                )
            triangles.append(tuple(corners))
        return mesh_transport.build_triangle_soup_mesh_payload(triangles, triangle_count=triangle_count)
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _resolve_color_rows_numpy(color_attribute) -> tuple[str, object] | None:
    import numpy as np

    if color_attribute is None:
        return None
    domain, data = color_attribute
    if isinstance(data, np.ndarray):
        # Attribute rows arrive as a finished (n, 3) float32 stream.
        return domain, data
    if data is None or not hasattr(data, "foreach_get"):
        return None
    element_count = len(data)
    if element_count <= 0:
        return domain, np.empty((0, 3), dtype=np.float32)
    color_flat = np.empty(element_count * 4, dtype=np.float32)
    data.foreach_get("color", color_flat)
    return domain, color_flat.reshape(element_count, 4)[:, :3]


def _build_evaluated_obj_payload_fast(
    obj,
    depsgraph,
    uv_layer_name: str | None = None,
    *,
    average_split_normals: bool = False,
    paint_offset_image=None,
    paint_skew_image=None,
    paint_offset_scale_fallback: float = 1.0,
    paint_skew_fallback: float = 0.0,
    paint_offset_layer_mode: bool = False,
    # Which mesh data fills the corner colour stream (None = the active colour attribute).
    color_source: color_stream.ColorStreamSource | None = None,
    # HIGH-POLY MESHES MUST BE EXPORTED IN LOCAL SPACE. The backend's contract for a high
    # mesh is "local-space geometry + ExportedMeshRef.matrix_world as the TLAS instance
    # transform" -- see write_evaluated_high_obj, which says so explicitly and is the path
    # every non-vertex-colour bake takes. Baking the transform into the payload and leaving
    # matrix_world unset instead makes the ray and the BLAS disagree, and the projection
    # resolves misses on EVERY covered texel: the bake then falls back to low-poly
    # interpolated normals, which is the large-facet corruption that hit Normal,
    # ObjectNormal, WorldNormal, AO, Thickness, Curvature, Cavity, Concave and Convex
    # together on any bake with VERTEX_COLOR enabled.
    local_space: bool = False,
) -> bytes | None:
    try:
        import numpy as np
    except ModuleNotFoundError:
        return _build_evaluated_obj_payload_fast_python(
            obj,
            depsgraph,
            uv_layer_name=uv_layer_name,
            average_split_normals=average_split_normals,
            paint_offset_image=paint_offset_image,
            paint_skew_image=paint_skew_image,
            paint_offset_scale_fallback=paint_offset_scale_fallback,
            paint_skew_fallback=paint_skew_fallback,
            paint_offset_layer_mode=paint_offset_layer_mode,
            local_space=local_space,
            color_source=color_source,
        )

    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=True)
    if mesh is None:
        return None

    try:
        calc_normals_split = getattr(mesh, "calc_normals_split", None)
        if callable(calc_normals_split):
            calc_normals_split()
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()

        loop_triangles = getattr(mesh, "loop_triangles", None)
        loops = getattr(mesh, "loops", None)
        vertices = getattr(mesh, "vertices", None)
        if loop_triangles is None or loops is None or vertices is None:
            return None
        if not (
            hasattr(loop_triangles, "foreach_get")
            and hasattr(loops, "foreach_get")
            and hasattr(vertices, "foreach_get")
        ):
            return None

        triangle_count = len(loop_triangles)
        loop_count = len(loops)
        vertex_count = len(vertices)
        if triangle_count <= 0 or loop_count <= 0 or vertex_count <= 0:
            return None

        triangle_loop_indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("loops", triangle_loop_indices)
        triangle_loop_indices = rna_buffers.as_i32(triangle_loop_indices)

        loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
        corner_verts_cached = getattr(mesh, "corner_verts", None)
        if corner_verts_cached is not None and hasattr(corner_verts_cached, "foreach_get"):
            corner_verts_cached.foreach_get("vertex", loop_vertex_indices)
        else:
            loops.foreach_get("vertex_index", loop_vertex_indices)
        loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)
        vertex_positions_flat = np.empty(vertex_count * 3, dtype=np.float32)
        read_vertex_positions(mesh, vertices, vertex_positions_flat)
        vertex_positions = vertex_positions_flat.reshape(vertex_count, 3)

        loop_normals_flat = np.empty(loop_count * 3, dtype=np.float32)
        corner_normals_cached = getattr(mesh, "corner_normals", None)
        if corner_normals_cached is not None and hasattr(corner_normals_cached, "foreach_get"):
            corner_normals_cached.foreach_get("vector", loop_normals_flat)
        else:
            loops.foreach_get("normal", loop_normals_flat)
        loop_normals = loop_normals_flat.reshape(loop_count, 3)
        averaged_vertex_normals = None
        if average_split_normals:
            averaged_vertex_normals = _average_split_normal_rows_numpy(mesh, loop_vertex_indices, loop_normals, vertex_positions)
            if averaged_vertex_normals is None:
                return None
            # The per-loop normals are not read again on this path.
            loop_normals = None
            loop_normals_flat = None

        uv_layer = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name)
        loop_uvs = None
        if uv_layer is not None:
            if not hasattr(uv_layer, "foreach_get"):
                return None
            uv_flat = np.empty(loop_count * 2, dtype=np.float32)
            uv_layer.foreach_get("uv", uv_flat)
            loop_uvs = uv_flat.reshape(loop_count, 2)

        color_attribute = _resolve_corner_color_attribute(mesh, color_source)
        color_values = None
        color_per_vertex = False
        if color_attribute is not None:
            color_rows = _resolve_color_rows_numpy(color_attribute)
            if color_rows is None:
                return None
            color_domain, color_values = color_rows
            color_per_vertex = color_domain == "POINT"

        translation = None
        position_linear_t = None
        normal_linear_t = None
        if not local_space:
            matrix_world = np.asarray(obj_eval.matrix_world, dtype=np.float32)
            position_linear_t = matrix_world[:3, :3].T
            translation = matrix_world[:3, 3]
            # Normals are covectors: the inverse transpose under non-uniform scale
            # (cage.normal_matrix_3x3); conformal matrices keep the exact old product.
            linear = matrix_world[:3, :3]
            if not cage.is_conformal_3x3(linear):
                linear = np.linalg.inv(linear.astype(np.float64)).T.astype(np.float32)
            normal_linear_t = linear.T

        # Paint values need the corner UVs only to sample a paint image; without one they
        # are a pure function of the loops, so the whole-mesh corner UV array is skipped.
        paint_corner_uvs = None
        if paint_offset_image is not None or paint_skew_image is not None:
            if loop_uvs is None:
                paint_corner_uvs = np.zeros((triangle_count * 3, 2), dtype=np.float32)
            else:
                paint_corner_uvs = loop_uvs[triangle_loop_indices]
        paint_offsets, paint_skews = paint_sampling.corner_paint_values(
            mesh,
            triangle_loop_indices,
            paint_corner_uvs,
            loop_vertex_indices=loop_vertex_indices,
            offset_image=paint_offset_image,
            skew_image=paint_skew_image,
            offset_scale=paint_offset_scale_fallback,
            skew_amount=paint_skew_fallback,
            offset_layer_mode=paint_offset_layer_mode,
        )
        paint_corner_uvs = None
        use_v3 = mesh_transport.triangle_soup_paint_columns_needed(paint_offsets, paint_skews)
        if use_v3:
            paint_offsets = np.asarray(paint_offsets, dtype=np.float32).reshape(-1)
            paint_skews = np.asarray(paint_skews, dtype=np.float32).reshape(-1)
        else:
            paint_offsets = paint_skews = None
        width = 13 if use_v3 else 11

        # Same per-corner values as the whole-array build (every step is row-wise, so a
        # chunk boundary cannot change a byte), gathered and written one chunk at a time.
        # The whole-array build held the corner arrays plus column_stack, tobytes and the
        # header concat at once: ~4x the payload size in Blender for every high-poly
        # export that needs UVs or vertex colours.
        def _corner_rows():
            corner_total = triangle_count * 3
            step = max(1, int(_HIGH_EXPORT_CHUNK_TRIANGLES)) * 3
            for begin in range(0, corner_total, step):
                chunk_loops = triangle_loop_indices[begin:begin + step]
                chunk_vertices = loop_vertex_indices[chunk_loops]
                rows = np.empty((chunk_loops.shape[0], width), dtype=np.float32)
                corner_positions = vertex_positions[chunk_vertices]
                if averaged_vertex_normals is not None:
                    corner_normals = averaged_vertex_normals[chunk_vertices]
                else:
                    corner_normals = loop_normals[chunk_loops]
                if local_space:
                    # Leave the transform to the backend's TLAS instance (see local_space above).
                    rows[:, 0:3] = corner_positions
                    world_normals = corner_normals
                else:
                    rows[:, 0:3] = (corner_positions @ position_linear_t) + translation
                    world_normals = corner_normals @ normal_linear_t
                corner_positions = None
                normal_lengths = np.linalg.norm(world_normals, axis=1, keepdims=True)
                safe_lengths = np.where(normal_lengths > 1.0e-10, normal_lengths, 1.0)
                normalized_normals = world_normals / safe_lengths
                rows[:, 3:6] = np.where(normal_lengths > 1.0e-10, normalized_normals, world_normals)
                if loop_uvs is None:
                    rows[:, 6:8] = 0.0
                else:
                    rows[:, 6:8] = loop_uvs[chunk_loops]
                if color_values is None:
                    rows[:, 8:11] = 1.0
                elif color_per_vertex:
                    rows[:, 8:11] = color_values[chunk_vertices]
                else:
                    rows[:, 8:11] = color_values[chunk_loops]
                if use_v3:
                    rows[:, 11] = paint_offsets[begin:begin + step]
                    rows[:, 12] = paint_skews[begin:begin + step]
                yield rows

        return mesh_transport.StreamedTriangleSoupPayload(
            triangle_count=triangle_count,
            use_v3=use_v3,
            chunk_factory=_corner_rows,
        )
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


# The pure-Python writer builds a Python tuple per corner (roughly 1 KB per triangle), so
# it is only viable for small meshes. 2026-09-28: SvAT (41.4M-triangle high) fell into it
# when the numpy path raised MemoryError under low free memory; Blender grew from 22 to
# 48 GB, system commit hit zero, Windows killed dwm.exe and the PC had to be reset.
_SLOW_EXPORT_MAX_TRIANGLES = 1_000_000


def _export_out_of_memory_error(obj, exc: BaseException) -> MemoryError:
    """The error a fast export raises when it ran out of memory.

    A MemoryError must never fall through to a heavier export path: every fallback needs
    more memory than the fast path that just failed.
    """
    name = getattr(obj, "name", "") or "mesh"
    return MemoryError(
        f"Not enough free memory to export '{name}'. Close other applications or split the "
        f"bake group, then bake again. ({exc.__class__.__name__}: {exc})"
    )


def _write_evaluated_obj_slow(
    obj,
    depsgraph,
    destination: Path,
    uv_layer_name: str | None = None,
    *,
    average_split_normals: bool = False,
    cache_key_override: str | None = None,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
    paint_offset_image=None,
    paint_skew_image=None,
    paint_offset_scale_fallback: float = 1.0,
    paint_skew_fallback: float = 0.0,
    paint_offset_layer_mode: bool = False,
    # Which mesh data fills the corner colour stream (None = the active colour attribute).
    color_source: color_stream.ColorStreamSource | None = None,
) -> protocol.ExportedMeshRef:
    destination.parent.mkdir(parents=True, exist_ok=True)

    paint_offset_sampler = _make_image_sampler(paint_offset_image)
    paint_skew_sampler = _make_image_sampler(paint_skew_image)

    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")
    floater_faces.filter_export_mesh(obj, mesh)
    low_material_subset.filter_export_mesh(obj, mesh)

    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        triangle_count = len(mesh.loop_triangles)
        if triangle_count > _SLOW_EXPORT_MAX_TRIANGLES:
            raise RuntimeError(
                f"Could not export '{obj.name}' ({triangle_count:,} triangles): the fast "
                f"export failed and the fallback exporter only handles up to "
                f"{_SLOW_EXPORT_MAX_TRIANGLES:,} triangles."
            )
        uv_layer = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name)
        color_attribute = _resolve_corner_color_attribute(mesh, color_source)
        averaged_normal_lookup = cage.build_average_split_normal_lookup(mesh) if average_split_normals else {}
        # The paint offset layer resolves per loop up front (same rule as the fast writer).
        layer_offsets = None
        if paint_offset_layer_mode:
            import numpy as np

            loop_ids = np.arange(len(mesh.loops), dtype=np.int64)
            layer_offsets, _ = paint_sampling.corner_paint_values(
                mesh,
                loop_ids,
                np.zeros((loop_ids.shape[0], 2), dtype=np.float32),
                offset_scale=paint_offset_scale_fallback,
                offset_layer_mode=True,
            )

        triangles = []

        for tri in mesh.loop_triangles:
            triangle_corners = []
            for loop_index in tri.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                world_co = obj_eval.matrix_world @ vertex.co
                source_normal = averaged_normal_lookup.get(loop.vertex_index, loop.normal)
                world_normal = _transformed_normal(obj_eval.matrix_world, source_normal)
                if uv_layer is not None:
                    uv = uv_layer[loop_index].uv
                    u_value = float(uv.x)
                    v_value = float(uv.y)
                else:
                    u_value = 0.0
                    v_value = 0.0
                if layer_offsets is not None:
                    paint_offset_value = float(layer_offsets[loop_index])
                elif paint_offset_sampler is not None:
                    paint_offset_value = paint_offset_sampler(u_value, v_value) * float(paint_offset_scale_fallback)
                else:
                    paint_offset_value = paint_offset_scale_fallback
                if paint_skew_sampler is not None:
                    paint_skew_value = paint_skew_sampler(u_value, v_value) * float(paint_skew_fallback)
                else:
                    paint_skew_value = paint_skew_fallback
                triangle_corners.append(
                    (
                        (float(world_co.x), float(world_co.y), float(world_co.z)),
                        (float(world_normal.x), float(world_normal.y), float(world_normal.z)),
                        (float(u_value), float(v_value)),
                        _color_attribute_value(color_attribute, loop_index, loop.vertex_index),
                        paint_offset_value,
                        paint_skew_value,
                    )
                )
            triangles.append(tuple(triangle_corners))

        resolved_path = mesh_transport.write_triangle_soup_mesh_ref(
            destination,
            triangles,
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
        )
    finally:
        obj_eval.to_mesh_clear()

    return protocol.ExportedMeshRef(
        name=naming.sanitize_token(obj.name),
        object_name=obj.name,
        role="",
        path=str(resolved_path),
        cache_key=str(
            cache_key_override
            or _object_export_cache_key(
                obj,
                uv_layer_name=uv_layer_name,
                average_split_normals=average_split_normals,
            )
        ),
        material_name=_resolve_stable_material_name(obj),
        material_color=_resolve_object_material_color(obj),
        collection_name=_resolve_object_collection_name(obj),
        file_id_key=_resolve_object_file_id_key(obj),
        world_to_object=_world_to_object_matrix_values(obj),
    )


# Triangles per streamed V4 chunk: ~125 MB of transient arrays per chunk.
_HIGH_EXPORT_CHUNK_TRIANGLES = 1 << 19
_HIGH_EXPORT_GATHER_WORKERS = 4
_HIGH_EXPORT_GATHER_POOL = None
_HIGH_EXPORT_GATHER_POOL_LOCK = threading.Lock()


def _high_export_gather_pool():
    """Shared worker pool for high-mesh corner gathers (main thread and prewarm writer)."""
    global _HIGH_EXPORT_GATHER_POOL
    with _HIGH_EXPORT_GATHER_POOL_LOCK:
        if _HIGH_EXPORT_GATHER_POOL is None:
            from concurrent.futures import ThreadPoolExecutor

            _HIGH_EXPORT_GATHER_POOL = ThreadPoolExecutor(
                max_workers=_HIGH_EXPORT_GATHER_WORKERS, thread_name_prefix="FyrHighGather"
            )
        return _HIGH_EXPORT_GATHER_POOL


def _write_evaluated_high_obj_payload_fast(obj, depsgraph, destination: Path) -> Path | None:
    """Export position + normal only as V4 for high-poly ray-cast meshes, streamed to disk.

    UV is always discarded by the backend GPU path and color is only used by the CPU-only
    VertexColor map. Skipping them reduces the payload by ~45% vs V2 and avoids two
    foreach_get passes over millions of loops.

    Only the per-loop/per-vertex inputs (~50 B per triangle) are held whole; corner
    positions and normals are gathered, normalized and written one chunk at a time. The
    whole-mesh version peaked at ~410 B per triangle in Blender. Returns None when the mesh
    cannot take the fast path (nothing written).
    """
    captured = capture_high_obj_corner_arrays(obj, depsgraph)
    if captured is None:
        return None
    return write_high_corner_arrays(destination, captured)


def capture_high_obj_corner_arrays(obj, depsgraph):
    """The per-loop/per-vertex inputs of :func:`write_high_corner_arrays` (main thread:
    reads the evaluated mesh), or None when the mesh cannot take the fast path. The
    arrays are copies, so the write can run later on another thread."""
    import numpy as np

    # preserve_all_data_layers=False: we only need geometry, not extra layers.
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=False)
    if mesh is None:
        return None

    try:
        calc_normals_split = getattr(mesh, "calc_normals_split", None)
        if callable(calc_normals_split):
            calc_normals_split()
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()

        loop_triangles = getattr(mesh, "loop_triangles", None)
        loops = getattr(mesh, "loops", None)
        vertices = getattr(mesh, "vertices", None)
        if loop_triangles is None or loops is None or vertices is None:
            return None
        if not (
            hasattr(loop_triangles, "foreach_get")
            and hasattr(loops, "foreach_get")
            and hasattr(vertices, "foreach_get")
        ):
            return None

        loop_count = len(loops)
        vertex_count = len(vertices)
        polygons = getattr(mesh, "polygons", None)
        if polygons is not None and loop_count > 0 and loop_count == 3 * len(polygons):
            # Every face is a triangle, so triangle i IS loops 3i..3i+2 (checked against
            # loop_triangles on all 178 meshes of a customer gun). Reading loop_triangles
            # triangulates the copy and copies 3 ints per triangle on the main thread:
            # 0.8 s of a 9 M-triangle high's freeze. The writer makes the indices.
            triangle_count = len(polygons)
            triangle_loop_indices = None
        else:
            triangle_count = len(loop_triangles)
            triangle_loop_indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
            if triangle_count > 0:
                loop_triangles.foreach_get("loops", triangle_loop_indices)
            triangle_loop_indices = rna_buffers.as_i32(triangle_loop_indices)
        if triangle_count <= 0 or loop_count <= 0 or vertex_count <= 0:
            return None

        corner_verts_cached = getattr(mesh, "corner_verts", None)
        if corner_verts_cached is not None and hasattr(corner_verts_cached, "foreach_get"):
            loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
            corner_verts_cached.foreach_get("vertex", loop_vertex_indices)
            loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)
        else:
            # INT attribute data wants an intc buffer, the loops collection a uintc one.
            loop_vertex_indices = rna_buffers.empty_i32_for_attribute(loop_count)
            if not _read_corner_vert_attribute(mesh, loop_vertex_indices):
                loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
                loops.foreach_get("vertex_index", loop_vertex_indices)
                loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)
            else:
                loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)

        vertex_positions_flat = np.empty(vertex_count * 3, dtype=np.float32)
        read_vertex_positions(mesh, vertices, vertex_positions_flat)
        vertex_positions = vertex_positions_flat.reshape(vertex_count, 3)

        # Prefer the Blender 4.1+ corner_normals attribute (no calc_normals_split overhead)
        loop_normals_flat = np.empty(loop_count * 3, dtype=np.float32)
        corner_normals_attr = getattr(mesh, "corner_normals", None)
        if corner_normals_attr is not None and hasattr(corner_normals_attr, "foreach_get"):
            corner_normals_attr.foreach_get("vector", loop_normals_flat)
        else:
            loops.foreach_get("normal", loop_normals_flat)
        loop_normals = loop_normals_flat.reshape(loop_count, 3)
        return triangle_count, triangle_loop_indices, loop_vertex_indices, vertex_positions, loop_normals
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _read_corner_vert_attribute(mesh, out) -> bool:
    """Fill ``out`` from the mesh's ``.corner_vert`` attribute; False when unavailable.

    Same values as ``loops.foreach_get("vertex_index")``, but a flat attribute read
    instead of the per-loop RNA path: about 3 s less main-thread capture on a
    72 M-triangle scene."""
    attributes = getattr(mesh, "attributes", None)
    getter = getattr(attributes, "get", None)
    if getter is None:
        return False
    try:
        attribute = getter(".corner_vert")
        if attribute is None or getattr(attribute, "domain", "") != "CORNER":
            return False
        data = attribute.data
        if len(data) != len(out):
            return False
        data.foreach_get("value", out)
        return True
    except Exception:
        return False


def write_high_corner_arrays(destination: Path, captured) -> Path:
    """Write :func:`capture_high_obj_corner_arrays` output as V4. Touches no Blender data,
    so it may run on a worker thread."""
    import numpy as np

    triangle_count, triangle_loop_indices, loop_vertex_indices, vertex_positions, loop_normals = captured

    # Same bytes from C++ (several threads, no per-chunk numpy temporaries). None means the
    # arrays or the DLL are not usable for it and the numpy writer below does the work.
    native_path = native_mesh_write.write_fymesh_v4_arrays(destination, captured)
    if native_path is not None:
        return native_path

    # Export in local (object) space so the file content — and therefore the
    # per-mesh BLAS cache key — is stable across pure transform changes.
    # The backend receives matrix_world_transform separately and uses it as
    # the TLAS instance transform so DXR handles the local→world mapping.
    corner_total = triangle_count * 3
    # Chunks are gathered on a small pool (numpy releases the GIL in the gather and
    # normalise) and written in order. Each chunk is a quarter of the single-thread
    # chunk, so the rows in flight take no more memory than one chunk used to.
    step = max(1, (_HIGH_EXPORT_CHUNK_TRIANGLES * 3) // _HIGH_EXPORT_GATHER_WORKERS)

    def _build(begin):
        if triangle_loop_indices is None:  # all triangles: corner i is loop i
            chunk_loops = np.arange(begin, min(begin + step, corner_total), dtype=np.int64)
        else:
            chunk_loops = triangle_loop_indices[begin:begin + step]
        rows = np.empty((chunk_loops.shape[0], 6), dtype=np.float32)
        rows[:, :3] = vertex_positions[loop_vertex_indices[chunk_loops]]
        corner_normals = loop_normals[chunk_loops]
        normal_lengths = np.linalg.norm(corner_normals, axis=1, keepdims=True)
        safe_lengths = np.where(normal_lengths > 1.0e-10, normal_lengths, 1.0)
        rows[:, 3:] = corner_normals / safe_lengths
        return rows

    def _corner_rows():
        begins = range(0, corner_total, step)
        if len(begins) <= 1:
            for begin in begins:
                yield _build(begin)
            return
        pool = _high_export_gather_pool()
        pending = collections.deque()
        try:
            for begin in begins:
                pending.append(pool.submit(_build, begin))
                if len(pending) >= _HIGH_EXPORT_GATHER_WORKERS:
                    yield pending.popleft().result()
            while pending:
                yield pending.popleft().result()
        finally:
            for future in pending:
                future.cancel()

    return mesh_transport.write_high_poly_mesh_payload_chunks(destination, triangle_count, _corner_rows())


def write_evaluated_high_obj(
    obj,
    depsgraph,
    destination: Path,
    *,
    cache_key_override: str | None = None,
) -> protocol.ExportedMeshRef:
    """Write a high-poly mesh in V4 format (position + normal only).

    Falls back to the full V2 write_evaluated_obj path if the fast path fails.
    """
    mesh_transport.ensure_dir(destination.parent)
    try:
        resolved_path = _write_evaluated_high_obj_payload_fast(obj, depsgraph, destination)
    except MemoryError as exc:
        raise _export_out_of_memory_error(obj, exc) from exc
    except Exception:
        resolved_path = None

    if resolved_path is not None:
        # Use a local-space cache key so that the per-mesh BLAS survives pure
        # transform changes.  matrix_world is sent separately as the TLAS
        # instance transform so the backend can apply it for CPU Embree and
        # for reconstructing world-space positions from the local BLAS.
        return protocol.ExportedMeshRef(
            name=naming.sanitize_token(obj.name),
            object_name=obj.name,
            role="",
            path=str(resolved_path),
            cache_key=str(cache_key_override or _high_mesh_local_export_cache_key(obj)),
            material_name=_resolve_object_material_name(obj),
            material_color=_resolve_object_material_color(obj),
            collection_name=_resolve_object_collection_name(obj),
            file_id_key=_resolve_object_file_id_key(obj),
            world_to_object=_world_to_object_matrix_values(obj),
            matrix_world=_matrix_world_values(obj),
        )

    return write_evaluated_obj(
        obj,
        depsgraph,
        destination,
        cache_key_override=cache_key_override,
    )



# ---- Evaluated-mesh payload reuse ---------------------------------------------------
#
# The job workspace is a NEW directory every bake, so the exported mesh payload was
# rebuilt and rewritten every time even when nothing about the geometry had changed.
# Profiled on BakeTester3 (Skull/Jaw/Teeth, 16.4M high-poly triangles) re-baking after
# one AO slider move: 29.8s of blocking invoke, all of it here -- 17.9s of
# BufferedWriter.write, 9.5s rebuilding the payload, 2.0s writing the same bytes again
# into shared memory -- in front of a 0.9s backend.
#
# Keyed on the SAME cache_key that already rides on ExportedMeshRef. That key is a pure
# function of the object signature (topology, matrix, data pointer, uv layer, split-normal
# mode, collection) and the BACKEND ALREADY TRUSTS IT to skip re-preparing the group
# outright -- so trusting it to skip rewriting identical bytes is not a weaker claim than
# the one the bake already rests on. If it were unsafe, warm re-bakes would already be
# serving stale prepared geometry.
#
# Deliberately disabled whenever a paint offset/skew image is involved: those feed the
# payload but do NOT feed the cache key, and their pixels can change in place without any
# identity change, so a hit there could go stale. Correctness over coverage.
#
# The payload still goes through the normal shared-memory ref on a MISS, so the first bake
# of a session is byte-for-byte and timing-for-timing what it was; only the redundant
# rewrite on later bakes disappears. Files live under the managed persistent cache root in
# a per-session directory, so the existing disk-hygiene sweep owns their lifetime.
#
# FYR_BAKER_MESH_PAYLOAD_CACHE=0 restores the unconditional rebuild+rewrite.
_EXPORT_PAYLOAD_CACHE: dict[str, tuple[str, int]] = {}
# Keyed on the PROCESS, not the process plus a timestamp. The timestamp meant every addon
# reload minted a fresh directory and re-wrote every high-poly payload into it, so a day of
# reloads left 4 GB of duplicates in five session directories and filled the drive. The pid
# is stable across reloads inside one Blender, which is exactly the reuse this cache is for.
def _export_payload_session_id() -> str:
    """Per-process id that survives addon reloads but not pid recycling.

    A bare pid let a new Blender that happened to get a dead run's pid adopt
    (and, being "live", never prune) that run's directory. The first-seen
    timestamp is parked on sys so a disable/purge/enable reload keeps the same
    directory, which is the reuse this cache exists for.
    """
    import sys
    import time as _time

    started = getattr(sys, "_fyr_baker_payload_session_started", None)
    if started is None:
        started = int(_time.time() * 1000)
        try:
            sys._fyr_baker_payload_session_started = started  # noqa: SLF001
        except Exception:
            pass
    return hashlib.blake2b(f"{os.getpid()}:{started}".encode("utf-8"), digest_size=8).hexdigest()


_EXPORT_PAYLOAD_SESSION = _export_payload_session_id()

# High-poly payloads run to gigabytes each (729 MB and 1.3 GB for two objects of a 16.4M
# triangle project), so this directory has to be bounded or it eats the drive. Prune oldest
# first, by directory, down to the budget. Only sibling sessions are removed: this process's
# own directory is never a candidate.
# 2 GB of STALE sessions. The live session is never counted, so the worst case is one
# live set plus this. Deliberately tight: a single high mesh here is 1.3 GB, and the
# value of this cache is reuse WITHIN a session, not across dead ones.
_EXPORT_PAYLOAD_CACHE_BUDGET_BYTES = 2 * 1024 * 1024 * 1024


def _prune_export_payload_cache_root(root: Path, keep: str) -> None:
    try:
        sessions = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return
    sized: list[tuple[float, int, Path]] = []
    total = 0
    for entry in sessions:
        if entry.name == keep:
            continue
        # A second Blender's session hashes to a different name, so "not ours" is
        # not the same as "dead". Deleting a live sibling's payloads pulled a 1.3 GB
        # mesh out from under its running export, and because this prunes
        # oldest-mtime first an idle-but-live sibling was the FIRST one taken. Live
        # sessions are excluded from the budget exactly as our own directory is.
        if storage_cleanup.session_owner_alive(entry):
            continue
        size = 0
        newest = 0.0
        try:
            for path in entry.rglob("*"):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                size += int(stat.st_size)
                newest = max(newest, float(stat.st_mtime))
        except OSError:
            continue
        total += size
        sized.append((newest, size, entry))
    if total <= _EXPORT_PAYLOAD_CACHE_BUDGET_BYTES:
        return
    for _newest, size, entry in sorted(sized, key=lambda item: item[0]):
        try:
            shutil.rmtree(entry, ignore_errors=True)
        except Exception:
            continue
        total -= size
        if total <= _EXPORT_PAYLOAD_CACHE_BUDGET_BYTES:
            break


def _export_payload_cache_enabled() -> bool:
    return str(os.environ.get("FYR_BAKER_MESH_PAYLOAD_CACHE", "") or "").strip() != "0"


_EXPORT_PAYLOAD_PRUNED = False
_EXPORT_PAYLOAD_STAMPED = False


def _stamp_export_payload_session_owner(root: Path) -> None:
    """Claim this payload directory for our pid so no sibling Blender prunes it."""
    global _EXPORT_PAYLOAD_STAMPED
    try:
        owner_file = root / storage_cleanup._RUNTIME_SESSION_OWNER_FILE  # noqa: SLF001
        if not _EXPORT_PAYLOAD_STAMPED or not owner_file.exists():
            _EXPORT_PAYLOAD_STAMPED = True
            storage_cleanup.mark_runtime_session_owner(root)
    except Exception:
        pass


def _export_payload_cache_root() -> Path:
    global _EXPORT_PAYLOAD_PRUNED
    parent = preferences.persistent_cache_root() / "blender_high_exports" / "payloads"
    root = parent / _EXPORT_PAYLOAD_SESSION
    mesh_transport.ensure_dir(root)
    _stamp_export_payload_session_owner(root)
    if not _EXPORT_PAYLOAD_PRUNED:
        # Once per process, and after our own directory exists so it is never a candidate.
        _EXPORT_PAYLOAD_PRUNED = True
        _prune_export_payload_cache_root(parent, _EXPORT_PAYLOAD_SESSION)
    return root


def _export_payload_cached_path(cache_key: str) -> str | None:
    """Path of a previously written payload for ``cache_key``, if it is still on disk."""
    entry = _EXPORT_PAYLOAD_CACHE.get(cache_key)
    if not entry:
        return None
    path_text, expected_size = entry
    try:
        candidate = Path(path_text)
        if candidate.is_file() and candidate.stat().st_size == expected_size:
            return path_text
    except OSError:
        pass
    _EXPORT_PAYLOAD_CACHE.pop(cache_key, None)
    return None


def _export_payload_cache_store(cache_key: str, path: Path) -> None:
    # No eviction inside the live session: a job references several payloads at
    # once (three high meshes of one project already exceed the sibling budget),
    # and unlinking any of them here failed the next bake with "Failed to open
    # cache file". Stale keys of this session are reclaimed as a sibling
    # directory by the next process.
    try:
        _EXPORT_PAYLOAD_CACHE[cache_key] = (str(path), path.stat().st_size)
    except OSError:
        pass


def write_evaluated_obj(
    obj,
    depsgraph,
    destination: Path,
    uv_layer_name: str | None = None,
    *,
    average_split_normals: bool = False,
    cache_key_override: str | None = None,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
    paint_offset_image=None,
    paint_skew_image=None,
    paint_offset_scale_fallback: float = 1.0,
    paint_skew_fallback: float = 0.0,
    paint_offset_layer_mode: bool = False,
    # Which mesh data fills the corner colour stream (None = the active colour attribute).
    color_source: color_stream.ColorStreamSource | None = None,
    # True for HIGH-poly meshes, whose payload must stay in local space with the transform
    # carried on the ref instead. See the local_space note on _build_evaluated_obj_payload_fast.
    local_space: bool = False,
) -> protocol.ExportedMeshRef:
    mesh_transport.ensure_dir(destination.parent)
    resolved_cache_key = str(
        cache_key_override
        or _object_export_cache_key(
            obj,
            uv_layer_name=uv_layer_name,
            average_split_normals=average_split_normals,
        )
    )
    # Paint images feed the payload but not the key -- never reuse across them.
    # The paint offset/skew SCALARS are written per corner too (and switch the
    # payload to the paint-controls format the backend treats as authoritative),
    # so a changed Offset Scale under an unchanged key reused the old bytes and
    # the new value never reached the bake. Fold them into the identity; the
    # token must stay filesystem-safe because the key doubles as a file name.
    if abs(float(paint_offset_scale_fallback) - 1.0) > 1e-9 or abs(float(paint_skew_fallback)) > 1e-9:
        resolved_cache_key = "{}_po{}_ps{}".format(
            resolved_cache_key,
            f"{float(paint_offset_scale_fallback):.4f}".replace("-", "m").replace(".", "_"),
            f"{float(paint_skew_fallback):.4f}".replace("-", "m").replace(".", "_"),
        )
    # The paint offset layer lives on the mesh, where no vertex count, bound or modifier
    # term of the object key sees a stroke: fold its content in.
    if paint_offset_layer_mode:
        resolved_cache_key = "{}_plo{}".format(
            resolved_cache_key,
            paint_sampling.paint_layer_digest(getattr(obj, "data", None)) or "n",
        )
    # The same object exported local-space and world-space yields DIFFERENT bytes under the
    # same object-signature key, so the space has to be part of the reuse identity.
    # An Attribute row fills the colour stream from other mesh data under the same
    # object signature. Hashed: the key doubles as a file name.
    if color_source is not None and not color_source.is_active_color:
        resolved_cache_key = "{}_cs{}".format(
            resolved_cache_key,
            hashlib.sha1(color_source.cache_key.encode("utf-8")).hexdigest()[:16],
        )
    if local_space:
        # NOTE: this key is also used as a FILENAME for the payload cache, so the suffix
        # must be filesystem-safe. "|local" is not: Windows rejects it with EINVAL and
        # every high-mesh export fails the moment the payload cache is on (its default).
        resolved_cache_key = resolved_cache_key + "_local"
    payload_reuse_allowed = (
        paint_offset_image is None
        and paint_skew_image is None
        and _export_payload_cache_enabled()
    )
    if payload_reuse_allowed:
        cached_path = _export_payload_cached_path(resolved_cache_key)
        if cached_path is not None:
            return protocol.ExportedMeshRef(
                name=naming.sanitize_token(obj.name),
                object_name=obj.name,
                role="",
                path=cached_path,
                cache_key=resolved_cache_key,
                material_name=_resolve_object_material_name(obj),
                material_color=_resolve_object_material_color(obj),
                collection_name=_resolve_object_collection_name(obj),
                file_id_key=_resolve_object_file_id_key(obj),
                world_to_object=_world_to_object_matrix_values(obj),
                # Same local-space contract as the fresh-export return below. Omitting
                # this on the cache hit shipped a LOCAL-space payload with the transform
                # unset, so the backend instanced the high mesh at the object's local
                # origin: every material channel (Metalness/Base Color/Roughness/...) on
                # an object away from the world origin baked correct once and BLACK on
                # every rebake, because only the first bake missed this cache.
                matrix_world=_matrix_world_values(obj) if local_space else [],
            )
    try:
        payload = _build_evaluated_obj_payload_fast(
            obj,
            depsgraph,
            uv_layer_name=uv_layer_name,
            average_split_normals=average_split_normals,
            paint_offset_image=paint_offset_image,
            paint_skew_image=paint_skew_image,
            paint_offset_scale_fallback=paint_offset_scale_fallback,
            paint_skew_fallback=paint_skew_fallback,
            paint_offset_layer_mode=paint_offset_layer_mode,
            local_space=local_space,
            color_source=color_source,
        )
    except MemoryError as exc:
        raise _export_out_of_memory_error(obj, exc) from exc
    except Exception:
        payload = None

    # On a reusable export the payload file goes to the session cache root instead of the
    # job workspace, which is discarded after every bake and is why nothing could be
    # reused before. The shared-memory ref is still produced exactly as before; the file
    # written underneath it is simply somewhere that outlives this job.
    resolved_path = None
    payload_destination = destination
    if payload is not None:
        if payload_reuse_allowed:
            payload_destination = _export_payload_cache_root() / f"{resolved_cache_key}.mbmesh"
        try:
            resolved_path = mesh_transport.write_triangle_soup_payload_ref(
                payload_destination,
                payload,
                workspace_key=workspace_key,
                use_shared_memory=use_shared_memory,
            )
        except MemoryError as exc:
            raise _export_out_of_memory_error(obj, exc) from exc
        except Exception:
            # A streamed payload computes its corner rows while it writes, so a failure
            # there is a failed build: take the same fallbacks a failed build takes.
            if not isinstance(payload, mesh_transport.StreamedTriangleSoupPayload):
                raise
            payload = None

    if payload is None and local_space:
        # _write_evaluated_obj_slow bakes the transform in, which is exactly what a
        # local-space caller must not ship. Take the V4 local-space high writer instead:
        # it drops UV/colour (so a VERTEX_COLOR map degrades to flat) but the geometry
        # stays correct, and wrong geometry is far worse than a flat vertex-colour map.
        return write_evaluated_high_obj(
            obj, depsgraph, destination, cache_key_override=cache_key_override
        )

    if payload is None:
        return _write_evaluated_obj_slow(
            obj,
            depsgraph,
            destination,
            uv_layer_name=uv_layer_name,
            average_split_normals=average_split_normals,
            cache_key_override=cache_key_override,
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
            paint_offset_image=paint_offset_image,
            paint_skew_image=paint_skew_image,
            paint_offset_scale_fallback=paint_offset_scale_fallback,
            paint_skew_fallback=paint_skew_fallback,
            paint_offset_layer_mode=paint_offset_layer_mode,
            color_source=color_source,
        )

    if payload_reuse_allowed:
        # Record the FILE, never the shared-memory ref string: the mapping is owned by
        # this workspace and is released with it, while the file keeps working.
        _export_payload_cache_store(
            resolved_cache_key, mesh_transport.binary_mesh_path(payload_destination)
        )

    return protocol.ExportedMeshRef(
        name=naming.sanitize_token(obj.name),
        object_name=obj.name,
        role="",
        path=str(resolved_path),
        cache_key=resolved_cache_key,
        material_name=_resolve_object_material_name(obj),
        material_color=_resolve_object_material_color(obj),
        collection_name=_resolve_object_collection_name(obj),
        file_id_key=_resolve_object_file_id_key(obj),
        world_to_object=_world_to_object_matrix_values(obj),
        # Only meaningful for a local-space payload: the backend applies it as the TLAS
        # instance transform. A world-space payload must leave it unset (zero sentinel) or
        # the transform would be applied twice.
        matrix_world=_matrix_world_values(obj) if local_space else [],
    )


def _slot_cage_offset_delta(group, slot) -> float:
    """The per-mesh Object Offset as the UI and the cage overlays see it.

    The UI edits the slot in group.role_assignments; the flat group.low_meshes slot the
    exporter iterates keeps its default 0, so reading the flat slot alone dropped every
    Object Offset from the bake while the overlay drew it.
    """
    own = float(getattr(slot, "cage_offset_delta", 0.0) or 0.0)
    obj = getattr(slot, "object_ref", None)
    role_state = getattr(group, "role_assignments", None)
    if obj is None or role_state is None:
        return own
    for nested in getattr(role_state, "low_meshes", []) or []:
        if getattr(nested, "object_ref", None) == obj:
            nested_delta = float(getattr(nested, "cage_offset_delta", 0.0) or 0.0)
            return nested_delta if nested_delta != 0.0 else own
    return own


def group_paint_offset_layer_mode(group) -> bool:
    """Whether any bakeable low of *group* carries the paint offset layer.

    In layer mode every low of the group reads the layer (0 where a mesh has none) and the
    group's legacy offset image is ignored, so the two sources never mix.
    """
    for slot in _iter_bakeable_low_slots(getattr(group, "low_meshes", []) or []):
        mesh = getattr(getattr(slot, "object_ref", None), "data", None)
        if paint_sampling.has_paint_layer(mesh, paint_sampling.OFFSET_ATTRIBUTE):
            return True
    return False


def _export_low_mesh_refs(
    group,
    depsgraph,
    group_root: Path,
    *,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> list[protocol.ExportedMeshRef]:
    low_meshes: list[protocol.ExportedMeshRef] = []
    projection_state = _group_projection_settings_state(group)
    paint_state = _group_paint_projection_settings_state(group)
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
    paint_offset_image = getattr(paint_state, "paint_offset_image", None)
    paint_skew_image = getattr(paint_state, "paint_skew_image", None)
    paint_offset_scale_fallback = float(getattr(paint_state, "paint_offset_scale", 1.0))
    paint_skew_fallback = float(getattr(paint_state, "paint_skew", 0.0))
    distance_mode = str(getattr(projection_state, "cage_mode", "") or "") == constants.CAGE_MODE_DISTANCE
    group_offset = max(0.0, float(getattr(projection_state, "cage_offset", 0.0) or 0.0))
    offset_layer_mode = group_paint_offset_layer_mode(group)
    if offset_layer_mode:
        paint_offset_image = None
    with low_material_subset.group_scope(group):
        return _write_low_mesh_refs(
            group, depsgraph, group_root, low_meshes, uv_layer_name, paint_offset_image, paint_skew_image,
            paint_offset_scale_fallback, paint_skew_fallback, distance_mode, group_offset, offset_layer_mode,
            workspace_key, use_shared_memory,
        )


def _write_low_mesh_refs(
    group, depsgraph, group_root, low_meshes, uv_layer_name, paint_offset_image, paint_skew_image,
    paint_offset_scale_fallback, paint_skew_fallback, distance_mode, group_offset, offset_layer_mode,
    workspace_key, use_shared_memory,
) -> list[protocol.ExportedMeshRef]:
    for index, slot in enumerate(_iter_bakeable_low_slots(group.low_meshes)):
        obj = slot.object_ref
        # Distance mode has no cage mesh to carry the per-object Object Offset, so it
        # rides on the per-corner paint-offset multiplier the backend already applies
        # (effective offset = group offset * paint offset). Without this the viewport
        # cage and its coverage check used group + delta while the bake used the group
        # offset alone: a cage tuned to "no red" still baked at the old distance.
        slot_offset_scale = paint_offset_scale_fallback
        slot_delta = _slot_cage_offset_delta(group, slot)
        if distance_mode and group_offset > 0.0 and slot_delta != 0.0:
            slot_offset_scale *= max(0.0, group_offset + slot_delta) / group_offset
        ref = write_evaluated_obj(
            obj,
            depsgraph,
            group_root / f"low_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
            uv_layer_name=uv_layer_name,
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
            paint_offset_image=paint_offset_image,
            paint_skew_image=paint_skew_image,
            paint_offset_scale_fallback=slot_offset_scale,
            paint_skew_fallback=paint_skew_fallback,
            paint_offset_layer_mode=offset_layer_mode,
        )
        ref.role = constants.OBJECT_ROLE_LOW
        low_meshes.append(ref)
    return low_meshes


def _export_high_mesh_refs(
    group,
    depsgraph,
    group_root: Path,
    *,
    preserve_vertex_colors: bool = False,
    color_source: color_stream.ColorStreamSource | None = None,
    requires_high_uvs: bool = False,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
    cancel_check=None,
    opacity_by_object: dict[int, dict[str, object]] | None = None,
    self_material: bool = False,
) -> list[protocol.ExportedMeshRef]:
    high_meshes: list[protocol.ExportedMeshRef] = []
    high_slots = list(_iter_valid_object_slots(properties.effective_high_mesh_slots(group)))
    if not high_slots and self_material:
        # Bake Selected Materials: no High role. Evaluate the low object's own
        # materials at its UVs by exporting the low mesh as the shading source.
        role_state = properties.group_role_assignments_state(group)
        high_slots = list(_iter_valid_object_slots(getattr(role_state, "low_meshes", [])))
    # A masked high needs its UVs, which only the evaluated-OBJ export carries, and a group
    # cannot mix that with indexed FYRGEOM1 meshes. Only a group that HAS a masked high goes
    # that way: switching every group of the project over for one decal anywhere re-exported
    # unrelated meshes through the other exporter and changed their pixels.
    if opacity_by_object and not requires_high_uvs:
        for slot in high_slots:
            try:
                object_key = int(slot.object_ref.as_pointer())
            except Exception:
                object_key = id(slot.object_ref)
            if object_key in opacity_by_object:
                requires_high_uvs = True
                break
    # Decided once per group. enabled() flips to True when the asynchronous backend probe
    # finishes, so asking it per mesh could export the first highs as FYMESH soup and the
    # rest as FYRGEOM1 in the same group; the backend cannot build one scene from both.
    use_indexed_transport = bool(
        (_JOB_INDEXED_TRANSPORT if _JOB_INDEXED_TRANSPORT is not None else indexed_geometry.enabled())
        and workspace_key
        and not requires_high_uvs
    )

    def _export_one(index, obj, file_suffix=""):
        if use_indexed_transport:
            ref = high_mesh_cache.resolve_indexed_high_mesh_ref(
                obj,
                depsgraph,
                workspace_key,
                include_corner_colors=preserve_vertex_colors,
                color_source=color_source,
                cancel_check=cancel_check,
            )
            ref.role = constants.OBJECT_ROLE_HIGH
        elif preserve_vertex_colors or requires_high_uvs:
            # local_space=True: this is a HIGH mesh, and the backend's high-mesh contract is
            # local geometry + matrix_world as the TLAS instance transform (the convention
            # write_evaluated_high_obj documents and every non-vertex-colour bake uses).
            # Shipping a world-space payload here made the projection miss on EVERY covered
            # texel, so the bake fell back to low-poly interpolated normals -- large-facet
            # corruption across Normal/ObjectNormal/WorldNormal/AO/Thickness/Curvature/
            # Cavity/Concave/Convex on any bake with VERTEX_COLOR enabled, while the same
            # maps baked alone were correct.
            ref = write_evaluated_obj(
                obj,
                depsgraph,
                group_root / f"high_{index:02d}_{naming.sanitize_token(obj.name)}{file_suffix}.fymesh",
                workspace_key=workspace_key,
                use_shared_memory=use_shared_memory,
                local_space=True,
                color_source=color_source,
            )
            ref.role = constants.OBJECT_ROLE_HIGH
        else:
            ref = high_mesh_cache.resolve_high_mesh_ref(obj, depsgraph)
            if Path(ref.path).suffix.lower() == ".fyrgeom":
                # The cache may hold the canonical FYRGEOM1 of this high (prewarmed while
                # indexed transport was on). This group goes out as FYMESH, and one scene
                # cannot mix both, so export the legacy file for it.
                ref = high_mesh_cache.export_legacy_high_mesh_ref(obj, depsgraph)
        opacity_binding = None
        if opacity_by_object:
            try:
                object_key = int(obj.as_pointer())
            except Exception:
                object_key = id(obj)
            opacity_binding = opacity_by_object.get(object_key)
        if opacity_binding:
            ref.opacity_image_path = str(opacity_binding.get("image_path", "") or "")
            ref.opacity_constant = float(opacity_binding.get("constant", 1.0))
            ref.opacity_address_mode = str(opacity_binding.get("address", "REPEAT") or "REPEAT")
            ref.opacity_filter = str(opacity_binding.get("filter", "LINEAR") or "LINEAR")
        return ref

    for index, slot in enumerate(high_slots):
        obj = slot.object_ref
        if not floater_faces.has_floater_faces(obj):
            high_meshes.append(_export_one(index, obj))
            continue
        # Marked floater faces (floater_faces.py): the body under the object's own name,
        # then the marked faces as "<object>__fyr_floater", which bakes with Casts AO off.
        if floater_faces.marked_face_count(obj) < mesh_read.element_count(obj.data, "polygons"):
            with floater_faces.export_part(obj, floater_faces.PART_BODY):
                high_meshes.append(_export_one(index, obj))
        with floater_faces.export_part(obj, floater_faces.PART_FLOATER):
            floater_ref = _export_one(index, obj, "_floater")
        floater_name = floater_faces.floater_object_name(obj.name)
        high_meshes.append(
            replace(floater_ref, name=naming.sanitize_token(floater_name), object_name=floater_name)
        )
    return high_meshes


#: Cage-fit warnings raised while building one job's cages. The fit runs deep inside the
#: export, far from any operator, so the message has nowhere to be reported from; parking it
#: here lets :func:`apply_progress_to_project` fold it into the bake's own warning list, which
#: is what the UI already shows. Filled by :func:`_report_cage_fit_diagnostics`, reset per job
#: by :func:`prepare_bake_job`, and emptied by :func:`drain_cage_fit_warnings`.
_CAGE_FIT_WARNINGS: list[str] = []


def reset_cage_fit_warnings() -> None:
    _CAGE_FIT_WARNINGS.clear()


def pending_cage_fit_warnings() -> list[str]:
    """The job's cage warnings so far. Deliberately NOT destructive.

    Both progress-application passes run repeatedly across one bake, each with a freshly
    read progress object, and each overwrites ``project.last_warning_*``. Handing the
    warnings out once (a drain) meant the first pass consumed them and every later pass
    reset the count back to zero, so the warning reached nothing. They are cleared per job
    by :func:`prepare_bake_job` instead, so whichever pass writes the fields last still
    sees them.
    """
    return list(_CAGE_FIT_WARNINGS)


def _merge_cage_fit_warnings(progress) -> None:
    """Fold this job's cage warnings into ``progress`` without duplicating them."""
    pending = pending_cage_fit_warnings()
    if not pending:
        return
    existing = list(getattr(progress, "warnings", None) or [])
    existing.extend(warning for warning in pending if warning not in existing)
    progress.warnings = existing


#: Share of a group's ray samples still short after the fit above which the bake warns.
#: Measured 2026-10-27 on 13 real projects: every part left short (up to 1.1%, a customer
#: gun's Box) baked the same as Distance references there, so a lower line only raised
#: false alarms. 2% keeps the warning for a cage that is clearly not covering.
_CAGE_SHORT_WARN_FRACTION = 0.02


def _report_cage_fit_diagnostics(group, diagnostics: dict) -> None:
    """Say out loud when the automatic cage fit had to clamp a cross-part reach.

    The clamp keeps a mis-bound high vertex from ballooning a patch of cage, but the mis-binding
    itself is a scene-setup problem the artist has to resolve -- parts nested closer to each
    other than to their own high. Silently clamping and baking anyway is how this ends up being
    diagnosed from a screenshot.
    """
    samples = int(diagnostics.get("ray_samples", 0) or 0)
    short = int(diagnostics.get("ray_short_samples", 0) or 0)
    if samples and short / samples > _CAGE_SHORT_WARN_FRACTION:
        # The fit checks its cage against the bake's own rays and widens it where they fall
        # short; whatever is left means high detail sits farther out than the cage can
        # safely reach. Say so before the bake instead of leaving it to a stray texel.
        message = (
            f"Bake group '{getattr(group, 'name', '')}': the automatic cage still falls short on "
            f"{100.0 * short / samples:.2f}% of its surface, where the high poly sits far outside "
            f"the low. Check those spots with Show Cage Coverage, or use a Distance Based or "
            f"Custom cage for this group."
        )
        print(f"[MasterBaker] {message}")
        _CAGE_FIT_WARNINGS.append(message)
    clamped = diagnostics.get("clamped_objects") or {}
    if not clamped:
        return
    worst = sorted(clamped.items(), key=lambda item: item[1]["peak"], reverse=True)
    names = ", ".join(name for name, _ in worst[:4])
    if len(worst) > 4:
        names += f", +{len(worst) - 4} more"
    message = (
        f"Bake group '{getattr(group, 'name', '')}': the automatic cage was clamped on "
        f"{int(diagnostics.get('clamped_vertices', 0))} cage vertices across {len(worst)} mesh(es) "
        f"({names}). High-poly detail is binding to a neighbouring low mesh, which means those "
        f"meshes sit closer to each other than to their own high. Turn on Match By Mesh Name "
        f"(Cage settings), split them into separate bake groups, or switch to a Distance Based cage."
    )
    print(f"[MasterBaker] {message}")
    _CAGE_FIT_WARNINGS.append(message)


#: Fitted automatic-cage offsets by group geometry, so the bake reuses a fit the
#: step-by-step prefit (prefit_automatic_cage) already made behind a progress card.
_AUTO_CAGE_OFFSETS: dict = {}
_AUTO_CAGE_OFFSETS_ORDER: list = []
_AUTO_CAGE_OFFSETS_MAX = 256


def _automatic_cage_fit_key(low_signature, high_signature, uv_layer_name, smooth_normals, match_by_isolation):
    return (
        "AUTO_CAGE_OFFSETS_V10",
        low_signature,
        high_signature,
        str(uv_layer_name or ""),
        bool(smooth_normals),
        bool(match_by_isolation),
    )


def _automatic_cage_offsets(
    group, depsgraph, low_triangle_groups, high_objs, *, fit_key, match_by_isolation, low_objs, smooth_normals
):
    """(offsets, diagnostics) for one group's automatic cage, memoized by ``fit_key``, and
    shared with the viewport preview through cage_fit_store (the preview usually fitted it
    already, so the bake does not fit again)."""
    cached = _AUTO_CAGE_OFFSETS.get(fit_key)
    if cached is not None:
        return cached
    ahead = _FIT_AHEAD
    if ahead is not None:
        started = ahead.take(fit_key)
        if started is not None:
            _remember_automatic_cage_offsets(fit_key, started)
            return started

    def _fit():
        high_source_data = []
        high_object_names = []
        for high_obj in high_objs:
            captured = cage.capture_high_mesh_fit_source_data(high_obj, depsgraph)
            if captured is not None:
                high_source_data.append(captured)
                high_object_names.append(str(getattr(high_obj, "name", "")))
        if not high_source_data:
            return None
        diagnostics: dict = {}
        offsets = cage.build_group_coverage_offsets(
            low_triangle_groups,
            high_source_data,
            high_object_names=high_object_names,
            match_by_isolation=match_by_isolation,
            diagnostics=diagnostics,
            high_surface_index=cage.get_or_build_fit_high_index(high_objs, depsgraph),
        )
        return offsets, diagnostics

    result = cage_fit_store.get_or_fit(
        cage_fit_store.content_key(
            low_objs, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
        ),
        _fit,
    )
    if result is None:
        return None
    _remember_automatic_cage_offsets(fit_key, result)
    return result


def _remember_automatic_cage_offsets(fit_key, result) -> None:
    _AUTO_CAGE_OFFSETS[fit_key] = result
    _AUTO_CAGE_OFFSETS_ORDER.append(fit_key)
    while len(_AUTO_CAGE_OFFSETS_ORDER) > _AUTO_CAGE_OFFSETS_MAX:
        _AUTO_CAGE_OFFSETS.pop(_AUTO_CAGE_OFFSETS_ORDER.pop(0), None)


def _automatic_cage_inputs(group):
    with low_material_subset.group_scope(group):
        return _automatic_cage_inputs_in_scope(group)


def _automatic_cage_inputs_in_scope(group):
    """(projection_state, high_objs, fit_key) for an Automatic group, or None. Cheap: signatures only."""
    projection_state = _group_projection_settings_state(group)
    if str(getattr(projection_state, "cage_mode", "") or "") != constants.CAGE_MODE_AUTOMATIC:
        return None
    high_objs = [slot.object_ref for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group))]
    lows = [slot.object_ref for slot in _iter_bakeable_low_slots(group.low_meshes)]
    if not high_objs or not lows:
        return None
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
    fit_key = _automatic_cage_fit_key(
        tuple(_object_signature(obj) for obj in lows),
        tuple(_object_signature(obj) for obj in high_objs),
        uv_layer_name,
        cage.auto_cage_uses_average_normals(projection_state),
        bool(getattr(projection_state, "match_by_isolation", False)),
    )
    return projection_state, high_objs, fit_key


class _CageFitAhead:
    """Starts the Automatic cage fits of the next few groups while the job build works on
    the current one.

    A fit is the plain coverage fit (reads Blender data, stays on the main thread, done here a
    few groups early) and the ray reach check (touches no Blender data; most of the fit, and
    mostly waiting on ``fyr_cage_gpu.exe``). The check runs on one worker thread, so the main
    thread builds the meshes and cages of the groups in front of it meanwhile. Same
    computation, same inputs, same order of effects as the inline fit: the result reaches
    ``_automatic_cage_offsets`` through :meth:`take`, which stores it as the inline fit would,
    and any failure here just leaves the group to the inline fit."""

    WINDOW = 6

    def __init__(self, groups, depsgraph):
        self._groups = list(groups)
        self._depsgraph = depsgraph
        self._next = 0
        self._pending: dict = {}
        self._captured: dict = {}
        self._executor = None
        self._failed = False
        self._memo_keys: dict = {}

    def memo_key(self, fit_key, lows, highs):
        """The cage payload memo key of ``fit_key``, built once per group: the start of the fit
        and the cage export of the same group ask for the same key."""
        if fit_key not in self._memo_keys:
            self._memo_keys[fit_key] = _cage_payload_memo_key(fit_key, lows, highs)
        return self._memo_keys[fit_key]

    def captured_triangles(self, fit_key, lows):
        """The source triangles captured for ``fit_key`` (one list per entry of ``lows``), once,
        or None when this group was not captured here."""
        entries = self._captured.pop(fit_key, None)
        if entries is None or len(entries) != len(lows):
            return None
        if any(name != str(getattr(obj, "name", "")) for (name, _triangles), obj in zip(entries, lows)):
            return None
        return [triangles for _name, triangles in entries]

    def _start(self, group) -> None:
        with low_material_subset.group_scope(group):
            self._start_in_scope(group)

    def advance(self, position: int) -> None:
        """Start fits for the group at ``position`` and the ``WINDOW`` groups after it."""
        if self._failed:
            return
        try:
            target = min(len(self._groups), position + 1 + self.WINDOW)
            while self._next < target:
                group = self._groups[self._next]
                self._next += 1
                self._start(group)
        except Exception:
            self._failed = True

    def _start_in_scope(self, group) -> None:
        import concurrent.futures

        inputs = _automatic_cage_inputs(group)
        if inputs is None:
            return
        projection_state, high_objs, fit_key = inputs
        if fit_key in _AUTO_CAGE_OFFSETS or fit_key in self._pending:
            return
        uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
        smooth_normals = cage.auto_cage_uses_average_normals(projection_state)
        match_by_isolation = bool(getattr(projection_state, "match_by_isolation", False))
        all_lows = [slot.object_ref for slot in _iter_bakeable_low_slots(group.low_meshes)]
        memo_key = self.memo_key(fit_key, all_lows, high_objs)
        if _cage_payload_memo_get(memo_key) is not None:
            return  # the cage itself is remembered: no fit is needed
        depsgraph = self._depsgraph
        low_triangle_groups = []
        low_objs = []
        captured_by_index = []
        for obj in all_lows:
            triangles = cage.capture_cage_source_triangles(
                obj, depsgraph, smooth_normals=smooth_normals, uv_layer_name=uv_layer_name, as_soup=True
            )
            captured_by_index.append((str(getattr(obj, "name", "")), triangles))
            if triangles:
                low_triangle_groups.append(triangles)
                low_objs.append(obj)
        # The job build reads these same triangles next (see captured_triangles): one capture
        # per low, not two. Held for the few groups in flight only.
        self._captured[fit_key] = captured_by_index
        if not low_triangle_groups:
            return
        content_key = cage_fit_store.content_key(
            low_objs, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
        )
        stored = cage_fit_store.cached(content_key)
        if stored is not None:
            _remember_automatic_cage_offsets(fit_key, stored)
            return
        high_source_data = []
        high_object_names = []
        for high_obj in high_objs:
            captured = cage.capture_high_mesh_fit_source_data(high_obj, depsgraph)
            if captured is not None:
                high_source_data.append(captured)
                high_object_names.append(str(getattr(high_obj, "name", "")))
        if not high_source_data:
            return
        diagnostics: dict = {}
        # build_group_coverage_offsets without the index is the plain fit alone; the ray check
        # it would have run next is the worker's job below.
        offsets = cage.build_group_coverage_offsets(
            low_triangle_groups,
            high_source_data,
            high_object_names=high_object_names,
            match_by_isolation=match_by_isolation,
            diagnostics=diagnostics,
        )
        index = cage.get_or_build_fit_high_index(high_objs, depsgraph)
        triangles = cage_soup.flatten(low_triangle_groups)
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="fyr-cage-ray")

        def _ray_check():
            if offsets and index and cage.RAY_REACH_CHECK:
                raised = cage.raise_offsets_to_ray_reach(triangles, offsets, index, diagnostics=diagnostics)
                if diagnostics is not None and raised:
                    diagnostics["ray_raised_vertices"] = int(diagnostics.get("ray_raised_vertices", 0)) + raised
            return offsets, diagnostics

        self._pending[fit_key] = (self._executor.submit(_ray_check), content_key)

    def take(self, fit_key):
        """The finished fit for ``fit_key`` (stored like an inline fit), or None."""
        entry = self._pending.pop(fit_key, None)
        if entry is None:
            return None
        future, content_key = entry
        try:
            value = future.result()
        except BaseException:
            return None
        if value is None:
            return None
        offsets, _diagnostics = value
        if content_key is not None and offsets:
            cage_fit_store.put(content_key, value)
        return value

    def close(self) -> None:
        executor, self._executor = self._executor, None
        self._pending.clear()
        self._captured.clear()
        self._memo_keys.clear()
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)


#: The fit-ahead of the job build in progress (see _CageFitAhead), else None.
_FIT_AHEAD: "_CageFitAhead | None" = None


def automatic_cage_groups_to_fit(project, group_names=None) -> list:
    """The Automatic groups (of ``group_names``, or all) whose bake cage is not fitted yet."""
    wanted = set(group_names or ())
    pending = []
    for group in getattr(project, "groups", []) or []:
        if wanted and str(getattr(group, "name", "") or "") not in wanted:
            continue
        try:
            inputs = _automatic_cage_inputs(group)
        except Exception:
            continue
        if inputs is not None and inputs[2] not in _AUTO_CAGE_OFFSETS:
            pending.append(group)
    return pending


def begin_cage_tree_pool(groups) -> None:
    """Share high-mesh BVH trees between the ``groups`` about to be prefitted (see
    cage.begin_high_tree_pool). Pair with :func:`end_cage_tree_pool`."""
    try:
        cage.begin_high_tree_pool(
            [[slot.object_ref for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group))] for group in groups]
        )
    except Exception:
        cage.end_high_tree_pool()


def end_cage_tree_pool() -> None:
    cage.end_high_tree_pool()
    # The fits are done and the bake starts next: hand the cage tool's VRAM back to the bake worker.
    try:
        from . import cage_gpu

        cage_gpu.release_gpu_memory()
    except Exception:
        pass


def prefit_automatic_cage(group, depsgraph) -> None:
    with low_material_subset.group_scope(group):
        _prefit_automatic_cage_in_scope(group, depsgraph)


def _prefit_automatic_cage_in_scope(group, depsgraph) -> None:
    """Fit ``group``'s bake cage now, so the export that follows reuses it."""
    inputs = _automatic_cage_inputs(group)
    if inputs is None:
        return
    projection_state, high_objs, fit_key = inputs
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
    smooth_normals = cage.auto_cage_uses_average_normals(projection_state)
    match_by_isolation = bool(getattr(projection_state, "match_by_isolation", False))
    # A stored fit needs no triangles: capturing every low mesh just to find the fit
    # already there was all of a warm prefit (27 ms a group, 1.7 s on a 73-group gun). The
    # key over every bakeable low equals the fit's own key whenever no low captures empty,
    # and a stored fit exists only if none did (emptiness follows from the hashed content).
    try:
        all_lows = [slot.object_ref for slot in _iter_bakeable_low_slots(group.low_meshes)]
        stored_key = cage_fit_store.content_key(
            all_lows, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
        )
        stored = cage_fit_store.cached(stored_key)
    except Exception:
        stored = None
    if stored is not None:
        _remember_automatic_cage_offsets(fit_key, stored)
        return
    low_triangle_groups = []
    low_objs = []
    for slot in _iter_bakeable_low_slots(group.low_meshes):
        triangles = cage.capture_cage_source_triangles(
            slot.object_ref, depsgraph, smooth_normals=smooth_normals, uv_layer_name=uv_layer_name
        )
        if triangles:
            low_triangle_groups.append(triangles)
            low_objs.append(slot.object_ref)
    if not low_triangle_groups:
        return
    _automatic_cage_offsets(
        group,
        depsgraph,
        low_triangle_groups,
        high_objs,
        fit_key=fit_key,
        match_by_isolation=bool(getattr(projection_state, "match_by_isolation", False)),
        low_objs=low_objs,
        smooth_normals=smooth_normals,
    )


#: Timing of the last prefit_automatic_cages_batch call (seconds), for harnesses and the log.
LAST_BATCH_TIMING: dict = {}


def prefit_automatic_cages_batch(groups, depsgraph) -> bool:
    """Fit every Automatic group in ``groups`` with ONE batched GPU ray-check request.

    Per group the plain coverage fit still runs here (it is already numpy plus one GPU pass); the
    ray check, which was two thirds of a cold fit, runs natively in ``fyr_cage_gpu.exe`` for all
    groups in a single call, with each high loaded once and kept resident. The highs are read from
    the ``.fymesh`` files the bake itself uses (exported now if the prewarm has not yet), so nothing
    is exported twice. Groups the GPU path cannot serve fall back to :func:`prefit_automatic_cage`.
    Returns False when the batch path is unavailable (the caller fits group by group)."""
    from . import cage_gpu, cage_gpu_fit

    if not (cage_gpu_fit.available() and cage_gpu_fit.native_enabled() and cage.RAY_REACH_CHECK):
        return False
    started = time.perf_counter()
    timing = {"plain_s": 0.0, "export_s": 0.0, "prepare_s": 0.0, "request_s": 0.0, "apply_s": 0.0, "groups": 0, "fallback": 0, "cover_s": 0.0}
    pending = []  # (group, fit_key, store_key, offsets, diagnostics, prepared)
    native_cover = []  # groups whose plain coverage fit runs in the tool (see below)
    use_native_cover = cage_gpu_fit.coverage_enabled()
    for group in groups:
        if low_material_subset.group_material_name(group):
            # The batch below reads whole objects; a restricted group fits on its own.
            prefit_automatic_cage(group, depsgraph)
            continue
        inputs = _automatic_cage_inputs(group)
        if inputs is None:
            continue
        projection_state, high_objs, fit_key = inputs
        if fit_key in _AUTO_CAGE_OFFSETS:
            continue
        uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
        smooth_normals = cage.auto_cage_uses_average_normals(projection_state)
        match_by_isolation = bool(getattr(projection_state, "match_by_isolation", False))
        try:
            all_lows = [slot.object_ref for slot in _iter_bakeable_low_slots(group.low_meshes)]
            stored = cage_fit_store.cached(
                cage_fit_store.content_key(
                    all_lows, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
                )
            )
        except Exception:
            stored = None
        if stored is not None:
            _remember_automatic_cage_offsets(fit_key, stored)
            continue
        low_triangle_groups = []
        low_objs = []
        for slot in _iter_bakeable_low_slots(group.low_meshes):
            triangles = cage.capture_cage_source_triangles(
                slot.object_ref, depsgraph, smooth_normals=smooth_normals, uv_layer_name=uv_layer_name
            )
            if triangles:
                low_triangle_groups.append(triangles)
                low_objs.append(slot.object_ref)
        if not low_triangle_groups:
            continue
        t0 = time.perf_counter()
        index = cage.get_or_build_fit_high_index(high_objs, depsgraph)  # exports a missing .fymesh
        timing["export_s"] += time.perf_counter() - t0
        if not isinstance(index, cage_gpu_fit.GpuHighIndex):
            timing["fallback"] += 1
            prefit_automatic_cage(group, depsgraph)
            continue
        try:  # the tool builds this high's scene now, while the plain fits below run
            cage_gpu.shared_worker().preload([index.entries])
        except Exception:
            pass
        if use_native_cover:
            # The plain coverage fit binds every high vertex to its nearest low face in the tool, from
            # the same .fymesh files the ray check traces: no Blender mesh copy of the highs, no
            # per-group GPU upload of them from Python.
            t0 = time.perf_counter()
            flat = [triangle for triangles in low_triangle_groups for triangle in triangles]
            arrays = cage_gpu_fit.prepare_arrays(flat)
            if arrays is None:
                continue
            diagnostics: dict = {}
            partitions = cage_gpu_fit.coverage_partitions(
                low_triangle_groups, index, match_by_isolation=match_by_isolation, diagnostics=diagnostics
            )
            unique_keys = cage_gpu_fit.unique_keys_of(arrays, flat)
            store_key = cage_fit_store.content_key(
                low_objs, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
            )
            native_cover.append(
                {
                    "group": group,
                    "fit_key": fit_key,
                    "store_key": store_key,
                    "arrays": arrays,
                    "partitions": partitions,
                    "unique_keys": unique_keys,
                    "diagnostics": diagnostics,
                    "index": index,
                    "items": cage_gpu_fit.coverage_items(arrays, partitions, index),
                }
            )
            timing["prepare_s"] += time.perf_counter() - t0
            continue
        t0 = time.perf_counter()
        high_source_data = []
        high_object_names = []
        for high_obj in high_objs:
            captured = cage.capture_high_mesh_fit_source_data(high_obj, depsgraph)
            if captured is not None:
                high_source_data.append(captured)
                high_object_names.append(str(getattr(high_obj, "name", "")))
        if not high_source_data:
            continue
        diagnostics: dict = {}
        offsets = cage.build_group_coverage_offsets(
            low_triangle_groups,
            high_source_data,
            high_object_names=high_object_names,
            match_by_isolation=match_by_isolation,
            diagnostics=diagnostics,
            high_surface_index=None,
        )
        timing["plain_s"] += time.perf_counter() - t0
        t0 = time.perf_counter()
        flat = [triangle for triangles in low_triangle_groups for triangle in triangles]
        prepared = cage_gpu_fit.prepare_fit_job(flat, offsets, index)
        timing["prepare_s"] += time.perf_counter() - t0
        store_key = cage_fit_store.content_key(
            low_objs, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation
        )
        pending.append((group, fit_key, store_key, offsets, diagnostics, prepared))
    worker = cage_gpu.shared_worker()
    if native_cover:
        t0 = time.perf_counter()
        items = [item for entry in native_cover for item in entry["items"]]
        try:
            cover_results = worker.coverage_batch(items)
        except Exception as error:
            cage_gpu_fit.disable(f"{type(error).__name__}: {error}")
            for entry in native_cover:
                prefit_automatic_cage(entry["group"], depsgraph)
            for item in pending:
                prefit_automatic_cage(item[0], depsgraph)
            return True
        timing["cover_s"] = time.perf_counter() - t0
        timing["cover_gather_s"] = sum(r["gather_ms"] for r in cover_results) / 1000.0
        timing["cover_gpu_s"] = sum(r["gpu_ms"] for r in cover_results) / 1000.0
        t0 = time.perf_counter()
        cursor = 0
        for entry in native_cover:
            count = len(entry["items"])
            results = cover_results[cursor : cursor + count]
            cursor += count
            fitted = cage_gpu_fit.finish_coverage(
                entry["arrays"], entry["unique_keys"], entry["partitions"], results, diagnostics=entry["diagnostics"]
            )
            offsets = dict(zip(entry["unique_keys"], fitted.tolist()))
            job = cage_gpu_fit.fit_job_from_arrays(entry["arrays"], fitted, entry["index"])
            prepared = (job, entry["unique_keys"]) if job is not None else None
            pending.append(
                (entry["group"], entry["fit_key"], entry["store_key"], offsets, entry["diagnostics"], prepared)
            )
        timing["prepare_s"] += time.perf_counter() - t0
    jobs = [item[5][0] for item in pending if item[5] is not None]
    results = []
    if jobs:
        t0 = time.perf_counter()
        try:
            results = worker.fit_batch(jobs)
        except Exception as error:
            cage_gpu_fit.disable(f"{type(error).__name__}: {error}")
            for item in pending:
                prefit_automatic_cage(item[0], depsgraph)
            return True
        timing["request_s"] = time.perf_counter() - t0
        timing["load_s"] = sum(r["load_ms"] for r in results) / 1000.0
        timing["fit_s"] = sum(r["fit_ms"] for r in results) / 1000.0
    t0 = time.perf_counter()
    result_iter = iter(results)
    for group, fit_key, store_key, offsets, diagnostics, prepared in pending:
        if prepared is not None:
            job, unique_keys = prepared
            cage_gpu_fit.apply_fit_result(offsets, unique_keys, job, next(result_iter), diagnostics)
        value = (offsets, diagnostics)
        cage_fit_store.put(store_key, value)
        _remember_automatic_cage_offsets(fit_key, value)
        timing["groups"] += 1
    timing["apply_s"] = time.perf_counter() - t0
    timing["total_s"] = time.perf_counter() - started
    LAST_BATCH_TIMING.clear()
    LAST_BATCH_TIMING.update(timing)
    if os.environ.get("FYR_CAGE_TIMING"):
        print("[MasterBaker] cage batch timing: " + ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in timing.items()))
    return True


#: Cage payloads of Automatic groups built earlier this session, so a rebake of an unchanged
#: group skips the triangle capture, the offsets and the payload build (about half of a warm
#: 300-group prepare) and only writes the file. Keyed by everything the cage reads: the fit
#: key (object signatures of every low and high, UV layer, switches), the fit version, the
#: depsgraph revision of every object (UV and paint edits move no signature term) and a
#: checksum of the lows' UV layers. In memory, bounded by bytes.
_CAGE_PAYLOAD_MEMO: "collections.OrderedDict" = collections.OrderedDict()
_CAGE_PAYLOAD_MEMO_BYTES = 0
_CAGE_PAYLOAD_MEMO_MAX_BYTES = 96 * 1024 * 1024


def _uv_layers_fingerprint(obj):
    """Names and checksum of every UV layer of ``obj``'s mesh."""
    import zlib

    import numpy as np

    data = getattr(obj, "data", None)
    layers = getattr(data, "uv_layers", None)
    if layers is None:
        return ()
    crc = 0
    names = []
    for layer in layers:
        values = layer.data
        buffer = np.empty(len(values) * 2, dtype=np.float32)
        values.foreach_get("uv", buffer)
        crc = zlib.crc32(memoryview(buffer).cast("B"), crc)
        names.append(str(getattr(layer, "name", "")))
    return (tuple(names), crc)


def _cage_payload_memo_key(fit_key, lows, highs):
    try:
        import sys

        # The add-on imports overlay_keys at start-up (its depsgraph handler stamps the
        # revisions read here); never import it from here, so a host without it just does
        # not remember cages.
        overlay_keys = sys.modules.get(f"{__package__}.overlay_keys")
        if overlay_keys is None:
            return None
        object_revision_signature = overlay_keys.object_revision_signature

        low_revisions = tuple(object_revision_signature(obj) for obj in lows)
        high_revisions = tuple(object_revision_signature(obj) for obj in highs)
        uv_fingerprints = tuple(_uv_layers_fingerprint(obj) for obj in lows)
        # Last: the fit version probes the GPU fit tool, which a key that cannot be built
        # (an object without a signature) has no reason to start.
        return (
            "AUTO_CAGE_PAYLOAD_V1",
            cage_fit_store.fit_version(),
            fit_key,
            low_revisions,
            high_revisions,
            uv_fingerprints,
        )
    except Exception:
        return None


def _cage_payload_memo_get(key):
    if key is None:
        return None
    entry = _CAGE_PAYLOAD_MEMO.get(key)
    if entry is None:
        return None
    _CAGE_PAYLOAD_MEMO.move_to_end(key)
    return entry[0], entry[1]


def _cage_payload_memo_put(key, entries, diagnostics) -> None:
    global _CAGE_PAYLOAD_MEMO_BYTES
    size = sum(len(payload) for _index, _name, payload in entries)
    if size > _CAGE_PAYLOAD_MEMO_MAX_BYTES // 4:
        return
    previous = _CAGE_PAYLOAD_MEMO.pop(key, None)
    if previous is not None:
        _CAGE_PAYLOAD_MEMO_BYTES -= previous[2]
    _CAGE_PAYLOAD_MEMO[key] = (entries, diagnostics, size)
    _CAGE_PAYLOAD_MEMO_BYTES += size
    while _CAGE_PAYLOAD_MEMO_BYTES > _CAGE_PAYLOAD_MEMO_MAX_BYTES and _CAGE_PAYLOAD_MEMO:
        _evicted_key, evicted = _CAGE_PAYLOAD_MEMO.popitem(last=False)
        _CAGE_PAYLOAD_MEMO_BYTES -= evicted[2]


def _export_cage_mesh_refs(group, *args, **kwargs) -> list[protocol.ExportedMeshRef]:
    with low_material_subset.group_scope(group):
        return _export_cage_mesh_refs_in_scope(group, *args, **kwargs)


def _export_cage_mesh_refs_in_scope(
    group,
    depsgraph,
    group_root: Path,
    *,
    high_mesh_refs: list[protocol.ExportedMeshRef] | None = None,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> list[protocol.ExportedMeshRef]:
    cage_meshes: list[protocol.ExportedMeshRef] = []
    projection_state = _group_projection_settings_state(group)
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None

    if projection_state.cage_mode == constants.CAGE_MODE_CUSTOM:
        if projection_state.custom_cage is None:
            raise ValueError(f"Bake group '{group.name}' is set to Custom cage but no custom cage object is assigned")
        only_material = low_material_subset.group_material_name(group)
        if only_material and not low_material_subset.has_faces(projection_state.custom_cage, only_material):
            raise ValueError(
                f"Bake group '{group.name}' bakes the material '{only_material}', but its custom cage "
                f"'{projection_state.custom_cage.name}' has no faces with that material"
            )
        with low_material_subset.object_scope([projection_state.custom_cage], only_material):
            ref = write_evaluated_obj(
                projection_state.custom_cage,
                depsgraph,
                group_root / f"cage_{naming.sanitize_token(projection_state.custom_cage.name)}.fymesh",
                uv_layer_name=uv_layer_name,
                workspace_key=workspace_key,
                use_shared_memory=use_shared_memory,
            )
        ref.role = constants.OBJECT_ROLE_CAGE
        cage_meshes.append(ref)
        return cage_meshes

    if projection_state.cage_mode == constants.CAGE_MODE_AUTOMATIC:
        # Export the reverse-mapped coverage cage directly (cage.build_coverage_offsets): each low
        # vertex's cage distance is the farthest the high detail extends outward there, so every
        # high-poly point falls inside the cage's ray-reach envelope -> 100% bake coverage, and the
        # baked cage is byte-for-byte the same fit the viewport overlay draws. (Previously left empty
        # for the backend to synthesize; that path used a nearest-surface fit that under-reached at
        # mid-face protrusions and disagreed with the preview.)
        smooth_normals = cage.auto_cage_uses_average_normals(projection_state)
        # Match By Isolation restricts the backend's projection rays to the name-matched high
        # (find_isolation_source_name); the fit has to partition the same way or the cage it
        # builds is not the cage those rays are allowed to use. Names stay index-parallel with
        # high_source_data so the fit can pair them.
        match_by_isolation = bool(getattr(projection_state, "match_by_isolation", False))
        high_objs = [slot.object_ref for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group))]
        if not high_objs:
            return cage_meshes
        # _object_signature() returns a tuple, not a string, so these can't be
        # str.join()'d (that raised "sequence item 0: expected str instance,
        # tuple found" on the first AUTOMATIC-cage bake). _signature_cache_key
        # repr()s whatever it's handed, so a tuple of signatures keys the cache
        # just as well.
        high_signature = tuple(_object_signature(obj) for obj in high_objs)
        # Fit all of the group's low meshes together so no low mesh balloons out to reach another
        # mesh's high detail (e.g. the lower-teeth cage inflating up into the upper teeth). Each high
        # vertex then maps to its globally nearest low face. Because a low object's fit now depends on
        # its siblings, the per-object cache key folds in the whole group's low signature.
        all_lows = [slot.object_ref for slot in _iter_bakeable_low_slots(group.low_meshes)]
        # The low signatures are the same terms the capture loop always computed, taken
        # first so a group whose cage was built before (a rebake) is answered from memory.
        all_low_signatures = [_object_signature(obj) for obj in all_lows]
        low_signature = tuple(all_low_signatures)
        fit_key = _automatic_cage_fit_key(low_signature, high_signature, uv_layer_name, smooth_normals, match_by_isolation)

        def _cage_cache_key(index, obj):
            return _signature_cache_key(
                # V11: ray-check raises scale the plain fit, not the current offsets
                # (2026-10-28). V10: the GPU fit readback fix, the collapsed-blend guard and the ray
                # reach check (2026-10-27). V9: Smooth Cage off bridges by smooth fans (backend v16). V8: Smooth
                # Cage off bridges convex hard edges (backend v15). V7: the
                # fit clamps cross-part reach outliers and partitions by Match By
                # Isolation. Older entries are a different cage.
                "AUTO_CAGE_COVERAGE_V11",
                all_low_signatures[index],
                low_signature,
                high_signature,
                str(uv_layer_name or ""),
                bool(smooth_normals),
                bool(match_by_isolation),
            )

        memo_key = (
            _FIT_AHEAD.memo_key(fit_key, all_lows, high_objs)
            if _FIT_AHEAD is not None
            else _cage_payload_memo_key(fit_key, all_lows, high_objs)
        )
        memo = _cage_payload_memo_get(memo_key)
        if memo is not None:
            entries, memo_diagnostics = memo
            if all(
                index < len(all_lows) and getattr(all_lows[index], "name", None) == name
                for index, name, _payload in entries
            ):
                _report_cage_fit_diagnostics(group, memo_diagnostics)
                for index, _name, payload in entries:
                    obj = all_lows[index]
                    ref = cage.write_obj_from_payload(
                        object_name=f"{obj.name}_auto_cage",
                        payload=payload,
                        destination=group_root / f"cage_auto_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
                        world_to_object=_world_to_object_matrix_values(obj),
                        cache_key=_cage_cache_key(index, obj),
                        workspace_key=workspace_key,
                        use_shared_memory=use_shared_memory,
                    )
                    ref.role = constants.OBJECT_ROLE_CAGE
                    cage_meshes.append(ref)
                return cage_meshes

        ahead_triangles = _FIT_AHEAD.captured_triangles(fit_key, all_lows) if _FIT_AHEAD is not None else None
        low_entries = []  # (index, obj, source_triangles)
        for index, obj in enumerate(all_lows):
            source_triangles = (
                ahead_triangles[index]
                if ahead_triangles is not None
                else cage.capture_cage_source_triangles(
                    obj,
                    depsgraph,
                    smooth_normals=smooth_normals,
                    uv_layer_name=uv_layer_name,
                    as_soup=True,
                )
            )
            if not source_triangles:
                continue
            low_entries.append((index, obj, source_triangles))
        if not low_entries:
            return cage_meshes
        fitted = _automatic_cage_offsets(
            group,
            depsgraph,
            [source_triangles for _, _, source_triangles in low_entries],
            high_objs,
            fit_key=fit_key,
            match_by_isolation=match_by_isolation,
            low_objs=[obj for _, obj, _ in low_entries],
            smooth_normals=smooth_normals,
        )
        if fitted is None:
            return cage_meshes
        offsets, cage_fit_diagnostics = fitted
        _report_cage_fit_diagnostics(group, cage_fit_diagnostics)
        remembered = []
        for index, obj, source_triangles in low_entries:
            triangles = cage.offset_triangles_with_proximity_fit(source_triangles, offsets)
            payload_sink: list = []
            ref = cage.write_obj_from_triangles(
                object_name=f"{obj.name}_auto_cage",
                triangles=triangles,
                destination=group_root / f"cage_auto_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
                world_to_object=_world_to_object_matrix_values(obj),
                cache_key=_cage_cache_key(index, obj),
                workspace_key=workspace_key,
                use_shared_memory=use_shared_memory,
                payload_sink=payload_sink,
            )
            ref.role = constants.OBJECT_ROLE_CAGE
            cage_meshes.append(ref)
            remembered.append((index, str(getattr(obj, "name", "")), payload_sink[0] if len(payload_sink) == 1 else None))
        if memo_key is not None and all(isinstance(payload, bytes) for _i, _n, payload in remembered):
            _cage_payload_memo_put(memo_key, tuple(remembered), cage_fit_diagnostics)
        return cage_meshes

    if projection_state.cage_mode == constants.CAGE_MODE_DISTANCE:
        return cage_meshes

    for index, slot in enumerate(_iter_bakeable_low_slots(group.low_meshes)):
        obj = slot.object_ref
        total_offset = max(0.0, float(projection_state.cage_offset) + _slot_cage_offset_delta(group, slot))
        smooth_normals = cage.auto_cage_uses_average_normals(projection_state)
        if smooth_normals:
            source_triangles = cage.capture_cage_source_triangles(
                obj,
                depsgraph,
                smooth_normals=True,
                uv_layer_name=uv_layer_name,
            )
            triangles = cage.offset_triangles_with_local_inflation(source_triangles, offset=total_offset)
        else:
            triangles = cage.capture_offset_triangles(
                obj,
                depsgraph,
                offset=total_offset,
                smooth_normals=False,
                uv_layer_name=uv_layer_name,
            )
        ref = cage.write_obj_from_triangles(
            object_name=f"{obj.name}_auto_cage",
            triangles=triangles,
            destination=group_root / f"cage_auto_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
            world_to_object=_world_to_object_matrix_values(obj),
            cache_key=_auto_cage_export_cache_key(
                obj,
                uv_layer_name=uv_layer_name,
                offset=total_offset,
                smooth_normals=smooth_normals,
            ),
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
        )
        ref.role = constants.OBJECT_ROLE_CAGE
        cage_meshes.append(ref)
    return cage_meshes


def _debug_overlay_cache_key(context, project, group) -> tuple:
    scene = getattr(context, "scene", None)
    return (
        scene.as_pointer() if scene is not None and hasattr(scene, "as_pointer") else 0,
        str(getattr(project, "name", "") or ""),
        str(getattr(group, "name", "") or ""),
    )


def _effective_ignore_backface(project, group=None) -> bool:
    if project is not None and hasattr(project, "ignore_backface"):
        return bool(getattr(project, "ignore_backface", False))
    if group is not None:
        return bool(getattr(_group_projection_settings_state(group), "ignore_backface", False))
    return False


def _debug_overlay_static_signature(group) -> tuple:
    projection_state = _group_projection_settings_state(group)
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip()
    custom_cage = getattr(projection_state, "custom_cage", None)
    return (
        str(getattr(group, "name", "") or ""),
        str(getattr(projection_state, "cage_mode", "") or ""),
        bool(getattr(projection_state, "average_normals", True)),
        uv_layer_name,
        _group_low_slot_signature(group),
        bool(properties.group_uses_low_as_high(group)),
        _slot_collection_signature(properties.effective_high_mesh_slots(group)),
        _object_signature(custom_cage) if custom_cage is not None else None,
    )


def _debug_overlay_dynamic_signature(project, group) -> tuple:
    projection_state = _group_projection_settings_state(group)
    return (
        str(getattr(projection_state, "cage_mode", "") or ""),
        round(float(getattr(projection_state, "cage_offset", 0.0)), 6),
        tuple(
            round(_slot_cage_offset_delta(group, slot), 6)
            for slot in _iter_bakeable_low_slots(getattr(group, "low_meshes", []))
        ),
        bool(getattr(projection_state, "average_normals", True)),
        _effective_ignore_backface(project, group),
    )


def debug_overlay_input_signature(project, group) -> tuple:
    return (
        _debug_overlay_static_signature(group),
        _debug_overlay_dynamic_signature(project, group),
    )


def _write_skew_correction_maps(group, directory: Path) -> list[protocol.SkewCorrectionMapRef]:
    """Write the group's painted Paint Skew correction (paint_sampling.skew_correction_tiles) as
    one raw little-endian float32 file per UDIM tile for the backend (MBBJOB37). Nothing is
    written, and nothing is sent, for an unpainted group, so its bake is unchanged."""
    import numpy as np

    try:
        tiles = paint_sampling.skew_correction_tiles(group) or {}
    except Exception:
        tiles = {}
    if not tiles:
        return []
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = hashlib.sha1(str(getattr(group, "name", "") or "").encode("utf-8")).hexdigest()[:12]
    refs: list[protocol.SkewCorrectionMapRef] = []
    for tile, entry in sorted(tiles.items()):
        width, height = int(entry[0]), int(entry[1])
        values = np.clip(np.asarray(entry[2], dtype=np.float32).reshape(height, width), 0.0, 1.0)
        path = directory / f"skew_correction_{stem}_{int(tile)}.f32"
        path.write_bytes(np.ascontiguousarray(values, dtype="<f4").tobytes())
        refs.append(protocol.SkewCorrectionMapRef(udim_tile=int(tile), path=str(path), width=width, height=height))
    return refs


def _exported_ao_non_casters(group, high_meshes) -> list[str]:
    """High meshes with Casts AO off, limited to the highs this job actually exports.

    A floater-faces piece (floater_faces.py) never casts AO.
    """
    exported = [str(getattr(ref, "object_name", "") or "") for ref in high_meshes or []]
    exported_names = set(exported)
    names = [name for name in properties.group_ao_non_caster_objects(group) if name in exported_names]
    for name in exported:
        if name != floater_faces.source_family(name) and name not in names:
            names.append(name)
    return names


def _build_group_config_from_exported_refs(project, group, low_meshes, high_meshes, cage_meshes) -> protocol.BakeGroupConfig:
    if not low_meshes:
        raise ValueError(f"Bake group '{group.name}' has no low meshes assigned")
    metadata_state = properties.group_metadata_state(group)
    projection_state = _group_projection_settings_state(group)
    paint_state = _group_paint_projection_settings_state(group)
    return protocol.BakeGroupConfig(
        name=group.name,
        low_material=low_material_subset.group_material_name(group),
        cage_mode=projection_state.cage_mode,
        cage_offset=float(projection_state.cage_offset),
        projection_rear_distance=max(0.0, float(getattr(projection_state, "projection_rear_distance", 0.0) or 0.0)),
        average_normals=bool(getattr(projection_state, "average_normals", True)),
        ignore_backface=_effective_ignore_backface(project, group),
        match_by_isolation=bool(getattr(projection_state, "match_by_isolation", False)),
        id_collection_name=(getattr(metadata_state, "id_collection_name", "") or "").strip(),
        id_color_set_name=(getattr(metadata_state, "id_color_set_name", "") or "").strip(),
        paint_offset_scale=float(getattr(paint_state, "paint_offset_scale", 1.0)),
        paint_skew=float(getattr(paint_state, "paint_skew", 0.0)),
        texture_set=(getattr(metadata_state, "texture_set_name", "") or "").strip(),
        low_meshes=list(low_meshes),
        high_meshes=list(high_meshes),
        cage_meshes=list(cage_meshes),
        ao_non_caster_objects=_exported_ao_non_casters(group, high_meshes),
        # A Bevel-shader high has SHARP corners (the bevel is shading), so the convex-edge
        # ray bridge has nothing to reach and only leans rays into neighbouring faces.
        straight_convex_rays=bool(_group_has_material_normal_detail(group)),
    )


def _material_target_path(output_targets, *, effective_type: str, map_uuid: str, tile_number: int, tokenized_naming: bool):
    """The output file one material ROW writes for one tile, or None.

    Matching on the effective map type alone was not enough: a full bake builds targets
    for every enabled row, and two rows of the same effective type -- two Custom rows,
    or two Albedo rows -- both took the first one. The second row then baked over the
    first row's file and its own file was never written, with no error.
    """
    wanted_uuid = str(map_uuid or "").strip()

    def _matches(target, *, require_uuid: bool) -> bool:
        if str(target.map_type or "").strip().upper() != effective_type:
            return False
        target_uuid = str(getattr(target, "map_uuid", "") or "").strip()
        if require_uuid and (not wanted_uuid or target_uuid != wanted_uuid):
            return False
        target_tile = int(getattr(target, "udim_tile", 0) or 0)
        if tokenized_naming and tile_number and target_tile and target_tile != tile_number:
            return False
        return True

    for require_uuid in (True, False):
        # The type-only pass is the fallback for targets built without a uuid; a row
        # whose uuid matched is always preferred.
        for target in output_targets:
            if _matches(target, require_uuid=require_uuid):
                return target.path
    return None


def _resolve_group_tile_plan(project, group, *, depsgraph=None, cache=None):
    """Resolve the UDIM tile plan for ``group``'s texture set.

    Returns ``(tile_specs, tokenized, diagnostics)``. ``tile_specs`` is always non-empty;
    ``tokenized`` says whether filenames carry a ``.NNNN`` suffix. A group not in a texture
    set, or one whose set resolves to plain tile 1001, yields a single untiled spec so the
    legacy single-tile path stays byte-for-byte identical.

    Occupancy is a union over every low mesh in the texture set, not just this group's, because
    all member groups composite into the same logical outputs. ``cache`` memoises that union
    per texture-set key for the duration of one job build -- without it a set with N member
    groups would walk its meshes N times.
    """
    from . import udim as _udim

    project_width = max(1, int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    project_height = max(1, int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    untiled = ([_udim.TileSpec(constants.UDIM_TILE_MIN, project_width, project_height)], False, [])

    metadata_state = properties.group_metadata_state(group)
    set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip()
    if not set_key:
        return untiled
    texture_set = properties.find_texture_set(project, set_key)
    if texture_set is None:
        return untiled

    if cache is not None and set_key in cache:
        return cache[set_key]

    diagnostics: list[str] = []
    detected: list[int] = []
    try:
        member_objects = _texture_set_low_objects(project, set_key)
        with low_material_subset.object_scope(member_objects, _texture_set_low_material(project, set_key)):
            detected, crossing_count, errors = _udim.detect_occupied_tiles(
                member_objects, depsgraph=depsgraph
            )
        diagnostics.extend(errors)
        if crossing_count:
            # Baked correctly into every tile it touches, but still an authoring defect: no
            # baker can make a border-crossing island filter seamlessly, because each UDIM
            # tile is an independently sampled texture downstream.
            diagnostics.append(
                f"Texture set '{set_key}': {crossing_count} triangle(s) cross a UDIM tile "
                "border. They will bake correctly into every tile they touch, but the seam "
                "cannot be filtered away downstream -- keep UV islands inside one tile."
            )
    except Exception as exc:  # pragma: no cover - Blender-only failure paths
        diagnostics.append(f"Texture set '{set_key}': UDIM detection failed ({exc})")

    specs, warnings = _udim.resolve_effective_tiles(
        texture_set, detected, project_width, project_height
    )
    diagnostics.extend(warnings)
    tokenized = _udim.uses_tokenized_naming(texture_set, specs)
    plan = (specs, tokenized, diagnostics)
    if cache is not None:
        cache[set_key] = plan
    return plan


def collect_udim_occupancy(project, depsgraph=None) -> dict:
    """``{texture set name: (tiles, crossing_count, errors)}`` for every set with low meshes.

    validation.validate_bake_project takes this as ``udim_occupancy``; without it the
    detected-occupancy rules (border-crossing triangles, occupied-but-excluded tiles,
    invalid UV tile space) are skipped as "occupancy unknown". Nothing passed it before,
    so Check never reported what the bake's own tile planner later flagged.
    """
    from . import udim as _udim

    occupancy: dict = {}
    for texture_set in getattr(project, "texture_sets", []) or ():
        set_key = str(getattr(texture_set, "name", "") or "").strip()
        if not set_key:
            continue
        try:
            objects = _texture_set_low_objects(project, set_key)
        except Exception:
            objects = []
        if not objects:
            continue
        try:
            with low_material_subset.object_scope(objects, _texture_set_low_material(project, set_key)):
                occupancy[set_key] = _udim.detect_occupied_tiles(objects, depsgraph=depsgraph)
        except Exception as exc:
            occupancy[set_key] = ((), 0, [f"UDIM detection failed ({exc})"])
    return occupancy


def _texture_set_low_objects(project, set_key: str) -> list:
    """Low-poly mesh objects across every bake group assigned to ``set_key``.

    Tile occupancy is a property of the whole texture set, so this spans member groups rather
    than reading one group's low collection. A group with no Fyr Low collection (a "Use My
    Collections" project) contributes its low slots instead.
    """
    from . import project_structure

    target = (set_key or "").strip().casefold()
    objects: list = []
    seen: set[str] = set()
    for group in getattr(project, "groups", []) or ():
        state = properties.group_metadata_state(group)
        if (getattr(state, "texture_set_name", "") or "").strip().casefold() != target:
            continue
        for obj in project_structure.group_low_mesh_objects(group):
            name = getattr(obj, "name", "")
            if name in seen:
                continue
            seen.add(name)
            objects.append(obj)
    return objects


def _texture_set_low_material(project, set_key) -> str:
    """The material every group of a texture set is restricted to, "" when they differ."""
    wanted = str(set_key or "").strip().casefold()
    names = {
        low_material_subset.group_material_name(group)
        for group in getattr(project, "groups", []) or []
        if (getattr(properties.group_metadata_state(group), "texture_set_name", "") or "").strip().casefold() == wanted
    }
    return next(iter(names)) if len(names) == 1 else ""


def group_occupied_tiles(group, *, depsgraph=None) -> set[int]:
    """The UDIM tiles this group's own lows touch. Empty when that cannot be told."""
    from . import project_structure, udim as _udim

    try:
        with low_material_subset.group_scope(group):
            tiles, _crossing, _errors = _udim.detect_occupied_tiles(
                project_structure.group_low_mesh_objects(group), depsgraph=depsgraph
            )
    except Exception:  # noqa: BLE001 - callers fall back to the whole set's tiles
        return set()
    return {int(tile) for tile in tiles}


def _prime_own_tile_plan(project, groups, *, depsgraph, cache) -> None:
    """Leave only the tiles the in-job groups occupy in each texture set's memoised plan.

    ``groups`` are the groups this job holds (one group is accepted too). For every texture
    set they belong to, the plan keeps the union of the tiles those groups' own lows touch.
    A pass that writes only some of a set's groups (a merge pass, a subset bake) has nothing
    to put on a tile only the other groups touch: those files stay as they are, and the pass
    does not spend a full-resolution projection on an empty tile. Untokenized sets, and a set
    whose occupancy cannot be told for every in-job group, keep the whole set's plan.
    """
    if not isinstance(groups, (list, tuple, set)):
        groups = [groups]
    members_by_set: dict[str, list] = {}
    for group in groups:
        set_key = (getattr(properties.group_metadata_state(group), "texture_set_name", "") or "").strip()
        if set_key:
            members_by_set.setdefault(set_key, []).append(group)
    for set_key, members in members_by_set.items():
        specs, tokenized, diagnostics = _resolve_group_tile_plan(project, members[0], depsgraph=depsgraph, cache=cache)
        if not tokenized:
            continue
        occupied: set[int] = set()
        for member in members:
            own = group_occupied_tiles(member, depsgraph=depsgraph)
            if not own:
                occupied = set()
                break
            occupied |= own
        own_specs = [spec for spec in specs if int(getattr(spec, "udim_tile", 0) or 0) in occupied]
        if own_specs:
            cache[set_key] = (own_specs, tokenized, diagnostics)


def _ao_bevel_normal_mode(item, bevel_present: bool) -> int:
    """The job index of an AO row's Use Bevel Normal option (0 = off).

    Auto is resolved here: a Bevel shader on the high normal becomes Convex Edges,
    everything else stays geometric. Off, Convex Edges and All Edges pass through.
    """
    resolved = bake_dependencies.resolve_ao_bevel_normal(item, bevel_present=bevel_present)
    return int(constants.AO_BEVEL_NORMAL_JOB_MODES.get(resolved, 0))


#: Job-workspace folder a source-only row writes to (see _build_output_targets
#: redirect_dirs). Output ingestion never registers a file from it.
SOURCE_ONLY_OUTPUT_DIR_NAME = "material_normal_source"


def _is_source_only_output(path) -> bool:
    try:
        parent = Path(str(path or "")).parent
        # Lit Color sources live in .fyr_baker/lit_color_sources/<project>/; the
        # composite they feed is what the artist gets (derived_outputs renames it in).
        return parent.name == SOURCE_ONLY_OUTPUT_DIR_NAME or parent.parent.name == derived_outputs.LIT_COLOR_SOURCE_DIR_NAME
    except Exception:
        return False


def _build_output_targets(
    project,
    group,
    output_dir: Path,
    *,
    selected_map_types: set[str] | None = None,
    selected_map_uuids: set[str] | None = None,
    bit_depth_override: str | None = None,
    image_format_override: str | None = None,
    tile_specs=None,
    tokenized_naming: bool = False,
    # map_uuid -> directory that row writes to instead of output_dir: a Normal row baked
    # only as the material-normal source of other maps (prepare_bake_job
    # source_only_map_uuids) lands in the job workspace, never over the artist's file.
    redirect_dirs: dict[str, Path] | None = None,
) -> list[protocol.OutputTarget]:
    outputs: list[protocol.OutputTarget] = []
    metadata_state = properties.group_metadata_state(group)
    _set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip()
    texture_set_name = properties.resolve_texture_set_output_name(project, _set_key) if _set_key else None
    bit_depth = str(bit_depth_override or getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8)
    image_format = str(
        image_format_override
        or getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT)
        or constants.DEFAULT_IMAGE_FORMAT
    )
    for map_setting in project.maps:
        if getattr(map_setting, "is_add_phantom", False):
            continue
        map_uuid = properties.ensure_map_setting_uuid(map_setting)
        map_selected_by_uuid = selected_map_uuids is not None and map_uuid in selected_map_uuids
        if selected_map_uuids is not None:
            if not map_selected_by_uuid:
                continue
            if selected_map_types is not None and map_setting.map_type not in selected_map_types:
                continue
        elif selected_map_types is not None:
            if map_setting.map_type not in selected_map_types:
                continue
        elif not bool(getattr(map_setting, "enabled", False)):
            continue
        effective_map_type = _effective_map_type_for_setting(map_setting)
        map_label_override = properties.effective_map_output_suffix(project, map_setting)
        display_name = naming.output_display_label(
            group.name,
            effective_map_type,
            texture_set_name=texture_set_name,
            map_label_override=map_label_override,
            project_name=str(getattr(project, "name", "") or ""),
        )
        # One target per (map, tile). The same map_uuid deliberately repeats across a texture
        # set's tiles -- the physical identity is (texture_set, map_uuid, udim_tile) -- so every
        # matcher downstream keys on the pair.
        for spec in tile_specs or (None,):
            udim_tile = int(getattr(spec, "udim_tile", 0) or 0) if spec is not None else 0
            file_name = naming.build_output_file_name(
                group_name=group.name,
                map_type=effective_map_type,
                bit_depth=bit_depth,
                image_format=image_format,
                texture_set_name=texture_set_name,
                udim_tile=udim_tile if tokenized_naming and udim_tile else None,
                map_label_override=map_label_override,
                project_name=str(getattr(project, "name", "") or ""),
            )
            outputs.append(
                protocol.OutputTarget(
                    map_type=effective_map_type,
                    path=str(Path((redirect_dirs or {}).get(map_uuid, output_dir)) / file_name),
                    display_name=display_name,
                    output_suffix=map_label_override or "",
                    map_uuid=map_uuid,
                    # 0 for the legacy untiled path; the backend treats 0 as "no tile".
                    udim_tile=udim_tile if tokenized_naming else 0,
                    resolution_width=int(getattr(spec, "width", 0) or 0) if spec is not None else 0,
                    resolution_height=int(getattr(spec, "height", 0) or 0) if spec is not None else 0,
                )
            )
    return outputs


def _group_texture_set_name(project, group_name: str) -> str | None:
    target_name = (group_name or "").strip().casefold()
    if not target_name:
        return None
    # Inside one progress pass the answer cannot change; the scan below is O(groups) and
    # runs once per tracked output, so a many-group bake paid O(groups x outputs) per tick.
    from . import runtime_output_images as _scope

    if _scope._NORMALIZED_PATH_CACHE is None:
        return _group_texture_set_name_uncached(project, target_name)
    return _scope.cached_normalized_path(
        "group_texture_set",
        f"{id(project)}|{target_name}",
        lambda: (_group_texture_set_name_uncached(project, target_name), project),
    )[0]


def _group_texture_set_name_uncached(project, target_name: str) -> str | None:
    groups = getattr(project, "groups", [])
    for group in groups:
        current_name = (getattr(group, "name", "") or "").strip().casefold()
        if current_name != target_name:
            continue
        metadata_state = properties.group_metadata_state(group)
        texture_set_name = (getattr(metadata_state, "texture_set_name", "") or "").strip()
        if not texture_set_name:
            return None
        # Resolve the set's name_mode (Custom / .blend / Material) to the output token.
        # The stored link key is unchanged; only the file name reflects the mode.
        return properties.resolve_texture_set_output_name(project, texture_set_name)
    return None


def _selected_project_maps(project, selected_map_types=None, selected_map_uuids=None):
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        item_uuid = properties.ensure_map_setting_uuid(item)
        if selected_map_uuids is not None and item_uuid not in selected_map_uuids:
            continue
        if selected_map_types is not None and str(getattr(item, "map_type", "") or "") not in selected_map_types:
            continue
        if selected_map_uuids is None and selected_map_types is None and not bool(getattr(item, "enabled", True)):
            continue
        yield item


def _selected_maps_need_high_vertex_colors(project, selected_map_types=None, selected_map_uuids=None) -> bool:
    for item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        map_type = str(getattr(item, "map_type", "") or "")
        if map_type == constants.MAP_VERTEX_COLOR:
            return True
        if map_type != constants.MAP_ID:
            continue
        if str(getattr(item, "id_source", constants.MAP_ID_SOURCE_OBJECT) or "") == constants.MAP_ID_SOURCE_VERTEX_COLOR:
            return True
    return False


def _job_backend_will_run() -> bool:
    """Whether the FYR backend is actually going to execute this job. Under Route =
    Cycles it is not, which changes who owns a natively-compilable material channel."""
    try:
        from . import bake_backends as _bake_backends

        return _bake_backends.resolve_active_render_backend().backend_id != "cycles"
    except Exception:
        return True


def _lit_color_rows(project, selected_map_types=None, selected_map_uuids=None) -> dict[str, object]:
    """uuid -> row for the selected Scene Lighting rows whose Output is Lit Color."""
    rows: dict[str, object] = {}
    for item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if constants.effective_lighting_map_type(item) == constants.MAP_LIT_COLOR:
            rows[properties.ensure_map_setting_uuid(item)] = item
    return rows


def _lit_color_material_row(channel: str):
    """The Material row a Lit Color source compiles as: a plain Principled channel."""
    from types import SimpleNamespace

    return SimpleNamespace(
        map_type=constants.MAP_MATERIAL,
        material_channel=channel,
        material_origin=constants.MATERIAL_ORIGIN_MANUAL,
        material_custom_name="",
        material_data_type="",
        normal_encode_low_frame=False,
        execution_route=constants.EXECUTION_ROUTE_AUTO,
    )


#: Texture set of the hidden Scene Blockers group (no other group can share it).
SCENE_BLOCKERS_GROUP_NAME = "Scene Blockers"
SCENE_BLOCKERS_TEXTURE_SET = "__fyr_scene_blockers__"


def _scene_blocker_objects(project, selected_group_names) -> list:
    """Render-visible meshes of the project's Scene Blockers collection that are not
    already a low or high of a bake group in this job."""
    if not bool(getattr(project, "use_scene_blockers", True)):
        return []
    collection = getattr(project, "scene_blockers", None)
    if collection is None:
        return []
    in_groups: set[str] = set()
    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        for slot in list(getattr(group, "low_meshes", ()) or ()) + list(properties.effective_high_mesh_slots(group)):
            obj = getattr(slot, "object_ref", None)
            if obj is not None:
                in_groups.add(str(obj.name))
    objects = []
    for obj in getattr(collection, "all_objects", ()) or ():
        if getattr(obj, "type", "") != "MESH" or bool(getattr(obj, "hide_render", False)):
            continue
        if str(obj.name) in in_groups:
            continue
        objects.append(obj)
    return sorted(objects, key=lambda o: str(o.name))


def _export_scene_blockers_group(
    project,
    groups,
    depsgraph,
    meshes_root: Path,
    workspace_path,
    selected_map_types,
    selected_map_uuids,
    selected_group_names,
    *,
    requires_high_uvs: bool,
    is_material_workflow: bool,
):
    """The hidden Scene Blockers group, or None.

    Its meshes join the whole-scene lighting of every lighting row that includes other
    groups; the backend prepares the group (so it is in the world) and never bakes or
    writes it. Tiny outputs keep its preparation cheap; their paths are never written.
    """
    if is_material_workflow or not groups:
        return None
    rows = [
        item
        for item in _selected_project_maps(project, selected_map_types, selected_map_uuids)
        if constants.effective_lighting_map_type(item) in constants.LIGHTING_COMPONENT_BY_EFFECTIVE_TYPE
        and bool(getattr(item, "lighting_occlude_other_groups", True))
    ]
    if not rows:
        return None
    objects = _scene_blocker_objects(project, selected_group_names)
    if not objects:
        return None
    blocker_root = workspace.ensure_directory(meshes_root / "__scene_blockers__")
    sink_root = workspace.ensure_directory(Path(workspace_path) / "scene_blockers_unused")
    low_meshes = []
    high_meshes = []
    for index, obj in enumerate(objects):
        token = naming.sanitize_token(obj.name)
        low = write_evaluated_obj(obj, depsgraph, blocker_root / f"low_{index:02d}_{token}.fymesh")
        low.role = constants.OBJECT_ROLE_LOW
        low_meshes.append(low)
        if requires_high_uvs:
            high = write_evaluated_obj(
                obj, depsgraph, blocker_root / f"high_{index:02d}_{token}.fymesh", local_space=True
            )
            high.role = constants.OBJECT_ROLE_HIGH
        else:
            # A blocker shadows with every face, floater faces included.
            with floater_faces.export_part(obj, floater_faces.PART_WHOLE):
                high = high_mesh_cache.resolve_high_mesh_ref(obj, depsgraph)
        high_meshes.append(high)
    outputs = []
    seen: set[str] = set()
    for group in groups:
        for target in group.outputs:
            key = target.map_uuid or target.map_type
            if key in seen:
                continue
            seen.add(key)
            outputs.append(
                protocol.OutputTarget(
                    map_type=target.map_type,
                    path=str(sink_root / f"{len(outputs):03d}.exr"),
                    display_name=target.display_name,
                    output_suffix=target.output_suffix,
                    map_uuid=target.map_uuid,
                    udim_tile=0,
                    resolution_width=16,
                    resolution_height=16,
                )
            )
    return protocol.BakeGroupConfig(
        name=SCENE_BLOCKERS_GROUP_NAME,
        cage_mode=constants.CAGE_MODE_DISTANCE,
        cage_offset=0.01,
        texture_set=SCENE_BLOCKERS_TEXTURE_SET,
        low_meshes=low_meshes,
        high_meshes=high_meshes,
        outputs=outputs,
        occluder_only=True,
        occluder_shadows=bool(getattr(project, "scene_blockers_cast_shadows", True)),
        occluder_bounces=bool(getattr(project, "scene_blockers_bounce_light", True)),
    )


def _upsample_grid(values: list[float], side: int) -> list[float]:
    """A square single-value grid repeated (nearest) up to side x side; [] stays []."""
    if not values or not side:
        return []
    current = int(round(len(values) ** 0.5))
    if current == side:
        return list(values)
    out = []
    for j in range(side):
        row = (j * current) // side
        for i in range(side):
            out.append(values[row * current + (i * current) // side])
    return out


def _lighting_rows_need_high_uvs(project, selected_map_types, selected_map_uuids, selected_group_names) -> bool:
    """Whether a Scene Lighting row bounces light off a textured high material.

    Bounces read the material's albedo texture at the hit's UV, so the highs must
    carry their UVs (FYMESH transport) just as for a Material row.
    """
    if not any(
        constants.effective_lighting_map_type(item)
        in (
            constants.MAP_LIGHTING,
            constants.MAP_LIT_COLOR,
            constants.MAP_INDIRECT_LIGHTING,
            constants.MAP_SPECULAR_LIGHTING,
        )
        for item in _selected_project_maps(project, selected_map_types, selected_map_uuids)
    ):
        return False
    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        objects = list(properties.effective_high_mesh_objects(group) or [])
        if not objects:
            from . import project_structure

            objects = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or [])
        for obj in objects:
            for slot in getattr(obj, "material_slots", None) or ():
                material = getattr(slot, "material", None)
                if material is None:
                    continue
                record = _build_scene_material_record(material)
                if record.albedo_texture or record.roughness_texture or record.metallic_texture:
                    return True
    return False


def _lit_color_scene_emits(project, selected_group_names) -> bool:
    """Whether any high material of the job can emit light into its own Lit Color texels.

    Principled and Emission shaders are judged by their emission inputs; any other
    surface graph may emit through a node the record cannot see, so it counts too.
    """
    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        objects = list(properties.effective_high_mesh_objects(group) or [])
        if not objects:
            from . import project_structure

            objects = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or [])
        for obj in objects:
            for slot in getattr(obj, "material_slots", None) or ():
                material = getattr(slot, "material", None)
                if material is None:
                    continue
                node_tree = getattr(material, "node_tree", None)
                if bool(getattr(material, "use_nodes", False)) and node_tree is not None:
                    shader = _material_surface_shader(node_tree)
                    if getattr(shader, "type", "") not in (_PRINCIPLED_NODE_TYPE, _EMISSION_NODE_TYPE):
                        return True
                record = _build_scene_material_record(material)
                if record.has_textured_emission or max(record.emission, default=0.0) > 0.0:
                    return True
    return False


def _collect_lit_color_sources(project, lit_rows, workspace_path, selected_group_names, *, diagnostics=None):
    """uuid -> {"albedo": source, "emission": source or None} for each Lit Color row.

    Each source is what _collect_material_ir_source returns for the high materials'
    ALBEDO / EMISSION channel; a non-native one bakes through Cycles instead.
    """
    if not lit_rows:
        return {}
    albedo = _collect_material_ir_source(
        _lit_color_material_row(constants.MATERIAL_CHANNEL_ALBEDO),
        project,
        workspace_path,
        selected_group_names,
        diagnostics=diagnostics,
    )
    emission = None
    if any(bool(getattr(row, "lighting_emission_enabled", True)) for row in lit_rows.values()) and (
        _lit_color_scene_emits(project, selected_group_names)
    ):
        emission = _collect_material_ir_source(
            _lit_color_material_row(constants.MATERIAL_CHANNEL_EMISSION),
            project,
            workspace_path,
            selected_group_names,
            diagnostics=diagnostics,
        )
        if emission is None:
            emission = {"program": None}
    sources: dict[str, dict] = {}
    for map_uuid, row in lit_rows.items():
        sources[map_uuid] = {
            "albedo": albedo if albedo is not None else {"program": None},
            "emission": emission if bool(getattr(row, "lighting_emission_enabled", True)) else None,
        }
    return sources


def _lit_color_source_is_native(source) -> bool:
    from . import material_ir

    program = (source or {}).get("program")
    return isinstance(program, material_ir.MaterialIrProgram) and bool(program.native)


def _lit_color_material_config(project, row, map_uuid: str, channel: str, source) -> protocol.BakeMapConfig:
    """Backend config of one native Lit Color source: an ordinary Material channel bake."""
    from . import material_ir

    program = source["program"]
    resource_paths = list(source.get("resource_paths") or [])
    wire = program.wire_payload()
    wire["resources"] = [
        material_ir.wire_resource(res, path)
        for res, path in zip(
            program.resources,
            resource_paths or [program.image_path] * len(program.resources),
        )
    ]
    return protocol.BakeMapConfig(
        map_type=constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE[channel],
        map_uuid=map_uuid,
        enabled=True,
        samples=1,
        output_suffix="",
        denoising_enabled=False,
        material_channel=channel,
        material_fast_path_image_path=str(source.get("path") or program.image_path or ""),
        material_fast_path_tile_images=list(source.get("tiles") or []),
        material_ir_version=int(program.version),
        material_ir_kind=str(program.kind),
        material_ir_fallback_reason=str(program.fallback_reason or ""),
        material_ir_program_json=json.dumps(wire, separators=(",", ":"), sort_keys=True),
        material_ir_resource_paths=resource_paths,
        output_soften=properties.resolve_map_soften(project, row),
    )


def _split_derived_outputs(project, group, outputs, output_dir: Path, *, lit_color_sources=None, lit_color_dir=None):
    """(backend targets, derived_outputs entries) for one group's output targets.

    A Wireframe target leaves the backend job entirely; a Derivative target stays (the
    backend bakes its hidden tangent-normal source) and gains the conversion entry. A
    Lit Color target becomes hidden Lighting / Base Color / Emission sources plus the
    entry that multiplies them into the artist's file.
    """
    kept: list[protocol.OutputTarget] = []
    entries: list[dict] = []
    group_name = str(getattr(group, "name", "") or "")
    for target in outputs:
        map_type = str(target.map_type or "").strip().upper()
        row = properties.find_map_setting_by_uuid(project, target.map_uuid) if target.map_uuid else None
        tile = int(target.udim_tile or 0)
        if map_type in (constants.MAP_DIRECT_LIGHTING, constants.MAP_INDIRECT_LIGHTING, constants.MAP_SPECULAR_LIGHTING):
            # The backend selects outputs by wire type; the row restores its own type when
            # the produced file comes back (_restore_lighting_output_types).
            target = replace(target, map_type=constants.MAP_LIGHTING)
            map_type = constants.MAP_LIGHTING
        if map_type == constants.MAP_LIT_COLOR and lit_color_dir is not None and target.map_uuid in (lit_color_sources or {}):
            sources = lit_color_sources[target.map_uuid]
            paths = derived_outputs.lit_color_source_paths(lit_color_dir, Path(target.path).name)

            def _hidden(path: str, hidden_type: str, hidden_uuid: str) -> protocol.OutputTarget:
                return protocol.OutputTarget(
                    map_type=hidden_type,
                    path=path,
                    display_name=target.display_name,
                    output_suffix=target.output_suffix,
                    map_uuid=hidden_uuid,
                    udim_tile=target.udim_tile,
                    resolution_width=target.resolution_width,
                    resolution_height=target.resolution_height,
                )

            kept.append(_hidden(paths["lighting"], constants.MAP_LIGHTING, target.map_uuid))
            routes: dict[str, str] = {}
            for role, channel, suffix in (
                ("albedo", constants.MATERIAL_CHANNEL_ALBEDO, derived_outputs.LIT_COLOR_ALBEDO_UUID_SUFFIX),
                ("emission", constants.MATERIAL_CHANNEL_EMISSION, derived_outputs.LIT_COLOR_EMISSION_UUID_SUFFIX),
            ):
                if sources.get(role) is None:
                    continue
                if _lit_color_source_is_native(sources[role]):
                    routes[role] = constants.EXECUTION_ROUTE_BACKEND
                    kept.append(_hidden(
                        paths[role],
                        constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE[channel],
                        target.map_uuid + suffix,
                    ))
                else:
                    routes[role] = constants.EXECUTION_ROUTE_BLENDER
            entries.append({
                "kind": derived_outputs.KIND_LIT_COLOR,
                "group_name": group_name,
                "map_uuid": str(target.map_uuid or ""),
                "udim_tile": tile,
                "final_path": str(target.path),
                "lighting_source": paths["lighting"],
                "albedo_source": paths["albedo"],
                "emission_source": paths["emission"] if "emission" in routes else "",
                "albedo_route": routes.get("albedo", ""),
                "emission_route": routes.get("emission", ""),
                # The backend applies the row's exposure to the lighting; the composite
                # applies it to the emission, so the whole Lit Color scales together.
                "emission_scale": float(getattr(row, "lighting_exposure", 1.0)) if row is not None else 1.0,
                "width": int(target.resolution_width or getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION)),
                "height": int(target.resolution_height or getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION)),
                "bit_depth": str(getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8),
            })
            continue
        if (
            row is not None
            and str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL
            and str(getattr(row, "map_type", "") or "").strip().upper() == constants.MAP_MATERIAL
            and str(getattr(row, "material_origin", "") or "").strip().upper() != constants.MATERIAL_ORIGIN_CUSTOM
            and str(getattr(row, "material_channel", "") or "").strip().upper() == constants.MATERIAL_CHANNEL_NORMAL
            and _job_backend_will_run()
        ):
            # The Cycles route finishes this row with the Relief post-passes; a GPU
            # bake gets the same, so the route does not change the look.
            entries.append({
                "kind": derived_outputs.KIND_NORMAL_RELIEF,
                "group_name": group_name,
                "map_uuid": str(target.map_uuid or ""),
                "udim_tile": tile,
                "path": str(target.path),
                "relief": _map_normal_relief(row),
            })
        if map_type == constants.MAP_WIREFRAME:
            tile_u, tile_v = naming.udim_tile_to_coords(tile) if tile else (0, 0)
            projection_state = _group_projection_settings_state(group)
            entries.append({
                "kind": derived_outputs.KIND_WIREFRAME,
                "group_name": group_name,
                "map_uuid": str(target.map_uuid or ""),
                "udim_tile": tile,
                "final_path": str(target.path),
                "width": int(target.resolution_width or getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION)),
                "height": int(target.resolution_height or getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION)),
                "tile_u": float(tile_u),
                "tile_v": float(tile_v),
                "objects": [
                    str(slot.object_ref.name) for slot in _iter_bakeable_low_slots(getattr(group, "low_meshes", []))
                ],
                "uv_layer": (getattr(projection_state, "uv_layer_name", "") or "").strip(),
                "line_width": float(getattr(row, "wireframe_line_width", constants.DEFAULT_WIREFRAME_LINE_WIDTH)),
                "triangles": bool(getattr(row, "wireframe_triangles", False)),
                "bit_depth": str(getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8),
            })
            continue
        if map_type == constants.MAP_DERIVATIVE:
            entries.append({
                "kind": derived_outputs.KIND_DERIVATIVE,
                "group_name": group_name,
                "map_uuid": str(target.map_uuid or ""),
                "udim_tile": tile,
                "source_path": str(target.path),
                "final_path": str(Path(output_dir) / Path(target.path).name),
                "max_slope": float(getattr(row, "derivative_max_slope", constants.DEFAULT_DERIVATIVE_MAX_SLOPE)),
                "flip_green": bool(
                    row is not None
                    and properties.effective_normal_format(row).strip().upper() == constants.NORMAL_FORMAT_DIRECTX
                ),
            })
        kept.append(target)
    return kept, entries


def _partition_color_stream_rows(project, selected_map_types=None, selected_map_uuids=None):
    """(stream source of this job, uuids of each deferred stage, narrowed uuid selection).

    A selection needing at most one stream source passes through untouched. Otherwise
    the job keeps the first stage (every streamless row plus the first source's rows,
    see color_stream.partition_rows) and the uuid selection narrows to exactly it.
    """
    rows = list(_selected_project_maps(project, selected_map_types, selected_map_uuids))
    stages = color_stream.partition_rows(rows)
    if len(stages) <= 1:
        return (stages[0][0] if stages else None), [], selected_map_uuids
    first_source, first_rows = stages[0]
    kept = {properties.ensure_map_setting_uuid(row) for row in first_rows}
    deferred = [
        [properties.ensure_map_setting_uuid(row) for row in stage_rows]
        for _source, stage_rows in stages[1:]
    ]
    return first_source, deferred, kept


def _iter_group_high_materials(group):
    seen: set[int] = set()
    for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group)):
        obj = getattr(slot, "object_ref", None)
        for material_slot in getattr(obj, "material_slots", []) if obj is not None else []:
            material = getattr(material_slot, "material", None)
            if material is None or not bool(getattr(material, "use_nodes", False)):
                continue
            try:
                key = int(material.as_pointer())
            except Exception:
                key = id(material)
            if key in seen:
                continue
            seen.add(key)
            yield material


def _normal_socket_has_detail_source(normal_input) -> bool:
    """True when the Principled Normal link actually carries something to bake.

    FBX imports (Maya exports in particular) leave a Normal Map node wired into
    Principled Normal with NOTHING on its Color socket. Treating that bare link as
    material detail scheduled a Cycles ``__DETAIL_NORMAL__`` pass for every group of
    a 66-group character (2026-09-07), minutes of work that produced a flat map.
    A Normal Map needs its Color fed, a Bump needs its Height fed, an Image Texture
    needs an image; any other node feeding Normal is a real procedural graph and
    still qualifies.
    """
    if normal_input is None or not bool(getattr(normal_input, "is_linked", False)):
        return False
    links = getattr(normal_input, "links", ()) or ()
    if not links:
        return False
    from_node = getattr(links[0], "from_node", None)
    node_type = str(getattr(from_node, "type", "") or "")
    if node_type == "NORMAL_MAP":
        color_input = from_node.inputs.get("Color") if from_node is not None else None
        return color_input is not None and bool(getattr(color_input, "is_linked", False))
    if node_type == "BUMP":
        height_input = from_node.inputs.get("Height") if from_node is not None else None
        return height_input is not None and bool(getattr(height_input, "is_linked", False))
    if node_type == "TEX_IMAGE":
        return getattr(from_node, "image", None) is not None
    return True


def _surface_principled_nodes(material, *, with_stack: bool = False):
    """Principled BSDFs that feed the material's Surface, through groups and mixes.

    A top-level scan misses a shader library that wraps the surface in a node group
    (ZenBBQ's preview shader: Material Output <- group <- switch group <- Mix Shader <-
    the Principled carrying the Bevel). Follows the closure the way the Material IR
    compiler does: Reroute, Mix / Add Shader (every shader input), into a group through
    its Group Output and back out through Group Input.

    ``with_stack`` returns ``(node, group_stack)`` pairs, the group nodes entered to
    reach each Principled (outermost first) -- what an upstream walk from one of its
    sockets needs to cross a Group Input.
    """
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return []
    output = None
    for node in getattr(tree, "nodes", []) or []:
        if getattr(node, "type", "") != "OUTPUT_MATERIAL":
            continue
        if output is None or bool(getattr(node, "is_active_output", False)):
            output = node
    if output is None:
        return []
    found: list = []
    seen: set = set()
    budget = [512]

    def group_output_node(group_tree):
        candidates = [
            node for node in (getattr(group_tree, "nodes", []) or [])
            if getattr(node, "type", "") == "GROUP_OUTPUT"
        ]
        for node in candidates:
            if bool(getattr(node, "is_active_output", False)):
                return node
        return candidates[0] if candidates else None

    def matching(sockets, template, index_source):
        if sockets is None or template is None:
            return None
        for key in (getattr(template, "identifier", None), getattr(template, "name", None)):
            if not key:
                continue
            try:
                hit = sockets.get(key)
            except Exception:
                hit = None
            if hit is not None:
                return hit
        try:
            index = list(index_source).index(template)
            return list(sockets)[index]
        except Exception:
            return None

    def follow(socket, stack):
        if socket is None or budget[0] <= 0:
            return
        for link in (getattr(socket, "links", ()) or ())[:1]:
            visit(getattr(link, "from_node", None), getattr(link, "from_socket", None), stack)

    def visit(node, out_socket, stack):
        if node is None or budget[0] <= 0:
            return
        budget[0] -= 1
        node_type = str(getattr(node, "type", "") or "")
        if node_type == "BSDF_PRINCIPLED":
            key = (id(node), tuple(id(frame) for frame in stack))
            if key not in seen:
                seen.add(key)
                found.append((node, tuple(stack)) if with_stack else node)
            return
        inputs = getattr(node, "inputs", None) or []
        if node_type == "REROUTE":
            follow(inputs[0] if len(inputs) else None, stack)
        elif node_type in {"MIX_SHADER", "ADD_SHADER"}:
            for candidate in inputs:
                if str(getattr(candidate, "type", "") or "") == "SHADER":
                    follow(candidate, stack)
        elif node_type == "GROUP" and len(stack) < 16:
            group_tree = getattr(node, "node_tree", None)
            group_output = group_output_node(group_tree)
            if group_output is None:
                return
            inner = matching(group_output.inputs, out_socket, getattr(node, "outputs", []) or [])
            follow(inner, stack + (node,))
        elif node_type == "GROUP_INPUT" and stack:
            outer = matching(stack[-1].inputs, out_socket, getattr(node, "outputs", []) or [])
            follow(outer, stack[:-1])

    try:
        follow(output.inputs.get("Surface"), ())
    except Exception:
        return found
    return found


def _group_has_material_normal_detail(group) -> bool:
    for material in _iter_group_high_materials(group):
        nodes = list(getattr(getattr(material, "node_tree", None), "nodes", []) or [])
        principled = [node for node in nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"]
        # Plus the ones reached through node groups; the top-level scan stays as it
        # was so no material that qualified before stops qualifying.
        for node in _surface_principled_nodes(material):
            if node not in principled:
                principled.append(node)
        for node in principled:
            if _normal_socket_has_detail_source(node.inputs.get("Normal")):
                return True
    return False


def _group_material_ao_source(group, explicit_image=None):
    from . import blender_bake

    if explicit_image is not None:
        return explicit_image
    for material in _iter_group_high_materials(group):
        node = blender_bake._semantic_ao_image_node(material)  # noqa: SLF001
        if node is not None and getattr(node, "image", None) is not None:
            return node.image
    return None


def _direct_image_from_socket(socket):
    node = _direct_image_texture_node_from_socket(socket)
    return getattr(node, "image", None) if node is not None else None


def _direct_image_texture_node_from_socket(socket):
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        return None
    links = getattr(socket, "links", ()) or ()
    if not links:
        return None
    node = getattr(links[0], "from_node", None)
    if getattr(node, "type", "") != "TEX_IMAGE":
        return None
    return node


def _follow_vector_source(socket, *, depth: int = 0):
    """Walk Reroute/Mapping to the coordinate source of an Image Texture Vector input."""
    if socket is None or depth > 16:
        return None, None
    if not bool(getattr(socket, "is_linked", False)):
        return None, None
    links = getattr(socket, "links", ()) or ()
    if not links:
        return None, None
    node = getattr(links[0], "from_node", None)
    out = getattr(links[0], "from_socket", None)
    ntype = str(getattr(node, "type", "") or "")
    if ntype == "REROUTE":
        return _follow_vector_source(node.inputs[0] if node.inputs else None, depth=depth + 1)
    if ntype == "MAPPING":
        # Only identity Mapping (no linked transforms) is compatible with the UV fast path.
        for name in ("Location", "Rotation", "Scale"):
            inp = node.inputs.get(name)
            if inp is not None and bool(getattr(inp, "is_linked", False)):
                return node, out
        try:
            loc = tuple(float(v) for v in node.inputs["Location"].default_value)
            rot = tuple(float(v) for v in node.inputs["Rotation"].default_value)
            scale = tuple(float(v) for v in node.inputs["Scale"].default_value)
        except Exception:
            return node, out
        if any(abs(v) > 1e-5 for v in loc) or any(abs(v) > 1e-5 for v in rot):
            return node, out
        if any(abs(v - 1.0) > 1e-5 for v in scale):
            return node, out
        return _follow_vector_source(node.inputs.get("Vector"), depth=depth + 1)
    return node, out


def _image_texture_uses_plain_uv(tex_node) -> bool:
    """True when the backend UV-hit fast path can sample this texture correctly.

    The fast path ignores Object/Generated coordinates and non-identity Mapping.
    Unlinked Vector uses the active UV map (safe). Anything else must use Cycles.
    """
    if tex_node is None or str(getattr(tex_node, "type", "") or "") != "TEX_IMAGE":
        return False
    vector = tex_node.inputs.get("Vector") if hasattr(tex_node, "inputs") else None
    if vector is None or not bool(getattr(vector, "is_linked", False)):
        return True
    node, socket = _follow_vector_source(vector)
    if node is None:
        return False
    ntype = str(getattr(node, "type", "") or "")
    sname = str(getattr(socket, "name", "") or "")
    if ntype == "UVMAP":
        return True
    if ntype == "TEX_COORD" and sname == "UV":
        return True
    return False


_IDENTITY_UV_TRANSFORM = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _rotation_matrix_xyz(rx: float, ry: float, rz: float):
    """3x3 rotation for a Blender XYZ euler (X applied first, then Y, then Z)."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # R = Rz @ Ry @ Rx
    return [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]


def _mat3_mul(a, b):
    return [
        [sum(a[row][k] * b[k][col] for k in range(3)) for col in range(3)]
        for row in range(3)
    ]


def _mat3_vec(a, v):
    return [sum(a[row][k] * v[k] for k in range(3)) for row in range(3)]


def _mat3_inverse(a):
    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    return [
        [
            (a[1][1] * a[2][2] - a[1][2] * a[2][1]) * inv_det,
            (a[0][2] * a[2][1] - a[0][1] * a[2][2]) * inv_det,
            (a[0][1] * a[1][2] - a[0][2] * a[1][1]) * inv_det,
        ],
        [
            (a[1][2] * a[2][0] - a[1][0] * a[2][2]) * inv_det,
            (a[0][0] * a[2][2] - a[0][2] * a[2][0]) * inv_det,
            (a[0][2] * a[1][0] - a[0][0] * a[1][2]) * inv_det,
        ],
        [
            (a[1][0] * a[2][1] - a[1][1] * a[2][0]) * inv_det,
            (a[0][1] * a[2][0] - a[0][0] * a[2][1]) * inv_det,
            (a[0][0] * a[1][1] - a[0][1] * a[1][0]) * inv_det,
        ],
    ]


def _image_texture_uv_affine(tex_node):
    """The constant 2D affine a texture's Vector chain applies to the UV, or None.

    Returns [a, b, c, d, tx, ty] with u' = a*u + b*v + tx and v' = c*u + d*v + ty,
    for a chain of Reroute and CONSTANT Mapping nodes ending at the active UV
    (unlinked Vector, UV Map node, or Texture Coordinate's UV output). The UV's z
    is always 0 and w always 1, so chained 3D Mapping transforms reduce exactly to
    this 2D affine regardless of their z rows. None means the chain is not a
    constant UV transform (linked Mapping sockets, Object/Generated coordinates,
    NORMAL-type Mapping, unknown nodes) and the detail fast path must decline.
    Pure Python on purpose: this also runs in the mathutils-free test harness.
    """
    if tex_node is None or str(getattr(tex_node, "type", "") or "") != "TEX_IMAGE":
        return None
    socket = tex_node.inputs.get("Vector") if hasattr(tex_node, "inputs") else None
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        return list(_IDENTITY_UV_TRANSFORM)

    # Walk from the texture towards the coordinate source. Each Mapping found is
    # applied AFTER everything upstream of it, so composition multiplies newly
    # found transforms on the RIGHT: combined = combined o local.
    combined_linear = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    combined_translation = [0.0, 0.0, 0.0]
    depth = 0
    while depth < 16:
        depth += 1
        links = getattr(socket, "links", ()) or ()
        if not links:
            return None
        node = getattr(links[0], "from_node", None)
        out_socket = getattr(links[0], "from_socket", None)
        ntype = str(getattr(node, "type", "") or "")
        if ntype == "REROUTE":
            socket = node.inputs[0] if node.inputs else None
        elif ntype == "MAPPING":
            for name in ("Location", "Rotation", "Scale"):
                inp = node.inputs.get(name)
                if inp is not None and bool(getattr(inp, "is_linked", False)):
                    return None
            try:
                loc = [float(v) for v in node.inputs["Location"].default_value]
                rot = [float(v) for v in node.inputs["Rotation"].default_value]
                scale = [float(v) for v in node.inputs["Scale"].default_value]
            except Exception:
                return None
            rotation = _rotation_matrix_xyz(rot[0], rot[1], rot[2])
            # POINT applies scale, then rotation, then translation.
            linear = _mat3_mul(rotation, [
                [scale[0], 0.0, 0.0],
                [0.0, scale[1], 0.0],
                [0.0, 0.0, scale[2]],
            ])
            vector_type = str(getattr(node, "vector_type", "POINT") or "POINT")
            if vector_type == "POINT":
                translation = loc
            elif vector_type == "VECTOR":
                translation = [0.0, 0.0, 0.0]
            elif vector_type == "TEXTURE":
                inverse = _mat3_inverse(linear)
                if inverse is None:
                    return None
                linear = inverse
                translation = [-v for v in _mat3_vec(inverse, loc)]
            else:
                # NORMAL renormalizes; not an affine map of the UV.
                return None
            combined_translation = [
                t + v
                for t, v in zip(
                    _mat3_vec(combined_linear, translation), combined_translation
                )
            ]
            combined_linear = _mat3_mul(combined_linear, linear)
            socket = node.inputs.get("Vector")
        elif ntype == "UVMAP" or (
            ntype == "TEX_COORD" and str(getattr(out_socket, "name", "") or "") == "UV"
        ):
            return [
                float(combined_linear[0][0]),
                float(combined_linear[0][1]),
                float(combined_linear[1][0]),
                float(combined_linear[1][1]),
                float(combined_translation[0]),
                float(combined_translation[1]),
            ]
        else:
            return None
        if socket is None or not bool(getattr(socket, "is_linked", False)):
            return None
    return None


def _uv_transform_is_identity(transform) -> bool:
    values = list(transform or _IDENTITY_UV_TRANSFORM)
    if len(values) != 6:
        return False
    return all(
        abs(float(value) - reference) <= 1e-6
        for value, reference in zip(values, _IDENTITY_UV_TRANSFORM)
    )


#: Backend modes whose detail is built from a Normal Map node, so that node's space
#: decides whether the composition is meaningful.
_NORMAL_MAP_DETAIL_MODES = frozenset({"NORMAL_COMBINE", "NORMAL_AO"})


def _material_normal_map_space(material) -> str:
    """Space of the Normal Map node feeding this material's Principled Normal input.

    Empty when nothing usable is linked. Only meaningful for a source the resolver
    reported as one of :data:`_NORMAL_MAP_DETAIL_MODES`, which is exactly when that
    node is what the detail is built from. Mirrors the traversal in
    ``_material_detail_source`` below, which is six lines and has no seam to share.
    """
    nodes = getattr(getattr(material, "node_tree", None), "nodes", ()) or ()
    principled = next(
        (node for node in nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"),
        None,
    )
    if principled is None:
        return ""
    socket = principled.inputs.get("Normal")
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        return ""
    links = getattr(socket, "links", ()) or ()
    linked_node = getattr(links[0], "from_node", None) if links else None
    if getattr(linked_node, "type", "") != "NORMAL_MAP":
        return ""
    return str(getattr(linked_node, "space", "") or "").strip().upper()


def _material_detail_source(material, map_type: str):
    """Return (image, backend mode, strength, flip_green, uv_transform) for an
    image-backed detail. ``uv_transform`` is the constant 2D affine the texture's
    Vector chain applies to the UV ([a, b, c, d, tx, ty], identity for a plain UV
    hookup); a chain that is not a constant UV transform declines the source, and
    a tiled (UDIM) source only qualifies with the identity transform because tile
    selection happens in untransformed UV space."""
    from . import blender_bake

    def _qualify(image, tex_node, backend_mode, strength, flip_green):
        transform = _image_texture_uv_affine(tex_node)
        if transform is None:
            return None
        if (
            str(getattr(image, "source", "") or "").upper() == "TILED"
            and not _uv_transform_is_identity(transform)
        ):
            return None
        return image, backend_mode, strength, flip_green, transform

    nodes = getattr(getattr(material, "node_tree", None), "nodes", ()) or ()
    principled = next(
        (node for node in nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"),
        None,
    )
    if principled is None:
        return None

    normal_socket = principled.inputs.get("Normal")
    linked_node = None
    if normal_socket is not None and bool(getattr(normal_socket, "is_linked", False)):
        links = getattr(normal_socket, "links", ()) or ()
        linked_node = getattr(links[0], "from_node", None) if links else None

    bump_image = None
    bump_tex_node = None
    bump_strength = 1.0
    if getattr(linked_node, "type", "") == "BUMP":
        bump_tex_node = _direct_image_texture_node_from_socket(linked_node.inputs.get("Height"))
        bump_image = getattr(bump_tex_node, "image", None) if bump_tex_node is not None else None
        try:
            bump_strength = float(linked_node.inputs.get("Strength").default_value)
            bump_strength *= float(linked_node.inputs.get("Distance").default_value)
        except (AttributeError, TypeError, ValueError):
            bump_strength = 1.0

    normal_image = None
    normal_tex_node = None
    normal_strength = 1.0
    if getattr(linked_node, "type", "") == "NORMAL_MAP":
        normal_tex_node = _direct_image_texture_node_from_socket(linked_node.inputs.get("Color"))
        normal_image = getattr(normal_tex_node, "image", None) if normal_tex_node is not None else None
        try:
            normal_strength = float(linked_node.inputs.get("Strength").default_value)
        except (AttributeError, TypeError, ValueError):
            normal_strength = 1.0
    elif getattr(linked_node, "type", "") == "TEX_IMAGE":
        normal_tex_node = linked_node
        normal_image = getattr(linked_node, "image", None)

    if map_type == constants.MAP_NORMAL:
        if normal_image is not None:
            return _qualify(normal_image, normal_tex_node, "NORMAL_COMBINE", normal_strength, False)
        if bump_image is not None:
            return _qualify(bump_image, bump_tex_node, "HEIGHT_NORMAL", bump_strength, False)
        return None

    semantic_node = blender_bake._semantic_ao_image_node(material)  # noqa: SLF001
    semantic_image = getattr(semantic_node, "image", None) if semantic_node is not None else None
    if semantic_image is not None:
        return _qualify(semantic_image, semantic_node, "AO_TEXTURE", 1.0, False)
    if bump_image is not None:
        return _qualify(bump_image, bump_tex_node, "HEIGHT_AO", bump_strength, False)
    if normal_image is not None:
        return _qualify(normal_image, normal_tex_node, "NORMAL_AO", normal_strength, False)
    return None


def _opacity_socket_expression(socket, *, material_name: str):
    """Resolve a common scalar opacity graph to one image plus a pixel evaluator.

    The evaluator receives source RGBA and returns unclamped opacity. Constants
    may be combined with one image source; multiple independent images and
    procedural coordinate domains are rejected deliberately.
    """
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        try:
            value = float(getattr(socket, "default_value", 1.0))
        except (TypeError, ValueError):
            value = 1.0
        return {
            "image": None,
            "eval": lambda _rgba, value=value: value,
            "identity": f"CONST:{value:.9g}",
            "address": "REPEAT",
            "filter": "LINEAR",
        }

    links = tuple(getattr(socket, "links", ()) or ())
    node = getattr(links[0], "from_node", None) if links else None
    output = getattr(links[0], "from_socket", None) if links else None
    node_type = str(getattr(node, "type", "") or "")
    if node_type == "TEX_IMAGE":
        image = getattr(node, "image", None)
        if image is None:
            raise ValueError(
                f"High-poly material '{material_name}' has an opacity Image Texture with no image. "
                "Assign an image or disable Respect Opacity."
            )
        if str(getattr(image, "source", "") or "").upper() == "TILED":
            raise ValueError(
                f"High-poly material '{material_name}' uses UDIM opacity. UDIM opacity bindings "
                "must be flattened to a regular image before baking, or Respect Opacity must be disabled."
            )
        vector_input = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Vector")
        if vector_input is not None and bool(getattr(vector_input, "is_linked", False)):
            vector_links = tuple(getattr(vector_input, "links", ()) or ())
            vector_node = getattr(vector_links[0], "from_node", None) if vector_links else None
            vector_socket = getattr(vector_links[0], "from_socket", None) if vector_links else None
            vector_type = str(getattr(vector_node, "type", "") or "")
            vector_name = str(getattr(vector_socket, "name", "") or "").upper()
            if vector_type not in {"UVMAP", "TEX_COORD"} or (
                vector_type == "TEX_COORD" and vector_name != "UV"
            ):
                raise ValueError(
                    f"High-poly material '{material_name}' uses unsupported opacity coordinates. "
                    "Use the active UV map directly, or disable Respect Opacity."
                )
        extension = str(getattr(node, "extension", "REPEAT") or "REPEAT").upper()
        if extension not in {"REPEAT", "EXTEND", "CLIP"}:
            raise ValueError(
                f"High-poly material '{material_name}' uses unsupported opacity extension "
                f"'{extension}'. Use Repeat, Extend, or Clip."
            )
        interpolation = str(getattr(node, "interpolation", "Linear") or "Linear").upper()
        if interpolation not in {"LINEAR", "CLOSEST"}:
            raise ValueError(
                f"High-poly material '{material_name}' uses unsupported opacity filtering "
                f"'{interpolation}'. Use Linear or Closest."
            )
        output_name = str(getattr(output, "name", "") or "").upper()
        if output_name != "ALPHA":
            raise ValueError(
                f"High-poly material '{material_name}' must drive opacity from the Image Texture "
                "Alpha output, not its Color output."
            )
        return {
            "image": image,
            "eval": lambda rgba: float(rgba[3]),
            "identity": f"IMAGE_ALPHA:{getattr(image, 'name_full', getattr(image, 'name', ''))}",
            "address": extension,
            "filter": interpolation,
        }

    if node_type == "INVERT":
        child = _opacity_socket_expression(node.inputs.get("Color"), material_name=material_name)
        child_eval = child["eval"]
        return {
            **child,
            "eval": lambda rgba, child_eval=child_eval: 1.0 - child_eval(rgba),
            "identity": f"INVERT({child['identity']})",
        }

    if node_type == "VALTORGB":
        child = _opacity_socket_expression(node.inputs.get("Fac"), material_name=material_name)
        ramp = getattr(node, "color_ramp", None)
        interpolation = str(getattr(ramp, "interpolation", "LINEAR") or "LINEAR").upper()
        if interpolation not in {"LINEAR", "CONSTANT"}:
            raise ValueError(
                f"High-poly material '{material_name}' uses unsupported Color Ramp interpolation "
                f"'{interpolation}'. Use Linear or Constant, or disable Respect Opacity."
            )
        elements = sorted(
            (
                (
                    float(getattr(element, "position", 0.0)),
                    float(getattr(getattr(element, "color", (0.0, 0.0, 0.0, 1.0)), "__getitem__", lambda _i: 0.0)(0)),
                )
                for element in (getattr(ramp, "elements", ()) or ())
            ),
            key=lambda item: item[0],
        )
        if not elements:
            elements = [(0.0, 0.0), (1.0, 1.0)]

        def evaluate_ramp(value, elements=tuple(elements), interpolation=interpolation):
            if value <= elements[0][0]:
                return elements[0][1]
            for index in range(1, len(elements)):
                right_position, right_value = elements[index]
                left_position, left_value = elements[index - 1]
                if value <= right_position:
                    if interpolation == "CONSTANT" or right_position <= left_position:
                        return left_value
                    factor = (value - left_position) / (right_position - left_position)
                    return left_value * (1.0 - factor) + right_value * factor
            return elements[-1][1]

        child_eval = child["eval"]
        return {
            **child,
            "eval": lambda rgba, child_eval=child_eval: evaluate_ramp(child_eval(rgba)),
            "identity": f"COLOR_RAMP:{interpolation}({child['identity']}):{elements!r}",
        }

    if node_type == "MATH":
        operation = str(getattr(node, "operation", "") or "").upper()
        supported = {
            "MULTIPLY": lambda a, b: a * b,
            "ADD": lambda a, b: a + b,
            "SUBTRACT": lambda a, b: a - b,
            "MINIMUM": min,
            "MAXIMUM": max,
            "LESS_THAN": lambda a, b: 1.0 if a < b else 0.0,
            "GREATER_THAN": lambda a, b: 1.0 if a > b else 0.0,
        }
        if operation not in supported:
            raise ValueError(
                f"High-poly material '{material_name}' uses unsupported opacity Math operation "
                f"'{operation}'. Use Multiply, Add, Subtract, Minimum, Maximum, or a comparison."
            )
        lhs = _opacity_socket_expression(node.inputs[0], material_name=material_name)
        rhs = _opacity_socket_expression(node.inputs[1], material_name=material_name)
        images = [item["image"] for item in (lhs, rhs) if item["image"] is not None]
        if len({id(image) for image in images}) > 1:
            raise ValueError(
                f"High-poly material '{material_name}' combines multiple opacity images. "
                "Flatten the opacity mask to one image or disable Respect Opacity."
            )
        fn = supported[operation]
        lhs_eval, rhs_eval = lhs["eval"], rhs["eval"]
        return {
            "image": images[0] if images else None,
            "eval": lambda rgba, fn=fn, lhs_eval=lhs_eval, rhs_eval=rhs_eval: fn(
                lhs_eval(rgba), rhs_eval(rgba)
            ),
            "identity": f"{operation}({lhs['identity']},{rhs['identity']})",
            "address": lhs["address"] if lhs["image"] is not None else rhs["address"],
            "filter": lhs["filter"] if lhs["image"] is not None else rhs["filter"],
        }

    raise ValueError(
        f"High-poly material '{material_name}' uses unsupported procedural opacity node "
        f"'{getattr(node, 'name', node_type)}'. Flatten the mask to an Image Texture Alpha "
        "feeding Principled Alpha, or disable Respect Opacity."
    )


def _material_opacity_source(material):
    """Return a supported effective-opacity expression, or None when fully opaque."""
    if material is None or not bool(getattr(material, "use_nodes", False)):
        return None
    name = str(getattr(material, "name", "") or "Material")
    nodes = tuple(getattr(getattr(material, "node_tree", None), "nodes", ()) or ())
    active_output = next(
        (
            node
            for node in nodes
            if getattr(node, "type", "") == "OUTPUT_MATERIAL"
            and bool(getattr(node, "is_active_output", False))
        ),
        None,
    )
    surface = active_output.inputs.get("Surface") if active_output is not None else None
    source_node = None
    if surface is not None and bool(getattr(surface, "is_linked", False)):
        source_node = getattr(tuple(surface.links)[0], "from_node", None)
    if source_node is None:
        source_node = next(
            (node for node in nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"),
            None,
        )
    source_type = str(getattr(source_node, "type", "") or "")

    if source_type == "BSDF_PRINCIPLED":
        expression = _opacity_socket_expression(
            source_node.inputs.get("Alpha"),
            material_name=name,
        )
    elif source_type == "BSDF_TRANSPARENT":
        expression = {
            "image": None,
            "eval": lambda _rgba: 0.0,
            "identity": "TRANSPARENT",
            "address": "REPEAT",
            "filter": "LINEAR",
        }
    elif source_type == "MIX_SHADER":
        shader_a = source_node.inputs[1]
        shader_b = source_node.inputs[2]
        node_a = getattr(tuple(shader_a.links)[0], "from_node", None) if bool(getattr(shader_a, "is_linked", False)) else None
        node_b = getattr(tuple(shader_b.links)[0], "from_node", None) if bool(getattr(shader_b, "is_linked", False)) else None
        a_transparent = getattr(node_a, "type", "") == "BSDF_TRANSPARENT"
        b_transparent = getattr(node_b, "type", "") == "BSDF_TRANSPARENT"
        if not a_transparent and not b_transparent:
            # Mixing two OPAQUE closures is just an opaque surface: layered Principled
            # setups, a Principled mixed with Emission, nested Mix Shaders. There is no
            # opacity to extract, so there is nothing to transport.
            #
            # This used to raise, which aborted the ENTIRE bake job with a message about
            # an opacity graph the artist had never set up. Mixing two shaders is one of
            # the most common material patterns there is, and Respect Opacity defaults to
            # on, so any such material made the bake fail outright.
            return None
        if a_transparent and b_transparent:
            raise ValueError(
                f"High-poly material '{name}' mixes two Transparent BSDFs, so its opacity "
                "cannot be resolved to a single mask. Flatten its opacity mask or disable "
                "Respect Opacity."
            )
        expression = _opacity_socket_expression(
            source_node.inputs[0],
            material_name=name,
        )
        if b_transparent:
            child_eval = expression["eval"]
            expression = {
                **expression,
                "eval": lambda rgba, child_eval=child_eval: 1.0 - child_eval(rgba),
                "identity": f"ONE_MINUS({expression['identity']})",
            }
    else:
        # An opaque closure needs no special transport. A graph containing
        # Transparent BSDF elsewhere is potentially non-opaque and must not be guessed.
        if any(getattr(node, "type", "") == "BSDF_TRANSPARENT" for node in nodes):
            raise ValueError(
                f"High-poly material '{name}' has an unsupported transparent surface graph. "
                "Use Principled Alpha or a Transparent/Principled Mix Shader, or disable Respect Opacity."
            )
        return None

    if expression["image"] is None:
        value = max(0.0, min(1.0, float(expression["eval"]((1.0, 1.0, 1.0, 1.0)))))
        if value >= 1.0 - 1.0e-7:
            return None
        expression["constant"] = value
    else:
        expression["constant"] = 1.0
    return expression


def _normalize_opacity_source_to_png(expression, workspace_path, *, identity: str) -> str | None:
    image = expression.get("image")
    if image is None:
        return None
    from array import array

    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return None
    source = array("f", [0.0]) * (width * height * 4)
    image.pixels.foreach_get(source)
    evaluator = expression["eval"]
    output = array("f", [0.0]) * (width * height * 4)
    for index in range(0, len(source), 4):
        value = max(
            0.0,
            min(
                1.0,
                float(
                    evaluator(
                        (
                            source[index],
                            source[index + 1],
                            source[index + 2],
                            source[index + 3],
                        )
                    )
                ),
            ),
        )
        output[index] = output[index + 1] = output[index + 2] = value
        output[index + 3] = 1.0
    content_key = hashlib.sha1(output.tobytes()).hexdigest()
    output_root = Path(workspace_path) / "material_inputs"
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"opacity_{hashlib.sha1((identity + content_key).encode()).hexdigest()[:16]}.png"
    if output_path.is_file():
        return str(output_path)
    if not _write_rgba_png_file(output_path, width, height, output):
        return None
    return str(output_path) if output_path.is_file() else None


def _collect_high_object_opacity_bindings(
    project, workspace_path, selected_group_names, *, warnings=None
):
    """Resolve supported opacity once per selected high object.

    Material-index sidecars are introduced separately; until then an evaluated
    high object must have one effective opacity expression across all slots.

    An opacity graph the projection cannot express is NOT fatal. Refusing the whole
    job took every other map down with it -- a Mapping node on a tiled cut-out alpha
    stopped albedo, roughness and the geometry maps from baking at all -- and the
    remedy the message offered ("disable Respect Opacity") is exactly the opaque
    treatment this falls back to. The refusal is reported as a warning naming the
    object so the artist can still see that the high baked opaque.
    """
    if not bool(getattr(project, "respect_opacity", True)):
        return {}
    resolved = {}
    for group in getattr(project, "groups", ()):
        group_name = str(getattr(group, "name", "") or "")
        if selected_group_names is not None and group_name not in selected_group_names:
            continue
        for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group)):
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            try:
                expressions = []
                for material_slot in getattr(obj, "material_slots", ()) or ():
                    material = getattr(material_slot, "material", None)
                    expression = _material_opacity_source(material)
                    if expression is not None:
                        expressions.append((material, expression))
                if not expressions:
                    continue
                if len(getattr(obj, "material_slots", ()) or ()) != 1:
                    raise ValueError(
                        f"High-poly object '{obj.name}' uses transparent opacity across multiple "
                        "material slots. Split the decal materials into separate objects, or disable Respect Opacity."
                    )
                material, expression = expressions[0]
                image_path = _normalize_opacity_source_to_png(
                    expression,
                    workspace_path,
                    identity=f"{obj.name}|{getattr(material, 'name', '')}|{expression['identity']}",
                )
                if expression["image"] is not None and not image_path:
                    raise ValueError(
                        f"High-poly opacity image for '{obj.name}' could not be exported. "
                        "Pack or save the image, or disable Respect Opacity."
                    )
            except ValueError as exc:
                message = f"Respect Opacity skipped for '{obj.name}': {exc}"
                if warnings is None:
                    print(f"[MasterBaker] {message}")
                elif message not in warnings:
                    warnings.append(message)
                continue
            resolved[int(obj.as_pointer())] = {
                "image_path": image_path or "",
                "constant": float(expression.get("constant", 1.0)),
                "address": str(expression.get("address", "REPEAT")),
                "filter": str(expression.get("filter", "LINEAR")),
            }
    return resolved


#: Bumped whenever the bytes this function writes change meaning, so workspaces
#: holding a file from an older encoding cannot serve it. v2 decodes display-referred
#: sources to scene-linear; v1 copied the stored values across untouched. v3 applies
#: the datablock's alpha_mode the way Cycles does at image load. v4 picks the decode
#: PER COLORSPACE instead of applying the sRGB EOTF to everything that was not
#: recognised as linear -- the ACES linear spaces were being darkened by it
#: (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P2). v5 also converts the ACES gamuts to
#: Rec.709; the curve fix alone still left them 12% off on the mean.
_MATERIAL_INPUT_ENCODING_VERSION = 5

#: Colorspaces whose stored values need the sRGB EOTF to reach scene-linear.
#:
#: `aces2065-1` and `acescg` USED to be in this set and are not display-referred at
#: all -- both are scene-linear. Putting them through the sRGB EOTF darkened every
#: texture tagged with one: measured at 0.2932 against Cycles' 0.4615 on the same
#: bake, 99.9% of texels over 8/255, with no warning anywhere
#: (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P2). The transfer function per space is now
#: chosen by `_colorspace_decoder` below instead of by one boolean.
_SRGB_ENCODED_COLORSPACES = {
    "srgb",
    "filmic srgb",
    "rec.709",
}

#: Log encodings. Each needs its own inverse; the sRGB EOTF is not close enough to
#: stand in for any of them.
_LOG_ENCODED_COLORSPACES = {
    "acescc",
    "acescct",
}

#: Already scene-linear: nothing to undo. `scene_linear` is spelled out because the
#: name-prefix test below looks for "linear" at the START and would otherwise call
#: the scene's own linear space display-referred.
_LINEAR_COLORSPACES = {
    "acescg",
    "aces2065-1",
    "scene_linear",
    "linear",
}


def _colorspace_name(image) -> str:
    settings = getattr(image, "colorspace_settings", None)
    return str(getattr(settings, "name", "") or "").strip().lower()


def _colorspace_is_display_referred(image) -> bool:
    """Whether this colorspace needs ANY decode. Kept for callers that only ask that."""
    return _colorspace_decoder(_colorspace_name(image)) is not None


def _colorspace_decoder(name: str):
    """The function that turns stored values into scene-linear, or None for linear.

    Returns a callable taking a numpy array. Rec.1886 and the Rec.2020 family are
    pure 2.4 gamma rather than sRGB's linear-toe curve, so they get their own
    branch; the difference is only visible in the bottom few percent of the range,
    but it costs nothing to be right about it.
    """
    if not name:
        return None
    if name in _LINEAR_COLORSPACES or name.startswith("non-color") or name.startswith("raw"):
        return None
    if name.startswith("linear"):
        return None
    if name in _LOG_ENCODED_COLORSPACES:
        return _acescc_to_linear if name == "acescc" else _acescct_to_linear
    if name in {"rec.1886", "rec.2020"}:
        return _gamma_2_4_to_linear
    if name in _SRGB_ENCODED_COLORSPACES:
        return _srgb_to_linear
    # Unknown / OCIO-config-specific names. sRGB variants vastly outnumber exotic
    # linear ones in real material graphs, so that stays the assumption -- but only
    # after every space we can actually name has been handled above.
    return _srgb_to_linear


#: Gamut conversions to scene-linear Rec.709, applied AFTER the transfer function.
#: The ACES spaces do not share Blender's working primaries, so decoding the curve
#: alone still leaves them wrong -- measured at 12% on the mean before these were
#: added. Values are the standard ACES matrices with the D60 -> D65 Bradford
#: adaptation OCIO uses; rows are Rec.709 R/G/B in terms of the source primaries.
_AP1_TO_REC709 = (
    (1.70505, -0.62179, -0.08326),
    (-0.13026, 1.14080, -0.01055),
    (-0.02400, -0.12897, 1.15297),
)
_AP0_TO_REC709 = (
    (2.52169, -1.13413, -0.38756),
    (-0.27648, 1.37272, -0.09624),
    (-0.01538, -0.15298, 1.16835),
)

#: Colorspace -> gamut matrix. Anything absent already uses Rec.709 primaries.
_COLORSPACE_PRIMARIES = {
    "acescg": _AP1_TO_REC709,
    "acescc": _AP1_TO_REC709,
    "acescct": _AP1_TO_REC709,
    "aces2065-1": _AP0_TO_REC709,
}


def _colorspace_primaries(name: str):
    return _COLORSPACE_PRIMARIES.get(str(name or "").strip().lower())


def _apply_primaries(values, matrix):
    """RGB rows through a 3x3 gamut matrix, in place-safe float64."""
    import numpy as np

    m = np.asarray(matrix, dtype=np.float64)
    return np.asarray(values, dtype=np.float64) @ m.T


def _gamma_2_4_to_linear(values):
    import numpy as np

    return np.power(np.clip(values, 0.0, None), 2.4)


def _acescc_to_linear(values):
    """Inverse ACEScc (S-2014-003). Below the toe the curve is offset, not clamped."""
    import numpy as np

    x = np.asarray(values, dtype=np.float64)
    toe = np.power(2.0, x * 17.52 - 9.72)
    return np.where(x < -0.3013698630136986, (toe - np.power(2.0, -16.0)) * 2.0, toe)


def _acescct_to_linear(values):
    """Inverse ACEScct (S-2016-001): a linear segment under 0.155251141552511."""
    import numpy as np

    x = np.asarray(values, dtype=np.float64)
    return np.where(
        x <= 0.155251141552511,
        (x - 0.0729055341958355) / 10.5402377416545,
        np.power(2.0, x * 17.52 - 9.72),
    )


def _srgb_to_linear(values):
    """Exact sRGB EOTF, matching what Blender's shader applies on sample."""
    import numpy as np

    return np.where(
        values <= 0.04045,
        values / 12.92,
        np.power((values + 0.055) / 1.055, 2.4),
    )


_PARALLEL_DEFLATE_MIN_BYTES = 4 * 1024 * 1024


def _parallel_zlib_compress(data, level: int) -> bytes:
    """A zlib stream of ``data``, deflated in slices on worker threads (pigz style).

    Each slice is raw deflate ended with a sync flush (the last one finished), so the
    concatenation is one valid deflate stream; the zlib header and the Adler-32 of the
    whole input wrap it. zlib releases the GIL, so 8 slices run on 8 cores: a 4K
    texture at level 6 took 0.45-1.5 s on one thread and 0.1-0.3 s like this, on the
    main thread of a bake prepare that encoded ten of them (24 s on fyrtest51). Each
    slice restarts the 32 KB window, which costs well under 0.1 % in size.
    """
    import zlib

    view = memoryview(data).cast("B")
    total = len(view)
    workers = max(1, min(8, (os.cpu_count() or 1)))
    if total < _PARALLEL_DEFLATE_MIN_BYTES or workers == 1:
        return zlib.compress(view, level)
    from concurrent.futures import ThreadPoolExecutor

    step = (total + workers - 1) // workers
    slices = [view[offset : offset + step] for offset in range(0, total, step)]
    last = len(slices) - 1

    def _deflate(index: int) -> bytes:
        compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
        body = compressor.compress(slices[index])
        return body + compressor.flush(zlib.Z_FINISH if index == last else zlib.Z_SYNC_FLUSH)

    with ThreadPoolExecutor(max_workers=len(slices)) as pool:
        bodies = list(pool.map(_deflate, range(len(slices))))
    adler = zlib.adler32(view) & 0xFFFFFFFF
    # 0x78 0x9C: deflate, 32 KB window, default-level flag; a valid header checksum.
    return b"\x78\x9c" + b"".join(bodies) + adler.to_bytes(4, "big")


def _write_rgba_png_bytes_file(path, width: int, height: int, rgba_u8) -> bool:
    """Write 8-bit RGBA rows (Blender bottom-up order) as a PNG, datablock-free.

    Bake prep used to write every workspace PNG through a temporary
    ``bpy.data.images.new`` + ``save`` + ``remove`` round trip. Removing an image
    datablock frees its GPU textures on the main thread, and Blender's material
    preview render job can be binding textures concurrently -- crashed as an
    EXCEPTION_ACCESS_VIOLATION inside GLStateManager::texture_bind during
    "Preparing high-poly meshes" (2026-08-24). Encoding the PNG directly leaves
    bpy.data.images untouched for the whole prepare phase.
    """
    import struct
    import zlib

    import numpy as np

    # Flipped rows go straight into the scanline buffer (no intermediate contiguous
    # copy), and zlib reads that buffer in place (no tobytes copy). Filter None: the
    # same writer packs per-corner data sidecars, which an Up filter made larger.
    rows = np.asarray(rgba_u8, dtype=np.uint8).reshape(height, width * 4)[::-1]
    scanlines = np.empty((height, width * 4 + 1), dtype=np.uint8)
    scanlines[:, 0] = 0  # filter byte 0 (None) per scanline
    scanlines[:, 1:] = rows
    return _write_png_scanlines_file(path, width, height, scanlines)


def _write_png_scanlines_file(path, width: int, height: int, scanlines) -> bool:
    """Encode ready PNG scanlines (filter byte 0 + RGBA8 per row, top row first) to
    ``path`` atomically. The shared tail of _write_rgba_png_bytes_file and the byte-backed
    LUT encoder, so both produce the same bytes for the same pixels."""
    import struct
    import zlib

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    encoded = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", _parallel_zlib_compress(memoryview(scanlines).cast("B"), 6))
        + _chunk(b"IEND", b"")
    )
    # Temp + replace, never a direct write: this also lands in the SHARED persistent
    # material-input cache, whose hit test is "the file exists". A second Blender
    # session encoding the same texture, or a crash mid-write, left a truncated PNG
    # that every later bake then fed to the backend until the cache was cleared.
    destination = Path(path)
    temporary = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, destination)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def _write_rgba_png_file(path, width: int, height: int, rgba_float) -> bool:
    """Quantize float RGBA (Blender pixel order) exactly like Blender's byte
    images (floor(v * 255 + 0.5), clamped) and write a PNG without touching
    bpy.data.images. See _write_rgba_png_bytes_file for why."""
    import numpy as np

    values = np.asarray(rgba_float, dtype=np.float32)
    quantized = np.clip(np.floor(values * 255.0 + 0.5), 0.0, 255.0).astype(np.uint8)
    return _write_rgba_png_bytes_file(path, width, height, quantized)


def _quantize_float_to_u8(values):
    """floor(v * 255 + 0.5) clamped to 0..255, exactly like Blender's byte images."""
    import numpy as np

    return np.clip(np.floor(values * 255.0 + 0.5), 0.0, 255.0).astype(np.uint8)


def _byte_lut_enabled() -> bool:
    return str(os.environ.get("FYR_BAKER_MATERIAL_PNG_LUT", "") or "").strip().upper() not in {
        "0", "OFF", "FALSE", "NO", "DISABLED",
    }


def _byte_backed_value_table(np_module, sample):
    """The float32 value of each byte 0..255 as Blender's ``Image.pixels`` returns it
    (byte * (1/255) in float32), or None when ``sample`` (a strided slice of the real
    pixels) is not made of exactly those values."""
    np = np_module
    ks = np.arange(256, dtype=np.float32)
    table = ks * np.float32(1.0 / 255.0)
    keys = np.floor(sample * np.float32(255.0) + np.float32(0.5)).astype(np.int64)
    if keys.size and (keys.min() < 0 or keys.max() > 255):
        return None
    if not np.array_equal(table[keys], sample):
        return None
    return table


def _encode_byte_backed_scanlines(pixels, width: int, height: int, decoder, alpha_mode: str):
    """PNG scanlines for a byte-backed image through 256-entry lookup tables, or None.

    A byte image's ``pixels`` are exactly k * (1/255) in float32, so decode, alpha
    association and the floor(v*255+0.5) quantize are each a function of a single byte
    per channel: the tables below run the SAME float32 expressions as the general path
    on the 256 possible values, and the image is then one gather per channel. Output is
    byte-identical to the general path (hash-checked on fyrtest51's materials and random
    images covering every byte value); anything that is not exactly byte-valued, has
    varying alpha under STRAIGHT association, or needs a gamut matrix returns None and
    takes the general path. Rows are written flipped (Blender is bottom-up) in slabs on
    worker threads; numpy releases the GIL for these array passes.
    """
    import numpy as np

    count = width * height
    if count <= 0 or pixels.size != count * 4:
        return None
    sample = pixels[:: max(1, pixels.size // 65537)]
    table = _byte_backed_value_table(np, sample)
    if table is None:
        return None
    px = pixels.reshape(height, width, 4)
    # Decode (per channel, elementwise) exactly as the general path: float32 in, astype
    # float32 out.
    if decoder is not None:
        decoded_table = np.ascontiguousarray(
            decoder(np.repeat(table[:, None], 3, axis=1)).astype(np.float32)
        )
        if not (
            np.array_equal(decoded_table[:, 0], decoded_table[:, 1])
            and np.array_equal(decoded_table[:, 0], decoded_table[:, 2])
        ):
            return None
        rgb_values = decoded_table[:, 0].copy()
    else:
        rgb_values = table.copy()
    alpha_table = table
    if alpha_mode == "STRAIGHT":
        alpha_plane = px[:, :, 3]
        low, high = float(alpha_plane.min()), float(alpha_plane.max())
        if low != high:
            return None
        rgb_values = (rgb_values * np.float32(low)).astype(np.float32)
    elif alpha_mode == "NONE":
        alpha_table = np.ones(256, dtype=np.float32)
    rgb_lut = _quantize_float_to_u8(rgb_values)
    alpha_lut = _quantize_float_to_u8(alpha_table)

    scanlines = np.empty((height, width * 4 + 1), dtype=np.uint8)
    scanlines[:, 0] = 0
    body = scanlines[:, 1:].reshape(height, width, 4)
    slab_rows = max(1, min(height, (1 << 22) // max(1, width)))
    slabs = [(y, min(height, y + slab_rows)) for y in range(0, height, slab_rows)]

    def _fill(span):
        y0, y1 = span
        block = px[y0:y1]
        keys = np.multiply(block, np.float32(255.0))
        keys += np.float32(0.5)
        keys = keys.astype(np.uint8)
        target = body[height - y1 : height - y0][::-1]
        target[:, :, 0:3] = rgb_lut[keys[:, :, 0:3]]
        target[:, :, 3] = alpha_lut[keys[:, :, 3]]

    workers = max(1, min(8, os.cpu_count() or 1, len(slabs)))
    if workers == 1:
        for span in slabs:
            _fill(span)
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_fill, slabs))
    return scanlines


def _persistent_material_input_path(image, cache_identity: str):
    """Where this decoded material input may be cached BETWEEN workspaces, or None.

    Every speculative PREPARE mints a fresh workspace, so a workspace-scoped cache
    never hits and each settings change re-encodes every texture on the main
    thread. Caching across workspaces is only correct while the source is provably
    unchanged, so the key carries the backing file's size and mtime on top of the
    caller's identity. Anything without such a token -- packed, generated, tiled,
    or edited-but-unsaved images -- returns None and keeps the per-workspace
    behaviour, which re-encodes and is therefore always right.
    """
    try:
        source = str(getattr(image, "source", "") or "").upper()
        if source not in {"FILE", "SEQUENCE"}:
            return None
        if bool(getattr(image, "is_dirty", False)):
            # Edited in Blender and not saved: the file on disk no longer describes
            # the pixels this would encode.
            return None
        if getattr(image, "packed_file", None) is not None:
            return None
        raw = bpy.path.abspath(
            str(getattr(image, "filepath", "") or ""), library=getattr(image, "library", None)
        )
        if not raw:
            return None
        stat = os.stat(raw)
        token = f"{stat.st_size}:{stat.st_mtime_ns}"

        from . import preferences

        root = Path(preferences.persistent_cache_root()) / "material_inputs"
        digest = hashlib.sha1(
            f"{cache_identity}|{token}".encode("utf-8", errors="replace")
        ).hexdigest()[:24]
        return root / f"detail_{digest}.png"
    except (OSError, AttributeError, TypeError, ValueError):
        return None


def _content_keyed_material_input_path(pixels, width, height, colorspace, alpha_mode, is_float):
    """Cache path of the decoded PNG for these exact pixels, or None when it cannot be keyed."""
    if str(os.environ.get("FYR_BAKER_CONTENT_KEYED_INPUTS", "1") or "1").strip().upper() in {"0", "OFF", "FALSE", "NO"}:
        return None
    try:
        from . import preferences

        digest = hashlib.blake2b(digest_size=12)
        digest.update(
            f"v{_MATERIAL_INPUT_ENCODING_VERSION}|{colorspace}|{alpha_mode}|{width}x{height}|{int(is_float)}".encode(
                "utf-8", errors="replace"
            )
        )
        try:
            # XXH3 reads the pixels at memory speed; blake2b would cost 0.3 s per 4K image.
            library = indexed_geometry._load_hash_library()
            digest.update(
                int(library.fyr_xxh3_64bits(pixels.ctypes.data, pixels.nbytes)).to_bytes(8, "little")
            )
        except Exception:
            digest.update(memoryview(pixels).cast("B"))
        root = Path(preferences.persistent_cache_root()) / "material_inputs"
        return root / f"content_{digest.hexdigest()}.png"
    except Exception:
        return None


def _normalize_material_image_to_png(image, workspace_path, *, identity: str) -> str | None:
    """Copy an arbitrary Blender image to a workspace-owned non-color PNG.

    The backend reads these resources RAW (``load_png_rgba_image_file`` divides the
    bytes by 255 and applies no transfer function) and works in scene-linear, so the
    file has to CONTAIN scene-linear values.

    ``Image.pixels`` returns the stored values and ignores the datablock's colorspace
    (verified on Blender 5.1: the same file tagged sRGB and Non-Color reads
    identically). Copying them straight across therefore shipped an sRGB-encoded
    texture as though it were linear: a byte of 128 reached the shading program as
    0.502 where Blender's own render sees 0.216. Baked albedo came out far too
    bright, and any channel derived from a color texture (a ramp driving roughness,
    for instance) was pushed the same way.
    """
    if image is None:
        return None
    material_input_root = Path(workspace_path) / "material_inputs"
    material_input_root.mkdir(parents=True, exist_ok=True)
    # The cache key must cover HOW the file was produced, not just which image it came
    # from. Without the version token every workspace that already holds a file written
    # by the pre-decode code would keep serving it, and the fix would never reach a user
    # who has baked this material before. The colorspace is part of the key for the same
    # reason: retagging a texture changes the correct contents of this file.
    colorspace = str(getattr(getattr(image, "colorspace_settings", None), "name", "") or "")
    alpha_mode = str(getattr(image, "alpha_mode", "STRAIGHT") or "STRAIGHT").strip().upper()
    cache_identity = "|".join(
        (f"v{_MATERIAL_INPUT_ENCODING_VERSION}", identity, colorspace, alpha_mode)
    )
    output_name = hashlib.sha1(cache_identity.encode("utf-8", errors="replace")).hexdigest()[:16]
    output_path = material_input_root / f"detail_{output_name}.png"
    if output_path.is_file():
        return str(output_path)

    # Cross-workspace reuse. The key above is stable for a given image, but the
    # DIRECTORY is not: the speculative PREPARE mints a new workspace on every
    # settings change, so this always missed and re-encoded every texture from
    # scratch -- on the main thread. Measured on a two-material asset: 0.08 s of
    # UI stall with 128px textures, 1.67 s with 2048px ones, on EVERY map-stack
    # interaction and never improving ("the map stack is a bit heavy and causes
    # Blender to freeze for a short time", tester 2026-08-24).
    #
    # A persistent copy is only safe when the source provably has not changed, so
    # the token is the backing file's size and mtime. A packed, generated or
    # unsaved-edited image has no such token and keeps re-encoding exactly as
    # before -- correctness first, speed only where it is provable.
    persistent_path = _persistent_material_input_path(image, cache_identity)
    if persistent_path is not None:
        try:
            if persistent_path.is_file():
                return str(persistent_path)
        except OSError:
            persistent_path = None

    try:
        import numpy as np

        width, height = int(image.size[0]), int(image.size[1])
        if width <= 0 or height <= 0:
            return None
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        if persistent_path is None:
            # Packed, generated or unsaved-edited images have no file token, so they
            # re-encoded in every workspace (stage 2 of a bake repeated stage 1's PNGs,
            # 3.96 s on fyrtest51 at 4K). The pixels themselves are the key instead: any
            # edit changes them, and the colour space, alpha mode and size are part of it.
            persistent_path = _content_keyed_material_input_path(
                pixels, width, height, colorspace, alpha_mode, bool(getattr(image, "is_float", True))
            )
            if persistent_path is not None:
                try:
                    if persistent_path.is_file():
                        return str(persistent_path)
                except OSError:
                    persistent_path = None
        rgba = pixels.reshape(-1, 4)
        colorspace_name = _colorspace_name(image)
        decoder = _colorspace_decoder(colorspace_name)
        primaries = _colorspace_primaries(colorspace_name)
        if (
            primaries is None
            and _byte_lut_enabled()
            and not bool(getattr(image, "is_float", True))
        ):
            lut_scanlines = _encode_byte_backed_scanlines(pixels, width, height, decoder, alpha_mode)
            if lut_scanlines is not None:
                lut_destination = output_path
                if persistent_path is not None:
                    try:
                        persistent_path.parent.mkdir(parents=True, exist_ok=True)
                        lut_destination = persistent_path
                    except OSError:
                        lut_destination = output_path
                if not _write_png_scanlines_file(lut_destination, width, height, lut_scanlines):
                    return None
                return str(lut_destination) if lut_destination.is_file() else None
        if decoder is not None or primaries is not None:
            # Decode RGB only. Alpha is always stored linearly.
            decoded = rgba[:, :3]
            if decoder is not None:
                decoded = decoder(decoded)
            if primaries is not None:
                decoded = _apply_primaries(decoded, primaries)
            rgba[:, :3] = decoded.astype(np.float32)
        # Apply the datablock's alpha_mode, which is what Cycles does when it loads
        # the image, not something the shading program can see afterwards:
        #   STRAIGHT       associate the alpha -> the Color output is colour x alpha,
        #                  which is why a cut-out texture renders black in its holes.
        #   PREMUL         the file is already associated; nothing to do.
        #   CHANNEL_PACKED alpha is unrelated data (a packed mask); leave both alone.
        #   NONE           ignore the stored alpha entirely; Alpha reads 1.0.
        # Sampling the raw RGB regardless, as this did until 2026-08-19, put the native
        # route at odds with both a Cycles render and the Cycles fallback of the same
        # material — measured as a fully lit albedo where Cycles baked black holes.
        if alpha_mode == "STRAIGHT":
            rgba[:, :3] *= rgba[:, 3:4]
        elif alpha_mode == "NONE":
            rgba[:, 3] = 1.0
        # Encode straight into the persistent cache when one is available, so the
        # NEXT settings change is a hit instead of another full re-encode.
        destination = output_path
        if persistent_path is not None:
            try:
                persistent_path.parent.mkdir(parents=True, exist_ok=True)
                destination = persistent_path
            except OSError:
                destination = output_path
        if not _write_rgba_png_file(destination, width, height, rgba.reshape(-1)):
            return None
        return str(destination) if destination.is_file() else None
    except Exception:
        return None


def _collect_material_ao_fast_path_png(
    map_item,
    project,
    workspace_path,
    selected_group_names,
) -> str | None:
    """Resolve one common AO image that the backend can reproject for all groups."""
    mode = str(
        getattr(map_item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
        or constants.MATERIAL_DETAIL_AUTO
    ).strip().upper()
    if mode == constants.MATERIAL_DETAIL_OFF:
        return None
    explicit_image = (
        getattr(map_item, "material_detail_image", None)
        if mode == constants.MATERIAL_DETAIL_MANUAL
        else None
    )
    common_image = None
    common_pointer = None
    for group in getattr(project, "groups", []):
        group_name = str(getattr(group, "name", "") or "")
        if selected_group_names is not None and group_name not in selected_group_names:
            continue
        image = _group_material_ao_source(group, explicit_image)
        if image is None:
            return None
        try:
            pointer = int(image.as_pointer())
        except Exception:
            pointer = id(image)
        if common_pointer is None:
            common_image = image
            common_pointer = pointer
        elif common_pointer != pointer:
            return None
    if common_image is None:
        return None
    identity = "|".join(
        (
            str(getattr(common_image, "name_full", getattr(common_image, "name", "")) or ""),
            str(getattr(common_image, "filepath", "") or ""),
            str(getattr(common_image, "source", "") or ""),
        )
    )
    return _normalize_material_image_to_png(
        common_image,
        workspace_path,
        identity=f"AO|{identity}",
    )


def _variance_detail_fields(map_item, detail_fp) -> dict:
    """Detail fields for a MATERIAL row that carries normal-variance compensation.

    Empty for every other row, so the material config it is spread into is byte-for-byte
    what it has always been unless this feature is switched on.
    """
    if not detail_fp or not _map_wants_normal_variance(map_item):
        return {}
    return {
        "material_detail_mode": str(detail_fp.get("mode", "") or ""),
        # NORMAL_VARIANCE does not derive an image, so the map-level strength field is
        # free to carry the artist's Amount slider instead.
        "material_detail_strength": float(
            getattr(map_item, "roughness_normal_variance_strength", 1.0)
        ),
        "material_detail_radius": int(detail_fp.get("radius", 8)),
        "material_detail_flip_green": bool(detail_fp.get("flip_green", False)),
        "material_detail_bindings": [
            protocol.MaterialDetailBinding(
                material_name=str(binding["material_name"]),
                image_path=str(binding["image_path"]),
                mode=str(binding["mode"]),
                strength=float(binding["strength"]),
                flip_green=bool(binding["flip_green"]),
                uv_transform=[float(v) for v in (binding.get("uv_transform") or [])],
            )
            for binding in (detail_fp.get("bindings") or [])
        ],
        "material_detail_slot_index_image_path": str(detail_fp.get("slot_sidecar", "") or ""),
        "material_detail_uv_transform": [
            float(v) for v in (detail_fp.get("uv_transform") or [])
        ],
    }


def _map_wants_normal_variance(map_item) -> bool:
    """True for a MATERIAL/Roughness row asking to carry the normal detail it loses.

    Minifying a bumpy normal map into a coarser bake averages its bumps to flat. The
    surface is still bumpy, so the lost variation belongs in roughness; without this the
    bake comes out shinier than the high poly, and shinier by an amount that changes with
    the bake resolution.
    """
    if str(getattr(map_item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
        return False
    channel = str(getattr(map_item, "material_channel", "") or "").strip().upper()
    if channel != constants.MATERIAL_CHANNEL_ROUGHNESS:
        return False
    return bool(getattr(map_item, "roughness_normal_variance", False))


def _collect_material_detail_fast_path(*args, **kwargs):
    """Resolve detail sources, rewriting the mode for a roughness variance row.

    The resolver picks a backend mode per source KIND (normal, bump, derivative,
    height). Roughness does not compose the detail normal at all -- it measures how
    much of it the bake resolution cannot store -- so every one of those collapses to
    a single mode here. Done as a wrapper because the resolver returns from several
    places and hooking one of them silently missed the others.
    """
    result = _collect_material_detail_fast_path_impl(*args, **kwargs)
    if not result or not _map_wants_normal_variance(args[0] if args else kwargs.get("map_item")):
        return result
    variance = constants.MATERIAL_DETAIL_BACKEND_NORMAL_VARIANCE
    result["mode"] = variance
    for binding in (result.get("bindings") or []):
        binding["mode"] = variance
    return result


def _collect_material_detail_fast_path_impl(
    map_item,
    project,
    workspace_path,
    selected_group_names,
    diagnostics=None,
    *,
    speculative: bool = False,
):
    """Resolve one common image-backed AO/normal detail source for the backend.

    The job carries ONE detail source per map, so the source has to be identical
    across every selected group and every material on their highs. When it is not,
    the detail is dropped and the map bakes from geometry alone. That drop used to
    be silent, which reads as "the bake is missing the normal detail" with nothing
    to act on; *diagnostics*, when given, collects a plain-language reason per map.
    """
    from . import project_structure

    map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()
    # A roughness row opting into variance compensation needs exactly the sources the
    # NORMAL map resolves -- the high materials' normal textures -- so it borrows this
    # whole resolution path and only differs in the mode it stamps on the result.
    variance_for_roughness = _map_wants_normal_variance(map_item)
    if variance_for_roughness:
        map_type = constants.MAP_NORMAL
    if map_type not in {constants.MAP_AO, constants.MAP_NORMAL}:
        return None
    mode = str(
        getattr(map_item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
        or constants.MATERIAL_DETAIL_AUTO
    ).strip().upper()
    if variance_for_roughness:
        # The roughness row has no detail-mode enum of its own; AUTO is what "resolve
        # the high materials' normal textures" means here.
        mode = constants.MATERIAL_DETAIL_AUTO
    if mode == constants.MATERIAL_DETAIL_OFF:
        return None

    map_label = naming.map_label(map_type)

    def _decline(reason: str, *, when_unasked: bool = False):
        # OFF is an explicit user choice and never reported. AUTO is the shipped
        # default, so "no material has a usable detail texture" there is not a
        # complaint -- it is the ordinary case for a procedural material, and warning
        # about it on every bake of every affected map is pure noise the artist cannot
        # act on (MATERIAL_BAKE_QA_2026_08_19_PASS2, G11). Declines that describe
        # something actually going wrong with detail that IS being applied pass
        # `when_unasked=True` and are always reported.
        if not when_unasked and mode == constants.MATERIAL_DETAIL_AUTO:
            return None
        if diagnostics is not None and reason and reason not in diagnostics:
            diagnostics.append(reason)
        return None

    explicit_image = (
        getattr(map_item, "material_detail_image", None)
        if mode == constants.MATERIAL_DETAIL_MANUAL and map_type == constants.MAP_AO
        else None
    )
    common_source = None
    common_key = None
    per_material: dict[str, tuple] = {}
    materials_without_source: list[str] = []
    # High objects carrying more than one material. A hit can only report the material
    # of the mesh RANGE it struck, and the exporter emits one range per object with that
    # object's FIRST material name, so nothing downstream can tell two materials on one
    # object apart. Per-material bindings are therefore only honest when every high
    # object owns exactly one material.
    multi_material_objects: list[str] = []
    if explicit_image is not None:
        common_source = (explicit_image, "AO_TEXTURE", 1.0, False, list(_IDENTITY_UV_TRANSFORM))
    else:
        for group in getattr(project, "groups", []):
            group_name = str(getattr(group, "name", "") or "")
            if selected_group_names is not None and group_name not in selected_group_names:
                continue
            materials = tuple(_iter_group_high_materials(group))
            if not materials:
                return _decline(
                    f"{map_label}: material detail skipped, the high meshes in "
                    f"'{group_name}' have no material."
                )
            for high_object in (
                project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH) or []
            ):
                object_materials = [
                    slot.material
                    for slot in (getattr(high_object, "material_slots", []) or [])
                    if slot is not None and slot.material is not None
                ]
                if len(object_materials) > 1:
                    name = str(getattr(high_object, "name", "") or "")
                    if name and name not in multi_material_objects:
                        multi_material_objects.append(name)
            for material in materials:
                material_name = str(getattr(material, "name", "") or "")
                source = _material_detail_source(material, map_type)
                if source is None:
                    # One material without a usable texture no longer vetoes the rest:
                    # its hits simply carry no detail, and every other material keeps
                    # its own. Recorded so the summary below can name them.
                    if material_name and material_name not in materials_without_source:
                        materials_without_source.append(material_name)
                    continue
                image, backend_mode, strength, flip_green, uv_transform = source
                # The detail is composed as tangent space. An object or world space
                # Normal Map node resolves to the same source and is then combined as
                # if it were tangent, which is silently wrong detail. material_ir
                # already refuses a non-tangent Normal Map ("not native yet"); this
                # path had no such check, so at least say so. Always reported: it
                # describes detail that IS being applied, not an absent one.
                if backend_mode in _NORMAL_MAP_DETAIL_MODES:
                    normal_space = _material_normal_map_space(material)
                    if normal_space and normal_space != "TANGENT":
                        notice = (
                            f"{map_label}: '{material_name or material}' has a Normal Map "
                            f"node set to {normal_space.replace('BLENDER_', '').title()} space. "
                            "Material detail is combined as tangent space, so this "
                            "material's detail will be wrong. Convert it to a tangent "
                            "space normal map, or turn Material Detail off for this map."
                        )
                        if diagnostics is not None and notice not in diagnostics:
                            diagnostics.append(notice)
                if material_name:
                    per_material[material_name] = source
                try:
                    image_key = int(image.as_pointer())
                except Exception:
                    image_key = id(image)
                key = (
                    image_key,
                    backend_mode,
                    round(float(strength), 7),
                    bool(flip_green),
                    tuple(round(float(v), 7) for v in uv_transform),
                )
                if common_key is None:
                    common_key = key
                    common_source = source
                elif common_key != key:
                    # Sources genuinely differ. That is no longer fatal: each material
                    # ships its own binding and the backend selects per hit. `common_*`
                    # stays at the first source purely to keep the legacy single-source
                    # fields populated, which is what gates the detail path on.
                    pass
    if common_source is None:
        if materials_without_source:
            detail_kind = "normal or bump" if map_type == constants.MAP_NORMAL else "AO"
            return _decline(
                f"{map_label}: material detail skipped, no high material has a usable "
                f"{detail_kind} texture (it needs a Principled BSDF with an image "
                f"texture on plain UVs). Checked: {', '.join(materials_without_source[:4])}."
            )
        return None
    if materials_without_source and per_material:
        # Partial coverage is worth saying out loud: those surfaces bake from geometry
        # alone while their neighbours carry detail, which looks like a bug otherwise.
        _decline(
            f"{map_label}: {len(materials_without_source)} material(s) have no usable "
            f"detail texture and bake from geometry alone "
            f"({', '.join(materials_without_source[:4])}).",
            when_unasked=True,
        )

    def _apply_material_only_mode(backend_mode: str) -> str:
        if mode != constants.MATERIAL_DETAIL_MATERIAL_ONLY or map_type != constants.MAP_NORMAL:
            return backend_mode
        if backend_mode == constants.MATERIAL_DETAIL_BACKEND_NORMAL_COMBINE:
            return constants.MATERIAL_DETAIL_BACKEND_NORMAL_REPLACE
        if backend_mode == constants.MATERIAL_DETAIL_BACKEND_HEIGHT_NORMAL:
            return constants.MATERIAL_DETAIL_BACKEND_HEIGHT_REPLACE
        return backend_mode

    def _binding_identity(source_image, resolved_mode: str) -> str:
        return "|".join(
            (
                map_type,
                resolved_mode,
                str(getattr(source_image, "name_full", getattr(source_image, "name", "")) or ""),
                str(getattr(source_image, "filepath", "") or ""),
                str(getattr(source_image, "source", "") or ""),
            )
        )

    def _build_bindings() -> list:
        """One binding per high material that has its own usable detail texture.

        Emitted when the materials genuinely disagree, and ALSO when coverage is
        partial (some materials resolved, some declined): without bindings the
        backend applies the single legacy source to EVERY hit, so a declined
        material silently borrowed its neighbour's normal map instead of baking
        from geometry alone as the warning promises (tester report 2026-08-24).
        A job where every material resolves to the same source keeps shipping the
        single legacy field alone, so its wire payload and its bake are unchanged.
        """
        partial_coverage = bool(materials_without_source)
        if not per_material or (len(per_material) < 2 and not partial_coverage):
            return []
        # Multi-material objects are handled by the per-triangle sidecar written by the
        # caller (see _collect_material_detail_fast_path's return); nothing to refuse
        # here any more. The sidecar itself still refuses multi-group selections.
        resolved: list[dict[str, object]] = []
        distinct: set[tuple] = set()
        for material_name, source in sorted(per_material.items()):
            source_image, source_mode, source_strength, source_flip, source_uv = source
            resolved_mode = _apply_material_only_mode(source_mode)
            # A tiled source has no single path to bind; those keep the legacy route.
            if str(getattr(source_image, "source", "") or "").upper() == "TILED":
                return []
            path = _normalize_material_image_to_png(
                source_image,
                workspace_path,
                identity=_binding_identity(source_image, resolved_mode),
            )
            if not path:
                return []
            resolved.append(
                {
                    "material_name": material_name,
                    "image_path": path,
                    "mode": resolved_mode,
                    "strength": float(source_strength),
                    "flip_green": bool(source_flip),
                    "uv_transform": [float(v) for v in source_uv],
                }
            )
            distinct.add(
                (
                    path,
                    resolved_mode,
                    round(float(source_strength), 7),
                    bool(source_flip),
                    tuple(round(float(v), 7) for v in source_uv),
                )
            )
        return resolved if (len(distinct) > 1 or partial_coverage) else []

    image, backend_mode, strength, flip_green, common_uv_transform = common_source
    backend_mode = _apply_material_only_mode(backend_mode)
    identity = "|".join(
        (
            map_type,
            backend_mode,
            str(getattr(image, "name_full", getattr(image, "name", "")) or ""),
            str(getattr(image, "filepath", "") or ""),
            str(getattr(image, "source", "") or ""),
        )
    )
    # A tiled (UDIM) detail source must fan out to one PNG per tile. image.pixels and
    # image.size on a TILED datablock expose only the ACTIVE tile, so normalizing it as a
    # single image would ship one tile's pixels and bake them over every tile.
    tiles = _material_detail_source_tiles(image, workspace_path, identity=identity)
    if tiles is not None:
        if not tiles:
            return None
        return {
            "path": tiles[0].image_path,
            "tiles": tiles,
            "mode": backend_mode,
            "strength": float(strength),
            "radius": 8,
            "flip_green": bool(flip_green),
            "bindings": [],
            # Tiled sources only qualify on the identity transform (tile selection
            # happens in untransformed UV space), so nothing to carry here.
            "uv_transform": [],
        }

    png_path = _normalize_material_image_to_png(
        image,
        workspace_path,
        identity=identity,
    )
    if not png_path:
        return None
    # The speculative PREPARE runs this whole export on the MAIN THREAD from a
    # timer, on every settings change and during the launch prewarm. The
    # per-material binding machinery below is far too heavy for that path: one PNG
    # encode per material, plus a slot sidecar that evaluates the high meshes and
    # rasterizes up to 400k triangles in Python. Before per-material bindings
    # became common (they used to require two materials with DIFFERENT sources),
    # this cost effectively never appeared here; once partial coverage started
    # emitting bindings it froze Blender for seconds per AA slider settle and
    # during startup warming (tester report 2026-08-24).
    #
    # The probe exists to prime the backend's GEOMETRY and scene caches, which do
    # not depend on which detail image each material uses, so it ships the legacy
    # single-source fields exactly as it did before bindings existed. Real bakes
    # still resolve per material. Worst case the probe's job differs enough that
    # the real bake re-runs PREPARE -- slower, never wrong.
    if speculative:
        return {
            "path": png_path,
            "tiles": [],
            "mode": backend_mode,
            "strength": float(strength),
            "radius": 8,
            "flip_green": bool(flip_green),
            "bindings": [],
            "slot_sidecar": "",
            "uv_transform": (
                []
                if _uv_transform_is_identity(common_uv_transform)
                else [float(v) for v in common_uv_transform]
            ),
        }
    bindings = _build_bindings()
    slot_sidecar = ""
    if bindings and multi_material_objects:
        # A high object with 2+ materials: name-based selection cannot tell its
        # faces apart, so ship the per-triangle binding index alongside.
        binding_index_by_material = {
            str(binding["material_name"]): index for index, binding in enumerate(bindings)
        }
        slot_sidecar = _write_material_slot_sidecar(
            project,
            workspace_path,
            selected_group_names,
            f"{map_type}_{hashlib.sha1(repr(sorted(binding_index_by_material)).encode()).hexdigest()[:12]}",
            binding_index_by_material,
        ) or ""
        if not slot_sidecar:
            # Sidecar could not be written: a multi-group selection (indices are only
            # meaningful within the group the backend concatenates into one scene) or
            # more than 254 bindings. Mesh size is no longer a reason -- the sidecar is
            # one byte per triangle now, not a rasterized UV mask.
            #
            # Bindings without the sidecar cannot tell a multi-material object's faces
            # apart, and dropping to the legacy single-source field would apply ONE
            # material's detail everywhere -- the exact borrow the bindings exist to
            # prevent. Skip the detail entirely so the message above stays true.
            _decline(
                f"{map_label}: material detail skipped, "
                f"{', '.join(multi_material_objects[:3])} carry more than one material "
                "and the per-triangle sidecar could not be written for this selection. "
                "Bake the groups one at a time.",
                when_unasked=True,
            )
            return None
    return {
        "path": png_path,
        "tiles": [],
        "mode": backend_mode,
        "strength": float(strength),
        "radius": 8,
        "flip_green": bool(flip_green),
        "bindings": bindings,
        "slot_sidecar": slot_sidecar,
        "uv_transform": (
            []
            if _uv_transform_is_identity(common_uv_transform)
            else [float(v) for v in common_uv_transform]
        ),
    }


def _material_detail_source_tiles(image, workspace_path, *, identity: str):
    """Per-tile PNGs for a tiled detail source, or ``None`` when the image is not tiled.

    ``None`` means "not a tiled image, use the ordinary single-image path". An empty list
    means "tiled but unusable" and disables the detail source rather than baking one tile's
    pixels everywhere.

    Only file-backed tiled images can be fanned out: each tile is read from its own file on
    disk. A packed or generated tiled image has no per-tile file and no way to read a
    non-active tile without mutating the user's datablock, which §6 forbids.
    """
    if image is None or str(getattr(image, "source", "") or "") != "TILED":
        return None

    import os

    from . import udim as _udim

    raw_path = bpy.path.abspath(
        str(getattr(image, "filepath", "") or ""), library=getattr(image, "library", None)
    )
    logical = os.path.normpath(raw_path) if raw_path else ""
    if not logical or not _udim.is_logical_udim_path(logical):
        return []

    tiles: list = []
    for tile_number, concrete_path in _udim.sibling_tile_paths(logical):
        tile_image = None
        try:
            tile_image = bpy.data.images.load(concrete_path, check_existing=False)
            tile_image.colorspace_settings.name = "Non-Color"
            png_path = _normalize_material_image_to_png(
                tile_image,
                workspace_path,
                identity=f"{identity}|tile{int(tile_number)}",
            )
        except Exception:
            png_path = None
        finally:
            if tile_image is not None:
                try:
                    image_cleanup.remove_image_when_safe(tile_image, reason="udim tile normalize")
                except Exception:
                    pass
        if not png_path:
            return []
        tiles.append(
            protocol.MaterialSourceTile(udim_tile=int(tile_number), image_path=str(png_path))
        )
    return tiles


def _image_tile_numbers(image):
    """Tile numbers the TILED datablock itself lists, or None when it cannot say.

    Cycles builds a UDIM image's tile list from the datablock (`image.tiles`), not from
    the directory, so a stray file beside the set is not part of it.
    """
    tiles = getattr(image, "tiles", None)
    if tiles is None:
        return None
    try:
        return {int(getattr(tile, "number")) for tile in tiles}
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_tiled_image_to_pngs(image, workspace_path, identity: str, occupied_tiles=None):
    """Per-tile workspace PNGs for a file-backed UDIM image, as a Material IR tile table.

    Returns ``(tiles, missing)``: ``tiles`` is ``[{"tile": n, "path": png}, ...]``
    ascending, ``missing`` the sorted tile numbers in ``occupied_tiles`` that have no
    file. ``occupied_tiles`` (the tiles the high poly's UVs actually reach, or None for
    "unknown, ship every tile") limits what is encoded; a tile nobody samples costs
    encode time and GPU memory for nothing. Returns None when the image cannot be read
    tile by tile or a tile fails to encode, which sends the channel to Cycles.

    Each tile is loaded as a temporary image that inherits the PARENT's colour space
    and alpha mode, then goes through `_normalize_material_image_to_png` like every
    other resource. The detail-map helper forces Non-Color, right for a normal map and
    wrong for albedo, and the old raw-file route (`_normalize_material_source_to_png`)
    did no decode at all.
    """
    import os

    from . import udim as _udim

    if image is None or str(getattr(image, "source", "") or "").upper() != "TILED":
        return None
    raw_path = bpy.path.abspath(
        str(getattr(image, "filepath", "") or ""), library=getattr(image, "library", None)
    )
    logical = os.path.normpath(raw_path) if raw_path else ""
    if not logical or not _udim.is_logical_udim_path(logical):
        return None
    on_disk = dict(_udim.sibling_tile_paths(logical))
    listed = _image_tile_numbers(image)
    if listed is not None:
        on_disk = {tile: path for tile, path in on_disk.items() if tile in listed}
    if occupied_tiles is None:
        wanted = sorted(on_disk)
        missing: list[int] = []
    else:
        occupied = {int(tile) for tile in occupied_tiles}
        wanted = sorted(tile for tile in occupied if tile in on_disk)
        missing = sorted(tile for tile in occupied if tile not in on_disk)

    colorspace = str(getattr(getattr(image, "colorspace_settings", None), "name", "") or "")
    alpha_mode = str(getattr(image, "alpha_mode", "") or "")
    tiles: list[dict] = []
    for tile_number in wanted:
        tile_image = None
        try:
            tile_image = bpy.data.images.load(on_disk[tile_number], check_existing=False)
            if colorspace:
                tile_image.colorspace_settings.name = colorspace
            if alpha_mode:
                tile_image.alpha_mode = alpha_mode
            png_path = _normalize_material_image_to_png(
                tile_image,
                workspace_path,
                identity=f"{identity}|tile{int(tile_number)}",
            )
        except Exception:
            png_path = None
        finally:
            if tile_image is not None:
                try:
                    image_cleanup.remove_image_when_safe(tile_image, reason="udim tile normalize")
                except Exception:
                    pass
        if not png_path:
            return None
        tiles.append({"tile": int(tile_number), "path": str(png_path)})
    return tiles, missing


def _export_group_meshes(
    project,
    group=None,
    depsgraph=None,
    meshes_root: Path | None = None,
    *,
    preserve_high_vertex_colors: bool = False,
    high_color_source: color_stream.ColorStreamSource | None = None,
    requires_high_uvs: bool = False,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
    cancel_check=None,
    opacity_by_object: dict[int, dict[str, object]] | None = None,
    skip_high: bool = False,
) -> protocol.BakeGroupConfig:
    if meshes_root is None:
        meshes_root = depsgraph
        depsgraph = group
        group = project
        project = None
    group_root = meshes_root / workspace.slugify_name(group.name)
    low_meshes = _export_low_mesh_refs(
        group,
        depsgraph,
        group_root,
        workspace_key=workspace_key,
        use_shared_memory=use_shared_memory,
    )
    if skip_high:
        # Low-only selection (Wireframe): nothing samples the high or the cage.
        return _build_group_config_from_exported_refs(project, group, low_meshes, [], [])
    high_meshes = _export_high_mesh_refs(
        group,
        depsgraph,
        group_root,
        preserve_vertex_colors=preserve_high_vertex_colors,
        color_source=high_color_source,
        requires_high_uvs=requires_high_uvs,
        workspace_key=workspace_key,
        use_shared_memory=use_shared_memory,
        cancel_check=cancel_check,
        opacity_by_object=opacity_by_object,
        self_material=str(getattr(project, "workflow", "") or "").strip().upper()
        == constants.WORKFLOW_MATERIAL,
    )
    cage_meshes = _export_cage_mesh_refs(
        group,
        depsgraph,
        group_root,
        high_mesh_refs=high_meshes,
        workspace_key=workspace_key,
        use_shared_memory=use_shared_memory,
    )
    return _build_group_config_from_exported_refs(project, group, low_meshes, high_meshes, cage_meshes)


def resolve_live_normal_preview_dimensions(project) -> tuple[int, int]:
    source_width = max(1, int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    source_height = max(1, int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION) or constants.DEFAULT_RESOLUTION))
    max_dimension = max(source_width, source_height)
    preview_max_dimension = int(round(max_dimension * float(constants.LIVE_NORMAL_PREVIEW_SCALE)))
    preview_max_dimension = max(constants.LIVE_NORMAL_PREVIEW_MIN_RESOLUTION, preview_max_dimension)
    preview_max_dimension = min(preview_max_dimension, constants.LIVE_NORMAL_PREVIEW_MAX_RESOLUTION)
    preview_max_dimension = min(preview_max_dimension, max_dimension)
    scale = 1.0 if max_dimension <= 0 else float(preview_max_dimension) / float(max_dimension)
    preview_width = max(1, int(round(source_width * scale)))
    preview_height = max(1, int(round(source_height * scale)))
    return preview_width, preview_height


def prepare_live_normal_preview_job(context, project, group) -> PreparedLivePreviewJob:
    depsgraph = context.evaluated_depsgraph_get()
    preview_root = workspace.ensure_directory(
        storage_cleanup.ensure_scratch_subdir("live_preview")
        / workspace.slugify_name(project.name)
        / workspace.slugify_name(group.name)
    )
    workspace_path = workspace.ensure_directory(preview_root / "workspace")
    meshes_root = workspace.ensure_directory(workspace_path / "meshes")
    output_dir = workspace.ensure_directory(preview_root / "outputs")
    progress_path = workspace_path / "progress.json"
    job_path = workspace_path / "job.mbjob"
    job_id = f"live_preview_{workspace.slugify_name(project.name)}_{workspace.slugify_name(group.name)}"
    group_root = workspace.ensure_directory(meshes_root / workspace.slugify_name(group.name))
    cache_key = _debug_overlay_cache_key(context, project, group)
    static_signature, dynamic_signature = debug_overlay_input_signature(project, group)
    use_shared_memory = mesh_transport.shared_memory_transport_enabled()
    cache_entry = _LIVE_PREVIEW_EXPORT_CACHE.get(cache_key)
    if cache_entry is None or cache_entry.static_signature != static_signature:
        opacity_by_object = _collect_high_object_opacity_bindings(
            project,
            workspace_path,
            {str(getattr(group, "name", "") or "")},
        )
        low_meshes = _export_low_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        high_meshes = _export_high_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
            opacity_by_object=opacity_by_object,
            self_material=str(getattr(project, "workflow", "") or "").strip().upper()
            == constants.WORKFLOW_MATERIAL,
        )
        cage_meshes = _export_cage_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        cache_entry = _DebugOverlayExportCacheEntry(
            workspace_path=workspace_path,
            group_root=group_root,
            static_signature=static_signature,
            dynamic_signature=dynamic_signature,
            low_meshes=low_meshes,
            high_meshes=high_meshes,
            cage_meshes=cage_meshes,
        )
        _LIVE_PREVIEW_EXPORT_CACHE[cache_key] = cache_entry
    elif cache_entry.dynamic_signature != dynamic_signature:
        cache_entry.cage_meshes = _export_cage_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        cache_entry.dynamic_signature = dynamic_signature

    group_config = _build_group_config_from_exported_refs(
        project,
        group,
        cache_entry.low_meshes,
        cache_entry.high_meshes,
        cache_entry.cage_meshes,
    )
    group_config.skew_correction_maps = _write_skew_correction_maps(group, Path(workspace_path) / "skew_correction")
    normal_map = properties.find_map_setting(project, constants.MAP_NORMAL)
    group_config.outputs = _build_output_targets(
        project,
        group,
        output_dir,
        selected_map_types={constants.MAP_NORMAL},
        selected_map_uuids={properties.ensure_map_setting_uuid(normal_map)} if normal_map is not None else None,
        # Throwaway preview: 8-bit uncompressed TGA is the cheapest encode, and it is
        # loaded straight into Blender, so the project's format/depth do not apply.
        bit_depth_override=constants.BIT_DEPTH_8,
        image_format_override=constants.IMAGE_FORMAT_TGA,
    )
    if not group_config.outputs:
        raise ValueError("Could not prepare a Normal output target for live preview")

    output_target = group_config.outputs[0]
    normal_format = (
        properties.effective_normal_format(normal_map)
        if normal_map is not None
        else constants.default_normal_format_for_map(constants.MAP_NORMAL)
    )
    normalized_normal_format = str(normal_format or "").strip().upper()
    if normalized_normal_format == constants.NORMAL_FORMAT_DIRECTX:
        flip_green = True
    elif normalized_normal_format == constants.NORMAL_FORMAT_OPENGL:
        flip_green = False
    else:
        flip_green = bool(getattr(normal_map, "flip_green", False)) if normal_map is not None else False
    preview_width, preview_height = resolve_live_normal_preview_dimensions(project)

    job = protocol.BakeJob(
        version=constants.PROTOCOL_VERSION,
        job_id=job_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        progress_path=str(progress_path),
        project=protocol.BakeProjectInfo(
            name=f"{project.name}_LivePreview",
            output_root=str(preview_root),
            workspace=str(workspace_path),
            resolution_width=preview_width,
            resolution_height=preview_height,
            bit_depth=int(constants.BIT_DEPTH_8),
            margin=(properties.effective_bake_margin(project, preview_width, preview_height)
                    if str(getattr(project, "margin_mode", constants.DILATION_DISTANCE)) == constants.DILATION_INFINITE
                    else min(properties.effective_bake_margin(project, preview_width, preview_height),
                             constants.LIVE_NORMAL_PREVIEW_MAX_MARGIN)),
            tangent_basis=constants.normalize_tangent_basis(getattr(project, "tangent_basis", constants.TANGENT_MIKKTSPACE)),
            bake_mode=constants.BAKE_MODE_DRAFT,
            anti_aliasing=constants.ANTI_ALIASING_1X,
            aa_samples=1,
            execution_backend=constants.EXECUTION_BACKEND_AUTO,
            image_format=constants.IMAGE_FORMAT_TGA,
            respect_opacity=bool(getattr(project, "respect_opacity", True)),
        ),
        maps=[
            protocol.BakeMapConfig(
                map_type=constants.MAP_NORMAL,
                map_uuid=properties.ensure_map_setting_uuid(normal_map) if normal_map is not None else "",
                enabled=True,
                samples=1,
                output_suffix=(getattr(normal_map, "output_suffix", "") or "").strip() if normal_map is not None else "",
                normal_space=str(getattr(normal_map, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)) if normal_map is not None else constants.MAP_NORMAL_SPACE_TANGENT,
                normal_format=normal_format,
                flip_green=flip_green,
            )
        ],
        groups=[group_config],
    )

    protocol.write_progress(
        progress_path,
        protocol.BakeProgress(
            status=constants.STATUS_EXPORTED,
            message="Live normal preview queued",
            active_group=str(getattr(group, "name", "") or ""),
            active_map=constants.MAP_NORMAL,
        ),
    )
    job_path = protocol.write_binary_job(job_path, job)
    return PreparedLivePreviewJob(
        job=job,
        job_path=job_path,
        progress_path=progress_path,
        workspace_path=workspace_path,
        output_path=Path(output_target.path),
        group_name=str(getattr(group, "name", "") or ""),
    )


def _bake_low_bounds_diagonal(project, selected_group_names, depsgraph) -> float:
    """World-space bounding-box diagonal of all low meshes being baked.

    AO "Relative to Bounds" distances are authored as a fraction of model size; the backend
    treats ao_distance as absolute units, so prepare_bake_job multiplies the fraction by this
    diagonal before sending. Maps are shared across groups, so we use the whole bake's bounds
    (the occlusion scale is the model as a whole, which is also what AO context depends on).
    """
    import mathutils

    mn = [float("inf"), float("inf"), float("inf")]
    mx = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        for slot in getattr(group, "low_meshes", ()):
            obj = getattr(slot, "object_ref", None)
            if obj is None or getattr(obj, "type", "") != "MESH":
                continue
            eval_obj = obj.evaluated_get(depsgraph) if depsgraph is not None else obj
            matrix_world = eval_obj.matrix_world
            for corner in eval_obj.bound_box:
                world = matrix_world @ mathutils.Vector(corner)
                for axis in range(3):
                    if world[axis] < mn[axis]:
                        mn[axis] = world[axis]
                    if world[axis] > mx[axis]:
                        mx[axis] = world[axis]
                found = True
    if not found:
        return 0.0
    dx, dy, dz = mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]
    return float((dx * dx + dy * dy + dz * dz) ** 0.5)


_LIGHTING_SUPPORTED_LIGHT_TYPES = frozenset({"POINT", "SPOT", "SUN", "AREA"})


def _job_has_lighting_maps(map_configs) -> bool:
    return any(
        config.map_type in (constants.MAP_LIGHTING, constants.MAP_LIT_COLOR)
        for config in map_configs
    )


def _resolve_lighting_engine(scene, requested: str) -> str:
    if str(requested or "").strip().upper() != constants.LIGHTING_ENGINE_AUTO:
        return str(requested).strip().upper()
    engine = str(getattr(getattr(scene, "render", None), "engine", "") or "").upper()
    if "EEVEE" in engine:
        return constants.LIGHTING_ENGINE_EEVEE
    return constants.LIGHTING_ENGINE_CYCLES


def _linking_collection_sets(collection) -> tuple[bool, list[str]]:
    """(only, names) of one light-linking collection, by Blender's rules.

    Each entry is Include or Exclude; a child collection's entry covers every object in
    it. Only includes: exactly those objects. Only excludes: everything else. Both: the
    includes minus the excludes. Returned as only=True with the member names, or
    only=False with the excluded names; no collection is (False, []), i.e. everything.
    """
    if collection is None:
        return False, []
    included: set[str] = set()
    excluded: set[str] = set()

    def _state(entry) -> str:
        linking = getattr(entry, "light_linking", None)
        return str(getattr(linking, "link_state", "INCLUDE") or "INCLUDE").upper()

    for obj, entry in zip(getattr(collection, "objects", ()) or (), getattr(collection, "collection_objects", ()) or ()):
        (excluded if _state(entry) == "EXCLUDE" else included).add(str(getattr(obj, "name", "") or ""))
    for child, entry in zip(getattr(collection, "children", ()) or (), getattr(collection, "collection_children", ()) or ()):
        names = {str(getattr(obj, "name", "") or "") for obj in getattr(child, "all_objects", ()) or ()}
        (excluded if _state(entry) == "EXCLUDE" else included).update(names)
    included.discard("")
    excluded.discard("")
    if included:
        return True, sorted(included - excluded)
    return False, sorted(excluded)


def _light_linking_fields(obj) -> dict:
    """Receiver and blocker sets of a light or emissive object (Blender light linking)."""
    original = getattr(obj, "original", obj)
    linking = getattr(original, "light_linking", None)
    receiver_only, receivers = _linking_collection_sets(getattr(linking, "receiver_collection", None))
    blocker_only, blockers = _linking_collection_sets(getattr(linking, "blocker_collection", None))
    return {
        "receiver_only": receiver_only,
        "receiver_objects": receivers,
        "blocker_only": blocker_only,
        "blocker_objects": blockers,
    }


def _light_linking_active(fields: dict) -> bool:
    return bool(fields["receiver_only"] or fields["receiver_objects"] or fields["blocker_only"] or fields["blocker_objects"])


def _build_scene_light_record(instance_object, matrix_world) -> protocol.SceneLightRecord | None:
    light_data = getattr(instance_object, "data", None)
    light_type = str(getattr(light_data, "type", "") or "").upper()
    if light_type not in _LIGHTING_SUPPORTED_LIGHT_TYPES:
        return None
    color = [float(component) for component in tuple(getattr(light_data, "color", (1.0, 1.0, 1.0)))[:3]]
    energy = float(getattr(light_data, "energy", 0.0))
    radius = float(getattr(light_data, "shadow_soft_size", 0.0)) if light_type in ("POINT", "SPOT") else 0.0
    sun_angle = float(getattr(light_data, "angle", 0.0)) if light_type == "SUN" else 0.0
    spot_size = float(getattr(light_data, "spot_size", 0.0)) if light_type == "SPOT" else 0.0
    spot_blend = float(getattr(light_data, "spot_blend", 0.0)) if light_type == "SPOT" else 0.0
    area_shape = str(getattr(light_data, "shape", "") or "") if light_type == "AREA" else ""
    area_size_x = float(getattr(light_data, "size", 0.0)) if light_type == "AREA" else 0.0
    if light_type == "AREA" and area_shape in ("RECTANGLE", "ELLIPSE"):
        area_size_y = float(getattr(light_data, "size_y", 0.0))
    elif light_type == "AREA":
        area_size_y = area_size_x
    else:
        area_size_y = 0.0
    matrix_values = _flatten_matrix(matrix_world)
    record = protocol.SceneLightRecord(
        identity=str(getattr(instance_object, "name", "") or ""),
        light_type=light_type,
        color=color,
        energy=energy,
        matrix_world=matrix_values,
        radius=radius,
        sun_angle=sun_angle,
        spot_size=spot_size,
        spot_blend=spot_blend,
        area_shape=area_shape,
        area_size_x=area_size_x,
        area_size_y=area_size_y,
        use_shadow=bool(getattr(light_data, "use_shadow", True)),
        diffuse_factor=float(getattr(light_data, "diffuse_factor", 1.0)),
        visible=True,
        specular_factor=float(getattr(light_data, "specular_factor", 1.0)),
        visible_diffuse=bool(getattr(instance_object, "visible_diffuse", True)),
        visible_glossy=bool(getattr(instance_object, "visible_glossy", True)),
        **_light_linking_fields(instance_object),
    )
    signature_links = (
        (record.receiver_only, tuple(record.receiver_objects), record.blocker_only, tuple(record.blocker_objects))
        if (record.receiver_only or record.receiver_objects or record.blocker_only or record.blocker_objects)
        else ()
    )
    record.cache_signature = _signature_cache_key(
        record.identity,
        record.light_type,
        tuple(record.color),
        record.energy,
        tuple(record.matrix_world),
        record.radius,
        record.sun_angle,
        record.spot_size,
        record.spot_blend,
        record.area_shape,
        record.area_size_x,
        record.area_size_y,
        record.use_shadow,
        record.diffuse_factor,
        # Linked lights only, so every unlinked light keeps its key.
        *((signature_links,) if signature_links else ()),
        # Likewise a Specular factor other than 1 and a hidden diffuse / glossy visibility.
        *((("specular", record.specular_factor),) if record.specular_factor != 1.0 else ()),
        *((("rays", record.visible_diffuse, record.visible_glossy),)
          if not (record.visible_diffuse and record.visible_glossy) else ()),
    )
    return record


def _collect_emitter_links(depsgraph) -> list[protocol.SceneEmitterLinkRecord]:
    """Light linking of mesh objects (emissive meshes light the scene in Cycles too)."""
    links: list[protocol.SceneEmitterLinkRecord] = []
    seen: set[str] = set()
    for instance in getattr(depsgraph, "object_instances", []) or []:
        instance_object = getattr(instance, "object", None)
        if instance_object is None or getattr(instance_object, "type", "") != "MESH":
            continue
        original = getattr(instance_object, "original", instance_object)
        name = str(getattr(original, "name", "") or "")
        if not name or name in seen or bool(getattr(original, "hide_render", False)):
            continue
        seen.add(name)
        fields = _light_linking_fields(original)
        if not _light_linking_active(fields):
            continue
        record = protocol.SceneEmitterLinkRecord(object_name=name, **fields)
        record.cache_signature = _signature_cache_key(
            name, record.receiver_only, tuple(record.receiver_objects), record.blocker_only, tuple(record.blocker_objects)
        )
        links.append(record)
    return links


_WORLD_ENV_CACHE_MAGIC = b"MBENVMP1"


def _resolve_direct_environment_image(color_input):
    """Return the Image of an Environment Texture node linked straight into the
    Background color input, or None for any other (procedural) graph."""
    links = getattr(color_input, "links", None) or ()
    if len(links) != 1:
        return None
    from_node = getattr(links[0], "from_node", None)
    if getattr(from_node, "type", "") != "TEX_ENVIRONMENT":
        return None
    vector_input = from_node.inputs.get("Vector") if hasattr(from_node, "inputs") else None
    if vector_input is not None and getattr(vector_input, "is_linked", False):
        # A mapping node changes orientation; treat as procedural until
        # rotation support lands.
        return None
    return getattr(from_node, "image", None)


def _write_world_environment_cache(image, cache_dir: Path) -> tuple[str, str]:
    """Write the image as a linear lat-long .mbenv blob (row 0 = v0/bottom,
    Cycles equirect convention). Returns (path, content_signature)."""
    import numpy

    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"Environment image '{image.name}' has no pixel data")
    channels = max(1, int(getattr(image, "channels", 4)))
    buffer = numpy.empty(width * height * channels, dtype=numpy.float32)
    image.pixels.foreach_get(buffer)
    pixels = buffer.reshape(height, width, channels)
    if channels >= 3:
        rgb = pixels[..., :3]
    else:
        rgb = numpy.repeat(pixels[..., :1], 3, axis=2)
    if not bool(getattr(image, "is_float", True)):
        # Byte images arrive in their display space; linearize sRGB.
        rgb = numpy.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    rgb = numpy.ascontiguousarray(rgb, dtype="<f4")
    signature = _signature_cache_key(
        "MBENV",
        getattr(image, "name", ""),
        getattr(image, "filepath", ""),
        width,
        height,
        bool(getattr(image, "is_float", True)),
    )
    cache_path = Path(cache_dir) / f"world_env_{signature}.mbenv"
    if not cache_path.exists():
        header = _WORLD_ENV_CACHE_MAGIC + struct.pack("<II", width, height)
        cache_path.write_bytes(header + rgb.tobytes())
    return str(cache_path), signature


def _build_scene_world_record(scene, env_cache_dir: Path | None = None) -> protocol.SceneWorldRecord:
    world = getattr(scene, "world", None)
    if world is None:
        return protocol.SceneWorldRecord(world_mode="NONE")
    if not getattr(world, "use_nodes", False):
        color = [float(component) for component in tuple(getattr(world, "color", (0.0, 0.0, 0.0)))[:3]]
        record = protocol.SceneWorldRecord(world_mode="COLOR", color=color, strength=1.0)
        record.cache_signature = _signature_cache_key("COLOR", tuple(color), 1.0)
        return record
    background_node = None
    node_tree = getattr(world, "node_tree", None)
    for node in getattr(node_tree, "nodes", []) or []:
        if getattr(node, "type", "") == "BACKGROUND":
            background_node = node
            break
    if background_node is None:
        return protocol.SceneWorldRecord(world_mode="NONE")
    color_input = background_node.inputs.get("Color") if hasattr(background_node, "inputs") else None
    strength_input = background_node.inputs.get("Strength") if hasattr(background_node, "inputs") else None
    strength = float(getattr(strength_input, "default_value", 1.0)) if strength_input is not None else 1.0
    if color_input is not None and getattr(color_input, "is_linked", False):
        environment_image = _resolve_direct_environment_image(color_input)
        if environment_image is not None and env_cache_dir is not None:
            try:
                cache_path, content_signature = _write_world_environment_cache(environment_image, env_cache_dir)
            except (ValueError, OSError, RuntimeError) as error:
                print(f"[MasterBaker] world environment cache export failed: {error}")
            else:
                record = protocol.SceneWorldRecord(
                    world_mode="HDRI",
                    strength=strength,
                    image_path=cache_path,
                )
                record.cache_signature = _signature_cache_key("HDRI", content_signature, strength)
                return record
        # Procedural graph (or no cache dir): the Blender-evaluated lat-long
        # reduction is not implemented yet; preflight warns, backend treats the
        # pathless HDRI record as no world contribution.
        record = protocol.SceneWorldRecord(world_mode="HDRI", strength=strength)
        record.cache_signature = _signature_cache_key("HDRI", strength)
        return record
    color_value = tuple(getattr(color_input, "default_value", (0.0, 0.0, 0.0, 1.0)))[:3] if color_input is not None else (0.0, 0.0, 0.0)
    color = [float(component) for component in color_value]
    record = protocol.SceneWorldRecord(world_mode="COLOR", color=color, strength=strength)
    record.cache_signature = _signature_cache_key("COLOR", tuple(color), strength)
    return record


_MATERIAL_OUTPUT_NODE_TYPE = "OUTPUT_MATERIAL"
_PRINCIPLED_NODE_TYPE = "BSDF_PRINCIPLED"
_EMISSION_NODE_TYPE = "EMISSION"
_DEFAULT_SCENE_ALBEDO = (0.8, 0.8, 0.8)


def _material_surface_shader(node_tree):
    """Return the shader node feeding the active Material Output's Surface input.

    Falls back to a lone Principled/Emission node when no output node is present
    (keeps duck-typed test graphs simple), or None for an untraceable graph."""
    nodes = list(getattr(node_tree, "nodes", None) or [])
    if not nodes:
        return None
    output_node = None
    for node in nodes:
        if getattr(node, "type", "") != _MATERIAL_OUTPUT_NODE_TYPE:
            continue
        output_node = node
        if bool(getattr(node, "is_active_output", False)):
            break
    if output_node is not None:
        inputs = getattr(output_node, "inputs", None)
        surface = inputs.get("Surface") if hasattr(inputs, "get") else None
        if surface is not None and bool(getattr(surface, "is_linked", False)):
            links = getattr(surface, "links", None) or ()
            if links:
                shader = getattr(links[0], "from_node", None)
                if shader is not None:
                    return shader
        # An output exists but nothing drives its surface: untraceable.
        return None
    for node in nodes:
        if getattr(node, "type", "") in (_PRINCIPLED_NODE_TYPE, _EMISSION_NODE_TYPE):
            return node
    return None


def _shader_vec3_input(node, socket_name):
    """(rgb list or None, is_linked) for a color socket, read unclamped so HDR
    emission survives."""
    inputs = getattr(node, "inputs", None)
    socket = inputs.get(socket_name) if hasattr(inputs, "get") else None
    if socket is None:
        return None, False
    value = tuple(getattr(socket, "default_value", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))[:3]
    return [float(component) for component in value], bool(getattr(socket, "is_linked", False))


def _shader_scalar_input(node, socket_name, default=1.0):
    inputs = getattr(node, "inputs", None)
    socket = inputs.get(socket_name) if hasattr(inputs, "get") else None
    if socket is None:
        return default, False
    try:
        value = float(getattr(socket, "default_value", default))
    except (TypeError, ValueError):
        value = default
    return value, bool(getattr(socket, "is_linked", False))


#: Side of the UV grid a material channel's average is taken over, and of the thumbnail
#: each of its images is reduced to first: one sample per thumbnail texel.
_CHANNEL_MEAN_GRID = 32
_CHANNEL_MEAN_THUMBNAIL = 32
_channel_mean_cache: dict[tuple, tuple[list[float], list[float]] | None] = {}


def _block_mean(pixels, size: int):
    """(h, w, c) -> (size, size, c) by plain block means (h, w >= size)."""
    import numpy as np

    height, width = pixels.shape[:2]
    rows = np.add.reduceat(pixels.astype(np.float64), (np.arange(size) * height) // size, axis=0)
    rows /= np.diff(np.append((np.arange(size) * height) // size, height))[:, None, None]
    cols = np.add.reduceat(rows, (np.arange(size) * width) // size, axis=1)
    cols /= np.diff(np.append((np.arange(size) * width) // size, width))[None, :, None]
    return cols.astype(np.float32)


def _image_mean_thumbnail(image, size: int | None = None):
    """(size, size, 4) linear float thumbnail of a Blender image (row 0 = v 1), or None.

    Averaging sRGB-encoded values darkens the mean, so every image is decoded before
    it is averaged down. Files are first shrunk by OpenImageIO to a size Python can
    hold, so a 4K texture never becomes a Python float buffer; packed or generated
    images read Blender's own pixels.
    """
    import numpy as np

    size = int(size or _CHANNEL_MEAN_THUMBNAIL)
    working = max(size * 16, 512) if size <= 64 else size * 2
    settings = getattr(image, "colorspace_settings", None)
    is_data = bool(getattr(settings, "is_data", False)) or str(getattr(settings, "name", "") or "") in {
        "Non-Color", "Linear Rec.709", "Linear", "Linear CIE-XYZ E", "scene_linear"
    }
    pixels = None
    encoded = False
    path = ""
    if getattr(image, "packed_file", None) is None and str(getattr(image, "source", "")) == "FILE":
        try:
            path = bpy.path.abspath(str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or ""))
        except Exception:
            path = ""
    if path and os.path.isfile(path):
        try:
            import OpenImageIO as oiio

            source = oiio.ImageBuf(path)
            spec = source.spec()
            channels = int(spec.nchannels)
            work_w = min(int(spec.width), working)
            work_h = min(int(spec.height), working)
            if (work_w, work_h) != (int(spec.width), int(spec.height)):
                source = oiio.ImageBufAlgo.resize(source, roi=oiio.ROI(0, work_w, 0, work_h, 0, 1, 0, channels))
            pixels = np.asarray(source.get_pixels(oiio.FLOAT), dtype=np.float32).reshape(work_h, work_w, channels)
            encoded = not is_data and spec.format.basetype not in (oiio.FLOAT, oiio.HALF, oiio.DOUBLE)
        except Exception:
            pixels = None
    if pixels is None:
        width, height = (int(v) for v in tuple(getattr(image, "size", (0, 0)))[:2])
        if width <= 0 or height <= 0 or width * height > 2048 * 2048:
            return None
        try:
            flat = np.empty(width * height * 4, dtype=np.float32)
            image.pixels.foreach_get(flat)
        except Exception:
            return None
        pixels = flat.reshape(height, width, 4)[::-1]  # Blender row 0 is v 0
        encoded = not is_data and not bool(getattr(image, "is_float", False))
    channels = int(pixels.shape[2])
    rgba = np.ones(pixels.shape[:2] + (4,), dtype=np.float32)
    rgba[..., :3] = pixels[..., :3] if channels >= 3 else pixels[..., :1]
    if channels in (2, 4):
        rgba[..., 3] = pixels[..., channels - 1]
    if encoded:
        rgb = np.clip(rgba[..., :3], 0.0, 1.0)
        rgba[..., :3] = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    if rgba.shape[0] < size or rgba.shape[1] < size:
        ys = (np.arange(size) * rgba.shape[0]) // size
        xs = (np.arange(size) * rgba.shape[1]) // size
        return rgba[ys][:, xs]
    return _block_mean(rgba, size)


#: Side of the grid read straight from an Image Texture plugged into a shader input: it
#: carries the texture's own detail into bounce colour and Specular Lighting.
_DIRECT_IMAGE_GRID = 256
_direct_image_grid_cache: dict[tuple, tuple[list[float], list[float]] | None] = {}


def _direct_image_grid(shader, socket_name: str, rgb: bool) -> tuple[list[float], list[float]] | None:
    """(mean, grid) of a shader input fed straight by an Image Texture node, or None.

    Only the plain case: the input's single link comes from an Image Texture with
    nothing on its Vector input (so it samples the active UV map with its own repeat).
    The image is decoded to linear and resized to _DIRECT_IMAGE_GRID squared; rows run
    v = (j + 0.5) / side like the material grids. rgb=False gives one value per texel:
    the Alpha output's alpha, else the colour's luminance (Blender's colour to float).
    """
    inputs = getattr(shader, "inputs", None)
    socket = inputs.get(socket_name) if hasattr(inputs, "get") else None
    links = getattr(socket, "links", None) or ()
    if socket is None or len(links) != 1:
        return None
    node = getattr(links[0], "from_node", None)
    if getattr(node, "type", "") != "TEX_IMAGE":
        return None
    vector = node.inputs.get("Vector") if hasattr(node, "inputs") else None
    if vector is not None and getattr(vector, "is_linked", False):
        return None
    if str(getattr(node, "projection", "FLAT")) != "FLAT" or str(getattr(node, "extension", "REPEAT")) != "REPEAT":
        return None
    image = getattr(node, "image", None)
    if image is None:
        return None
    from_alpha = str(getattr(getattr(links[0], "from_socket", None), "name", "")) == "Alpha"
    path = str(getattr(image, "filepath_raw", "") or "")
    try:
        stamp = os.path.getmtime(bpy.path.abspath(path)) if path else 0.0
    except (OSError, AttributeError):
        stamp = 0.0
    key = (str(getattr(image, "name", "")), path, stamp, bool(getattr(image, "is_dirty", False)), rgb, from_alpha)
    if key in _direct_image_grid_cache:
        cached = _direct_image_grid_cache[key]
        return (list(cached[0]), list(cached[1])) if cached is not None else None
    result = None
    try:
        import numpy as np

        pixels = _image_mean_thumbnail(image, _DIRECT_IMAGE_GRID)
        if pixels is not None:
            grid = np.asarray(pixels, dtype=np.float64)[::-1]  # thumbnail row 0 is v = 1
            if rgb:
                values = np.clip(grid[..., :3], 0.0, None)
                mean = [float(v) for v in values.reshape(-1, 3).mean(axis=0)]
                result = (mean, [float(v) for v in values.reshape(-1)])
            else:
                single = grid[..., 3] if from_alpha else (
                    0.2126 * grid[..., 0] + 0.7152 * grid[..., 1] + 0.0722 * grid[..., 2]
                )
                single = np.clip(single, 0.0, None)
                result = ([float(single.mean())] * 3, [float(v) for v in single.reshape(-1)])
    except Exception:
        result = None
    if len(_direct_image_grid_cache) > 128:
        _direct_image_grid_cache.clear()
    _direct_image_grid_cache[key] = result
    return (list(result[0]), list(result[1])) if result is not None else None


def _material_channel_mean(material, channel: str) -> list[float] | None:
    """Average linear RGB of one material channel over its 0-1 texture space, or None.

    Light bouncing off a textured surface picks up the texture's average colour, which
    is what emissive-surface lights carry (and bounces, where no texture reaches them).
    """
    result = _material_channel_grid(material, channel)
    return list(result[0]) if result is not None else None


#: Channel programs reading these have no UV-space pattern for the grid to sample.
_POSITION_ATTR_OPS = frozenset({"ATTR_GENERATED", "ATTR_OBJECT", "ATTR_POSITION", "ATTR_NORMAL", "ATTR_TRUE_NORMAL"})
#: (material name, channel) of every grid built from such a program since the last
#: _build_scene_lighting_config; it warns about them.
_position_dependent_channels: set[tuple[str, str]] = set()


def _program_reads_position(program) -> bool:
    return any(str(op.get("op", "")) in _POSITION_ATTR_OPS for op in (getattr(program, "ops", None) or ()))


def _material_channel_grid(material, channel: str) -> tuple[list[float], list[float]] | None:
    """(mean RGB, grid) of one material channel over its 0-1 texture space, or None.

    The channel's native program is evaluated over a stratified UV grid of
    _CHANNEL_MEAN_GRID squared cells; image taps read a small linear thumbnail, so the
    cost is the same for a 512 and an 8K texture. The grid is linear RGB, row j holding
    v = (j + 0.5) / grid: scene lighting's bounces read it as a small texture. Cached per
    material graph and image file state.
    """
    from . import material_ir

    try:
        program = material_ir.compile_channel_program(material, channel)
    except Exception:
        return None
    if not getattr(program, "native", False):
        return None
    reads_position = _program_reads_position(program)
    if reads_position:
        _position_dependent_channels.add((str(getattr(material, "name", "") or ""), channel))
    images = [resource.get("image") for resource in (program.resources or [])]
    image_keys = []
    for image in images:
        if image is None:
            image_keys.append(None)
            continue
        path = str(getattr(image, "filepath_raw", "") or "")
        try:
            stamp = os.path.getmtime(bpy.path.abspath(path)) if path else 0.0
        except OSError:
            stamp = 0.0
        image_keys.append((str(getattr(image, "name", "")), path, stamp, bool(getattr(image, "is_dirty", False))))
    try:
        program_key = json.dumps(program.wire_payload(), sort_keys=True, default=str)
    except Exception:
        return None
    key = (str(getattr(material, "name", "")), channel, program_key, tuple(image_keys))
    if key in _channel_mean_cache:
        cached = _channel_mean_cache[key]
        return (list(cached[0]), list(cached[1])) if cached is not None else None
    thumbnails = [_image_mean_thumbnail(image) if image is not None else None for image in images]
    size = _CHANNEL_MEAN_THUMBNAIL

    def _sample(index, u=0.0, v=0.0):
        thumb = thumbnails[index] if 0 <= index < len(thumbnails) else None
        if thumb is None:
            return (0.8, 0.8, 0.8, 1.0)
        x = int(math.floor((float(u) % 1.0) * size)) % size
        y = int(math.floor((1.0 - (float(v) % 1.0)) * size)) % size
        return tuple(float(c) for c in thumb[y, x])

    grid = _CHANNEL_MEAN_GRID
    total = [0.0, 0.0, 0.0]
    texels: list[float] = []
    try:
        for j in range(grid):
            for i in range(grid):
                # A position-driven program has no pattern over UV space: each cell samples a
                # different point of the unit texture space instead, and the grid below keeps
                # their average (the value at one point is no estimate of it).
                point = (
                    ((i * 0.6180339887 + j * 0.3819660113) % 1.0),
                    ((i * 0.7548776662 + j * 0.5698402910 + 0.25) % 1.0),
                    ((i * 0.4142135624 + j * 0.7320508076 + 0.5) % 1.0),
                ) if reads_position else (0.0, 0.0, 0.0)
                rgb = material_ir.evaluate_program_cpu(
                    program, _sample, uv=((i + 0.5) / grid, (j + 0.5) / grid),
                    generated_position=point, object_position=point, world_position=point,
                )
                for c in range(3):
                    value = float(rgb[c])
                    value = max(0.0, value) if math.isfinite(value) else 0.0
                    total[c] += value
                    texels.append(value)
        mean = [value / (grid * grid) for value in total]
        if reads_position:
            texels = [mean[k % 3] for k in range(grid * grid * 3)]
    except Exception:
        mean = None
    result = (mean, texels) if mean is not None else None
    if len(_channel_mean_cache) > 512:
        _channel_mean_cache.clear()
    _channel_mean_cache[key] = result
    return (list(result[0]), list(result[1])) if result is not None else None


def _build_scene_material_record(material) -> protocol.SceneMaterialRecord:
    """Constant diffuse/emission transport for one material. material_name matches
    the mesh-ref resolution (bare material.name) so the backend can match by name.
    Textured sockets keep their constant fallback value and set the textured flag."""
    name = str(getattr(material, "name", "") or "")
    albedo = list(_DEFAULT_SCENE_ALBEDO)
    emission = [0.0, 0.0, 0.0]
    has_textured_albedo = False
    has_textured_emission = False
    albedo_texture: list[float] = []
    albedo_texture_size = _CHANNEL_MEAN_GRID
    # Principled specular inputs (MBBJOB46); other surfaces have no specular lobe.
    roughness, metallic, specular_ior_level, ior = 0.5, 0.0, 0.0, 1.5
    specular_tint = [1.0, 1.0, 1.0]
    roughness_texture: list[float] = []
    metallic_texture: list[float] = []

    node_tree = getattr(material, "node_tree", None)
    if not bool(getattr(material, "use_nodes", False)) or node_tree is None:
        albedo = _resolve_rgb_triplet(getattr(material, "diffuse_color", None), fallback=_DEFAULT_SCENE_ALBEDO)
    else:
        shader = _material_surface_shader(node_tree)
        shader_type = getattr(shader, "type", "") if shader is not None else ""
        if shader_type == _PRINCIPLED_NODE_TYPE:
            base, base_linked = _shader_vec3_input(shader, "Base Color")
            if base is not None:
                albedo = base
            has_textured_albedo = base_linked
            roughness, roughness_linked = _shader_scalar_input(shader, "Roughness", 0.5)
            metallic, metallic_linked = _shader_scalar_input(shader, "Metallic", 0.0)
            specular_ior_level, _ = _shader_scalar_input(shader, "Specular IOR Level", 0.5)
            ior, _ = _shader_scalar_input(shader, "IOR", 1.5)
            tint, _ = _shader_vec3_input(shader, "Specular Tint")
            if tint is not None:
                specular_tint = list(tint)
            for linked, socket_name, channel, target in (
                (roughness_linked, "Roughness", constants.MATERIAL_CHANNEL_ROUGHNESS, roughness_texture),
                (metallic_linked, "Metallic", constants.MATERIAL_CHANNEL_METALNESS, metallic_texture),
            ):
                if not linked:
                    continue
                direct = _direct_image_grid(shader, socket_name, rgb=False)
                sampled = direct if direct is not None else _material_channel_grid(material, channel)
                if sampled is None:
                    continue
                if channel == constants.MATERIAL_CHANNEL_ROUGHNESS:
                    roughness = sampled[0][0]
                else:
                    metallic = sampled[0][0]
                # One value per texel (a direct image's own values, a material grid's red).
                values = sampled[1] if direct is not None else sampled[1][0::3]
                if max(values, default=0.0) - min(values, default=0.0) > 1e-4:
                    target.extend(values)
            emit_color, emit_color_linked = _shader_vec3_input(shader, "Emission Color")
            emit_strength, emit_strength_linked = _shader_scalar_input(shader, "Emission Strength", 1.0)
            if emit_color is not None:
                emission = [component * emit_strength for component in emit_color]
            has_textured_emission = emit_color_linked or emit_strength_linked
        elif shader_type == _EMISSION_NODE_TYPE:
            # Pure emitter: no diffuse albedo, radiance from Color * Strength.
            albedo = [0.0, 0.0, 0.0]
            emit_color, emit_color_linked = _shader_vec3_input(shader, "Color")
            emit_strength, emit_strength_linked = _shader_scalar_input(shader, "Strength", 1.0)
            if emit_color is not None:
                emission = [component * emit_strength for component in emit_color]
            has_textured_emission = emit_color_linked or emit_strength_linked
        else:
            # Any other surface graph: the native compiler knows what it means, and
            # the averages below replace these constants when it compiles.
            has_textured_albedo = True
            has_textured_emission = True
        # A texture (or any graph the sockets cannot express as one constant) reaches
        # the scene through its average: what light bouncing off the surface picks up.
        if has_textured_albedo:
            direct = (
                _direct_image_grid(shader, "Base Color", rgb=True) if shader_type == _PRINCIPLED_NODE_TYPE else None
            )
            sampled = direct if direct is not None else _material_channel_grid(material, constants.MATERIAL_CHANNEL_ALBEDO)
            if sampled is not None:
                albedo = sampled[0]
                # Bounces read the texture itself (a varying grid; a flat one is its mean).
                if max(sampled[1], default=0.0) - min(sampled[1], default=0.0) > 1e-4:
                    albedo_texture = sampled[1]
                    albedo_texture_size = _DIRECT_IMAGE_GRID if direct is not None else _CHANNEL_MEAN_GRID
        if has_textured_emission:
            mean = _material_channel_mean(material, constants.MATERIAL_CHANNEL_EMISSION)
            if mean is not None:
                emission = mean

    record = protocol.SceneMaterialRecord(
        material_name=name,
        albedo=albedo,
        emission=emission,
        has_textured_albedo=has_textured_albedo,
        has_textured_emission=has_textured_emission,
    )
    signature_parts = [
        record.material_name,
        tuple(record.albedo),
        tuple(record.emission),
        record.has_textured_albedo,
        record.has_textured_emission,
    ]
    if albedo_texture:
        record.albedo_texture_size = albedo_texture_size
        record.albedo_texture = albedo_texture
        # Only a textured record extends its key, so every other record keeps its key.
        signature_parts.append(_signature_cache_key(*(round(v, 6) for v in albedo_texture)))
    record.roughness = float(roughness)
    record.metallic = float(metallic)
    record.specular_ior_level = float(specular_ior_level)
    record.ior = float(ior)
    record.specular_tint = [float(v) for v in specular_tint]
    # One side for both grids: the larger; a smaller grid is repeated up to it.
    sides = [int(round(len(grid) ** 0.5)) for grid in (roughness_texture, metallic_texture) if grid]
    side = max(sides, default=0)
    record.roughness_texture = _upsample_grid(roughness_texture, side)
    record.metallic_texture = _upsample_grid(metallic_texture, side)
    record.specular_texture_size = side
    signature_parts.append(
        (
            round(record.roughness, 6),
            round(record.metallic, 6),
            round(record.specular_ior_level, 6),
            round(record.ior, 6),
            tuple(round(v, 6) for v in record.specular_tint),
            _signature_cache_key(*(round(v, 6) for v in roughness_texture)) if roughness_texture else "",
            _signature_cache_key(*(round(v, 6) for v in metallic_texture)) if metallic_texture else "",
        )
    )
    record.cache_signature = _signature_cache_key(*signature_parts)
    return record


def _collect_scene_materials(depsgraph, project=None, selected_group_names=None) -> list[protocol.SceneMaterialRecord]:
    """Unique materials of render-visible scene mesh instances (the participating
    scene per the lighting plan), plus a safety net over the job's bake targets in
    case a target is render-hidden. Deduped by material name; preview materials are
    skipped so records line up with _resolve_stable_material_name on the mesh refs."""
    materials: list[protocol.SceneMaterialRecord] = []
    seen: set[str] = set()

    def _consider_material(material) -> None:
        if material is None:
            return
        name = str(getattr(material, "name", "") or "")
        if not name or name.startswith(_PREVIEW_MATERIAL_NAME_PREFIX) or name in seen:
            return
        seen.add(name)
        materials.append(_build_scene_material_record(material))

    def _consider_object(obj) -> None:
        if obj is None or getattr(obj, "type", "") != "MESH":
            return
        for slot in getattr(obj, "material_slots", None) or ():
            _consider_material(getattr(slot, "material", None))

    for instance in getattr(depsgraph, "object_instances", []) or []:
        instance_object = getattr(instance, "object", None)
        if instance_object is None or getattr(instance_object, "type", "") != "MESH":
            continue
        original = getattr(instance_object, "original", instance_object)
        if bool(getattr(original, "hide_render", False)):
            continue
        _consider_object(instance_object)

    if project is not None:
        for group in getattr(project, "groups", []) or []:
            if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
                continue
            for slot in list(getattr(group, "low_meshes", ()) or ()) + list(properties.effective_high_mesh_slots(group)):
                _consider_object(getattr(slot, "object_ref", None))

    return materials


def _build_scene_lighting_config(
    context,
    depsgraph,
    map_configs,
    env_cache_dir: Path | None = None,
    project=None,
    selected_group_names=None,
    diagnostics: list[str] | None = None,
) -> protocol.SceneLightingConfig | None:
    if not _job_has_lighting_maps(map_configs):
        return None
    _position_dependent_channels.clear()
    lights: list[protocol.SceneLightRecord] = []
    for instance in getattr(depsgraph, "object_instances", []) or []:
        instance_object = getattr(instance, "object", None)
        if instance_object is None or getattr(instance_object, "type", "") != "LIGHT":
            continue
        original = getattr(instance_object, "original", instance_object)
        if bool(getattr(original, "hide_render", False)):
            continue
        record = _build_scene_light_record(instance_object, instance.matrix_world)
        if record is not None:
            lights.append(record)
    config = protocol.SceneLightingConfig(
        seed=0,
        lights=lights,
        world=_build_scene_world_record(getattr(context, "scene", None), env_cache_dir),
        materials=_collect_scene_materials(depsgraph, project=project, selected_group_names=selected_group_names),
        emitter_links=_collect_emitter_links(depsgraph),
        **_cycles_light_path_fields(getattr(context, "scene", None)),
    )
    if diagnostics is not None:
        labels = {
            constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
            constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
            constants.MATERIAL_CHANNEL_METALNESS: "Metallic",
        }
        used = {record.material_name for record in config.materials}
        for name, channel in sorted(_position_dependent_channels):
            if name not in used or channel not in labels:
                continue
            message = (
                f"Scene Lighting: the {labels[channel]} of material '{name}' is driven by object or "
                "position coordinates (for example a Noise texture on Generated). Bounces and "
                "Specular Lighting use its average there, without the pattern; feed the texture "
                "UV coordinates or bake it to an image for an exact result."
            )
            if message not in diagnostics:
                diagnostics.append(message)
    return config


def _cycles_light_path_fields(scene) -> dict:
    """The scene's Cycles Filter Glossy and Clamp Indirect (Blender's defaults when the
    Cycles settings are absent): Cycles rows bake bounce light with them, as Cycles does."""
    cycles = getattr(scene, "cycles", None)
    try:
        filter_glossy = float(getattr(cycles, "blur_glossy", 1.0))
        clamp_indirect = float(getattr(cycles, "sample_clamp_indirect", 10.0))
    except (TypeError, ValueError):
        filter_glossy, clamp_indirect = 1.0, 10.0
    return {"cycles_filter_glossy": max(filter_glossy, 0.0), "cycles_clamp_indirect": max(clamp_indirect, 0.0)}


def _cage_mode_hides_offset(cage_mode: str) -> bool:
    """True for the cage modes whose projection is driven by a cage MESH.

    `cage_offset` is a Distance-mode control: the backend only reads it to place the ray
    origin on that path (`cage_mode_uses_cage_segment`, master_baker_backend.cpp), and the
    UI hides the field entirely in these modes (ui.py / ui_group_editor.py /
    ui_sidebar_viewport.py all gate it on CAGE_MODE_DISTANCE). Whatever value the field
    still holds is therefore leftover state from before the cage mesh existed -- invisible
    and unreachable to the artist.
    """
    return str(cage_mode or "").strip().upper() in {
        constants.CAGE_MODE_CUSTOM,
        constants.CAGE_MODE_AUTOMATIC,
    }


def resolve_auto_height_half_range(project, depsgraph, selected_group_names=None) -> float:
    """Half-range for a HEIGHT row left on automatic (inner == outer == 0).

    The backend's own rule is ``max(group.cage_offset)`` over the job, which is right for
    Distance cages -- the estimator fits that offset to the low->high envelope, so it
    already tracks the relief. Measured on a 576-poly low vs 360k displaced high: estimated
    offset 0.0356 against a true half-relief of 0.0386, giving 255 distinct 8-bit levels.

    It is NOT right for the cage-mesh modes. There `cage_offset` is dead and hidden, so the
    range silently depended on a number the artist could neither see nor set -- and a group
    carrying 0 fell through the backend's ``height_half_range > 0`` guard entirely, back to
    +/-half the model diagonal. Same mesh, same relief, 8 of 256 levels instead of 255.

    So: Distance groups contribute their offset (unchanged behaviour), cage-mesh groups
    contribute a freshly measured low->high envelope instead of their stale field.
    """
    selected = set(selected_group_names or ())
    estimator = cage_offset_estimator.CageOffsetEstimator()
    half_range = 0.0
    for group in getattr(project, "groups", []):
        group_name = str(getattr(group, "name", "") or "")
        if selected and group_name not in selected:
            continue
        projection_state = _group_projection_settings_state(group)
        cage_mode = str(getattr(projection_state, "cage_mode", "") or "")
        if not _cage_mode_hides_offset(cage_mode):
            half_range = max(half_range, float(getattr(projection_state, "cage_offset", 0.0) or 0.0))
            continue
        low_objects = project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW)
        high_objects = project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH)
        if not low_objects or not high_objects:
            continue
        # estimate_group answers cached lows without building anything, reuses the Cage
        # Check overlay's memoized index when there is one, and otherwise visits the highs
        # one BVH tree at a time (the whole index kept every tree alive: ~12 GB and ~2 min
        # on SvAT's 87 M triangles, even when every estimate was already cached). Nothing
        # is memoized here; same measurement, same HEIGHT pixels.
        try:
            measurements = estimator.estimate_group(list(low_objects), list(high_objects), depsgraph)
        except Exception:
            measurements = []
        for measured in measurements:
            if measured:
                half_range = max(half_range, float(measured))
    return half_range


@dataclass(slots=True)
class _DetailTileTarget:
    path: str
    udim_tile: int
    width: int
    height: int
    tile_u: int
    tile_v: int


def _material_detail_tile_targets(output_targets, detail_uuid: str, tile_specs, tokenized_naming: bool) -> list:
    """Final output path, size and UV origin for every tile a detail layer lands on.

    Mirrors the per-tile matching of the material channel loop. Without a tile
    plan (or untokenized naming) there is exactly one untiled target.
    """
    from . import udim as _udim_mod

    detail_uuid = str(detail_uuid or "").strip()
    targets = [
        target
        for target in output_targets
        if str(getattr(target, "map_uuid", "") or "").strip() == detail_uuid
    ]
    if not targets:
        return []
    plan = list(tile_specs or []) if tokenized_naming else []
    if not plan:
        target = targets[0]
        return [_DetailTileTarget(path=str(target.path), udim_tile=0, width=0, height=0, tile_u=0, tile_v=0)]
    results: list[_DetailTileTarget] = []
    seen_paths: set[str] = set()
    for tile_spec in plan:
        tile_number = int(getattr(tile_spec, "udim_tile", 0) or 0)
        match = None
        for target in targets:
            target_tile = int(getattr(target, "udim_tile", 0) or 0)
            if tile_number and target_tile and target_tile != tile_number:
                continue
            match = target
            break
        if match is None:
            continue
        path = str(match.path)
        if path in seen_paths:
            continue
        seen_paths.add(path)
        tile_u = tile_v = 0
        if tile_number:
            tile_u, tile_v = _udim_mod.tile_origin(tile_number)
        results.append(_DetailTileTarget(
            path=path,
            udim_tile=tile_number,
            width=int(getattr(tile_spec, "width", 0) or 0),
            height=int(getattr(tile_spec, "height", 0) or 0),
            tile_u=int(tile_u),
            tile_v=int(tile_v),
        ))
    return results


#: Workspace of a prepare that is running right now, cleared the moment it hands its
#: PreparedJob back. Only the group-export loop used to clean up after itself, so any
#: raise after it -- a material row forced to the Fyr route on a non-native graph, "Enable
#: at least one output map", a job-write failure -- kept that job's pagefile-backed mesh
#: mappings for the rest of the session. The speculative prepare swallows the exception,
#: so an artist editing geometry with such a project leaked one workspace per edit,
#: invisibly.
_ACTIVE_PREPARE_WORKSPACE: str = ""


def _release_incomplete_prepare() -> None:
    global _ACTIVE_PREPARE_WORKSPACE
    workspace_path = _ACTIVE_PREPARE_WORKSPACE
    _ACTIVE_PREPARE_WORKSPACE = ""
    if not workspace_path:
        return
    try:
        indexed_geometry.wait_for_workspace_canonical_writes(workspace_path)
        high_mesh_cache.finalize_pending_canonical_aliases()
    except Exception:
        pass
    try:
        mesh_transport.release_workspace_shared_memory(workspace_path)
        storage_cleanup.delete_workspaces((Path(workspace_path),))
    except Exception:
        pass


def _without_incomplete_groups(project, selected_group_names):
    """Leave groups that cannot bake yet (no low, or no high source) out of the job.

    ``None`` means every group. The selection only narrows when a bakeable group
    remains: a job made solely of incomplete groups keeps them, so it still fails
    with the specific missing-mesh error instead of baking nothing.
    """
    from . import validation

    incomplete = set(validation.incomplete_group_names(project))
    if not incomplete:
        return selected_group_names
    candidates = (
        {str(getattr(group, "name", "") or "") for group in getattr(project, "groups", [])}
        if selected_group_names is None
        else set(selected_group_names)
    )
    remaining = {name for name in candidates if name.strip() and name not in incomplete}
    return remaining if remaining else selected_group_names


def selection_needs_high_geometry(project, map_types=None, map_uuids=None) -> bool:
    """False when every selected row is drawn from the low mesh alone (Wireframe).

    Such a bake never samples the high-poly, so prepare skips the high export, the
    high cache warm-up, the cage fits and the park. An empty selection and the
    Material workflow stay True: the former errors later with its own message, the
    latter self-bakes through a different geometry path.
    """
    if str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL:
        return True
    rows = list(_selected_project_maps(project, _as_set(map_types), _as_set(map_uuids)))
    if not rows:
        return True
    return any(
        str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_WIREFRAME
        for item in rows
    )


def _as_set(values):
    if values is None:
        return None
    return {str(value or "").strip() for value in values if str(value or "").strip()}


def output_selection_has_work(map_configs, has_material_maps: bool, has_wireframe_rows: bool) -> bool:
    """Backend rows, addon-side Material rows or addon-drawn Wireframe rows each make a bake."""
    return bool(map_configs) or bool(has_material_maps) or bool(has_wireframe_rows)


_JOB_INDEXED_TRANSPORT: bool | None = None


def prepare_bake_job(context, project, *args, **kwargs) -> PreparedJob:
    """Build a bake job, releasing its workspace if anything below fails."""
    _selection_types = kwargs["map_types"] if "map_types" in kwargs else (args[0] if len(args) > 0 else None)
    _selection_uuids = kwargs["map_uuids"] if "map_uuids" in kwargs else (args[1] if len(args) > 1 else None)
    if not kwargs.get("speculative", False) and selection_needs_high_geometry(
        project, _selection_types, _selection_uuids
    ):
        # A bake started before Auto-Build's queued Distance offset fits finished must
        # read the fitted offsets, not the 2 cm default they start on.
        distance_offset_queue.fit_now(project)
        # Groups switched to Distance after Auto-Build were never queued.
        distance_offset_queue.fit_unfitted_now(context, project)
    collection_index.open_scope()
    global _JOB_INDEXED_TRANSPORT
    # One transport for every group of the job: enabled() can flip while the job is built
    # (the backend probe is asynchronous), and the batches of one job share a scene.
    _JOB_INDEXED_TRANSPORT = bool(indexed_geometry.enabled())
    try:
        with high_mesh_cache.defer_persistence():
            prepared = _prepare_bake_job(context, project, *args, **kwargs)
    except BaseException:
        _release_incomplete_prepare()
        raise
    finally:
        _JOB_INDEXED_TRANSPORT = None
        collection_index.close_scope()
    global _ACTIVE_PREPARE_WORKSPACE
    _ACTIVE_PREPARE_WORKSPACE = ""
    return prepared


def _prepare_bake_job(
    context,
    project,
    map_types: list[str] | tuple[str, ...] | set[str] | None = None,
    map_uuids: list[str] | tuple[str, ...] | set[str] | None = None,
    group_names: list[str] | tuple[str, ...] | set[str] | None = None,
    *,
    dirty_object_names_by_group: dict[str, set[str]] | None = None,
    preserve_latest_outputs: bool = False,
    use_shared_memory: bool = False,
    use_binary_job_transport: bool = True,
    cancel_check=None,
    # True only for the speculative PREPARE probe, which runs on the main thread
    # from a timer after every settings change. It skips export work that exists
    # solely to make a BAKE correct (per-material detail bindings and their slot
    # sidecar) and would otherwise freeze the UI. Never set this for a real bake.
    speculative: bool = False,
    # {"map_uuid", "flip_green"} of the Normal row baked just before this job, whose
    # retained texels the AO / Cavity / Curvature rows shade from
    # (bake_dependencies.BakePhasePlan.material_normal_source). None = raw hit normals.
    # "composite": the groups bake their Normal in passes of their own, so the passes add to
    # and the rows read the per-texture-set composite; a pass names no map_uuid.
    material_normal_source: dict | None = None,
    # Rows baked only as the material-normal source of this run's other maps (a Normal
    # row the artist did not select): their files go to the job workspace instead of the
    # output folder (bake_dependencies.BakePhasePlan.normal_first_source_only).
    source_only_map_uuids: list[str] | tuple[str, ...] | set[str] | None = None,
    # Only the bake operator, which queues the follow-up phases, may set this: a Normal
    # row whose detail compiles natively for some groups but not for the whole selection
    # then skips the hidden Cycles layer for those groups (PreparedJob.
    # deferred_native_normal_groups). Any other caller keeps the Cycles layer.
    native_normal_group_phases: bool = False,
    # A pass that holds only some of a texture set's groups (a follow-up merging one group
    # onto the finished bake, a user subset bake): write only the UDIM tiles those groups
    # touch (_prime_own_tile_plan).
    own_tiles_only: bool = False,
) -> PreparedJob:
    properties.ensure_default_maps(project)
    if not preserve_latest_outputs:
        properties.reset_latest_outputs(project)
    properties.reset_runtime_state(project)
    # Start each job with an empty slate: an export that was cancelled part way through
    # must not carry its cage warnings into the next bake's report.
    reset_cage_fit_warnings()
    selected_map_types = None
    if map_types is not None:
        selected_map_types = {
            str(map_type or "")
            for map_type in map_types
            if str(map_type or "").strip()
        }
    selected_map_uuids = None
    if map_uuids is not None:
        selected_map_uuids = {
            str(map_uuid or "").strip()
            for map_uuid in map_uuids
            if str(map_uuid or "").strip()
        }
    selected_group_names = None
    if group_names is not None:
        selected_group_names = {
            str(group_name or "")
            for group_name in group_names
            if str(group_name or "").strip()
        }
    selected_group_names = _without_incomplete_groups(project, selected_group_names)
    # A job carries ONE corner colour stream (color_stream). Rows that need another
    # source stay out of this job and come back as follow-up stages, which the bake
    # operator queues from PreparedJob.deferred_color_stream_stages.
    color_source, deferred_color_stream_stages, selected_map_uuids = _partition_color_stream_rows(
        project, selected_map_types, selected_map_uuids
    )

    needs_high_geometry = selection_needs_high_geometry(project, selected_map_types, selected_map_uuids)
    depsgraph = context.evaluated_depsgraph_get()
    output_root, is_default_root = resolve_output_root(project)
    blend_file_name = Path(bpy.data.filepath).stem if bpy.data.filepath else None
    output_dir = workspace.ensure_directory(workspace.build_project_output_dir(output_root, project.name, blend_file_name if is_default_root else None))
    job_id = workspace.build_job_id(project.name)
    workspace_path = workspace.ensure_directory(workspace.build_job_workspace(output_root, job_id))
    _reset_group_triangle_sidecars(workspace_path)
    global _ACTIVE_PREPARE_WORKSPACE
    _ACTIVE_PREPARE_WORKSPACE = str(workspace_path)
    mesh_transport.release_workspace_shared_memory(workspace_path)
    meshes_root = workspace.ensure_directory(workspace_path / "meshes")
    _source_only_uuids = {
        str(value or "").strip() for value in (source_only_map_uuids or ()) if str(value or "").strip()
    }
    _source_only_dirs: dict[str, Path] = (
        {
            map_uuid: workspace.ensure_directory(workspace_path / SOURCE_ONLY_OUTPUT_DIR_NAME)
            for map_uuid in _source_only_uuids
        }
        if _source_only_uuids
        else {}
    )
    # Derivative rows: the backend bakes their tangent normal into a hidden source that
    # derived_outputs converts after the bake, so a partial live rebake always updates
    # a real normal and never a file that already holds slopes.
    _redirect_dirs: dict[str, Path] = dict(_source_only_dirs)
    for _derivative_row in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if naming.normal_row_is_derivative(_derivative_row):
            _redirect_dirs.setdefault(
                properties.ensure_map_setting_uuid(_derivative_row),
                workspace.ensure_directory(derived_outputs.derivative_source_dir(output_root, project.name)),
            )
    derived_output_entries: list[dict] = []
    progress_path = workspace_path / "progress.json"
    job_path = workspace_path / "job.mbjob" if use_binary_job_transport else workspace_path / "job.json"
    preserve_high_vertex_colors = color_source is not None

    # Resolve image-texture material fast paths before choosing the high geometry
    # transport. FYRGEOM1 intentionally has no high-mesh UV section, so only jobs
    # that actually use the backend material fast path retain the legacy FYMESH
    # representation needed for hit-UV interpolation.
    # MATERIAL-workflow (Bake Selected Materials) uses the same Fyr Material IR
    # path: native channels go to the backend; only non-native rows become Cycles
    # specs. Job geometry still self-bakes (empty High role → low mesh as source).
    is_material_workflow = str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL
    _mat_fp_by_uuid: dict[str, dict | None] = {}
    material_detail_diagnostics: list[str] = []
    _material_detail_fp_by_uuid: dict[str, dict[str, object] | None] = {}
    for _detail_item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if str(getattr(_detail_item, "map_type", "") or "").strip().upper() not in {
            constants.MAP_AO,
            constants.MAP_NORMAL,
        } and not _map_wants_normal_variance(_detail_item):
            continue
        _detail_uuid = properties.ensure_map_setting_uuid(_detail_item)
        _material_detail_fp_by_uuid[_detail_uuid] = _collect_material_detail_fast_path(
            _detail_item,
            project,
            workspace_path,
            selected_group_names,
            diagnostics=material_detail_diagnostics,
            speculative=speculative,
        )
    # A tangent Normal row whose high-material normal graph (Bevel, Bump, ...) compiles
    # natively bakes as the MATERIAL NORMAL channel instead of a geometry normal plus a
    # hidden Cycles detail layer. Compiled with ray ops allowed first: whether they may
    # stay is only known once every row of the job has been classified below.
    _normal_group_phases: dict[str, list[str]] = {}
    _normal_native_rows = _collect_native_normal_rows(
        project,
        workspace_path,
        selected_map_types,
        selected_map_uuids,
        selected_group_names,
        is_material_workflow=is_material_workflow,
        detail_fp_by_uuid=_material_detail_fp_by_uuid,
        diagnostics=material_detail_diagnostics,
        group_phases_out=_normal_group_phases if (native_normal_group_phases and not speculative) else None,
        group_phase_excluded_uuids=_source_only_uuids,
    )
    # Material IR secondary-ray opcodes ("AO" / "BEVEL" / "RAYCAST") only execute in the
    # backend's MATERIAL_ONLY shading permutation, which it selects only for an
    # all-material batch. Prove that here before letting the compiler emit
    # one; otherwise the graph compiles to Cycles instead. The DXR half of the
    # contract is enforced backend-side (enforce_material_ir_ray_op_route).
    _allow_ray_ops = _job_is_material_only_backend_batch(
        project, selected_map_types, selected_map_uuids,
        native_normal_uuids=set(_normal_native_rows),
    )
    if not _allow_ray_ops:
        # Mixed job: a ray-op Normal row cannot run native here, so it keeps the
        # geometry + Cycles-detail route. (The bake operator normally defers such a
        # row to the all-material phase before this point is reached.)
        from . import material_ir as _nn_material_ir

        for _nn_uuid in [
            uuid for uuid, (_row, source) in _normal_native_rows.items()
            if _nn_material_ir.program_uses_ray_opcodes(source["program"])
        ]:
            del _normal_native_rows[_nn_uuid]
            # Say so: this costs the artist a Cycles pass, and "why is the bevel slow
            # today" is otherwise unanswerable from the console.
            print(
                "[Fyr Baker] Normal map detail uses a ray node (Bevel / AO) but this job "
                "also bakes non-material maps ("
                + ", ".join(
                    sorted({
                        str(getattr(_item, "map_type", "") or "")
                        for _item in _selected_project_maps(
                            project, selected_map_types, selected_map_uuids
                        )
                    })
                )
                + "); baking it through Cycles for this run."
            )
    for _nn_uuid, (_nn_row, _nn_source) in _normal_native_rows.items():
        _mat_fp_by_uuid[_nn_uuid] = _nn_source
    for _fp_item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if str(getattr(_fp_item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        _fp_uuid = properties.ensure_map_setting_uuid(_fp_item)
        if _fp_uuid in _mat_fp_by_uuid:
            continue
        _mat_fp_by_uuid[_fp_uuid] = _collect_material_ir_source(
            _fp_item,
            project,
            workspace_path,
            selected_group_names,
            allow_ray_ops=_allow_ray_ops,
            diagnostics=material_detail_diagnostics,
        )
    # Lit Color rows bake as hidden Lighting + Base Color (+ Emission) sources that
    # derived_outputs multiplies after the bake. Only on the Fyr route: Cycles bakes the
    # row whole (COMBINED), textures included.
    _backend_will_run = _job_backend_will_run()
    _lit_color_sources = _collect_lit_color_sources(
        project,
        (
            _lit_color_rows(project, selected_map_types, selected_map_uuids)
            if _backend_will_run and not is_material_workflow
            else {}
        ),
        workspace_path,
        selected_group_names,
        diagnostics=material_detail_diagnostics,
    )
    _lit_color_dir = (
        workspace.ensure_directory(derived_outputs.lit_color_source_dir(output_root, project.name))
        if _lit_color_sources
        else None
    )
    for _lit_uuid, _lit_sources in _lit_color_sources.items():
        for _lit_role, _lit_suffix in (
            ("albedo", derived_outputs.LIT_COLOR_ALBEDO_UUID_SUFFIX),
            ("emission", derived_outputs.LIT_COLOR_EMISSION_UUID_SUFFIX),
        ):
            if _lit_color_source_is_native(_lit_sources.get(_lit_role)):
                _mat_fp_by_uuid[_lit_uuid + _lit_suffix] = _lit_sources[_lit_role]
    opacity_by_object = (
        _collect_high_object_opacity_bindings(
            project,
            workspace_path,
            selected_group_names,
            warnings=material_detail_diagnostics,
        )
        if needs_high_geometry
        else {}
    )
    requires_high_uvs = (
        any(
            _material_ir_source_requires_high_uvs(source)
            for source in _mat_fp_by_uuid.values()
        )
        or any(bool(source) for source in _material_detail_fp_by_uuid.values())
        or (
            not is_material_workflow
            and _lighting_rows_need_high_uvs(project, selected_map_types, selected_map_uuids, selected_group_names)
        )
    )

    groups: list[protocol.BakeGroupConfig] = []
    # Memoised per texture-set key: occupancy is a union over the set's member groups, so
    # without this a set with N groups would walk its meshes N times.
    udim_tile_plans: dict[str, tuple] = {}
    udim_diagnostics: list[str] = []
    global _FIT_AHEAD
    export_groups = [
        group
        for group in project.groups
        if selected_group_names is None or str(getattr(group, "name", "") or "") in selected_group_names
    ]
    if own_tiles_only and export_groups:
        _prime_own_tile_plan(project, export_groups, depsgraph=depsgraph, cache=udim_tile_plans)
    fit_ahead = (
        _CageFitAhead(export_groups, depsgraph)
        if needs_high_geometry and not speculative and len(export_groups) > 1
        else None
    )
    _FIT_AHEAD = fit_ahead
    try:
        for group_position, group in enumerate(export_groups):
            if fit_ahead is not None:
                fit_ahead.advance(group_position)
            group_config = _export_group_meshes(
                project,
                group,
                depsgraph,
                meshes_root,
                preserve_high_vertex_colors=preserve_high_vertex_colors,
                high_color_source=color_source,
                requires_high_uvs=requires_high_uvs,
                workspace_key=workspace_path,
                use_shared_memory=use_shared_memory,
                cancel_check=cancel_check,
                opacity_by_object=opacity_by_object,
                skip_high=not needs_high_geometry,
            )
            group_config.skew_correction_maps = _write_skew_correction_maps(
                group, Path(workspace_path) / "skew_correction"
            )
            tile_specs, tokenized_naming, tile_diagnostics = _resolve_group_tile_plan(
                project, group, depsgraph=depsgraph, cache=udim_tile_plans
            )
            for message in tile_diagnostics:
                if message not in udim_diagnostics:
                    udim_diagnostics.append(message)
            group_config.outputs = _build_output_targets(
                project,
                group,
                output_dir,
                selected_map_types=selected_map_types,
                selected_map_uuids=selected_map_uuids,
                tile_specs=tile_specs,
                tokenized_naming=tokenized_naming,
                redirect_dirs=_redirect_dirs,
            )
            group_config.outputs, _group_derived = _split_derived_outputs(
                project,
                group,
                group_config.outputs,
                output_dir,
                lit_color_sources=_lit_color_sources,
                lit_color_dir=_lit_color_dir,
            )
            derived_output_entries.extend(_group_derived)
            if dirty_object_names_by_group is not None:
                group_config.dirty_uv_rects = _build_dirty_uv_rects_for_group(
                    project,
                    group,
                    depsgraph,
                    group_config.outputs,
                    dirty_object_names_by_group.get(str(getattr(group, "name", "") or "")),
                )
            groups.append(group_config)
    except BaseException:
        # A cancelled or failed capture can occur after earlier objects have
        # registered section handles. Let any canonical writer finish before
        # closing those mappings, then remove the incomplete job workspace.
        try:
            indexed_geometry.wait_for_workspace_canonical_writes(workspace_path)
            high_mesh_cache.finalize_pending_canonical_aliases()
        finally:
            mesh_transport.release_workspace_shared_memory(workspace_path)
            storage_cleanup.delete_workspaces((workspace_path,))
        raise
    finally:
        _FIT_AHEAD = None
        if fit_ahead is not None:
            fit_ahead.close()

    if not groups:
        raise ValueError("Create at least one bake group before exporting a bake job")

    blocker_group = _export_scene_blockers_group(
        project,
        groups,
        depsgraph,
        meshes_root,
        workspace_path,
        selected_map_types,
        selected_map_uuids,
        selected_group_names,
        requires_high_uvs=requires_high_uvs,
        is_material_workflow=is_material_workflow,
    )
    if blocker_group is not None:
        groups.append(blocker_group)

    # AO "Relative to Bounds" distances are fractions of model size; convert to absolute
    # units once (the backend uses ao_distance as absolute).
    low_bounds_diagonal = _bake_low_bounds_diagonal(project, selected_group_names, depsgraph)

    # A HEIGHT row left on automatic (inner == outer == 0) resolves its range HERE rather
    # than in the backend, so the cage-mesh modes stop depending on their hidden, dead
    # `cage_offset`. Computed lazily: projects without an auto HEIGHT row pay nothing.
    _auto_height_half_range: float | None = None

    def _resolved_height_distance(map_item, prop_name: str, map_type: str) -> float:
        nonlocal _auto_height_half_range
        inner = float(getattr(map_item, "height_inner_distance", 0.0) or 0.0)
        outer = float(getattr(map_item, "height_outer_distance", 0.0) or 0.0)
        explicit = float(getattr(map_item, prop_name, 0.0) or 0.0)
        # Only a HEIGHT row reads these (every backend and shader use is gated on the map
        # kind). Resolving them for every row ran the cage estimate on every bake: on SvAT
        # its high digests held another ~0.9 GB in Blender for a project with no HEIGHT map.
        if inner != 0.0 or outer != 0.0 or str(map_type or "").strip().upper() != constants.MAP_HEIGHT:
            return explicit
        if _auto_height_half_range is None:
            try:
                _auto_height_half_range = resolve_auto_height_half_range(
                    project, depsgraph, selected_group_names
                )
            except Exception:
                _auto_height_half_range = 0.0
        if not _auto_height_half_range:
            # Nothing measurable -- leave the 0/0 sentinel so the backend's own fallback
            # still applies rather than inventing a number here.
            return explicit
        return (
            -_auto_height_half_range
            if prop_name == "height_inner_distance"
            else _auto_height_half_range
        )

    # MBBJOB35: per-face colours for ID maps on the "Material Color" source. Built once
    # (shared by every such row) and only when one is selected, so every other job is
    # unchanged.
    id_material_meshes: list[protocol.IdMaterialMesh] = []
    if not is_material_workflow and _selected_maps_use_id_material(
        project, selected_map_types, selected_map_uuids
    ):
        id_material_meshes = _build_id_material_meshes(
            project, selected_group_names, depsgraph, speculative=speculative
        )

    map_configs = []
    has_selected_wireframe = False
    # Marmoset curvature calibration knobs are GLOBAL scene props (see
    # properties.MM_CALIBRATION_KNOBS) shared by every curvature-family map. They
    # now flow per-bake through the job payload instead of env vars, so a slider change
    # applies on the next bake with no worker restart. Read once and stamped onto each
    # curvature-family map config below; jitter is job-level (set on the project block).
    _mm_scene = getattr(context, "scene", None)
    _mm_settings = getattr(_mm_scene, "fyr_baker_settings", None) if _mm_scene is not None else None

    def _mm_knob(prop_name: str, default: float) -> float:
        if _mm_settings is None:
            return float(default)
        try:
            return float(getattr(_mm_settings, prop_name, default))
        except (TypeError, ValueError):
            return float(default)

    _mm_power_gamma = _mm_knob("mm_power_gamma", 1.792)
    _mm_power_amplitude = _mm_knob("mm_power_amplitude", 9.2)
    _mm_power_linear_floor = _mm_knob("mm_power_linear_floor", 3.2)
    _mm_power_faint = _mm_knob("mm_power_faint", 1.75)
    _mm_convex_boost = _mm_knob("mm_convex_boost", 1.7)
    _mm_linear_bias = _mm_knob("mm_linear_bias", 1.0)
    _mm_aa_jitter_scale = _mm_knob("mm_aa_jitter_scale", 2.0)
    # Use Bevel Normal = Auto. One walk for the whole job: a Bevel on the high
    # normal shades AO from the convex bevel, and a bump-only normal does not.
    _ao_bevel_present = (
        bake_dependencies.high_normal_graph_has_bevel(project, selected_group_names)
        if needs_high_geometry
        else False
    )

    for item in project.maps:
        if getattr(item, "is_add_phantom", False):
            continue
        # Material-workflow Normal stays addon-side (self-bake Cycles NORMAL).
        # MAP_MATERIAL rows use the same backend IR path as HIGH_TO_LOW.
        if is_material_workflow and str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        item_uuid = properties.ensure_map_setting_uuid(item)
        map_selected_by_uuid = selected_map_uuids is not None and item_uuid in selected_map_uuids
        if selected_map_uuids is not None:
            if not map_selected_by_uuid:
                continue
            if selected_map_types is not None and item.map_type not in selected_map_types:
                continue
        elif selected_map_types is not None:
            if item.map_type not in selected_map_types:
                continue
        elif not item.enabled:
            continue
        if str(getattr(item, "map_type", "") or "").strip().upper() == constants.MAP_WIREFRAME:
            has_selected_wireframe = True
            continue  # drawn by derived_outputs; the backend never sees it
        normal_format = properties.effective_normal_format(item)
        normalized_normal_format = normal_format.strip().upper()
        if normalized_normal_format == constants.NORMAL_FORMAT_DIRECTX:
            flip_green = True
        elif normalized_normal_format == constants.NORMAL_FORMAT_OPENGL:
            flip_green = False
        else:
            flip_green = bool(getattr(item, "flip_green", False))
        if naming.normal_row_is_derivative(item):
            # The hidden source is always OpenGL (the backend reads both fields); the
            # row's format flips the V slope when derived_outputs converts it.
            flip_green = False
            normal_format = constants.NORMAL_FORMAT_OPENGL
        effective_map_type = _effective_map_type_for_setting(item)
        _lit_sources = _lit_color_sources.get(item_uuid)
        _lighting_component = "ALL"
        if effective_map_type in constants.LIGHTING_COMPONENT_BY_EFFECTIVE_TYPE:
            # Direct / Indirect Lighting bake as LIGHTING with the component set.
            effective_map_type, _lighting_component = constants.LIGHTING_COMPONENT_BY_EFFECTIVE_TYPE[effective_map_type]
        if effective_map_type == constants.MAP_LIT_COLOR or _lit_sources is not None:
            # Lit Color: the lighting carries the diffuse share of the texel's material
            # (1 - metallic, under the specular layer), as Cycles' diffuse colour does.
            _lighting_component = "LIT"
        if _lit_sources is not None:
            # Same row, same uuid: the job bakes its lighting; derived_outputs adds the colour.
            effective_map_type = constants.MAP_LIGHTING
        _native_normal = _normal_native_rows.get(item_uuid)
        if _native_normal is not None:
            # Same row, same uuid, same output file -- only the job's map type changes.
            item = _native_normal[0]
            effective_map_type = constants.MAP_MATERIAL_NORMAL
        if str(item.map_type or "").strip().upper() == constants.MAP_MATERIAL:
            # Material IR: IMAGE_SAMPLE (single UV TexImage) or EXPRESSION_UV
            # (Mix/Math/Invert/Ramp over plain-UV images). Forced Blender → Cycles.
            from . import material_ir

            channel = str(getattr(item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or "")
            origin = str(getattr(item, "material_origin", "") or constants.MATERIAL_ORIGIN_MANUAL)
            custom_name = str(getattr(item, "material_custom_name", "") or "").strip()
            custom_data_type = str(getattr(item, "material_data_type", "") or "")
            _fp_source = _mat_fp_by_uuid.get(item_uuid) or {}
            program = _fp_source.get("program")
            if not isinstance(program, material_ir.MaterialIrProgram):
                # _collect_material_ir_source returns the refused program with its own
                # reason, so there is nothing to recover here: this placeholder only
                # covers the case where collection never ran (no groups selected).
                program = material_ir.MaterialIrProgram(
                    version=material_ir.MATERIAL_IR_VERSION,
                    kind=material_ir.MATERIAL_IR_KIND_NONE,
                    channel=channel if origin != constants.MATERIAL_ORIGIN_CUSTOM else f"CUSTOM:{custom_name or 'Custom'}",
                    native=False,
                    fallback_reason="No native Material IR program for this channel",
                )
            requested_route = str(getattr(item, "execution_route", constants.EXECUTION_ROUTE_AUTO) or constants.EXECUTION_ROUTE_AUTO)
            effective_route, route_reason = material_ir.resolve_execution_route(requested_route, program)
            # A view-dependent node is not "slower through Cycles", it is unbakeable:
            # with no camera and no incoming ray the fallback evaluates it at normal
            # incidence and the whole map comes out one flat value. The Bakeability
            # panel already said so; the bake said nothing at all, finishing with 0
            # warnings (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P4). Warn so it reaches
            # the post-bake report, and keep baking -- a constant is still the answer
            # Cycles gives, and refusing outright would break projects that bake fine
            # apart from one decorative mask.
            if not program.native:
                from . import material_graph as _material_graph

                if _material_graph.node_type_is_view_dependent(
                    getattr(program, "fallback_node_type", "")
                ):
                    _node_label = str(getattr(program, "fallback_node_name", "") or "").strip()
                    _warning = (
                        f"Material map '{channel}' depends on "
                        f"{_node_label or getattr(program, 'fallback_node_type', 'a view-dependent node')}, "
                        "which cannot be baked: it has no value without a camera, so this "
                        "channel bakes as a flat constant."
                    )
                    if _warning not in material_detail_diagnostics:
                        material_detail_diagnostics.append(_warning)
            try:
                item.material_status_message = route_reason
            except Exception:
                pass
            if effective_route == constants.EXECUTION_ROUTE_BACKEND and not program.native:
                raise ValueError(
                    f"Material map '{channel}' is set to Fyr, but this material needs Cycles: {route_reason}"
                )
            if effective_route == constants.EXECUTION_ROUTE_BACKEND and program.native:
                _fp_png = str(_fp_source.get("path") or program.image_path or "")
                _resource_paths = list(_fp_source.get("resource_paths") or [])
                _wire = program.wire_payload()
                # Drop Blender image pointers from resources; keep channel metadata.
                # Per-map denoise for material rows: a material graph can contain
                # stochastic ray-op nodes (MIR "AO" / "BEVEL"), so the same option the
                # AO-family maps expose applies here. Default is off (the raw bake is the
                # product); encoded-vector outputs never denoise regardless of the switch.
                _mat_denoise = bool(
                    getattr(item, "denoising_enabled", False)
                ) and constants.material_denoise_available(channel, origin, custom_data_type)
                # A plain resource stays exactly {channel, path}; a UDIM or slot
                # table carries its tiles / slots (material_ir.wire_resource).
                _wire["resources"] = [
                    material_ir.wire_resource(res, path)
                    for res, path in zip(
                        program.resources,
                        _resource_paths or [program.image_path] * len(program.resources),
                    )
                ]
                map_configs.append(
                    protocol.BakeMapConfig(
                        map_type=effective_map_type,
                        map_uuid=item_uuid,
                        enabled=True,
                        samples=1,
                        output_suffix=properties.effective_map_output_suffix(project, item) or "",
                        # Material-detail normals (MBBJOB39): the native Normal row keeps
                        # its resolved texels in the worker for the following mesh bake.
                        material_normal_retain=bool(_native_normal is not None),
                        material_normal_composite=bool((material_normal_source or {}).get("composite")),
                        denoising_enabled=_mat_denoise,
                        # Only carry the project-level denoise knobs when the option is
                        # ON: they participate in the backend's prepared-map cache key, so
                        # sending them with denoise off would invalidate cached material
                        # bakes whenever an unrelated slider moved. Off => the exact
                        # protocol defaults this row has always sent.
                        denoise_strength=float(getattr(project, "denoise_strength", 1.0)) if _mat_denoise else 1.0,
                        denoise_quality=str(getattr(project, "denoise_quality", "HIGH")) if _mat_denoise else "HIGH",
                        diffusion_dilation_enabled=bool(getattr(item, "diffusion_dilation_enabled", False)),
                        diffusion_dilation_iterations=int(getattr(item, "diffusion_dilation_iterations", 3)),
                        material_channel=channel if origin != constants.MATERIAL_ORIGIN_CUSTOM else "CUSTOM",
                        # The NORMAL channel's DirectX flip is compiled into the IR; the
                        # backend's normal seam margin decodes/re-encodes the gutter texels
                        # and has to mirror the same convention.
                        flip_green=bool(
                            origin != constants.MATERIAL_ORIGIN_CUSTOM
                            and channel == constants.MATERIAL_CHANNEL_NORMAL
                            and _material_normal_flip_green(item)
                        ),
                        material_fast_path_image_path=_fp_png,
                        material_fast_path_tile_images=list(
                            _fp_source.get("tiles") or []
                        ),
                        material_ir_version=int(program.version),
                        material_ir_kind=str(program.kind),
                        material_ir_fallback_reason=str(program.fallback_reason or ""),
                        material_ir_program_json=json.dumps(_wire, separators=(",", ":"), sort_keys=True),
                        material_ir_resource_paths=_resource_paths,
                        output_soften=properties.resolve_map_soften(project, item),
                        # A roughness row opting into variance compensation carries the high
                        # materials' NORMAL sources as bindings. Deliberately NOT through
                        # material_fast_path_image_path: that field is this row's own
                        # roughness texture, and the backend derives the legacy single detail
                        # source from it, which would measure the variance off the wrong map.
                        **_variance_detail_fields(
                            item, _material_detail_fp_by_uuid.get(item_uuid)
                        ),
                    )
                )
            continue
        # Resolve AO "Relative to Bounds" into absolute units here; the backend treats
        # ao_distance/ao_min_distance as absolute, so the relative flag is consumed now.
        _ao_distance_raw = float(getattr(item, "ao_distance", 0.0))
        _ao_min_distance_raw = float(getattr(item, "ao_min_distance", 0.0))
        _ao_relative = bool(getattr(item, "ao_relative_to_bounding_box", False))
        if _ao_relative and low_bounds_diagonal > 0.0:
            _ao_distance_send = _ao_distance_raw * low_bounds_diagonal
            _ao_min_distance_send = _ao_min_distance_raw * low_bounds_diagonal
            _ao_relative_send = False
        else:
            _ao_distance_send = _ao_distance_raw
            _ao_min_distance_send = _ao_min_distance_raw
            _ao_relative_send = _ao_relative
        _detail_fp = _material_detail_fp_by_uuid.get(item_uuid) or {}
        _item_soften = properties.resolve_map_soften(project, item)
        map_configs.append(
            protocol.BakeMapConfig(
                map_type=effective_map_type,
                map_uuid=item_uuid,
                enabled=True,
                samples=int(item.samples),
                output_suffix=properties.effective_map_output_suffix(project, item) or "",
                normal_space=str(getattr(item, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)),
                normal_format=normal_format,
                flip_green=flip_green,
                ao_mode=str(getattr(item, "ao_mode", constants.MAP_AO_MODE_RAYCAST)),
                ao_distance=_ao_distance_send,
                ao_min_distance=_ao_min_distance_send,
                ao_two_sided=bool(getattr(item, "ao_two_sided", False)),
                ao_ignore_groups=bool(getattr(item, "ao_ignore_groups", False)),
                ao_occlude_other_groups=bool(getattr(item, "ao_occlude_other_groups", False)),
                # Material-detail normals (MBBJOB39): the native Normal row keeps its
                # resolved texels in the worker; the normal-consuming rows name it.
                material_normal_retain=bool(_native_normal is not None),
                # AO and Bent Normal name the source when Use Bevel Normal resolves on
                # (Auto does, if a Bevel shader feeds the high). Convex Edges keeps
                # concave fillets on the raw surface so crevices stay dark.
                material_normal_source_uuid=(
                    str((material_normal_source or {}).get("map_uuid") or "")
                    if str(effective_map_type or "").strip().upper()
                    in bake_dependencies.NORMAL_CONSUMER_MAP_TYPES
                    or (
                        str(effective_map_type or "").strip().upper()
                        in bake_dependencies.BEVEL_OCCLUSION_MAP_TYPES
                        and _ao_bevel_normal_mode(item, _ao_bevel_present) != 0
                    )
                    else ""
                ),
                material_normal_source_flip_green=bool(
                    (material_normal_source or {}).get("flip_green", False)
                ),
                material_normal_composite=bool((material_normal_source or {}).get("composite")),
                curvature_bevel_mask=bool(getattr(item, "curvature_bevel_mask", True)),
                ao_bevel_normal_mode=(
                    _ao_bevel_normal_mode(item, _ao_bevel_present)
                    if str(effective_map_type or "").strip().upper()
                    in bake_dependencies.BEVEL_OCCLUSION_MAP_TYPES
                    else 0
                ),
                ao_cavity_weight=float(getattr(item, "ao_cavity_weight", constants.default_ao_cavity_weight_for_map(getattr(item, "map_type", "")))),
                ao_floor_occlusion=bool(getattr(item, "ao_floor_occlusion", False)),
                ao_relative_to_bounding_box=_ao_relative_send,
                ao_spread_angle=float(getattr(item, "ao_spread_angle", 180.0)),
                ao_distribution=str(getattr(item, "ao_distribution", "COSINE")),
                ao_ignore_backface=bool(getattr(item, "ao_ignore_backface", False)),
                ao_self_occlusion=float(getattr(item, "ao_self_occlusion", 1.0)),
                ao_attenuation=float(getattr(item, "ao_attenuation", 1.0)),
                ao_output_min=float(getattr(item, "ao_output_min", constants.DEFAULT_AO_OUTPUT_MIN)),
                ao_output_max=float(getattr(item, "ao_output_max", 1.0)),
                ao_use_ground_plane=bool(getattr(item, "ao_use_ground_plane", False)),
                ao_ground_plane_offset=float(getattr(item, "ao_ground_plane_offset", 0.0)),
                ao_diffusion_quality=str(getattr(item, "ao_diffusion_quality", constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM)),
                ao_diffusion_clearance_scale=float(getattr(item, "ao_diffusion_clearance_scale", 0.2)),
                ao_diffusion_clearance_exponent=float(getattr(item, "ao_diffusion_clearance_exponent", 2.0)),
                env_light_intensity=float(getattr(item, "env_light_intensity", 1.0)),
                env_light_occlusion_strength=float(getattr(item, "env_light_occlusion_strength", 0.6)),
                env_light_contrast=float(getattr(item, "env_light_contrast", 1.0)),
                env_light_up_axis=str(getattr(item, "env_light_up_axis", "Z")),
                env_light_sky_r=float(getattr(item, "env_light_sky_color", (0.55, 0.70, 1.00))[0]),
                env_light_sky_g=float(getattr(item, "env_light_sky_color", (0.55, 0.70, 1.00))[1]),
                env_light_sky_b=float(getattr(item, "env_light_sky_color", (0.55, 0.70, 1.00))[2]),
                env_light_ground_r=float(getattr(item, "env_light_ground_color", (0.18, 0.16, 0.14))[0]),
                env_light_ground_g=float(getattr(item, "env_light_ground_color", (0.18, 0.16, 0.14))[1]),
                env_light_ground_b=float(getattr(item, "env_light_ground_color", (0.18, 0.16, 0.14))[2]),
                curvature_scale=float(getattr(item, "curvature_scale", 1.0)),
                curvature_distance=float(getattr(item, "curvature_distance", 0.0)),
                curvature_relative_to_bounding_box=bool(getattr(item, "curvature_relative_to_bounding_box", False)),
                curvature_secondary_rays=int(getattr(item, "curvature_secondary_rays", 64)),
                curvature_detect_folds=bool(getattr(item, "curvature_detect_folds", False)),
                curvature_self_intersection=str(getattr(item, "curvature_self_intersection", "GROUP")),
                curvature_auto_tonemapping=bool(getattr(item, "curvature_auto_tonemapping", False)),
                curvature_value_min=float(getattr(item, "curvature_value_min", -1.0)),
                curvature_value_max=float(getattr(item, "curvature_value_max", 1.0)),
                curvature_method=str(getattr(item, "curvature_method", "NORMAL_DERIVATIVE")),
                # Output range defaults are NEUTRAL (0/1): the Marmoset-matched response
                # was calibrated against an unstretched output, so the old 0.4/0.6 window
                # railed the curve. The artist can still dial a stretch deliberately.
                curvature_tonemapping_min=float(getattr(item, "curvature_tonemapping_min", 0.0)),
                curvature_tonemapping_max=float(getattr(item, "curvature_tonemapping_max", 1.0)),
                # Two different things, deliberately not the same number:
                # curvature_soften is the width of the normal-derivative sampling
                # kernel (Detail Smoothing, calibrated at 0.5), output_soften is the
                # artist's post-bake blur radius (Soften, off at 0).
                curvature_soften=float(getattr(item, "curvature_soften", 0.5)),
                output_soften=_item_soften,
                # Global Marmoset calibration knobs (per-bake; formerly FYR_BAKER_MM_* env).
                mm_power_gamma=_mm_power_gamma,
                mm_power_amplitude=_mm_power_amplitude,
                mm_power_linear_floor=_mm_power_linear_floor,
                mm_power_faint=_mm_power_faint,
                mm_convex_boost=_mm_convex_boost,
                mm_linear_bias=_mm_linear_bias,
                thickness_distance=float(getattr(item, "thickness_distance", 0.0)),
                thickness_min_distance=float(getattr(item, "thickness_min_distance", -1.0)),
                thickness_scale=float(getattr(item, "thickness_scale", 1.0)),
                thickness_gamma=float(getattr(item, "thickness_gamma", 1.0)),
                thickness_dither=bool(getattr(item, "thickness_dither", False)),
                thickness_ignore_groups=bool(getattr(item, "thickness_ignore_groups", False)),
                thickness_normalization=bool(getattr(item, "thickness_normalization", False)),
                thickness_log_response=bool(getattr(item, "thickness_log_response", False)),
                density_auto_levels=bool(getattr(item, "density_auto_levels", False)),
                density_auto_levels_per_group=bool(getattr(item, "density_auto_levels_per_group", True)),
                id_source=str(getattr(item, "id_source", constants.MAP_ID_SOURCE_OBJECT)),
                attribute_name=str(getattr(item, "attribute_name", "") or ""),
                attribute_range_min=float(getattr(item, "attribute_range_min", 0.0) or 0.0),
                attribute_range_max=float(getattr(item, "attribute_range_max", 1.0)),
                position_mode=str(getattr(item, "position_mode", "ABSOLUTE")),
                position_axis=str(getattr(item, "position_axis", "XYZ")),
                position_normalization=properties.map_position_normalization(item),
                relative_to_bounding_box=bool(getattr(item, "relative_to_bounding_box", True)),
                height_inner_distance=_resolved_height_distance(item, "height_inner_distance", effective_map_type),
                height_outer_distance=_resolved_height_distance(item, "height_outer_distance", effective_map_type),
                height_dither=bool(getattr(item, "height_dither", False)),
                denoising_enabled=bool(getattr(item, "denoising_enabled", False)),
                denoise_strength=float(getattr(project, "denoise_strength", 1.0)),
                denoise_quality=str(getattr(project, "denoise_quality", "HIGH")),
                diffusion_dilation_enabled=bool(getattr(item, "diffusion_dilation_enabled", False)),
                diffusion_dilation_iterations=int(getattr(item, "diffusion_dilation_iterations", 3)),
                material_channel=str(getattr(item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO)),
                material_fast_path_image_path=str(_detail_fp.get("path", "") or ""),
                material_fast_path_tile_images=list(_detail_fp.get("tiles") or []),
                material_detail_mode=str(_detail_fp.get("mode", "") or ""),
                material_detail_strength=float(_detail_fp.get("strength", 1.0)),
                material_detail_radius=int(_detail_fp.get("radius", 8)),
                material_detail_flip_green=bool(_detail_fp.get("flip_green", False)),
                material_detail_bindings=[
                    protocol.MaterialDetailBinding(
                        material_name=str(binding["material_name"]),
                        image_path=str(binding["image_path"]),
                        mode=str(binding["mode"]),
                        strength=float(binding["strength"]),
                        flip_green=bool(binding["flip_green"]),
                        uv_transform=[float(v) for v in (binding.get("uv_transform") or [])],
                    )
                    for binding in (_detail_fp.get("bindings") or [])
                ],
                material_detail_slot_index_image_path=str(_detail_fp.get("slot_sidecar", "") or ""),
                material_detail_uv_transform=[
                    float(v) for v in (_detail_fp.get("uv_transform") or [])
                ],
                lighting_engine=_resolve_lighting_engine(getattr(context, "scene", None), getattr(item, "lighting_engine", constants.LIGHTING_ENGINE_AUTO)),
                lighting_quality=str(getattr(item, "lighting_quality", constants.LIGHTING_QUALITY_BALANCED)),
                lighting_direct_enabled=bool(getattr(item, "lighting_direct_enabled", True)),
                lighting_indirect_enabled=bool(getattr(item, "lighting_indirect_enabled", True)),
                lighting_world_enabled=bool(getattr(item, "lighting_world_enabled", True)),
                lighting_emission_enabled=bool(getattr(item, "lighting_emission_enabled", True)),
                lighting_direct_samples=int(getattr(item, "lighting_direct_samples", 1)),
                lighting_indirect_paths=int(getattr(item, "lighting_indirect_paths", 64)),
                lighting_max_bounces=int(getattr(item, "lighting_max_bounces", 4)),
                lighting_noise_threshold=float(getattr(item, "lighting_noise_threshold", 0.02)),
                # MBBJOB42. Only a lighting row carries them; every other row sends the
                # protocol defaults, so its job bytes and cache keys are unchanged.
                lighting_occlude_other_groups=bool(
                    effective_map_type in (constants.MAP_LIGHTING, constants.MAP_LIT_COLOR)
                    and getattr(item, "lighting_occlude_other_groups", True)
                ),
                lighting_exposure=(
                    float(getattr(item, "lighting_exposure", 1.0))
                    if effective_map_type in (constants.MAP_LIGHTING, constants.MAP_LIT_COLOR)
                    else 1.0
                ),
                lighting_component=_lighting_component,
                id_material_meshes=(
                    list(id_material_meshes)
                    if str(item.map_type or "") == constants.MAP_ID
                    and str(getattr(item, "id_source", constants.MAP_ID_SOURCE_OBJECT) or "")
                    == constants.MAP_ID_SOURCE_MATERIAL
                    else []
                ),
            )
        )
        if _lit_sources is not None:
            for _lit_role, _lit_channel, _lit_suffix in (
                ("albedo", constants.MATERIAL_CHANNEL_ALBEDO, derived_outputs.LIT_COLOR_ALBEDO_UUID_SUFFIX),
                ("emission", constants.MATERIAL_CHANNEL_EMISSION, derived_outputs.LIT_COLOR_EMISSION_UUID_SUFFIX),
            ):
                if _lit_color_source_is_native(_lit_sources.get(_lit_role)):
                    map_configs.append(
                        _lit_color_material_config(
                            project, item, item_uuid + _lit_suffix, _lit_channel, _lit_sources[_lit_role]
                        )
                    )

    # Allow a bake job where all maps are material maps (handled addon-side).
    # Only error when there are no enabled maps at all (backend + addon-side combined).
    has_any_material_maps = any(
        not getattr(item, "is_add_phantom", False)
        and str(getattr(item, "map_type", "") or "").strip().upper() == constants.MAP_MATERIAL
        and bool(getattr(item, "enabled", False))
        for item in project.maps
    )
    if not output_selection_has_work(map_configs, has_any_material_maps, has_selected_wireframe):
        raise ValueError("Enable at least one output map before baking")

    job = protocol.BakeJob(
        version=constants.PROTOCOL_VERSION,
        job_id=job_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        progress_path=str(progress_path),
        scene_lighting=_build_scene_lighting_config(
            context,
            depsgraph,
            map_configs,
            env_cache_dir=workspace_path,
            project=project,
            selected_group_names=selected_group_names,
            diagnostics=material_detail_diagnostics,
        ),
        project=protocol.BakeProjectInfo(
            name=project.name,
            output_root=str(output_root),
            workspace=str(workspace_path),
            resolution_width=int(project.resolution_x),
            resolution_height=int(project.resolution_y),
            bit_depth=int(project.bit_depth),
            margin=resolve_job_bake_margin(project, groups),
            tangent_basis=constants.normalize_tangent_basis(project.tangent_basis),
            bake_mode=project.bake_mode,
            # Free integer sample count is authoritative; the legacy enum is the
            # nearest ladder rung so older backends still degrade gracefully.
            aa_samples=_job_aa_samples(project, map_configs),
            anti_aliasing=constants.samples_to_anti_aliasing(_job_aa_samples(project, map_configs)),
            execution_backend=_resolve_execution_backend(),
            image_format=str(getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT)),
            # Job-level Marmoset AA jitter scale (per-bake; formerly FYR_BAKER_AA_JITTER_SCALE).
            mm_aa_jitter_scale=_mm_aa_jitter_scale,
            respect_opacity=bool(getattr(project, "respect_opacity", True)),
            workflow=str(getattr(project, "workflow", constants.WORKFLOW_HIGH_TO_LOW)),
            live_reproject=bool(getattr(project, "live_reproject", False)),
        ),
        maps=map_configs,
        groups=groups,
    )

    protocol.write_progress(
        progress_path,
        protocol.BakeProgress(
            status=constants.STATUS_EXPORTED,
            message="Bake workspace exported",
        ),
    )
    project.last_job_id = job_id
    project.last_workspace_path = str(workspace_path)
    project.last_output_dir = str(output_dir)
    # Keep the last workspace a bake actually RAN in, alongside the one just prepared.
    # Pruning to the newest workspace alone deleted the finished bake's job, progress
    # and backend log within seconds of it completing, because the speculative
    # background prepare fires on any edit. A support bundle collected after that
    # point could never contain a bake, which is precisely when someone asks for one.
    # Workspaces are slimmed of their meshes, so the retained one costs a few KB.
    _keep_paths = [workspace_path]
    _prior_bake_workspace = str(getattr(project, "last_bake_workspace_path", "") or "").strip()
    if _prior_bake_workspace:
        _keep_paths.append(_prior_bake_workspace)
    storage_cleanup.prune_job_workspaces(output_root, keep_paths=_keep_paths)
    try:
        storage_cleanup.prune_live_reproject_stores(
            output_root, keep_tokens=_live_reproject_store_tokens_for_output_root(output_root)
        )
    except Exception:
        pass
    storage_cleanup.launch_idle_cache_reclaim()
    project.last_status_message = constants.STATUS_EXPORTED

    # Collect material bake specs (handled addon-side before the backend job runs)
    import bpy as _bpy
    material_specs: list[MaterialBakeSpec] = []
    deferred_multi_group_uuids: list[str] = []
    # Selected-to-active material bakes trace from the Automatic cage this export just
    # fitted, read here once per group: the job's mesh files may be gone by the time a
    # queued material bake runs.
    job_groups_by_name = {str(getattr(config, "name", "") or ""): config for config in groups}
    fitted_cage_memo: dict[tuple, tuple] = {}
    width = int(getattr(project, "resolution_x", 1024))
    height = int(getattr(project, "resolution_y", 1024))
    for mat_item in project.maps:
        if getattr(mat_item, "is_add_phantom", False):
            continue
        if str(getattr(mat_item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        mat_item_uuid = str(getattr(mat_item, "uuid", "") or "").strip()
        mat_selected_by_uuid = selected_map_uuids is not None and mat_item_uuid in selected_map_uuids
        if selected_map_uuids is not None:
            if not mat_selected_by_uuid:
                continue
            if selected_map_types is not None and mat_item.map_type not in selected_map_types:
                continue
        elif selected_map_types is not None:
            if mat_item.map_type not in selected_map_types:
                continue
        elif not bool(getattr(mat_item, "enabled", False)):
            continue
        # If the backend Material IR handles this item, skip Cycles.
        # Respect forced Blender route even when a native program exists.
        from . import material_ir as _material_ir

        _fp_hit = _mat_fp_by_uuid.get(mat_item_uuid) or {}
        _program = _fp_hit.get("program") if isinstance(_fp_hit, dict) else None
        if not isinstance(_program, _material_ir.MaterialIrProgram):
            _program = _material_ir.MaterialIrProgram(
                native=False,
                fallback_reason=str(getattr(mat_item, "material_status_message", "") or ""),
            )
        _requested = str(getattr(mat_item, "execution_route", constants.EXECUTION_ROUTE_AUTO) or "")
        _effective, _reason = _material_ir.resolve_execution_route(_requested, _program)
        # "The backend handles it" is only true when the backend is going to RUN.
        # Under Route = Cycles it never does, so deferring a natively-compilable
        # channel to it dropped the row on the floor and the job then failed in the
        # projection planner instead of baking.
        if _effective == constants.EXECUTION_ROUTE_BACKEND and not _backend_will_run:
            _effective = constants.EXECUTION_ROUTE_BLENDER
        if _effective == constants.EXECUTION_ROUTE_BACKEND and _program.native:
            continue
        if _effective == constants.EXECUTION_ROUTE_BACKEND and not _program.native:
            raise ValueError(
                f"Material map '{getattr(mat_item, 'material_channel', '?')}' requires Backend, "
                f"but native Material IR is unavailable: {_reason}"
            )
        if (
            _backend_will_run
            and str(_requested or "").strip().upper() in ("", constants.EXECUTION_ROUTE_AUTO)
            and isinstance(_fp_hit, dict)
            and _fp_hit.get("multi_group_refusal")
        ):
            # Every group alone compiles native; only the shared-sidecar union cannot.
            # No Cycles spec: the bake operator re-runs this row per group on the
            # backend once the main job lands (F8, docs/MATERIAL_PER_GROUP_NATIVE_PLAN.md).
            deferred_multi_group_uuids.append(mat_item_uuid)
            try:
                mat_item.material_status_message = (
                    "Baking natively per bake group (Combined texture set)"
                )
            except Exception:
                pass
            continue
        origin = str(getattr(mat_item, "material_origin", "") or constants.MATERIAL_ORIGIN_MANUAL)
        custom_name = str(getattr(mat_item, "material_custom_name", "") or "").strip()
        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            channel = "CUSTOM"
            effective_type = constants.MAP_MATERIAL_CUSTOM
        else:
            channel = str(getattr(mat_item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or "").strip().upper()
            effective_type = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel, constants.MAP_MATERIAL_ALBEDO)
        for group in project.groups:
            if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
                continue
            tile_specs, tokenized_naming, _tile_diagnostics = _resolve_group_tile_plan(
                project, group, depsgraph=depsgraph, cache=udim_tile_plans
            )
            # Without the tile plan every target came back untiled (udim_tile=0,
            # no .NNNN in the name), the per-tile match below never applied and
            # every tile of a UDIM set saved over the same file.
            output_targets = _build_output_targets(
                project, group, output_dir,
                selected_map_types={mat_item.map_type} if selected_map_types is not None else None,
                selected_map_uuids={mat_item_uuid} if selected_map_uuids is not None else None,
                tile_specs=tile_specs,
                tokenized_naming=tokenized_naming,
                redirect_dirs=_redirect_dirs,
            )
            low_obj_names = tuple(
                str(slot.object_ref.name)
                for slot in _iter_valid_object_slots(getattr(group, "low_meshes", []))
                if getattr(slot, "object_ref", None) is not None
            )
            if not low_obj_names:
                continue
            # Use Low as High bakes each low's own material onto itself. Projecting the
            # lows onto each other let a neighbouring low win the cage ray where two
            # objects touch, the same bleed _merge_material_specs_by_output avoids.
            high_obj_names = () if properties.group_uses_low_as_high(group) else tuple(
                str(slot.object_ref.name)
                for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group))
                if getattr(slot, "object_ref", None) is not None
            )
            projection_state = _group_projection_settings_state(group)
            # Per-tile Cycles: shift low UVs by the tile origin so 0-1 bake covers that tile.
            from . import udim as _udim_mod
            for tile_spec in tile_specs:
                tile_number = int(getattr(tile_spec, "udim_tile", 0) or 0)
                tile_u = tile_v = 0
                if tokenized_naming and tile_number:
                    tile_u, tile_v = _udim_mod.tile_origin(tile_number)
                output_path = _material_target_path(
                    output_targets,
                    effective_type=effective_type,
                    map_uuid=mat_item_uuid,
                    tile_number=tile_number,
                    tokenized_naming=tokenized_naming,
                )
                if output_path is None:
                    continue
                spec_cage_extrusion, spec_fitted_cages = _material_spec_cage(
                    projection_state,
                    job_groups_by_name.get(str(getattr(group, "name", "") or "")),
                    low_obj_names,
                    high_obj_names,
                    fitted_cage_memo,
                )
                material_specs.append(MaterialBakeSpec(
                    low_obj_names=low_obj_names,
                    high_obj_names=high_obj_names,
                    channel=channel,
                    output_path=output_path,
                    width=int(getattr(tile_spec, "width", width) or width),
                    height=int(getattr(tile_spec, "height", height) or height),
                    margin=properties.effective_bake_margin(
                        project, int(getattr(tile_spec, "width", width) or width),
                        int(getattr(tile_spec, "height", height) or height)),
                    cage_extrusion=spec_cage_extrusion,
                    fitted_cages=spec_fitted_cages,
                    group_name=str(getattr(group, "name", "") or ""),
                    map_uuid=mat_item_uuid,
                    uv_offset_u=float(tile_u),
                    uv_offset_v=float(tile_v),
                    custom_output_name=custom_name if origin == constants.MATERIAL_ORIGIN_CUSTOM else "",
                    udim_tile=tile_number if tokenized_naming else 0,
                    normal_relief=_map_normal_relief(mat_item),
                    normal_flip_green=(
                        channel == constants.MATERIAL_CHANNEL_NORMAL
                        and _material_normal_flip_green(mat_item)
                    ),
                    uv_layer_name=(getattr(projection_state, "uv_layer_name", "") or "").strip(),
                ))

    # MATERIAL-workflow material-space Normal: bake the target object's OWN material normal
    # (Normal Map / Bump nodes) through a Cycles NORMAL pass in its UV space. Self-bake
    # (empty high). This branch never runs for HIGH_TO_LOW projects, whose Normal rows are
    # projected geometry maps owned by the backend.
    if is_material_workflow:
        for norm_item in project.maps:
            if getattr(norm_item, "is_add_phantom", False):
                continue
            if str(getattr(norm_item, "map_type", "") or "").strip().upper() != constants.MAP_NORMAL:
                continue
            norm_uuid = str(getattr(norm_item, "uuid", "") or "").strip()
            if selected_map_uuids is not None:
                if norm_uuid not in selected_map_uuids:
                    continue
            elif selected_map_types is not None:
                # Same three-way branch as every other selection site: a
                # MATERIAL-only dirty rebake must not queue a full Cycles NORMAL
                # bake over the Normal file, and an explicit NORMAL rebake must not
                # be dropped because the row is disabled.
                if constants.MAP_NORMAL not in selected_map_types:
                    continue
            elif not bool(getattr(norm_item, "enabled", False)):
                continue
            for group in project.groups:
                if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
                    continue
                norm_tile_specs, norm_tokenized_naming, _norm_tile_diagnostics = _resolve_group_tile_plan(
                    project, group, depsgraph=depsgraph, cache=udim_tile_plans
                )
                output_targets = _build_output_targets(
                    project, group, output_dir,
                    selected_map_types={norm_item.map_type} if selected_map_types is not None else None,
                    selected_map_uuids={norm_uuid} if selected_map_uuids is not None else None,
                    tile_specs=norm_tile_specs,
                    tokenized_naming=norm_tokenized_naming,
                    redirect_dirs=_redirect_dirs,
                )
                low_obj_names = tuple(
                    str(slot.object_ref.name)
                    for slot in _iter_valid_object_slots(getattr(group, "low_meshes", []))
                    if getattr(slot, "object_ref", None) is not None
                )
                if not low_obj_names:
                    continue
                # One Cycles bake per UDIM tile, shifted to that tile's origin, as the
                # channel branch above does. Taking the first target alone baked only
                # X_Normal.1001 and left every other tile without a Normal file.
                from . import udim as _udim_mod
                for tile_spec in norm_tile_specs:
                    tile_number = int(getattr(tile_spec, "udim_tile", 0) or 0)
                    tile_u = tile_v = 0
                    if norm_tokenized_naming and tile_number:
                        tile_u, tile_v = _udim_mod.tile_origin(tile_number)
                    output_path = _material_target_path(
                        output_targets,
                        effective_type=_effective_map_type_for_setting(norm_item).strip().upper(),
                        map_uuid=norm_uuid,
                        tile_number=tile_number,
                        tokenized_naming=norm_tokenized_naming,
                    )
                    if output_path is None:
                        continue
                    material_specs.append(MaterialBakeSpec(
                        low_obj_names=low_obj_names,
                        high_obj_names=(),
                        channel="NORMAL",
                        output_path=output_path,
                        width=int(getattr(tile_spec, "width", width) or width),
                        height=int(getattr(tile_spec, "height", height) or height),
                        margin=properties.effective_bake_margin(
                            project, int(getattr(tile_spec, "width", width) or width),
                            int(getattr(tile_spec, "height", height) or height)),
                        cage_extrusion=0.0,
                        group_name=str(getattr(group, "name", "") or ""),
                        map_uuid=norm_uuid,
                        uv_offset_u=float(tile_u),
                        uv_offset_v=float(tile_v),
                        udim_tile=tile_number if norm_tokenized_naming else 0,
                        normal_relief=_map_normal_relief(norm_item),
                        normal_flip_green=_material_normal_flip_green(norm_item),
                    ))

    # Lit Color sources whose material graph needs Cycles: bake that channel into the
    # hidden source the Lit Color composite reads (the lighting still bakes on Fyr).
    for _lit_entry in derived_output_entries:
        if str(_lit_entry.get("kind", "")) != derived_outputs.KIND_LIT_COLOR:
            continue
        _lit_group = next(
            (g for g in project.groups if str(getattr(g, "name", "") or "") == _lit_entry["group_name"]),
            None,
        )
        _lit_row = properties.find_map_setting_by_uuid(project, _lit_entry["map_uuid"])
        if _lit_group is None or _lit_row is None:
            continue
        _lit_lows = tuple(
            str(slot.object_ref.name)
            for slot in _iter_valid_object_slots(getattr(_lit_group, "low_meshes", []))
            if getattr(slot, "object_ref", None) is not None
        )
        if not _lit_lows:
            continue
        _lit_highs = () if properties.group_uses_low_as_high(_lit_group) else tuple(
            str(slot.object_ref.name)
            for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(_lit_group))
            if getattr(slot, "object_ref", None) is not None
        )
        _lit_projection = _group_projection_settings_state(_lit_group)
        _lit_tile = int(_lit_entry.get("udim_tile", 0) or 0)
        from . import udim as _udim_mod

        _lit_tile_u, _lit_tile_v = _udim_mod.tile_origin(_lit_tile) if _lit_tile else (0, 0)
        _lit_width = int(_lit_entry["width"])
        _lit_height = int(_lit_entry["height"])
        for _lit_role, _lit_channel, _lit_suffix in (
            ("albedo", constants.MATERIAL_CHANNEL_ALBEDO, derived_outputs.LIT_COLOR_ALBEDO_UUID_SUFFIX),
            ("emission", constants.MATERIAL_CHANNEL_EMISSION, derived_outputs.LIT_COLOR_EMISSION_UUID_SUFFIX),
        ):
            if _lit_entry.get(f"{_lit_role}_route") != constants.EXECUTION_ROUTE_BLENDER:
                continue
            _lit_cage_extrusion, _lit_fitted_cages = _material_spec_cage(
                _lit_projection,
                job_groups_by_name.get(str(_lit_entry["group_name"])),
                _lit_lows,
                _lit_highs,
                fitted_cage_memo,
            )
            material_specs.append(MaterialBakeSpec(
                low_obj_names=_lit_lows,
                high_obj_names=_lit_highs,
                channel=_lit_channel,
                output_path=str(_lit_entry[f"{_lit_role}_source"]),
                width=_lit_width,
                height=_lit_height,
                margin=properties.effective_bake_margin(project, _lit_width, _lit_height),
                cage_extrusion=_lit_cage_extrusion,
                fitted_cages=_lit_fitted_cages,
                group_name=str(_lit_entry["group_name"]),
                map_uuid=str(_lit_entry["map_uuid"]) + _lit_suffix,
                uv_offset_u=float(_lit_tile_u),
                uv_offset_v=float(_lit_tile_v),
                udim_tile=_lit_tile,
                uv_layer_name=(getattr(_lit_projection, "uv_layer_name", "") or "").strip(),
            ))

    # Groups sharing a texture set share the OUTPUT FILE, and each spec used to
    # allocate its own image, clear it, write only its own islands and save -- so the
    # last group won and every other member baked as background. Merge them into one
    # bake per file before anything runs.
    _low_material_by_group = {
        str(getattr(group, "name", "") or ""): low_material_subset.group_material_name(group)
        for group in project.groups
    }
    for _spec in material_specs:
        _spec.only_material = _low_material_by_group.get(str(getattr(_spec, "group_name", "") or ""), "")
    material_specs = _merge_material_specs_by_output(material_specs)

    material_detail_entries: list[dict[str, object]] = []

    # Normal and AO remain single artist-facing outputs. When compatible high
    # procedural material detail exists, bake a hidden transfer layer and
    # combine it after projection. Image-backed detail is already composed by
    # the backend using the same projection hit.
    for detail_item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        detail_map_type = str(getattr(detail_item, "map_type", "") or "").strip().upper()
        if detail_map_type not in {constants.MAP_NORMAL, constants.MAP_AO}:
            continue
        detail_mode = str(
            getattr(detail_item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
            or constants.MATERIAL_DETAIL_AUTO
        ).strip().upper()
        if detail_mode == constants.MATERIAL_DETAIL_OFF:
            continue
        detail_uuid = properties.ensure_map_setting_uuid(detail_item)
        if _material_detail_fp_by_uuid.get(detail_uuid):
            continue
        if detail_uuid in _normal_native_rows:
            # Baked by the backend as the MATERIAL NORMAL channel: no hidden layer.
            continue
        _native_phase_groups = set(_normal_group_phases.get(detail_uuid, ()))
        explicit_image = (
            getattr(detail_item, "material_detail_image", None)
            if detail_mode == constants.MATERIAL_DETAIL_MANUAL and detail_map_type == constants.MAP_AO
            else None
        )
        for group in project.groups:
            group_name = str(getattr(group, "name", "") or "")
            if selected_group_names is not None and group_name not in selected_group_names:
                continue
            if detail_map_type == constants.MAP_NORMAL:
                if not _group_has_material_normal_detail(group):
                    continue
                if group_name in _native_phase_groups:
                    # Baked natively by this group's own phase and composited over the
                    # geometry Normal this job writes: no hidden Cycles layer.
                    continue
                detail_channel = "__DETAIL_NORMAL__"
                # The hidden layer is a Cycles selected-to-active NORMAL bake: the high's
                # FULL shading normal (geometry + Bevel / Bump / normal-map detail) in the
                # low's tangent space, not a delta. RNM-combining it over Fyr's geometric
                # normal applied the high's geometry twice -- a faceted high under a
                # Bevel shader baked visible facet bands that neither the high nor a
                # plain Cycles bake shows (measured 2026-10-01: layer alone vs Cycles
                # reference 0.021 mean abs error, combined 0.295). Where the layer has
                # coverage it is the answer; uncovered texels keep Fyr's geometry.
                post_action = "REPLACE_NORMAL"
                source_image = None
            else:
                source_image = _group_material_ao_source(group, explicit_image)
                if source_image is None:
                    continue
                detail_channel = "__DETAIL_AO__"
                post_action = "MULTIPLY_AO"

            detail_tile_specs, detail_tokenized_naming, _detail_tile_diagnostics = _resolve_group_tile_plan(
                project, group, depsgraph=depsgraph, cache=udim_tile_plans
            )
            # With the tile plan the target path is the tiled name the backend
            # actually writes (X.1001.png), so apply_workspace_material_detail no
            # longer reports the required image missing on every UDIM group.
            output_targets = _build_output_targets(
                project,
                group,
                output_dir,
                selected_map_types={detail_map_type},
                selected_map_uuids={detail_uuid},
                tile_specs=detail_tile_specs,
                tokenized_naming=detail_tokenized_naming,
                redirect_dirs=_redirect_dirs,
            )
            # One detail layer per (map, tile): taking the first target only baked
            # the detail into tile 1001 and shipped the other tiles without it.
            detail_tile_targets = _material_detail_tile_targets(
                output_targets, detail_uuid, detail_tile_specs, detail_tokenized_naming
            )
            if not detail_tile_targets:
                continue
            low_obj_names = tuple(
                str(slot.object_ref.name)
                for slot in _iter_valid_object_slots(getattr(group, "low_meshes", []))
                if getattr(slot, "object_ref", None) is not None
            )
            high_obj_names = tuple(
                str(slot.object_ref.name)
                for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group))
                if getattr(slot, "object_ref", None) is not None
            )
            if not low_obj_names or not high_obj_names:
                continue
            projection_state = _group_projection_settings_state(group)
            temp_name = hashlib.sha1(f"{group_name}|{detail_uuid}|{post_action}".encode("utf-8")).hexdigest()[:16]
            effective_format = properties.effective_normal_format(detail_item)
            detail_cage_extrusion, detail_fitted_cages = _material_spec_cage(
                projection_state,
                job_groups_by_name.get(str(group_name)),
                low_obj_names,
                high_obj_names,
                fitted_cage_memo,
            )
            for tile_target in detail_tile_targets:
                tile_suffix = f".{tile_target.udim_tile}" if tile_target.udim_tile else ""
                temp_path = workspace_path / "material_detail" / f"{temp_name}{tile_suffix}.exr"
                material_specs.append(MaterialBakeSpec(
                    low_obj_names=low_obj_names,
                    high_obj_names=high_obj_names,
                    channel=detail_channel,
                    output_path=str(temp_path),
                    width=int(tile_target.width or width),
                    height=int(tile_target.height or height),
                    margin=properties.effective_bake_margin(
                        project, int(tile_target.width or width), int(tile_target.height or height)),
                    cage_extrusion=detail_cage_extrusion,
                    fitted_cages=detail_fitted_cages,
                    group_name=group_name,
                    map_uuid=detail_uuid,
                    post_action=post_action,
                    final_output_path=str(tile_target.path),
                    source_image_name=str(getattr(source_image, "name", "") or "") if source_image is not None else "",
                    flip_green=bool(
                        detail_map_type == constants.MAP_NORMAL
                        and effective_format == constants.NORMAL_FORMAT_DIRECTX
                        and not naming.normal_row_is_derivative(detail_item)
                    ),
                    uv_offset_u=float(tile_target.tile_u),
                    uv_offset_v=float(tile_target.tile_v),
                    udim_tile=int(tile_target.udim_tile),
                    normal_relief=_map_normal_relief(detail_item),
                ))

    derived_outputs.write_sidecar(workspace_path, derived_output_entries)
    manifest_path = Path(workspace_path) / "material_detail_manifest.json"
    if material_detail_entries or material_detail_diagnostics:
        # Diagnostics ride in the manifest so apply_workspace_material_detail can
        # return them on EVERY successful completion path: prepared.warnings alone
        # only surfaces at prepare time and is overwritten by the backend
        # progress warnings when the bake finishes (tester report 2026-08-24:
        # partial detail coverage baked with last_warning_count still 0).
        manifest_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": material_detail_entries,
                    "warnings": list(material_detail_diagnostics),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    elif manifest_path.exists():
        manifest_path.unlink()

    if _normal_native_rows:
        # The backend selects outputs by map type, so the Normal row's target has to
        # name the type its map config now carries. The path is untouched.
        for _group_config in job.groups:
            for _target in getattr(_group_config, "outputs", None) or ():
                if str(getattr(_target, "map_uuid", "") or "") in _normal_native_rows:
                    _target.map_type = constants.MAP_MATERIAL_NORMAL

    # Material-detail dependency maps and their hidden output targets are added
    # after the artist-facing map list is assembled. Serialize only once the
    # complete dependency graph is present.
    execution_job_path = (
        protocol.write_binary_job(job_path, job)
        if use_binary_job_transport
        else protocol.write_job(job_path, job)
    )

    # Derive runtime selection only after material-detail dependencies have
    # extended the serialized job.  A selected AO/normal map may therefore
    # require a hidden backend material map in the same invocation.
    effective_runtime_map_types = list(
        dict.fromkeys(map_config.map_type for map_config in job.maps)
    )

    return PreparedJob(
        job=job,
        job_path=execution_job_path,
        progress_path=progress_path,
        workspace_path=workspace_path,
        output_dir=output_dir,
        # Runtime selection must include hidden backend detail maps; output
        # tracking filters their reserved UUIDs so they never surface in the UI.
        effective_map_types=effective_runtime_map_types,
        material_bake_specs=material_specs,
        material_detail_entries=material_detail_entries,
        warnings=list(material_detail_diagnostics),
        deferred_multi_group_material_uuids=deferred_multi_group_uuids,
        deferred_native_normal_groups={uuid: list(names) for uuid, names in _normal_group_phases.items() if names},
        deferred_color_stream_stages=deferred_color_stream_stages,
        derived_outputs=derived_output_entries,
        group_bake_uv_layers=_group_bake_uv_layers(project, groups),
    )


def _group_bake_uv_layers(project, group_configs) -> dict[str, str]:
    """UV Set override of every exported group, by group name ("" = none)."""
    exported = {str(getattr(config, "name", "") or "") for config in group_configs or ()}
    return {
        name: (getattr(_group_projection_settings_state(group), "uv_layer_name", "") or "").strip()
        for group in getattr(project, "groups", []) or []
        if (name := str(getattr(group, "name", "") or "")) in exported
    }


def _resolve_source_groups(spec, fallback):
    """Spec `source_groups` (names) -> per-target object lists, or None.

    Returns None when the spec carries no per-target mapping, which keeps the
    single-group case on the plain shared-source path.
    """
    import bpy

    groups = tuple(getattr(spec, "source_groups", ()) or ())
    if not groups:
        return None
    resolved = []
    for names in groups:
        objects = [bpy.data.objects.get(str(name)) for name in (names or ())]
        objects = [obj for obj in objects if obj is not None]
        resolved.append(objects if objects else list(fallback))
    return resolved


def _note_material_bake_device(prepared: PreparedJob, device_note: str) -> None:
    """Record a Cycles GPU->CPU degrade as a bake WARNING, never as an error.

    ``prepared.warnings`` is the right channel: the material-only route folds it into
    the bake's warning summary, while the errors list a material queue returns marks
    the whole run FAILED on the Cycles-primary route. The note is non-empty only when
    the artist asked for GPU Compute and Cycles has no usable device, which used to
    mean an unexplained CPU bake.
    """
    if not device_note:
        return
    warnings = getattr(prepared, "warnings", None)
    if warnings is None:
        return
    if device_note not in warnings:
        warnings.append(device_note)


def _rewrite_material_detail_manifest(workspace_path, entries) -> None:
    """Replace the manifest's entries while keeping its export-time warnings.

    prepare_bake_job parks the material-detail diagnostics in the manifest so
    apply_workspace_material_detail can return them on every completion path.
    The Cycles material queue used to rewrite the file with entries only (and
    delete it when it had none), so a partial-coverage warning plus any Cycles
    material row finished with last_warning_count 0.
    """
    manifest_path = Path(workspace_path) / "material_detail_manifest.json"
    warnings: list[str] = []
    try:
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                warnings = [str(item) for item in (existing.get("warnings") or [])]
    except Exception:
        warnings = []
    entries = list(entries or [])
    if entries or warnings:
        manifest_path.write_text(
            json.dumps({"version": 1, "entries": entries, "warnings": warnings}, indent=2),
            encoding="utf-8",
        )
    elif manifest_path.exists():
        manifest_path.unlink()


def execute_material_bakes(
    prepared: PreparedJob, context, *, owns_machine: bool = False
) -> list[str]:
    """Run addon-side material map bakes from prepared.material_bake_specs.

    Returns a list of error strings for any bakes that failed (empty on full success).
    Writes output files directly — backend does not process material maps.

    ``owns_machine`` says no FYR GPU bake is running alongside this queue, so the
    user's Cycles device may be used instead of the concurrent-safe CPU default.
    This path BLOCKS the main thread for the whole queue; prefer
    :func:`execute_material_bakes_async` anywhere a window exists.
    """
    import bpy
    from . import blender_bake

    device, device_note = blender_bake.resolve_material_bake_device_with_note(
        owns_machine=owns_machine
    )
    _note_material_bake_device(prepared, device_note)
    errors: list[str] = []
    post_entries: list[dict[str, object]] = list(prepared.material_detail_entries)
    for spec in prepared.material_bake_specs:
        low_objects = [bpy.data.objects.get(name) for name in spec.low_obj_names]
        missing_lows = [name for name, obj in zip(spec.low_obj_names, low_objects) if obj is None]
        if missing_lows:
            errors.append(f"Material bake skipped: low object(s) not found: {', '.join(missing_lows)}")
            continue
        high_objects = [bpy.data.objects.get(name) for name in spec.high_obj_names]
        missing_highs = [name for name, obj in zip(spec.high_obj_names, high_objects) if obj is None]
        if missing_highs:
            errors.append(f"Material bake skipped: high object(s) not found: {', '.join(missing_highs)}")
            continue
        # Bake path: Cycles via bpy.ops.object.bake.
        # NOTE: Items with a valid image-texture fast path (M4) were already routed to the
        # backend job in prepare_bake_job and are not present in material_bake_specs.
        # Specs here only cover channels that need a full Cycles bake.
        try:
            source_image = (
                bpy.data.images.get(spec.source_image_name)
                if str(spec.source_image_name or "").strip()
                else None
            )
            blender_bake.bake_material_channel(
                low_objects,
                source_objects=high_objects,
                channel=spec.channel,
                width=spec.width,
                height=spec.height,
                output_path=spec.output_path,
                margin=spec.margin,
                cage_extrusion=spec.cage_extrusion,
                source_image=source_image,
                uv_offset_u=float(getattr(spec, "uv_offset_u", 0.0) or 0.0),
                uv_offset_v=float(getattr(spec, "uv_offset_v", 0.0) or 0.0),
                custom_output_name=str(getattr(spec, "custom_output_name", "") or ""),
                only_material=str(getattr(spec, "only_material", "") or ""),
                # A spec with a post action is a hidden detail layer that
                # material_detail.py composites using its alpha as coverage; only a
                # spec writing its own output file is what the artist receives.
                artist_facing=not bool(spec.post_action),
                device=device,
                source_groups=_resolve_source_groups(spec, high_objects),
                normal_relief=float(getattr(spec, "normal_relief", 0.5) or 0.5),
                normal_flip_green=bool(getattr(spec, "normal_flip_green", False)),
                uv_layer_name=str(getattr(spec, "uv_layer_name", "") or ""),
                fitted_cages=tuple(getattr(spec, "fitted_cages", ()) or ()),
                cage_extrusions=tuple(getattr(spec, "cage_extrusions", ()) or ()),
            )
            if spec.post_action and spec.final_output_path:
                post_entries.append({
                    "action": spec.post_action,
                    "detail_path": spec.output_path,
                    "final_path": spec.final_output_path,
                    "flip_green": bool(spec.flip_green),
                    "group_name": spec.group_name,
                    "map_uuid": spec.map_uuid,
                })
        except Exception as exc:
            errors.append(f"Material bake failed for '{spec.group_name}' {spec.channel}: {exc}")

    _rewrite_material_detail_manifest(prepared.workspace_path, post_entries)
    return errors


_ASYNC_MATERIAL_BAKES: dict[str, dict[str, object]] = {}


class MaterialBakeQueueStatus(NamedTuple):
    """Live state of the addon-side Cycles material queue for one bake job."""

    workspace_path: str
    job_id: str
    done: int
    total: int
    channel: str
    group_name: str
    cancel_requested: bool

    @property
    def label(self) -> str:
        position = min(self.done + 1, max(1, self.total))
        # "Material detail" is a different feature (procedural detail folded into the
        # Normal/AO maps). This queue is the Cycles fallback for material CHANNELS, and
        # calling it detail told an artist nothing about why a bake that normally takes
        # seconds had just grown by a minute.
        prefix = "Cancelling Cycles material bake" if self.cancel_requested else "Baking on Cycles"
        return f"{prefix}… ({position}/{max(1, self.total)})"


def material_bakes_pending(workspace_path) -> bool:
    return str(Path(workspace_path)) in _ASYNC_MATERIAL_BAKES


def _material_bake_queue_status(workspace_key: str, state: dict) -> MaterialBakeQueueStatus:
    current = state.get("current")
    return MaterialBakeQueueStatus(
        workspace_path=workspace_key,
        job_id=str(state.get("job_id", "") or ""),
        done=int(state.get("index", 0) or 0),
        total=len(state.get("specs", []) or []),
        channel=str(getattr(current, "channel", "") or ""),
        group_name=str(getattr(current, "group_name", "") or ""),
        cancel_requested=bool(state.get("cancel_requested", False)),
    )


def active_material_bake_status(job_id: str | None = None) -> MaterialBakeQueueStatus | None:
    """Status of a queued/running addon-side material phase, or None when idle.

    The Cycles material queue outlives the backend process, so every busy-state
    surface has to consult it as part of the active bake rather than treating the
    backend's exit as the end of the run.
    """
    wanted = str(job_id or "").strip()
    for workspace_key, state in _ASYNC_MATERIAL_BAKES.items():
        status = _material_bake_queue_status(workspace_key, state)
        if wanted and status.job_id != wanted:
            continue
        return status
    return None


def reset_async_material_bakes() -> int:
    """Forget every queued material phase. Returns how many were dropped.

    The queue is driven by a NON-persistent bpy timer, which Blender discards on
    wm.open_mainfile while this dict survives: finish_queue() then never runs, so
    active_material_bake_status() stays non-None and every later bake in the
    session is refused with "Blender is still baking material detail from the
    previous run". Called from the file-load reset, where the job is gone anyway.
    """
    dropped = len(_ASYNC_MATERIAL_BAKES)
    _ASYNC_MATERIAL_BAKES.clear()
    return dropped


def cancel_material_bakes(job_id: str | None = None) -> bool:
    """Ask the material queue to stop after the in-flight Blender bake finishes."""
    wanted = str(job_id or "").strip()
    cancelled = False
    for _workspace_key, state in _ASYNC_MATERIAL_BAKES.items():
        if wanted and str(state.get("job_id", "") or "") != wanted:
            continue
        state["cancel_requested"] = True
        cancelled = True
    return cancelled


def _material_spec_input_key(spec: MaterialBakeSpec) -> tuple:
    # Hidden detail layers of identical inputs share one bake. A spec writing its own file
    # never does: its file would not exist, and two UDIM tiles of one low differ only here.
    return (
        "" if spec.post_action else str(spec.output_path or ""),
        round(float(spec.uv_offset_u), 7),
        round(float(spec.uv_offset_v), 7),
        tuple(spec.cage_extrusions or ()),
        spec.low_obj_names,
        spec.high_obj_names,
        spec.channel,
        int(spec.width),
        int(spec.height),
        int(spec.margin),
        round(float(spec.cage_extrusion), 7),
        spec.source_image_name,
        tuple(str(cage.low_name) for cage in spec.fitted_cages or ()),
        str(spec.uv_layer_name or ""),
    )


def track_material_only_outputs(project, prepared: PreparedJob) -> None:
    """Register output records for an all-addon-side bake with no backend phase.

    A MATERIAL-workflow (Bake Selected Materials) project self-bakes every channel via
    Cycles; execute_material_bakes wrote each file directly. Normally output tracking rides
    on the backend job's reported outputs, so with the backend skipped we populate
    project.latest_outputs from the material specs instead — one record per spec — so the
    reversible PBR preview, output history, and incremental re-bake see the results.
    """
    properties.reset_latest_outputs(project)
    project.last_progress_percent = 100.0
    project.last_stage_progress_percent = -1.0
    project.last_error_count = 0
    project.last_warning_count = 0
    project.last_error_summary = ""
    for spec in prepared.material_bake_specs:
        file_path = str(spec.final_output_path or spec.output_path or "").strip()
        if not file_path:
            continue
        channel = str(spec.channel or "").strip().upper()
        row = properties.find_map_setting_by_uuid(project, spec.map_uuid) if spec.map_uuid else None
        row_type = str(getattr(row, "map_type", "") or "").strip().upper() if row is not None else ""
        # Two different rows produce spec.channel == "NORMAL": the MATERIAL-workflow
        # geometry Normal row (a MAP_NORMAL row, baked from the object's own Normal
        # Map / Bump nodes) and a MAP_MATERIAL row whose material_channel is NORMAL.
        # Only the row's own map_type tells them apart.
        if channel == constants.MATERIAL_CHANNEL_NORMAL and row_type != constants.MAP_MATERIAL:
            effective_type = constants.MAP_NORMAL
        else:
            effective_type = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel, constants.MAP_MATERIAL_ALBEDO)
        item = project.latest_outputs.add()
        item.map_uuid = str(spec.map_uuid or "")
        # Same contract as _latest_output_descriptor: raw stack type in map_type so
        # the Outputs panel matches the row, effective type alongside it for the
        # template/export side. With no resolvable row the effective type is all
        # there is, so it fills both.
        item.map_type = row_type or effective_type
        item.effective_map_type = effective_type
        item.group_name = str(spec.group_name or "")
        item.output_suffix = str(getattr(row, "output_suffix", "") or "") if row is not None else ""
        item.display_name = naming.map_label(effective_type)
        item.file_path = file_path


def execute_material_bakes_async(
    prepared: PreparedJob,
    context,
    *,
    on_complete=None,
    on_progress=None,
    owns_machine: bool = False,
) -> bool:
    """Start unsupported Blender material evaluations as modal background jobs.

    Returns True when work was scheduled. Direct texture material detail is
    already part of the backend job and never enters this queue.

    ``owns_machine`` says no FYR GPU bake is running alongside this queue (the
    Cycles-primary route), so the user's Cycles device may be used instead of the
    concurrent-safe CPU default.
    """
    import bpy
    from . import blender_bake

    if not prepared.material_bake_specs:
        return False
    device, device_note = blender_bake.resolve_material_bake_device_with_note(
        owns_machine=owns_machine
    )
    _note_material_bake_device(prepared, device_note)
    workspace_key = str(Path(prepared.workspace_path))
    if workspace_key in _ASYNC_MATERIAL_BAKES:
        return True

    unique_specs: list[MaterialBakeSpec] = []
    aliases_by_key: dict[tuple, list[MaterialBakeSpec]] = {}
    canonical_by_key: dict[tuple, MaterialBakeSpec] = {}
    for spec in prepared.material_bake_specs:
        key = _material_spec_input_key(spec)
        canonical = canonical_by_key.get(key)
        if canonical is None:
            canonical_by_key[key] = spec
            unique_specs.append(spec)
        else:
            aliases_by_key.setdefault(key, []).append(spec)

    state: dict[str, object] = {
        "specs": unique_specs,
        "aliases": aliases_by_key,
        "index": 0,
        "session": None,
        "current": None,
        "errors": [],
        "entries": list(prepared.material_detail_entries),
        "callback": on_complete,
        "progress_callback": on_progress,
        "job_id": str(getattr(prepared.job, "job_id", "") or ""),
        "cancel_requested": False,
    }
    _ASYNC_MATERIAL_BAKES[workspace_key] = state

    def report_progress():
        callback = state.get("progress_callback")
        if not callable(callback):
            return
        try:
            callback(_material_bake_queue_status(workspace_key, state))
        except Exception as exc:
            print(f"[MasterBaker] material progress callback failed: {exc}")

    def append_entry(spec, detail_path):
        if spec.post_action and spec.final_output_path:
            state["entries"].append({
                "action": spec.post_action,
                "detail_path": str(detail_path),
                "final_path": spec.final_output_path,
                "flip_green": bool(spec.flip_green),
                "group_name": spec.group_name,
                "map_uuid": spec.map_uuid,
            })

    def finish_queue():
        entries = list(state["entries"])
        _rewrite_material_detail_manifest(prepared.workspace_path, entries)
        errors = list(state["errors"])
        _ASYNC_MATERIAL_BAKES.pop(workspace_key, None)
        callback = state.get("callback")
        if callable(callback):
            try:
                callback(errors)
            except Exception as exc:
                print(f"[MasterBaker] material completion callback failed: {exc}")

    def timer_step():
        try:
            session = state.get("session")
            if session is None:
                index = int(state["index"])
                specs = state["specs"]
                if index >= len(specs) or state.get("cancel_requested"):
                    if state.get("cancel_requested") and index < len(specs):
                        state["errors"].append(
                            f"Material bake cancelled with {len(specs) - index} channel(s) remaining"
                        )
                    finish_queue()
                    return None
                spec = specs[index]
                low_objects = [bpy.data.objects.get(name) for name in spec.low_obj_names]
                high_objects = [bpy.data.objects.get(name) for name in spec.high_obj_names]
                missing = [
                    name
                    for name, obj in zip(spec.low_obj_names + spec.high_obj_names, low_objects + high_objects)
                    if obj is None
                ]
                if missing:
                    state["errors"].append(
                        f"Material bake skipped: object(s) not found: {', '.join(missing)}"
                    )
                    state["index"] = index + 1
                    return 0.01
                source_image = (
                    bpy.data.images.get(spec.source_image_name)
                    if str(spec.source_image_name or "").strip()
                    else None
                )
                session = blender_bake.MaterialBakeSession(
                    low_objects,
                    source_objects=high_objects,
                    channel=spec.channel,
                    width=spec.width,
                    height=spec.height,
                    output_path=spec.output_path,
                    margin=spec.margin,
                    cage_extrusion=spec.cage_extrusion,
                    source_image=source_image,
                    uv_offset_u=float(getattr(spec, "uv_offset_u", 0.0) or 0.0),
                    uv_offset_v=float(getattr(spec, "uv_offset_v", 0.0) or 0.0),
                    custom_output_name=str(getattr(spec, "custom_output_name", "") or ""),
                    only_material=str(getattr(spec, "only_material", "") or ""),
                    artist_facing=not bool(spec.post_action),
                    device=device,
                    source_groups=_resolve_source_groups(spec, high_objects),
                    normal_relief=float(getattr(spec, "normal_relief", 0.5) or 0.5),
                    normal_flip_green=bool(getattr(spec, "normal_flip_green", False)),
                    uv_layer_name=str(getattr(spec, "uv_layer_name", "") or ""),
                    fitted_cages=tuple(getattr(spec, "fitted_cages", ()) or ()),
                    cage_extrusions=tuple(getattr(spec, "cage_extrusions", ()) or ()),
                )
                state["session"] = session
                state["current"] = spec
                report_progress()
            if not session.poll():
                return 0.1

            spec = state["current"]
            if session.error:
                state["errors"].append(
                    f"Material bake failed for '{spec.group_name}' {spec.channel}: {session.error}"
                )
            else:
                append_entry(spec, spec.output_path)
                for alias in state["aliases"].get(_material_spec_input_key(spec), []):
                    append_entry(alias, spec.output_path)
            state["index"] = int(state["index"]) + 1
            state["session"] = None
            state["current"] = None
            return 0.01
        except Exception as exc:
            state["errors"].append(f"Material bake queue failed: {exc}")
            finish_queue()
            return None

    bpy.app.timers.register(timer_step, first_interval=0.01)
    return True


def prepare_debug_overlay_job(context, project, group, *, debug_view: protocol.DebugViewConfig | None = None) -> PreparedDebugOverlayJob:
    depsgraph = context.evaluated_depsgraph_get()
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    debug_root = workspace.ensure_directory(
        storage_cleanup.ensure_scratch_subdir("debug_overlay") / workspace.slugify_name(project.name)
    )
    workspace_path = workspace.ensure_directory(debug_root / workspace.slugify_name(group.name))
    meshes_root = workspace.ensure_directory(workspace_path / "meshes")
    result_path = workspace_path / "debug_overlay.json"
    job_path = workspace_path / "job.mbjob"
    group_root = workspace.ensure_directory(meshes_root / workspace.slugify_name(group.name))
    cache_key = _debug_overlay_cache_key(context, project, group)
    input_signature = debug_overlay_input_signature(project, group)
    static_signature, dynamic_signature = input_signature
    use_shared_memory = mesh_transport.shared_memory_transport_enabled()
    cache_entry = _DEBUG_OVERLAY_EXPORT_CACHE.get(cache_key)
    if cache_entry is None or cache_entry.static_signature != static_signature:
        opacity_by_object = _collect_high_object_opacity_bindings(
            project,
            workspace_path,
            {str(getattr(group, "name", "") or "")},
        )
        low_meshes = _export_low_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        high_meshes = _export_high_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
            opacity_by_object=opacity_by_object,
            self_material=str(getattr(project, "workflow", "") or "").strip().upper()
            == constants.WORKFLOW_MATERIAL,
        )
        cage_meshes = _export_cage_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        cache_entry = _DebugOverlayExportCacheEntry(
            workspace_path=workspace_path,
            group_root=group_root,
            static_signature=static_signature,
            dynamic_signature=dynamic_signature,
            low_meshes=low_meshes,
            high_meshes=high_meshes,
            cage_meshes=cage_meshes,
        )
        _DEBUG_OVERLAY_EXPORT_CACHE[cache_key] = cache_entry
    elif cache_entry.dynamic_signature != dynamic_signature:
        cache_entry.cage_meshes = _export_cage_mesh_refs(
            group,
            depsgraph,
            group_root,
            workspace_key=workspace_path,
            use_shared_memory=use_shared_memory,
        )
        cache_entry.dynamic_signature = dynamic_signature

    group_config = _build_group_config_from_exported_refs(
        project,
        group,
        cache_entry.low_meshes,
        cache_entry.high_meshes,
        cache_entry.cage_meshes,
    )
    group_config.skew_correction_maps = _write_skew_correction_maps(group, Path(workspace_path) / "skew_correction")
    group_config.outputs = []
    group_config.debug_heatmap_enabled = False
    overlay_state = properties.overlay_settings_state(settings)
    group_config.debug_ray_miss_enabled = bool(getattr(overlay_state, "show_ray_miss_debug", False))
    job = protocol.BakeJob(
        version=constants.PROTOCOL_VERSION,
        job_id=f"debug_{workspace.slugify_name(project.name)}_{workspace.slugify_name(group.name)}",
        created_at=datetime.now(timezone.utc).isoformat(),
        progress_path=str(workspace_path / "progress.json"),
        project=protocol.BakeProjectInfo(
            name=project.name,
            output_root=str(debug_root),
            workspace=str(workspace_path),
            resolution_width=int(project.resolution_x),
            resolution_height=int(project.resolution_y),
            bit_depth=int(project.bit_depth),
            margin=properties.effective_bake_margin(project, project.resolution_x, project.resolution_y),
            tangent_basis=constants.normalize_tangent_basis(project.tangent_basis),
            bake_mode=project.bake_mode,
            aa_samples=properties.resolve_aa_samples(project),
            anti_aliasing=constants.samples_to_anti_aliasing(properties.resolve_aa_samples(project)),
            execution_backend=constants.EXECUTION_BACKEND_AUTO,
            image_format=str(getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT)),
            respect_opacity=bool(getattr(project, "respect_opacity", True)),
        ),
        maps=[],
        groups=[group_config],
        debug_view=debug_view,
        debug_heatmap_blob_enabled=True,
    )
    job_path = protocol.write_binary_job(job_path, job)
    return PreparedDebugOverlayJob(
        job=job,
        job_path=job_path,
        workspace_path=workspace_path,
        result_path=result_path,
        group_name=group.name,
        input_signature=input_signature,
    )


def _produced_file_key(
    group_name: str,
    map_type: str,
    output_suffix: str = "",
    map_uuid: str = "",
    udim_tile: int = 0,
) -> tuple[str, str, str, str, int]:
    # udim_tile is part of the key because one map_uuid repeats across a texture set's tiles.
    # Keyed on uuid alone, each tile's produced file would overwrite the previous one in
    # project.latest_outputs and only the last tile would survive in the output record.
    # 0 for untiled, so single-tile projects keep a stable key shape.
    return (
        str(group_name or ""),
        str(map_type or ""),
        str(output_suffix or ""),
        str(map_uuid or ""),
        int(udim_tile or 0),
    )


def _produced_file_legacy_key(group_name: str, map_type: str, output_suffix: str = "") -> tuple[str, str, str]:
    return (str(group_name or ""), str(map_type or ""), str(output_suffix or ""))


def _produced_file_udim_tile(produced) -> int:
    """The tile a produced file belongs to, from the backend's field or the filename.

    The reported field is authoritative; the filename is the fallback for a produced file
    that predates the field (a stale progress JSON on disk, or a re-adopted output).
    """
    from . import udim as _udim

    try:
        reported = int(getattr(produced, "udim_tile", 0) or 0)
    except (TypeError, ValueError):
        reported = 0
    if reported:
        return reported
    return _udim.tile_from_path(str(getattr(produced, "path", "") or ""))


def _collapse_udim_produced_files(produced_files):
    """Fold a texture set's per-tile produced files into one entry per logical map.

    Returns ``(representatives, tiles_by_representative_path)``. The representative is the
    lowest-numbered tile's produced file, emitted **at its own position in the input list** so
    the untiled maps around it keep their relative order and a mixed project's output list does
    not reshuffle; the remaining tiles are carried in the side table and reattached to the
    finished descriptor.

    Keying the side table on the representative's concrete path -- rather than on
    (group, map, uuid) -- is deliberate: descriptors translate effective backend map types
    back to raw stack types along the way, so the path is the only identifier that survives
    the round trip intact.

    An untiled produced file passes through untouched. That is the single-tile common case and
    it must come out the far side indistinguishable from before UDIM existed.
    """
    from . import udim as _udim

    grouped: dict[tuple[str, str, str, str], list[tuple[int, str]]] = {}
    for produced in produced_files:
        path = str(getattr(produced, "path", "") or "").strip()
        if not path:
            continue
        tile = _produced_file_udim_tile(produced)
        if not tile:
            continue
        logical = _udim.logical_udim_path(path)
        if logical == path:
            # Tile reported but the filename carries none: tokenized naming is off, so there
            # is exactly one file and nothing to collapse.
            continue
        key = (
            str(getattr(produced, "group_name", "") or ""),
            str(getattr(produced, "map_type", "") or ""),
            str(getattr(produced, "map_uuid", "") or ""),
            logical,
        )
        grouped.setdefault(key, []).append((tile, path))

    representatives: list = []
    tiles_by_path: dict[str, list[tuple[int, str]]] = {}
    emitted: set[tuple[str, str, str, str]] = set()
    for produced in produced_files:
        path = str(getattr(produced, "path", "") or "").strip()
        tile = _produced_file_udim_tile(produced) if path else 0
        logical = _udim.logical_udim_path(path) if path else ""
        key = (
            str(getattr(produced, "group_name", "") or ""),
            str(getattr(produced, "map_type", "") or ""),
            str(getattr(produced, "map_uuid", "") or ""),
            logical,
        )
        entries = grouped.get(key) if tile else None
        if not entries:
            representatives.append(produced)
            continue
        if key in emitted:
            continue
        ordered = sorted(set(entries))
        if tile != ordered[0][0]:
            continue
        emitted.add(key)
        representatives.append(produced)
        tiles_by_path[path] = ordered
    return representatives, tiles_by_path


def _attach_udim_tiles(descriptors: list[dict], tiles_by_path: dict[str, list[tuple[int, str]]]) -> None:
    """Hang the concrete tile list, the logical ``<UDIM>`` path and stale files off descriptors.

    Stale files are only ever *reported* here (plan §1.4): a tile that stops being occupied
    keeps its file until the artist runs the cleanup operator, because the file may have been
    hand-edited or already referenced downstream and deleting it is unrecoverable.
    """
    if not tiles_by_path:
        return
    from . import udim as _udim
    from . import udim_images as _udim_images

    directory_names: dict[str, list[str]] = {}
    for descriptor in descriptors:
        path = str(descriptor.get("file_path", "") or "")
        tiles = tiles_by_path.get(path)
        if not tiles:
            continue
        logical = _udim.logical_udim_path(path)
        if not _udim.is_logical_udim_path(logical):
            continue
        directory = str(Path(logical).parent)
        if directory not in directory_names:
            directory_names[directory] = _udim.directory_file_names(logical)
        live_numbers = [tile_number for tile_number, _tile_path in tiles]
        stale = _udim_images.find_stale_tile_files(
            logical,
            live_numbers,
            directory_names=directory_names[directory],
        )
        descriptor["udim_logical_path"] = logical
        # Sizes come from each file's header, not from the project settings: tiles may
        # legitimately differ in resolution, and the artist may have changed the project
        # since the bake. apply_progress_to_project runs once per finished job, so this is a
        # handful of 24-byte reads, not a per-tick cost.
        descriptor["udim_tiles"] = [
            _udim_tile_record(tile_number, tile_path, stale=False)
            for tile_number, tile_path in tiles
        ] + [
            _udim_tile_record(tile_number, tile_path, stale=True)
            for tile_number, tile_path in stale
        ]


def _udim_tile_record(tile_number: int, tile_path: str, *, stale: bool) -> dict:
    from . import udim_images as _udim_images

    width, height = _udim_images.read_image_size(tile_path)
    return {
        "udim_tile": int(tile_number),
        "file_path": str(tile_path),
        "width": int(width),
        "height": int(height),
        "stale": bool(stale),
    }


# Moved to naming.py (bpy-free) so validation can resolve file names exactly like
# export does; kept as an alias for the ~dozen callers in this module.
effective_map_type_for_setting = naming.effective_map_type_for_setting


# Keep private alias for backwards-compat within this module.
_effective_map_type_for_setting = effective_map_type_for_setting


# Map material channel → Principled BSDF input socket name
_MATERIAL_CHANNEL_TO_SOCKET: dict[str, str] = {
    constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
    constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    constants.MATERIAL_CHANNEL_METALNESS: "Metallic",
    constants.MATERIAL_CHANNEL_EMISSION: "Emission Color",
    constants.MATERIAL_CHANNEL_OPACITY: "Alpha",
    constants.MATERIAL_CHANNEL_SPECULAR: "Specular IOR Level",
    constants.MATERIAL_CHANNEL_TRANSMISSION: "Transmission Weight",
}


def resolve_material_fast_path(obj, channel: str, workspace_path=None) -> str | None:
    """Return an absolute image file path if the target channel on every material slot
    is a direct Image Texture → Principled BSDF connection with a file-backed image.

    Returns None if the fast path is not available (procedural nodes, packed images
    that can't be resolved to a path, mixed or missing materials).
    """
    import bpy
    import os

    socket_name = _MATERIAL_CHANNEL_TO_SOCKET.get(str(channel or "").strip().upper())
    if not socket_name:
        return None

    material_slots = getattr(obj, "material_slots", None)
    if not material_slots:
        return None

    resolved_paths: list[str] = []
    for slot in material_slots:
        mat = slot.material if slot else None
        if mat is None:
            return None
        node_tree = getattr(mat, "node_tree", None)
        if node_tree is None:
            return None

        # Find the active Material Output node's surface socket
        principled = None
        for node in node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                principled = node
                break
        if principled is None:
            return None

        input_socket = principled.inputs.get(socket_name)
        if input_socket is None:
            return None

        if not input_socket.is_linked:
            return None

        link = input_socket.links[0]
        src_node = link.from_node
        if src_node.type != "TEX_IMAGE":
            return None

        # Backend fast path samples the image with the high-poly hit UV only. Object /
        # Generated coordinates and non-identity Mapping must use Cycles so the shader
        # vector chain is evaluated at the projected hit (albedo often already falls
        # through because Base Color is mixed with AO).
        if not _image_texture_uses_plain_uv(src_node):
            return None

        image = src_node.image
        if image is None:
            return None

        # A tiled (UDIM) source resolves to its LOGICAL "<UDIM>" path. The concrete tiles are
        # enumerated later, once every slot has agreed on the same source, and each is shipped
        # to the backend separately -- the backend picks the tile per hit from the high mesh's
        # global UV. A tiled image that is not file-backed (packed or generated) has no
        # per-tile file to read, so it stays off the fast path and falls back to EEVEE, which
        # is slower but correct; exporting its active tile alone would bake wrong colours on
        # every other tile.
        if image.source == "TILED":
            from . import udim as _udim

            tiled_raw = bpy.path.abspath(image.filepath, library=image.library)
            tiled_logical = os.path.normpath(tiled_raw) if tiled_raw else ""
            if not tiled_logical or not _udim.is_logical_udim_path(tiled_logical):
                return None
            if not _udim.sibling_tile_paths(tiled_logical):
                return None
            resolved_paths.append(tiled_logical)
            continue

        # Only file-backed images are usable for the fast path
        if image.source not in {"FILE", "SEQUENCE"}:
            return None

        raw_path = bpy.path.abspath(image.filepath, library=image.library)
        abs_path = os.path.normpath(raw_path)
        if not os.path.isfile(abs_path):
            # Packed image: save a workspace-owned PNG without mutating the user's
            # image datablock. Image.save() takes no filepath argument; the previous
            # call used an invalid API signature and silently disabled this fast path.
            identity = f"{getattr(image, 'name_full', getattr(image, 'name', 'image'))}|{image.filepath}"
            packed_name = f"packed_{hashlib.sha1(identity.encode('utf-8', errors='replace')).hexdigest()[:16]}.png"
            if workspace_path is None:
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                temp_path = tmp.name
            else:
                material_input_root = Path(workspace_path) / "material_inputs"
                material_input_root.mkdir(parents=True, exist_ok=True)
                temp_path = str(material_input_root / packed_name)
            try:
                import numpy as np

                width, height = int(image.size[0]), int(image.size[1])
                pixels = np.empty(width * height * 4, dtype=np.float32)
                image.pixels.foreach_get(pixels)
                if not _write_rgba_png_file(temp_path, width, height, pixels):
                    return None
                abs_path = temp_path
            except Exception:
                return None

        resolved_paths.append(abs_path)

    if not resolved_paths:
        return None

    # All slots must resolve to the same image for the fast path to apply
    if len(set(resolved_paths)) != 1:
        return None

    return resolved_paths[0]


def _normalize_material_source_to_png(source_path: str, workspace_path) -> str | None:
    """Return a PNG path for the source image, normalizing if necessary.

    If the source is already a PNG file on disk, return it directly.
    Otherwise load it in Blender, save a copy as PNG to workspace_path, and return that path.
    Returns None on any failure.
    """
    import bpy
    import os

    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".png" and os.path.isfile(source_path):
        return source_path

    import hashlib
    uid = hashlib.md5(source_path.encode("utf-8", errors="replace")).hexdigest()[:12]
    out_path = str(Path(workspace_path) / f"mat_fp_{uid}.png")
    if os.path.isfile(out_path):
        return out_path

    try:
        img = bpy.data.images.load(source_path, check_existing=True)
        img_copy = img.copy()
        try:
            img_copy.file_format = "PNG"
            img_copy.filepath_raw = out_path
            img_copy.save()
        finally:
            image_cleanup.remove_image_when_safe(img_copy, reason="material fingerprint copy")
        if os.path.isfile(out_path):
            return out_path
        return None
    except Exception:
        return None


def _collect_native_normal_rows(
    project,
    workspace_path,
    selected_map_types,
    selected_map_uuids,
    selected_group_names,
    *,
    is_material_workflow: bool,
    detail_fp_by_uuid,
    diagnostics=None,
    group_phases_out: dict | None = None,
    group_phase_excluded_uuids=(),
) -> dict:
    """Normal rows that bake as the native MATERIAL NORMAL channel.

    Returns ``{map_uuid: (NormalAsMaterialRow, ir_source)}``. A row qualifies when it is
    a tangent Normal row on Material Detail = Auto, the high materials carry real
    normal detail that is NOT already composed by the image fast path, the Fyr backend
    is the one running, and the whole graph compiles to one native program. Anything
    else keeps the existing route, so a refusal here is never an error.
    """
    from . import material_ir, normal_material_route

    rows: dict = {}
    if is_material_workflow:
        return rows
    try:
        from . import bake_backends as _bake_backends

        if _bake_backends.resolve_active_render_backend().backend_id == "cycles":
            return rows
    except Exception:
        pass
    detail_groups = [
        group
        for group in getattr(project, "groups", [])
        if selected_group_names is None
        or str(getattr(group, "name", "") or "") in selected_group_names
    ]
    for item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if not normal_material_route.row_is_eligible(item):
            continue
        item_uuid = properties.ensure_map_setting_uuid(item)
        if detail_fp_by_uuid.get(item_uuid):
            continue
        if not any(_group_has_material_normal_detail(group) for group in detail_groups):
            continue
        row = normal_material_route.NormalAsMaterialRow(item)
        try:
            source = _collect_material_ir_source(
                row,
                project,
                workspace_path,
                selected_group_names,
                allow_ray_ops=True,
                diagnostics=None,
            )
        except Exception as exc:  # noqa: BLE001 - the Cycles detail route still works
            # Not silent: the fallback is correct but can be minutes slower, and a
            # console-only line never reaches the artist.
            import traceback

            traceback.print_exc()
            message = (
                "Normal map material detail could not bake on the GPU "
                f"({type(exc).__name__}: {exc}); it was baked through Cycles instead."
            )
            print(f"[Fyr Baker] {message}")
            if diagnostics is not None and message not in diagnostics:
                diagnostics.append(message)
            continue
        program = source.get("program") if isinstance(source, dict) else None
        if (
            not isinstance(source, dict)
            or source.get("multi_group_refusal")
            or not isinstance(program, material_ir.MaterialIrProgram)
            or not program.native
        ):
            # The program over every selected group is not native (one group's highs
            # lack an attribute another's material reads, a group has no material, ...).
            # Each group compiled alone may still be: the caller bakes those as per-group
            # native phases and composites them over the geometry Normal.
            if (
                group_phases_out is not None
                and len(detail_groups) > 1
                and item_uuid not in group_phase_excluded_uuids
                and not naming.normal_row_is_derivative(item)
            ):
                native_groups = _native_normal_detail_groups(
                    row, project, workspace_path, detail_groups, material_ir
                )
                if native_groups:
                    group_phases_out[item_uuid] = native_groups
            continue
        _raise_bevel_samples_for_normal_bake(program)
        _stamp_bevel_connected_only(program, bool(getattr(project, "bevel_connected_only", True)))
        rows[item_uuid] = (row, source)
    return rows


def _every_selected_group_compiles_native(
    mat_item, project, workspace_path, selected_group_names, *, allow_ray_ops: bool
) -> bool:
    """True when two or more groups are selected and each compiles natively on its own."""
    from . import material_ir

    names = [
        str(getattr(group, "name", "") or "")
        for group in project.groups
        if selected_group_names is None
        or str(getattr(group, "name", "") or "") in selected_group_names
    ]
    if len(names) < 2:
        return False
    for name in names:
        try:
            source = _collect_material_ir_source(
                mat_item, project, workspace_path, {name},
                allow_ray_ops=allow_ray_ops, diagnostics=None, compile_only=True,
            )
        except Exception:  # noqa: BLE001 - a group that cannot compile keeps the row on Cycles
            return False
        program = source.get("program") if isinstance(source, dict) else None
        if not isinstance(program, material_ir.MaterialIrProgram) or not program.native:
            return False
    return True


def _native_normal_detail_groups(row, project, workspace_path, detail_groups, material_ir) -> list[str]:
    """Names of the groups whose own normal detail compiles to a native program alone.

    Only groups that carry detail are asked; a group without any keeps the geometry Normal
    the main job writes. Ray ops are allowed: each group's phase is an all-material job.
    """
    names: list[str] = []
    for group in detail_groups:
        if not _group_has_material_normal_detail(group):
            continue
        group_name = str(getattr(group, "name", "") or "")
        try:
            source = _collect_material_ir_source(
                row, project, workspace_path, {group_name},
                allow_ray_ops=True, diagnostics=None, compile_only=True,
            )
        except Exception:  # noqa: BLE001 - this group keeps the Cycles detail layer
            continue
        program = source.get("program") if isinstance(source, dict) else None
        if (
            isinstance(source, dict)
            and not source.get("multi_group_refusal")
            and isinstance(program, material_ir.MaterialIrProgram)
            and program.native
        ):
            names.append(group_name)
    return names


#: Bevel rays per texel and AA pass for a Normal map bake. The node's own Samples
#: property (Blender default 4) is a per-render-sample count: a Cycles render or bake
#: multiplies it by hundreds of path samples, while a Fyr bake only multiplies it by the
#: spatial AA passes. Baked at the node value the bevel band is visibly grainy.
_NORMAL_BAKE_BEVEL_SAMPLES = 96


def _raise_bevel_samples_for_normal_bake(program) -> None:
    """Lift every Bevel op to the bake floor, inside the program's GPU ray budget."""
    from . import material_ir

    ops = [op for op in (getattr(program, "ops", None) or []) if isinstance(op, dict)]
    bevels = [op for op in ops if str(op.get("op", "") or "").upper() == material_ir.OPCODE_BEVEL]
    if not bevels:
        return
    current = sum(int(op.get("samples", 4) or 4) for op in bevels)
    spare = material_ir.GPU_MAX_RAY_SAMPLES - material_ir.program_ray_sample_total(program)
    per_op = (current + max(0, spare)) // len(bevels)
    target = min(_NORMAL_BAKE_BEVEL_SAMPLES, material_ir.RAY_NODE_MAX_SAMPLES, per_op)
    for op in bevels:
        op["samples"] = max(int(op.get("samples", 4) or 4), int(target))


def _stamp_bevel_connected_only(program, connected_only: bool) -> None:
    """Restrict every Bevel op to the connected piece it shades (backend mode bit).

    Cycles' Bevel walks the whole shaded object, so two loose pieces of one mesh that
    sit within the radius round into each other (keys resting on a base). The key is
    only written when on, so a program with the option off is byte-identical to before.
    """
    from . import material_ir

    for op in (getattr(program, "ops", None) or []):
        if isinstance(op, dict) and str(op.get("op", "") or "").upper() == material_ir.OPCODE_BEVEL:
            if connected_only:
                op["connected_only"] = True
            else:
                op.pop("connected_only", None)


def _job_is_material_only_backend_batch(
    project, selected_map_types, selected_map_uuids, *, native_normal_uuids=()
) -> bool:
    """Whether every backend map this job can produce is a material fast-path map.

    This is the addon-side mirror of the backend's
    `projection_shading_batch_is_material_only()`
    (master_baker_backend_gpu_d3d12.cpp), which requires every map in a shading
    batch to be `GpuProjectionMapKind::MaterialFastPath` before it selects the
    MATERIAL_ONLY shader permutation — the only permutation that compiles the
    Material IR secondary-ray opcodes in. Anywhere else the opcode writes the
    neutral fully-unoccluded 1.0, so this predicate is what lets the compiler
    pass `allow_ray_ops=True`.

    A raw `MAP_MATERIAL` row is exactly what becomes a MaterialFastPath map; every
    other raw map type becomes a geometry map and would force the megakernel. The
    backend may still split an all-material job into several batches, but each
    split stays all-material, so the predicate survives batching.

    Deliberately conservative:

    * `None` selection means "every enabled map", which `_selected_project_maps`
      already resolves — but an empty result proves nothing, so it returns False.
    * It does NOT prove DXR-inline availability, which the addon never learns
      (the capabilities handshake in runtime.py reads only
      `indexed_geometry_shm_v1`, and no bake result reports the raytracing tier).
      The backend's `enforce_material_ir_ray_op_route()` covers that half: a
      DXR-less bake fails loudly with GPU_FAILED_USE_CYCLES and the addon
      re-bakes through Cycles, rather than baking a wrong image.
    """
    saw_material = False
    try:
        for item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
            if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
                # A Normal row routed through the Material IR becomes a
                # MaterialFastPath map too (normal_material_route).
                if properties.ensure_map_setting_uuid(item) not in native_normal_uuids:
                    return False
            saw_material = True
    except Exception:
        return False
    return saw_material


def _material_ir_source_requires_high_uvs(source) -> bool:
    """Return whether a compiled native material actually reads source UVs.

    Object/Generated/constant programs still carry a native material source record,
    but they do not need the heavyweight FYMESH triangle-soup transport. Be
    conservative for malformed/unknown records so a future IR shape cannot silently
    lose required attributes.
    """
    if not source:
        return False
    try:
        program = source.get("program")
        ops = getattr(program, "ops", None)
        if ops is None and isinstance(program, dict):
            ops = program.get("ops")
        if ops is None:
            return True
        # ATTR_CORNER_FLOAT sidecars are indexed in loop_triangles order, which only
        # the FYMESH transport preserves -- the FYRGEOM1 indexed path reorders
        # triangles, and a triangle-ID diagnostic bake measured only 1.9% of texels
        # reading their own slot through it.
        return any(
            str(op.get("op", "") or "").strip().upper()
            in {"ATTR_UV", "ATTR_CORNER_FLOAT", "ATTR_TRIANGLE_SLOT", "SAMPLE_IMAGE"}
            for op in ops
            if isinstance(op, dict)
        )
    except Exception:
        return True


def _material_normal_flip_green(mat_item) -> bool:
    """Whether a MAP_MATERIAL row on the NORMAL channel wants the DirectX convention.

    Mirrors the geometry Normal map's resolution order: an explicit Normal Format on
    the row wins, and only an unset/legacy value falls back to the row's own
    `flip_green` checkbox.
    """
    try:
        normal_format = properties.effective_normal_format(mat_item)
    except Exception:
        normal_format = getattr(mat_item, "normal_format", "")
    normalized = str(normal_format or "").strip().upper()
    if normalized == constants.NORMAL_FORMAT_DIRECTX:
        return True
    if normalized == constants.NORMAL_FORMAT_OPENGL:
        return False
    return bool(getattr(mat_item, "flip_green", False))


def _job_aa_samples(project, map_configs) -> int:
    """Sample count for one backend job.

    With AA off, Curvature is computed on the CPU from raw hit normals and never sees the
    Normal map's retained bevel, so the bands of a Bevel-shader high vanish. Only the AA
    route folds the retained normals into Curvature, so such a job takes two samples.
    """
    samples = properties.resolve_aa_samples(project)
    if samples > constants.AA_SAMPLES_OFF_PASSES:
        return samples
    for config in map_configs:
        if (
            str(getattr(config, "material_normal_source_uuid", "") or "")
            and str(getattr(config, "map_type", "") or "").strip().upper()
            in (constants.MAP_CURVATURE, constants.MAP_CONCAVE, constants.MAP_CONVEX)
            and str(getattr(config, "curvature_method", "") or "") == "NORMAL_DERIVATIVE"
        ):
            return 2
    return samples


def _merge_material_specs_by_output(specs: list[MaterialBakeSpec]) -> list[MaterialBakeSpec]:
    """Fold specs that write the SAME file into one bake over all their targets.

    A combined texture set gives every member group the same `output_path`. Each spec
    used to be baked independently: a fresh image, `use_clear` on its own first
    target, its own islands, then `image.save()` over the file the previous group had
    just written. Last group wins and the rest come out as background -- black for
    roughness, which is exactly what an artist sees on a two-object atlas.

    Merging keeps each low paired with its OWN group's highs through `source_groups`.
    Unioning the sources instead would be a different bug: where two objects touch in
    3D (a strip lying on a base), a neighbouring group's high is the nearest surface
    along the cage ray and would win the projection.

    Specs are only merged when everything that defines the IMAGE matches. A
    difference in size, margin or UDIM tile means they were never really the same
    output, and merging those would paper over a genuine collision that
    `find_duplicate_output_map_settings` is supposed to report.
    """
    merged: dict[tuple, MaterialBakeSpec] = {}
    order: list[tuple] = []
    for spec in specs:
        path = str(spec.output_path or "")
        # A spec with no path, or a hidden detail layer that composites later, is not
        # part of a shared artist-facing file and must not be folded into one.
        if not path or spec.post_action:
            key = ("unmergeable", id(spec))
            merged[key] = spec
            order.append(key)
            continue
        key = (
            path, spec.channel, int(spec.width), int(spec.height), int(spec.margin),
            int(spec.udim_tile), spec.custom_output_name, spec.source_image_name,
            bool(spec.flip_green),
            # Cages stay out of the key: each low keeps its own group's cage or distance, and
            # splitting here let the later group's bake replace the earlier group's file.
            round(float(spec.uv_offset_u), 7), round(float(spec.uv_offset_v), 7),
            str(spec.uv_layer_name or ""),
            str(spec.only_material or ""),
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = replace(
                spec,
                source_groups=tuple(spec.high_obj_names for _ in spec.low_obj_names),
                cage_extrusions=tuple((name, float(spec.cage_extrusion)) for name in spec.low_obj_names),
            )
            order.append(key)
            continue
        merged[key] = replace(
            existing,
            low_obj_names=tuple(existing.low_obj_names) + tuple(spec.low_obj_names),
            # Keep the union for callers that only look at high_obj_names (the job's
            # own bookkeeping); source_groups is what the bake actually reads.
            high_obj_names=tuple(dict.fromkeys(
                tuple(existing.high_obj_names) + tuple(spec.high_obj_names)
            )),
            source_groups=tuple(existing.source_groups)
            + tuple(spec.high_obj_names for _ in spec.low_obj_names),
            cage_extrusion=max(float(existing.cage_extrusion), float(spec.cage_extrusion)),
            fitted_cages=tuple(existing.fitted_cages) + tuple(spec.fitted_cages),
            cage_extrusions=tuple(existing.cage_extrusions)
            + tuple((name, float(spec.cage_extrusion)) for name in spec.low_obj_names),
        )
    return [merged[key] for key in order]


def _collect_material_ir_source(
    mat_item,
    project,
    workspace_path,
    selected_group_names,
    *,
    allow_ray_ops: bool = False,
    diagnostics: list | None = None,
    compile_only: bool = False,
):
    """Compile Material IR for a MAP_MATERIAL item and normalize texture resources.

    `compile_only` stops after the compile: the returned dict carries the program but no
    resource files, which is all a caller asking "would this group compile natively?" needs.

    `allow_ray_ops` vouches for the material-only DXR shading route; see
    `_job_is_material_only_backend_batch`. Leave it False unless that predicate
    holds — a ray opcode on any other route bakes as fully unoccluded.

    `diagnostics` collects artist-facing warnings (a UDIM tile the high poly reaches
    with no file on disk).

    Returns ``None`` when native IR is unavailable, otherwise::

        {
            "path": <representative PNG>,
            "tiles": [],  # legacy field; UDIM sources ride the program's tile tables
            "resource_paths": [png or "" per resource ("" for a table)],
            "program": MaterialIrProgram,
        }
    """
    from . import material_ir
    from . import project_structure

    channel = str(getattr(mat_item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or "").strip().upper()
    origin = str(getattr(mat_item, "material_origin", "") or constants.MATERIAL_ORIGIN_MANUAL)
    # The row's Normal Format reached the backend but nothing consumed it for this
    # channel, so DirectX baked as OpenGL. The flip belongs between the IR's
    # world->tangent conversion and its 0-1 encode, so it is resolved here and
    # compiled in; see material_ir._encode_world_normal_as_tangent.
    normal_flip_green = _material_normal_flip_green(mat_item)         if channel == constants.MATERIAL_CHANNEL_NORMAL else False
    custom_name = str(getattr(mat_item, "material_custom_name", "") or "").strip()
    custom_data_type = str(getattr(mat_item, "material_data_type", "") or "")
    materials = []
    shading_objects = []
    group_bake_uv_names = []
    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        high_targets = list(properties.effective_high_mesh_objects(group) or [])
        source_objs = high_targets
        if not source_objs:
            source_objs = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or [])
        if not source_objs:
            return None
        group_uv = str(getattr(_group_projection_settings_state(group), "uv_layer_name", "") or "").strip()
        group_bake_uv_names.append(group_uv)
        for obj in source_objs:
            if obj not in shading_objects:
                shading_objects.append(obj)
            for slot in getattr(obj, "material_slots", []) or []:
                mat = getattr(slot, "material", None)
                if mat is not None and mat not in materials:
                    materials.append(mat)
            # Objects with no slots cannot contribute a shared program.
            if not getattr(obj, "material_slots", None):
                return None

    if not materials:
        return None

    # A material program may be shared across all selected groups. ATTR_UV is only
    # interchangeable with an explicitly named material UV when every such group
    # projects to that same, known UV set. Blank or differing group overrides must
    # retain the named per-corner sidecar.
    bake_uv_layer_name = _common_explicit_bake_uv_layer_name(group_bake_uv_names)

    # Object Info bakes as per-object constants, so the compiler needs to know which
    # objects this program will shade. Fields the objects disagree on come back None
    # and send that output to Cycles rather than baking one object's value onto all.
    object_info = material_ir.resolve_object_info(shading_objects)
    # Bump differentiates against the texture coordinate, so its slopes are per UV
    # unit and need the world size of a UV unit to meet the tangent frame.
    uv_to_world_scale = material_ir.resolve_uv_to_world_scales(shading_objects)

    # A compiler bug must cost this channel its native route, never the whole bake.
    # compile_*_program is expected to REFUSE by returning a Cycles program; anything
    # that escapes as an exception (a RecursionError on a nested node group did exactly
    # this) used to abort the run before a single map was written.
    try:
        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            if not custom_name:
                return None
            program = material_ir.compile_group_custom_output_program(
                materials,
                custom_name,
                workspace_path=workspace_path,
                data_type=custom_data_type,
                object_info=object_info,
                uv_to_world_scale=uv_to_world_scale,
                attribute_objects=shading_objects,
                allow_ray_ops=allow_ray_ops,
                bake_uv_layer_name=bake_uv_layer_name,
            )
            ir_identity = f"custom:{custom_name}"
        else:
            program = material_ir.compile_group_channel_program(
                materials,
                channel,
                workspace_path=workspace_path,
                object_info=object_info,
                uv_to_world_scale=uv_to_world_scale,
                attribute_objects=shading_objects,
                allow_ray_ops=allow_ray_ops,
                flip_green=normal_flip_green,
                # A Normal row baked through this channel is a normal MAP: it encodes
                # around the low's interpolated normal (normal_material_route).
                normal_low_frame=bool(getattr(mat_item, "normal_encode_low_frame", False)),
                bake_uv_layer_name=bake_uv_layer_name,
            )
            ir_identity = channel
    except RecursionError:
        return {
            "path": "",
            "tiles": [],
            "resource_paths": [],
            "program": material_ir.cycles_fallback_program(
                channel,
                "Material graph is too deeply nested for the native compiler. Needs Cycles",
            ),
        }
    except Exception as exc:  # pragma: no cover - defensive, exercised by the unit test
        return {
            "path": "",
            "tiles": [],
            "resource_paths": [],
            "program": material_ir.cycles_fallback_program(
                channel,
                f"Native material compile failed ({type(exc).__name__}). Needs Cycles",
            ),
        }
    if not program.native:
        # Carry the refused program back so the caller keeps the real reason. Returning
        # a bare None used to send the caller into a "recover a reason" loop that
        # recompiled the FIRST material on its own -- and a single material usually
        # compiles natively, so the loop handed back a native program and the exporter
        # sent a backend map config built from material #1's graph for the whole
        # object, on top of the Cycles spec that was already queued for the same file.
        # No paths: a non-native program has no resources to ship.
        refused: dict[str, object] = {"path": "", "tiles": [], "resource_paths": [], "program": program}
        # The union can refuse where every group alone compiles (more materials than
        # one program can select between). Marked like the sidecar refusal below, so
        # the row bakes as per-group native passes instead of on Cycles.
        if _every_selected_group_compiles_native(
            mat_item, project, workspace_path, selected_group_names, allow_ray_ops=allow_ray_ops
        ):
            refused["multi_group_refusal"] = True
        return refused
    if compile_only:
        return {"path": "", "tiles": [], "resource_paths": [], "program": program}

    # IMAGE_SAMPLE with a single file-backed, untiled image. A UDIM image never reaches
    # this kind (the compiler keeps table programs EXPRESSION_UV), so tiles only ride
    # the resource loop below.
    if (
        program.kind == material_ir.MATERIAL_IR_KIND_IMAGE_SAMPLE
        and len(program.resources) == 1
        and not program.resources[0].get("tiled")
    ):
        # Every image the backend reads goes through _normalize_material_image_to_png,
        # on this route as much as on the EXPRESSION_UV one below. It used to hand the
        # source file straight to the backend via _normalize_material_source_to_png,
        # which returns an existing .png verbatim -- no sRGB decode and no alpha_mode
        # association. That made the SAME material bake two different images depending
        # on whether an unrelated node (a Mapping node, say) kept the program off this
        # single-sample path: an sRGB texture into Roughness baked 109 where Cycles
        # bakes 46, and a straight-alpha cut-out baked its holes lit instead of black.
        # See docs/MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G3.
        image = program.resources[0].get("image")
        if image is None:
            return None
        png = _normalize_material_image_to_png(
            image,
            workspace_path,
            identity=f"material_ir:{ir_identity}:{getattr(image, 'name', 'img')}",
        )
        if not png:
            return None
        program.image_path = png
        return {
            "path": png,
            "tiles": [],
            "resource_paths": [png],
            "program": program,
        }

    # UDIM occupancy is only knowable when a tap samples the plain hit UV; any other
    # coordinate (Mapping, Object, a box plane...) can reach any tile, so those ship
    # every tile the image has. Computed lazily and at most once per collection.
    occupancy_cache: dict[str, object] = {}

    def _occupancy_for(resource_index: int, materials_filter):
        if not _sampler_taps_read_hit_uv(program, resource_index):
            return None
        if "by_material" not in occupancy_cache:
            occupancy_cache["by_material"] = _high_uv_sampler_tiles_by_material(shading_objects)
        by_material = occupancy_cache["by_material"]
        if by_material is None:
            return None
        if materials_filter is None:
            names = list(by_material)
        else:
            names = [str(name) for name in materials_filter]
        occupied: set[int] = set()
        for name in names:
            occupied.update(by_material.get(name, ()))
        return occupied

    def _tile_table(image, identity: str, occupied, resource):
        normalized = _normalize_tiled_image_to_pngs(
            image, workspace_path, identity, occupied_tiles=occupied
        )
        if normalized is None:
            return None
        tiles, missing = normalized
        if missing and diagnostics is not None:
            label = str(getattr(image, "name", "") or "image")
            colour = (
                "the Image Texture's Missing colour"
                if resource.get("missing") is not None
                else "magenta"
            )
            plural = "s" if len(missing) > 1 else ""
            warning = (
                f"UDIM image '{label}' has no file for tile{plural} "
                f"{', '.join(str(tile) for tile in missing)}, which the high poly's UVs "
                f"reach. Those areas bake {colour}, as they do in Cycles."
            )
            if warning not in diagnostics:
                diagnostics.append(warning)
        return tiles

    slot_materials = tuple(getattr(program, "slot_materials", ()) or ())
    indexed_sidecar_groups = [
        group for group in project.groups
        if selected_group_names is None
        or str(getattr(group, "name", "") or "") in selected_group_names
    ]

    # EXPRESSION_UV: normalize every resource image; UDIM images and per-material
    # slot tables become tile / slot tables.
    resource_paths: list[str] = []
    for index, resource in enumerate(program.resources):
        channel_tag = str(resource.get("channel") or "")
        is_triangle_attr = channel_tag.startswith(material_ir.TRIANGLE_ATTR_CHANNEL_PREFIX)
        if is_triangle_attr or channel_tag.startswith(material_ir.CORNER_ATTR_CHANNEL_PREFIX):
            if len(indexed_sidecar_groups) > 1:
                # One 0-based sidecar per group. The backend concatenates them in
                # pack order when the groups share a pass, and reads each group's
                # own file when a pass stays separate. Either way the index matches
                # the scene, so the row stays on the GPU instead of one Blender
                # re-entry per group.
                png = _write_per_group_indexed_sidecars(
                    channel_tag,
                    project,
                    workspace_path,
                    indexed_sidecar_groups,
                    triangle=is_triangle_attr,
                    ir_identity=ir_identity,
                    slot_materials=slot_materials,
                )
            elif is_triangle_attr:
                png = _write_triangle_attribute_sidecar(
                    channel_tag,
                    project,
                    workspace_path,
                    selected_group_names,
                    slot_materials=slot_materials,
                )
            else:
                png = _write_corner_attribute_sidecar(
                    channel_tag,
                    project,
                    workspace_path,
                    selected_group_names,
                    ir_identity,
                    slot_materials=slot_materials,
                )
            if not png:
                # Multi-group selections or a failed compute: no honest sidecar
                # exists, so the whole program routes to Cycles. Distinguish the two,
                # because a bare None makes the caller fabricate "No native Material IR
                # program for this channel" -- untrue for a multi-group refusal, where
                # the program compiled natively and only the sidecar cannot be shared.
                selected_groups = [
                    group for group in project.groups
                    if selected_group_names is None
                    or str(getattr(group, "name", "") or "") in selected_group_names
                ]
                if len(selected_groups) != 1:
                    # The marker lets prepare_bake_job route this row to per-group
                    # native sub-bakes instead of Cycles: each group compiled alone
                    # needs no cross-group sidecar. The Cycles program stays as the
                    # honest fallback for routes that cannot split (forced Blender,
                    # Cycles-primary).
                    return {
                        "path": "",
                        "tiles": [],
                        "resource_paths": [],
                        "multi_group_refusal": True,
                        "program": material_ir.cycles_fallback_program(
                            channel,
                            "Combined texture set spans multiple bake groups; per-texel "
                            "material selection works within one group, so this channel "
                            "bakes via Cycles",
                        ),
                    }
                return None
            resource_paths.append(png)
            resource["path"] = png
            continue
        if "slots" in resource:
            # One image per material, in slot_materials order. Colour space and
            # alpha mode are baked into each PNG by the normaliser, per image.
            slots = list(resource.get("slots") or ())
            for slot_index, slot in enumerate(slots):
                image = slot.get("image")
                if image is None:
                    slot.pop("path", None)
                    slot.pop("tiles", None)
                    continue
                image_label = str(
                    getattr(image, "name_full", "") or getattr(image, "name", "") or "img"
                )
                identity = f"material_ir:{ir_identity}:slot:{image_label}"
                if slot.get("tiled"):
                    material_name = (
                        slot_materials[slot_index] if slot_index < len(slot_materials) else None
                    )
                    tiles = _tile_table(
                        image,
                        identity,
                        _occupancy_for(index, [material_name] if material_name else None),
                        resource,
                    )
                    if tiles is None:
                        return None
                    slot["tiles"] = tiles
                else:
                    png = _normalize_material_image_to_png(image, workspace_path, identity=identity)
                    if not png:
                        return None
                    slot["path"] = png
            resource_paths.append("")
            resource["path"] = ""
            continue
        image = resource.get("image")
        if image is None:
            return None
        if resource.get("tiled"):
            owner = resource.get("material")
            tiles = _tile_table(
                image,
                f"material_ir:{ir_identity}:r{index}:{getattr(image, 'name', 'img')}",
                _occupancy_for(index, [owner] if owner else None),
                resource,
            )
            if tiles is None:
                return None
            resource["tiles"] = tiles
            resource_paths.append("")
            resource["path"] = ""
            continue
        png = _normalize_material_image_to_png(
            image,
            workspace_path,
            identity=f"material_ir:{ir_identity}:r{index}:{getattr(image, 'name', 'img')}",
        )
        if not png:
            return None
        resource_paths.append(png)
        resource["path"] = png

    # Constants-only programs still need a native path marker for requires_high_uvs /
    # routing. A table has no single path, so the marker is the first real file.
    representative = next((path for path in resource_paths if path), "")
    program.image_path = representative
    return {
        "path": representative,
        "tiles": [],
        "resource_paths": resource_paths,
        "program": program,
    }


#: Row width of the per-triangle sidecar image. Purely a packing choice -- the
#: sidecar is a byte container indexed linearly by triangle, not a picture.
_DETAIL_SIDECAR_ROW_WIDTH = 1024
#: Highest binding index the one-byte encoding can carry (0 means "no detail").
_DETAIL_SIDECAR_MAX_BINDING = 253


def _single_group_source_objects(project, selected_group_names):
    """The one selected group's projection sources (highs, else lows), or None.

    Per-triangle and per-corner sidecars are indexed by the triangle's export-order
    index, which restarts per group -- the unit the backend concatenates into one
    scene -- so a multi-group selection has no single honest sidecar.
    """
    from . import project_structure

    groups = [
        group for group in project.groups
        if selected_group_names is None
        or str(getattr(group, "name", "") or "") in selected_group_names
    ]
    if len(groups) != 1:
        return None
    high_targets = list(
        project_structure.group_role_targets(groups[0], constants.OBJECT_ROLE_HIGH) or []
    )
    source_objs = high_targets or list(
        project_structure.group_role_targets(groups[0], constants.OBJECT_ROLE_LOW) or []
    )
    return source_objs or None


def _per_triangle_material_lookup(source_objs, index_by_material, depsgraph, *,
                                  max_index: int, require_known: bool = False):
    """Per-triangle ``index_by_material[material]`` in EXPORT order, -1 when unknown.

    Concatenates `source_objs` in order, each object's evaluated `loop_triangles`, the
    same contract every per-triangle and per-corner sidecar relies on. Returns an int64
    array, or None when an object cannot be evaluated, an index exceeds `max_index`,
    or (with `require_known`) an object carries no material the caller knows -- one
    sidecar serves the whole group, so guessing would shade that object with another
    material's program.
    """
    import numpy as np

    chunks = []
    for obj in source_objs:
        slot_to_index = []
        for slot in getattr(obj, "material_slots", []) or []:
            material = getattr(slot, "material", None)
            name = str(getattr(material, "name", "") or "") if material else ""
            slot_to_index.append(index_by_material.get(name, -1))
        if require_known and (not slot_to_index or all(i < 0 for i in slot_to_index)):
            return None
        if not slot_to_index:
            slot_to_index = [-1]
        lookup = np.asarray(slot_to_index, dtype=np.int64)
        if lookup.size and int(lookup.max()) > int(max_index):
            return None

        # Same export-order slot mapping the ID map's Material Color sidecar uses.
        slots_per_tri = _object_triangle_material_slots(obj, depsgraph, len(lookup))
        if slots_per_tri is None:
            return None
        if slots_per_tri.size == 0:
            continue
        chunks.append(lookup[slots_per_tri])
    if not chunks:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(chunks) if len(chunks) > 1 else chunks[0]


def _per_triangle_byte_sidecar_rgba(per_triangle, *, grey: bool):
    """Pack one byte per triangle into a fixed-width RGBA8 container, linear order.

    `grey` writes R=G=B=value (the backend auto-packs r==g==b with a==255 to one
    byte per triangle); otherwise only R carries it. A is always 255.
    """
    import numpy as np

    width = _DETAIL_SIDECAR_ROW_WIDTH
    height = max(1, (int(per_triangle.size) + width - 1) // width)
    padded = np.zeros((height * width, 4), dtype=np.uint8)
    if grey:
        padded[: per_triangle.size, :3] = per_triangle[:, None]
    else:
        padded[: per_triangle.size, 0] = per_triangle
    padded[:, 3] = 255
    return width, height, padded


def _write_material_slot_sidecar(
    project, workspace_path, selected_group_names, ir_identity, binding_index_by_material
):
    """Per-TRIANGLE detail-binding index in EXPORT order: one byte per triangle,
    ``binding_index + 1``, 0 meaning "this triangle's material carries no detail".

    RayHit's material name is per exported mesh range -- one per OBJECT -- so a high
    carrying two materials cannot be told apart by name at hit time.

    This used to rasterize the indices into HIGH-UV space instead, because keying by
    triangle index did not survive `optimize_mesh`'s spatial sort. That is no longer
    true: every packed triangle now carries `source_triangle_index`, its ORIGINAL
    export-order index, added so Material IR's corner-attribute sidecars could be
    indexed through exactly that sort. Reusing it here removes the three limits the
    UV mask imposed:

      * the 400k-triangle cap (a Python rasterizer bounded per object), which refused
        detail outright on any real sculpt -- a 10M-triangle high got NO material
        detail at all;
      * the per-triangle rasterization itself, which ran on the main thread and froze
        Blender for seconds (see the speculative-PREPARE note in prepare_bake_job);
      * the one-texel error wherever two materials met in UV space. A per-triangle
        index is exact, which is the same argument
        `material_geometry_attributes.material_index_per_corner` already makes for
        preferring a corner attribute over this mask.

    Triangle order must match the exporter's, which concatenates `source_objs` in this
    order and takes each mesh's `loop_triangles` -- the same contract the Material IR
    corner sidecars rely on.

    Multi-group selections still refuse: a group is the unit the backend concatenates
    into one scene, so indices are only meaningful within one.
    """
    import bpy

    import numpy as np

    source_objs = _single_group_source_objects(project, selected_group_names)
    if not source_objs:
        return None

    depsgraph = bpy.context.evaluated_depsgraph_get()
    try:
        binding_per_tri = _per_triangle_material_lookup(
            source_objs,
            binding_index_by_material,
            depsgraph,
            max_index=_DETAIL_SIDECAR_MAX_BINDING,
        )
    except Exception:
        return None
    if binding_per_tri is None or binding_per_tri.size == 0:
        return None
    # 0 = no detail for this triangle's material; otherwise index + 1.
    per_triangle = np.where(binding_per_tri < 0, 0, binding_per_tri + 1).astype(np.uint8)
    if not per_triangle.any():
        return None

    # Byte container, one triangle per pixel in the R channel, indexed linearly by
    # the triangle's export-order index. Not a picture: never sampled by UV.
    width, height, padded = _per_triangle_byte_sidecar_rgba(per_triangle, grey=False)

    directory = Path(workspace_path) / "material_ir"
    directory.mkdir(parents=True, exist_ok=True)
    safe_identity = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in str(ir_identity)
    )
    path = directory / f"detail_tris_{safe_identity}.png"
    if not _write_rgba_png_bytes_file(path, width, height, padded):
        return None
    return str(path)


_GROUP_SIDECAR_MANIFESTS: set[str] = set()


def _reset_group_triangle_sidecars(workspace_path) -> None:
    """Drop a previous prepare's per-group sidecar list in this workspace."""
    path = Path(workspace_path) / "material_ir" / "group_triangle_sidecars.tsv"
    _GROUP_SIDECAR_MANIFESTS.discard(str(path))
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _note_group_triangle_sidecar(workspace_path, group_name, channel, png_path) -> None:
    """Record one group's 0-based sidecar so the backend can bind or concatenate it."""
    directory = Path(workspace_path) / "material_ir"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "group_triangle_sidecars.tsv"
    key = str(path)
    mode = "a" if key in _GROUP_SIDECAR_MANIFESTS else "w"
    _GROUP_SIDECAR_MANIFESTS.add(key)
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(f"{group_name}\n{channel}\n{png_path}\n")


def _sidecar_path_token(group_name) -> str:
    token = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in str(group_name or "")
    )
    return token or "group"


def _write_per_group_indexed_sidecars(
    channel_tag, project, workspace_path, groups, *, triangle, ir_identity, slot_materials
):
    """Write each group's sidecar on its own, then point the manifest at them.

    Returns the first group's path (the resource still needs one file) or None
    when any group cannot be written, which keeps the existing per-group fallback.
    """
    written = []
    for group in groups:
        name = str(getattr(group, "name", "") or "")
        if not name or "\n" in name or "\n" in channel_tag:
            return None
        token = _sidecar_path_token(name)
        if triangle:
            png = _write_triangle_attribute_sidecar(
                channel_tag,
                project,
                workspace_path,
                {name},
                slot_materials=slot_materials,
                path_token=token,
            )
        else:
            png = _write_corner_attribute_sidecar(
                channel_tag,
                project,
                workspace_path,
                {name},
                ir_identity,
                slot_materials=slot_materials,
                path_token=token,
            )
        if not png:
            return None
        written.append((name, png))
    for name, png in written:
        _note_group_triangle_sidecar(workspace_path, name, channel_tag, png)
    return written[0][1] if written else None


def _write_triangle_attribute_sidecar(
    channel_tag, project, workspace_path, selected_group_names, *, slot_materials=(),
    path_token: str = "",
):
    """Per-TRIANGLE byte sidecar for a Material IR TRIANGLE_ATTR:* resource.

    Only TRIANGLE_ATTR:MATSLOT exists: the material's position in the program's
    `slot_materials`, one texel per triangle at its export-order index, R=G=B=slot and
    A=255 so the backend packs it at one byte per triangle. A slot whose material the
    program does not know (an empty slot, say) reads 0 -- the same answer the
    CORNER_ATTR:MATSLOT select staircase gives its -1 -- and an object carrying none of
    the program's materials refuses, exactly as that corner sidecar does.

    Returns None for multi-group selections (see `_single_group_source_objects`).
    """
    import bpy

    import numpy as np

    from . import material_ir

    if channel_tag != material_ir.TRIANGLE_ATTR_MATERIAL_SLOT:
        return None
    slot_materials = tuple(str(name) for name in (slot_materials or ()))
    if not slot_materials or len(slot_materials) > material_ir.MAX_SLOT_TABLE_MATERIALS:
        return None
    source_objs = _single_group_source_objects(project, selected_group_names)
    if not source_objs:
        return None

    directory = Path(workspace_path) / "material_ir"
    directory.mkdir(parents=True, exist_ok=True)
    # Two channels can index DIFFERENT material sets, so the order is the identity.
    order = hashlib.sha1(repr(slot_materials).encode("utf-8", "replace")).hexdigest()[:12]
    token = f"_{path_token}" if path_token else ""
    path = directory / f"triangle_matslot_{order}{token}.png"
    if path.is_file():
        return str(path)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    try:
        slot_per_tri = _per_triangle_material_lookup(
            source_objs,
            {name: index for index, name in enumerate(slot_materials)},
            depsgraph,
            max_index=material_ir.MAX_SLOT_TABLE_MATERIALS - 1,
            require_known=True,
        )
    except Exception:
        return None
    if slot_per_tri is None or slot_per_tri.size == 0:
        return None
    per_triangle = np.where(slot_per_tri < 0, 0, slot_per_tri).astype(np.uint8)

    # Content-addressed reuse across bakes, like the corner sidecars: the key is the
    # bytes themselves, so it cannot go stale when a face changes material.
    name = "triangle_matslot"
    payload = per_triangle.tobytes()
    cached = _cached_corner_sidecar(name, payload)
    if cached is not None:
        try:
            shutil.copyfile(cached, path)
            return str(path)
        except OSError:
            pass
    width, height, padded = _per_triangle_byte_sidecar_rgba(per_triangle, grey=True)
    if not _write_rgba_png_bytes_file(path, width, height, padded):
        return None
    _store_cached_corner_sidecar(name, payload, path)
    return str(path)


def _sampler_taps_read_hit_uv(program, resource_index: int) -> bool:
    """Whether every sampler tap of a resource reads the plain interpolated hit UV.

    True for a coordinate of -1 (the backend's "hit UV" default) or one written by
    ATTR_UV. Anything else -- a Mapping, a box plane, a sphere remap -- can land in
    any tile, so the caller cannot restrict which tiles to ship.
    """
    last_writer: dict[int, str] = {}
    for op in getattr(program, "ops", None) or ():
        opcode = str(op.get("op") or "")
        if opcode == "SAMPLE_IMAGE" and int(op.get("resource", -1)) == int(resource_index):
            coord = op.get("coord", -1)
            if type(coord) is int and coord >= 0 and last_writer.get(coord) != "ATTR_UV":
                return False
        for field in ("dst", "dst2"):
            value = op.get(field)
            if type(value) is int and value >= 0:
                last_writer[value] = opcode
    return True


def _render_uv_layer(mesh):
    layers = getattr(mesh, "uv_layers", None)
    if not layers:
        return None
    for layer in layers:
        if bool(getattr(layer, "active_render", False)):
            return layer
    return getattr(layers, "active", None)


#: Triangles per chunk when gathering hit-UV triangles for tile occupancy. Bounds the
#: transient (N, 3, 2) float64 array at ~48 MB on a 15M-triangle high.
_SAMPLER_OCCUPANCY_CHUNK = 1 << 20


def _high_uv_sampler_tiles_by_material(objects):
    """``{material name: tiles}`` the high poly's hit UVs make a UDIM sampler read.

    Walks each object's evaluated mesh in export order over the render UV layer (the
    layer ATTR_UV interpolates), keyed the way the sampler keys tiles (see
    `udim.sampler_tiles_by_group`). A triangle whose slot has no material counts under
    "". Returns None when any object cannot be read, which means "ship every tile".
    """
    import bpy

    import numpy as np

    from . import udim as _udim

    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        return None
    result: dict[str, set[int]] = {}
    for obj in objects or ():
        if obj is None:
            continue
        try:
            evaluated = obj.evaluated_get(depsgraph)
        except Exception:
            return None
        mesh = getattr(evaluated, "data", None) if getattr(evaluated, "type", "") == "MESH" else None
        temporary = False
        try:
            if mesh is None:
                mesh = evaluated.to_mesh()
                temporary = True
            if mesh is None:
                return None
            calc = getattr(mesh, "calc_loop_triangles", None)
            if callable(calc):
                calc()
            tris = mesh.loop_triangles
            count = len(tris)
            if count == 0:
                continue
            layer = _render_uv_layer(mesh)
            if layer is None:
                return None
            # foreach_get needs exactly typed buffers: int32 indices, float32 UVs.
            loops = rna_buffers.empty_u32_for_rna(count * 3)
            tris.foreach_get("loops", loops)
            loops = rna_buffers.as_i32(loops)
            uv = np.empty(len(layer.data) * 2, dtype=np.float32)
            layer.data.foreach_get("uv", uv)
            uv = uv.reshape(-1, 2)
            polygon_count = len(mesh.polygons)
            poly_material = rna_buffers.zeros_u32_for_rna(max(1, polygon_count))
            if polygon_count:
                mesh.polygons.foreach_get("material_index", poly_material)
            poly_material = rna_buffers.as_i32(poly_material)
            poly_index = rna_buffers.empty_u32_for_rna(count)
            tris.foreach_get("polygon_index", poly_index)
            poly_index = rna_buffers.as_i32(poly_index)
            slot_names = [
                str(getattr(getattr(slot, "material", None), "name", "") or "")
                for slot in (getattr(obj, "material_slots", []) or [])
            ] or [""]
            slot_per_tri = np.clip(poly_material[poly_index], 0, len(slot_names) - 1)
            del poly_material, poly_index
            for start in range(0, count, _SAMPLER_OCCUPANCY_CHUNK):
                stop = min(count, start + _SAMPLER_OCCUPANCY_CHUNK)
                tri_uv = uv[loops[start * 3: stop * 3]].reshape(-1, 3, 2)
                by_slot = _udim.sampler_tiles_by_group(tri_uv, slot_per_tri[start:stop])
                for slot_index, tiles in by_slot.items():
                    result.setdefault(slot_names[int(slot_index)], set()).update(tiles)
        except Exception:
            return None
        finally:
            if temporary:
                try:
                    evaluated.to_mesh_clear()
                except Exception:
                    pass
    return result


def _common_explicit_bake_uv_layer_name(group_uv_names) -> str | None:
    """Return a UV name only when all material-sharing groups target the same set."""
    names = [str(name or "").strip() for name in (group_uv_names or ())]
    if not names or not names[0] or any(name != names[0] for name in names[1:]):
        return None
    return names[0]


def _object_triangle_material_slots(obj, depsgraph, slot_count: int):
    """Material SLOT index of every evaluated triangle of ``obj``, in EXPORT order.

    Export order is ``mesh.loop_triangles`` of the evaluated mesh -- the order every
    high-mesh writer (FYRGEOM1, FYMESH, OBJ) emits triangles in, and the order the
    backend's per-triangle sidecars are indexed by (``source_triangle_index`` undoes
    optimize_mesh's spatial sort). Indices are clamped to ``[0, slot_count - 1]`` the way
    Blender itself resolves an out-of-range face material index. The dtype is the
    narrowest that holds ``slot_count`` (uint8 up to 256 slots, else uint16), so the
    result for a 62M-triangle high is 62 MB, not 248.

    Returns None when the object cannot be evaluated. Reads the evaluated mesh in place
    (no ``to_mesh`` copy) whenever the object is a mesh.
    """
    import numpy as np

    slot_count = max(1, int(slot_count))
    index_dtype = np.uint8 if slot_count <= 256 else np.uint16
    evaluated = obj.evaluated_get(depsgraph)
    mesh = getattr(evaluated, "data", None) if getattr(evaluated, "type", "") == "MESH" else None
    temporary = False
    if mesh is None:
        mesh = evaluated.to_mesh()
        temporary = True
    if mesh is None:
        return None
    try:
        calc = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc):
            calc()
        tris = mesh.loop_triangles
        count = len(tris)
        if count == 0:
            return np.zeros(0, dtype=index_dtype)
        polygon_count = len(mesh.polygons)
        # foreach_get writes int32; a wider buffer receives interleaved garbage.
        poly_material = rna_buffers.zeros_u32_for_rna(max(1, polygon_count))
        if polygon_count:
            mesh.polygons.foreach_get("material_index", poly_material)
        poly_material = rna_buffers.as_i32(poly_material)
        # Narrow the per-POLYGON table first so the per-triangle gather below is
        # already in the compact dtype.
        poly_slot = np.clip(poly_material, 0, slot_count - 1).astype(index_dtype)
        del poly_material
        poly_index = rna_buffers.empty_u32_for_rna(count)
        tris.foreach_get("polygon_index", poly_index)
        poly_index = rna_buffers.as_i32(poly_index)
        slots = poly_slot[poly_index]
        if floater_faces.has_floater_faces(obj):
            # Export order of a high with floater faces: body triangles, then the piece's.
            slots = floater_faces.reorder_export_triangles(mesh, slots)
        return slots
    finally:
        if temporary:
            evaluated.to_mesh_clear()


#: FYRMSLT1: the ID map's per-triangle material-slot sidecar. Little-endian:
#:   "FYRMSLT1" | u32 triangle_count | u32 index_bytes (1|2) | u32 used_slot_count K |
#:   u32[K] used slot indices, ascending | u32 compressed_size | zlib(indices)
#: Read by load_id_material_slot_sidecar (backend_id_material.cpp). The used-slot list
#: lets a warm prepare decide "does this object really show 2+ materials?" without
#: re-evaluating the mesh.
_ID_SLOT_SIDECAR_MAGIC = b"FYRMSLT1"
_ID_SLOT_SIDECAR_FAMILY = "idslots"
#: In-process memo of objects whose faces use ONE slot only. No sidecar file is kept for
#: them (the job never references one), so without this every warm bake would
#: re-evaluate such a mesh just to learn that again.
_ID_SLOT_SINGLE_USE_MEMO: dict[str, tuple[int, tuple[int, ...]]] = {}


def _id_slot_sidecar_cache_path(revision_key: str, slot_count: int):
    try:
        from . import preferences

        root = Path(preferences.persistent_cache_root()) / "material_ir_sidecars"
    except Exception:
        return None
    digest = hashlib.blake2b(
        f"fyrmslt1|{revision_key}|{int(slot_count)}".encode("utf-8", "replace"),
        digest_size=16,
    ).hexdigest()
    return root / f"{_ID_SLOT_SIDECAR_FAMILY}_{digest}.fyslot"


def _read_id_slot_sidecar_header(path):
    """(triangle_count, used_slots) of an existing FYRMSLT1 file, or None."""
    import struct

    try:
        with open(path, "rb") as handle:
            head = handle.read(20)
            if len(head) < 20 or head[:8] != _ID_SLOT_SIDECAR_MAGIC:
                return None
            triangle_count, index_bytes, used_count = struct.unpack("<III", head[8:20])
            if index_bytes not in (1, 2) or used_count > 65536:
                return None
            used_raw = handle.read(4 * used_count)
            if len(used_raw) != 4 * used_count:
                return None
            used = struct.unpack(f"<{used_count}I", used_raw) if used_count else ()
    except OSError:
        return None
    return int(triangle_count), tuple(int(value) for value in used)


def _write_id_slot_sidecar_file(path: Path, slots, used_slots) -> bool:
    import struct
    import zlib

    import numpy as np

    index_bytes = int(np.dtype(slots.dtype).itemsize)
    raw = np.ascontiguousarray(slots.astype(f"<u{index_bytes}", copy=False)).tobytes()
    # Level 1: face material indices are long runs, so even the fastest level shrinks
    # them by one to two orders of magnitude; higher levels only cost encode time.
    compressed = zlib.compress(raw, 1)
    del raw
    header = bytearray(_ID_SLOT_SIDECAR_MAGIC)
    header += struct.pack("<III", int(slots.size), index_bytes, len(used_slots))
    if used_slots:
        header += struct.pack(f"<{len(used_slots)}I", *used_slots)
    header += struct.pack("<I", len(compressed))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # The cache hit test is "the file exists", so publish atomically: a torn write
        # would otherwise be served to every later bake.
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary, "wb") as handle:
                handle.write(bytes(header))
                handle.write(compressed)
            os.replace(temporary, path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    except OSError:
        return False
    return True


def _id_material_triangle_slots(obj, depsgraph, slot_count: int, *, speculative: bool = False):
    """(sidecar_path, triangle_count, used_slots) for ``obj``'s face material slots.

    ``sidecar_path`` is empty when the faces use a single slot (nothing to ship).
    Content-addressed in the persistent ``material_ir_sidecars`` cache family by the
    high-mesh cache's geometry revision, so a warm bake reads a 20-byte header instead
    of re-evaluating the mesh; the family's LRU/budget prune and Clear Cache already
    cover it. Returns None when it cannot be produced: the speculative PREPARE probe
    never evaluates a mesh on the main thread for it, and an evaluation failure falls
    back to today's single colour per object.
    """
    import numpy as np

    from . import high_mesh_cache

    try:
        revision_key = high_mesh_cache.geometry_revision_key(obj)
    except Exception:
        revision_key = ""
    memo_key = f"{revision_key}|{int(slot_count)}" if revision_key else ""
    cache_path = _id_slot_sidecar_cache_path(revision_key, slot_count) if revision_key else None
    if memo_key and memo_key in _ID_SLOT_SINGLE_USE_MEMO:
        triangle_count, used = _ID_SLOT_SINGLE_USE_MEMO[memo_key]
        return "", triangle_count, used
    if cache_path is not None and cache_path.is_file():
        header = _read_id_slot_sidecar_header(cache_path)
        if header is not None:
            try:
                # LRU touch: the family prune keeps the most recently used entries.
                os.utime(cache_path, None)
            except OSError:
                pass
            return str(cache_path), header[0], header[1]
    if speculative:
        return None
    try:
        slots = _object_triangle_material_slots(obj, depsgraph, slot_count)
    except Exception:
        slots = None
    if slots is None:
        return None
    counts = np.bincount(slots, minlength=max(1, int(slot_count)))
    used = tuple(int(index) for index in np.flatnonzero(counts))
    triangle_count = int(slots.size)
    if len(used) <= 1:
        if memo_key:
            _ID_SLOT_SINGLE_USE_MEMO[memo_key] = (triangle_count, used)
        return "", triangle_count, used
    if cache_path is None or not _write_id_slot_sidecar_file(cache_path, slots, used):
        return None
    return str(cache_path), triangle_count, used


def _id_material_mesh_for_object(obj, depsgraph, *, speculative: bool = False):
    """The MBBJOB35 ID "Material Color" record for one high object, or None.

    None keeps today's behaviour for that object: one colour for the whole mesh from
    ``ExportedMeshRef.material_color``. That is exactly right for an object with no
    material at all (it bakes ``obj.color``), and it is the degraded answer when the
    per-triangle slots cannot be produced.
    """
    from . import id_material_color

    materials = [
        getattr(slot, "material", None)
        for slot in (getattr(obj, "material_slots", None) or [])
    ]
    if not materials or all(material is None for material in materials):
        return None
    # An empty slot's faces take the object-level fallback a material-less object bakes.
    object_fallback = _resolve_rgb_triplet(getattr(obj, "color", None))
    palette = [
        list(id_material_color.material_id_color(material))
        if material is not None
        else list(object_fallback)
        for material in materials
    ]

    def _identity(material):
        if material is None:
            return None
        try:
            return int(material.as_pointer())
        except Exception:
            return str(getattr(material, "name", "") or "")

    object_name = str(getattr(obj, "name", "") or "")
    if len({_identity(material) for material in materials}) <= 1:
        # One material on every slot: no per-triangle data, the colour paints the mesh.
        return protocol.IdMaterialMesh(object_name=object_name, colors=[palette[0]])
    resolved = _id_material_triangle_slots(
        obj, depsgraph, len(materials), speculative=speculative
    )
    if resolved is None:
        return None
    sidecar_path, triangle_count, used_slots = resolved
    used_slots = [slot for slot in used_slots if 0 <= slot < len(materials)] or [0]
    if len({_identity(materials[slot]) for slot in used_slots}) <= 1:
        # Several slots exist but the faces only show one material.
        return protocol.IdMaterialMesh(object_name=object_name, colors=[palette[used_slots[0]]])
    if not sidecar_path:
        return None
    return protocol.IdMaterialMesh(
        object_name=object_name,
        colors=palette,
        slot_index_path=sidecar_path,
        triangle_count=int(triangle_count),
    )


def _selected_maps_use_id_material(project, selected_map_types=None, selected_map_uuids=None) -> bool:
    for item in _selected_project_maps(project, selected_map_types, selected_map_uuids):
        if str(getattr(item, "map_type", "") or "") != constants.MAP_ID:
            continue
        if (
            str(getattr(item, "id_source", constants.MAP_ID_SOURCE_OBJECT) or "")
            == constants.MAP_ID_SOURCE_MATERIAL
        ):
            return True
    return False


def _build_id_material_meshes(project, selected_group_names, depsgraph, *, speculative: bool = False):
    """MBBJOB35 records for every high object of the selected groups, sorted by name.

    Called only when a selected ID map uses the "Material Color" source; every other job
    carries no records, so its payload and every backend cache key stay unchanged.
    """
    records: dict[str, protocol.IdMaterialMesh] = {}
    seen: set[str] = set()
    for group in getattr(project, "groups", []) or []:
        if (
            selected_group_names is not None
            and str(getattr(group, "name", "") or "") not in selected_group_names
        ):
            continue
        for slot in _iter_valid_object_slots(properties.effective_high_mesh_slots(group)):
            obj = slot.object_ref
            name = str(getattr(obj, "name", "") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            if floater_faces.has_floater_faces(obj):
                for record in _id_material_meshes_for_split_object(obj, depsgraph, speculative=speculative):
                    records[record.object_name] = record
                continue
            record = _id_material_mesh_for_object(obj, depsgraph, speculative=speculative)
            if record is not None:
                records[name] = record
    return [records[name] for name in sorted(records)]


def _id_material_meshes_for_split_object(obj, depsgraph, *, speculative: bool = False):
    """ID "Material Color" records for a high with floater faces (floater_faces.py).

    The export writes it as two sources, the body under the object's name and the marked
    faces as its floater piece, so each gets its own record and per-triangle slot sidecar.
    A piece showing one material gets that colour alone. Empty when nothing can be built:
    each piece then falls back to the object's single colour, as for any object.
    """
    import numpy as np

    from . import high_mesh_cache, id_material_color

    materials = [getattr(slot, "material", None) for slot in (getattr(obj, "material_slots", None) or [])]
    if not materials or all(material is None for material in materials):
        return []
    object_fallback = _resolve_rgb_triplet(getattr(obj, "color", None))
    palette = [
        list(id_material_color.material_id_color(material)) if material is not None else list(object_fallback)
        for material in materials
    ]
    names = (str(obj.name), floater_faces.floater_object_name(obj.name))
    if speculative:
        return []
    try:
        slots = _object_triangle_material_slots(obj, depsgraph, len(materials))
        evaluated = obj.evaluated_get(depsgraph)
        mesh = getattr(evaluated, "data", None) if getattr(evaluated, "type", "") == "MESH" else None
        mask = floater_faces.triangle_marked_mask(mesh) if mesh is not None else None
    except Exception:
        return []
    if slots is None or mask is None or len(mask) != len(slots):
        return []
    floater_count = int(mask.sum())
    pieces = ((names[0], slots[: len(slots) - floater_count], "BODY"), (names[1], slots[len(slots) - floater_count :], "FLOATER"))
    try:
        revision_key = high_mesh_cache.geometry_revision_key(obj)
    except Exception:
        revision_key = ""
    records = []
    for name, piece, part in pieces:
        if piece.size == 0:
            continue
        used = tuple(int(index) for index in np.flatnonzero(np.bincount(piece, minlength=len(materials))))
        if len(used) <= 1:
            records.append(protocol.IdMaterialMesh(object_name=name, colors=[palette[used[0] if used else 0]]))
            continue
        key = f"{revision_key}|{'|'.join(str(term) for term in floater_faces.signature(obj))}|{part}" if revision_key else ""
        path = _id_slot_sidecar_cache_path(key, len(materials)) if key else None
        if path is None or not (path.is_file() or _write_id_slot_sidecar_file(path, piece, used)):
            continue
        records.append(
            protocol.IdMaterialMesh(
                object_name=name, colors=palette, slot_index_path=str(path), triangle_count=int(piece.size)
            )
        )
    return records


def resolve_group_map_output_paths(project, group, map_setting, output_dir=None, depsgraph=None) -> list[str]:
    """Every concrete file one map row writes for one group, one per UDIM tile.

    Same resolution export itself uses (effective type + effective suffix through
    ``naming``, plus the group's tile plan), so callers outside the exporter cannot
    drift from the real names. A non-tiled set yields exactly one path.
    """
    directory = str(output_dir or getattr(project, "last_output_dir", "") or "").strip()
    if not directory or group is None or map_setting is None:
        return []
    metadata_state = properties.group_metadata_state(group)
    set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip()
    texture_set_name = properties.resolve_texture_set_output_name(project, set_key) if set_key else None
    try:
        tile_specs, tokenized, _diagnostics = _resolve_group_tile_plan(project, group, depsgraph=depsgraph)
    except Exception:
        tile_specs, tokenized = [], False
    tiles: list[int | None] = (
        [int(getattr(spec, "udim_tile", 0) or 0) for spec in tile_specs] if tokenized else [None]
    )
    paths: list[str] = []
    for tile in tiles:
        try:
            file_name = naming.build_output_file_name(
                group_name=str(getattr(group, "name", "") or ""),
                map_type=_effective_map_type_for_setting(map_setting),
                bit_depth=str(getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8),
                image_format=str(getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT),
                texture_set_name=texture_set_name,
                udim_tile=tile,
                map_label_override=properties.effective_map_output_suffix(project, map_setting),
                project_name=str(getattr(project, "name", "") or ""),
            )
        except Exception:
            continue
        paths.append(str(Path(directory) / file_name))
    return paths


def resolve_group_map_output_path(project, group, map_setting, output_dir=None):
    """The first file one map row writes for one group, or None.

    Kept for callers that only need a representative name; anything that touches the
    files themselves must use :func:`resolve_group_map_output_paths`, because a
    tokenized texture set writes one file per tile and this name matches none of them.
    """
    paths = resolve_group_map_output_paths(project, group, map_setting, output_dir=output_dir)
    return paths[0] if paths else None


def rasterize_group_low_uv_mask(group, width: int, height: int, *, dilate_texels: int = 0, udim_tile: int = 0):
    """Boolean mask of the texels this group's LOW meshes occupy, or None.

    Used to composite per-group bakes that share one texture-set file: only the
    texels a group actually owns may be taken from that group's pass. ``dilate_texels``
    grows the mask so the backend's own margin dilation rides along with its island.
    ``udim_tile`` (1001..) restricts the mask to the islands of that tile; 0 folds
    every tile onto one 0..1 mask, which is only right for a non-UDIM output. Folded
    onto one mask, a group with islands in 1001 and 1002 claimed the same texels twice
    and the composite handed another group's texels to it in whichever tile file it
    was applied to.
    """
    from . import project_structure

    low_objs = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or [])
    if not low_objs:
        return None
    only_material = low_material_subset.group_material_name(group)
    # The group's BAKE UV set, like every other rasterization path: reading the active
    # layer built the ownership mask from a different layout than the bake, so the
    # composite took texels from the wrong regions and one group's islands overwrote
    # another's in the shared texture-set file.
    projection_state = _group_projection_settings_state(group)
    bake_uv_name = (getattr(projection_state, "uv_layer_name", "") or "").strip()
    with low_material_subset.object_scope(low_objs, only_material):
        return rasterize_low_uv_mask(
            low_objs, width, height, uv_layer_name=bake_uv_name, dilate_texels=dilate_texels, udim_tile=udim_tile
        )


def rasterize_low_uv_mask(
    low_objs,
    width: int,
    height: int,
    *,
    uv_layer_name: str = "",
    use_active_render: bool = False,
    dilate_texels: int = 0,
    udim_tile: int = 0,
):
    """Boolean mask of the texels ``low_objs`` occupy in one UV layer, or None.

    The layer is ``uv_layer_name`` where the mesh has it, else the active layer, or
    the active RENDER layer with ``use_active_render`` (the one a Blender bake
    without an explicit ``uv_layer`` rasterizes into).
    """
    import numpy as np

    width = max(1, int(width))
    height = max(1, int(height))
    tile_filter = None
    if int(udim_tile or 0) > 0:
        from . import udim as _udim_mod

        tile_filter = np.asarray(_udim_mod.tile_origin(int(udim_tile)), dtype=np.float32)
    low_objs = list(low_objs or [])
    if not low_objs:
        return None
    bake_uv_name = str(uv_layer_name or "").strip()
    mask = np.zeros((height, width), dtype=bool)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    try:
        for obj in low_objs:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                calc = getattr(mesh, "calc_loop_triangles", None)
                if callable(calc):
                    calc()
                tris = mesh.loop_triangles
                count = len(tris)
                fallback_layer = mesh.uv_layers.active
                if use_active_render:
                    fallback_layer = next(
                        (layer for layer in mesh.uv_layers if bool(getattr(layer, "active_render", False))),
                        fallback_layer,
                    )
                uv_layer = (mesh.uv_layers.get(bake_uv_name) if bake_uv_name else None) or fallback_layer
                if count == 0 or uv_layer is None:
                    continue
                loop_uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
                uv_layer.data.foreach_get("uv", loop_uv)
                loop_uv = loop_uv.reshape(-1, 2)
                # foreach_get writes int32; a wider buffer receives interleaved garbage.
                tri_loops = rna_buffers.empty_u32_for_rna(count * 3)
                tris.foreach_get("loops", tri_loops)
                tri_loops = rna_buffers.as_i32(tri_loops).reshape(-1, 3)
                uv_a = loop_uv[tri_loops[:, 0]]
                uv_b = loop_uv[tri_loops[:, 1]]
                uv_c = loop_uv[tri_loops[:, 2]]
                material_mask = low_material_subset.triangle_mask(obj, mesh)
                for index in range(count):
                    if material_mask is not None and not material_mask[index]:
                        continue
                    # Translate by the centroid tile (never per vertex): a UV of exactly
                    # 1.0 would collapse a border triangle into a degenerate sliver.
                    tile = np.floor((uv_a[index] + uv_b[index] + uv_c[index]) / 3.0)
                    if tile_filter is not None and not np.array_equal(tile, tile_filter):
                        continue
                    a = (uv_a[index] - tile) * (width, height)
                    b = (uv_b[index] - tile) * (width, height)
                    c = (uv_c[index] - tile) * (width, height)
                    x0 = max(0, int(np.floor(min(a[0], b[0], c[0]))) - 1)
                    x1 = min(width - 1, int(np.ceil(max(a[0], b[0], c[0]))) + 1)
                    y0 = max(0, int(np.floor(min(a[1], b[1], c[1]))) - 1)
                    y1 = min(height - 1, int(np.ceil(max(a[1], b[1], c[1]))) + 1)
                    if x1 < x0 or y1 < y0:
                        continue
                    determinant = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
                    if abs(float(determinant)) < 1e-12:
                        continue
                    xs = np.arange(x0, x1 + 1, dtype=np.float32) + 0.5
                    ys = np.arange(y0, y1 + 1, dtype=np.float32) + 0.5
                    gx, gy = np.meshgrid(xs, ys)
                    w0 = ((b[0] - gx) * (c[1] - gy) - (c[0] - gx) * (b[1] - gy)) / determinant
                    w1 = ((c[0] - gx) * (a[1] - gy) - (a[0] - gx) * (c[1] - gy)) / determinant
                    w2 = 1.0 - w0 - w1
                    # Slight negative tolerance so texel centres on an edge rasterize.
                    inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
                    mask[y0 : y1 + 1, x0 : x1 + 1] |= inside
            finally:
                evaluated.to_mesh_clear()
    except Exception:
        return None
    if not mask.any():
        return None
    for _ in range(max(0, int(dilate_texels))):
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        mask = grown
    return mask


def composite_take_mask(mask, base_rgb, group_rgb, island_union=None, *, epsilon: float = 0.5 / 255.0):
    """Flat boolean selector for :func:`composite_group_texels`.

    A texel takes the new pass's value when it belongs to this group's (dilated)
    islands, or — outside every island in the set — when the base left it empty and
    the new pass filled it, which is how the pass keeps its own margin dilation
    without overwriting a neighbour's.
    """
    import numpy as np

    take = np.asarray(mask).reshape(-1).copy()
    if island_union is None:
        return take
    union = np.asarray(island_union).reshape(-1)
    if union.shape != take.shape:
        return take
    empty_base = np.asarray(base_rgb).reshape(-1, 3).max(axis=1) <= epsilon
    filled_group = np.asarray(group_rgb).reshape(-1, 3).max(axis=1) > epsilon
    return take | (empty_base & filled_group & ~union)


def infinite_dilation_group_take_mask(current_islands, previous_islands):
    """Assign infinite padding to the closest group's UV islands."""
    import numpy as np
    from . import export_pack

    current = np.asarray(current_islands, dtype=bool)
    previous = np.asarray(previous_islands, dtype=bool)
    if current.shape != previous.shape:
        raise ValueError("Per-group UV masks must have the same size")
    if not current.any():
        return np.zeros_like(current)
    if not previous.any():
        return np.ones_like(current)
    _, _, current_distance = export_pack._nearest_covered_texels(current)
    _, _, previous_distance = export_pack._nearest_covered_texels(previous)
    return (~previous) & (current_distance < previous_distance)


def composite_group_texels(base_path: str, group_path: str, mask, *, island_union=None) -> bool:
    """Write ``group_path``'s texels into ``base_path`` wherever ``mask`` is set.

    Per-group native material passes each render one group into the texture set's
    shared file, so without this the last group's pass would leave every other
    group's islands black. Both images are read as Non-Color, so the stored values
    round-trip untouched whatever the file's colour space claims to be.

    ``island_union`` (every group's undilated islands) additionally lets this pass
    keep its own margin dilation: outside every island, a texel the base left empty
    takes the new bake's value. Without it the groups after the first shipped a
    thinner dilation ring than the single-job route did, which is what a mip chain
    pulls dark edges from.
    """
    import numpy as np

    if mask is None:
        return False
    base_image = None
    group_image = None
    try:
        base_image = bpy.data.images.load(str(base_path), check_existing=False)
        group_image = bpy.data.images.load(str(group_path), check_existing=False)
        base_image.colorspace_settings.name = "Non-Color"
        group_image.colorspace_settings.name = "Non-Color"
        width, height = base_image.size
        if (width, height) != tuple(group_image.size) or mask.shape != (height, width):
            return False
        base_pixels = np.empty(width * height * 4, dtype=np.float32)
        group_pixels = np.empty(width * height * 4, dtype=np.float32)
        base_image.pixels.foreach_get(base_pixels)
        group_image.pixels.foreach_get(group_pixels)
        take = composite_take_mask(
            mask,
            base_pixels.reshape(-1, 4)[:, :3],
            group_pixels.reshape(-1, 4)[:, :3],
            island_union if island_union is not None and island_union.shape == (height, width) else None,
        )
        selector = np.repeat(take, 4)
        np.copyto(base_pixels, group_pixels, where=selector)
        base_image.pixels.foreach_set(base_pixels)
        base_image.filepath_raw = str(base_path)
        base_image.save()
        return True
    except Exception:
        return False
    finally:
        for image in (group_image, base_image):
            if image is not None:
                try:
                    image_cleanup.remove_image_when_safe(image, reason="group composite")
                except Exception:
                    pass


def _corner_sidecar_cache_path(name: str, payload: bytes):
    """Where a content-addressed corner sidecar lives, or None if unavailable."""
    try:
        from . import preferences

        root = Path(preferences.persistent_cache_root()) / "material_ir_sidecars"
        digest = hashlib.blake2b(payload, digest_size=16).hexdigest()
        return root / f"{name}_{digest}.png"
    except Exception:
        return None


def _cached_corner_sidecar(name: str, payload: bytes):
    path = _corner_sidecar_cache_path(name, payload)
    if path is None:
        return None
    try:
        return str(path) if path.is_file() else None
    except OSError:
        return None


def _store_cached_corner_sidecar(name: str, payload: bytes, written) -> None:
    """Publish a freshly encoded sidecar for the next bake. Best effort throughout:
    a full disk or a swept cache must never fail the bake that produced it."""
    path = _corner_sidecar_cache_path(name, payload)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            # Same reason as _write_rgba_png_bytes_file: the hit test is "the file
            # exists", so a half-copied sidecar would be served forever.
            temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                shutil.copyfile(str(written), str(temporary))
                os.replace(temporary, path)
            except OSError:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
    except OSError:
        pass


#: Per-run memo for the multi-component arrays a corner sidecar is sliced from.
#: A colour needs three or four components and a UV two, and each one used to
#: re-read the whole layer off the evaluated mesh: measured at 2.83 s per read on
#: this 44.2 M-corner high, so a UV pair paid it twice for identical bytes. Keyed
#: by workspace, because a workspace belongs to exactly one job and a mesh cannot
#: change under a bake that is already running. Only the newest workspace is kept,
#: so the arrays (hundreds of MB) are dropped as soon as the next bake starts.
_CORNER_SOURCE_MEMO: dict[tuple, "object"] = {}
_CORNER_SOURCE_MEMO_WORKSPACE: str = ""


def _corner_source_cached(workspace_path, family, layer_name, obj, build):
    """Read a per-corner layer once per (workspace, family, layer, object)."""
    global _CORNER_SOURCE_MEMO_WORKSPACE
    workspace_key = str(workspace_path or "")
    if workspace_key != _CORNER_SOURCE_MEMO_WORKSPACE:
        _CORNER_SOURCE_MEMO.clear()
        _CORNER_SOURCE_MEMO_WORKSPACE = workspace_key
    key = (family, str(layer_name or ""), str(getattr(obj, "name", "") or ""))
    cached = _CORNER_SOURCE_MEMO.get(key)
    if cached is None:
        cached = build()
        _CORNER_SOURCE_MEMO[key] = cached
    return cached


def _write_corner_attribute_sidecar(
    channel_tag, project, workspace_path, selected_group_names, ir_identity,
    slot_materials=(), path_token: str = "",
):
    """Pack a per-corner attribute into a sidecar PNG riding the resource pipeline.

    Texel index = high_triangle_index * 3 + corner; each float32 is stored
    bit-exactly in the texel's RGBA8 bytes (little-endian). The arrays are
    computed on the ORIGINAL Blender topology (see material_geometry_attributes)
    of the group's high objects, concatenated in slot order to match the exported
    triangle order. Per-object computation makes the concatenation safe: neither
    pointiness nor islands cross object boundaries.

    Returns None for multi-group selections: resource paths are per-job while
    triangle indices restart per group, so one sidecar cannot serve two groups.
    Those bakes route to Cycles rather than reading another group's triangles.
    """
    import bpy

    import numpy as np

    from . import material_geometry_attributes
    from . import material_ir
    from . import project_structure

    groups = [
        group for group in project.groups
        if selected_group_names is None
        or str(getattr(group, "name", "") or "") in selected_group_names
    ]
    if len(groups) != 1:
        return None
    high_targets = list(
        project_structure.group_role_targets(groups[0], constants.OBJECT_ROLE_HIGH) or []
    )
    source_objs = high_targets or list(
        project_structure.group_role_targets(groups[0], constants.OBJECT_ROLE_LOW) or []
    )
    if not source_objs:
        return None

    name = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in channel_tag.split(":", 1)[1].lower()
    )
    directory = Path(workspace_path) / "material_ir"
    directory.mkdir(parents=True, exist_ok=True)
    # A sidecar's contents depend only on the channel tag and the group's source
    # objects, and a workspace belongs to exactly one job (and, per the guard above,
    # one group). Colour sidecars therefore drop the per-channel identity from the
    # name: without that a four-channel material wrote the same 88 MB component file
    # once per channel -- half a gigabyte of duplicates for one bake of a 7.4 M-triangle
    # high. The existing tags keep their identity in the name so no previously written
    # workspace can be misread, and every tag now short-circuits on an existing file.
    if channel_tag == material_ir.CORNER_ATTR_MATERIAL_SLOT:
        # Two channels can merge DIFFERENT material sets (one channel's materials
        # may agree while another's do not), so the order is part of the identity.
        order = hashlib.sha1(repr(tuple(slot_materials)).encode("utf-8", "replace")).hexdigest()[:12]
        path = directory / f"corner_{name}_{order}.png"
    elif channel_tag.startswith(
        (
            material_ir.CORNER_ATTR_COLOR_PREFIX,
            material_ir.CORNER_ATTR_UV_PREFIX,
            # The attribute name is the whole identity for a scalar sidecar, so it
            # dedupes across channels the same way, rather than writing one copy per
            # channel that happens to read the same mask.
            material_ir.CORNER_ATTR_FLOAT_PREFIX,
        )
    ):
        path = directory / f"corner_{name}.png"
    else:
        safe_identity = "".join(
            ch if ch.isalnum() or ch in "-_" else "_" for ch in str(ir_identity)
        )
        path = directory / f"corner_{name}_{safe_identity}.png"
    if path_token:
        path = path.with_name(f"{path.stem}_{path_token}{path.suffix}")
    if path.is_file():
        return str(path)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    chunks = []
    # The tangent solve writes (and then frees) loop tangents on the mesh it is given,
    # so it keeps working on a private copy. Every other family only READS the mesh.
    mutates_mesh = material_ir.parse_corner_tangent_channel_tag(channel_tag) is not None
    try:
        for obj in source_objs:
            evaluated = obj.evaluated_get(depsgraph)
            # Read the evaluated mesh in place, as _object_triangle_material_slots does.
            # `to_mesh()` duplicated the whole evaluated mesh first -- about 1 GB on a
            # 15M-triangle high -- only to read a few arrays out of it.
            mesh = None
            if not mutates_mesh and getattr(evaluated, "type", "") == "MESH":
                mesh = getattr(evaluated, "data", None)
            temporary = mesh is None
            if temporary:
                mesh = evaluated.to_mesh()
            try:
                if channel_tag == material_ir.CORNER_ATTR_POINTINESS:
                    chunks.append(
                        material_geometry_attributes.pointiness_per_corner(mesh)
                    )
                elif channel_tag == material_ir.CORNER_ATTR_ISLAND_RANDOM:
                    per_triangle = material_geometry_attributes.island_random_per_triangle(mesh)
                    # A broadcast VIEW: the three corners are written straight into
                    # the sidecar buffer below, never materialised as their own array.
                    chunks.append(
                        np.broadcast_to(per_triangle[:, None], (per_triangle.shape[0], 3))
                    )
                elif material_ir.parse_corner_color_channel_tag(channel_tag) is not None:
                    layer_name, component = material_ir.parse_corner_color_channel_tag(
                        channel_tag
                    )
                    rgba = _corner_source_cached(
                        workspace_path, "COLOR", layer_name, obj,
                        lambda: material_geometry_attributes.color_attribute_per_corner(
                            mesh, layer_name
                        ),
                    )
                    if rgba.size == 0:
                        # No such colour layer on this object. One sidecar serves the
                        # whole group, so a partial read would hand another object's
                        # corners to this one; refuse and let the channel take Cycles.
                        return None
                    chunks.append(rgba[:, :, int(component)])
                elif material_ir.parse_corner_float_attr_tag(channel_tag) is not None:
                    attr_name = material_ir.parse_corner_float_attr_tag(channel_tag)
                    scalars = _corner_source_cached(
                        workspace_path, "FLOAT", attr_name, obj,
                        lambda: material_geometry_attributes.float_attribute_per_corner(
                            mesh, attr_name
                        ),
                    )
                    if scalars.size == 0:
                        # Same contract as the colour branch: one sidecar serves the
                        # whole group, so a partial read would hand another object's
                        # corners to this one. Refuse and let the channel take Cycles.
                        return None
                    chunks.append(scalars)
                elif channel_tag == material_ir.CORNER_ATTR_MATERIAL_SLOT:
                    order = {str(n): i for i, n in enumerate(slot_materials)}
                    slot_to_index = [
                        order.get(
                            str(getattr(getattr(slot, "material", None), "name", "") or ""), -1
                        )
                        for slot in (getattr(obj, "material_slots", []) or [])
                    ]
                    if not slot_to_index or all(i < 0 for i in slot_to_index):
                        # This object contributes no material the merged program
                        # knows about; one sidecar serves the whole group, so guessing
                        # an index would shade it with another material's program.
                        return None
                    chunks.append(
                        material_geometry_attributes.material_index_per_corner(
                            mesh, slot_to_index
                        )
                    )
                elif material_ir.parse_corner_tangent_channel_tag(channel_tag) is not None:
                    layer_name, component = material_ir.parse_corner_tangent_channel_tag(
                        channel_tag
                    )
                    tangents = _corner_source_cached(
                        workspace_path, "TANGENT", layer_name, obj,
                        lambda: material_geometry_attributes.uv_tangent_per_corner(
                            mesh, layer_name
                        ),
                    )
                    if tangents.size == 0:
                        # Same rule as the UV and colour layers: a frame missing from
                        # one contributing object cannot be faked from its neighbours,
                        # and a wrong tangent frame is a wrong normal map everywhere.
                        return None
                    chunks.append(tangents[:, :, int(component)])
                elif material_ir.parse_corner_uv_channel_tag(channel_tag) is not None:
                    layer_name, component = material_ir.parse_corner_uv_channel_tag(
                        channel_tag
                    )
                    uvs = _corner_source_cached(
                        workspace_path, "UV", layer_name, obj,
                        lambda: material_geometry_attributes.uv_layer_per_corner(
                            mesh, layer_name
                        ),
                    )
                    if uvs.size == 0:
                        # Same rule as the colour layers above: a UV set missing from
                        # one contributing object cannot be faked from its neighbours.
                        return None
                    chunks.append(uvs[:, :, int(component)])
                else:
                    return None
                if chunks and floater_faces.has_floater_faces(obj):
                    # Export order of a high with floater faces: body, then the piece.
                    chunks[-1] = floater_faces.reorder_export_triangles(mesh, chunks[-1])
            finally:
                if temporary:
                    evaluated.to_mesh_clear()
    except Exception:
        return None
    if not chunks:
        return None
    for chunk in chunks:
        if chunk.size % 3:
            # Every family is per corner, three per triangle; the old reshape(-1, 3)
            # raised here, and so does this.
            raise ValueError(f"corner sidecar chunk of {chunk.size} values is not per corner")
    corner_count = int(sum(int(chunk.size) for chunk in chunks))

    # float32 -> RGBA8 bytes, one texel per corner, row-major into a fixed-width image.
    # `<f4` pins little-endian so the shader's byte order holds on a big-endian host,
    # which is what struct's "<f" was doing.
    #
    # Written straight into the ONE padded buffer the PNG encoder reads. The old path
    # went concatenate -> astype -> tobytes -> padded copy: four full-size copies,
    # ~540 MB each at a 15M-triangle high's 45M corners, alive at once for ~3 GB of
    # transient per sidecar. Same bytes, one buffer.
    width = 1024
    height = max(1, (corner_count + width - 1) // width)
    padded = np.zeros((height * width, 4), dtype=np.uint8)
    corner_bytes = padded.reshape(-1)[: corner_count * 4]
    corners = corner_bytes.view("<f4")
    offset = 0
    for chunk in chunks:
        count = int(chunk.size)
        # Same float32 rounding as the old astype(np.float32); strided views (one
        # component of a colour or UV layer) are gathered by the assignment itself.
        # (reshape of an already (N, 3) view is itself a view, so nothing is copied.)
        corners[offset: offset + count].reshape(-1, 3)[...] = np.asarray(chunk).reshape(-1, 3)
        offset += count
    del chunks
    payload = memoryview(corner_bytes)

    # Content-addressed reuse across bakes. The key is a hash of the bytes about to
    # be written, so it cannot go stale: edit the layer and the hash changes with it.
    # That matters because the cheap per-object signatures the mesh cache uses do NOT
    # cover per-loop UV or colour values, and a sidecar keyed on one of those would
    # happily serve yesterday's UVs. Encoding measured 2.9 s per component on this
    # high (2.35 s of it inside the PNG writer), so a repeat bake skips that.
    cached = _cached_corner_sidecar(name, payload)
    if cached is not None:
        try:
            shutil.copyfile(cached, path)
            return str(path)
        except OSError:
            pass

    # The PNG is a bit container, not a picture: write the exact bytes without a
    # float round trip or a temporary image datablock.
    if not _write_rgba_png_bytes_file(path, width, height, padded):
        raise OSError(f"could not write corner sidecar '{path}'")
    _store_cached_corner_sidecar(name, payload, path)
    return str(path)


def _collect_material_fast_path_source(mat_item, project, workspace_path, selected_group_names):
    """Resolve the untiled material fast-path source.

    Returns ``None`` when the fast path does not apply, otherwise a dict:

    ``{"path": <PNG>, "tiles": []}``

    ``tiles`` is always empty. A tiled (UDIM) source declines here: UDIM images bake
    through Material IR's per-tile tables (`_normalize_tiled_image_to_pngs`), which
    decode each tile's colour space and alpha mode. This route handed raw tile files
    to the backend with neither.
    """
    common_source = _collect_material_fast_path_common_source(
        mat_item, project, selected_group_names, workspace_path
    )
    if common_source is None:
        return None

    from . import udim as _udim

    if _udim.is_logical_udim_path(common_source):
        return None

    normalized = _normalize_material_source_to_png(common_source, workspace_path)
    if not normalized:
        return None
    return {"path": normalized, "tiles": []}


def _collect_material_fast_path_common_source(
    mat_item, project, selected_group_names, workspace_path
) -> str | None:
    """The one source path every relevant object agrees on, or ``None``.

    Split out of :func:`_collect_material_fast_path_png` so the untiled and tiled collectors
    share one traversal. The returned string is either a concrete image path or, for a tiled
    source, the logical ``<UDIM>`` path.
    """
    channel = str(getattr(mat_item, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or "").strip().upper()
    common_source: str | None = None

    for group in project.groups:
        if selected_group_names is not None and str(getattr(group, "name", "") or "") not in selected_group_names:
            continue
        # Sample from high meshes when present; they are the projection source.
        # Fall back to low meshes for same-object (no-highpoly) bakes.
        high_slots = list(_iter_valid_object_slots(properties.effective_high_mesh_slots(group)))
        source_slots = high_slots if high_slots else list(_iter_valid_object_slots(getattr(group, "low_meshes", [])))
        if not source_slots:
            return None
        for slot in source_slots:
            obj = slot.object_ref
            path = resolve_material_fast_path(obj, channel, workspace_path)
            if path is None:
                return None
            if common_source is None:
                common_source = path
            elif common_source != path:
                return None  # Different images across objects — fall back to EEVEE

    return common_source


def _collect_material_fast_path_png(mat_item, project, workspace_path, selected_group_names) -> str | None:
    """Determine a single PNG source image for a MAP_MATERIAL item across all groups/objects.

    For each group, the material source is read from the HIGH meshes when present (those are
    the objects the backend projects from), falling back to LOW meshes for same-object bakes.
    All objects across all relevant groups must agree on the same source image; any mismatch,
    missing material, or unresolvable fast path returns None (→ Cycles bake path).

    Objects with no material slots also return None. Multi-slot objects where channel sources
    differ between slots likewise return None via resolve_material_fast_path.

    A tiled (UDIM) source returns None; see :func:`_collect_material_fast_path_source`.
    """
    resolved = _collect_material_fast_path_source(
        mat_item, project, workspace_path, selected_group_names
    )
    if resolved is None:
        return None
    return str(resolved.get("path") or "") or None


def find_duplicate_output_map_settings(
    project,
    selected_map_uuids=None,
    selected_map_types=None,
):
    """Return collision groups for the given selection filter.

    Each group is a list of ``(map_setting, effective_type, effective_suffix)`` tuples for
    *all* maps that share the same output key — including the first occurrence.
    Only groups with two or more entries are returned; an empty list means no collisions."""
    groups: dict = {}  # key -> list of (map_setting, effective_type, effective_suffix)
    for map_setting in getattr(project, "maps", []):
        if getattr(map_setting, "is_add_phantom", False):
            continue
        map_uuid = properties.ensure_map_setting_uuid(map_setting)
        map_selected_by_uuid = selected_map_uuids is not None and map_uuid in selected_map_uuids
        if selected_map_uuids is not None:
            if not map_selected_by_uuid:
                continue
            if selected_map_types is not None and map_setting.map_type not in selected_map_types:
                continue
        elif selected_map_types is not None:
            if map_setting.map_type not in selected_map_types:
                continue
        elif not bool(getattr(map_setting, "enabled", False)):
            continue
        effective_type = effective_map_type_for_setting(map_setting)
        effective_suffix = properties.effective_map_output_suffix(project, map_setting)
        # Key on the FILE the row writes, not on (type, suffix). Two different map
        # types can name the same file: geometry Normal and Material -> Normal both
        # resolve to "Normal" (and geometry Opacity / Material -> Opacity both to
        # "Opacity"), so an ordinary texture set tripped
        # the hard "would write X twice" validator instead of this dialog's offer to
        # rename. Casefolded because NTFS is. See MATERIAL_BAKE_QA_2026_08_19_PASS2, G9.
        key = _duplicate_output_key(project, map_setting, effective_type, effective_suffix)
        groups.setdefault(key, []).append((map_setting, effective_type, effective_suffix))
    return [group for group in groups.values() if len(group) > 1]


def _duplicate_output_key(project, map_setting, effective_type, effective_suffix):
    """The identity two map rows must not share: the output file name, casefolded.

    Falls back to the old (type, suffix) pair when the naming pipeline cannot resolve
    a name -- a project with no groups, say. A weaker key can only miss a collision
    the validator still catches; it can never invent one.
    """
    group_name = ""
    for group in getattr(project, "groups", []) or []:
        group_name = str(getattr(group, "name", "") or "")
        if group_name:
            break
    if group_name:
        file_name = _current_output_file_name(project, group_name, map_setting)
        if file_name:
            return ("file", file_name.casefold())
    return ("pair", str(effective_type), str(effective_suffix or ""))


def _infer_output_suffix(project, group_name: str, map_type: str, file_path: str) -> str:
    """Infer the effective output_suffix for a produced file by comparing its stem against the
    stems we would generate for each configured map of that type.

    ``map_type`` may be an *effective* backend type (e.g. ``CURVATURE_DIRECTION``) that differs
    from the raw stack type (``CURVATURE``).  The comparison therefore uses
    ``_effective_map_type_for_setting`` so that all curvature mode variants are matched correctly."""
    if not file_path:
        return ""
    from pathlib import Path as _Path
    # Path.stem of "Asset_Normal.1001.png" is "Asset_Normal.1001", so the tile has to come
    # off before comparing against the untiled stems build_output_stem generates. Without
    # this, every tokenized-naming output silently fails suffix recovery.
    file_stem, _file_udim_tile = naming.split_udim_tile_suffix(_Path(file_path).stem)
    texture_set_name = _group_texture_set_name(project, group_name)
    normalized_type = str(map_type or "").strip().upper()
    for ms in getattr(project, "maps", []):
        if _effective_map_type_for_setting(ms).upper() != normalized_type:
            continue
        if getattr(ms, "is_add_phantom", False):
            continue
        effective_suffix = properties.effective_map_output_suffix(project, ms)
        expected_stem = naming.build_output_stem(
            group_name=group_name,
            map_type=map_type,
            texture_set_name=texture_set_name,
            map_label_override=effective_suffix,
            project_name=str(getattr(project, "name", "") or ""),
        )
        if file_stem == expected_stem:
            return effective_suffix or ""
    # Stem didn't match any setting; fall back to the first setting with a matching effective type.
    for ms in getattr(project, "maps", []):
        if getattr(ms, "is_add_phantom", False):
            continue
        if _effective_map_type_for_setting(ms).upper() == normalized_type:
            return properties.effective_map_output_suffix(project, ms) or ""
    return ""


def _latest_output_descriptor(
    project,
    group_name: str,
    map_type: str,
    file_path: str,
    *,
    output_suffix: str | None = None,
    map_uuid: str = "",
    effective_map_type: str = "",
) -> dict:
    """One tracked-output descriptor.

    ``map_type`` is always the RAW map-stack type (``MATERIAL``, ``SCENE_LIGHTING``)
    so the Outputs panel and every raw-type consumer can match it against the row
    that produced it. ``effective_map_type`` is always populated with the
    effective/backend type (``MATERIAL_ALBEDO``, ``LIGHTING``,
    ``CURVATURE_DIRECTION``); when the two coincide it simply repeats the raw
    type. Callers that genuinely cannot resolve a raw type (an orphaned uuid, a
    file no row matches) pass the effective type as BOTH, which keeps every
    consumer addressing the entry under the only name that exists for it.
    """
    texture_set_name = _group_texture_set_name(project, group_name)
    if output_suffix is None:
        output_suffix = _infer_output_suffix(project, group_name, map_type, file_path)
    map_label_override = output_suffix or None
    resolved_effective = str(effective_map_type or "").strip() or str(map_type or "")
    return {
        "map_uuid": str(map_uuid or ""),
        "group_name": group_name,
        "map_type": map_type,
        # Never left empty: an unpopulated effective type made healed entries
        # unaddressable by the templates that reference the effective name.
        "effective_map_type": resolved_effective,
        "output_suffix": output_suffix or "",
        # Labeled by the EFFECTIVE type so a MATERIAL row's Albedo and Roughness
        # outputs read as distinct entries instead of two identical "Material"s.
        "display_name": naming.output_display_label(
            group_name,
            resolved_effective,
            texture_set_name=texture_set_name,
            map_label_override=map_label_override,
            project_name=str(getattr(project, "name", "") or ""),
        ),
        "file_path": file_path,
    }


def _merge_output_descriptors(project, produced_files) -> list[dict]:
    # Build existing_paths keyed by (group_name, map_type, output_suffix, map_uuid).
    # Values carry (file_path, recorded effective type) so a merge pass never loses the
    # effective-type translation an orphaned-uuid entry cannot re-derive from the stack.
    existing_paths = {
        _produced_file_key(
            getattr(item, "group_name", ""),
            getattr(item, "map_type", ""),
            getattr(item, "output_suffix", ""),
            getattr(item, "map_uuid", ""),
        ): (
            str(getattr(item, "file_path", "") or ""),
            str(getattr(item, "effective_map_type", "") or ""),
        )
        for item in getattr(project, "latest_outputs", [])
        if str(getattr(item, "file_path", "") or "").strip()
    }
    existing_paths_by_legacy_key: dict[tuple[str, str, str], str | None] = {}
    for key, (file_path, _effective) in existing_paths.items():
        legacy_key = _produced_file_legacy_key(key[0], key[1], key[2])
        current_path = existing_paths_by_legacy_key.get(legacy_key)
        if current_path is None and legacy_key not in existing_paths_by_legacy_key:
            existing_paths_by_legacy_key[legacy_key] = file_path
        elif current_path != file_path:
            existing_paths_by_legacy_key[legacy_key] = None
    produced_descriptors_by_path: dict[str, dict] = {}
    produced_descriptors_by_key: dict[tuple[str, str, str, str], dict] = {}
    produced_descriptors_by_legacy_key: dict[tuple[str, str, str], dict | None] = {}
    for item in produced_files:
        if str(getattr(item, "map_uuid", "") or "").startswith("__fyr_detail_"):
            continue
        path = str(getattr(item, "path", "") or "").strip()
        if not path:
            continue
        descriptor = _descriptor_from_produced_file(
            project,
            str(getattr(item, "group_name", "") or ""),
            str(getattr(item, "map_type", "") or ""),
            path,
            map_uuid=str(getattr(item, "map_uuid", "") or ""),
        )
        produced_descriptors_by_path[path] = descriptor
        key = _produced_file_key(
            descriptor["group_name"],
            descriptor["map_type"],
            descriptor.get("output_suffix", ""),
            descriptor.get("map_uuid", ""),
        )
        produced_descriptors_by_key[key] = descriptor
        legacy_key = _produced_file_legacy_key(
            descriptor["group_name"],
            descriptor["map_type"],
            descriptor.get("output_suffix", ""),
        )
        current_descriptor = produced_descriptors_by_legacy_key.get(legacy_key)
        if current_descriptor is None and legacy_key not in produced_descriptors_by_legacy_key:
            produced_descriptors_by_legacy_key[legacy_key] = descriptor
        elif current_descriptor is not descriptor and (
            current_descriptor is None
            or str(current_descriptor.get("file_path", "") or "") != path
        ):
            produced_descriptors_by_legacy_key[legacy_key] = None

    descriptors: list[dict] = []
    seen_paths: set[str] = set()
    seen_keys: set[tuple[str, str, str, str]] = set()
    seen_legacy_keys: set[tuple[str, str, str]] = set()
    configured_legacy_key_counts: dict[tuple[str, str, str], int] = {}
    project_groups = list(getattr(project, "groups", []))
    current_group_names = {
        str(getattr(group, "name", "") or "")
        for group in project_groups
        if str(getattr(group, "name", "") or "").strip()
    }
    # Everything below that depends only on the map row (type, suffix, effective type, uuid)
    # is resolved once here instead of once per group x row: with G groups the stack walk
    # below visits G x M pairs twice, and each used to re-resolve its row from scratch.
    map_rows: list[tuple] = []
    if project_groups:
        for map_setting in getattr(project, "maps", []):
            if getattr(map_setting, "is_add_phantom", False):
                continue
            map_type = str(getattr(map_setting, "map_type", "") or "").strip()
            if not map_type:
                continue
            map_rows.append(
                (
                    map_setting,
                    map_type,
                    properties.effective_map_output_suffix(project, map_setting) or "",
                    # The row is live, so the raw -> effective translation is known;
                    # carrying it forward keeps rebuilt descriptors as addressable as the
                    # ones bake ingestion produced.
                    _effective_map_type_for_setting(map_setting) or map_type,
                    properties.ensure_map_setting_uuid(map_setting),
                )
            )
    for group in project_groups:
        group_name = str(getattr(group, "name", "") or "")
        for _map_setting, map_type, effective_suffix, _row_effective_type, _map_uuid in map_rows:
            legacy_key = _produced_file_legacy_key(group_name, map_type, effective_suffix)
            configured_legacy_key_counts[legacy_key] = configured_legacy_key_counts.get(legacy_key, 0) + 1
    # Directory this bake actually wrote into. A carried-forward entry pointing somewhere
    # else belongs to a superseded output root (the project's output directory changed, or
    # a preset moved it) and must not be listed as if it were current.
    current_output_dirs = {
        str(Path(str(descriptor.get("file_path", "") or "")).parent).casefold()
        for descriptor in produced_descriptors_by_path.values()
        if str(descriptor.get("file_path", "") or "").strip()
    }

    def _carried_path_is_current(path_text: str) -> bool:
        if not current_output_dirs:
            # Nothing produced this pass (e.g. Refresh Outputs after a no-op bake): there
            # is no evidence the recorded path is stale, so keep the existing behaviour.
            return True
        candidate = str(path_text or "").strip()
        if not candidate:
            return False
        return str(Path(candidate).parent).casefold() in current_output_dirs

    for group in project_groups:
        group_name = str(getattr(group, "name", "") or "")
        for _map_setting, map_type, effective_suffix, row_effective_type, map_uuid in map_rows:
            key = _produced_file_key(group_name, map_type, effective_suffix, map_uuid)
            legacy_key = _produced_file_legacy_key(group_name, map_type, effective_suffix)
            produced_descriptor = produced_descriptors_by_key.get(key)
            if produced_descriptor is not None:
                file_path = str(produced_descriptor.get("file_path", "") or "")
                descriptor = produced_descriptor
            else:
                # Nothing was produced for this row THIS pass, so anything listed here is
                # carried over from an earlier bake. A row switched off after a good bake
                # legitimately keeps its output (that file is still current -- see
                # test_apply_progress_merge_existing_preserves_outputs_for_disabled_maps),
                # but an entry pointing OUTSIDE the directory this bake wrote into belongs
                # to a superseded output root and cannot be current by definition.
                existing_entry = existing_paths.get(key)
                file_path = existing_entry[0] if existing_entry else None
                existing_effective = existing_entry[1] if existing_entry else ""
                if not _carried_path_is_current(file_path):
                    file_path = None
                    existing_effective = ""
                if not str(file_path or "").strip():
                    if configured_legacy_key_counts.get(legacy_key, 0) != 1:
                        continue
                    produced_descriptor = produced_descriptors_by_legacy_key.get(legacy_key)
                    if produced_descriptor is not None:
                        file_path = str(produced_descriptor.get("file_path", "") or "")
                        descriptor = _latest_output_descriptor(
                            project,
                            group_name,
                            map_type,
                            file_path,
                            output_suffix=effective_suffix,
                            map_uuid=map_uuid,
                            effective_map_type=row_effective_type,
                        )
                    else:
                        file_path = existing_paths_by_legacy_key.get(legacy_key)
                        if not str(file_path or "").strip():
                            continue
                        if not _carried_path_is_current(file_path):
                            continue
                        descriptor = _latest_output_descriptor(
                            project,
                            group_name,
                            map_type,
                            file_path,
                            output_suffix=effective_suffix,
                            map_uuid=map_uuid,
                            effective_map_type=row_effective_type,
                        )
                else:
                    descriptor = _latest_output_descriptor(
                        project,
                        group_name,
                        map_type,
                        file_path,
                        output_suffix=effective_suffix,
                        map_uuid=map_uuid,
                        # A pre-unification entry recorded no effective type; the
                        # live row is the authority, so re-derive rather than
                        # carrying the blank forward.
                        effective_map_type=existing_effective or row_effective_type,
                    )
            if not str(file_path or "").strip():
                continue
            if file_path in seen_paths:
                continue
            descriptors.append(descriptor)
            seen_paths.add(file_path)
            seen_keys.add(key)
            seen_legacy_keys.add(legacy_key)

    for key, (file_path, existing_effective) in existing_paths.items():
        legacy_key = _produced_file_legacy_key(key[0], key[1], key[2])
        if key in seen_keys or file_path in seen_paths:
            continue
        if legacy_key in seen_legacy_keys:
            continue
        if file_path in produced_descriptors_by_path:
            continue
        if key[0] and key[0] not in current_group_names:
            continue
        # An entry pointing outside the directory this bake wrote into belongs to a
        # superseded output root (the project's output directory changed, or a preset
        # moved it). Without this the Outputs list accumulated every map the project had
        # ever baked across every directory it had ever used and presented all of it as
        # current -- a 3-group / 2-map project showed 33 rows spanning two directories.
        if not _carried_path_is_current(file_path):
            continue
        descriptors.append(
            _latest_output_descriptor(
                project, key[0], key[1], file_path,
                output_suffix=key[2], map_uuid=key[3], effective_map_type=existing_effective))
        seen_paths.add(file_path)
        seen_legacy_keys.add(legacy_key)

    for path, descriptor in produced_descriptors_by_path.items():
        if path in seen_paths:
            continue
        descriptors.append(descriptor)
        seen_paths.add(path)
        seen_legacy_keys.add(
            _produced_file_legacy_key(
                descriptor["group_name"],
                descriptor["map_type"],
                descriptor.get("output_suffix", ""),
            )
        )
    return descriptors


def _descriptor_from_produced_file(
    project,
    group_name: str,
    effective_map_type: str,
    file_path: str,
    *,
    map_uuid: str = "",
) -> dict:
    """Build a latest_output descriptor from a produced file, translating effective backend
    map_types (e.g. ``CURVATURE_DIRECTION``) back to the raw map stack type (``CURVATURE``) and
    the correct output_suffix.  This keeps ``latest_outputs`` consistent with the map stack so
    that the Outputs panel, open/preview buttons, and partial-bake merging all work correctly."""
    normalized_map_uuid = str(map_uuid or "").strip()
    if normalized_map_uuid:
        map_setting = properties.find_map_setting_by_uuid(project, normalized_map_uuid)
        if map_setting is not None:
            raw_type = str(getattr(map_setting, "map_type", "") or "").strip()
            effective_suffix = properties.effective_map_output_suffix(project, map_setting) or ""
            return _latest_output_descriptor(
                project,
                group_name,
                raw_type or effective_map_type,
                file_path,
                output_suffix=effective_suffix,
                map_uuid=normalized_map_uuid,
                effective_map_type=effective_map_type,
            )
        return _latest_output_descriptor(
            project,
            group_name,
            effective_map_type,
            file_path,
            map_uuid=normalized_map_uuid,
            effective_map_type=effective_map_type,
        )

    from pathlib import Path as _Path
    # See _infer_output_suffix: strip the .NNNN tile before matching untiled stems.
    file_stem, _file_udim_tile = (
        naming.split_udim_tile_suffix(_Path(file_path).stem) if file_path else ("", None)
    )
    normalized = str(effective_map_type or "").strip().upper()
    texture_set_name = _group_texture_set_name(project, group_name)
    for ms in getattr(project, "maps", []):
        if getattr(ms, "is_add_phantom", False):
            continue
        if _effective_map_type_for_setting(ms).upper() != normalized:
            continue
        raw_type = str(getattr(ms, "map_type", "") or "").strip()
        effective_type = _effective_map_type_for_setting(ms)
        effective_suffix = properties.effective_map_output_suffix(project, ms)
        if file_stem:
            expected_stem = naming.build_output_stem(
                group_name=group_name,
                map_type=effective_type,
                texture_set_name=texture_set_name,
                map_label_override=effective_suffix,
                project_name=str(getattr(project, "name", "") or ""),
            )
            if file_stem != expected_stem:
                continue
        return _latest_output_descriptor(
            project, group_name, raw_type, file_path,
            output_suffix=effective_suffix or "", effective_map_type=effective_map_type)
    # No map setting matched — fall back to storing the effective type as-is.
    return _latest_output_descriptor(
        project, group_name, effective_map_type, file_path, effective_map_type=effective_map_type)


def _current_output_file_name(project, group_name: str, map_setting) -> str:
    """The file name the CURRENT project settings would write for this group x map row.

    Same naming pipeline as _build_output_targets / _heal_missing_outputs_from_disk, so
    "matches current naming" here means "is the file this project writes today"."""
    try:
        return naming.build_output_file_name(
            group_name=group_name,
            map_type=_effective_map_type_for_setting(map_setting),
            bit_depth=str(getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8),
            image_format=str(getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT),
            texture_set_name=_group_texture_set_name(project, group_name),
            map_label_override=properties.effective_map_output_suffix(project, map_setting),
            project_name=str(getattr(project, "name", "") or ""),
        )
    except (ValueError, TypeError):
        return ""


def _output_descriptor_identity(file_path: str) -> tuple[str, str]:
    """``(stem without its UDIM tile, extension)`` of one tracked output path, casefolded."""
    if not file_path:
        return ("", "")
    path = Path(file_path)
    stem, _tile = naming.split_udim_tile_suffix(path.stem)
    return (stem.casefold(), path.suffix.casefold())


def _prune_superseded_output_descriptors(project, descriptors: list[dict]) -> list[dict]:
    """Drop tracked outputs a rename or format switch superseded.

    One (map row, bake group) writes exactly one logical output -- UDIM tiles are already
    collapsed into a single descriptor -- so two descriptors sharing ``map_uuid`` +
    ``group_name`` mean the old file name is still being tracked next to the new one
    (change ``output_suffix`` or ``image_format`` and re-bake). The survivor is the one
    matching what the CURRENT settings name; if none of them does, nothing is pruned --
    a naming pipeline we cannot reproduce must never cost the user a tracked output.
    Entries without a ``map_uuid``, and other groups/maps, are untouched."""
    buckets: dict[tuple[str, str], list[int]] = {}
    for index, descriptor in enumerate(descriptors):
        map_uuid = str(descriptor.get("map_uuid", "") or "").strip()
        if not map_uuid:
            continue
        buckets.setdefault((map_uuid, str(descriptor.get("group_name", "") or "")), []).append(index)

    superseded: set[int] = set()
    resolving_type_keys: set[tuple[str, str]] = set()
    orphan_indices: list[int] = []
    for (map_uuid, group_name), indices in buckets.items():
        map_setting = properties.find_map_setting_by_uuid(project, map_uuid)
        if map_setting is None:
            # Rows recreated with fresh uuids (e.g. a project-preset load rebuilds the
            # map stack) orphan their old entries; collect them for the sibling pass.
            orphan_indices.extend(indices)
            continue
        for index in indices:
            resolving_type_keys.add(
                (
                    str(descriptors[index].get("group_name", "") or ""),
                    str(descriptors[index].get("map_type", "") or ""),
                )
            )
        if len(indices) < 2:
            continue
        expected = _output_descriptor_identity(_current_output_file_name(project, group_name, map_setting))
        if expected == ("", ""):
            continue
        matching = [
            index
            for index in indices
            if _output_descriptor_identity(str(descriptors[index].get("file_path", "") or "")) == expected
        ]
        if not matching:
            continue
        keep = matching[-1]
        superseded.update(index for index in indices if index != keep)

    # Orphan-uuid entries are stale history once a LIVE row tracks an output for the
    # same (group, map type). Without a live sibling they stay: a removed map row's
    # last output remains restorable, and nothing is pruned on mere suspicion.
    for index in orphan_indices:
        type_key = (
            str(descriptors[index].get("group_name", "") or ""),
            str(descriptors[index].get("map_type", "") or ""),
        )
        if type_key in resolving_type_keys:
            superseded.add(index)

    if not superseded:
        return descriptors
    return [descriptor for index, descriptor in enumerate(descriptors) if index not in superseded]


def _unproduced_map_types_after_failure(project, progress) -> frozenset[str]:
    """Map types this bake ATTEMPTED, when the bake did not finish cleanly.

    Empty for a successful bake, so healing keeps working exactly as it always has. After
    a failure the attempted rows are the ones whose files on disk are now known-stale: the
    bake set out to replace them and did not. Group x map granularity comes for free --
    combinations that DID succeed are already in ``descriptors`` and healing skips those.
    """
    errors = list(getattr(progress, "errors", None) or [])
    status = str(getattr(progress, "status", "") or "").strip()
    failed_statuses = {constants.STATUS_FAILED, constants.STATUS_CANCELLED, constants.STATUS_CANCELLING}
    if not errors and status not in failed_statuses:
        return frozenset()

    from . import map_rebuild

    attempted = {
        str(map_type or "").strip().upper()
        for map_type in map_rebuild.active_bake_map_types(project)
    }
    attempted.discard("")
    if not attempted:
        # No recorded selection (a full bake does not always narrow one): every enabled
        # row was attempted.
        attempted = {
            str(getattr(map_setting, "map_type", "") or "").strip().upper()
            for map_setting in getattr(project, "maps", [])
            if bool(getattr(map_setting, "enabled", False))
            and not getattr(map_setting, "is_add_phantom", False)
        }
        attempted.discard("")
    return frozenset(attempted)


def _heal_missing_outputs_from_disk(
    project, descriptors: list[dict], *, failed_map_types: frozenset[str] | None = None
) -> None:
    """Re-adopt previously-baked outputs that still exist on disk.

    ``latest_outputs`` is a session/file artifact: after opening a .blend whose
    saved list is empty or stale, a SUBSET bake (e.g. just AO) used to leave
    every other map "unavailable" in the UI (no Show on Low) even though its
    output file sits untouched in the output directory. After computing the
    produced/merged descriptors, probe the EXPECTED output path (same naming as
    build_group_output_targets) for every configured group x map that is still
    missing, and adopt the file if it exists. Appends to ``descriptors``.
    """
    output_dir_text = str(getattr(project, "last_output_dir", "") or "").strip()
    if not output_dir_text:
        return
    output_dir = Path(output_dir_text)
    if not output_dir.is_dir():
        return
    # Keyed on the EFFECTIVE type because that is what the probe below resolves a
    # file name from. Descriptors record the raw stack type in ``map_type``, so a
    # MATERIAL row already tracked as ("MATERIAL", "MATERIAL_ALBEDO") must not be
    # re-adopted a second time under its effective name.
    seen_keys = {
        (
            str(d.get("group_name", "") or ""),
            (str(d.get("effective_map_type", "") or "") or str(d.get("map_type", "") or "")).upper(),
            str(d.get("output_suffix", "") or ""),
        )
        for d in descriptors
    }
    bit_depth = str(getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8)
    image_format = str(getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT) or constants.DEFAULT_IMAGE_FORMAT)
    from . import udim as _udim_listing

    # One listing of the output directory answers every "is this file there" probe below.
    # A many-group bake used to stat (and, for each missing file, re-scan the whole listing
    # for UDIM tiles) groups x rows candidates on every progress pass, almost all of them
    # for outputs that had not been produced yet.
    listed_names = tuple(_udim_listing.directory_file_names(str(output_dir / "_")))
    fold_names = os.name == "nt"
    present_names = {name.casefold() if fold_names else name for name in listed_names}
    tile_names_by_stem: dict[tuple[str, str], list[str]] = {}
    for listed in listed_names:
        stem_part, dot, extension = listed.rpartition(".")
        base, tile_dot, middle = stem_part.rpartition(".")
        if dot and tile_dot and middle.isdigit():
            tile_names_by_stem.setdefault((base, "." + extension), []).append(listed)
    # Enabled-row data that does not depend on the group, resolved once.
    heal_rows: list[tuple] = []
    for map_setting in getattr(project, "maps", []):
        if getattr(map_setting, "is_add_phantom", False):
            continue
        # Only ENABLED rows may be healed. A disabled row's file on disk is a
        # leftover from an earlier session (or another project sharing the output
        # directory); adopting it made export_textures ship a stale map the artist
        # had explicitly switched off.
        if not bool(getattr(map_setting, "enabled", False)):
            continue
        map_type = str(getattr(map_setting, "map_type", "") or "").strip()
        if not map_type:
            continue
        heal_rows.append(
            (
                map_setting,
                map_type,
                _effective_map_type_for_setting(map_setting),
                properties.effective_map_output_suffix(project, map_setting),
            )
        )
    for group in getattr(project, "groups", []):
        group_name = str(getattr(group, "name", "") or "").strip()
        if not group_name:
            continue
        metadata_state = properties.group_metadata_state(group)
        # Resolve the set's name_mode (Custom/.blend/Material) to the output token, matching
        # _build_output_targets. Using the raw key here searched the wrong filename for
        # non-Custom modes (e.g. "Based on .blend File"), so on-disk outputs were never
        # re-adopted after reopening the .blend.
        _set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip()
        texture_set_name = properties.resolve_texture_set_output_name(project, _set_key) if _set_key else None
        for map_setting, map_type, effective_map_type, map_label_override in heal_rows:
            # A map this bake TRIED and failed to produce must not be healed from disk.
            # The file sitting there is the output of an earlier, successful run; adopting
            # it presents a bake that just errored as if it had produced current maps, and
            # export_textures then treats those stale files as available and ships them.
            if failed_map_types and map_type.upper() in failed_map_types:
                continue
            key = (group_name, effective_map_type.upper(), map_label_override or "")
            if key in seen_keys:
                continue
            file_name = naming.build_output_file_name(
                group_name=group_name,
                map_type=effective_map_type,
                bit_depth=bit_depth,
                image_format=image_format,
                texture_set_name=texture_set_name,
                map_label_override=map_label_override,
                project_name=str(getattr(project, "name", "") or ""),
            )
            candidate = output_dir / file_name
            listed_tiles = None
            if "/" in file_name or "\\" in file_name:
                # A name with a directory part is not in the flat listing.
                try:
                    candidate_exists = candidate.is_file()
                except OSError:
                    continue
            else:
                candidate_exists = (file_name.casefold() if fold_names else file_name) in present_names
                if not candidate_exists and not fold_names:
                    # A case-sensitive listing may sit on a case-insensitive filesystem
                    # (macOS): a miss is only trusted after the real probe.
                    try:
                        candidate_exists = candidate.is_file()
                    except OSError:
                        continue
                if not candidate_exists:
                    stem_text, name_dot, extension_text = file_name.rpartition(".")
                    if name_dot:
                        listed_tiles = tile_names_by_stem.get((stem_text, "." + extension_text), ())
            udim_tiles: list[tuple[int, str]] = []
            if not candidate_exists:
                # No untiled file, so this map may have been baked with tokenized naming.
                # Probing the <UDIM> form here is what stops a multi-tile project from
                # showing every map as unavailable after the .blend is reopened.
                udim_tiles = _udim_tiles_on_disk(candidate, directory_names=listed_tiles)
                if not udim_tiles:
                    continue
            seen_keys.add(key)
            # Store the RAW stack type with the effective type alongside it, exactly
            # as bake ingestion does. Healed entries used to record the effective
            # type as ``map_type`` with a blank effective field, which left the
            # Outputs panel unable to match the row that owns the file.
            descriptor = _latest_output_descriptor(
                project,
                group_name,
                map_type,
                str(udim_tiles[0][1]) if udim_tiles else str(candidate),
                output_suffix=map_label_override or "",
                map_uuid=properties.ensure_map_setting_uuid(map_setting),
                effective_map_type=effective_map_type,
            )
            if udim_tiles:
                from . import udim as _udim

                descriptor["udim_logical_path"] = _udim.logical_udim_path(str(udim_tiles[0][1]))
                descriptor["udim_tiles"] = [
                    _udim_tile_record(tile_number, tile_path, stale=False)
                    for tile_number, tile_path in udim_tiles
                ]
            descriptors.append(descriptor)


def _udim_tiles_on_disk(untiled_candidate, *, directory_names=None) -> list[tuple[int, str]]:
    """Tile files on disk for an output whose untiled filename is ``untiled_candidate``.

    ``Asset_Normal.png`` -> the concrete files behind ``Asset_Normal.<UDIM>.png``. Every tile
    there is live by definition: nothing here can tell what the current occupancy *should* be,
    so nothing here may call a file stale.
    """
    from . import udim as _udim

    candidate = Path(untiled_candidate)
    logical = str(candidate.with_name(f"{candidate.stem}.{constants.UDIM_PATH_TOKEN}{candidate.suffix}"))
    return _udim.sibling_tile_paths(logical, directory_names=directory_names)


def apply_progress_status_to_project(project, progress: protocol.BakeProgress) -> None:
    """Cheap per-tick progress mirror: status text, percentages and counters only.

    The full apply_progress_to_project pass below re-merges output descriptors,
    heals paths from disk and rebuilds latest_outputs — fine at 1Hz, but the
    background poll runs at up to 20Hz during a bake and that work (plus the
    image refresh / preview-material sync it feeds) competes with the backend
    for the GPU and main thread. This mirror keeps every visible progress
    surface live between heavy passes without touching latest_outputs."""
    project.last_progress_percent = float(progress.percent)
    stage_percent = getattr(progress, "stage_percent", -1.0)
    project.last_stage_progress_percent = float(-1.0 if stage_percent is None else stage_percent)
    project.last_active_group = progress.active_group
    project.last_active_map = progress.active_map
    # Both passes overwrite last_warning_* from a freshly read progress object, so each
    # has to carry the cage-fit warnings or it erases what the other just recorded.
    _merge_cage_fit_warnings(progress)
    project.last_warning_count = len(progress.warnings)
    project.last_error_count = len(progress.errors)
    project.last_warning_summary = progress.warnings[0] if progress.warnings else ""
    project.last_error_summary = progress.errors[0] if progress.errors else ""
    # Humanise every map identifier in the message, not just the active one: a
    # multi-map stage arrives as "Shading Skull / Normal,CURVATURE,BENT_NORMAL" and the
    # old replace(..., 1) fixed only the first token.
    raw_message = naming.humanize_map_tokens(
        naming.relabel_attribute_progress(
            str(progress.message or ""), naming.project_attribute_suffixes(project)
        )
    )
    project.last_status_message = raw_message or progress.status


def apply_progress_to_project(project, progress: protocol.BakeProgress, *, merge_existing: bool = False) -> None:
    # Path normalisation and output-directory listings are memoised for this call only.
    from . import runtime_output_images

    with runtime_output_images.normalized_path_cache(), naming.output_suffix_memo():
        _apply_progress_to_project(project, progress, merge_existing=merge_existing)


def _restore_lighting_output_types(project, produced_files) -> None:
    """Direct / Indirect Lighting rows bake as LIGHTING; name the file by the row's output."""
    for produced in produced_files or ():
        if str(getattr(produced, "map_type", "") or "").strip().upper() != constants.MAP_LIGHTING:
            continue
        row = properties.find_map_setting_by_uuid(project, getattr(produced, "map_uuid", "") or "")
        effective = constants.effective_lighting_map_type(row) if row is not None else None
        if effective in (constants.MAP_DIRECT_LIGHTING, constants.MAP_INDIRECT_LIGHTING, constants.MAP_SPECULAR_LIGHTING):
            produced.map_type = effective


def _apply_progress_to_project(project, progress: protocol.BakeProgress, *, merge_existing: bool = False) -> None:
    _restore_lighting_output_types(project, progress.produced_files)
    # Collapse first, so everything downstream -- merging, healing, de-duplication, the output
    # list itself -- sees one produced file per logical map exactly as it did before UDIM.
    produced_files, udim_tiles_by_path = _collapse_udim_produced_files(
        [
            produced
            for produced in progress.produced_files
            if not _is_source_only_output(getattr(produced, "path", ""))
        ]
    )
    descriptors = (
        _merge_output_descriptors(project, produced_files)
        if merge_existing
        else [
            _descriptor_from_produced_file(
                project,
                getattr(produced, "group_name", ""),
                getattr(produced, "map_type", ""),
                getattr(produced, "path", ""),
                map_uuid=getattr(produced, "map_uuid", ""),
            )
            for produced in produced_files
        ]
    )
    _heal_missing_outputs_from_disk(
        project, descriptors, failed_map_types=_unproduced_map_types_after_failure(project, progress)
    )
    _attach_udim_tiles(descriptors, udim_tiles_by_path)
    # Renames / format switches leave the previous file name tracked alongside the new
    # one; drop it here so both bake ingestion and Refresh Outputs converge.
    descriptors = _prune_superseded_output_descriptors(project, descriptors)

    # The backend keys composite produced-files by texture-set name; the merge expands
    # those into per-group entries. Occasionally one leftover descriptor keyed by the
    # texture-set name (not a real bake group) survives — a redundant duplicate of a
    # group's output (seen for HEIGHT in multi-texture-set bakes). Drop such non-group
    # descriptors only when a real group already covers the same file, so no output is
    # ever lost (a genuinely group-less output is kept).
    _real_group_names = {str(getattr(g, "name", "") or "") for g in getattr(project, "groups", [])}
    _group_covered_paths = {
        d["file_path"]
        for d in descriptors
        if d.get("group_name") in _real_group_names and d.get("file_path")
    }
    descriptors = [
        d
        for d in descriptors
        if (not d.get("group_name"))
        or (d.get("group_name") in _real_group_names)
        or (d.get("file_path") not in _group_covered_paths)
    ]

    properties.reset_latest_outputs(project)
    project.last_progress_percent = float(progress.percent)
    stage_percent = getattr(progress, "stage_percent", -1.0)
    project.last_stage_progress_percent = float(-1.0 if stage_percent is None else stage_percent)
    project.last_active_group = progress.active_group
    project.last_active_map = progress.active_map
    # Both passes overwrite last_warning_* from a freshly read progress object, so each
    # has to carry the cage-fit warnings or it erases what the other just recorded.
    _merge_cage_fit_warnings(progress)
    project.last_warning_count = len(progress.warnings)
    project.last_error_count = len(progress.errors)
    project.last_warning_summary = progress.warnings[0] if progress.warnings else ""
    project.last_error_summary = progress.errors[0] if progress.errors else ""
    for descriptor in descriptors:
        item = project.latest_outputs.add()
        item.map_uuid = descriptor.get("map_uuid", "")
        item.map_type = descriptor["map_type"]
        item.effective_map_type = descriptor.get("effective_map_type", "")
        item.group_name = descriptor["group_name"]
        item.output_suffix = descriptor.get("output_suffix", "")
        item.display_name = descriptor["display_name"]
        item.file_path = descriptor["file_path"]
        # Untiled outputs leave both of these untouched, which is what keeps a single-tile
        # project byte-for-byte the record it always was.
        udim_logical_path = str(descriptor.get("udim_logical_path", "") or "")
        if udim_logical_path:
            item.udim_logical_path = udim_logical_path
            for tile in descriptor.get("udim_tiles", []) or ():
                tile_item = item.udim_tiles.add()
                tile_item.udim_tile = int(tile.get("udim_tile", 0) or 0)
                tile_item.file_path = str(tile.get("file_path", "") or "")
                tile_item.stale = bool(tile.get("stale", False))
                width, height = int(tile.get("width", 0) or 0), int(tile.get("height", 0) or 0)
                tile_item.width = width
                tile_item.height = height

    # Build a human-readable status: replace the raw backend map-type token (e.g.
    # "CURVATURE_DIRECTION") embedded in progress.message with its display label.
    # Humanise every map identifier in the message, not just the active one: a
    # multi-map stage arrives as "Shading Skull / Normal,CURVATURE,BENT_NORMAL" and the
    # old replace(..., 1) fixed only the first token.
    raw_message = naming.humanize_map_tokens(
        naming.relabel_attribute_progress(
            str(progress.message or ""), naming.project_attribute_suffixes(project)
        )
    )
    project.last_status_message = raw_message or progress.status
