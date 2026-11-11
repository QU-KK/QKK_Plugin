from __future__ import annotations

"""Seam-relationship-aware UV preparation.

The planning core in this module deliberately has no bpy dependency.  Blender mesh
data is adapted by the operator, while tests can feed compact :class:`UvMeshInput`
records directly.  Coordinates are optimized in texel space; returned values are UVs.
"""

from dataclasses import dataclass, field
import itertools
import math
from collections import defaultdict, deque
from typing import Iterable, Sequence


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class UvTriangleInput:
    loops: tuple[int, int, int]
    face_index: int


@dataclass(frozen=True)
class UvFaceInput:
    loops: tuple[int, ...]


@dataclass
class UvMeshInput:
    object_id: str
    domain: str
    uv_layer_name: str
    uvs: list[Vec2]
    loop_vertices: list[int]
    faces: list[UvFaceInput]
    triangles: list[UvTriangleInput]
    world_vertices: list[Vec3]
    face_normals: list[Vec3]


# Clearance an optimised island must keep: to the tile border and to other islands.
_MIN_BORDER_CLEARANCE_PX = 1.0
_MIN_ISLAND_CLEARANCE_PX = 2.0

@dataclass(frozen=True)
class UvOptimizationLimits:
    max_local_adjustment_px: float = 1.0
    max_rotation_deg: float = 3.0
    axis_threshold_deg: float = 3.0
    min_triangle_area_px2: float = 0.1
    min_area_ratio: float = 0.8
    min_edge_length_px: float = 0.1


@dataclass
class IslandPlan:
    island_id: str
    object_id: str
    domain: str
    loops: tuple[int, ...]
    stack_id: str
    locked_reason: str = ""
    rotation_deg: float = 0.0
    translation_px: Vec2 = (0.0, 0.0)
    local_adjustments: int = 0


@dataclass(frozen=True)
class SeamSidePlan:
    island_id: str
    object_id: str
    loop0: int
    loop1: int
    reversed: bool = False
    geometric_length: float = 0.0


@dataclass
class SeamChainPlan:
    seam_id: str
    sides: tuple[SeamSidePlan, ...]
    cross_object: bool = False
    component_id: str = ""


@dataclass
class UvOptimizationPlan:
    updated_uvs: dict[str, list[Vec2]] = field(default_factory=dict)
    islands: list[IslandPlan] = field(default_factory=list)
    seams: list[SeamChainPlan] = field(default_factory=list)
    optimized_components: int = 0
    optimized_islands: int = 0
    preserved_stacks: int = 0
    skipped_partial_overlaps: int = 0
    skipped_degenerate: int = 0
    skipped_unsafe: int = 0
    skipped_reasons: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.optimized_islands > 0


def mesh_input_from_blender_object(obj, uv_layer_name: str, domain: str, depsgraph=None) -> UvMeshInput:
    """Adapt a Blender mesh without retaining RNA references in the planner.

    The evaluated mesh may deform positions, but it must preserve the writable
    source loop/vertex correspondence.  Generative topology is rejected here,
    before any proposal or datablock copy is made.
    """
    mesh = getattr(obj, "data", None)
    if mesh is None or getattr(obj, "type", None) != "MESH":
        raise ValueError("not a mesh object")
    uv_layers = getattr(mesh, "uv_layers", None)
    layer = uv_layers.get(uv_layer_name) if uv_layer_name else getattr(uv_layers, "active", None)
    if layer is None:
        raise ValueError(f"UV layer '{uv_layer_name or 'active'}' is unavailable")

    evaluated_mesh = None
    evaluated_owner = None
    geometry_mesh = mesh
    try:
        if depsgraph is not None and hasattr(obj, "evaluated_get"):
            evaluated_owner = obj.evaluated_get(depsgraph)
            evaluated_mesh = evaluated_owner.to_mesh()
            geometry_mesh = evaluated_mesh
            source_loop_vertices = [int(loop.vertex_index) for loop in mesh.loops]
            evaluated_loop_vertices = [int(loop.vertex_index) for loop in geometry_mesh.loops]
            if (
                len(geometry_mesh.vertices) != len(mesh.vertices)
                or len(geometry_mesh.polygons) != len(mesh.polygons)
                or source_loop_vertices != evaluated_loop_vertices
            ):
                raise ValueError("evaluated modifiers change writable UV topology")

        mesh.calc_loop_triangles()
        loop_count = len(mesh.loops)
        flat_uvs = [0.0] * (loop_count * 2)
        try:
            layer.data.foreach_get("uv", flat_uvs)
            uvs = [(flat_uvs[index], flat_uvs[index + 1]) for index in range(0, len(flat_uvs), 2)]
        except Exception:
            uvs = [(float(item.uv[0]), float(item.uv[1])) for item in layer.data]

        matrix = getattr(obj, "matrix_world", None)
        world_vertices = []
        for vertex in geometry_mesh.vertices:
            co = vertex.co
            point = matrix @ co if matrix is not None else co
            world_vertices.append((float(point[0]), float(point[1]), float(point[2])))

        normal_matrix = None
        try:
            normal_matrix = matrix.to_3x3().inverted().transposed() if matrix is not None else None
        except Exception:
            normal_matrix = matrix.to_3x3() if matrix is not None else None
        face_normals = []
        for polygon in geometry_mesh.polygons:
            normal = normal_matrix @ polygon.normal if normal_matrix is not None else polygon.normal
            try:
                normal.normalize()
            except Exception:
                pass
            face_normals.append((float(normal[0]), float(normal[1]), float(normal[2])))

        return UvMeshInput(
            object_id=str(getattr(obj, "name_full", None) or getattr(obj, "name", "Mesh")),
            domain=str(domain),
            uv_layer_name=str(layer.name),
            uvs=uvs,
            loop_vertices=[int(loop.vertex_index) for loop in mesh.loops],
            faces=[UvFaceInput(tuple(int(index) for index in polygon.loop_indices)) for polygon in mesh.polygons],
            triangles=[
                UvTriangleInput(tuple(int(index) for index in triangle.loops), int(triangle.polygon_index))
                for triangle in mesh.loop_triangles
            ],
            world_vertices=world_vertices,
            face_normals=face_normals,
        )
    finally:
        if evaluated_mesh is not None and evaluated_owner is not None:
            evaluated_owner.to_mesh_clear()


@dataclass
class _HalfEdge:
    object_id: str
    face_index: int
    loop0: int
    loop1: int
    vertex0: int
    vertex1: int
    island_id: str = ""
    open_boundary: bool = False


@dataclass
class _Island:
    island_id: str
    mesh: UvMeshInput
    face_indices: set[int]
    loops: set[int]
    triangles: list[UvTriangleInput]
    boundary: list[_HalfEdge]
    locked_reason: str = ""
    stack_id: str = ""


