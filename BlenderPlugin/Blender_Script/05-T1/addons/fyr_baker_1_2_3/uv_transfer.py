from __future__ import annotations

"""Quality-checked topology-changing UV transfer using Blender's native modifier."""

from dataclasses import dataclass
import math
import uuid


@dataclass(frozen=True)
class TransferDiagnostics:
    confidence: str
    coverage: float
    maximum_distance: float
    percentile_95_distance: float
    normal_mismatch_fraction: float
    ambiguous_faces: int
    degenerate_faces: int
    max_distance: float


@dataclass(frozen=True)
class SurfaceTransferResult:
    values: tuple[tuple[float, float], ...]
    diagnostics: TransferDiagnostics


def _bbox_diagonal(mesh) -> float:
    if not mesh.vertices:
        return 0.0
    minimum = [min(float(vertex.co[axis]) for vertex in mesh.vertices) for axis in range(3)]
    maximum = [max(float(vertex.co[axis]) for vertex in mesh.vertices) for axis in range(3)]
    return math.sqrt(sum((maximum[axis] - minimum[axis]) ** 2 for axis in range(3)))


def _uv_island_ids(mesh, layer):
    parent = list(range(len(mesh.polygons)))

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    edge_sides = {}
    for polygon in mesh.polygons:
        loops = list(polygon.loop_indices)
        for index, loop0 in enumerate(loops):
            loop1 = loops[(index + 1) % len(loops)]
            v0, v1 = mesh.loops[loop0].vertex_index, mesh.loops[loop1].vertex_index
            edge_sides.setdefault(tuple(sorted((v0, v1))), []).append((polygon.index, loop0, loop1, v0, v1))
    for sides in edge_sides.values():
        for first_index in range(len(sides)):
            for second_index in range(first_index + 1, len(sides)):
                a, b = sides[first_index], sides[second_index]
                a0, a1 = layer.data[a[1]].uv, layer.data[a[2]].uv
                b0, b1 = layer.data[b[1]].uv, layer.data[b[2]].uv
                if a[3] == b[3] and a[4] == b[4]:
                    matches = (a0 - b0).length <= 1e-7 and (a1 - b1).length <= 1e-7
                else:
                    matches = (a0 - b1).length <= 1e-7 and (a1 - b0).length <= 1e-7
                if matches:
                    union(a[0], b[0])
    roots = {}
    result = []
    for polygon in mesh.polygons:
        root = find(polygon.index)
        if root not in roots:
            roots[root] = len(roots)
        result.append(roots[root])
    return result


def preflight_surface_transfer(source_mesh, destination_mesh, *, max_distance: float | None = None):
    from mathutils.bvhtree import BVHTree  # type: ignore

    source_layer = getattr(source_mesh.uv_layers, "active", None)
    if source_layer is None:
        raise ValueError("The UV snapshot payload has no active UV layer")
    source_vertices = [tuple(float(value) for value in vertex.co) for vertex in source_mesh.vertices]
    source_polygons = [tuple(int(value) for value in polygon.vertices) for polygon in source_mesh.polygons]
    if not source_vertices or not source_polygons or not destination_mesh.polygons:
        raise ValueError("Source and destination meshes need non-empty surfaces")
    bvh = BVHTree.FromPolygons(source_vertices, source_polygons, all_triangles=False)
    scale = max(_bbox_diagonal(source_mesh), _bbox_diagonal(destination_mesh), 1e-6)
    limit = float(max_distance) if max_distance is not None and max_distance > 0 else scale * 0.02
    island_ids = _uv_island_ids(source_mesh, source_layer)

    distances = []
    misses = normal_mismatches = ambiguous_faces = degenerate = 0
    for polygon in destination_mesh.polygons:
        if float(polygon.area) <= 1e-16:
            degenerate += 1
            continue
        source_faces = set()
        points = [destination_mesh.vertices[index].co.copy() for index in polygon.vertices]
        points.append(polygon.center.copy())
        for point in points:
            location, source_normal, source_index, distance = bvh.find_nearest(point, limit)
            if location is None or source_index is None or distance is None:
                misses += 1
                continue
            distance = float(distance)
            distances.append(distance)
            source_faces.add(int(source_index))
            if source_normal is not None and float(polygon.normal.dot(source_normal)) < 0.5:
                normal_mismatches += 1
        resolved_islands = {island_ids[index] for index in source_faces if 0 <= index < len(island_ids)}
        if len(resolved_islands) > 1:
            ambiguous_faces += 1

    sample_count = len(distances) + misses
    coverage = len(distances) / sample_count if sample_count else 0.0
    ordered = sorted(distances)
    p95 = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))] if ordered else math.inf
    max_observed = ordered[-1] if ordered else math.inf
    mismatch_fraction = normal_mismatches / max(1, len(distances))
    confidence = classify_confidence(coverage, bool(ordered), mismatch_fraction, ambiguous_faces, degenerate)
    return TransferDiagnostics(
        confidence, coverage, max_observed, p95, mismatch_fraction,
        ambiguous_faces, degenerate, limit,
    )


