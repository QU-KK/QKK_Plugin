"""Blender/Cycles projection fallback for maps the FYR GPU path cannot finish.

When AUTO baking has no GPU runtime, or GPU projection/shading fails mid-bake,
the backend raises an error tagged with ``CYCLES_HANDOFF_MARKERS``. This module
retries supported maps through ``bpy.ops.object.bake`` (selected-to-active when
highs exist). Unsupported maps are reported as errors.

Fidelity note: synthesised maps (pointiness curvature / cavity / thickness) will
not match Fyr's Marmoset-style estimators — that is intentional and acceptable
for recovery. Do not imply parity in UI copy.

This replaces the removed Embree-only recovery route for production AUTO bakes.
"""

from __future__ import annotations

import math
import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import low_material_subset, rna_buffers
from . import (
    blender_bake,
    constants,
    cycles_memory,
    floater_faces,
    id_material_color,
    image_cleanup,
    mesh_transport,
)


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class CyclesMapStrategy:
    """How to produce one map type through Cycles."""

    bake_type: str
    # native | emit | derived — emit installs a temporary Emission network on shading
    # materials; derived runs several passes and composes the result in NumPy.
    mode: str = "native"
    normal_space: str | None = None
    emit_kind: str | None = None
    requires_highs: bool = True
    approximate: bool = False
    note: str = ""
    # Cycles bake passes one step of this map costs. Only used for honest progress
    # labels — the derived maps are several bakes deep and should say so.
    passes: int = 1


# World-space axes used to reconstruct the bent normal.  The AO node samples the
# hemisphere around whatever vector is wired into its Normal input, so baking
# visibility around six fixed axes samples the visibility function in six wide
# lobes; the bent normal is its first-order direction, recovered as the
# visibility-weighted sum of the probe axes.  Opposite pairs cancel in proportion
# to how much more open one side is than the other, which is the whole trick.
_BENT_NORMAL_PROBE_DIRECTIONS: tuple[tuple[float, float, float], ...] = (
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
)


# Thickness on Cycles mirrors Fyr's estimator (estimate_thickness in
# projection_shading.slang): the hits-only mean chord of inward rays traced to
# 0.625x the encode range, encoded (1 - mean/range)^2 with the map's Scale and
# Gamma on top. Cycles cannot return a hit distance, but an inside AO node with
# Distance x returns U(x) = P(chord > x), and
#     E[chord | min < chord <= R] = min + integral_min^R (U(x) - U(R)) dx / (U(min) - U(R))
# so U at a few distances recovers the same mean. Every U is a plain visibility
# fraction, which averages linearly over samples, so it is baked raw into float
# channels and the nonlinear part runs once in NumPy afterwards.
THICKNESS_AUTO_RANGE_DIAGONAL = 0.26  # auto_thickness_max_distance
THICKNESS_TRACE_REACH = 0.625  # trace_reach = 0.625 * max_distance
THICKNESS_QUADRATURE_POINTS = 4
#: (min_distance, scale, gamma) of the map's thickness encode; min <= 0 is Auto (0).
DEFAULT_THICKNESS_ENCODE: tuple = (0.0, 1.0, 1.0)


# Every map type the Cycles path can produce. Bucket A+B recovery maps, plus the
# derived ones: Height, Bent Normal, Curvature Direction, Thickness.
_CYCLES_MAP_STRATEGIES: dict[str, CyclesMapStrategy] = {
    constants.MAP_NORMAL: CyclesMapStrategy("NORMAL", normal_space="TANGENT"),
    # A Derivative row's hidden source: an OpenGL tangent normal that
    # derived_outputs converts to slopes after the bake.
    constants.MAP_DERIVATIVE: CyclesMapStrategy("NORMAL", normal_space="TANGENT"),
    constants.MAP_OBJECT_NORMAL: CyclesMapStrategy("NORMAL", normal_space="OBJECT"),
    # Blender 5.1+ bake accepts only OBJECT and TANGENT. WORLD is converted after
    # an OBJECT-space pass, the same way POSITION is converted from world to object.
    constants.MAP_WORLD_NORMAL: CyclesMapStrategy(
        "NORMAL",
        normal_space="OBJECT",
        note="Cycles OBJECT-space normal converted to world space",
    ),
    constants.MAP_AO: CyclesMapStrategy("AO"),
    constants.MAP_POSITION: CyclesMapStrategy(
        "POSITION",
        note="Cycles world-space position converted to object space",
    ),
    constants.MAP_ENV_LIGHT: CyclesMapStrategy("ENVIRONMENT", requires_highs=False),
    constants.MAP_SCENE_LIGHTING: CyclesMapStrategy("COMBINED", requires_highs=False),
    constants.MAP_LIGHTING: CyclesMapStrategy(
        "DIFFUSE",
        requires_highs=False,
        approximate=True,
        note="Cycles DIFFUSE irradiance stand-in for legacy LIGHTING rows",
    ),
    constants.MAP_LIT_COLOR: CyclesMapStrategy(
        "COMBINED",
        requires_highs=False,
        approximate=True,
        note="Cycles COMBINED stand-in for legacy LIT_COLOR rows",
    ),
    # Direct / Indirect Lighting outputs travel as LIGHTING with lighting_component set;
    # the plan maps them back so the DIFFUSE pass bakes only that part.
    constants.MAP_DIRECT_LIGHTING: CyclesMapStrategy(
        "DIFFUSE",
        requires_highs=False,
        approximate=True,
        note="Cycles DIFFUSE direct-light stand-in for Direct Lighting rows",
    ),
    constants.MAP_INDIRECT_LIGHTING: CyclesMapStrategy(
        "DIFFUSE",
        requires_highs=False,
        approximate=True,
        note="Cycles DIFFUSE indirect-light stand-in for Indirect Lighting rows",
    ),
    constants.MAP_SPECULAR_LIGHTING: CyclesMapStrategy(
        "GLOSSY",
        requires_highs=False,
        approximate=True,
        note="Cycles GLOSSY stand-in for Specular Lighting rows",
    ),
    constants.MAP_OPACITY: CyclesMapStrategy(
        "EMIT", mode="emit", emit_kind="opacity", requires_highs=True
    ),
    constants.MAP_VERTEX_COLOR: CyclesMapStrategy(
        "EMIT", mode="emit", emit_kind="vertex_color", requires_highs=True
    ),
    constants.MAP_ATTRIBUTE: CyclesMapStrategy(
        "EMIT", mode="emit", emit_kind="attribute", requires_highs=True
    ),
    constants.MAP_ID: CyclesMapStrategy(
        "EMIT", mode="emit", emit_kind="material_id", requires_highs=True
    ),
    constants.MAP_CURVATURE: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="pointiness",
        requires_highs=True,
        approximate=True,
        note="Cycles pointiness; not Fyr Marmoset-method curvature",
    ),
    constants.MAP_PRINCIPAL_CURVATURE: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="pointiness",
        requires_highs=True,
        approximate=True,
        note="Cycles pointiness stand-in for Principal Curvature",
    ),
    constants.MAP_CAVITY: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="cavity",
        requires_highs=True,
        approximate=True,
        note="Cycles pointiness concave mask",
    ),
    constants.MAP_CONCAVE: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="concave",
        requires_highs=True,
        approximate=True,
        note="Cycles pointiness concave half",
    ),
    constants.MAP_CONVEX: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="convex",
        requires_highs=True,
        approximate=True,
        note="Cycles pointiness convex half",
    ),
    constants.MAP_THICKNESS: CyclesMapStrategy(
        "EMIT",
        mode="derived",
        emit_kind="thickness",
        requires_highs=True,
        approximate=True,
        note="Fyr thickness mean chord from inside-AO visibility",
        passes=2,
    ),
    constants.MAP_HEIGHT: CyclesMapStrategy(
        "POSITION",
        mode="derived",
        emit_kind="height",
        requires_highs=True,
        approximate=True,
        note="Height from high−low position along low normal",
        passes=3,
    ),
    constants.MAP_DENSITY: CyclesMapStrategy(
        "EMIT",
        mode="emit",
        emit_kind="density",
        requires_highs=True,
        approximate=True,
        note="Cycles inward+outward AO occupancy probe",
    ),
    constants.MAP_BENT_NORMAL: CyclesMapStrategy(
        "EMIT",
        mode="derived",
        emit_kind="bent_normal",
        requires_highs=True,
        approximate=True,
        note="Bent normal reconstructed from 6 directional visibility probes",
        passes=len(_BENT_NORMAL_PROBE_DIRECTIONS),
    ),
    constants.MAP_CURVATURE_DIRECTION: CyclesMapStrategy(
        "NORMAL",
        mode="derived",
        normal_space="TANGENT",
        emit_kind="curvature_direction",
        requires_highs=True,
        approximate=True,
        note="Major curvature axis from the baked tangent-space normal field",
    ),
}

# Nothing is categorically unsupported any more; this stays for map types that are
# simply not part of the projection set (material channels have their own path).
_UNSUPPORTED_REASON: dict[str, str] = {}


def is_cycles_handoff_error(text: str | None) -> bool:
    message = str(text or "")
    return any(marker in message for marker in constants.CYCLES_HANDOFF_MARKERS)


def _progress_texts(progress) -> list[str]:
    candidates: list[str] = []
    message = getattr(progress, "message", None)
    if message:
        candidates.append(str(message))
    for collection_name in ("errors", "warnings"):
        values = getattr(progress, collection_name, None) or []
        candidates.extend(str(value) for value in values)
    return candidates