@dataclass(frozen=True)
class _Transform:
    angle: float = 0.0
    dx: float = 0.0
    dy: float = 0.0


class _UnionFind:
    def __init__(self, items: Iterable):
        self.parent = {item: item for item in items}

    def find(self, item):
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _sub2(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def _dot2(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _len2(a: Vec2) -> float:
    return math.hypot(a[0], a[1])


def _sub3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot3(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len3(a: Vec3) -> float:
    return math.sqrt(_dot3(a, a))


def _uv_to_px(uv: Vec2, width: int, height: int) -> Vec2:
    return (uv[0] * width - 0.5, uv[1] * height - 0.5)


def _px_to_uv(px: Vec2, width: int, height: int) -> Vec2:
    return ((px[0] + 0.5) / width, (px[1] + 0.5) / height)


def _close2(a: Vec2, b: Vec2, epsilon: float = 1e-7) -> bool:
    return abs(a[0] - b[0]) <= epsilon and abs(a[1] - b[1]) <= epsilon


def _edge_uv_matches(a: _HalfEdge, b: _HalfEdge, meshes: dict[str, UvMeshInput]) -> bool:
    auv, buv = meshes[a.object_id].uvs, meshes[b.object_id].uvs
    a0, a1 = auv[a.loop0], auv[a.loop1]
    b0, b1 = buv[b.loop0], buv[b.loop1]
    if a.vertex0 == b.vertex0 and a.vertex1 == b.vertex1:
        return _close2(a0, b0) and _close2(a1, b1)
    return _close2(a0, b1) and _close2(a1, b0)


def _face_half_edges(mesh: UvMeshInput) -> tuple[list[_HalfEdge], dict[tuple[int, int], list[_HalfEdge]]]:
    edges: list[_HalfEdge] = []
    by_geometry: dict[tuple[int, int], list[_HalfEdge]] = defaultdict(list)
    for face_index, face in enumerate(mesh.faces):
        loops = face.loops
        for index, loop0 in enumerate(loops):
            loop1 = loops[(index + 1) % len(loops)]
            v0 = mesh.loop_vertices[loop0]
            v1 = mesh.loop_vertices[loop1]
            edge = _HalfEdge(mesh.object_id, face_index, loop0, loop1, v0, v1)
            edges.append(edge)
            by_geometry[tuple(sorted((v0, v1)))].append(edge)
    for members in by_geometry.values():
        if len(members) == 1:
            members[0].open_boundary = True
    return edges, by_geometry


def _build_islands(mesh: UvMeshInput) -> tuple[list[_Island], list[_HalfEdge], dict[tuple[int, int], list[_HalfEdge]]]:
    edges, by_geometry = _face_half_edges(mesh)
    uf = _UnionFind(range(len(mesh.faces)))
    meshes = {mesh.object_id: mesh}
    for members in by_geometry.values():
        for a, b in itertools.combinations(members, 2):
            if _edge_uv_matches(a, b, meshes):
                uf.union(a.face_index, b.face_index)

    faces_by_root: dict[int, set[int]] = defaultdict(set)
    for face_index in range(len(mesh.faces)):
        faces_by_root[uf.find(face_index)].add(face_index)
    islands: list[_Island] = []
    face_to_island: dict[int, _Island] = {}
    for ordinal, face_indices in enumerate(sorted(faces_by_root.values(), key=lambda v: min(v))):
        island_id = f"{mesh.object_id}:{ordinal}"
        loops = {loop for face_index in face_indices for loop in mesh.faces[face_index].loops}
        triangles = [triangle for triangle in mesh.triangles if triangle.face_index in face_indices]
        island = _Island(island_id, mesh, face_indices, loops, triangles, [])
        islands.append(island)
        for face_index in face_indices:
            face_to_island[face_index] = island
    for edge in edges:
        edge.island_id = face_to_island[edge.face_index].island_id
        members = by_geometry[tuple(sorted((edge.vertex0, edge.vertex1)))]
        if edge.open_boundary or any(member.island_id != edge.island_id for member in members):
            face_to_island[edge.face_index].boundary.append(edge)
    return islands, edges, by_geometry


def _signed_area(a: Vec2, b: Vec2, c: Vec2) -> float:
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _orient(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Vec2, b: Vec2, p: Vec2, eps: float = 1e-6) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
        and abs(_orient(a, b, p)) <= eps
    )


def _segments_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2, *, proper: bool = False) -> bool:
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    eps = 1e-7
    if proper:
        return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
            (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
        )
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    ):
        return True
    return any((abs(o) <= eps and _on_segment(x, y, p)) for o, x, y, p in (
        (o1, a, b, c), (o2, a, b, d), (o3, c, d, a), (o4, c, d, b)
    ))


def _point_in_triangle(p: Vec2, tri: tuple[Vec2, Vec2, Vec2], *, strict: bool = False) -> bool:
    a, b, c = tri
    values = (_orient(a, b, p), _orient(b, c, p), _orient(c, a, p))
    eps = 1e-7
    if strict:
        return all(value > eps for value in values) or all(value < -eps for value in values)
    return all(value >= -eps for value in values) or all(value <= eps for value in values)


def _triangles_overlap_positive(a: tuple[Vec2, Vec2, Vec2], b: tuple[Vec2, Vec2, Vec2]) -> bool:
    for i in range(3):
        for j in range(3):
            if _segments_intersect(a[i], a[(i + 1) % 3], b[j], b[(j + 1) % 3], proper=True):
                return True
    return any(_point_in_triangle(point, b, strict=True) for point in a) or any(
        _point_in_triangle(point, a, strict=True) for point in b
    )


def _point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    edge = _sub2(b, a)
    denom = _dot2(edge, edge)
    if denom <= 1e-20:
        return _len2(_sub2(p, a))
    t = max(0.0, min(1.0, _dot2(_sub2(p, a), edge) / denom))
    return _len2(_sub2(p, (a[0] + edge[0] * t, a[1] + edge[1] * t)))


def _segment_distance(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> float:
    if _segments_intersect(a, b, c, d):
        return 0.0
    return min(
        _point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b), _point_segment_distance(d, a, b),
    )