def classify_confidence(
    coverage: float,
    any_sampled: bool,
    mismatch_fraction: float,
    ambiguous_faces: int,
    degenerate_faces: int,
) -> str:
    """HIGH / REVIEW / BLOCKED for a proximity transfer.

    Zero-area faces are skipped by the sampler, so they cannot corrupt the result;
    they used to force BLOCKED, which made one stray degenerate triangle on an
    imported mesh refuse the whole restore with a message about coverage. They now
    only lower the confidence to REVIEW (the transfer still writes a NEW layer and
    never replaces the current one at REVIEW).
    """
    if coverage < 0.90 or not any_sampled:
        return "BLOCKED"
    if coverage < 0.99 or mismatch_fraction > 0.10 or ambiguous_faces > 0 or degenerate_faces > 0:
        return "REVIEW"
    return "HIGH"


def blocked_reason(diagnostics: TransferDiagnostics) -> str:
    """Why a transfer is BLOCKED, naming the cause and what to change."""
    if diagnostics.confidence != "BLOCKED":
        return ""
    limit = f"{diagnostics.max_distance:.6g}"
    if not math.isfinite(diagnostics.maximum_distance):
        return (
            f"no face of the current mesh lies within {limit} local units of the snapshot "
            "surface. Raise Maximum Transfer Distance or capture a snapshot from a closer mesh"
        )
    return (
        f"only {diagnostics.coverage:.1%} of the surface is within {limit} local units of the "
        "snapshot (90% is needed). Raise Maximum Transfer Distance or capture a snapshot from a "
        "closer mesh"
    )


def surface_transfer(snapshot, destination_obj, depsgraph, *, max_distance: float | None = None):
    import bpy  # type: ignore

    source_mesh = snapshot.payload_mesh
    destination_mesh = destination_obj.data
    diagnostics = preflight_surface_transfer(source_mesh, destination_mesh, max_distance=max_distance)
    if diagnostics.confidence == "BLOCKED":
        raise ValueError(blocked_reason(diagnostics))

    token = uuid.uuid4().hex
    # Every temporary datablock is built INSIDE the try. They used to be created ahead
    # of it, so the MemoryError destination_mesh.copy() can raise on a heavy mesh (an
    # expected path - the operator catches it) leaked all four into the .blend. The
    # leaked source_obj also pinned snapshot.payload_mesh, so delete_snapshot saw
    # users != 0 and skipped removal: the artist deleted the snapshot, was told it
    # worked, and the payload mesh stayed resident with no UI left to reach it.
    collection = None
    source_obj = None
    destination_temp_mesh = None
    destination_temp = None
    evaluated_mesh = None
    evaluated_owner = None
    try:
        collection = bpy.data.collections.new(f".FyrBaker_UVTransfer_{token}")
        source_obj = destination_obj.copy()
        source_obj.name = f".FyrBaker_UVTransferSource_{token}"
        source_obj.data = source_mesh
        source_obj.animation_data_clear()
        source_obj.modifiers.clear()
        source_obj.constraints.clear()
        source_obj.parent = None
        destination_temp_mesh = destination_mesh.copy()
        destination_temp = destination_obj.copy()
        destination_temp.name = f".FyrBaker_UVTransferDestination_{token}"
        destination_temp.data = destination_temp_mesh
        destination_temp.animation_data_clear()
        destination_temp.modifiers.clear()
        destination_temp.constraints.clear()
        destination_temp.parent = None
        source_obj.matrix_world.identity()
        destination_temp.matrix_world.identity()
        bpy.context.scene.collection.children.link(collection)
        collection.objects.link(source_obj)
        collection.objects.link(destination_temp)
        source_mesh.uv_layers.active = source_mesh.uv_layers.get(str(snapshot.uv_layer_name))
        while destination_temp_mesh.uv_layers:
            destination_temp_mesh.uv_layers.remove(destination_temp_mesh.uv_layers[0])
        target_layer = destination_temp_mesh.uv_layers.new(name=str(snapshot.uv_layer_name))
        destination_temp_mesh.uv_layers.active = target_layer
        modifier = destination_temp.modifiers.new(name=f".FyrBaker_UVTransfer_{token}", type="DATA_TRANSFER")
        modifier.object = source_obj
        modifier.use_object_transform = False
        modifier.use_loop_data = True
        modifier.data_types_loops = {"UV"}
        modifier.loop_mapping = "POLYINTERP_NEAREST"
        modifier.layers_uv_select_src = str(snapshot.uv_layer_name)
        modifier.layers_uv_select_dst = "NAME"
        modifier.mix_mode = "REPLACE"
        modifier.islands_precision = 0.02
        modifier.use_max_distance = True
        modifier.max_distance = diagnostics.max_distance
        bpy.context.view_layer.update()
        evaluated_owner = destination_temp.evaluated_get(depsgraph)
        evaluated_mesh = evaluated_owner.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        result_layer = evaluated_mesh.uv_layers.get(target_layer.name)
        if result_layer is None or len(result_layer.data) != len(destination_mesh.loops):
            raise RuntimeError("Blender Data Transfer did not produce a complete UV layer")
        values = tuple((float(item.uv[0]), float(item.uv[1])) for item in result_layer.data)
        if not all(math.isfinite(value) for uv in values for value in uv):
            raise RuntimeError("Blender Data Transfer produced non-finite UV coordinates")
        return SurfaceTransferResult(values, diagnostics)
    finally:
        if evaluated_mesh is not None and evaluated_owner is not None:
            evaluated_owner.to_mesh_clear()
        for obj in (destination_temp, source_obj):
            if obj is not None and obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        if destination_temp_mesh is not None and destination_temp_mesh.name in bpy.data.meshes:
            bpy.data.meshes.remove(destination_temp_mesh)
        if collection is not None and collection.name in bpy.data.collections:
            bpy.data.collections.remove(collection)