def prepared_high_triangle_total(prepared, *, object_lookup=None) -> int:
    """Triangles across every high mesh the prepared job references, from Blender's
    own tessellation. ``object_lookup(name)`` defaults to the evaluated object from
    ``bpy.data.objects``; unknown objects count as zero, so a stale reference never
    blocks anything."""
    if object_lookup is None:
        try:
            import bpy  # noqa: PLC0415

            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:  # noqa: BLE001 - outside Blender there is nothing to count
            return 0

        def object_lookup(name):
            # The modifier-EVALUATED mesh: a 1 M base under Multires / Subdivision bakes
            # as the 64 M the stack produces, and that is what Cycles would chew on.
            obj = bpy.data.objects.get(name)
            if obj is None:
                return None
            try:
                return obj.evaluated_get(depsgraph)
            except Exception:  # noqa: BLE001 - fall back to the base mesh
                return obj
    job = getattr(prepared, "job", prepared)
    seen: set[str] = set()
    total = 0
    for group in getattr(job, "groups", None) or ():
        for ref in getattr(group, "high_meshes", None) or ():
            name = str(getattr(ref, "object_name", "") or getattr(ref, "name", "") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                obj = object_lookup(name)
                mesh = getattr(obj, "data", None)
                triangles = getattr(mesh, "loop_triangles", None)
                if triangles is not None:
                    total += int(len(triangles))
                    continue
                polygons = getattr(mesh, "polygons", None)
                if polygons is not None:
                    total += int(len(polygons)) * 2
            except Exception:  # noqa: BLE001 - counting must never fail a bake
                continue
    return total


def estimate_cycles_recovery_cost(prepared, *, map_types=None) -> tuple[int, int, int, float]:
    """(groups, maps, passes, seconds) the automatic Cycles retry of this job would cost.

    Walks the job's output targets: one entry per (group, map[, UDIM tile]) that Cycles
    can produce, honouring ``map_types`` when the bake was a partial one. ``passes``
    sums each map's own Cycles pass count (a bent normal is six), ``seconds`` is
    passes x CYCLES_AUTO_RECOVERY_SECONDS_PER_PASS. Needs no Blender objects.
    """
    requested = None
    if map_types is not None:
        requested = {str(value).strip().upper() for value in map_types if str(value or "").strip()}
    job = getattr(prepared, "job", prepared)
    groups = 0
    maps = 0
    passes = 0
    for group in getattr(job, "groups", None) or ():
        if bool(getattr(group, "occluder_only", False)):
            continue
        group_maps = 0
        for target in getattr(group, "outputs", None) or ():
            map_type = str(getattr(target, "map_type", "") or "").strip().upper()
            if requested is not None and map_type not in requested:
                continue
            strategy = cycles_map_strategy(map_type)
            if strategy is None:
                continue
            group_maps += 1
            passes += max(1, int(getattr(strategy, "passes", 1) or 1))
        if group_maps:
            groups += 1
            maps += group_maps
    seconds = float(passes) * float(constants.CYCLES_AUTO_RECOVERY_SECONDS_PER_PASS)
    return groups, maps, passes, seconds


def _format_duration(seconds: float) -> str:
    minutes = int(round(seconds / 60.0))
    if minutes < 90:
        return f"{max(1, minutes)} min"
    return f"{seconds / 3600.0:.1f} h"


def auto_recovery_cost_blocked_reason(prepared, *, map_types=None) -> str:
    """Why the automatic Cycles retry is too expensive to run unattended, or "".

    groups x maps x seconds-per-pass above CYCLES_AUTO_RECOVERY_MAX_SECONDS. Small
    bakes keep recovering through Cycles on their own.
    """
    groups, maps, passes, seconds = estimate_cycles_recovery_cost(prepared, map_types=map_types)
    if seconds <= float(constants.CYCLES_AUTO_RECOVERY_MAX_SECONDS):
        return ""
    return (
        f"The GPU bake failed and Fyr could not recover it on the GPU. Recovering {maps} maps across "
        f"{groups} bake groups through Blender Cycles would take about {_format_duration(seconds)} "
        f"({passes} Cycles passes), so the automatic Cycles retry was not started. "
        "Run the bake again (a restart of the GPU usually clears this), bake fewer groups at a time, "
        "or set the Bake Renderer to Cycles to bake it that way on purpose."
    )


def auto_recovery_blocked_reason(progress, prepared, *, object_lookup=None, map_types=None) -> str:
    """Why the AUTOMATIC Cycles retry must not run for this failed bake, or "".

    Two triggers, both about scenes Cycles would bake on the main thread for hours:
    the backend said the group is too large for hardware RT (GPU_GROUP_TOO_LARGE),
    or the job's high-poly meshes exceed CYCLES_AUTO_RECOVERY_MAX_TRIANGLES. The
    text is written for the artist and names what to change.
    """
    if not progress_requests_cycles_handoff(progress):
        return ""
    limit = int(constants.CYCLES_AUTO_RECOVERY_MAX_TRIANGLES)
    too_large_text = next(
        (text for text in _progress_texts(progress) if constants.GPU_GROUP_TOO_LARGE_MARKER in text),
        "",
    )
    total = prepared_high_triangle_total(prepared, object_lookup=object_lookup)
    size_blocked = bool(too_large_text) or total > limit
    scene_bytes = prepared_scene_bytes(prepared, object_lookup=object_lookup)
    memory = cycles_memory.scene_exceeds_memory(scene_bytes)
    if not size_blocked and memory is None:
        return auto_recovery_cost_blocked_reason(prepared, map_types=map_types)
    parts = []
    if too_large_text:
        marker_index = too_large_text.find(constants.GPU_GROUP_TOO_LARGE_MARKER)
        detail = too_large_text[marker_index + len(constants.GPU_GROUP_TOO_LARGE_MARKER):].lstrip(": ")
        detail = detail.split("). Addon should retry")[0].rstrip(")").rstrip(".")
        parts.append(detail + ".")
    elif size_blocked:
        parts.append(
            f"the GPU bake failed and the job's high-poly meshes total {total:,} triangles"
        )
    if memory is not None:
        parts.append(
            f"Cycles would need about {cycles_memory.format_gb(scene_bytes)} of memory just to load"
            f" this job's meshes and textures, but only {cycles_memory.format_gb(memory.available)}"
            " is free."
        )
    if size_blocked:
        parts.append(
            "The automatic Cycles retry was not started: on a scene this size it would bake one map"
            " at a time on Blender's main thread for a very long time with no way to cancel."
            " Split the bake group into smaller groups (one per part), reduce the high-poly meshes,"
            " or set the Bake Renderer to Cycles to bake it that way on purpose."
        )
    else:
        parts.append(
            "The automatic Cycles retry was not started because Blender would run out of memory."
            " Close other applications, split the bake group into smaller groups (one per part),"
            " or reduce the high-poly meshes."
        )
    return " ".join(parts)


def prepared_scene_bytes(prepared, *, object_lookup=None) -> int:
    """cycles_memory.estimate_scene_bytes over every low and high the prepared job names.

    Uses the same ``object_lookup`` contract as :func:`prepared_high_triangle_total`
    (evaluated objects by default), so the estimate counts the modifier result.
    """
    if object_lookup is None:
        try:
            import bpy  # noqa: PLC0415

            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:  # noqa: BLE001 - outside Blender there is nothing to estimate
            return 0

        def object_lookup(name):
            obj = bpy.data.objects.get(name)
            if obj is None:
                return None
            try:
                return obj.evaluated_get(depsgraph)
            except Exception:  # noqa: BLE001
                return obj
    job = getattr(prepared, "job", prepared)
    highs: list = []
    lows: list = []
    for group in getattr(job, "groups", None) or ():
        for attr, bucket in (("high_meshes", highs), ("low_meshes", lows)):
            for ref in getattr(group, attr, None) or ():
                name = str(getattr(ref, "object_name", "") or getattr(ref, "name", "") or "")
                if not name:
                    continue
                try:
                    obj = object_lookup(name)
                except Exception:  # noqa: BLE001
                    obj = None
                if obj is not None:
                    bucket.append(obj)
    try:
        # The looked-up objects are already evaluated: no depsgraph lookup on top.
        return cycles_memory.estimate_scene_bytes(highs, lows, evaluated=True)
    except Exception:  # noqa: BLE001 - an estimate must never block on its own failure
        return 0


def progress_requests_cycles_handoff(progress) -> bool:
    if progress is None:
        return False
    candidates = []
    message = getattr(progress, "message", None)
    if message:
        candidates.append(str(message))
    for collection_name in ("errors", "warnings"):
        values = getattr(progress, collection_name, None) or []
        candidates.extend(str(value) for value in values)
    return any(is_cycles_handoff_error(value) for value in candidates)


def cycles_map_strategy(map_type: str) -> CyclesMapStrategy | None:
    return _CYCLES_MAP_STRATEGIES.get(str(map_type or "").strip().upper())


def cycles_bake_type_for_map(map_type: str) -> str | None:
    strategy = cycles_map_strategy(map_type)
    return None if strategy is None else strategy.bake_type


def unsupported_cycles_reason(map_type: str) -> str:
    normalized = str(map_type or "").strip().upper()
    if normalized in _UNSUPPORTED_REASON:
        return _UNSUPPORTED_REASON[normalized]
    if normalized.startswith("MATERIAL"):
        return "Material channels already use the dedicated Cycles material path"
    return f"Map type '{normalized}' is not supported by the Cycles fallback"


def _resolve_objects(names) -> tuple[list, list[str]]:
    import bpy

    objects = []
    missing = []
    for name in names or []:
        obj = bpy.data.objects.get(name)
        if obj is None:
            missing.append(str(name))
        else:
            objects.append(obj)
    return objects, missing


def _group_cage_object_name(group) -> str:
    """The scene object behind a CUSTOM cage ref, or "" (Automatic cages are files)."""
    for ref in getattr(group, "cage_meshes", []) or []:
        name = str(getattr(ref, "object_name", "") or getattr(ref, "name", "") or "").strip()
        if not name:
            continue
        found, _missing = _resolve_objects([name])
        if found and getattr(found[0], "type", "MESH") == "MESH":
            return name
    return ""


def _group_cage_extrusion(group) -> float:
    for attr in ("cage_extrusion", "cage_offset", "ray_distance"):
        value = getattr(group, attr, None)
        if value is not None:
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                pass
    return 0.0


#: Object name the export gives each low's fitted cage (export._export_group_cage_meshes).
_AUTO_CAGE_SUFFIX = "_auto_cage"
#: Floats per triangle corner in the soup layouts a fitted cage is written in.
_CAGE_CORNER_FLOATS = {
    mesh_transport.MBMESH_MAGIC_V1: 8,
    mesh_transport.MBMESH_MAGIC_V2: 11,
    mesh_transport.MBMESH_MAGIC_V3: 13,
}


@dataclass(frozen=True)
class FittedCage:
    """An exported Automatic cage, as one LOCAL position per corner of its low.

    Blender's bake cannot read Fyr's cage file, and without it the Cycles route traced
    from the hidden Distance offset (0.02 by default): every high detail standing
    further out than that, a floating bolt or a deep bevel, was missed, so the Normal
    map came back flat and AO found the plate under a bolt instead of the bolt.
    """

    low_name: str
    #: ``(len(mesh.loops), 3)`` float32, indexed like the evaluated low's corners.
    corner_positions: object
    #: Largest world distance any corner moved: the uniform fallback and Height range.
    max_offset: float


def _mesh_ref_file(path: str) -> Path:
    """The on-disk file of a mesh ref (a shared-memory ref always keeps a file fallback)."""
    text = str(path or "")
    if "|fallback=" in text:
        text = text.split("|fallback=", 1)[1]
    return Path(text)


def _read_cage_corner_positions(path):
    """World positions of every triangle corner of a soup-layout cage file, ``(3 * T, 3)``."""
    import numpy as np

    source = _mesh_ref_file(path)
    raw = source.read_bytes()
    header = mesh_transport._HEADER  # noqa: SLF001 - the one definition of the layout
    if len(raw) < header.size:
        raise ValueError(f"cage file header is incomplete: {source.name}")
    magic, triangle_count, _reserved = header.unpack_from(raw, 0)
    floats = _CAGE_CORNER_FLOATS.get(magic)
    if floats is None:
        raise ValueError(f"cage file layout {magic!r} is not a triangle soup: {source.name}")
    corners = int(triangle_count) * 3
    if len(raw) != header.size + corners * floats * 4:
        raise ValueError(f"cage file size does not match its header: {source.name}")
    payload = np.frombuffer(raw, dtype="<f4", offset=header.size).reshape(corners, floats)
    return np.array(payload[:, :3], dtype=np.float64)


def _fitted_cage_for_low(low, world_corners) -> FittedCage | None:
    """Map a cage file's triangle corners onto ``low``'s face corners, traced as Fyr traces.

    The export captured the cage from the evaluated low's ``loop_triangles`` in order
    (cage.capture_cage_source_triangles), so triangle ``t`` corner ``k`` belongs to
    loop ``loop_triangles[t].loops[k]``. None when the low no longer tessellates to
    that many triangles.

    Fyr uses the cage only for how far out a ray starts and aims it along the low's
    interpolated vertex normal (projection_hits.slang). Blender aims from the
    interpolated cage point at the low point, so a face whose corners reach very
    different distances bent its rays toward the far corner: along a plate's top edge
    (0.16 where the top face must reach a floating bolt, 0.006 next to it) the side
    faces' rays came down onto the plate's top and left 90 degree wedges in the Normal
    map. Every corner of a face therefore reaches the face's widest fit along its own
    fitted direction: Blender's ray then follows the interpolated normal, as on Fyr,
    and no point reaches less than the fit asked for.
    """
    import bpy
    import numpy as np

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = low.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        triangle_count = len(mesh.loop_triangles)
        if triangle_count * 3 != len(world_corners):
            return None
        triangle_loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        mesh.loop_triangles.foreach_get("loops", triangle_loops)
        triangle_loops = rna_buffers.as_i32(triangle_loops)
        triangle_faces = rna_buffers.empty_u32_for_rna(triangle_count)
        mesh.loop_triangles.foreach_get("polygon_index", triangle_faces)
        triangle_faces = rna_buffers.as_i32(triangle_faces)
        face_count = len(mesh.polygons)
        vert_count = len(mesh.vertices)
        positions = np.empty(vert_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", positions)
        corner_count = len(mesh.loops)
        corner_verts = rna_buffers.empty_u32_for_rna(corner_count)
        mesh.loops.foreach_get("vertex_index", corner_verts)
        corner_verts = rna_buffers.as_i32(corner_verts)
        corner_normals = np.zeros(corner_count * 3, dtype=np.float32)
        try:
            mesh.corner_normals.foreach_get("vector", corner_normals)
        except (AttributeError, RuntimeError):
            pass
    finally:
        evaluated.to_mesh_clear()
    world_corners = np.asarray(world_corners, dtype=np.float64).reshape(-1, 3)
    matrix = np.array(low.matrix_world, dtype=np.float64)
    inverse = np.linalg.inv(matrix)
    low_world = positions.reshape(-1, 3).astype(np.float64)[corner_verts][triangle_loops]
    low_world = low_world @ matrix[:3, :3].T + matrix[:3, 3]
    segments = world_corners - low_world
    reach = np.linalg.norm(segments, axis=1)
    # A corner the fit left on the surface has no direction of its own: the low's normal.
    fallback = corner_normals.reshape(-1, 3).astype(np.float64)[triangle_loops] @ inverse[:3, :3]
    fallback /= np.maximum(np.linalg.norm(fallback, axis=1, keepdims=True), 1e-20)
    moved = reach > 1e-9
    directions = np.where(moved[:, None], segments / np.maximum(reach, 1e-20)[:, None], fallback)
    corner_faces = np.repeat(triangle_faces, 3)
    face_reach = np.zeros(max(face_count, 1), dtype=np.float64)
    np.maximum.at(face_reach, corner_faces, reach)
    cage_world = low_world + directions * face_reach[corner_faces][:, None]
    local = cage_world @ inverse[:3, :3].T + inverse[:3, 3]
    # A corner no triangle uses (a degenerate face) keeps the low's own position.
    corner_positions = positions.reshape(-1, 3).astype(np.float64)[corner_verts]
    corner_positions[triangle_loops] = local
    return FittedCage(
        low_name=str(low.name),
        corner_positions=corner_positions.astype(np.float32),
        max_offset=float(reach.max()) if len(reach) else 0.0,
    )


def _group_fitted_cages(group, low_objects) -> tuple[FittedCage, ...]:
    """The group's exported Automatic cages, one per low that has one."""
    if str(getattr(group, "cage_mode", "") or "").upper() == constants.CAGE_MODE_CUSTOM:
        return ()
    refs = {
        str(getattr(ref, "object_name", "") or ""): ref
        for ref in getattr(group, "cage_meshes", []) or []
    }
    refs.pop("", None)
    if not refs:
        return ()
    fitted = []
    for low in low_objects:
        low_name = str(getattr(low, "name", "") or "")
        ref = refs.get(f"{low_name}{_AUTO_CAGE_SUFFIX}") if low_name else None
        if ref is None:
            continue
        try:
            corners = _read_cage_corner_positions(getattr(ref, "path", ""))
            only_material = str(getattr(group, "low_material", "") or "")
            if only_material:
                corners = low_material_subset.expand_cage_corners(low, corners, only_material)
            cage = _fitted_cage_for_low(low, corners) if corners is not None else None
        except (OSError, ValueError) as exc:
            print(f"[FyrBaker] Cycles: Automatic cage of '{low_name}' unreadable ({exc}); using a uniform distance")
            continue
        if cage is None:
            print(f"[FyrBaker] Cycles: Automatic cage of '{low_name}' no longer matches its mesh; using a uniform distance")
            continue
        fitted.append(cage)
    return tuple(fitted)


#: Maps whose target image is a float buffer (everything else bakes into 8-bit).
_FLOAT_TARGET_MAPS = frozenset(
    {
        constants.MAP_POSITION,
        constants.MAP_OBJECT_NORMAL,
        constants.MAP_WORLD_NORMAL,
        constants.MAP_SCENE_LIGHTING,
        constants.MAP_LIGHTING,
        constants.MAP_LIT_COLOR,
        constants.MAP_DIRECT_LIGHTING,
        constants.MAP_INDIRECT_LIGHTING,
        constants.MAP_SPECULAR_LIGHTING,
        constants.MAP_ENV_LIGHT,
        constants.MAP_HEIGHT,
    }
)


def _diffuse_pass_filter(map_type: str) -> set[str]:
    """Which light a DIFFUSE bake keeps: Direct / Indirect Lighting rows bake their part."""
    normalized = str(map_type or "").strip().upper()
    if normalized == constants.MAP_DIRECT_LIGHTING:
        return {"DIRECT"}
    if normalized == constants.MAP_INDIRECT_LIGHTING:
        return {"INDIRECT"}
    return {"DIRECT", "INDIRECT"}


def _make_target_image(name: str, width: int, height: int, map_type: str, *, force_float: bool = False):
    import bpy

    image = bpy.data.images.new(
        name=name,
        width=max(1, int(width)),
        height=max(1, int(height)),
        alpha=True,
        float_buffer=bool(force_float) or map_type in _FLOAT_TARGET_MAPS,
    )
    image.colorspace_settings.name = "Non-Color"
    return image


def _stable_material_id_color(material) -> tuple[float, float, float, float]:
    # The SAME rule the native ID map uses (id_material_color.material_id_color), so a
    # Cycles recovery bake paints every material the colour Fyr would have.
    r, g, b = id_material_color.material_id_color(material)
    return (r, g, b, 1.0)


def _collect_materials(objects) -> list:
    materials = []
    seen = set()
    for obj in objects or []:
        for slot in getattr(obj, "material_slots", []) or []:
            material = slot.material if slot else None
            if material is None:
                continue
            key = material.as_pointer()
            if key in seen:
                continue
            seen.add(key)
            materials.append(material)
    return materials


@contextmanager
def _ensured_shading_materials(objects):
    """Guarantee every shading object has a material for the duration of a bake.

    EMIT bakes shade *through materials* — the temporary Emission network is
    installed per material. A high-poly with no material at all (a raw sculpt
    straight out of ZBrush, or a mesh with empty slots) therefore had nothing to
    install onto and baked pure black, silently, for every synthesised map. Fill
    the gaps with throwaway materials and take them back out afterwards.
    """
    import bpy

    created = []
    filled_slots = []
    appended = []
    try:
        for obj in objects or []:
            slots = list(getattr(obj, "material_slots", []) or [])
            if not slots:
                material = bpy.data.materials.new("FYR_Cycles_TempShading")
                material.use_nodes = True
                created.append(material)
                try:
                    obj.data.materials.append(material)
                    appended.append(obj)
                except Exception:
                    pass
                continue
            for index, slot in enumerate(slots):
                if slot.material is not None:
                    continue
                material = bpy.data.materials.new("FYR_Cycles_TempShading")
                material.use_nodes = True
                created.append(material)
                try:
                    slot.material = material
                    filled_slots.append((obj, index))
                except Exception:
                    pass
        yield
    finally:
        for obj, index in reversed(filled_slots):
            try:
                obj.material_slots[index].material = None
            except Exception:
                pass
        for obj in reversed(appended):
            try:
                # clear(), not pop(): pop() empties the material but LEAVES the slot
                # (measured on 5.1 - append 1/1, pop 0/1, clear 0/0), so every recovery
                # bake left one more empty slot on the artist's mesh. We only append to
                # objects that had no slots at all, so clearing restores exactly that.
                obj.data.materials.clear()
            except Exception:
                pass
        for material in created:
            try:
                bpy.data.materials.remove(material)
            except Exception:
                pass


def _local_ao_factor(new, links, local_ao_socket, *, loc):
    """mix(1, local AO, flag) with the flag read from LOCAL_AO_ATTRIBUTE: 1 + flag * (AO - 1)."""
    flag = new("ShaderNodeAttribute", loc=(loc[0] - 700, loc[1] - 260))
    flag.attribute_type = "OBJECT"
    flag.attribute_name = LOCAL_AO_ATTRIBUTE
    minus_one = new("ShaderNodeMath", loc=(loc[0] - 460, loc[1] - 260))
    minus_one.operation = "SUBTRACT"
    links.new(local_ao_socket, minus_one.inputs[0])
    minus_one.inputs[1].default_value = 1.0
    blend = new("ShaderNodeMath", loc=(loc[0] - 240, loc[1] - 260))
    blend.operation = "MULTIPLY_ADD"
    links.new(flag.outputs["Fac"], blend.inputs[0])
    links.new(minus_one.outputs["Value"], blend.inputs[1])
    blend.inputs[2].default_value = 1.0
    return blend.outputs["Value"]


def _material_alpha_source(new, links, mat_output, *, loc):
    """The material's own alpha as a float socket (or a constant): Principled Alpha,
    Transparent BSDF = 0, Mix Shader blending its two sides; the opacity rules
    export._material_opacity_source accepts. Anything else is opaque."""
    surface = mat_output.inputs.get("Surface") if mat_output is not None else None

    def from_node(socket):
        if socket is None or not bool(getattr(socket, "is_linked", False)):
            return None
        node = getattr(tuple(socket.links)[0], "from_node", None)
        if node is not None and getattr(node, "type", "") == "REROUTE":
            # Recursion follows a chain of reroutes.
            node = from_node(node.inputs[0]) if node.inputs else None
        return node

    def alpha_of(node, depth: int):
        node_type = str(getattr(node, "type", "") or "")
        if depth > 8 or node is None:
            return 1.0
        if node_type == "BSDF_TRANSPARENT":
            return 0.0
        if node_type == "BSDF_PRINCIPLED":
            socket = node.inputs.get("Alpha")
            if socket is not None and bool(getattr(socket, "is_linked", False)):
                return tuple(socket.links)[0].from_socket
            return float(getattr(socket, "default_value", 1.0)) if socket is not None else 1.0
        if node_type == "MIX_SHADER":
            first = alpha_of(from_node(node.inputs[1]), depth + 1)
            second = alpha_of(from_node(node.inputs[2]), depth + 1)
            factor_socket = node.inputs[0]
            if isinstance(first, float) and isinstance(second, float) and first == second:
                return first
            # first + fac * (second - first)
            delta = new("ShaderNodeMath", loc=(loc[0] - 460, loc[1] + 200 + 60 * depth))
            delta.operation = "SUBTRACT"
            for index, value in enumerate((second, first)):
                if isinstance(value, float):
                    delta.inputs[index].default_value = value
                else:
                    links.new(value, delta.inputs[index])
            blend = new("ShaderNodeMath", loc=(loc[0] - 240, loc[1] + 200 + 60 * depth))
            blend.operation = "MULTIPLY_ADD"
            if bool(getattr(factor_socket, "is_linked", False)):
                links.new(tuple(factor_socket.links)[0].from_socket, blend.inputs[0])
            else:
                blend.inputs[0].default_value = float(factor_socket.default_value)
            links.new(delta.outputs["Value"], blend.inputs[1])
            if isinstance(first, float):
                blend.inputs[2].default_value = first
            else:
                links.new(first, blend.inputs[2])
            return blend.outputs["Value"]
        return 1.0

    return alpha_of(from_node(surface), 0)


@contextmanager
def _temporary_emit_network(mat, emit_kind: str, params: dict | None = None):
    """Install a temporary Emission→Output network for EMIT bakes.

    ``params`` carries per-bake values the network needs (probe distance, probe
    direction).  Kinds that predate it ignore it and keep their exact output.
    """
    params = params or {}
    # Resolved BEFORE the network below exists: the rule reads the material's own
    # Principled BSDF through its active output, which this function re-points.
    material_id_rgba = (
        _stable_material_id_color(mat) if emit_kind == "material_id" else None
    )
    if not getattr(mat, "use_nodes", False):
        mat.use_nodes = True
    tree = mat.node_tree
    if tree is None:
        yield
        return

    nodes = tree.nodes
    links = tree.links
    mat_output = None
    for node in nodes:
        if getattr(node, "type", "") == "OUTPUT_MATERIAL" and getattr(node, "is_active_output", False):
            mat_output = node
            break
    if mat_output is None:
        for node in nodes:
            if getattr(node, "type", "") == "OUTPUT_MATERIAL":
                mat_output = node
                break
    if mat_output is None:
        yield
        return

    created = []
    previous_active = bool(getattr(mat_output, "is_active_output", True))

    def _new(node_type: str, *, loc=(0.0, 0.0)):
        node = nodes.new(node_type)
        node.location = loc
        created.append(node)
        return node

    try:
        emit_node = _new("ShaderNodeEmission", loc=(mat_output.location[0] - 250, mat_output.location[1] - 180))
        out_node = _new("ShaderNodeOutputMaterial", loc=(mat_output.location[0], mat_output.location[1] - 180))
        out_node.is_active_output = True
        mat_output.is_active_output = False

        if emit_kind == "opacity":
            emit_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        elif emit_kind == "material_id":
            emit_node.inputs["Color"].default_value = material_id_rgba
        elif emit_kind == "vertex_color":
            attr = _new("ShaderNodeVertexColor", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            # Empty layer name → active color attribute in Blender 3.2+.
            try:
                attr.layer_name = ""
            except Exception:
                pass
            links.new(attr.outputs["Color"], emit_node.inputs["Color"])
        elif emit_kind == "attribute":
            # Same stream the Fyr path bakes (color_stream.attribute_stream_rows): the
            # attribute's first three components, (v - min) / (max - min), clamped. A
            # scalar reads as grey through Color; a mesh without it reads 0 (black).
            name, range_min, range_max = (tuple(params.get("attribute", ())) + ("", 0.0, 1.0))[:3]
            attr = _new("ShaderNodeAttribute", loc=(emit_node.location[0] - 440, emit_node.location[1]))
            attr.attribute_type = "GEOMETRY"
            attr.attribute_name = str(name or "")
            remap = _new("ShaderNodeMapRange", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            remap.data_type = "FLOAT_VECTOR"
            remap.clamp = True
            if float(range_max) == float(range_min):
                range_max = float(range_min) + 1.0
            remap.inputs[7].default_value = (float(range_min),) * 3  # From Min (vector)
            remap.inputs[8].default_value = (float(range_max),) * 3  # From Max (vector)
            remap.inputs[9].default_value = (0.0, 0.0, 0.0)  # To Min (vector)
            remap.inputs[10].default_value = (1.0, 1.0, 1.0)  # To Max (vector)
            links.new(attr.outputs["Vector"], remap.inputs[6])  # Vector input
            links.new(remap.outputs["Vector"], emit_node.inputs["Color"])
        elif emit_kind in {"pointiness", "cavity", "concave", "convex"}:
            geom = _new("ShaderNodeNewGeometry", loc=(emit_node.location[0] - 420, emit_node.location[1]))
            ramp = _new("ShaderNodeMapRange", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            ramp.data_type = "FLOAT"
            if emit_kind == "pointiness":
                ramp.inputs["From Min"].default_value = 0.0
                ramp.inputs["From Max"].default_value = 1.0
                ramp.inputs["To Min"].default_value = 0.0
                ramp.inputs["To Max"].default_value = 1.0
            elif emit_kind in {"cavity", "concave"}:
                # Pointiness near 0 is concave.
                ramp.inputs["From Min"].default_value = 0.0
                ramp.inputs["From Max"].default_value = 0.5
                ramp.inputs["To Min"].default_value = 1.0
                ramp.inputs["To Max"].default_value = 0.0
                ramp.clamp = True
            else:  # convex
                ramp.inputs["From Min"].default_value = 0.5
                ramp.inputs["From Max"].default_value = 1.0
                ramp.inputs["To Min"].default_value = 0.0
                ramp.inputs["To Max"].default_value = 1.0
                ramp.clamp = True
            links.new(geom.outputs["Pointiness"], ramp.inputs["Value"])
            links.new(ramp.outputs["Result"], emit_node.inputs["Color"])
        elif emit_kind == "thickness_probe":
            # Up to three inside-visibility fractions U(d), one per colour channel;
            # a channel whose distance is None emits a constant 1 (nothing is ever
            # hit closer than distance 0). See THICKNESS_TRACE_REACH.
            combine = _new("ShaderNodeCombineColor", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            for index, distance in enumerate(tuple(params.get("distances", ()))[:3]):
                channel = index  # Red / Green / Blue, by position across Blender versions
                if distance is None:
                    combine.inputs[channel].default_value = 1.0
                    continue
                ao = _new(
                    "ShaderNodeAmbientOcclusion",
                    loc=(emit_node.location[0] - 460, emit_node.location[1] - 160 * index),
                )
                ao.inside = True
                ao.only_local = False
                # One ray per evaluation: the scene sample count is the ray budget,
                # and the node's own `samples` would multiply it (see density).
                ao.samples = 1
                ao.inputs["Distance"].default_value = max(1e-6, float(distance))
                links.new(ao.outputs["AO"], combine.inputs[channel])
            links.new(combine.outputs["Color"], emit_node.inputs["Color"])
        elif emit_kind == "density":
            # Fyr's DENSITY is the average distance an inward ray travels before it
            # exits the material, normalised against the probe radius and then
            # INVERTED (`encoded = gamma(1 - scaled)` in projection_shading.slang) —
            # so thin reads white and thick reads dark.
            #
            # Inside-AO measures the complement: a ray that escapes the radius
            # without hitting the far wall counts as unoccluded, so AO rises with
            # exit distance. One minus it lands on Fyr's polarity and response.
            distance = max(1e-4, float(params.get("distance", 1.0)))
            ao_in = _new("ShaderNodeAmbientOcclusion", loc=(emit_node.location[0] - 460, emit_node.location[1]))
            try:
                ao_in.inside = True
                ao_in.only_local = False
                # One ray per shader evaluation: the scene sample count already
                # supplies the ray budget, and the node's own `samples` MULTIPLIES
                # it (16 x 128 = 2048 rays/texel against a 14.7M-tri high poly).
                ao_in.samples = 1
                ao_in.inputs["Distance"].default_value = distance
            except Exception:
                pass
            invert = _new("ShaderNodeMath", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            invert.operation = "SUBTRACT"
            invert.inputs[0].default_value = 1.0
            links.new(ao_in.outputs["AO"], invert.inputs[1])
            links.new(invert.outputs["Value"], emit_node.inputs["Color"])
        elif emit_kind == "bent_probe":
            # One directional visibility probe: the AO hemisphere is steered by the
            # vector wired into Normal rather than the shading normal.
            distance = max(1e-4, float(params.get("distance", 1.0)))
            direction = params.get("direction", (0.0, 0.0, 1.0))
            ao = _new("ShaderNodeAmbientOcclusion", loc=(emit_node.location[0] - 260, emit_node.location[1]))
            try:
                ao.inside = False
                ao.only_local = False
                # See the density kind: the node's own sample count multiplies the
                # scene's, and this network is baked once per probe direction.
                ao.samples = 1
                ao.inputs["Distance"].default_value = distance
            except Exception:
                pass
            axis = _new("ShaderNodeCombineXYZ", loc=(emit_node.location[0] - 460, emit_node.location[1] - 140))
            for index, key in enumerate("XYZ"):
                try:
                    axis.inputs[key].default_value = float(direction[index])
                except Exception:
                    pass
            links.new(axis.outputs["Vector"], ao.inputs["Normal"])
            probe_output = ao.outputs["AO"]
            if params.get("local_ao"):
                # Casts AO off highs: global probes no longer see them, so their own
                # occlusion multiplies back in through an only-local probe.
                local = _new("ShaderNodeAmbientOcclusion", loc=(emit_node.location[0] - 260, emit_node.location[1] - 200))
                local.inside = False
                local.only_local = True
                local.samples = 1
                local.inputs["Distance"].default_value = distance
                links.new(axis.outputs["Vector"], local.inputs["Normal"])
                factor = _local_ao_factor(_new, links, local.outputs["AO"], loc=emit_node.location)
                product = _new("ShaderNodeMath", loc=(emit_node.location[0] - 120, emit_node.location[1] - 60))
                product.operation = "MULTIPLY"
                links.new(probe_output, product.inputs[0])
                links.new(factor, product.inputs[1])
                probe_output = product.outputs["Value"]
            links.new(probe_output, emit_node.inputs["Color"])
        elif emit_kind == "local_ao":
            # 1 on every surface but a Casts AO off high, which gets its own occlusion.
            local = _new("ShaderNodeAmbientOcclusion", loc=(emit_node.location[0] - 460, emit_node.location[1]))
            local.inside = False
            local.only_local = True
            local.samples = 1
            local.inputs["Distance"].default_value = max(1e-6, float(params.get("distance", 10.0)))
            factor = _local_ao_factor(_new, links, local.outputs["AO"], loc=emit_node.location)
            links.new(factor, emit_node.inputs["Color"])
        elif emit_kind == "material_alpha":
            # Baked against EVERY source, so the nearest hit decides: a masked high
            # (OPACITY_FRONT_ATTRIBUTE = 1) emits its alpha, any other surface 0.
            source = _material_alpha_source(_new, links, mat_output, loc=emit_node.location)
            flag = _new("ShaderNodeAttribute", loc=(emit_node.location[0] - 700, emit_node.location[1] + 120))
            flag.attribute_type = "OBJECT"
            flag.attribute_name = OPACITY_FRONT_ATTRIBUTE
            masked_alpha = _new("ShaderNodeMath", loc=(emit_node.location[0] - 200, emit_node.location[1] + 120))
            masked_alpha.operation = "MULTIPLY"
            links.new(flag.outputs["Fac"], masked_alpha.inputs[0])
            if isinstance(source, float):
                masked_alpha.inputs[1].default_value = source
            else:
                links.new(source, masked_alpha.inputs[1])
            links.new(masked_alpha.outputs["Value"], emit_node.inputs["Color"])
        elif emit_kind == "tangent_world":
            # World-space surface tangent, encoded 0..1 so it survives a byte buffer
            # and decodes with the same *2-1 rule as the normal passes.
            geom = _new("ShaderNodeNewGeometry", loc=(emit_node.location[0] - 420, emit_node.location[1]))
            encode = _new("ShaderNodeVectorMath", loc=(emit_node.location[0] - 220, emit_node.location[1]))
            encode.operation = "MULTIPLY_ADD"
            encode.inputs[1].default_value = (0.5, 0.5, 0.5)
            encode.inputs[2].default_value = (0.5, 0.5, 0.5)
            links.new(geom.outputs["Tangent"], encode.inputs[0])
            links.new(encode.outputs["Vector"], emit_node.inputs["Color"])
        else:
            emit_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)

        links.new(emit_node.outputs["Emission"], out_node.inputs["Surface"])
        yield
    finally:
        for node in reversed(created):
            try:
                nodes.remove(node)
            except Exception:
                pass
        try:
            mat_output.is_active_output = previous_active
        except Exception:
            pass


def _image_rgba(image):
    import numpy as np

    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(height, width, 4)


def _set_image_rgba(image, rgba) -> None:
    import numpy as np

    flat = np.asarray(rgba, dtype=np.float32).reshape(-1)
    image.pixels.foreach_set(flat)
    image.update()


def cycles_bake_normal_space(normal_space: str | None) -> str | None:
    """Value legal for ``bpy.ops.object.bake(normal_space=...)`` on Blender 5.1+.

    The operator enum is OBJECT / TANGENT only. WORLD is rejected at RNA, so a
    World Normal map must bake OBJECT and convert afterwards.
    """
    if not normal_space:
        return None
    space = str(normal_space).strip().upper()
    if space not in {"OBJECT", "TANGENT"}:
        raise RuntimeError(
            f"Cycles bake normal_space must be OBJECT or TANGENT, not {space!r}"
        )
    return space


def _normal_object_to_world_matrix(target):
    """3x3 taking object-space normals to world (inverse-transpose of the world 3x3)."""
    import numpy as np

    world3 = target.matrix_world.to_3x3()
    inverted = getattr(world3, "inverted", None)
    if inverted is not None:
        try:
            inv = inverted()
            transposed = getattr(inv, "transposed", None)
            if transposed is not None:
                world3 = transposed()
        except (ValueError, ZeroDivisionError):
            pass
    return np.asarray(world3, dtype=np.float32)


def _convert_object_normal_to_world(image, target) -> None:
    """Cycles OBJECT-space normals → world-space, encoded 0..1 in place."""
    import numpy as np

    rgba = _image_rgba(image)
    mask = rgba[..., 3] > 1e-5
    if not np.any(mask):
        return
    n_obj = rgba[mask, :3] * 2.0 - 1.0
    world = n_obj @ _normal_object_to_world_matrix(target).T
    lengths = np.maximum(np.linalg.norm(world, axis=1, keepdims=True), 1e-8)
    world = world / lengths
    rgba[mask, :3] = np.clip(0.5 + 0.5 * world, 0.0, 1.0)
    _set_image_rgba(image, rgba)


def _convert_position_world_to_object(image, target) -> None:
    """Cycles POSITION is world-space; Fyr stores object-space — convert in place."""
    import numpy as np

    inv = target.matrix_world.inverted()
    rgba = _image_rgba(image)
    mask = rgba[..., 3] > 1e-5
    if not np.any(mask):
        return
    world = rgba[mask, :3]
    ones = np.ones((world.shape[0], 1), dtype=np.float32)
    homogeneous = np.concatenate([world, ones], axis=1)
    mat = np.array(inv, dtype=np.float32)
    obj = homogeneous @ mat.T
    rgba[mask, 0] = obj[:, 0]
    rgba[mask, 1] = obj[:, 1]
    rgba[mask, 2] = obj[:, 2]
    _set_image_rgba(image, rgba)


# Map kinds whose encoded normal the GPU path runs through apply_channel_flips
# (backend_bake_maps.cpp): the row's Normal Format decides the green sign.
_FLIP_GREEN_MAP_TYPES = frozenset(
    {constants.MAP_NORMAL, constants.MAP_OBJECT_NORMAL, constants.MAP_WORLD_NORMAL}
)

# Formats whose bit depth follows the image buffer: a byte buffer saves 8-bit and
# a float buffer 16-bit (verified on 5.1). TGA is always 8-bit, EXR always float.
_DEPTH_FOLLOWS_BUFFER_SUFFIXES = frozenset({".png", ".tif", ".tiff"})


def _flip_green_channel(image) -> None:
    """DirectX green: Cycles bakes OpenGL (+Y), the GPU path honours the row's format."""
    rgba = _image_rgba(image)
    rgba[..., 1] = 1.0 - rgba[..., 1]
    _set_image_rgba(image, rgba)


def _save_image(image, output_path: Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str(output_path)
    image.file_format = {
        ".tga": "TARGA_RAW",
        ".png": "PNG",
        ".exr": "OPEN_EXR",
        ".tif": "TIFF",
        ".tiff": "TIFF",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
    }.get(output_path.suffix.lower(), "OPEN_EXR")
    if cycles_memory.blender_exr_save_decodes_srgb(image, image.file_format):
        cycles_memory.write_data_exr(
            output_path, _image_rgba(image).reshape(int(image.size[1]), int(image.size[0]), 4)
        )
        return str(output_path)
    image.save()
    return str(output_path)


@contextmanager
def _saved_cycles_samples(cycles, samples: int):
    original = getattr(cycles, "samples", None)
    try:
        cycles.samples = int(samples)
    except Exception:
        pass
    try:
        yield
    finally:
        if original is not None:
            try:
                cycles.samples = original
            except Exception:
                pass


#: Mirrors blender_bake._PINNED_BAKE_SETTINGS, which documents why this exists.
#: ``target`` was missing here while that module's comment claimed both pinned the
#: same set: the projection route never passes target either, so an artist with the
#: Bake panel on "Active Color Attribute" had every Cycles-recovered projection map
#: baked into their low's colour attribute -- destroying it -- while the injected
#: image was never written and each output saved from an empty buffer.
_PINNED_BAKE_SETTINGS = {
    "target": "IMAGE_TEXTURES",
    "normal_r": "POS_X",
    "normal_g": "POS_Y",
    "normal_b": "POS_Z",
    "use_cage": False,
    "save_mode": "INTERNAL",
}


@contextmanager
def _pinned_scene_bake_settings(scene):
    """Pin the scene's bake swizzle / cage flags for one pass and put them back."""
    bake = getattr(getattr(scene, "render", None), "bake", None)
    saved = {}
    if bake is not None:
        for name, value in _PINNED_BAKE_SETTINGS.items():
            if not hasattr(bake, name):
                continue
            saved[name] = getattr(bake, name)
            try:
                setattr(bake, name, value)
            except Exception:
                saved.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            try:
                setattr(bake, name, value)
            except Exception:
                pass


#: Master switch for :func:`_isolated_render_scope`. Only the headless byte-identity
#: smoke (tests/blender_cycles_render_scope_smoke.py) turns it off, to bake the
#: reference arm.
RENDER_SCOPE_ISOLATION = True

#: Does the temporary Emission network of each ``emit_kind`` (see
#: ``_temporary_emit_network``) cast rays or read any object other than the one
#: being shaded? True = TRACING: its pixels can depend on every render-visible
#: object, so the pass keeps today's full render scope. A kind missing from this
#: table is treated as tracing (:func:`emit_kind_traces`), so a new network can
#: never silently change pixels by being baked in isolation.
_EMIT_KIND_TRACES: dict[str, bool] = {
    # Constant white Emission colour. No input node at all.
    "opacity": False,
    # Constant per-material colour (hash of the material name). No input node.
    "material_id": False,
    # Color Attribute node: the shaded mesh's own active colour attribute.
    "vertex_color": False,
    # Attribute node -> Map Range: the shaded mesh's own named attribute.
    "attribute": False,
    # Geometry.Pointiness -> Map Range. Cycles computes pointiness per mesh from
    # that mesh's own vertices at sync; no ray is cast. Same for the three below.
    "pointiness": False,
    "cavity": False,
    "concave": False,
    "convex": False,
    # Geometry.Tangent -> Vector Math: the shaded mesh's own tangent attribute.
    "tangent_world": False,
    # Ambient Occlusion nodes, inside=True, only_local=False: their rays hit ANY
    # render-visible object.
    "thickness_probe": True,
    # Ambient Occlusion node (inside, only_local=False): scene-wide rays.
    "density": True,
    # Ambient Occlusion node steered along a probe axis, only_local=False.
    "bent_probe": True,
    # Ambient Occlusion node with only_local=True: rays test the shaded object only.
    "local_ao": False,
    # The material's own alpha inputs (image textures, values): the shaded surface only.
    "material_alpha": False,
}


def emit_kind_traces(emit_kind: str | None) -> bool:
    """True unless ``emit_kind``'s network is known to read only the shaded surface."""
    return _EMIT_KIND_TRACES.get(str(emit_kind or ""), True)


#: Shader nodes that make a NORMAL or POSITION pass depend on geometry other than the
#: surface being shaded, or that we cannot prove do not. Cycles finishes those data
#: passes only on a surface whose alpha clears the pass alpha threshold; a
#: transparent / ray-portal / volume-only hit lets the path continue and the pass is
#: written on whatever lies BEHIND it (kernel/film/data_passes.h). The rest cast rays
#: or sample other objects from inside the shader.
_SCENE_DEPENDENT_SHADER_NODES = frozenset(
    {
        "ShaderNodeAmbientOcclusion",
        "ShaderNodeBevel",
        "ShaderNodeLightPath",
        "ShaderNodeRaycast",
        "ShaderNodeScript",
        "ShaderNodeTexPointDensity",
        "ShaderNodeBsdfTransparent",
        "ShaderNodeBsdfRayPortal",
        "ShaderNodeHoldout",
        "ShaderNodeVolumeAbsorption",
        "ShaderNodeVolumeScatter",
        "ShaderNodeVolumePrincipled",
        "ShaderNodeVolumeCoefficients",
    }
)


def _node_tree_sees_other_objects(tree, visited: set) -> bool:
    if tree is None:
        return False
    key = _datablock_key(tree)
    if key in visited:
        return False
    visited.add(key)
    for node in getattr(tree, "nodes", None) or ():
        idname = str(getattr(node, "bl_idname", "") or "")
        if idname in _SCENE_DEPENDENT_SHADER_NODES:
            return True
        if getattr(node, "type", "") == "OUTPUT_MATERIAL":
            volume = _node_input(node, "Volume")
            if volume is not None and getattr(volume, "is_linked", False):
                return True
        alpha = _node_input(node, "Alpha")
        if alpha is not None and idname.startswith("ShaderNodeBsdf"):
            if getattr(alpha, "is_linked", False):
                return True
            try:
                if float(alpha.default_value) < 1.0:
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        if idname == "ShaderNodeGroup" and _node_tree_sees_other_objects(
            getattr(node, "node_tree", None), visited
        ):
            return True
    return False


def _node_input(node, name: str):
    inputs = getattr(node, "inputs", None)
    if inputs is None:
        return None
    try:
        return inputs.get(name) if hasattr(inputs, "get") else None
    except Exception:  # noqa: BLE001 - a malformed socket list is "no such input"
        return None


def _materials_see_other_objects(materials) -> bool:
    visited: set = set()
    for material in materials or ():
        if _node_tree_sees_other_objects(getattr(material, "node_tree", None), visited):
            return True
    return False


def _emit_networks_replace_every_surface(materials) -> bool:
    """``_temporary_emit_network`` installs only where a Material Output exists; a
    material it skipped would bake its OWN graph, which may trace."""
    for material in materials or ():
        tree = getattr(material, "node_tree", None)
        if tree is None:
            return False
        if not any(getattr(node, "type", "") == "OUTPUT_MATERIAL" for node in getattr(tree, "nodes", None) or ()):
            return False
    return True


def pass_is_scene_independent(bake_type: str, emit_kind: str | None, shading_materials) -> bool:
    """Can this pass's pixels depend on any object that does not take part in it?

    Only passes answered "no" may bake with non-participants hidden from render.

    With the bake types below, Cycles' ``bake_setup_pass`` turns direct and indirect
    light OFF, so lights and bounces never contribute (intern/cycles/blender/session.cpp).
    What is left is what the shader and the data-pass writer read at the hit
    (intern/cycles/kernel/film/data_passes.h):

    - NORMAL: the closures' average normal, so the shading material matters.
    - POSITION: ``sd->P`` of the hit, but the writer keeps overwriting it on every
      surface until PATH_RAY_SINGLE_PASS_DONE, which is only set once a hit clears
      the pass alpha threshold. A see-through high therefore bakes the position of
      whatever lies behind it, exactly like NORMAL.
      Both are scene-independent unless a shading material can trace or let the path
      continue past the surface (``_SCENE_DEPENDENT_SHADER_NODES`` / BSDF Alpha).
    - EMIT: only our own temporary networks, classified in ``_EMIT_KIND_TRACES``.
    """
    kind = str(bake_type or "").strip().upper()
    if kind in {"NORMAL", "POSITION"}:
        return not _materials_see_other_objects(shading_materials)
    if kind == "EMIT":
        if not emit_kind or emit_kind_traces(emit_kind):
            return False
        return _emit_networks_replace_every_surface(shading_materials)
    return False


#: blender_bake material strategies -> the Cycles bake type each one runs.
_MATERIAL_STRATEGY_BAKE_TYPES = {
    "emit": "EMIT",
    "emit_normal": "EMIT",
    "ao_image": "EMIT",
    "diffuse_color": "DIFFUSE",
    "normal": "NORMAL",
}


def material_pass_is_scene_independent(strategy: str, shading_materials) -> bool:
    """:func:`pass_is_scene_independent` for a material-channel bake (blender_bake).

    A material channel is the artist's own graph routed into an Emission node (EMIT,
    also for a detail AO image), the DIFFUSE colour pass, or the NORMAL pass. With
    lighting off (``bake_setup_pass``) each reads only the shaded hit, exactly like the
    NORMAL/POSITION data passes above: it depends on other objects only if a node can
    trace or sample them, or the surface lets the path continue behind it. The whole
    node tree is scanned (not just the routed branch), which can only say "depends"
    more often, never less.
    """
    bake_type = _MATERIAL_STRATEGY_BAKE_TYPES.get(str(strategy or "").strip().lower())
    if bake_type is None:
        return False
    return not _materials_see_other_objects(shading_materials)


#: Object types hidden from a scene-independent pass. Renderable geometry only:
#: lights, cameras, probes, armatures, lattices and plain empties are never touched.
_ISOLATABLE_OBJECT_TYPES = frozenset(
    {
        "MESH",
        "CURVE",
        "CURVES",
        "SURFACE",
        "META",
        "FONT",
        "POINTCLOUD",
        "VOLUME",
        "GPENCIL",
        "GREASEPENCIL",
    }
)


def _datablock_key(datablock):
    pointer = getattr(datablock, "as_pointer", None)
    if pointer is not None:
        try:
            return pointer()
        except Exception:  # noqa: BLE001 - removed datablock
            pass
    return id(datablock)


def _collection_reaches(collection, participant_keys, depth: int = 0) -> bool:
    """Does instancing ``collection`` instance a participant (nested instancers too)?"""
    if collection is None or depth > 8:
        return False
    for obj in getattr(collection, "all_objects", None) or ():
        if _datablock_key(obj) in participant_keys:
            return True
        if _instancing_reaches(obj, participant_keys, depth + 1):
            return True
    return False


def _id_reaches(value, participant_keys, depth: int) -> bool:
    if value is None:
        return False
    if _datablock_key(value) in participant_keys:
        return True
    if hasattr(value, "all_objects"):
        return _collection_reaches(value, participant_keys, depth + 1)
    return False


def _geometry_nodes_reach(tree, participant_keys, depth: int, visited: set) -> bool:
    if tree is None:
        return False
    key = _datablock_key(tree)
    if key in visited:
        return False
    visited.add(key)
    for node in getattr(tree, "nodes", None) or ():
        for socket in getattr(node, "inputs", None) or ():
            try:
                value = getattr(socket, "default_value", None)
            except Exception:  # noqa: BLE001
                value = None
            if hasattr(value, "as_pointer") and _id_reaches(value, participant_keys, depth):
                return True
        if _geometry_nodes_reach(getattr(node, "node_tree", None), participant_keys, depth, visited):
            return True
    return False


def _instancing_reaches(obj, participant_keys, depth: int = 0) -> bool:
    """Can ``obj`` instance a participant?

    Cycles marks EVERY instance whose real object is the bake target as a bake
    target and bakes the first one it synced (intern/cycles/blender/object.cpp,
    session.cpp). Hiding an instancer of a participant could therefore change which
    copy is baked, so such an instancer keeps its visibility.
    """
    if depth > 8:
        return False
    try:
        instance_type = str(getattr(obj, "instance_type", "NONE") or "NONE")
        if instance_type == "COLLECTION" and _collection_reaches(
            getattr(obj, "instance_collection", None), participant_keys, depth + 1
        ):
            return True
        if instance_type in {"VERTS", "FACES"}:
            for child in getattr(obj, "children", None) or ():
                if _datablock_key(child) in participant_keys:
                    return True
        for system in getattr(obj, "particle_systems", None) or ():
            settings = getattr(system, "settings", None)
            if _id_reaches(getattr(settings, "instance_object", None), participant_keys, depth):
                return True
            if _id_reaches(getattr(settings, "instance_collection", None), participant_keys, depth):
                return True
        for modifier in getattr(obj, "modifiers", None) or ():
            if getattr(modifier, "type", "") != "NODES":
                continue
            try:
                keys = list(modifier.keys())
            except Exception:  # noqa: BLE001
                keys = []
            for input_key in keys:
                try:
                    value = modifier[input_key]
                except Exception:  # noqa: BLE001
                    continue
                if hasattr(value, "as_pointer") and _id_reaches(value, participant_keys, depth):
                    return True
            if _geometry_nodes_reach(getattr(modifier, "node_group", None), participant_keys, depth, set()):
                return True
    except ReferenceError:
        return False
    return False


def _render_scope_outsiders(view_layer_objects, participants) -> list:
    """Render-visible geometry in the view layer that a pass may hide.

    ``hide_render`` is per object: Blender derives a base's render flag from the
    object's own ``visibility_flag`` only (BKE_base_eval_flags), never from its
    parent, and the bake depsgraph is built with the visibility optimisation OFF
    (object_bake_api.cc), so a hidden parent still drives its children's transform.
    Parents are therefore not protected; instancers that could instance a
    participant are.
    """
    participant_keys = {_datablock_key(obj) for obj in participants if obj is not None}
    outsiders = []
    for obj in view_layer_objects or ():
        try:
            if _datablock_key(obj) in participant_keys:
                continue
            if str(getattr(obj, "type", "") or "") not in _ISOLATABLE_OBJECT_TYPES:
                continue
            if bool(getattr(obj, "hide_render", True)):
                continue
            if _instancing_reaches(obj, participant_keys):
                continue
        except ReferenceError:
            continue
        outsiders.append(obj)
    return outsiders


@contextmanager
def _isolated_render_scope(view_layer_objects, participants, *, enabled: bool):
    """Hide every non-participant from render for one scene-independent pass.

    ``bpy.ops.object.bake`` builds a render depsgraph of the whole view layer and
    Cycles syncs and BVH-builds every render-visible object in it, once per high per
    call. A pass whose pixels cannot depend on those objects
    (:func:`pass_is_scene_independent`) skips them. Restores exactly what it
    changed; an object deleted mid-pass is skipped.
    """
    hidden: list = []
    try:
        if enabled and RENDER_SCOPE_ISOLATION:
            for obj in _render_scope_outsiders(view_layer_objects, participants):
                try:
                    obj.hide_render = True
                except (ReferenceError, AttributeError, TypeError):
                    continue
                hidden.append(obj)
        yield hidden
    finally:
        for obj in reversed(hidden):
            try:
                obj.hide_render = False
            except (ReferenceError, AttributeError, TypeError):
                pass
            except Exception:  # noqa: BLE001 - restore every other object regardless
                pass


#: Object custom property that switches the only-local AO factor on in the
#: ``local_ao`` / ``bent_probe`` emit networks (Attribute node, Object type).
LOCAL_AO_ATTRIBUTE = "fyr_ao_local"
#: Object custom property marking the Respect Opacity highs in the alpha pass.
OPACITY_FRONT_ATTRIBUTE = "fyr_opacity_front"
#: Transparent layers a masked-decal pass lets a shadow ray cross (Cycles allows 1024).
MASKED_TRANSPARENT_BOUNCES = 64


def _pop_id_property(datablock, key: str) -> None:
    try:
        del datablock[key]
    except (KeyError, ReferenceError, TypeError):
        pass


def _world_ao_distance(scene) -> float:
    """The distance Cycles' AO pass traces: the World's AO distance, 10 without a
    World (intern/cycles/blender/shader.cpp)."""
    world = getattr(scene, "world", None)
    settings = getattr(world, "light_settings", None) if world is not None else None
    if settings is None:
        return 10.0
    return max(1.0e-6, float(getattr(settings, "distance", 10.0)))


def _cleanup_scratch_images(images) -> None:
    for scratch in images:
        try:
            image_cleanup.remove_image_when_safe(scratch, reason="cycles scratch")
        except Exception:
            pass


def _run_cycles_bake_pass(*, opacity_masked_objects=(), **kwargs) -> None:
    """One bake pass, with Respect Opacity highs composited by their own alpha.

    Blender finds a selected-to-active hit by a pure geometry ray cast (bake.cc
    cast_ray_highpoly), so a decal's alpha-0 texels hid whatever lay behind them.
    The GPU route keeps a masked hit with probability = opacity; its expectation is
    lerp(behind, masked, alpha), composed here from three bakes: the pass without
    the masked highs, the pass with only them, and their alpha (EMIT, margin 0, so
    it stays 0 wherever no masked high is hit).
    """
    import numpy as np

    sources = list(kwargs.get("source_objects") or [])
    masked_keys = {_datablock_key(obj) for obj in opacity_masked_objects or ()}
    masked = [obj for obj in sources if _datablock_key(obj) in masked_keys]
    solid = [obj for obj in sources if _datablock_key(obj) not in masked_keys]
    if not masked or not solid:
        # Nothing masked, or nothing behind the masks to fall back to.
        _run_cycles_bake_pass_with_self_ao(**kwargs)
        return
    image = kwargs["image"]
    width, height = int(image.size[0]), int(image.size[1])
    scratch = []
    try:
        _run_cycles_bake_pass_with_self_ao(
            **{**kwargs, "source_objects": solid, "extra_participants": masked, "transparent_shadow_objects": masked}
        )
        front_image = _make_target_image(f"{image.name}_masked", width, height, "", force_float=True)
        scratch.append(front_image)
        _run_cycles_bake_pass_with_self_ao(
            **{
                **kwargs,
                "image": front_image,
                "source_objects": masked,
                "margin": 0,
                "extra_participants": solid,
                "transparent_shadow_objects": masked,
            }
        )
        alpha_image = _make_target_image(f"{image.name}_alpha", width, height, "", force_float=True)
        scratch.append(alpha_image)
        # Against every source: the masked-only pass also reaches a decal from behind
        # solid geometry (a ray up through the box from its bottom face), and only the
        # nearest hit may let the decal in.
        _run_cycles_bake_pass_once(
            target_objects=kwargs["target_objects"],
            source_objects=sources,
            image=alpha_image,
            bake_type="EMIT",
            margin=0,
            cage_extrusion=kwargs["cage_extrusion"],
            cage_object_name=kwargs.get("cage_object_name", ""),
            fitted_cages=kwargs.get("fitted_cages", ()),
            samples=1,
            emit_kind="material_alpha",
            device=kwargs.get("device", "CPU"),
            uv_layer=kwargs.get("uv_layer", ""),
            flagged_objects=((OPACITY_FRONT_ATTRIBUTE, masked),),
        )
        behind = _image_rgba(image)
        front = _image_rgba(front_image)
        alpha = np.clip(_image_rgba(alpha_image)[..., :1], 0.0, 1.0)
        composed = behind.copy()
        composed[..., :3] = behind[..., :3] + (front[..., :3] - behind[..., :3]) * alpha
        _set_image_rgba(image, composed)
    finally:
        _cleanup_scratch_images(scratch)


def _run_cycles_bake_pass_with_self_ao(**kwargs) -> None:
    """One pass; a native AO pass then multiplies in the Casts AO off highs' own
    occlusion (only-local AO at the AO pass distance), which hiding them from shadow
    rays took away. Fyr keeps it the same way: a texel on a non-caster re-traces its
    own source."""
    import numpy as np

    _run_cycles_bake_pass_once(**kwargs)
    hidden_keys = {_datablock_key(obj) for obj in kwargs.get("shadow_hidden_objects") or ()}
    sources = list(kwargs.get("source_objects") or [])
    if kwargs.get("bake_type") != "AO" or not any(_datablock_key(obj) in hidden_keys for obj in sources):
        return
    import bpy

    image = kwargs["image"]
    local_image = _make_target_image(
        f"{image.name}_local_ao", int(image.size[0]), int(image.size[1]), "", force_float=True
    )
    try:
        _run_cycles_bake_pass_once(
            **{
                **kwargs,
                "image": local_image,
                "bake_type": "EMIT",
                "emit_kind": "local_ao",
                "emit_params": {"distance": _world_ao_distance(bpy.context.scene)},
                "normal_space": None,
                "pass_filter": None,
            }
        )
        occlusion = _image_rgba(image)
        occlusion[..., :3] *= np.clip(_image_rgba(local_image)[..., :3], 0.0, 1.0)
        _set_image_rgba(image, occlusion)
    finally:
        _cleanup_scratch_images([local_image])


def _run_cycles_bake_pass_once(
    *,
    target_objects,
    source_objects,
    image,
    bake_type: str,
    margin: int,
    cage_extrusion: float,
    samples: int,
    normal_space: str | None = None,
    pass_filter=None,
    cage_object_name: str = "",
    fitted_cages=(),
    emit_kind: str | None = None,
    emit_params: dict | None = None,
    device: str = "CPU",
    uv_layer: str = "",
    shadow_hidden_objects=(),
    extra_participants=(),
    transparent_shadow_objects=(),
    flagged_objects=(),
) -> None:
    import bpy

    scene = bpy.context.scene
    injected_nodes: list[tuple] = []
    shading_objects = source_objects or target_objects
    try:
        with ExitStack() as stack:
            # Casts AO off: native AO and the AO-node probes trace shadow rays, so a
            # high hidden from them stops occluding while it still projects. Its own
            # occlusion comes back through only-local AO nodes, which still see an
            # object hidden from shadow rays; LOCAL_AO_ATTRIBUTE marks whose surface
            # applies them (an emit network is per material, not per object).
            for hidden in shadow_hidden_objects or ():
                if bool(getattr(hidden, "visible_shadow", False)):
                    hidden.visible_shadow = False
                    stack.callback(setattr, hidden, "visible_shadow", True)
                if LOCAL_AO_ATTRIBUTE not in hidden.keys():
                    hidden[LOCAL_AO_ATTRIBUTE] = 1.0
                    stack.callback(_pop_id_property, hidden, LOCAL_AO_ATTRIBUTE)
            # Per-object switches the temporary emit networks read (Attribute, Object).
            for attribute, flagged in flagged_objects or ():
                for obj in flagged:
                    if attribute not in obj.keys():
                        obj[attribute] = 1.0
                        stack.callback(_pop_id_property, obj, attribute)
            # A masked decal occludes AO through its alpha only with Transparent
            # Shadows on its material (Cycles reads MA_BL_TRANSPARENT_SHADOW).
            for material in _collect_materials(list(transparent_shadow_objects or ())):
                if hasattr(material, "use_transparent_shadow") and not material.use_transparent_shadow:
                    material.use_transparent_shadow = True
                    stack.callback(setattr, material, "use_transparent_shadow", False)
            # A shadow ray past more transparent layers than this reads FULLY occluded
            # (default 8; measured: nine stacked masked sheets baked AO 0.0).
            scene_cycles = getattr(scene, "cycles", None)
            if transparent_shadow_objects and scene_cycles is not None:
                bounces = int(getattr(scene_cycles, "transparent_max_bounces", 0) or 0)
                if bounces < MASKED_TRANSPARENT_BOUNCES:
                    scene_cycles.transparent_max_bounces = MASKED_TRANSPARENT_BOUNCES
                    stack.callback(setattr, scene_cycles, "transparent_max_bounces", bounces)
            # A low with no material (or an empty slot) had nothing to inject the bake
            # target image into, so bpy.ops.object.bake failed the whole recovery with
            # Blender's opaque "No active image found in material". The material route
            # already creates a throwaway target material for this case. Filling the
            # gaps has to happen INSIDE the stack so the temporary materials are taken
            # back out again, which is why the injection moved in here with it.
            stack.enter_context(_ensured_shading_materials(list(target_objects or [])))
            for target in target_objects:
                for slot in getattr(target, "material_slots", []) or []:
                    material = slot.material if slot else None
                    if material is None:
                        continue
                    # Not restored, deliberately: on 5.1 use_nodes cannot be turned
                    # off at all (measured -- a new material reads True and assigning
                    # False leaves it True), so this branch never fires and there is
                    # no flat-shaded material for it to switch over permanently.
                    if not getattr(material, "use_nodes", False):
                        material.use_nodes = True
                    node = blender_bake._inject_bake_target_node(  # noqa: SLF001
                        material,
                        low_material_subset.bake_image_for_material(
                            material, image, low_material_subset.cycles_only_material()
                        ),
                    )
                    injected_nodes.append((material, node))

            def _remove_injected_bake_targets():
                # Before the temporary materials above are removed, not after.
                while injected_nodes:
                    injected_material, injected_node = injected_nodes.pop()
                    try:
                        blender_bake._remove_bake_target_node(injected_material, injected_node)  # noqa: SLF001
                    except Exception:
                        pass

            stack.callback(_remove_injected_bake_targets)

            # Visibility first: re-including a layer collection resets its objects'
            # hide state, so nothing else may be staged before this settles. The cage
            # is not selected, but Cycles still resolves it from the evaluated scene,
            # which an excluded collection keeps it out of.
            # Extra participants are scene geometry a pass must see without baking
            # from it (the masked highs an unmasked pass still traces AO against).
            bake_participants = (
                list(target_objects or []) + list(source_objects or []) + list(extra_participants or [])
            )
            cage_object = bpy.data.objects.get(cage_object_name) if cage_object_name else None
            if cage_object is not None:
                bake_participants.append(cage_object)
            stack.enter_context(blender_bake.ensured_bake_visibility(bake_participants))
            stack.enter_context(blender_bake._saved_render_engine(scene))  # noqa: SLF001
            stack.enter_context(blender_bake._saved_cycles_device(scene, device))  # noqa: SLF001
            # EXTEND is the margin algorithm the material path already forces as the
            # closest match to the backend's dilation; left at the scene default a
            # recovered map shipped a visibly harder island edge than its neighbours.
            stack.enter_context(blender_bake._bake_margin_type(scene, "EXTEND"))  # noqa: SLF001
            # The scene's own Bake panel must not leak into a recovery bake: a
            # custom normal swizzle would be flipped twice, and a stale cage object
            # with use_cage on would override cage_extrusion.
            stack.enter_context(_pinned_scene_bake_settings(scene))
            world_cages = stack.enter_context(blender_bake.WorldDistanceCages())
            fitted_by_low = {cage.low_name: cage for cage in fitted_cages or ()}
            if scene.render.engine != "CYCLES":
                scene.render.engine = "CYCLES"
            cycles = getattr(scene, "cycles", None)
            if cycles is not None and hasattr(cycles, "samples"):
                # Restored on exit: one recovery bake used to rewrite the artist's
                # render sample count for good.
                stack.enter_context(_saved_cycles_samples(cycles, max(1, int(samples))))

            if emit_kind:
                stack.enter_context(_ensured_shading_materials(shading_objects))
                for material in _collect_materials(shading_objects):
                    stack.enter_context(_temporary_emit_network(material, emit_kind, emit_params))

            # Listed AFTER the visibility lift: re-including a participant's collection
            # brings its siblings into the view layer, and they must be hidden too.
            view_layer_objects = list(getattr(bpy.context.view_layer, "objects", []) or [])

            # Every bake call re-syncs and BVH-builds every render-visible object in
            # the view layer (other groups' dense highs; for a low-only pass, the
            # group's own highs too). Hide them when this pass provably cannot see
            # them; tracing passes keep today's full scope.
            stack.enter_context(
                _isolated_render_scope(
                    view_layer_objects,
                    bake_participants,
                    enabled=pass_is_scene_independent(
                        bake_type, emit_kind, _collect_materials(shading_objects)
                    ),
                )
            )

            # The selection and active object are the artist's, and this route never
            # put them back: after an AUTOMATIC GPU-to-Cycles recovery -- which they
            # never asked for -- their selection was cleared and the active object was
            # whichever low baked last, re-clobbered on every step of the modal driver.
            # The native route (blender_bake) has always restored both.
            original_selected = [
                item for item in view_layer_objects if bool(getattr(item, "select_get", lambda: False)())
            ]
            original_active = getattr(bpy.context.view_layer.objects, "active", None)

            def _restore_selection():
                for item in view_layer_objects:
                    try:
                        item.select_set(False)
                    except Exception:
                        pass
                for item in original_selected:
                    try:
                        item.select_set(True)
                    except Exception:
                        pass
                try:
                    bpy.context.view_layer.objects.active = original_active
                except Exception:
                    pass

            stack.callback(_restore_selection)
            for target_index, target in enumerate(target_objects):
                for other in view_layer_objects:
                    try:
                        other.select_set(False)
                    except Exception:
                        pass
                for source in source_objects or []:
                    source.select_set(True)
                target.select_set(True)
                bpy.context.view_layer.objects.active = target
                blender_bake._verify_bake_selection(source_objects or [], target)  # noqa: SLF001

                bake_kwargs = {
                    "use_selected_to_active": bool(source_objects),
                    "use_clear": target_index == 0,
                    "margin": max(0, int(margin)),
                }
                if source_objects:
                    fitted = fitted_by_low.get(str(target.name))
                    fitted_kwargs = (
                        world_cages.fitted_kwargs(target, fitted.corner_positions)
                        if fitted is not None
                        else None
                    )
                    if cage_object_name and bpy.data.objects.get(cage_object_name) is not None:
                        # The artist's Custom cage: without it a cage_offset of 0
                        # started rays on the low surface and every high detail
                        # outside it missed where the GPU path was correct.
                        bake_kwargs.update({"use_cage": True, "cage_object": cage_object_name})
                    elif fitted_kwargs is not None:
                        # The Automatic cage the export fitted for the GPU route.
                        bake_kwargs.update(fitted_kwargs)
                    else:
                        # cage_extrusion is in the low's LOCAL units to Blender; the
                        # offset is world units everywhere else.
                        bake_kwargs.update(world_cages.kwargs(target, cage_extrusion))
                    bake_kwargs["max_ray_distance"] = 0.0
                bake_space = cycles_bake_normal_space(normal_space)
                if bake_space:
                    bake_kwargs["normal_space"] = bake_space
                if pass_filter is not None:
                    bake_kwargs["pass_filter"] = pass_filter
                if uv_layer:
                    # The group's UV Set, or a striped bake's temporary strip UVs.
                    bake_kwargs["uv_layer"] = uv_layer

                # This call owns the main thread for minutes on a real scene, which is
                # slow but healthy: without standing the hang watchdog down it fired
                # once per map and wrote ~3.4 MB of all-threads stacks into the log that
                # ships in every support bundle.
                from . import hang_watchdog

                with hang_watchdog.suspended(f"Cycles bake {bake_type}"):
                    result = bpy.ops.object.bake(type=bake_type, **bake_kwargs)
                if "FINISHED" not in result:
                    raise RuntimeError(f"Cycles bake returned {sorted(result)} for {bake_type}")
    finally:
        for material, node in injected_nodes:
            try:
                blender_bake._remove_bake_target_node(material, node)  # noqa: SLF001
            except Exception:
                pass


def _compose_height_from_positions(
    high_pos_image,
    low_pos_image,
    low_normal_image,
    target,
    *,
    cage_extrusion: float,
) -> None:
    """Write greyscale height into high_pos_image (reused as the output buffer)."""
    import numpy as np

    height, mask = _height_field(
        _image_rgba(high_pos_image), _image_rgba(low_pos_image), _image_rgba(low_normal_image), target
    )
    abs_max = float(np.max(np.abs(height[mask]))) if np.any(mask) else None
    _set_image_rgba(high_pos_image, _encode_height(height, mask, _height_scale(abs_max, cage_extrusion)))


def _height_field(high, low, nrm, target):
    """(signed height along the low normal, coverage mask) from the three RGBA passes."""
    import numpy as np

    mask = (high[..., 3] > 1e-5) & (low[..., 3] > 1e-5)

    # Object normals from Cycles are encoded 0..1 → remap to -1..1.
    n_obj = nrm[..., :3] * 2.0 - 1.0
    rot = np.array(target.matrix_world.to_3x3(), dtype=np.float32)
    flat_n = n_obj.reshape(-1, 3)
    n_world = flat_n @ rot.T
    lengths = np.linalg.norm(n_world, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-8)
    n_world = (n_world / lengths).reshape(nrm.shape[0], nrm.shape[1], 3)

    delta = high[..., :3] - low[..., :3]
    height = np.sum(delta * n_world, axis=2)
    return height, mask


def _height_scale(abs_max, cage_extrusion: float) -> float:
    """The encode range: the cage extrusion, widened to the largest covered |height|."""
    scale = max(float(cage_extrusion), 1e-4)
    if abs_max is not None and abs_max > scale:
        scale = abs_max
    return scale


def _encode_height(height, mask, scale: float):
    import numpy as np

    encoded = np.clip(0.5 + 0.5 * (height / scale), 0.0, 1.0).astype(np.float32)
    out = np.zeros(height.shape + (4,), dtype=np.float32)
    out[..., 0] = encoded
    out[..., 1] = encoded
    out[..., 2] = encoded
    out[..., 3] = np.where(mask, 1.0, 0.0).astype(np.float32)
    return out


#: Cycles sample bounds for a recovery bake. Fyr's per-map "samples" is a ray
#: budget (512 is ordinary for AO); handing that straight to ``cycles.samples``
#: would make a fallback bake take minutes, and the bent normal multiplies it by
#: six. Floor it so a low-ray map is not baked at 1 spp, cap it so an artist's
#: 512-ray AO does not turn a recovery path into an overnight job.
_CYCLES_MIN_SAMPLES = 16
_CYCLES_MAX_SAMPLES = 128


def bent_normal_pass_count(normal_space: str | None) -> int:
    """Bakes one bent-normal step costs: the probes, plus the low-poly basis.

    Every space needs the low's own normal (to reject sub-surface directions);
    tangent space additionally needs its tangent.
    """
    space = str(normal_space or constants.MAP_NORMAL_SPACE_TANGENT).strip().upper()
    basis = 2 if space == constants.MAP_NORMAL_SPACE_TANGENT else 1
    return len(_BENT_NORMAL_PROBE_DIRECTIONS) + basis


def _cycles_sample_count(samples) -> int:
    """Clamp a Fyr ray budget into a sane Cycles sample count."""
    try:
        value = int(samples or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        value = _CYCLES_MIN_SAMPLES
    return max(_CYCLES_MIN_SAMPLES, min(value, _CYCLES_MAX_SAMPLES))


def _auto_probe_distance(target_objects) -> float:
    """Fyr treats a 0 distance as 'derive one from the low mesh'; Cycles has no
    such rule, so mirror ``auto_density_max_distance`` in projection_shading.slang:
    half the SMALLEST bounding-box extent, falling back to the diagonal when that
    degenerates. Using the diagonal instead saturates the probe — every inward ray
    finds the far wall inside the radius and the map bakes flat white.
    """
    import numpy as np

    corners = []
    for obj in target_objects or []:
        local = np.asarray([list(corner) for corner in getattr(obj, "bound_box", []) or []], dtype=np.float64)
        if local.size == 0:
            continue
        matrix = getattr(obj, "matrix_world", None)
        if matrix is None:
            corners.append(local)
            continue
        homogeneous = np.concatenate([local, np.ones((local.shape[0], 1))], axis=1)
        corners.append((homogeneous @ np.asarray(matrix, dtype=np.float64).T)[:, :3])
    if not corners:
        return 1.0
    points = np.concatenate(corners, axis=0)
    extent = np.abs(points.max(axis=0) - points.min(axis=0))
    smallest = float(extent.min())
    if smallest <= 1e-6:
        smallest = float(np.linalg.norm(extent))
    return max(1e-4, smallest * 0.5)


def _auto_thickness_distance(target_objects) -> float:
    """Fyr's Auto thickness range: 0.26x the WORLD bounding diagonal of the low.

    A group with several lows uses the largest per-mesh range, like the backend's
    group-level auto_thickness_max_distance.
    """
    import numpy as np

    best = 0.0
    for obj in target_objects or []:
        local = np.asarray([list(corner) for corner in getattr(obj, "bound_box", []) or []], dtype=np.float64)
        if local.size == 0:
            continue
        matrix = getattr(obj, "matrix_world", None)
        if matrix is not None:
            homogeneous = np.concatenate([local, np.ones((local.shape[0], 1))], axis=1)
            local = (homogeneous @ np.asarray(matrix, dtype=np.float64).T)[:, :3]
        diagonal = float(np.linalg.norm(local.max(axis=0) - local.min(axis=0)))
        best = max(best, diagonal * THICKNESS_AUTO_RANGE_DIAGONAL)
    return best if best > 1e-6 else 1.0


def thickness_probe_distances(encode_range: float, thickness_encode) -> tuple:
    """The six U(d) distances the two thickness passes bake, in channel order.

    ``(x_0 .. x_3, R, min)``: quadrature midpoints over the traced span, the reach R,
    and the trace minimum (None when it is 0, where U is 1 by definition).
    """
    min_distance = max(0.0, float(thickness_encode[0]))
    reach = THICKNESS_TRACE_REACH * max(float(encode_range), 1e-6)
    span = max(reach - min_distance, 0.0)
    points = THICKNESS_QUADRATURE_POINTS
    midpoints = tuple(min_distance + span * (index + 0.5) / points for index in range(points))
    return (*midpoints, reach, min_distance if min_distance > 0.0 else None)


def _compose_thickness(image, probes, *, encode_range: float, thickness_encode) -> None:
    """Write the encoded thickness into ``image`` from its two probe passes."""
    first, second = (_image_rgba(probe) for probe in probes)
    _set_image_rgba(
        image,
        compose_thickness(first, second, encode_range=encode_range, thickness_encode=thickness_encode),
    )


def compose_thickness(first_rgba, second_rgba, *, encode_range: float, thickness_encode):
    """Encoded greyscale thickness (RGBA) from the two ``thickness_probe`` passes."""
    import numpy as np

    min_distance = max(0.0, float(thickness_encode[0]))
    scale = max(float(thickness_encode[1]), 0.01)
    gamma = max(float(thickness_encode[2]), 0.01)
    encode_range = max(float(encode_range), min_distance + 1e-6)
    reach = THICKNESS_TRACE_REACH * encode_range
    span = max(reach - min_distance, 0.0)

    visible = np.concatenate([first_rgba[..., :3], second_rgba[..., :1]], axis=-1).astype(np.float64)
    visible_reach = second_rgba[..., 1].astype(np.float64)
    visible_min = (
        second_rgba[..., 2].astype(np.float64) if min_distance > 0.0 else np.ones_like(visible_reach)
    )
    hit_fraction = visible_min - visible_reach
    integral = np.sum(visible - visible_reach[..., None], axis=-1) * (span / THICKNESS_QUADRATURE_POINTS)
    has_hits = hit_fraction > 1e-4
    mean_chord = np.where(
        has_hits,
        np.clip(min_distance + integral / np.where(has_hits, hit_fraction, 1.0), min_distance, reach),
        # No chord ended inside the reach: Fyr's hits-only mean is empty -> white.
        0.0,
    )
    # encode_thickness_distance, linear response.
    normalized = np.clip((mean_chord - min_distance) / (encode_range - min_distance), 0.0, 1.0)
    inverted = 1.0 - np.clip(normalized * scale, 0.0, 1.0)
    value = np.power(np.clip(inverted * inverted, 0.0, 1.0), 1.0 / gamma).astype(np.float32)

    coverage = (first_rgba[..., 3] > 1e-5) | (second_rgba[..., 3] > 1e-5)
    out = np.zeros(first_rgba.shape[:-1] + (4,), dtype=np.float32)
    out[..., 0] = out[..., 1] = out[..., 2] = np.where(coverage, value, 0.0)
    out[..., 3] = coverage.astype(np.float32)
    return out


def _compose_bent_normal(
    output_image,
    probe_images,
    directions,
    target,
    *,
    normal_space: str,
    low_normal_image=None,
    low_tangent_image=None,
) -> None:
    """Reconstruct a bent normal from directional visibility probes.

    Each probe holds the visibility of the hemisphere around one world axis. Their
    visibility-weighted sum is the first-order direction of the visibility function
    — which is what a bent normal is. The result is then rotated into the space the
    map asks for and encoded 0..1 like every other normal-family output.
    """
    import numpy as np

    accum = None
    coverage = None
    for image, direction in zip(probe_images, directions):
        rgba = _image_rgba(image)
        visibility = rgba[..., 0].astype(np.float32)
        axis = np.asarray(direction, dtype=np.float32)
        contribution = visibility[..., None] * axis[None, None, :]
        accum = contribution if accum is None else accum + contribution
        alpha = rgba[..., 3] > 1e-5
        coverage = alpha if coverage is None else (coverage | alpha)
    if accum is None:
        return

    lengths = np.linalg.norm(accum, axis=2, keepdims=True)
    degenerate = (lengths[..., 0] <= 1e-6) | ~coverage
    bent_world = accum / np.maximum(lengths, 1e-8)

    # Fall back to the surface normal wherever the probes cancelled out (a fully
    # enclosed or fully open texel carries no directional information).
    surface_world = None
    if low_normal_image is not None:
        surface_world = _decode_world_normal(low_normal_image, target)
        bent_world = np.where(degenerate[..., None], surface_world, bent_world)
        # A bent normal never points into the surface.
        below = np.sum(bent_world * surface_world, axis=2) <= 0.0
        bent_world = np.where(below[..., None], surface_world, bent_world)

    space = str(normal_space or "TANGENT").strip().upper()
    if space == "WORLD":
        encoded_vec = bent_world
    elif space == "OBJECT":
        rot = np.array(target.matrix_world.to_3x3().inverted(), dtype=np.float32)
        flat = bent_world.reshape(-1, 3) @ rot.T
        norms = np.maximum(np.linalg.norm(flat, axis=1, keepdims=True), 1e-8)
        encoded_vec = (flat / norms).reshape(bent_world.shape)
    else:
        if surface_world is None or low_tangent_image is None:
            raise RuntimeError(
                "Tangent-space bent normal needs the low-poly normal and tangent passes"
            )
        tangent = _decode_world_vector(low_tangent_image)
        # Gram-Schmidt against the normal, then B = N x T (the same right-handed
        # basis Blender's own tangent-space bake uses).
        tangent = tangent - surface_world * np.sum(tangent * surface_world, axis=2, keepdims=True)
        t_len = np.maximum(np.linalg.norm(tangent, axis=2, keepdims=True), 1e-8)
        tangent = tangent / t_len
        bitangent = np.cross(surface_world, tangent)
        encoded_vec = np.stack(
            (
                np.sum(bent_world * tangent, axis=2),
                np.sum(bent_world * bitangent, axis=2),
                np.sum(bent_world * surface_world, axis=2),
            ),
            axis=2,
        )

    out = np.zeros(bent_world.shape[:2] + (4,), dtype=np.float32)
    out[..., :3] = np.clip(0.5 + 0.5 * encoded_vec, 0.0, 1.0)
    # Uncovered texels take the neutral fill the backend uses for this map.
    out[..., 0] = np.where(coverage, out[..., 0], 0.5)
    out[..., 1] = np.where(coverage, out[..., 1], 0.5)
    out[..., 2] = np.where(coverage, out[..., 2], 1.0)
    out[..., 3] = np.where(coverage, 1.0, 0.0).astype(np.float32)
    _set_image_rgba(output_image, out)


def _decode_world_normal(image, target):
    """Object-space normal bake (0..1) → unit world-space vectors."""
    import numpy as np

    rgba = _image_rgba(image)
    n_obj = rgba[..., :3] * 2.0 - 1.0
    mat = _normal_object_to_world_matrix(target)
    flat = n_obj.reshape(-1, 3) @ mat.T
    norms = np.maximum(np.linalg.norm(flat, axis=1, keepdims=True), 1e-8)
    return (flat / norms).reshape(n_obj.shape)


def _decode_world_vector(image):
    """Emit-baked vector (0..1) → unit vectors, no space change."""
    import numpy as np

    rgba = _image_rgba(image)
    vec = rgba[..., :3] * 2.0 - 1.0
    norms = np.maximum(np.linalg.norm(vec, axis=2, keepdims=True), 1e-8)
    return vec / norms


def _compose_curvature_direction(normal_image) -> None:
    """Write the major curvature axis into ``normal_image``, in place.

    Fyr encodes CURVATURE_DIRECTION as the major (kappa1) curvature axis in the
    tangent plane, packed into RG the same way a normal map is, with B pinned to
    1.0 and a neutral (0.5, 0.5, 1.0) fill where the direction is undefined. The
    same field is recoverable from a tangent-space normal bake: the shape operator
    is the spatial derivative of the normal, and its dominant eigenvector is the
    axis we want.
    """
    import numpy as np

    rgba = _image_rgba(normal_image)
    coverage = rgba[..., 3] > 1e-5
    normals = rgba[..., :3] * 2.0 - 1.0

    # Rows run bottom-up in Blender images, so axis 0 is +V and axis 1 is +U.
    dnx_dv, dnx_du = np.gradient(normals[..., 0])
    dny_dv, dny_du = np.gradient(normals[..., 1])

    # Symmetric part of the Jacobian — the shape operator's tangent-plane block.
    a = dnx_du
    b = 0.5 * (dnx_dv + dny_du)
    c = dny_dv

    half_trace = 0.5 * (a + c)
    gap = 0.5 * (a - c)
    root = np.sqrt(np.maximum(gap * gap + b * b, 0.0))
    lambda_major = np.where(
        np.abs(half_trace + root) >= np.abs(half_trace - root),
        half_trace + root,
        half_trace - root,
    )

    # Eigenvector for lambda: (b, lambda - a), falling back to (lambda - c, b)
    # when the first form degenerates (b == 0 on an axis-aligned ridge).
    ex = b
    ey = lambda_major - a
    fallback = (np.abs(ex) < 1e-12) & (np.abs(ey) < 1e-12)
    ex = np.where(fallback, lambda_major - c, ex)
    ey = np.where(fallback, b, ey)
    still_flat = (np.abs(ex) < 1e-12) & (np.abs(ey) < 1e-12)
    ex = np.where(still_flat, 1.0, ex)
    ey = np.where(still_flat, 0.0, ey)

    length = np.maximum(np.sqrt(ex * ex + ey * ey), 1e-12)
    ex = ex / length
    ey = ey / length
    # The axis is left signed. An eigenvector has no inherent sign, and Fyr's own
    # output is symmetric about 0.5 in R — canonicalising to a half-plane here
    # produced a map that correlated at 0.15 against it.

    undefined = ~coverage | (np.abs(lambda_major) < 1e-6)
    out = np.zeros_like(rgba)
    # The axis lies in the tangent plane, so its Z is 0 and encodes to 0.5. B is
    # only 1.0 where the direction is undefined — that is the map's neutral fill
    # (matching the backend's get_default_fill), not a constant.
    out[..., 0] = np.where(undefined, 0.5, np.clip(0.5 + 0.5 * ex, 0.0, 1.0))
    out[..., 1] = np.where(undefined, 0.5, np.clip(0.5 + 0.5 * ey, 0.0, 1.0))
    out[..., 2] = np.where(undefined, 1.0, 0.5)
    out[..., 3] = np.where(coverage, 1.0, 0.0).astype(np.float32)
    _set_image_rgba(normal_image, out)


def cycles_soften_sigma_pixels(soften: float) -> float:
    """Soften -> Gaussian sigma in texels for the Cycles recovery path.

    Same ramp the Fyr backend uses (resolve_output_soften_sigma_pixels): linear in
    radius, sigma = 2 * soften over a 0..2 scale, so 0 (the default) is off.
    """
    try:
        value = float(soften)
    except (TypeError, ValueError):
        value = float(constants.DEFAULT_SOFTEN)
    value = min(max(value, 0.0), float(constants.SOFTEN_MAX))
    return value * 2.0


def soften_radius_pixels(sigma_pixels: float) -> int:
    """Kernel radius :func:`_soften_image_gaussian` uses for ``sigma_pixels`` (0 = off).

    Kept in lockstep with that function: a striped bake sizes its apron from it.
    """
    if sigma_pixels <= 0.0:
        return 0
    sigma = max(float(sigma_pixels), 0.05)
    return max(1, min(32, int(math.ceil(sigma * 2.5))))


def _soften_image_gaussian(image, sigma_pixels: float) -> None:
    """Blur an image's RGB in place with a separable Gaussian, radius ~2.5 sigma.

    Approximate twin of the backend's soften_covered_gaussian. The radius tracks sigma
    for the same reason it does there: a fixed 3x3 kernel just flattens toward a box as
    sigma rises, which inflates isolated specks into square blobs instead of blurring.
    The backend masks taps by bake coverage; the Cycles path does not carry a coverage
    mask (Blender has already dilated into the margin), so this filters every texel.
    Edge taps clamp. Alpha is left alone.
    """
    import numpy as np

    if sigma_pixels <= 0.0:
        return
    width = int(image.size[0])
    height = int(image.size[1])
    if width <= 0 or height <= 0:
        return
    sigma = max(float(sigma_pixels), 0.05)
    radius = max(1, min(32, int(np.ceil(sigma * 2.5))))
    taps = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(taps * taps) / (2.0 * sigma * sigma))
    kernel /= float(kernel.sum())

    flat = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(flat)
    buf = flat.reshape(height, width, 4)
    rgb = buf[:, :, :3]

    # Clamp-to-edge padding, then one 1-D convolution per axis.
    padded = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    horizontal = np.zeros((padded.shape[0], width, 3), dtype=np.float32)
    for i, weight in enumerate(kernel):
        horizontal += padded[:, i:i + width, :] * float(weight)
    blurred = np.zeros((height, width, 3), dtype=np.float32)
    for i, weight in enumerate(kernel):
        blurred += horizontal[i:i + height, :, :] * float(weight)

    buf[:, :, :3] = blurred
    image.pixels.foreach_set(buf.reshape(-1))
    image.update()


def _validated_cycles_strategy(map_type: str, target_objects, source_objects) -> CyclesMapStrategy:
    strategy = cycles_map_strategy(map_type)
    if strategy is None:
        raise RuntimeError(unsupported_cycles_reason(map_type))
    if not target_objects:
        raise RuntimeError("Cycles projection bake requires at least one low object")
    if strategy.requires_highs and not source_objects:
        raise RuntimeError(f"Cycles {map_type} fallback requires high-poly source objects")
    return strategy


def cycles_map_pass_count(map_type: str, normal_space: str | None = None) -> int:
    """Cycles bake passes (``_run_cycles_bake_pass`` calls) one map costs per strip.

    A whole-image bake is one strip, so this is exactly the number of passes
    :class:`CyclesMapJob` steps through; a map the memory plan splits into strips runs
    this many passes per strip, and the planner stores the product on
    ``CyclesBakeStep.passes``.
    """
    strategy = cycles_map_strategy(map_type)
    if strategy is None:
        return 1
    if strategy.mode == "derived" and strategy.emit_kind == "bent_normal":
        return bent_normal_pass_count(normal_space)
    return max(1, int(strategy.passes or 1))


def _bake_map_passes(
    *,
    strategy: CyclesMapStrategy,
    image,
    make_scratch,
    target_objects,
    source_objects,
    map_type: str,
    margin: int,
    cage_extrusion: float,
    cage_object_name: str,
    samples: int,
    normal_space: str | None,
    probe_distance: float,
    emit_attribute: tuple = (),
    thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE,
    on_progress: ProgressCallback | None,
    device: str,
    uv_layer: str = "",
    raw_height: bool = False,
    shadow_hidden_objects=(),
    opacity_masked_objects=(),
    fitted_cages=(),
):
    """Every bake pass of one map into ``image``, then its compose / conversion step.

    Yields once after each ``_run_cycles_bake_pass`` (``cycles_map_pass_count``
    times). ``make_scratch(name, map_type, force_float)`` supplies the extra images a
    derived map needs, sized like ``image``; the caller owns their release. With
    ``raw_height`` a Height map stops before encoding and returns (height, mask) so a
    striped bake can find the global scale first. ``uv_layer`` is passed to every
    pass only when set: the group's UV Set, or a striped bake's strip UVs.
    """
    image_name = f"FYR_Cycles_{map_type}"
    uv = {"uv_layer": uv_layer} if uv_layer else {}
    # Rides along with the UV option into every pass of an AO-family map.
    if shadow_hidden_objects:
        uv["shadow_hidden_objects"] = tuple(shadow_hidden_objects)
    if opacity_masked_objects:
        uv["opacity_masked_objects"] = tuple(opacity_masked_objects)
    if fitted_cages:
        uv["fitted_cages"] = tuple(fitted_cages)
    if strategy.mode == "derived" and strategy.emit_kind == "height":
        high_pos = image
        low_pos = make_scratch(f"{image_name}_lowpos", constants.MAP_POSITION, False)
        low_nml = make_scratch(f"{image_name}_lownml", constants.MAP_OBJECT_NORMAL, False)
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=source_objects,
            image=high_pos,
            bake_type="POSITION",
            margin=margin,
            cage_extrusion=cage_extrusion,
            cage_object_name=cage_object_name,
            samples=samples,
            device=device,
            **uv,
        )
        yield
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=[],
            image=low_pos,
            bake_type="POSITION",
            margin=margin,
            cage_extrusion=0.0,
            samples=max(1, min(int(samples), 4)),
            device=device,
            **uv,
        )
        yield
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=[],
            image=low_nml,
            bake_type="NORMAL",
            margin=margin,
            cage_extrusion=0.0,
            samples=max(1, min(int(samples), 4)),
            normal_space="OBJECT",
            device=device,
            **uv,
        )
        yield
        if raw_height:
            return _height_field(
                _image_rgba(high_pos), _image_rgba(low_pos), _image_rgba(low_nml), target_objects[0]
            )
        # No cage_object_name: _compose_height_from_positions does not take one, and
        # passing it raised TypeError AFTER the three POSITION/NORMAL passes had
        # already run, so HEIGHT was unbakeable on the Cycles route entirely.
        _compose_height_from_positions(
            high_pos,
            low_pos,
            low_nml,
            target_objects[0],
            cage_extrusion=cage_extrusion,
        )
    elif strategy.mode == "derived" and strategy.emit_kind == "bent_normal":
        space = str(normal_space or constants.MAP_NORMAL_SPACE_TANGENT).strip().upper()
        distance = float(probe_distance) if probe_distance > 0.0 else _auto_probe_distance(target_objects)
        probe_samples = max(1, int(samples))
        probes = []
        for index, direction in enumerate(_BENT_NORMAL_PROBE_DIRECTIONS):
            probe = make_scratch(f"{image_name}_probe{index}", map_type, True)
            probes.append(probe)
            if on_progress:
                on_progress(
                    f"Cycles bent normal: visibility probe {index + 1}/"
                    f"{len(_BENT_NORMAL_PROBE_DIRECTIONS)}"
                )
            _run_cycles_bake_pass(
                target_objects=target_objects,
                source_objects=source_objects,
                image=probe,
                bake_type="EMIT",
                margin=margin,
                cage_extrusion=cage_extrusion,
                cage_object_name=cage_object_name,
                samples=probe_samples,
                emit_kind="bent_probe",
                emit_params=(
                    {"distance": distance, "direction": direction, "local_ao": True}
                    if shadow_hidden_objects
                    else {"distance": distance, "direction": direction}
                ),
                device=device,
                **uv,
            )
            yield

        # The low-poly's own frame, needed to reject sub-surface directions and
        # (for tangent space) to build the basis the map is expressed in.
        low_nml = make_scratch(f"{image_name}_lownml", constants.MAP_OBJECT_NORMAL, False)
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=[],
            image=low_nml,
            bake_type="NORMAL",
            margin=margin,
            cage_extrusion=0.0,
            samples=max(1, min(int(samples), 4)),
            normal_space="OBJECT",
            device=device,
            **uv,
        )
        yield
        low_tangent = None
        if space == constants.MAP_NORMAL_SPACE_TANGENT:
            low_tangent = make_scratch(f"{image_name}_lowtan", map_type, True)
            _run_cycles_bake_pass(
                target_objects=target_objects,
                source_objects=[],
                image=low_tangent,
                bake_type="EMIT",
                margin=margin,
                cage_extrusion=0.0,
                samples=max(1, min(int(samples), 4)),
                emit_kind="tangent_world",
                device=device,
                **uv,
            )
            yield
        _compose_bent_normal(
            image,
            probes,
            _BENT_NORMAL_PROBE_DIRECTIONS,
            target_objects[0],
            normal_space=space,
            low_normal_image=low_nml,
            low_tangent_image=low_tangent,
        )
    elif strategy.mode == "derived" and strategy.emit_kind == "thickness":
        encode_range = (
            float(probe_distance) if probe_distance > 0.0 else _auto_thickness_distance(target_objects)
        )
        distances = thickness_probe_distances(encode_range, thickness_encode)
        probes = []
        for index, channel_distances in enumerate((distances[:3], distances[3:])):
            probe = make_scratch(f"{image_name}_probe{index}", map_type, True)
            probes.append(probe)
            _run_cycles_bake_pass(
                target_objects=target_objects,
                source_objects=source_objects,
                image=probe,
                bake_type="EMIT",
                margin=margin,
                cage_extrusion=cage_extrusion,
                cage_object_name=cage_object_name,
                samples=max(1, int(samples)),
                emit_kind="thickness_probe",
                emit_params={"distances": channel_distances},
                device=device,
                **uv,
            )
            yield
        _compose_thickness(image, probes, encode_range=encode_range, thickness_encode=thickness_encode)
    elif strategy.mode == "derived" and strategy.emit_kind == "curvature_direction":
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=source_objects,
            image=image,
            bake_type="NORMAL",
            margin=margin,
            cage_extrusion=cage_extrusion,
            cage_object_name=cage_object_name,
            samples=samples,
            normal_space="TANGENT",
            device=device,
            **uv,
        )
        yield
        _compose_curvature_direction(image)
    else:
        _run_cycles_bake_pass(
            target_objects=target_objects,
            source_objects=source_objects,
            image=image,
            bake_type=strategy.bake_type,
            margin=margin,
            cage_extrusion=cage_extrusion,
            cage_object_name=cage_object_name,
            samples=samples,
            normal_space=strategy.normal_space,
            pass_filter=(
                _diffuse_pass_filter(map_type)
                if strategy.bake_type == "DIFFUSE"
                else ({"DIRECT", "INDIRECT", "COLOR"} if strategy.bake_type == "GLOSSY" else None)
            ),
            emit_kind=strategy.emit_kind if strategy.mode == "emit" else None,
            emit_params=(
                {
                    "distance": (
                        float(probe_distance)
                        if probe_distance > 0.0
                        else _auto_probe_distance(target_objects)
                    )
                }
                if strategy.emit_kind == "density"
                else {"attribute": tuple(emit_attribute)}
                if strategy.emit_kind == "attribute"
                else None
            ),
            device=device,
            **uv,
        )
        yield
        if map_type == constants.MAP_POSITION:
            _convert_position_world_to_object(image, target_objects[0])
        elif map_type == constants.MAP_WORLD_NORMAL:
            _convert_object_normal_to_world(image, target_objects[0])
    return None


def _finish_map_image(image, map_type: str, *, flip_green: bool, soften: float) -> None:
    """Output-side filters every Cycles projection map gets after its compose step."""
    if flip_green and map_type in _FLIP_GREEN_MAP_TYPES:
        _flip_green_channel(image)
    if constants.map_supports_soften(map_type):
        _soften_image_gaussian(image, cycles_soften_sigma_pixels(soften))


def _announce_baked(on_progress, map_type: str, strategy: CyclesMapStrategy) -> None:
    if on_progress:
        suffix = f" ({strategy.note})" if strategy.note else ""
        on_progress(f"Baked {map_type} via Cycles{suffix}")


def _deep_output(output_path, bit_depth: int) -> bool:
    return int(bit_depth or 8) > 8 and Path(output_path).suffix.lower() in _DEPTH_FOLLOWS_BUFFER_SUFFIXES


def _projection_map_passes(
    *,
    strategy: CyclesMapStrategy,
    target_objects,
    source_objects,
    map_type: str,
    width: int,
    height: int,
    output_path,
    margin: int,
    cage_extrusion: float,
    cage_object_name: str,
    samples: int,
    normal_space: str | None,
    probe_distance: float,
    emit_attribute: tuple = (),
    thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE,
    on_progress: ProgressCallback | None,
    device: str,
    uv_offset_u: float,
    uv_offset_v: float,
    soften: float,
    flip_green: bool,
    bit_depth: int,
    shadow_hidden_objects=(),
    opacity_masked_objects=(),
    fitted_cages=(),
    uv_layer_name: str = "",
):
    """The body of one Cycles projection map, suspended after every bake pass.

    Yields once after each ``_run_cycles_bake_pass`` (so exactly
    ``cycles_map_pass_count`` times), then composes, saves and returns the output
    path via ``StopIteration``. Everything that spans passes -- the target and
    scratch images and the UDIM uv offset -- is owned by the ``finally`` below, so
    it is released exactly once whether the generator finishes, raises, or is
    closed between passes (``CyclesMapJob.abort``). Every other Blender state a bake
    touches (visibility lift, emit networks, engine/device/samples, pinned bake
    settings, selection) is scoped to a single ``_run_cycles_bake_pass`` call and
    never outlives it.

    This is the whole-image path; a map the memory plan splits into strips runs
    :func:`_projection_map_strip_passes` instead.
    """
    image_name = f"FYR_Cycles_{map_type}"
    # The project's 16-bit setting used to be lost here: every non-float map baked
    # into a byte buffer and saved as 8-bit PNG while the GPU path wrote 16-bit.
    deep_output = _deep_output(output_path, bit_depth)
    image = _make_target_image(image_name, width, height, map_type, force_float=deep_output)
    scratch_images = []
    uv_offset = None
    active_uv = None

    def make_scratch(name, scratch_map_type, force_float):
        if force_float:
            scratch = _make_target_image(name, width, height, scratch_map_type, force_float=True)
        else:
            scratch = _make_target_image(name, width, height, scratch_map_type)
        scratch_images.append(scratch)
        return scratch

    try:
        # Built inside the try so a failure here still removes the target image
        # instead of leaving FYR_Cycles_<MAP> behind in bpy.data.images.
        # Tangent normals take their tangents from the active layer: the UV Set, as on Fyr.
        active_uv = blender_bake.bake_uv_layer_active(list(target_objects), uv_layer_name)
        active_uv.__enter__()
        # The UDIM shift moves the layer the passes rasterize: the group's UV Set.
        uv_offset = blender_bake._temporary_uv_tile_offset(  # noqa: SLF001
            list(target_objects),
            float(uv_offset_u or 0.0),
            float(uv_offset_v or 0.0),
            layer_name=uv_layer_name,
        )
        uv_offset.__enter__()
        yield from _bake_map_passes(
            strategy=strategy,
            image=image,
            make_scratch=make_scratch,
            target_objects=target_objects,
            source_objects=source_objects,
            map_type=map_type,
            margin=margin,
            cage_extrusion=cage_extrusion,
            cage_object_name=cage_object_name,
            samples=samples,
            normal_space=normal_space,
            probe_distance=probe_distance,
            emit_attribute=emit_attribute,
            thickness_encode=thickness_encode,
            on_progress=on_progress,
            device=device,
            uv_layer=uv_layer_name,
            shadow_hidden_objects=shadow_hidden_objects,
            opacity_masked_objects=opacity_masked_objects,
            fitted_cages=fitted_cages,
        )
        _finish_map_image(image, map_type, flip_green=flip_green, soften=soften)
        _announce_baked(on_progress, map_type, strategy)
        return _save_image(image, Path(output_path))
    finally:
        if uv_offset is not None:
            try:
                uv_offset.__exit__(None, None, None)
            except Exception:
                pass
        if active_uv is not None:
            try:
                active_uv.__exit__(None, None, None)
            except Exception:
                pass
        for scratch in scratch_images:
            try:
                image_cleanup.remove_image_when_safe(scratch, reason="cycles scratch")
            except Exception:
                pass
        try:
            image_cleanup.remove_image_when_safe(image, reason="cycles bake target")
        except Exception:
            pass


class _HeightStripStore:
    """Raw per-texel height and coverage of a striped Height map, on disk.

    Height is encoded against the largest covered |height| of the WHOLE map, which is
    only known once every strip has baked, so phase one parks the raw field here
    (memory-mapped, one float + one byte per texel) and phase two encodes it.
    """

    def __init__(self, width: int, height: int):
        import tempfile

        import numpy as np

        try:
            from . import storage_cleanup

            directory = storage_cleanup.ensure_scratch_subdir("cycles_strips")
        except Exception:  # noqa: BLE001 - fall back to the system temp dir
            directory = Path(tempfile.gettempdir())
        token = f"{os.getpid()}_{id(self):x}"
        self._paths = [directory / f"height_{token}.f32", directory / f"mask_{token}.u8"]
        self._height = None
        self._mask = None
        try:
            self._height = np.memmap(self._paths[0], dtype=np.float32, mode="w+", shape=(int(height), int(width)))
            self._mask = np.memmap(self._paths[1], dtype=np.uint8, mode="w+", shape=(int(height), int(width)))
        except BaseException:
            self.close()
            raise

    def store(self, strip, height, mask) -> None:
        first = strip.keep_start - strip.window_start
        last = strip.keep_end - strip.window_start
        self._height[strip.keep_start:strip.keep_end] = height[first:last]
        self._mask[strip.keep_start:strip.keep_end] = mask[first:last]

    def abs_max(self):
        import numpy as np

        best = None
        rows = int(self._height.shape[0])
        for start in range(0, rows, 256):
            mask = np.asarray(self._mask[start:start + 256]).astype(bool)
            if not np.any(mask):
                continue
            value = float(np.max(np.abs(np.asarray(self._height[start:start + 256])[mask])))
            best = value if best is None else max(best, value)
        return best

    def window(self, start: int, rows: int):
        import numpy as np

        height = np.array(self._height[start:start + rows], dtype=np.float32)
        mask = np.array(self._mask[start:start + rows]).astype(bool)
        return height, mask

    def close(self) -> None:
        for name in ("_height", "_mask"):
            array = getattr(self, name, None)
            setattr(self, name, None)
            if array is None:
                continue
            handle = getattr(array, "_mmap", None)
            del array
            if handle is not None:
                try:
                    handle.close()
                except Exception:  # noqa: BLE001
                    pass
        for path in self._paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass


def _allows_in_place_strip_uvs(strategy: CyclesMapStrategy, source_objects) -> bool:
    """Every pass of the map is selected-to-active, so no pass shades the low's UVs."""
    if not source_objects or not strategy.requires_highs:
        return False
    return not (strategy.mode == "derived" and strategy.emit_kind in {"height", "bent_normal"})


def _projection_map_strip_passes(
    *,
    strip_plan,
    strategy: CyclesMapStrategy,
    target_objects,
    source_objects,
    map_type: str,
    width: int,
    height: int,
    output_path,
    margin: int,
    cage_extrusion: float,
    cage_object_name: str,
    samples: int,
    normal_space: str | None,
    probe_distance: float,
    emit_attribute: tuple = (),
    thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE,
    on_progress: ProgressCallback | None,
    device: str,
    uv_offset_u: float,
    uv_offset_v: float,
    soften: float,
    flip_green: bool,
    bit_depth: int,
    shadow_hidden_objects=(),
    opacity_masked_objects=(),
    fitted_cages=(),
    uv_layer_name: str = "",
):
    """:func:`_projection_map_passes` for a map the memory plan splits into row strips.

    Same passes per strip, in the same order, into images one strip tall that are
    reused for every strip; the passes rasterize through temporary strip UVs (which
    also carry the UDIM offset, so the low's own UVs are not shifted). Strips run
    top-down and each finished strip is appended to a temporary file beside the
    output, which only :meth:`CyclesMapJob.finish` moves into place. Height runs in
    two phases because its encode range is global.
    """
    strip_rows = int(strip_plan.strip_rows)
    image_name = f"FYR_Cycles_{map_type}"
    deep_output = _deep_output(output_path, bit_depth)
    image = _make_target_image(image_name, width, strip_rows, map_type, force_float=deep_output)
    scratch: dict = {}
    uv_layers = None
    active_uv = None
    assembler = None
    height_store = None
    is_height = strategy.mode == "derived" and strategy.emit_kind == "height"

    def make_scratch(name, scratch_map_type, force_float):
        existing = scratch.get(name)
        if existing is not None:
            return existing
        if force_float:
            created = _make_target_image(name, width, strip_rows, scratch_map_type, force_float=True)
        else:
            created = _make_target_image(name, width, strip_rows, scratch_map_type)
        scratch[name] = created
        return created

    def release_scratch():
        while scratch:
            _name, scratch_image = scratch.popitem()
            try:
                image_cleanup.remove_image_when_safe(scratch_image, reason="cycles scratch")
            except Exception:
                pass

    try:
        # Outside the strip UVs; see _projection_map_passes.
        active_uv = blender_bake.bake_uv_layer_active(list(target_objects), uv_layer_name)
        active_uv.__enter__()
        uv_layers = cycles_memory.StripUVLayers(
            objects=list(target_objects),
            tile_u=float(uv_offset_u or 0.0),
            tile_v=float(uv_offset_v or 0.0),
            height=int(height),
            allow_in_place=_allows_in_place_strip_uvs(strategy, source_objects),
            # The strip UVs derive from the group's UV Set, the layout the GPU writes.
            source_layer_name=str(uv_layer_name or ""),
        )
        uv_layers.open()
        assembler = cycles_memory.StripAssembler(output_path, width, height)
        if is_height:
            height_store = _HeightStripStore(width, height)
        strips = strip_plan.top_down()
        for order, strip in enumerate(strips):
            if order:
                cycles_memory.check_strip_fits(strip_plan, credit_bytes=strip_plan.strip_bytes())
            uv_layers.set_window(strip.window_start, strip_rows)
            result = yield from _bake_map_passes(
                strategy=strategy,
                image=image,
                make_scratch=make_scratch,
                target_objects=target_objects,
                source_objects=source_objects,
                map_type=map_type,
                margin=margin,
                cage_extrusion=cage_extrusion,
                cage_object_name=cage_object_name,
                samples=samples,
                normal_space=normal_space,
                probe_distance=probe_distance,
                emit_attribute=emit_attribute,
                thickness_encode=thickness_encode,
                on_progress=on_progress,
                device=device,
                uv_layer=uv_layers.layer_name,
                raw_height=is_height,
                shadow_hidden_objects=shadow_hidden_objects,
                opacity_masked_objects=opacity_masked_objects,
                fitted_cages=fitted_cages,
            )
            if is_height:
                height_store.store(strip, *result)
                continue
            _finish_map_image(image, map_type, flip_green=flip_green, soften=soften)
            assembler.add_strip(image, strip, strip_rows)
        if is_height:
            # Phase two: nothing is baked any more; free the pass images first.
            release_scratch()
            scale = _height_scale(height_store.abs_max(), cage_extrusion)
            for strip in strips:
                field, mask = height_store.window(strip.window_start, strip_rows)
                _set_image_rgba(image, _encode_height(field, mask, scale))
                _finish_map_image(image, map_type, flip_green=flip_green, soften=soften)
                assembler.add_strip(image, strip, strip_rows)
        _announce_baked(on_progress, map_type, strategy)
        return assembler.commit()
    finally:
        if uv_layers is not None:
            uv_layers.close()
        if active_uv is not None:
            try:
                active_uv.__exit__(None, None, None)
            except Exception:
                pass
        if assembler is not None:
            assembler.abort()
        if height_store is not None:
            height_store.close()
        release_scratch()
        try:
            image_cleanup.remove_image_when_safe(image, reason="cycles bake target")
        except Exception:
            pass


def _map_label(map_type: str) -> str:
    try:
        from . import naming

        return naming.map_label(map_type)
    except Exception:  # noqa: BLE001
        return str(map_type or "")


def _strategy_may_see_other_objects(strategy: CyclesMapStrategy, shading_materials) -> bool:
    """Can any pass of this map sync / see render-visible objects beyond its own?"""
    if strategy.mode == "derived":
        if strategy.emit_kind == "bent_normal":
            return True
        return not pass_is_scene_independent(strategy.bake_type, None, shading_materials)
    emit_kind = strategy.emit_kind if strategy.mode == "emit" else None
    return not pass_is_scene_independent(strategy.bake_type, emit_kind, shading_materials)


def _projection_scene_bytes(strategy, target_objects, source_objects, cage_object_name: str) -> int:
    lows = list(target_objects or [])
    if cage_object_name:
        try:
            import bpy  # noqa: PLC0415

            cage = bpy.data.objects.get(cage_object_name)
            if cage is not None:
                lows.append(cage)
        except Exception:  # noqa: BLE001
            pass
    others: list = []
    shading = _collect_materials(list(source_objects or []) or lows)
    if _strategy_may_see_other_objects(strategy, shading):
        try:
            import bpy  # noqa: PLC0415

            view_layer_objects = list(getattr(bpy.context.view_layer, "objects", []) or [])
            others = _render_scope_outsiders(view_layer_objects, lows + list(source_objects or []))
        except Exception:  # noqa: BLE001
            others = []
    return cycles_memory.estimate_scene_bytes(source_objects, lows, others=others)


def _projection_strip_params(strategy, map_type, source_objects, margin, soften, output_path, bit_depth):
    """(apron rows, bytes per texel) of one projection map's bake."""
    radius = 0
    if constants.map_supports_soften(map_type):
        radius = soften_radius_pixels(cycles_soften_sigma_pixels(soften))
    derived = strategy.emit_kind if strategy.mode == "derived" else None
    per_texel = cycles_memory.bytes_per_texel(
        selected_to_active=bool(source_objects),
        float_target=map_type in _FLOAT_TARGET_MAPS or _deep_output(output_path, bit_depth),
        derived_extra=cycles_memory.derived_extra_bytes(derived),
    )
    return cycles_memory.apron_rows(margin, filter_radius=radius), per_texel


def plan_projection_strips(
    *,
    strategy: CyclesMapStrategy,
    map_type: str,
    target_objects,
    source_objects,
    width: int,
    height: int,
    margin: int,
    soften: float,
    output_path,
    bit_depth: int,
    cage_object_name: str = "",
    group_name: str = "",
    scene_bytes: int | None = None,
    memory=cycles_memory.MEASURE,
):
    """The memory plan of one projection map (see cycles_memory.plan_strips).

    Raises cycles_memory.CyclesMemoryError when not even the smallest strip fits.
    """
    apron, per_texel = _projection_strip_params(
        strategy, map_type, source_objects, margin, soften, output_path, bit_depth
    )
    if scene_bytes is None:
        scene_bytes = _projection_scene_bytes(strategy, target_objects, source_objects, cage_object_name)
    return cycles_memory.plan_strips(
        width,
        height,
        apron=apron,
        bytes_per_texel=per_texel,
        scene_bytes=scene_bytes,
        memory=memory,
        what=_map_label(map_type),
        group=group_name,
    )


def _strip_plan_for_job(
    strategy, map_type, target_objects, source_objects, width, height, margin, soften,
    output_path, bit_depth, cage_object_name, group_name, strip_rows,
):
    """None = the whole-image path; otherwise the StripPlan the job bakes."""
    if strip_rows is None:
        plan = plan_projection_strips(
            strategy=strategy,
            map_type=map_type,
            target_objects=target_objects,
            source_objects=source_objects,
            width=width,
            height=height,
            margin=margin,
            soften=soften,
            output_path=output_path,
            bit_depth=bit_depth,
            cage_object_name=cage_object_name,
            group_name=group_name,
        )
        return None if plan.single else plan
    strip_rows = int(strip_rows or 0)
    if strip_rows <= 0 or strip_rows >= int(height):
        return None
    apron, per_texel = _projection_strip_params(
        strategy, map_type, source_objects, margin, soften, output_path, bit_depth
    )
    return cycles_memory.strip_plan_from_rows(
        width,
        height,
        apron=apron,
        strip_rows=strip_rows,
        bytes_per_texel=per_texel,
        scene_bytes=_projection_scene_bytes(strategy, target_objects, source_objects, cage_object_name),
        what=_map_label(map_type),
        group=group_name,
    )


class CyclesMapJob:
    """One Cycles projection map, advanced one bake pass at a time.

    A derived map (Height, Bent Normal) is several blocking ``bpy.ops.object.bake``
    calls deep. The modal driver runs one :meth:`next_pass` per timer tick so the
    progress bar moves and ESC lands between passes instead of only between maps;
    the headless driver drains the job in one go through :func:`bake_projection_map`.

    Lifecycle: construct (validates and plans memory, allocates nothing) ->
    ``next_pass()`` x ``pass_count`` -> ``finish()`` (compose + save, returns the
    output path). The output file is written by ``finish()`` alone, so an aborted job
    never leaves a partial map on disk. ``abort()`` is idempotent and safe in every
    state; after a pass or ``finish()`` raises, the job has already released
    everything.

    A map too large for the free memory is baked in row strips: ``pass_count`` is
    then the map's passes times the strip count. ``strip_rows`` is the planner's
    choice (0 = whole image); None plans here.
    """

    _PENDING = "pending"
    _RUNNING = "running"
    _FINISHED = "finished"
    _FAILED = "failed"
    _ABORTED = "aborted"

    def __init__(
        self,
        *,
        target_objects,
        source_objects,
        map_type: str,
        width: int,
        height: int,
        output_path,
        margin: int = 16,
        cage_extrusion: float = 0.0,
        cage_object_name: str = "",
        samples: int = 16,
        normal_space: str | None = None,
        probe_distance: float = 0.0,
        emit_attribute: tuple = (),
        thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE,
        on_progress: ProgressCallback | None = None,
        device: str = "CPU",
        uv_offset_u: float = 0.0,
        uv_offset_v: float = 0.0,
        soften: float = constants.DEFAULT_SOFTEN,
        flip_green: bool = False,
        bit_depth: int = 8,
        strip_rows: int | None = None,
        group_name: str = "",
        shadow_hidden_objects=(),
        opacity_masked_objects=(),
        fitted_cages=(),
        texture_set_rank: int = 0,
        texture_set_lows=(),
        udim_tile: int = 0,
        uv_layer_name: str = "",
    ):
        strategy = _validated_cycles_strategy(map_type, target_objects, source_objects)
        uv_layer_name = str(uv_layer_name or "").strip()
        blender_bake._require_bake_uv_layer(target_objects, uv_layer_name)  # noqa: SLF001
        strip_plan = _strip_plan_for_job(
            strategy, map_type, target_objects, source_objects, width, height, margin, soften,
            output_path, bit_depth, cage_object_name, group_name, strip_rows,
        )
        self.map_type = map_type
        self.strip_count = 1 if strip_plan is None else strip_plan.count
        self.pass_count = cycles_map_pass_count(map_type, normal_space) * self.strip_count
        self.passes_done = 0
        self.result_path: str | None = None
        self._status = self._PENDING
        self._close_deferred = False
        # A later member of a texture set bakes beside the shared file and is merged
        # into it by finish(); the shared file is never written by the passes.
        self._texture_set = None
        if int(texture_set_rank or 0) > 0:
            self._texture_set = {
                "output_path": str(output_path),
                "pass_path": str(_texture_set_pass_path(output_path)),
                "target_objects": list(target_objects),
                "set_lows": list(texture_set_lows or ()),
                "margin": int(margin),
                "udim_tile": int(udim_tile or 0),
                "uv_layer_name": uv_layer_name,
            }
            output_path = self._texture_set["pass_path"]
        body = dict(
            strategy=strategy,
            target_objects=target_objects,
            source_objects=source_objects,
            map_type=map_type,
            width=width,
            height=height,
            output_path=output_path,
            margin=margin,
            cage_extrusion=cage_extrusion,
            cage_object_name=cage_object_name,
            samples=samples,
            normal_space=normal_space,
            probe_distance=probe_distance,
            emit_attribute=emit_attribute,
            thickness_encode=thickness_encode,
            on_progress=on_progress,
            device=device,
            uv_offset_u=uv_offset_u,
            uv_offset_v=uv_offset_v,
            soften=soften,
            flip_green=flip_green,
            bit_depth=bit_depth,
            shadow_hidden_objects=tuple(shadow_hidden_objects or ()),
            opacity_masked_objects=tuple(opacity_masked_objects or ()),
            fitted_cages=tuple(fitted_cages or ()),
            uv_layer_name=uv_layer_name,
        )
        # A generator does not run a line until the first next(): constructing the
        # job creates no image and shifts no UVs.
        if strip_plan is None:
            self._passes = _projection_map_passes(**body)
        else:
            self._passes = _projection_map_strip_passes(strip_plan=strip_plan, **body)

    @property
    def open(self) -> bool:
        return self._status in (self._PENDING, self._RUNNING)

    @property
    def passes_remaining(self) -> int:
        if not self.open:
            return 0
        return max(0, self.pass_count - self.passes_done)

    def next_pass(self) -> None:
        """Run exactly one Cycles bake pass (the first one also sets the map up)."""
        if not self.open:
            raise RuntimeError(f"Cycles {self.map_type} job is already {self._status}")
        if self.passes_done >= self.pass_count:
            raise RuntimeError(f"Cycles {self.map_type} has no bake pass left; call finish()")
        self._status = self._RUNNING
        try:
            next(self._passes)
        except StopIteration:
            # The generator's finally has already run; nothing is left to release.
            self._status = self._FAILED
            raise RuntimeError(
                f"Cycles {self.map_type} ran out of bake passes after "
                f"{self.passes_done} of {self.pass_count}"
            ) from None
        except BaseException:
            self._status = self._FAILED
            raise
        self.passes_done += 1
        self._close_if_deferred()

    def finish(self) -> str:
        """Compose and save the map after its last pass. Returns the output path."""
        if not self.open:
            raise RuntimeError(f"Cycles {self.map_type} job is already {self._status}")
        if self.passes_done < self.pass_count:
            raise RuntimeError(
                f"Cycles {self.map_type} still has {self.pass_count - self.passes_done} "
                "bake pass(es) to run"
            )
        self._status = self._RUNNING
        try:
            next(self._passes)
        except StopIteration as stop:
            result = stop.value
            if self._texture_set is not None:
                try:
                    _composite_into_texture_set(
                        self._texture_set["output_path"],
                        self._texture_set["pass_path"],
                        target_objects=self._texture_set["target_objects"],
                        set_lows=self._texture_set["set_lows"],
                        margin=self._texture_set["margin"],
                        udim_tile=self._texture_set["udim_tile"],
                        uv_layer_name=self._texture_set["uv_layer_name"],
                    )
                except BaseException:
                    self._status = self._FAILED
                    raise
                finally:
                    self._remove_texture_set_pass()
                result = self._texture_set["output_path"]
            self._status = self._FINISHED
            self.result_path = result
            return result
        except BaseException:
            self._status = self._FAILED
            self._remove_texture_set_pass()
            raise
        # The generator yielded again: it runs more passes than cycles_map_pass_count
        # says. Release everything rather than bake a pass nobody accounted for.
        self.abort()
        raise RuntimeError(
            f"Cycles {self.map_type} runs more than its {self.pass_count} planned bake passes"
        )

    def abort(self) -> None:
        """Release every temp image and the UV offset without writing the output.

        Idempotent. A no-op once the job finished or failed (both already released
        everything), and before the first pass (nothing was allocated yet).
        """
        if not self.open:
            return
        self._status = self._ABORTED
        self._remove_texture_set_pass()
        try:
            self._passes.close()
        except ValueError:
            # Called from inside a running pass (re-entrant cancel): the frame is
            # busy, so close it the moment that pass returns.
            self._close_deferred = True
        except Exception:
            pass

    def _remove_texture_set_pass(self) -> None:
        if self._texture_set is None:
            return
        try:
            os.remove(self._texture_set["pass_path"])
        except OSError:
            pass

    def _close_if_deferred(self) -> None:
        if self._close_deferred:
            self._close_deferred = False
            try:
                self._passes.close()
            except Exception:
                pass


def bake_projection_map(
    *,
    target_objects,
    source_objects,
    map_type: str,
    width: int,
    height: int,
    output_path,
    margin: int = 16,
    cage_extrusion: float = 0.0,
    cage_object_name: str = "",
    samples: int = 16,
    normal_space: str | None = None,
    probe_distance: float = 0.0,
    emit_attribute: tuple = (),
    thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE,
    on_progress: ProgressCallback | None = None,
    device: str = "CPU",
    uv_offset_u: float = 0.0,
    uv_offset_v: float = 0.0,
    soften: float = constants.DEFAULT_SOFTEN,
    flip_green: bool = False,
    bit_depth: int = 8,
    strip_rows: int | None = None,
    group_name: str = "",
    shadow_hidden_objects=(),
    opacity_masked_objects=(),
    fitted_cages=(),
    texture_set_rank: int = 0,
    texture_set_lows=(),
    udim_tile: int = 0,
    uv_layer_name: str = "",
) -> str:
    """Bake one projection map through Cycles (native, synthesised EMIT, or derived).

    Synchronous: drains a :class:`CyclesMapJob` in one call.
    """
    job = CyclesMapJob(
        target_objects=target_objects,
        source_objects=source_objects,
        map_type=map_type,
        width=width,
        height=height,
        output_path=output_path,
        margin=margin,
        cage_extrusion=cage_extrusion,
        cage_object_name=cage_object_name,
        samples=samples,
        normal_space=normal_space,
        probe_distance=probe_distance,
        emit_attribute=emit_attribute,
        thickness_encode=thickness_encode,
        on_progress=on_progress,
        device=device,
        uv_offset_u=uv_offset_u,
        uv_offset_v=uv_offset_v,
        soften=soften,
        flip_green=flip_green,
        bit_depth=bit_depth,
        strip_rows=strip_rows,
        group_name=group_name,
        shadow_hidden_objects=shadow_hidden_objects,
        opacity_masked_objects=opacity_masked_objects,
        fitted_cages=fitted_cages,
        texture_set_rank=texture_set_rank,
        texture_set_lows=texture_set_lows,
        udim_tile=udim_tile,
        uv_layer_name=uv_layer_name,
    )
    try:
        while job.passes_remaining:
            job.next_pass()
        return job.finish()
    finally:
        job.abort()


def _uv_offset_for_udim_tile(udim_tile) -> tuple[int, float, float]:
    """Shift low UVs so tile ``udim_tile`` occupies the 0–1 bake square.

    Tile 0 (untiled) and tile 1001 are both origin (0, 0). Matches the material
    bake path in ``blender_bake._temporary_uv_tile_offset``.
    """
    tile = int(udim_tile or 0)
    if tile <= 0:
        return 0, 0.0, 0.0
    from . import udim as _udim

    tile_u, tile_v = _udim.tile_origin(tile)
    return tile, float(tile_u), float(tile_v)


@dataclass
class CyclesBakeStep:
    """One (group, map, tile) unit of Cycles work — the granularity of async ticks."""

    group_name: str
    map_type: str
    map_uuid: str
    output_path: str
    target_objects: list
    source_objects: list
    width: int
    height: int
    margin: int
    cage_extrusion: float
    samples: int
    approximate: bool
    note: str
    normal_space: str = constants.MAP_NORMAL_SPACE_TANGENT
    probe_distance: float = 0.0
    # (attribute name, range min, range max) of an ATTRIBUTE row; empty otherwise.
    emit_attribute: tuple = ()
    thickness_encode: tuple = DEFAULT_THICKNESS_ENCODE
    passes: int = 1
    udim_tile: int = 0
    #: Name of a CUSTOM cage object in the scene, passed to Cycles as cage_object.
    #: Empty for Automatic cages (a generated file, no scene object): those ride in
    #: ``fitted_cages`` and get a temporary cage object per pass.
    cage_object_name: str = ""
    uv_offset_u: float = 0.0
    uv_offset_v: float = 0.0
    # The row's Normal Format, as the job carries it (DirectX -> True). Cycles bakes
    # OpenGL, so the recovery route has to flip green itself or a DirectX row comes
    # back OpenGL with a DirectX name.
    flip_green: bool = False
    # The project's output bit depth; PNG/TIFF targets follow it.
    bit_depth: int = 8
    # Resolved Soften for this map (properties.resolve_map_soften). On Cycles NO map
    # family carries a built-in output filter, so the whole ladder is centred on the
    # 0.5 neutral: at or below it nothing is filtered and the recovery path stays
    # byte-identical to what it produced before Soften existed.
    soften: float = constants.DEFAULT_SOFTEN
    # Memory plan (cycles_memory): rows per strip, 0 = the whole image in one bake.
    # ``passes`` already counts every strip.
    strip_rows: int = 0
    strips: int = 1
    # High objects with Casts AO off, hidden from shadow rays for AO-family maps.
    shadow_hidden_objects: tuple = ()
    # Respect Opacity highs (job opacity binding): each pass composites them by their alpha.
    opacity_masked_objects: tuple = ()
    # The Automatic cage the export fitted, per low (FittedCage); traced as a cage object.
    fitted_cages: tuple = ()
    # Texture sets: how many earlier groups of this plan write the same output file
    # (0 = this step writes it fresh), and the lows of every group sharing it.
    texture_set_rank: int = 0
    texture_set_lows: tuple = ()
    #: group.low_material: the faces this step writes ("" = whole objects).
    only_material: str = ""
    #: The group's UV Set override: the layer every pass rasterizes into, as the GPU
    #: does. "" bakes into each low's active render layer.
    uv_layer_name: str = ""

    @property
    def label(self) -> str:
        suffix = " (approx)" if self.approximate else ""
        cost = f", {self.passes} passes" if self.passes > 1 else ""
        tile = f" .{self.udim_tile}" if int(self.udim_tile or 0) else ""
        strips = f" in {self.strips} strips" if int(self.strips or 1) > 1 else ""
        return f"Cycles: {self.group_name} / {self.map_type}{tile}{suffix}{cost}{strips}"


@dataclass
class CyclesBakePlan:
    """Validated Cycles work list plus every problem found before baking started."""

    steps: list[CyclesBakeStep]
    errors: list[str]
    device: str
    device_note: str


def resolve_cycles_bake_device() -> tuple[str, str]:
    """Cycles device for a bake this backend owns outright (primary or recovery)."""
    try:
        from . import preferences as preferences_module

        return preferences_module.resolve_cycles_device()
    except Exception:
        return "CPU", ""


def _ao_shadow_hidden_objects(group, map_type: str, source_objects) -> tuple:
    """The group's Casts AO off highs among ``source_objects``, for an AO-family map."""
    if map_type not in constants.AO_OCCLUDER_MAP_TYPES:
        return ()
    names = {str(name) for name in getattr(group, "ao_non_caster_objects", []) or [] if str(name or "")}
    if not names:
        return ()
    return tuple(obj for obj in source_objects or [] if str(getattr(obj, "name", "") or "") in names)


def _opacity_masked_objects(job, group, source_objects) -> tuple:
    """The highs among ``source_objects`` the export bound an opacity mask to.

    The same set the GPU route opacity-tests: Respect Opacity on, and a job high ref
    carrying an opacity image or a constant below 1.
    """
    if not bool(getattr(getattr(job, "project", None), "respect_opacity", True)):
        return ()
    names = set()
    for ref in getattr(group, "high_meshes", []) or []:
        constant = getattr(ref, "opacity_constant", 1.0)
        constant = 1.0 if constant is None else float(constant)
        if str(getattr(ref, "opacity_image_path", "") or "") or constant < 1.0:
            names.add(str(getattr(ref, "object_name", None) or getattr(ref, "name", "") or ""))
    names.discard("")
    if not names:
        return ()
    return tuple(obj for obj in source_objects or [] if str(getattr(obj, "name", "") or "") in names)


def plan_cycles_projection(prepared, *, map_types=None) -> CyclesBakePlan:
    """Validate a prepared job into per-map Cycles steps without baking anything.

    All resolution problems (missing objects, unsupported map types, a map that
    cannot fit in the free memory even in strips) are collected up front so callers
    fail loudly before spending minutes of Cycles time.
    """
    device, device_note = resolve_cycles_bake_device()
    memory = cycles_memory.system_memory()
    steps: list[CyclesBakeStep] = []
    errors: list[str] = []
    job = getattr(prepared, "job", None)
    if job is None:
        return CyclesBakePlan([], ["Cycles bake skipped: prepared job is missing"], device, device_note)

    requested = None
    if map_types is not None:
        requested = {str(value).strip().upper() for value in map_types if str(value or "").strip()}

    # Outputs carry identity and paths; the artist's per-map settings live on the
    # job's map configs, keyed by the same uuid.
    map_configs = {
        str(getattr(config, "map_uuid", "") or ""): config
        for config in getattr(job, "maps", []) or []
        if getattr(config, "map_uuid", "")
    }

    margin = int(getattr(getattr(job, "project", None), "margin", 16) or 16)
    try:
        bit_depth = int(getattr(getattr(job, "project", None), "bit_depth", 8) or 8)
    except (TypeError, ValueError):
        bit_depth = 8
    # job.project is protocol.BakeProjectInfo: its fields are resolution_width /
    # resolution_height. The RNA names below never matched, so every output that
    # inherited the project size (resolution_width 0) baked at 2048 into a 4K
    # filename whenever the GPU path handed off to Cycles.
    job_project = getattr(job, "project", None)
    width = int(
        getattr(job_project, "resolution_width", 0)
        or getattr(job_project, "resolution_x", 0)
        or 0
    )
    height = int(
        getattr(job_project, "resolution_height", 0)
        or getattr(job_project, "resolution_y", 0)
        or 0
    )
    if width <= 0:
        width = int(getattr(job_project, "resolution", 2048) or 2048)
    if height <= 0:
        height = width

    # A Lit Color row reaches the job as hidden Lighting + Material sources that
    # derived_outputs multiplies after a Fyr bake. Cycles bakes the row whole instead
    # (the LIT_COLOR strategy, textures included) straight into the artist's file, and
    # skips the Material sources, which only the Fyr composite reads.
    from . import derived_outputs

    lit_color_final_by_source = {
        os.path.normcase(os.path.abspath(str(entry.get("lighting_source", "") or ""))): str(entry.get("final_path", ""))
        for entry in getattr(prepared, "derived_outputs", None) or []
        if str(entry.get("kind", "")) == derived_outputs.KIND_LIT_COLOR and entry.get("lighting_source")
    }
    lit_color_source_suffixes = (
        derived_outputs.LIT_COLOR_ALBEDO_UUID_SUFFIX,
        derived_outputs.LIT_COLOR_EMISSION_UUID_SUFFIX,
    )
    # The job format carries no UV Set (the exported meshes already hold that layer's
    # UVs), so the export records it per group for the Cycles passes.
    bake_uv_layers = dict(getattr(prepared, "group_bake_uv_layers", None) or {})

    for group in getattr(job, "groups", []) or []:
        low_names = [
            getattr(mesh, "object_name", None) or getattr(mesh, "name", "")
            for mesh in getattr(group, "low_meshes", []) or []
        ]
        # A floater-faces piece ("<object>__fyr_floater", floater_faces.py) is part of its
        # object here: Cycles bakes the whole object, so on this route floater faces still
        # cast AO.
        high_names = list(
            dict.fromkeys(
                floater_faces.source_family(getattr(mesh, "object_name", None) or getattr(mesh, "name", ""))
                for mesh in getattr(group, "high_meshes", []) or []
            )
        )
        low_objects, missing_lows = _resolve_objects(low_names)
        high_objects, missing_highs = _resolve_objects(high_names)
        if missing_lows:
            errors.append(
                f"Cycles fallback skipped for group '{getattr(group, 'name', '')}': "
                f"missing low object(s): {', '.join(missing_lows)}"
            )
            continue
        if not low_objects:
            errors.append(
                f"Cycles fallback skipped for group '{getattr(group, 'name', '')}': no low objects"
            )
            continue

        cage_extrusion = _group_cage_extrusion(group)
        cage_object_name = _group_cage_object_name(group)
        # Read now: the job's mesh files are gone once the bake finishes.
        fitted_cages = () if cage_object_name else _group_fitted_cages(group, low_objects)
        if fitted_cages:
            # cage_offset is the hidden Distance control under an Automatic cage. The
            # fit's own reach is the uniform fallback and the Height encode range.
            cage_extrusion = max(cage.max_offset for cage in fitted_cages)
        group_name = str(getattr(group, "name", "") or "")
        uv_layer_name = str(bake_uv_layers.get(group_name, "") or "").strip()
        missing_uv = _lows_missing_uv_layer(low_objects, uv_layer_name)
        if missing_uv:
            errors.append(
                f"Cycles fallback skipped group '{group_name}': no UV map named "
                f"'{uv_layer_name}' on {', '.join(missing_uv)}"
            )
            continue
        # Scene estimates per (sources, sees-other-objects) pair: every map of a group
        # syncs the same objects, so the meshes and textures are measured once.
        scene_estimates: dict = {}
        for output in getattr(group, "outputs", []) or []:
            map_type = str(getattr(output, "map_type", "") or "").strip().upper()
            if str(getattr(output, "map_uuid", "") or "").endswith(lit_color_source_suffixes):
                continue
            output_path = getattr(output, "path", None)
            lit_color_final = (
                lit_color_final_by_source.get(os.path.normcase(os.path.abspath(str(output_path))))
                if output_path and map_type == constants.MAP_LIGHTING
                else None
            )
            if lit_color_final:
                map_type = constants.MAP_LIT_COLOR
            component_config = map_configs.get(str(getattr(output, "map_uuid", "") or ""))
            component = str(getattr(component_config, "lighting_component", "") or "").strip().upper()
            component_type = (
                {
                    "DIRECT": constants.MAP_DIRECT_LIGHTING,
                    "INDIRECT": constants.MAP_INDIRECT_LIGHTING,
                    "SPECULAR": constants.MAP_SPECULAR_LIGHTING,
                }.get(component)
                if map_type == constants.MAP_LIGHTING
                else None
            )
            if requested is not None and map_type not in requested and not lit_color_final:
                # Job map rows are MAP_MATERIAL; outputs are MATERIAL_ALBEDO / etc.
                material_requested = any(
                    value == constants.MAP_MATERIAL or str(value).startswith("MATERIAL")
                    for value in requested
                )
                if not (map_type.startswith("MATERIAL") and material_requested):
                    continue
            if lit_color_final:
                output_path = lit_color_final
            if component_type:
                map_type = component_type
            if not output_path:
                continue
            strategy = cycles_map_strategy(map_type)
            if strategy is None:
                errors.append(
                    f"Cycles fallback does not support map '{map_type}' "
                    f"for group '{getattr(group, 'name', '')}': {unsupported_cycles_reason(map_type)}"
                )
                continue
            if strategy.requires_highs and missing_highs:
                errors.append(
                    f"Cycles fallback skipped {map_type} for group "
                    f"'{getattr(group, 'name', '')}': missing high object(s): "
                    f"{', '.join(missing_highs)}"
                )
                continue
            if strategy.requires_highs and not high_objects:
                errors.append(
                    f"Cycles fallback skipped {map_type} for group "
                    f"'{getattr(group, 'name', '')}': no high objects"
                )
                continue
            map_uuid = str(getattr(output, "map_uuid", "") or "")
            map_config = map_configs.get(map_uuid)
            probe_distance = 0.0
            thickness_encode = DEFAULT_THICKNESS_ENCODE
            emit_attribute: tuple = ()
            if map_config is not None:
                if map_type == constants.MAP_ATTRIBUTE:
                    emit_attribute = (
                        str(getattr(map_config, "attribute_name", "") or ""),
                        float(getattr(map_config, "attribute_range_min", 0.0) or 0.0),
                        float(getattr(map_config, "attribute_range_max", 1.0)),
                    )
                if map_type == constants.MAP_BENT_NORMAL:
                    probe_distance = float(getattr(map_config, "ao_distance", 0.0) or 0.0)
                elif map_type in {constants.MAP_DENSITY, constants.MAP_THICKNESS}:
                    probe_distance = float(getattr(map_config, "thickness_distance", 0.0) or 0.0)
                if map_type == constants.MAP_THICKNESS:
                    thickness_encode = (
                        float(getattr(map_config, "thickness_min_distance", 0.0) or 0.0),
                        float(getattr(map_config, "thickness_scale", 1.0) or 1.0),
                        float(getattr(map_config, "thickness_gamma", 1.0) or 1.0),
                    )
            map_normal_space = str(
                getattr(map_config, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)
                or constants.MAP_NORMAL_SPACE_TANGENT
            )
            passes = cycles_map_pass_count(map_type, map_normal_space)
            try:
                udim_tile, uv_offset_u, uv_offset_v = _uv_offset_for_udim_tile(
                    getattr(output, "udim_tile", 0)
                )
            except Exception as exc:
                errors.append(
                    f"Cycles fallback skipped {map_type} for group "
                    f"'{getattr(group, 'name', '')}': invalid UDIM tile "
                    f"{getattr(output, 'udim_tile', 0)!r} ({exc})"
                )
                continue
            step_sources = high_objects if strategy.requires_highs else []
            step_width = int(getattr(output, "resolution_width", 0) or 0) or width
            step_height = int(getattr(output, "resolution_height", 0) or 0) or height
            step_soften = float(getattr(map_config, "output_soften", constants.DEFAULT_SOFTEN))
            try:
                sees_others = _strategy_may_see_other_objects(
                    strategy, _collect_materials(step_sources or low_objects)
                )
                estimate_key = (bool(step_sources), sees_others)
                if estimate_key not in scene_estimates:
                    scene_estimates[estimate_key] = _projection_scene_bytes(
                        strategy, low_objects, step_sources, cage_object_name
                    )
                strip_plan = plan_projection_strips(
                    strategy=strategy,
                    map_type=map_type,
                    target_objects=low_objects,
                    source_objects=step_sources,
                    width=step_width,
                    height=step_height,
                    margin=margin,
                    soften=step_soften,
                    output_path=output_path,
                    bit_depth=bit_depth,
                    cage_object_name=cage_object_name,
                    group_name=group_name,
                    scene_bytes=scene_estimates[estimate_key],
                    memory=memory,
                )
            except cycles_memory.CyclesMemoryError as exc:
                errors.append(str(exc))
                continue
            strip_count = strip_plan.count
            steps.append(
                CyclesBakeStep(
                    group_name=str(getattr(group, "name", "") or ""),
                    only_material=str(getattr(group, "low_material", "") or ""),
                    map_type=map_type,
                    map_uuid=map_uuid,
                    output_path=str(output_path),
                    target_objects=low_objects,
                    source_objects=step_sources,
                    width=step_width,
                    height=step_height,
                    margin=margin,
                    cage_extrusion=cage_extrusion,
                    cage_object_name=cage_object_name,
                    samples=_cycles_sample_count(getattr(map_config, "samples", 0)),
                    approximate=bool(strategy.approximate),
                    note=str(strategy.note or ""),
                    normal_space=map_normal_space,
                    probe_distance=probe_distance,
                    emit_attribute=emit_attribute,
                    thickness_encode=thickness_encode,
                    # Every strip runs every pass, so progress weights stay honest.
                    passes=passes * strip_count,
                    udim_tile=udim_tile,
                    uv_offset_u=uv_offset_u,
                    uv_offset_v=uv_offset_v,
                    flip_green=bool(getattr(map_config, "flip_green", False))
                    if map_type in _FLIP_GREEN_MAP_TYPES
                    else False,
                    bit_depth=bit_depth,
                    # The addon already resolved project-vs-override before the job was
                    # built, so the job's per-map value IS the effective Soften.
                    soften=step_soften,
                    strip_rows=0 if strip_plan.single else int(strip_plan.strip_rows),
                    strips=strip_count,
                    shadow_hidden_objects=_ao_shadow_hidden_objects(group, map_type, step_sources),
                    opacity_masked_objects=_opacity_masked_objects(job, group, step_sources),
                    fitted_cages=fitted_cages if step_sources else (),
                    uv_layer_name=uv_layer_name,
                )
            )

    _rank_shared_texture_set_outputs(steps)
    return CyclesBakePlan(steps, errors, device, device_note)


def _lows_missing_uv_layer(low_objects, uv_layer_name: str) -> list[str]:
    """Names of the lows without the group's UV Set (none when no UV Set is set)."""
    if not uv_layer_name:
        return []
    missing = []
    for low in low_objects or ():
        layers = getattr(getattr(low, "data", None), "uv_layers", None)
        if layers is None or layers.get(uv_layer_name) is None:
            missing.append(str(getattr(low, "name", "?")))
    return missing


def _output_key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path or "")))