def _boundary_signature(island: _Island, width: int, height: int) -> tuple:
    segments = []
    for edge in island.boundary:
        a = _uv_to_px(island.mesh.uvs[edge.loop0], width, height)
        b = _uv_to_px(island.mesh.uvs[edge.loop1], width, height)
        qa = (round(a[0], 3), round(a[1], 3))
        qb = (round(b[0], 3), round(b[1], 3))
        segments.append(tuple(sorted((qa, qb))))
    # Merge collinear subdivisions so an exact stack remains recognizable when
    # one copy has extra boundary vertices.
    changed = True
    while changed:
        changed = False
        for i, first in enumerate(segments):
            if changed:
                break
            for j in range(i + 1, len(segments)):
                second = segments[j]
                shared = set(first) & set(second)
                if len(shared) != 1:
                    continue
                joint = next(iter(shared))
                outer_a = first[0] if first[1] == joint else first[1]
                outer_b = second[0] if second[1] == joint else second[1]
                if abs(_orient(outer_a, joint, outer_b)) > 1e-4:
                    continue
                replacement = tuple(sorted((outer_a, outer_b)))
                segments = [segment for k, segment in enumerate(segments) if k not in {i, j}]
                segments.append(replacement)
                changed = True
                break
    return tuple(sorted(segments))


def _triangle_points(island: _Island, uvs: Sequence[Vec2], width: int, height: int):
    for triangle in island.triangles:
        yield tuple(_uv_to_px(uvs[loop], width, height) for loop in triangle.loops)


def _island_px_triangles(island: _Island, uvs: Sequence[Vec2], width: int, height: int):
    """Triangles in pixel space with their bounding boxes, computed once per island."""
    result = []
    for triangle in island.triangles:
        points = tuple(_uv_to_px(uvs[loop], width, height) for loop in triangle.loops)
        xs = (points[0][0], points[1][0], points[2][0])
        ys = (points[0][1], points[1][1], points[2][1])
        result.append((points, min(xs), max(xs), min(ys), max(ys)))
    return result


def _boxes_bounds(boxes):
    return (
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        min(box[3] for box in boxes),
        max(box[4] for box in boxes),
    )


def _islands_overlap(a: _Island, b: _Island, uvs_by_object: dict[str, Sequence[Vec2]], width: int, height: int) -> bool:
    atris = _island_px_triangles(a, uvs_by_object[a.mesh.object_id], width, height)
    btris = _island_px_triangles(b, uvs_by_object[b.mesh.object_id], width, height)
    if not atris or not btris:
        return False
    # Island-level and per-triangle bounding-box rejection. These use the same
    # comparisons as the exact per-pair test below, so the answer is unchanged;
    # only the number of triangle pairs visited drops (most islands are disjoint).
    aminx_all, amaxx_all, aminy_all, amaxy_all = _boxes_bounds(atris)
    bminx_all, bmaxx_all, bminy_all, bmaxy_all = _boxes_bounds(btris)
    if amaxx_all <= bminx_all or bmaxx_all <= aminx_all or amaxy_all <= bminy_all or bmaxy_all <= aminy_all:
        return False
    for at, aminx, amaxx, aminy, amaxy in atris:
        if amaxx <= bminx_all or bmaxx_all <= aminx or amaxy <= bminy_all or bmaxy_all <= aminy:
            continue
        for bt, bminx, bmaxx, bminy, bmaxy in btris:
            if amaxx <= bminx or bmaxx <= aminx:
                continue
            if amaxy <= bminy or bmaxy <= aminy:
                continue
            if _triangles_overlap_positive(at, bt):
                return True
    return False


def _segment_boxes(uvs: Sequence[Vec2], boundary, width: int, height: int):
    segments = []
    for edge in boundary:
        p0 = _uv_to_px(uvs[edge.loop0], width, height)
        p1 = _uv_to_px(uvs[edge.loop1], width, height)
        segments.append((p0, p1, min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1])))
    return segments


def _box_gap(p, q) -> float:
    """Lower bound on the distance between anything inside box p and anything inside box q."""
    dx = max(0.0, p[2] - q[3], q[2] - p[3])
    dy = max(0.0, p[4] - q[5], q[4] - p[5])
    return math.hypot(dx, dy)


def _island_clearance(a: _Island, b: _Island, uvs_by_object: dict[str, Sequence[Vec2]], width: int, height: int) -> float:
    result = math.inf
    asegs = _segment_boxes(uvs_by_object[a.mesh.object_id], a.boundary, width, height)
    bsegs = _segment_boxes(uvs_by_object[b.mesh.object_id], b.boundary, width, height)
    if not asegs or not bsegs:
        return result
    # Bounding-box gaps are lower bounds on the true segment distance, so a pair
    # whose bound already meets the running minimum cannot lower it. The tiny
    # slack keeps float rounding in the bound from ever skipping a true minimum.
    b_all = (None, None, min(s[2] for s in bsegs), max(s[3] for s in bsegs), min(s[4] for s in bsegs), max(s[5] for s in bsegs))
    for aseg in asegs:
        if _box_gap(aseg, b_all) >= result + 1e-9:
            continue
        a0, a1 = aseg[0], aseg[1]
        for bseg in bsegs:
            if _box_gap(aseg, bseg) >= result + 1e-9:
                continue
            result = min(result, _segment_distance(a0, a1, bseg[0], bseg[1]))
            if result <= 0.0:
                return 0.0
    return result


def _edge_angle_delta(a: Vec2, b: Vec2) -> float:
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    quarter = math.pi * 0.5
    return ((angle + quarter * 0.5) % quarter) - quarter * 0.5


def _phase_distance(value: float) -> float:
    # Pixel boundaries are n-0.5 in the x=uW-0.5 coordinate system.
    return abs((value + 0.5) - round(value + 0.5))


def _centroid_for_islands(islands: Sequence[_Island], px_uvs: dict[str, list[Vec2]]) -> Vec2:
    points = [px_uvs[island.mesh.object_id][loop] for island in islands for loop in island.loops]
    if not points:
        return (0.0, 0.0)
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _transform_point(point: Vec2, transform: _Transform, center: Vec2) -> Vec2:
    if abs(transform.angle) <= 1e-15:
        return (point[0] + transform.dx, point[1] + transform.dy)
    cs, sn = math.cos(transform.angle), math.sin(transform.angle)
    x, y = point[0] - center[0], point[1] - center[1]
    return (center[0] + x * cs - y * sn + transform.dx, center[1] + x * sn + y * cs + transform.dy)


def _wrap_half(value: float) -> float:
    """Wrap a texel offset into [-0.5, 0.5): the shortest move to the same phase."""
    return (value + 0.5) % 1.0 - 0.5