def _rank_shared_texture_set_outputs(steps) -> None:
    """Mark the steps that must composite into a file an earlier group wrote.

    Groups in one texture set share every output file. Each Cycles step baked its own
    whole image and saved it over the path, so only the LAST group of a set survived:
    on BakeTester3 the Skull and Jaw islands came back empty, leaving Teeth alone.
    """
    groups_by_path: dict[str, list[str]] = {}
    lows_by_path: dict[str, list] = {}
    for step in steps:
        key = _output_key(step.output_path)
        names = groups_by_path.setdefault(key, [])
        if step.group_name not in names:
            names.append(step.group_name)
            lows_by_path.setdefault(key, []).extend(step.target_objects or [])
    for step in steps:
        key = _output_key(step.output_path)
        names = groups_by_path.get(key) or []
        if len(names) < 2:
            continue
        step.texture_set_rank = names.index(step.group_name)
        step.texture_set_lows = tuple(lows_by_path.get(key) or ())


def _texture_set_pass_path(output_path) -> Path:
    """Where a later texture-set member bakes before it is composited into the set."""
    path = Path(output_path)
    return path.with_name(f"{path.stem}.fyr_group_pass{path.suffix}")


def _composite_into_texture_set(
    output_path, pass_path, *, target_objects, set_lows, margin: int, udim_tile: int, uv_layer_name: str = ""
) -> None:
    """Take this group's texels (its islands plus its own margin) from ``pass_path``.

    The same rule the per-group material passes use (export.composite_group_texels):
    inside every set member's islands only the owner writes; outside all of them a
    texel the earlier groups left empty takes this pass's dilation.
    """
    import bpy

    from . import export

    output_path = Path(output_path)
    pass_path = Path(pass_path)
    if not output_path.is_file():
        # Every earlier member failed: this pass is the set's first content.
        os.replace(str(pass_path), str(output_path))
        return
    probe = bpy.data.images.load(str(pass_path), check_existing=False)
    try:
        width, height = (int(value) for value in probe.size)
    finally:
        image_cleanup.remove_image_when_safe(probe, reason="texture set probe")
    # The islands live in the layer the passes rasterized: the UV Set, else active_render.
    with low_material_subset.object_scope(
        list(target_objects or ()) + list(set_lows or ()), low_material_subset.cycles_only_material()
    ):
        mask = export.rasterize_low_uv_mask(
            target_objects,
            width,
            height,
            uv_layer_name=uv_layer_name,
            use_active_render=True,
            dilate_texels=int(margin),
            udim_tile=udim_tile,
        )
        union = export.rasterize_low_uv_mask(
            set_lows, width, height, uv_layer_name=uv_layer_name, use_active_render=True, udim_tile=udim_tile
        )
    if mask is None or not export.composite_group_texels(
        str(output_path), str(pass_path), mask, island_union=union
    ):
        raise RuntimeError(
            f"could not merge this group into the shared texture set file {output_path.name}"
        )


def run_cycles_projection_step(
    step: CyclesBakeStep,
    *,
    device: str = "CPU",
    on_progress: ProgressCallback | None = None,
) -> str | None:
    """Bake one planned step. Returns an error string, or None on success."""
    try:
        if on_progress:
            on_progress(step.label)
        bake_projection_map(**_step_bake_kwargs(step, device=device, on_progress=on_progress))
    except Exception as exc:
        return cycles_step_error(step, exc)
    return None


def _step_bake_kwargs(step: CyclesBakeStep, *, device: str, on_progress: ProgressCallback | None) -> dict:
    low_material_subset.set_cycles_only_material(step.only_material)
    return {
        "target_objects": step.target_objects,
        "source_objects": step.source_objects,
        "map_type": step.map_type,
        "width": step.width,
        "height": step.height,
        "output_path": step.output_path,
        "margin": step.margin,
        "cage_extrusion": step.cage_extrusion,
        "cage_object_name": step.cage_object_name,
        "samples": step.samples,
        "normal_space": step.normal_space,
        "probe_distance": step.probe_distance,
        "emit_attribute": tuple(getattr(step, "emit_attribute", ()) or ()),
        "thickness_encode": step.thickness_encode,
        "on_progress": on_progress,
        "device": device,
        "uv_offset_u": step.uv_offset_u,
        "uv_offset_v": step.uv_offset_v,
        "soften": step.soften,
        "flip_green": step.flip_green,
        "bit_depth": step.bit_depth,
        "strip_rows": int(getattr(step, "strip_rows", 0) or 0),
        "group_name": step.group_name,
        "shadow_hidden_objects": tuple(getattr(step, "shadow_hidden_objects", ()) or ()),
        "opacity_masked_objects": tuple(getattr(step, "opacity_masked_objects", ()) or ()),
        "fitted_cages": tuple(getattr(step, "fitted_cages", ()) or ()),
        "texture_set_rank": int(getattr(step, "texture_set_rank", 0) or 0),
        "texture_set_lows": tuple(getattr(step, "texture_set_lows", ()) or ()),
        "udim_tile": int(getattr(step, "udim_tile", 0) or 0),
        "uv_layer_name": str(getattr(step, "uv_layer_name", "") or ""),
    }