def _candidate_transforms(
    node_islands: Sequence[_Island],
    seam_edges: Sequence[_HalfEdge],
    px_uvs,
    limits,
    node_id: str = "",
    relations: Sequence[Sequence[_HalfEdge]] = (),
    island_to_node=None,
) -> list[_Transform]:
    center = _centroid_for_islands(node_islands, px_uvs)
    # A rotation moves the island's rim by radius * angle. Keep that inside the
    # same texel budget as translations: the user is promised "1 texel", and a
    # 3 degree turn of a 250 px island used to throw its rim 13 px and then turn
    # it back on the next run.
    radius = 0.0
    for island in node_islands:
        for loop in island.loops:
            radius = max(radius, _len2(_sub2(px_uvs[island.mesh.object_id][loop], center)))
    max_angle = math.radians(limits.max_rotation_deg)
    if radius > 1e-6:
        max_angle = min(max_angle, math.atan2(limits.max_local_adjustment_px, radius))
    angles = {0.0}
    weighted = []
    for edge in seam_edges:
        a = px_uvs[edge.object_id][edge.loop0]
        b = px_uvs[edge.object_id][edge.loop1]
        delta = _edge_angle_delta(a, b)
        if abs(delta) <= max_angle + 1e-9:
            weighted.append((-delta, _len2(_sub2(b, a))))
            angles.add(round(-delta, 10))
    if weighted:
        total = sum(weight for _, weight in weighted)
        mean = sum(angle * weight for angle, weight in weighted) / max(total, 1e-12)
        if abs(mean) <= max_angle:
            angles.add(round(mean, 10))

    candidates = set()
    for angle in sorted(angles):
        transformed_edges = []
        for edge in seam_edges:
            a = _transform_point(px_uvs[edge.object_id][edge.loop0], _Transform(angle), center)
            b = _transform_point(px_uvs[edge.object_id][edge.loop1], _Transform(angle), center)
            transformed_edges.append((a, b))
        dx_values, dy_values = [0.0], [0.0]
        for a, b in transformed_edges:
            delta = _edge_angle_delta(a, b)
            if abs(math.degrees(delta)) <= 0.75:
                # ``_edge_angle_delta`` is modulo 90 degrees, so the original
                # edge vector decides which grid axis the candidate reached.
                if abs(b[0] - a[0]) >= abs(b[1] - a[1]):
                    target = round(((a[1] + b[1]) * 0.5) + 0.5) - 0.5
                    dy_values.append(target - (a[1] + b[1]) * 0.5)
                else:
                    target = round(((a[0] + b[0]) * 0.5) + 0.5) - 0.5
                    dx_values.append(target - (a[0] + b[0]) * 0.5)
        dx_values.append(sorted(dx_values)[len(dx_values) // 2])
        dy_values.append(sorted(dy_values)[len(dy_values) // 2])
        dx_values = sorted({round(value, 4) for value in dx_values})
        dy_values = sorted({round(value, 4) for value in dy_values})
        for dx in dx_values:
            for dy in dy_values:
                if abs(dx) <= limits.max_local_adjustment_px + 1e-6 and abs(dy) <= limits.max_local_adjustment_px + 1e-6:
                    candidates.add((angle, round(dx, 8), round(dy, 8)))
    return [_Transform(*values) for values in sorted(candidates)]


def _circular_mean_offset(offsets: Sequence[float]) -> float:
    """Mean of texel offsets that live on a circle of length one texel."""
    if not offsets:
        return 0.0
    sx = sum(math.cos(2.0 * math.pi * value) for value in offsets)
    sy = sum(math.sin(2.0 * math.pi * value) for value in offsets)
    if abs(sx) < 1e-12 and abs(sy) < 1e-12:
        return 0.0
    return math.atan2(sy, sx) / (2.0 * math.pi)


def _seam_endpoint_loops(node_id: str, node_edges) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    for edge in node_edges.get(node_id, ()):
        seen.add((edge.object_id, edge.loop0))
        seen.add((edge.object_id, edge.loop1))
    return sorted(seen)


def _free_seam_endpoint_loops(node_id: str, node_edges, transforms, px_uvs, centers) -> list[tuple[str, int]]:
    """Seam endpoints not on an axis-aligned edge.

    Axis-aligned edges are snapped locally by _rectify_relationship_boundaries;
    if the rigid centring counted them too, the two stages would pull the island
    to different places every pass and never settle (measured 2026-09-06: 0.33 px
    of motion on every re-run). Falls back to all endpoints when there are no
    free ones."""
    free: set[tuple[str, int]] = set()
    everything: set[tuple[str, int]] = set()
    transform = transforms[node_id]
    center = centers[node_id]
    for edge in node_edges.get(node_id, ()):
        a = _transform_point(px_uvs[edge.object_id][edge.loop0], transform, center)
        b = _transform_point(px_uvs[edge.object_id][edge.loop1], transform, center)
        pair = ((edge.object_id, edge.loop0), (edge.object_id, edge.loop1))
        everything.update(pair)
        if abs(_edge_angle_delta(a, b)) > math.radians(0.75):
            free.update(pair)
    return sorted(free or everything)


def _seam_phase_energy(component, node_edges, transforms, px_uvs, centers) -> float:
    """How far the seam endpoints of these islands sit from texel boundaries, squared.

    Both sides of a seam are pulled to the same lattice (texel corners at
    half-integer pixel coordinates), so when the energy is low the two sides of
    every seam edge rasterise the same way and the seam is quiet. The lattice is
    also what the axis-aligned snapping targets, so the stages agree."""
    energy = 0.0
    for node in component:
        transform = transforms[node]
        center = centers[node]
        for object_id, loop in _free_seam_endpoint_loops(node, node_edges, transforms, px_uvs, centers):
            point = _transform_point(px_uvs[object_id][loop], transform, center)
            energy += _wrap_half(point[0] - 0.5) ** 2 + _wrap_half(point[1] - 0.5) ** 2
    return energy


def _refine_component_translations(component, trial, node_edges, node_islands, px_uvs, centers, limits):
    """Slide every movable island so its seam endpoints sit as close as a rigid
    translation allows to texel boundaries.

    Closed form: per axis, the circular mean over the island's seam endpoints of
    their offset to the nearest boundary. Applying it zeroes that mean, so a
    second run produces no motion. Islands with a partial overlap stay put."""
    limit = float(limits.max_local_adjustment_px)
    refined = dict(trial)
    for node in sorted(component):
        if any(island.locked_reason for island in node_islands[node]):
            continue
        endpoints = _free_seam_endpoint_loops(node, node_edges, trial, px_uvs, centers)
        if not endpoints:
            continue
        offsets_x, offsets_y = [], []
        for object_id, loop in endpoints:
            point = _transform_point(px_uvs[object_id][loop], trial[node], centers[node])
            offsets_x.append(_wrap_half(0.5 - point[0]))
            offsets_y.append(_wrap_half(0.5 - point[1]))
        dx = _circular_mean_offset(offsets_x)
        dy = _circular_mean_offset(offsets_y)
        new_dx = max(-limit, min(limit, trial[node].dx + dx))
        new_dy = max(-limit, min(limit, trial[node].dy + dy))
        if abs(new_dx - trial[node].dx) > 1e-9 or abs(new_dy - trial[node].dy) > 1e-9:
            refined[node] = _Transform(trial[node].angle, new_dx, new_dy)
    return refined


def _node_score(node_id: str, transform: _Transform, node_islands, node_edges, px_uvs, centers) -> float:
    center = centers[node_id]
    score = abs(transform.angle) * 0.05 + math.hypot(transform.dx, transform.dy) * 0.01
    for edge in node_edges.get(node_id, ()):
        a = _transform_point(px_uvs[edge.object_id][edge.loop0], transform, center)
        b = _transform_point(px_uvs[edge.object_id][edge.loop1], transform, center)
        delta = abs(_edge_angle_delta(a, b))
        score += delta * _len2(_sub2(b, a)) * 4.0
        if delta <= math.radians(0.75):
            score += (_phase_distance(a[1]) + _phase_distance(b[1])) * 2.0
    return score


def _relationship_score(relation: Sequence[_HalfEdge], transforms, island_to_node, px_uvs, centers) -> float:
    samples = []
    for edge in relation:
        node_id = island_to_node[edge.island_id]
        transform = transforms[node_id]
        a = _transform_point(px_uvs[edge.object_id][edge.loop0], transform, centers[node_id])
        b = _transform_point(px_uvs[edge.object_id][edge.loop1], transform, centers[node_id])
        direction = _sub2(b, a)
        angle_delta = _edge_angle_delta(a, b)
        endpoint_phase = sorted(((a[0] + 0.5) % 1.0, (b[0] + 0.5) % 1.0, (a[1] + 0.5) % 1.0, (b[1] + 0.5) % 1.0))
        samples.append((angle_delta, endpoint_phase, _len2(direction)))
    if len(samples) < 2:
        return 0.0
    result = 0.0
    reference = samples[0]
    for sample in samples[1:]:
        # Orientations are compared modulo 90 degrees: horizontal vs vertical is clean,
        # while equally sloped diagonals get matching staircase behavior.
        result += abs(reference[0] - sample[0]) * min(reference[2], sample[2]) * 10.0
        result += sum(abs(a - b) for a, b in zip(reference[1], sample[1])) * 0.5
    return result


def _world_edge_key(mesh: UvMeshInput, edge: _HalfEdge, tolerance: float) -> tuple:
    a, b = mesh.world_vertices[edge.vertex0], mesh.world_vertices[edge.vertex1]
    qa = tuple(round(value / tolerance) for value in a)
    qb = tuple(round(value / tolerance) for value in b)
    return tuple(sorted((qa, qb)))


def _build_cross_object_relations(meshes, open_edges, position_tolerance) -> list[list[_HalfEdge]]:
    buckets: dict[tuple, list[_HalfEdge]] = defaultdict(list)
    mesh_by_id = {mesh.object_id: mesh for mesh in meshes}
    for edge in open_edges:
        buckets[_world_edge_key(mesh_by_id[edge.object_id], edge, position_tolerance)].append(edge)
    result = []
    for members in buckets.values():
        if len(members) != 2 or members[0].object_id == members[1].object_id:
            continue
        a, b = members
        ma, mb = mesh_by_id[a.object_id], mesh_by_id[b.object_id]
        a0, a1 = ma.world_vertices[a.vertex0], ma.world_vertices[a.vertex1]
        b0, b1 = mb.world_vertices[b.vertex0], mb.world_vertices[b.vertex1]
        direct = max(_len3(_sub3(a0, b0)), _len3(_sub3(a1, b1)))
        reverse = max(_len3(_sub3(a0, b1)), _len3(_sub3(a1, b0)))
        if min(direct, reverse) > position_tolerance:
            continue
        la, lb = _len3(_sub3(a1, a0)), _len3(_sub3(b1, b0))
        if max(la, lb) <= 1e-20 or abs(la - lb) / max(la, lb) > 1e-5:
            continue
        na = ma.face_normals[a.face_index] if a.face_index < len(ma.face_normals) else (0.0, 0.0, 1.0)
        nb = mb.face_normals[b.face_index] if b.face_index < len(mb.face_normals) else (0.0, 0.0, 1.0)
        if _dot3(na, nb) < -0.25:
            continue
        result.append([a, b])
    return result


def _side_direction_against(reference: _HalfEdge, edge: _HalfEdge, mesh_by_id) -> bool:
    """True when ``edge`` traverses the common geometry opposite ``reference``."""
    if reference.object_id == edge.object_id:
        if reference.vertex0 == edge.vertex0 and reference.vertex1 == edge.vertex1:
            return False
        if reference.vertex0 == edge.vertex1 and reference.vertex1 == edge.vertex0:
            return True
    reference_mesh, edge_mesh = mesh_by_id[reference.object_id], mesh_by_id[edge.object_id]
    r0 = reference_mesh.world_vertices[reference.vertex0]
    r1 = reference_mesh.world_vertices[reference.vertex1]
    e0 = edge_mesh.world_vertices[edge.vertex0]
    e1 = edge_mesh.world_vertices[edge.vertex1]
    direct = _len3(_sub3(r0, e0)) + _len3(_sub3(r1, e1))
    reverse = _len3(_sub3(r0, e1)) + _len3(_sub3(r1, e0))
    return reverse < direct


def _component_sets(node_ids: Iterable[str], relations: Sequence[Sequence[_HalfEdge]], island_to_node) -> list[set[str]]:
    adjacency = {node_id: set() for node_id in node_ids}
    for relation in relations:
        nodes = {island_to_node[edge.island_id] for edge in relation}
        for node in nodes:
            adjacency[node].update(nodes - {node})
    seen, components = set(), []
    for start in sorted(adjacency):
        if start in seen:
            continue
        queue, component = deque([start]), set()
        while queue:
            node = queue.popleft()
            if node in component:
                continue
            component.add(node)
            queue.extend(sorted(adjacency[node] - component))
        seen.update(component)
        components.append(component)
    return components


def _apply_transforms(node_islands, transforms, centers, px_uvs):
    proposed = {object_id: list(values) for object_id, values in px_uvs.items()}
    for node_id, islands in node_islands.items():
        transform = transforms[node_id]
        center = centers[node_id]
        for island in islands:
            for loop in island.loops:
                proposed[island.mesh.object_id][loop] = _transform_point(
                    px_uvs[island.mesh.object_id][loop], transform, center
                )
    return proposed


def _uv_vertex_groups(islands: Sequence[_Island], px_uvs) -> dict[tuple[str, int], list[int]]:
    """(object_id, loop) -> every loop of the same island that sits on the same UV vertex.

    A UV vertex is one mesh vertex at one UV position; several face corners
    (loops) share it. Any snap applied to one corner must move all of them, or
    the island tears at that vertex (2026-09-06: one pass grew BakeTester3 from
    50 to 67 islands and created 18 overlaps that way)."""
    groups: dict[tuple[str, int], list[int]] = {}
    for island in islands:
        by_key: dict[tuple, list[int]] = defaultdict(list)
        uvs = px_uvs[island.mesh.object_id]
        vertices = island.mesh.loop_vertices
        for loop in island.loops:
            u, v = uvs[loop]
            by_key[(vertices[loop], round(u, 3), round(v, 3))].append(loop)
        for loops in by_key.values():
            for loop in loops:
                groups[(island.mesh.object_id, loop)] = loops
    return groups


def _rectify_relationship_boundaries(
    component, relations, island_to_node, proposed, limits, loop_groups=None, locked_nodes=(),
):
    constraints: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    changed = 0
    locked = set(locked_nodes or ())

    def group_of(object_id, loop):
        if loop_groups is None:
            return [loop]
        return loop_groups.get((object_id, loop), [loop])

    for relation in relations:
        if not ({island_to_node[edge.island_id] for edge in relation} & component):
            continue
        for edge in relation:
            node_id = island_to_node[edge.island_id]
            if node_id not in component:
                continue
            if node_id in locked:
                # A locked island (partial UV overlap) is pinned to the identity
                # transform so it cannot rotate or translate -- but that only stops
                # RIGID motion, and this pass writes individual loops. Snapping a
                # boundary loop of an island that overlaps another one moves UVs
                # inside the overlap the lock exists to protect, which is how a
                # "skipped" island still came back with edited texels.
                continue
            a = proposed[edge.object_id][edge.loop0]
            b = proposed[edge.object_id][edge.loop1]
            delta = abs(_edge_angle_delta(a, b))
            if delta <= math.radians(0.75):
                axis = 1 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 0
                value = (a[axis] + b[axis]) * 0.5
                target = round(value + 0.5) - 0.5
                if abs(target - a[axis]) <= limits.max_local_adjustment_px and abs(target - b[axis]) <= limits.max_local_adjustment_px:
                    # Key by UV vertex (its lowest loop), so every corner on that
                    # vertex receives one agreed target.
                    constraints[(edge.object_id, min(group_of(edge.object_id, edge.loop0)), axis)].append(target)
                    constraints[(edge.object_id, min(group_of(edge.object_id, edge.loop1)), axis)].append(target)
    for (object_id, loop, axis), targets in constraints.items():
        target = sum(targets) / len(targets)
        loops = group_of(object_id, loop)
        if any(abs(target - proposed[object_id][member][axis]) > limits.max_local_adjustment_px for member in loops):
            continue
        for member in loops:
            point = list(proposed[object_id][member])
            point[axis] = target
            proposed[object_id][member] = (point[0], point[1])
            changed += 1
    return changed


def _validate_component(component, node_islands, original, proposed, transforms, centers, width, height, margin, limits, stacks):
    affected = [island for node in component for island in node_islands[node]]
    for island in affected:
        node_id = island.stack_id or island.island_id
        transform = transforms[node_id]
        for triangle in island.triangles:
            before = [original[island.mesh.object_id][loop] for loop in triangle.loops]
            after = [proposed[island.mesh.object_id][loop] for loop in triangle.loops]
            if not all(math.isfinite(value) for point in after for value in point):
                return False, "non-finite UV", island.island_id
            area_before, area_after = _signed_area(*before), _signed_area(*after)
            if abs(area_before) < limits.min_triangle_area_px2:
                if island.locked_reason:
                    # A locked island never moves, so its slivers have nothing to
                    # check. Returning here vetoed the WHOLE component: on an 81-island
                    # panel, three boolean slivers on one face froze every island
                    # (2026-10-01), and the retry loop could not help because this test
                    # reads the original triangle, which parking the island leaves as is.
                    continue
                return False, "sub-texel triangle", island.island_id
            if area_before * area_after <= 0.0:
                return False, "triangle winding changed", island.island_id
            if abs(area_after) < limits.min_triangle_area_px2 or abs(area_after) < abs(area_before) * limits.min_area_ratio:
                return False, "triangle area reduced", island.island_id
            for index in range(3):
                if _len2(_sub2(after[index], after[(index + 1) % 3])) < limits.min_edge_length_px:
                    return False, "boundary edge collapsed", island.island_id
        # Preserve the tile occupied by every face corner.  This is stricter than a
        # centroid test and prevents a rotated corner leaking into a neighboring UDIM.
        for loop in island.loops:
            before, after = original[island.mesh.object_id][loop], proposed[island.mesh.object_id][loop]
            rigid = _transform_point(before, transform, centers[node_id])
            if _len2(_sub2(after, rigid)) > limits.max_local_adjustment_px + 1e-5:
                return False, "local adjustment exceeded", island.island_id
            before_tile = (math.floor((before[0] + 0.5) / width), math.floor((before[1] + 0.5) / height))
            after_tile = (math.floor((after[0] + 0.5) / width), math.floor((after[1] + 0.5) / height))
            if before_tile != after_tile:
                return False, "UDIM tile changed", island.island_id
        if island.loops:
            def border_clearance(points):
                distances = []
                for point in points:
                    local_x = (point[0] + 0.5) % width
                    local_y = (point[1] + 0.5) % height
                    distances.append(min(local_x, width - local_x, local_y, height - local_y))
                return min(distances)

            before_border = border_clearance([original[island.mesh.object_id][loop] for loop in island.loops])
            after_border = border_clearance([proposed[island.mesh.object_id][loop] for loop in island.loops])
            # An island may edge towards the tile border by its 1 texel budget as
            # long as it keeps a texel of clearance; requiring the full dilation
            # margin froze every island packed near the border (2026-09-06: 20 of
            # 50 islands on BakeTester3 were rejected here).
            if after_border + 1e-4 < min(before_border, _MIN_BORDER_CLEARANCE_PX):
                return False, "texture-border clearance reduced", island.island_id

    for stack in stacks:
        members = [island for island in stack if island in affected]
        if not members:
            continue
        reference = members[0]
        reference_points = sorted(
            proposed[reference.mesh.object_id][loop]
            for edge in reference.boundary for loop in (edge.loop0, edge.loop1)
        )
        for island in stack[1:]:
            points = sorted(
                proposed[island.mesh.object_id][loop]
                for edge in island.boundary for loop in (edge.loop0, edge.loop1)
            )
            if len(points) == len(reference_points) and any(
                _len2(_sub2(a, b)) > 0.001 for a, b in zip(reference_points, points)
            ):
                return False, "exact stack diverged", island.island_id

    affected_ids = {island.island_id for island in affected}
    all_islands = [island for islands in node_islands.values() for island in islands]
    orig_uv = {key: value for key, value in original.items()}
    prop_uv = {key: value for key, value in proposed.items()}
    for a, b in itertools.combinations(all_islands, 2):
        if a.mesh.domain != b.mesh.domain or not ({a.island_id, b.island_id} & affected_ids):
            continue
        same_stack = a.stack_id and a.stack_id == b.stack_id
        if same_stack:
            continue
        before_overlap = _islands_overlap(a, b, orig_uv, width, height)
        after_overlap = _islands_overlap(a, b, prop_uv, width, height)
        if after_overlap and not before_overlap:
            return False, "new UV overlap", (a.island_id if a.island_id in affected_ids else b.island_id)
        before_clearance = _island_clearance(a, b, orig_uv, width, height)
        if math.isfinite(before_clearance):
            # Same idea between islands: a texel-scale nudge may not bring two
            # islands closer than a couple of texels, but it need not preserve a
            # full double-margin gap that packed layouts never had.
            required = min(before_clearance, _MIN_ISLAND_CLEARANCE_PX)
            after_clearance = _island_clearance(a, b, prop_uv, width, height)
            if after_clearance + 1e-4 < required:
                return False, "dilation clearance reduced", (a.island_id if a.island_id in affected_ids else b.island_id)
    return True, "", ""


def plan_uv_seam_optimization(
    domains: Sequence[UvMeshInput],
    seam_graph=None,
    width: int = 1024,
    height: int = 1024,
    margin: int = 16,
    limits: UvOptimizationLimits | None = None,
) -> UvOptimizationPlan:
    """Build an atomic, seam-driven UV edit plan.

    ``seam_graph`` is reserved for callers that later need to inject explicit seam
    relationships.  Current Blender integration derives all relationships from the
    supplied topology and strict world-space boundary matching.
    """
    del seam_graph
    limits = limits or UvOptimizationLimits()
    width, height = max(1, int(width)), max(1, int(height))
    meshes = sorted(domains, key=lambda mesh: mesh.object_id)
    mesh_by_id = {mesh.object_id: mesh for mesh in meshes}
    plan = UvOptimizationPlan(updated_uvs={mesh.object_id: list(mesh.uvs) for mesh in meshes})
    if not meshes:
        return plan

    islands: list[_Island] = []
    geometric_maps = {}
    open_edges = []
    relations: list[list[_HalfEdge]] = []
    for mesh in meshes:
        mesh_islands, _edges, by_geometry = _build_islands(mesh)
        islands.extend(mesh_islands)
        geometric_maps[mesh.object_id] = by_geometry
        for members in by_geometry.values():
            if len(members) == 1:
                open_edges.extend(members)
            else:
                seam_members = []
                for edge in members:
                    if any(other.island_id != edge.island_id for other in members):
                        seam_members.append(edge)
                if len({edge.island_id for edge in seam_members}) >= 2:
                    relations.append(seam_members)

    world_points = [point for mesh in meshes for point in mesh.world_vertices]
    if world_points:
        mins = [min(point[axis] for point in world_points) for axis in range(3)]
        maxs = [max(point[axis] for point in world_points) for axis in range(3)]
        diagonal = _len3(tuple(maxs[i] - mins[i] for i in range(3)))
    else:
        diagonal = 1.0
    cross_relations = _build_cross_object_relations(meshes, open_edges, max(diagonal * 1e-6, 1e-7))
    relations.extend(cross_relations)

    # Exact footprint stacks are graph nodes.  Partial overlaps are locked before
    # optimization and remain fixed constraints for their seam-connected partners.
    signatures: dict[tuple[str, tuple], list[_Island]] = defaultdict(list)
    for island in islands:
        signatures[(island.mesh.domain, _boundary_signature(island, width, height))].append(island)
    stack_groups = [group for group in signatures.values() if len(group) > 1 and group[0].boundary]
    for ordinal, group in enumerate(stack_groups):
        stack_id = f"stack:{ordinal}"
        for island in group:
            island.stack_id = stack_id
    plan.preserved_stacks = len(stack_groups)

    original_uv = {mesh.object_id: list(mesh.uvs) for mesh in meshes}
    for a, b in itertools.combinations(islands, 2):
        if a.mesh.domain != b.mesh.domain or (a.stack_id and a.stack_id == b.stack_id):
            continue
        if _islands_overlap(a, b, original_uv, width, height):
            a.locked_reason = b.locked_reason = "partial UV overlap"
    plan.skipped_partial_overlaps = sum(1 for island in islands if island.locked_reason)

    node_islands: dict[str, list[_Island]] = defaultdict(list)
    island_to_node = {}
    for island in islands:
        node_id = island.stack_id or island.island_id
        node_islands[node_id].append(island)
        island_to_node[island.island_id] = node_id
    node_edges: dict[str, list[_HalfEdge]] = defaultdict(list)
    for relation in relations:
        for edge in relation:
            node_edges[island_to_node[edge.island_id]].append(edge)

    px_uvs = {
        mesh.object_id: [_uv_to_px(uv, width, height) for uv in mesh.uvs]
        for mesh in meshes
    }
    meshes_by_id = {mesh.object_id: mesh for mesh in meshes}
    # An island carrying a sub-texel triangle (boolean slivers, collapsed corners)
    # cannot be checked for winding or area change, so it stays where it is; its
    # seam partners still optimise around it, exactly like a partial overlap.
    for island in islands:
        if island.locked_reason:
            continue
        points = px_uvs[island.mesh.object_id]
        if any(
            abs(_signed_area(*(points[loop] for loop in triangle.loops))) < limits.min_triangle_area_px2
            for triangle in island.triangles
        ):
            island.locked_reason = "sub-texel triangle"
            plan.skipped_degenerate += 1
    loop_groups = _uv_vertex_groups(islands, px_uvs)
    centers = {node: _centroid_for_islands(members, px_uvs) for node, members in node_islands.items()}
    node_relations: dict[str, list[list[_HalfEdge]]] = defaultdict(list)
    for relation in relations:
        for node in {island_to_node[edge.island_id] for edge in relation}:
            node_relations[node].append(relation)
    candidates = {
        node: (
            _candidate_transforms(
                members, node_edges.get(node, ()), px_uvs, limits,
                node_id=node, relations=node_relations.get(node, ()), island_to_node=island_to_node,
            )
            or [_Transform()]
        )
        for node, members in node_islands.items()
    }
    locked_nodes = {
        node for node, members in node_islands.items()
        if any(island.locked_reason for island in members)
    }
    for node in locked_nodes:
        candidates[node] = [_Transform()]

    components = _component_sets(node_islands, relations, island_to_node)
    selected = {node: _Transform() for node in node_islands}
    all_proposed = {key: list(values) for key, values in px_uvs.items()}

    for component_index, component in enumerate(components):
        component_relations = [
            relation for relation in relations
            if {island_to_node[edge.island_id] for edge in relation} & component
        ]

        def score(transforms):
            total = sum(
                _node_score(node, transforms[node], node_islands, node_edges, px_uvs, centers)
                for node in component
            )
            total += sum(
                _relationship_score(relation, transforms, island_to_node, px_uvs, centers)
                for relation in component_relations
            )
            return total

        trial = dict(selected)
        before_score = score(trial)
        # A seam rotation is often beneficial only when both sides move together;
        # single-node coordinate descent cannot cross that intentional energy
        # barrier.  Seed it with deterministic component-wide angle proposals.
        best_seed, best_seed_score = dict(trial), before_score
        locally_best = dict(trial)
        for node in sorted(component):
            locally_best[node] = min(
                candidates[node],
                key=lambda candidate: (
                    _node_score(node, candidate, node_islands, node_edges, px_uvs, centers),
                    candidate.angle, candidate.dx, candidate.dy,
                ),
            )
        locally_best_score = score(locally_best)
        if locally_best_score < best_seed_score - 1e-8:
            best_seed, best_seed_score = locally_best, locally_best_score
        seed_angles = sorted({
            round(candidate.angle, 10)
            for node in component
            for candidate in candidates[node]
        })
        for seed_angle in seed_angles:
            seeded = dict(trial)
            for node in sorted(component):
                matching = [
                    candidate for candidate in candidates[node]
                    if abs(candidate.angle - seed_angle) <= 1e-9
                ]
                if matching:
                    seeded[node] = min(
                        matching,
                        key=lambda candidate: (
                            _node_score(node, candidate, node_islands, node_edges, px_uvs, centers),
                            candidate.angle,
                            candidate.dx,
                            candidate.dy,
                        ),
                    )
            seeded_score = score(seeded)
            if seeded_score < best_seed_score - 1e-8:
                best_seed, best_seed_score = seeded, seeded_score
        trial = best_seed
        for _pass in range(8):
            improved = False
            for node in sorted(component):
                best = trial[node]
                best_score = score(trial)
                for candidate in candidates[node]:
                    trial[node] = candidate
                    candidate_score = score(trial)
                    if candidate_score < best_score - 1e-8:
                        best, best_score, improved = candidate, candidate_score, True
                trial[node] = best
            if not improved:
                break
        after_score = score(trial)
        # Phase refinement for seams of any orientation (the candidate search above
        # only knows near-axis-aligned edges). Accepted when it lowers the seam
        # phase energy; the safety validation below still has the last word.
        energy_before = _seam_phase_energy(component, node_edges, trial, px_uvs, centers)
        refined = _refine_component_translations(component, trial, node_edges, node_islands, px_uvs, centers, limits)
        energy_after = _seam_phase_energy(component, node_edges, refined, px_uvs, centers)
        energy_improved = energy_after < energy_before - 1e-6
        if energy_improved:
            trial = refined
        if after_score >= before_score - 1e-8 and not energy_improved:
            continue

        # Validate; when one island breaks a rule, park that island (back to its
        # previous transform) and try again, so one packed island at the tile edge
        # does not veto every seam-connected neighbour.
        held_back: list[str] = []
        proposed = None
        valid, reason, last_reason = False, "", ""
        for _attempt in range(len(component) + 1):
            proposed = _apply_transforms(node_islands, trial, centers, px_uvs)
            _rectify_relationship_boundaries(
                component, component_relations, island_to_node, proposed, limits, loop_groups, locked_nodes,
            )
            valid, reason, offender = _validate_component(
                component, node_islands, px_uvs, proposed, trial, centers,
                width, height, margin, limits, stack_groups,
            )
            if valid:
                break
            node = island_to_node.get(offender)
            if node is None or node not in component or trial[node] == selected[node]:
                break
            trial[node] = selected[node]
            held_back.append(offender)
            last_reason = reason
        if not valid:
            plan.skipped_unsafe += len(component)
            plan.skipped_reasons.append(f"seam component {component_index + 1}: {reason}")
            continue
        if held_back:
            plan.skipped_unsafe += len(held_back)
            plan.skipped_reasons.append(f"seam component {component_index + 1}: {len(held_back)} island(s) held back ({last_reason or 'rule'})")
        if all(trial[node] == selected[node] for node in component):
            continue
        selected.update({node: trial[node] for node in component})
        for node in component:
            for island in node_islands[node]:
                for loop in island.loops:
                    all_proposed[island.mesh.object_id][loop] = proposed[island.mesh.object_id][loop]
        plan.optimized_components += 1
        changed_nodes = [
            node for node in component
            if any(
                _len2(_sub2(
                    proposed[island.mesh.object_id][loop],
                    px_uvs[island.mesh.object_id][loop],
                )) > 1e-7
                for island in node_islands[node]
                for loop in island.loops
            )
        ]
        plan.optimized_islands += sum(len(node_islands[node]) for node in changed_nodes)

    plan.updated_uvs = {
        object_id: [_px_to_uv(point, width, height) for point in points]
        for object_id, points in all_proposed.items()
    }
    for island in islands:
        node = island_to_node[island.island_id]
        transform = selected[node]
        plan.islands.append(IslandPlan(
            island_id=island.island_id,
            object_id=island.mesh.object_id,
            domain=island.mesh.domain,
            loops=tuple(sorted(island.loops)),
            stack_id=island.stack_id,
            locked_reason=island.locked_reason,
            rotation_deg=math.degrees(transform.angle),
            translation_px=(transform.dx, transform.dy),
        ))
    for ordinal, relation in enumerate(relations):
        nodes = sorted({island_to_node[edge.island_id] for edge in relation})
        component_id = next((f"component:{index}" for index, component in enumerate(components) if set(nodes) <= component), "")
        reference_edge = relation[0]
        plan.seams.append(SeamChainPlan(
            seam_id=f"seam:{ordinal}",
            sides=tuple(SeamSidePlan(
                edge.island_id,
                edge.object_id,
                edge.loop0,
                edge.loop1,
                _side_direction_against(reference_edge, edge, mesh_by_id),
                _len3(_sub3(
                    mesh_by_id[edge.object_id].world_vertices[edge.vertex1],
                    mesh_by_id[edge.object_id].world_vertices[edge.vertex0],
                )),
            ) for edge in relation),
            cross_object=len({edge.object_id for edge in relation}) > 1,
            component_id=component_id,
        ))
    return plan