def cycles_step_error(step, exc) -> str:
    """The error line a failed planned step reports (both drivers use this)."""
    return f"Cycles bake failed for {step.group_name}/{step.map_type}: {exc}"


def start_cycles_projection_job(
    step: CyclesBakeStep,
    *,
    device: str = "CPU",
    on_progress: ProgressCallback | None = None,
) -> CyclesMapJob:
    """A pass-by-pass job for one planned step (the modal driver's unit of work).

    Same parameters :func:`run_cycles_projection_step` bakes the step with; raises
    if the step cannot be baked at all (unsupported map, missing objects).
    """
    return CyclesMapJob(**_step_bake_kwargs(step, device=device, on_progress=on_progress))


def execute_cycles_projection_fallback(
    prepared,
    context,
    *,
    map_types=None,
    on_progress: ProgressCallback | None = None,
) -> list[str]:
    """Bake prepared job outputs through Cycles for supported projection maps.

    Synchronous driver over :func:`plan_cycles_projection`. Returns a list of error
    strings (empty on full success for the supported set). Unsupported map types in
    the request are reported as errors so the caller can surface an honest failure
    instead of silently dropping them.

    This is the HEADLESS driver. ``bpy.ops.object.bake`` runs with no execution context
    here, so Blender's main thread is held for the whole run: no progress, no redraw, no
    Esc. Anything with a window must step the plan through
    ``MASTER_BAKER_OT_cycles_bake_step`` instead (see
    ``operators._start_cycles_handoff_async`` and ``operators._run_cycles_primary_bake``).
    """
    del context  # device/engine come from add-on preferences, not scene context
    plan = plan_cycles_projection(prepared, map_types=map_types)
    errors = list(plan.errors)
    if not plan.steps:
        if not errors:
            errors.append(
                "Cycles fallback produced no bake steps for the requested maps"
            )
        return errors
    if plan.device_note and on_progress:
        on_progress(plan.device_note)
    for step in plan.steps:
        error = run_cycles_projection_step(step, device=plan.device, on_progress=on_progress)
        if error:
            errors.append(error)
    return errors
