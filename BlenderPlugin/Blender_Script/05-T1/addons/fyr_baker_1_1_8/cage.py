from __future__ import annotations

from array import array
from dataclasses import dataclass, field
import functools
import itertools
import json
from pathlib import Path
import math
import subprocess
import tempfile
import zlib
import time

from mathutils import Vector

from . import rna_buffers
from . import cage_soup, matching, mesh_read, mesh_transport, naming, protocol

_TRIANGLE_EDGE_INDICES = ((0, 1), (1, 2), (2, 0))
_AUTO_CAGE_LOCAL_INFLATION_MAX_GAIN = 0.75


@dataclass(slots=True)
class TriangleCorner:
    source_position: Vector
    position: Vector
    uv: tuple[float, float]
    normal: Vector
    # Paint layer values of this corner (paint_sampling.OFFSET_ATTRIBUTE / SKEW_ATTRIBUTE),
    # None when the mesh carries no such layer. Filled by the low-mesh captures.
    paint_offset: float | None = None
    paint_skew: float | None = None


@dataclass(slots=True)
class TriangleData:
    object_name: str
    corners: tuple[TriangleCorner, TriangleCorner, TriangleCorner]


@dataclass(slots=True)
class DrawBuffers:
    fill_positions: list[tuple[float, float, float]]
    line_positions: list[tuple[float, float, float]]


@dataclass(slots=True)
class OffsetBatchBuffers:
    positions: list[tuple[float, float, float]]
    normals: list[tuple[float, float, float]]
    uvs: list[tuple[float, float]] = field(default_factory=list)
    # Per-vertex paint-offset multiplier from the paint layer (max(0, 1 + r)); the paint
    # shader multiplies it with the legacy canvas sample. Empty = 1 everywhere.
    paints: list[float] = field(default_factory=list)
    # Per-vertex RGBA colors; populated by skew field builders for gradient coloring.
    colors: list[tuple[float, float, float, float]] = field(default_factory=list)


def _normalized(vector: Vector) -> Vector:
    value = vector.copy()
    if value.length_squared != 0.0:
        value.normalize()
    return value


def is_conformal_3x3(rows) -> bool:
    """True when a 3x3 linear map is a rotation/mirror times one uniform scale.

    Only then does the point matrix carry normals correctly; anything else needs the
    inverse transpose. ``rows`` is any row-indexable 3x3 (mathutils Matrix, nested list).
    """
    cols = [[float(rows[r][c]) for r in range(3)] for c in range(3)]
    sq = [sum(v * v for v in col) for col in cols]
    scale = max(sq)
    if scale <= 0.0:
        return True
    tol = 1.0e-6 * scale
    if max(sq) - min(sq) > tol:
        return False
    for a, b in ((0, 1), (0, 2), (1, 2)):
        if abs(sum(x * y for x, y in zip(cols[a], cols[b]))) > tol:
            return False
    return True


_NORMAL_MATRIX_CACHE: dict = {}


def normal_matrix_3x3(matrix_world):
    """The 3x3 that carries an object-space normal to world space.

    Normals are covectors: under non-uniform scale or shear the point matrix tilts them
    toward the stretched axis (a key scaled 0.01/0.0098/0.0071 baked its Normal map
    against a frame tilted up to ~8 deg off Blender's shading normal, a visible seam at
    every edge). Conformal matrices keep the point matrix so their export stays
    bit-identical.
    """
    m = matrix_world.to_3x3()
    key = tuple(float(m[r][c]) for r in range(3) for c in range(3))
    cached = _NORMAL_MATRIX_CACHE.get(key)
    if cached is not None:
        return cached
    if not is_conformal_3x3(m):
        m = m.inverted_safe().transposed()
    if len(_NORMAL_MATRIX_CACHE) > 256:
        _NORMAL_MATRIX_CACHE.clear()
    _NORMAL_MATRIX_CACHE[key] = m
    return m


def _transformed_normal(matrix_world, vector) -> Vector:
    return _normalized(normal_matrix_3x3(matrix_world) @ vector)


def _vector_position_key(vector, digits: int = 6) -> tuple[float, float, float]:
    return (
        round(float(vector.x), digits),
        round(float(vector.y), digits),
        round(float(vector.z), digits),
    )


def _source_position_group_key(object_name: str, position: Vector, digits: int = 6) -> tuple[str, tuple[float, float, float]]:
    # _vector_position_key spelled out: this runs once per triangle corner of every
    # low (450k calls on a 300-group job), twice per fit.
    return (
        str(object_name or ""),
        (round(float(position.x), digits), round(float(position.y), digits), round(float(position.z), digits)),
    )


def _vector_dot(lhs: Vector, rhs: Vector) -> float:
    return float(lhs.x * rhs.x) + float(lhs.y * rhs.y) + float(lhs.z * rhs.z)


def _corner_uv(uv_layer, loop_index: int) -> tuple[float, float]:
    if uv_layer is None:
        return (0.0, 0.0)
    uv = uv_layer[loop_index].uv
    return (float(uv.x), float(uv.y))


def _loop_paint_layers(mesh):
    """(offset values, skew values) per loop from the mesh's paint layers, None if absent."""
    try:
        from . import paint_sampling

        offsets = paint_sampling.read_loop_values(mesh, paint_sampling.OFFSET_ATTRIBUTE)
    except Exception:
        return None, None
    # Paint Skew moved to per-texel correction maps (a175084d) and its corner layer went
    # with it. Importing that gone name here raised, the except above swallowed it, and
    # every overlay capture dropped the painted OFFSET too: a painted cage and its Cage
    # Coverage drew as unpainted as soon as the brush session ended.
    skew_attribute = getattr(paint_sampling, "SKEW_ATTRIBUTE", None)
    try:
        skews = paint_sampling.read_loop_values(mesh, skew_attribute) if skew_attribute else None
    except Exception:
        skews = None
    return (
        offsets.tolist() if offsets is not None else None,
        skews.tolist() if skews is not None else None,
    )


def _corner_paint_offset_multiplier(corner) -> float:
    value = getattr(corner, "paint_offset", None)
    return 1.0 if value is None else max(0.0, 1.0 + float(value))


def _resolve_uv_layer_data(mesh, uv_layer_name: str | None, *, object_name: str = "", required: bool = True):
    """UV data for *uv_layer_name*, else the active layer.

    ``required=False`` is for the viewport overlays: they ask for the group's bake
    UV Set so the paint canvas is sampled exactly where the bake samples it, but a
    name the mesh does not carry must fall back to the active layer instead of
    raising out of a draw handler (the bake path is the one that validates it).
    """
    uv_layers = getattr(mesh, "uv_layers", None)
    if uv_layers is None:
        return None
    if uv_layer_name:
        target_layer = uv_layers.get(uv_layer_name) if hasattr(uv_layers, "get") else None
        if target_layer is not None:
            return target_layer.data
        if required:
            owner = object_name or "Mesh"
            raise ValueError(f"{owner} is missing the requested UV set '{uv_layer_name}'")
    active_layer = getattr(uv_layers, "active", None)
    if active_layer is not None:
        return active_layer.data
    return None


def _mesh_rows_to_numpy(rows, components: int):
    import numpy as np

    if isinstance(rows, array):
        if len(rows) == 0:
            return np.empty((0, int(components)), dtype=np.float32)
        return np.frombuffer(rows, dtype=np.float32).reshape(-1, int(components)).copy()
    return np.asarray(rows, dtype=np.float32).reshape(-1, int(components))


def _normalized_rows_numpy(vectors):
    import numpy as np

    vector_lengths = np.sqrt(np.einsum('ij,ij->i', vectors, vectors))[:, None]
    safe_lengths = np.where(vector_lengths > 1.0e-10, vector_lengths, 1.0)
    normalized = vectors / safe_lengths
    return np.where(vector_lengths > 1.0e-10, normalized, vectors)


# One overlay rebuild reads the same low mesh through several captures (cage triangles, edge lines,
# the projection set). Inside field_solve_scope they share a single solve of the Smooth Cage field,
# keyed by the mesh's content (a checksum of its positions and triangle loops) and the matrix, so a
# mesh edit between rebuilds can never be served stale: the scope ends with the rebuild.
_FIELD_SOLVES: dict | None = None
_FIELD_SOLVES_DEPTH = 0


def field_solve_scope(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        global _FIELD_SOLVES, _FIELD_SOLVES_DEPTH
        if _FIELD_SOLVES_DEPTH == 0:
            _FIELD_SOLVES = {}
        _FIELD_SOLVES_DEPTH += 1
        try:
            return function(*args, **kwargs)
        finally:
            _FIELD_SOLVES_DEPTH -= 1
            if _FIELD_SOLVES_DEPTH == 0:
                _FIELD_SOLVES = None

    return wrapper


def _field_output(per_vertex, matrix_world, world_space, pointer_key, solves):
    """The solved world-space (V, 3) field as the caller wants it: world space as is, or carried
    back into object space (world = N @ local up to scale, so local = inv(N) @ world)."""
    import numpy as np

    if not world_space and matrix_world is not None:
        normal_rows = np.array([[float(v) for v in row] for row in normal_matrix_3x3(matrix_world)], dtype=np.float64)
        back = np.linalg.inv(normal_rows)
        result = _normalized_rows_numpy((per_vertex @ back.T).astype(np.float32, copy=False))
    else:
        result = per_vertex.astype(np.float32)
    if pointer_key is not None:
        solves[(pointer_key, bool(world_space))] = result
    return result


def _smooth_cage_vertex_field_numpy(mesh, matrix_world=None, world_space: bool = False):
    """The Smooth Cage direction at every vertex of ``mesh`` -- the backend's field (Toolbag's:
    vertices welded by position, unit geometric face normals of the triangles weighted by corner
    angle, an 8-pass fix-up that keeps the direction within 80 degrees of every incident face;
    see :func:`cage_soup.smooth_cage_field`) -- as a (V, 3) float32 array, or None when the mesh
    cannot be read in bulk (no loop triangles / foreach_get).

    The field is solved on the world-space triangles (the bake's), then returned in world space
    when ``world_space`` is set and otherwise carried back into object space, so a caller that
    transforms it with the normal matrix lands on the same world direction. Vertices outside
    every usable triangle, and welded points whose faces cancel, take the position-welded average
    of their split loop normals (the previous behaviour)."""
    import numpy as np

    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loops is None or vertices is None:
        return None
    # Inside a rebuild scope the mesh cannot change: the same evaluated mesh (its data pointer) under
    # the same matrix is the same field, with nothing re-read on a hit.
    solves = _FIELD_SOLVES
    pointer_key = None
    if solves is not None and callable(getattr(mesh, "as_pointer", None)):
        try:
            pointer_key = (
                "ptr",
                int(mesh.as_pointer()),
                len(vertices),
                len(loops),
                len(getattr(mesh, "polygons", ()) or ()),
                tuple(float(matrix_world[r][c]) for r in range(4) for c in range(4)) if matrix_world is not None else None,
            )
        except Exception:
            pointer_key = None
        if pointer_key is not None:
            cached = solves.get((pointer_key, bool(world_space)))
            if cached is not None:
                return cached
            solved = solves.get((pointer_key, "solve"))
            if solved is not None:
                return _field_output(solved, matrix_world, world_space, pointer_key, solves)
    calc = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc):
        calc()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    if loop_triangles is None:
        return None
    if not all(hasattr(collection, "foreach_get") for collection in (loops, vertices, loop_triangles)):
        return None
    vertex_count = len(vertices)
    loop_count = len(loops)
    triangle_count = len(loop_triangles)
    if vertex_count <= 0 or loop_count <= 0 or triangle_count <= 0:
        return None

    vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
    if not mesh_read.read_positions_flat(mesh, vertex_positions):
        vertices.foreach_get("co", vertex_positions)
    vertex_positions = vertex_positions.reshape(vertex_count, 3)

    loop_vertex = rna_buffers.empty_u32_for_rna(loop_count)
    if not mesh_read.read_corner_verts_flat(mesh, loop_vertex):
        corner_verts = getattr(mesh, "corner_verts", None)
        if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
            corner_verts.foreach_get("vertex", loop_vertex)
        else:
            loops.foreach_get("vertex_index", loop_vertex)
    loop_vertex = rna_buffers.as_i32(loop_vertex).astype(np.int64)

    loop_normals = np.empty(loop_count * 3, dtype=np.float32)
    if not mesh_read.read_corner_normals_flat(mesh, loop_normals):
        corner_normals = getattr(mesh, "corner_normals", None)
        if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
            corner_normals.foreach_get("vector", loop_normals)
        else:
            loops.foreach_get("normal", loop_normals)
    loop_normals = loop_normals.reshape(loop_count, 3)

    if mesh_read.is_all_triangles(mesh) and triangle_count * 3 == loop_count:
        # Triangle i is loops 3i..3i+2: nothing to read.
        triangle_loops = np.arange(loop_count, dtype=np.int64).reshape(triangle_count, 3)
    else:
        triangle_loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("loops", triangle_loops)
        triangle_loops = rna_buffers.as_i32(triangle_loops).astype(np.int64).reshape(triangle_count, 3)
    triangle_vertices = loop_vertex[triangle_loops]

    if matrix_world is not None:
        world_positions = _matrix_vector_f32(_matrix_rows_f32(matrix_world), vertex_positions)
        normal_rows = np.array([[float(v) for v in row] for row in normal_matrix_3x3(matrix_world)], dtype=np.float64)
    else:
        world_positions = vertex_positions
        normal_rows = np.eye(3, dtype=np.float64)

    solve_key = None
    if solves is not None and pointer_key is None:
        solve_key = (
            tuple(float(matrix_world[r][c]) for r in range(4) for c in range(4)) if matrix_world is not None else None,
            vertex_count,
            loop_count,
            triangle_count,
            zlib.crc32(vertex_positions.data),
            zlib.crc32(np.ascontiguousarray(triangle_loops).data),
            zlib.crc32(loop_normals.data),
            zlib.crc32(loop_vertex.data),
        )
    per_vertex = solves.get(solve_key) if solve_key is not None else None
    if per_vertex is None:
        keys = np.rint(world_positions.astype(np.float64) * 1_000_000.0).astype(np.int64)
        first, vertex_group = cage_soup.unique_rows(keys)
        group_count = int(first.shape[0])
        own_sum = loop_normals[triangle_loops].sum(1, dtype=np.float64) @ normal_rows.T
        direction, ok = cage_soup.smooth_cage_field(
            world_positions, triangle_vertices, own_sum, vertex_group, group_count
        )
        if not ok.all():
            # The previous average of the split normals, for the welded points the field leaves open.
            wide = loop_normals.astype(np.float64, copy=False) @ normal_rows.T
            group_of_loop = vertex_group[loop_vertex]
            fallback = np.stack(
                [np.bincount(group_of_loop, weights=wide[:, axis], minlength=group_count) for axis in range(3)],
                axis=1,
            )
            fallback = _normalized_rows_numpy(fallback.astype(np.float32, copy=False)).astype(np.float64)
            direction = np.where(ok[:, None], direction, fallback)
        per_vertex = direction[vertex_group]
        if solve_key is not None:
            solves[solve_key] = per_vertex
    if pointer_key is not None:
        solves[(pointer_key, "solve")] = per_vertex
    return _field_output(per_vertex, matrix_world, world_space, pointer_key, solves)


def _average_split_normal_groups_numpy(mesh, matrix_world=None, world_space: bool = False):
    """(averaged_normals, vertex_group_indices) of the Smooth Cage direction, or None when the
    mesh cannot be read in bulk (the caller then walks it in Python). Vertex ``v`` carries
    ``averaged_normals[vertex_group_indices[v]]`` (float32). With loop triangles available the
    direction is the backend's field (:func:`_smooth_cage_vertex_field_numpy`, one entry per
    vertex); without a matrix or loop triangles it is the position-welded average of the split
    normals (what the export still writes)."""
    import numpy as np

    field = None
    if matrix_world is not None:  # the export keeps the split-normal average (no matrix)
        try:
            field = _smooth_cage_vertex_field_numpy(mesh, matrix_world, world_space)
        except Exception:
            field = None
    if field is not None:
        return field, np.arange(field.shape[0], dtype=np.int64)
    return _average_split_normal_groups_loops_numpy(mesh)


def _average_split_normal_groups_loops_numpy(mesh):
    """The position-welded average of the split loop normals (the Smooth Cage direction before the
    backend's face-normal field): ``(averaged_normals, vertex_group_indices)`` or None."""
    import numpy as np

    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loops is None or vertices is None:
        return None
    if not all(hasattr(collection, "foreach_get") for collection in (loops, vertices)):
        return None

    vertex_count = len(vertices)
    loop_count = len(loops)
    if vertex_count <= 0 or loop_count <= 0:
        return None

    try:
        vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("co", vertex_positions)
        vertex_position_keys = np.rint(vertex_positions.reshape(vertex_count, 3) * 1_000_000.0).astype(np.int64, copy=False)

        loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
        corner_verts_cached = getattr(mesh, "corner_verts", None)
        if corner_verts_cached is not None and hasattr(corner_verts_cached, "foreach_get"):
            corner_verts_cached.foreach_get("vertex", loop_vertex_indices)
        else:
            loops.foreach_get("vertex_index", loop_vertex_indices)
        loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)

        loop_normals = np.empty(loop_count * 3, dtype=np.float32)
        corner_normals_cached = getattr(mesh, "corner_normals", None)
        if corner_normals_cached is not None and hasattr(corner_normals_cached, "foreach_get"):
            corner_normals_cached.foreach_get("vector", loop_normals)
        else:
            loops.foreach_get("normal", loop_normals)
        loop_normals = loop_normals.reshape(loop_count, 3)

        # Vertices at one position (rounded to 1e-6) share a group. The group numbering does
        # not matter: each group's normals are summed in loop order either way.
        _first, vertex_group_indices = cage_soup.unique_rows(vertex_position_keys)
        group_count = int(_first.shape[0])

        loop_group_indices = vertex_group_indices[loop_vertex_indices]
        wide_normals = loop_normals.astype(np.float64, copy=False)
        # np.bincount adds the weights of a bin one after the other in index order, in double:
        # the sums np.add.at gave.
        grouped_normals = np.stack(
            [np.bincount(loop_group_indices, weights=wide_normals[:, axis], minlength=group_count) for axis in range(3)],
            axis=1,
        )
        averaged_normals = _normalized_rows_numpy(grouped_normals.astype(np.float32, copy=False))
        return averaged_normals, vertex_group_indices
    except Exception:
        return None


def _try_build_average_split_normal_lookup_numpy(mesh, matrix_world=None) -> dict[int, Vector] | None:
    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loops is None or vertices is None:
        return None
    if not hasattr(loops, "foreach_get") or not hasattr(vertices, "foreach_get"):
        return None

    if len(vertices) <= 0 or len(loops) <= 0:
        return {}

    groups = _average_split_normal_groups_numpy(mesh, matrix_world)
    if groups is None:
        return None
    averaged_normals, vertex_group_indices = groups
    try:
        return {
            int(vertex_index): Vector(
                (
                    float(averaged_normals[group_index, 0]),
                    float(averaged_normals[group_index, 1]),
                    float(averaged_normals[group_index, 2]),
                )
            )
            for vertex_index, group_index in enumerate(vertex_group_indices.tolist())
        }
    except Exception:
        return None


_CONVEX_BRIDGE_SAME_NORMAL_COS = 0.9999  # ~0.8 deg: shading already continuous there
_CONVEX_BRIDGE_COPLANAR_COS = 0.99939  # ~2 deg: the same flat face, triangulated / n-gon


def _try_build_convex_bridged_corner_normals_numpy(mesh):
    """Per-loop projection normals for Smooth Cage off (backend v16).

    Every corner keeps its own split normal (soft edges continuous, hard edges split)
    EXCEPT across convex hard edges, where the loops sharing a welded position are
    bridged: the corner-angle-weighted average of the normals of the loops in this
    loop's smooth fan (joined across soft, coplanar or convex shared edges). Concave
    hard edges stay split. This is exactly what the backend traces along
    (compute_convex_bridged_corner_normals), so the drawn cage, the needles and the
    exported Automatic cage all follow the rays. Returns an (loop_count, 3) float32
    array, or None when the host mesh cannot serve the bulk reads (the caller then
    keeps the plain corner normals)."""
    import numpy as np

    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    polygons = getattr(mesh, "polygons", None)
    if loops is None or vertices is None or polygons is None:
        return None
    if not all(hasattr(collection, "foreach_get") for collection in (loops, vertices, polygons)):
        return None
    loop_count = len(loops)
    vertex_count = len(vertices)
    polygon_count = len(polygons)
    if loop_count <= 0 or vertex_count <= 0 or polygon_count <= 0:
        return None
    try:
        positions = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("co", positions)
        positions = positions.reshape(vertex_count, 3).astype(np.float64)

        loop_vertex = rna_buffers.empty_u32_for_rna(loop_count)
        corner_verts = getattr(mesh, "corner_verts", None)
        if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
            corner_verts.foreach_get("vertex", loop_vertex)
        else:
            loops.foreach_get("vertex_index", loop_vertex)
        loop_vertex = rna_buffers.as_i32(loop_vertex)

        loop_normals = np.empty(loop_count * 3, dtype=np.float32)
        corner_normals = getattr(mesh, "corner_normals", None)
        if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
            corner_normals.foreach_get("vector", loop_normals)
        else:
            loops.foreach_get("normal", loop_normals)
        loop_normals = loop_normals.reshape(loop_count, 3).astype(np.float64)

        loop_start = rna_buffers.empty_u32_for_rna(polygon_count)
        polygons.foreach_get("loop_start", loop_start)
        loop_start = rna_buffers.as_i32(loop_start)
        loop_total = rna_buffers.empty_u32_for_rna(polygon_count)
        polygons.foreach_get("loop_total", loop_total)
        loop_total = rna_buffers.as_i32(loop_total)
        if int(loop_total.sum()) != loop_count or bool(np.any(loop_total < 3)):
            return None
        polygon_order = np.argsort(loop_start, kind="stable")
        sorted_starts = loop_start[polygon_order]
        sorted_totals = loop_total[polygon_order]
        expected_starts = np.concatenate(([0], np.cumsum(sorted_totals)[:-1]))
        if not np.array_equal(sorted_starts, expected_starts):
            return None
        # loop -> polygon (loops of a polygon are consecutive from loop_start)
        loop_polygon = np.repeat(polygon_order, sorted_totals).astype(np.int32)
        poly_start = loop_start[loop_polygon]
        poly_total = loop_total[loop_polygon]
        local = np.arange(loop_count, dtype=np.int32) - poly_start
        loop_next = poly_start + (local + 1) % poly_total
        loop_prev = poly_start + (local - 1) % poly_total

        corner_position = positions[loop_vertex]
        edge_a = positions[loop_vertex[loop_next]] - corner_position
        edge_b = positions[loop_vertex[loop_prev]] - corner_position
        corner_angle = np.arctan2(
            np.linalg.norm(np.cross(edge_a, edge_b), axis=1), np.einsum("ij,ij->i", edge_a, edge_b)
        )
        corner_angle = np.where(np.isfinite(corner_angle), corner_angle, 0.0)

        # Geometric face normals from MeshPolygon.normal. NOT mesh.polygon_normals: on a
        # mesh with custom normals (FBX imports) Blender 5.2 serves something else there
        # (up to 0.7 off on 733 of 736 faces of a customer's shears), which flipped the
        # convex test and made this cage disagree with the backend's rays.
        polygon_normals = np.empty(polygon_count * 3, dtype=np.float32)
        polygons.foreach_get("normal", polygon_normals)
        polygon_normals = polygon_normals.reshape(polygon_count, 3).astype(np.float64)
        polygon_centers = np.zeros((polygon_count, 3), dtype=np.float64)
        np.add.at(polygon_centers, loop_polygon, corner_position)
        polygon_centers /= loop_total[:, None].astype(np.float64)

        bounds_diagonal = float(np.linalg.norm(positions.max(axis=0) - positions.min(axis=0)))
        if not bounds_diagonal > 0.0:
            return None
        tolerance = bounds_diagonal * 1.0e-6

        # Weld loops by vertex position (6 digits, like build_average_split_normal_lookup).
        position_keys = np.rint(positions * 1_000_000.0).astype(np.int64)
        view_dtype = np.dtype((np.void, position_keys.dtype.itemsize * 3))
        structured_keys = np.ascontiguousarray(position_keys).view(view_dtype).ravel()
        _unique_keys, vertex_group = np.unique(structured_keys, return_inverse=True)
        loop_group = np.asarray(vertex_group).ravel()[loop_vertex].astype(np.int64)

        # v16 smooth fans (backend compute_convex_bridged_corner_normals): the loops around a
        # welded position join across a shared edge that is soft, coplanar or convex; only
        # concave hard edges cut the fan. A fan is an equivalence class, so a bridged edge
        # can never crack open (v15 averaged per loop over the neighbours IT accepted).
        group_a = loop_group
        group_b = loop_group[loop_next]
        live = group_a != group_b
        edge_loop = np.nonzero(live)[0]
        a_less = group_a[edge_loop] < group_b[edge_loop]
        edge_lo = np.where(a_less, group_a[edge_loop], group_b[edge_loop])
        edge_hi = np.where(a_less, group_b[edge_loop], group_a[edge_loop])
        corner_lo = np.where(a_less, edge_loop, loop_next[edge_loop])
        corner_hi = np.where(a_less, loop_next[edge_loop], edge_loop)
        order = np.lexsort((edge_hi, edge_lo))
        edge_lo, edge_hi = edge_lo[order], edge_hi[order]
        corner_lo, corner_hi = corner_lo[order], corner_hi[order]
        edge_key = edge_lo * (int(loop_group.max()) + 1) + edge_hi
        _edges, run_start, run_count = np.unique(edge_key, return_index=True, return_counts=True)
        # Every (i, j) half-edge pair, i < j, inside one shared edge.
        pair_count = run_count.astype(np.int64) * run_count.astype(np.int64)
        total_pairs = int(pair_count.sum())
        pair_run = np.repeat(np.arange(run_count.shape[0]), pair_count)
        pair_offset = np.concatenate(([0], np.cumsum(pair_count)[:-1])) if pair_count.size else np.zeros(0, np.int64)
        k = np.arange(total_pairs, dtype=np.int64) - pair_offset[pair_run]
        size = run_count[pair_run].astype(np.int64)
        start = run_start[pair_run].astype(np.int64)
        i = start + k // size
        j = start + k % size
        keep = i < j
        i, j = i[keep], j[keep]
        poly_i = loop_polygon[corner_lo[i]]
        poly_j = loop_polygon[corner_lo[j]]
        distinct = poly_i != poly_j
        normal_i = polygon_normals[poly_i]
        normal_j = polygon_normals[poly_j]
        coplanar = np.einsum("ij,ij->i", normal_i, normal_j) >= _CONVEX_BRIDGE_COPLANAR_COS
        # Convex: each face's centre lies behind the other's plane.
        s_ij = np.einsum("ij,ij->i", polygon_centers[poly_j] - polygon_centers[poly_i], normal_i)
        s_ji = np.einsum("ij,ij->i", polygon_centers[poly_i] - polygon_centers[poly_j], normal_j)
        faces_bridge = distinct & (coplanar | ((s_ij < -tolerance) & (s_ji < -tolerance)))
        usable = np.einsum("ij,ij->i", loop_normals, loop_normals) > 0.0
        union_a = []
        union_b = []
        for end_corners in (corner_lo, corner_hi):
            ca = end_corners[i]
            cb = end_corners[j]
            same_normal = np.einsum("ij,ij->i", loop_normals[ca], loop_normals[cb]) >= _CONVEX_BRIDGE_SAME_NORMAL_COS
            join = (faces_bridge | (distinct & same_normal)) & usable[ca] & usable[cb]
            union_a.append(ca[join])
            union_b.append(cb[join])
        union_a = np.concatenate(union_a)
        union_b = np.concatenate(union_b)

        # Connected components by min-label propagation + pointer jumping (fans are small).
        label = np.arange(loop_count, dtype=np.int64)
        for _ in range(loop_count):
            previous = label
            label = label.copy()
            np.minimum.at(label, union_a, previous[union_b])
            np.minimum.at(label, union_b, previous[union_a])
            label = label[label]
            if np.array_equal(label, previous):
                break

        weighted = loop_normals * np.where(usable, corner_angle, 0.0)[:, None]
        sums = np.zeros((loop_count, 3), dtype=np.float64)
        np.add.at(sums, label, weighted)
        fan_sums = sums[label]
        lengths = np.linalg.norm(fan_sums, axis=1)
        valid = (lengths > 1.0e-10) & usable
        bridged = np.where(valid[:, None], fan_sums / np.where(valid, lengths, 1.0)[:, None], loop_normals)
        return bridged.astype(np.float32)
    except Exception:
        return None


def build_average_split_normal_lookup(mesh, matrix_world=None) -> dict[int, Vector]:
    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loops is None or vertices is None:
        return {}

    numpy_lookup = None
    try:
        numpy_lookup = _try_build_average_split_normal_lookup_numpy(mesh, matrix_world)
    except Exception:
        numpy_lookup = None
    if numpy_lookup is not None:
        return numpy_lookup

    grouped_normals: dict[tuple[float, float, float], Vector] = {}
    vertex_position_keys: dict[int, tuple[float, float, float]] = {}
    for vertex_index, vertex in enumerate(vertices):
        vertex_position_keys[vertex_index] = _vector_position_key(vertex.co)

    for loop in loops:
        key = vertex_position_keys.get(loop.vertex_index)
        if key is None:
            continue
        accumulated = grouped_normals.get(key)
        if accumulated is None:
            grouped_normals[key] = loop.normal.copy()
        else:
            accumulated += loop.normal

    averaged_normals: dict[int, Vector] = {}
    for vertex_index, key in vertex_position_keys.items():
        accumulated = grouped_normals.get(key)
        if accumulated is None:
            continue
        averaged_normals[vertex_index] = _normalized(accumulated)
    return averaged_normals


def _acquire_evaluated_mesh(obj, depsgraph, *, preserve_all_data_layers: bool):
    mesh_read.ensure_object_ready(obj)
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = getattr(obj_eval, "data", None)
    if mesh is not None and getattr(obj_eval, "type", None) == "MESH":
        return obj_eval, mesh, False

    mesh = obj_eval.to_mesh(preserve_all_data_layers=preserve_all_data_layers, depsgraph=depsgraph)
    return obj_eval, mesh, True


def _offset_normal(vertex, loop, matrix_world, smooth_normals: bool, averaged_normal_lookup: dict[int, Vector] | None = None) -> Vector:
    # Smooth Cage on: the position-welded normal (the bake welds the same way). Off: the
    # corner's own split normal (backend v12; the bulk array path additionally bridges
    # convex hard edges, backend v15) -- concave hard edges split the cage, soft edges
    # stay continuous.
    if smooth_normals:
        source_normal = (averaged_normal_lookup or {}).get(loop.vertex_index, vertex.normal)
    else:
        loop_normal = getattr(loop, "normal", None)
        source_normal = loop_normal if loop_normal is not None else vertex.normal
    return _transformed_normal(matrix_world, source_normal)


def auto_cage_uses_average_normals(group) -> bool:
    return bool(getattr(group, "average_normals", True))


def offset_triangles(triangles: list[TriangleData], offset: float) -> list[TriangleData]:
    if offset == 0.0:
        return [
            TriangleData(
                object_name=triangle.object_name,
                corners=tuple(
                    TriangleCorner(
                        source_position=corner.source_position.copy(),
                        position=corner.source_position.copy(),
                        uv=corner.uv,
                        normal=corner.normal.copy(),
                    )
                    for corner in triangle.corners
                ),
            )
            for triangle in triangles
        ]

    scaled_offset = float(offset)
    return [
        TriangleData(
            object_name=triangle.object_name,
            corners=tuple(
                TriangleCorner(
                    source_position=corner.source_position.copy(),
                    position=corner.source_position + corner.normal * scaled_offset,
                    uv=corner.uv,
                    normal=corner.normal.copy(),
                )
                for corner in triangle.corners
            ),
        )
        for triangle in triangles
    ]


def build_local_inflation_lookup_from_face_normals(
    triangles: list[TriangleData],
    *,
    digits: int = 6,
    max_gain: float = _AUTO_CAGE_LOCAL_INFLATION_MAX_GAIN,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Compute corner inflation from geometric face normals (cross product), not stored normals.

    Using stored corner normals fails when they are already position-averaged (smooth_normals=True),
    because all normals at a shared vertex are identical, giving zero sharpness.  The geometric
    face normal from the cross product is always face-accurate and unaffected by any averaging.
    """
    grouped_normals: dict[tuple[str, tuple[float, float, float]], list[Vector]] = {}
    for triangle in triangles:
        a = triangle.corners[0].source_position
        b = triangle.corners[1].source_position
        c = triangle.corners[2].source_position
        cross = (b - a).cross(c - a)
        if cross.length_squared < 1e-20:
            continue
        face_normal = _normalized(cross)
        for corner in triangle.corners:
            key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            grouped_normals.setdefault(key, []).append(face_normal)

    inflation_lookup: dict[tuple[str, tuple[float, float, float]], float] = {}
    clamped_gain = max(0.0, float(max_gain))
    for key, normals in grouped_normals.items():
        if len(normals) < 2 or clamped_gain <= 0.0:
            inflation_lookup[key] = 1.0
            continue
        min_dot = 1.0
        for index, normal in enumerate(normals[:-1]):
            for other in normals[index + 1:]:
                pair_dot = max(-1.0, min(1.0, _vector_dot(normal, other)))
                if pair_dot < min_dot:
                    min_dot = pair_dot
        sharpness = 1.0 - max(0.0, min(1.0, min_dot))
        inflation_lookup[key] = 1.0 + (sharpness * clamped_gain)
    return inflation_lookup


def build_local_inflation_lookup(
    triangles: list[TriangleData],
    *,
    digits: int = 6,
    max_gain: float = _AUTO_CAGE_LOCAL_INFLATION_MAX_GAIN,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    grouped_normals: dict[tuple[str, tuple[float, float, float]], list[Vector]] = {}
    for triangle in triangles:
        for corner in triangle.corners:
            key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            grouped_normals.setdefault(key, []).append(_normalized(corner.normal))

    inflation_lookup: dict[tuple[str, tuple[float, float, float]], float] = {}
    clamped_gain = max(0.0, float(max_gain))
    for key, normals in grouped_normals.items():
        if len(normals) < 2 or clamped_gain <= 0.0:
            inflation_lookup[key] = 1.0
            continue

        min_dot = 1.0
        for index, normal in enumerate(normals[:-1]):
            for other in normals[index + 1:]:
                pair_dot = max(-1.0, min(1.0, _vector_dot(normal, other)))
                if pair_dot < min_dot:
                    min_dot = pair_dot

        sharpness = 1.0 - max(0.0, min(1.0, min_dot))
        inflation_lookup[key] = 1.0 + (sharpness * clamped_gain)
    return inflation_lookup


def offset_triangles_with_local_inflation(
    triangles: list[TriangleData],
    offset: float,
    *,
    digits: int = 6,
    max_gain: float = _AUTO_CAGE_LOCAL_INFLATION_MAX_GAIN,
) -> list[TriangleData]:
    if offset == 0.0:
        return offset_triangles(triangles, offset)

    scaled_offset = float(offset)
    inflation_lookup = build_local_inflation_lookup_from_face_normals(triangles, digits=digits, max_gain=max_gain)
    return [
        TriangleData(
            object_name=triangle.object_name,
            corners=tuple(
                TriangleCorner(
                    source_position=corner.source_position.copy(),
                    position=corner.source_position
                    + corner.normal
                    * (scaled_offset * inflation_lookup.get(_source_position_group_key(triangle.object_name, corner.source_position, digits=digits), 1.0)),
                    uv=corner.uv,
                    normal=corner.normal.copy(),
                )
                for corner in triangle.corners
            ),
        )
        for triangle in triangles
    ]


def _mesh_corner_arrays(mesh, uv_layer, *, want_loop_normals: bool):
    """Bulk-read the per-loop / per-vertex mesh data these captures walk.

    The capture loops used to reach through RNA once per triangle corner
    (``mesh.loops[i]``, ``mesh.vertices[j]``, ``.co``, ``.normal``, ``uv_layer[i].uv``),
    which allocates a wrapper object per access. ``foreach_get`` reads each layer once
    into a flat buffer instead; the arithmetic downstream is untouched, so the captured
    positions/UVs stay bit-for-bit what they were (these feed the exported cage mesh,
    not just the overlay). ``want_loop_normals`` (Smooth Cage off) returns the corner
    normals with convex hard edges bridged (_try_build_convex_bridged_corner_normals_numpy).

    Returns ``None`` when the host mesh cannot serve ``foreach_get``, so the caller keeps
    its original per-corner walk.
    """
    loop_triangles = getattr(mesh, "loop_triangles", None)
    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loop_triangles is None or loops is None or vertices is None:
        return None
    if not all(hasattr(collection, "foreach_get") for collection in (loop_triangles, loops, vertices)):
        return None

    try:
        import numpy as np
    except Exception:
        return None

    try:
        triangle_count = len(loop_triangles)
        loop_count = len(loops)
        vertex_count = len(vertices)

        triangle_loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("loops", triangle_loops)
        triangle_loops = rna_buffers.as_i32(triangle_loops)

        loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
        corner_verts = getattr(mesh, "corner_verts", None)
        if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
            corner_verts.foreach_get("vertex", loop_vertex_indices)
        else:
            loops.foreach_get("vertex_index", loop_vertex_indices)
        loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)

        vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("co", vertex_positions)
        vertex_normals = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("normal", vertex_normals)

        loop_normals = None
        if want_loop_normals:
            loop_normals = np.empty(loop_count * 3, dtype=np.float32)
            corner_normals = getattr(mesh, "corner_normals", None)
            if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
                corner_normals.foreach_get("vector", loop_normals)
            else:
                loops.foreach_get("normal", loop_normals)
            # Smooth Cage off: convex hard edges bridged (what the bake traces along).
            bridged = _try_build_convex_bridged_corner_normals_numpy(mesh)
            if bridged is not None and bridged.shape[0] == loop_count:
                loop_normals = bridged.tolist()
            else:
                loop_normals = loop_normals.reshape(loop_count, 3).tolist()

        uvs = None
        if uv_layer is not None and hasattr(uv_layer, "foreach_get"):
            uv_values = np.empty(loop_count * 2, dtype=np.float32)
            uv_layer.foreach_get("uv", uv_values)
            uvs = [(float(u), float(v)) for u, v in uv_values.reshape(loop_count, 2).tolist()]
    except Exception:
        return None

    return (
        triangle_loops.tolist(),
        loop_vertex_indices.tolist(),
        vertex_positions.reshape(vertex_count, 3).tolist(),
        vertex_normals.reshape(vertex_count, 3).tolist(),
        loop_normals,
        uvs,
        triangle_count,
        vertex_count,
        loop_count,
    )


def _matrix_rows_f32(matrix):
    """A mathutils matrix as a float32 array (rows)."""
    import numpy as np

    rows = len(matrix)
    columns = len(matrix[0])
    return np.array([[matrix[r][c] for c in range(columns)] for r in range(rows)], dtype=np.float32)


def _matrix_vector_f32(rows, vectors):
    """``matrix @ Vector(v)`` for every row of ``vectors`` ((N, 3) float32), bit for bit.

    mathutils multiplies a column vector with float32 products summed in double and rounds
    the sum to float32 (Matrix.__matmul__, column_vector_multiplication); a 4x4 matrix takes
    the vector as (x, y, z, 1). Checked against mathutils on random matrices and vectors
    (tests/test_cage_soup.py)."""
    import numpy as np

    count = vectors.shape[0]
    width = rows.shape[1]
    out = np.empty((count, 3), dtype=np.float32)
    for row in range(3):
        total = np.zeros(count, dtype=np.float64)
        for column in range(width):
            if column < 3:
                product = (rows[row, column] * vectors[:, column]).astype(np.float32)
            else:
                product = np.full(count, np.float32(rows[row, column] * np.float32(1.0)), dtype=np.float32)
            total += product.astype(np.float64)
        out[:, row] = total.astype(np.float32)
    return out


def _normalize_vectors_f32(vectors):
    """``_normalized(Vector(v))`` for every row of ``vectors`` ((N, 3) float32), bit for bit:
    Vector.normalize() sums the squares in double, takes the double square root rounded to
    float32 and multiplies each component by the float32 reciprocal. Rows too short for that
    to hold (or empty) take the mathutils route one by one."""
    import numpy as np

    wide = vectors.astype(np.float64)
    squared = (wide * wide).sum(axis=1)
    length = np.sqrt(squared).astype(np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = (np.float32(1.0) / length).astype(np.float32)
        out = (vectors * scale[:, None]).astype(np.float32)
    odd = ~(squared >= 1.0e-30)
    if odd.any():
        for index in np.flatnonzero(odd).tolist():
            out[index] = _normalized(Vector(vectors[index].tolist()))[:]
    return out


def _transform_normals_f32(normal_matrix, vectors):
    """``_transformed_normal(matrix_world, Vector(v))`` for every row of ``vectors``."""
    return _normalize_vectors_f32(_matrix_vector_f32(_matrix_rows_f32(normal_matrix), vectors))


def _mesh_corner_arrays_np(mesh, uv_layer, *, want_loop_normals: bool):
    """:func:`_mesh_corner_arrays` without the lists: the same bulk reads as numpy arrays.
    None when the host mesh cannot serve ``foreach_get``."""
    loop_triangles = getattr(mesh, "loop_triangles", None)
    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loop_triangles is None or loops is None or vertices is None:
        return None
    if not all(hasattr(collection, "foreach_get") for collection in (loop_triangles, loops, vertices)):
        return None
    try:
        import numpy as np

        triangle_count = len(loop_triangles)
        loop_count = len(loops)
        vertex_count = len(vertices)

        triangle_loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("loops", triangle_loops)
        triangle_loops = rna_buffers.as_i32(triangle_loops)

        loop_vertex_indices = rna_buffers.empty_u32_for_rna(loop_count)
        corner_verts = getattr(mesh, "corner_verts", None)
        if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
            corner_verts.foreach_get("vertex", loop_vertex_indices)
        else:
            loops.foreach_get("vertex_index", loop_vertex_indices)
        loop_vertex_indices = rna_buffers.as_i32(loop_vertex_indices)

        vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("co", vertex_positions)
        vertex_normals = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("normal", vertex_normals)

        loop_normals = None
        if want_loop_normals:
            loop_normals = np.empty(loop_count * 3, dtype=np.float32)
            corner_normals = getattr(mesh, "corner_normals", None)
            if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
                corner_normals.foreach_get("vector", loop_normals)
            else:
                loops.foreach_get("normal", loop_normals)
            bridged = _try_build_convex_bridged_corner_normals_numpy(mesh)
            if bridged is not None and bridged.shape[0] == loop_count:
                loop_normals = np.asarray(bridged, dtype=np.float32).reshape(loop_count, 3)
            else:
                loop_normals = loop_normals.reshape(loop_count, 3)

        uvs = None
        if uv_layer is not None and hasattr(uv_layer, "foreach_get"):
            uv_values = np.empty(loop_count * 2, dtype=np.float32)
            uv_layer.foreach_get("uv", uv_values)
            uvs = uv_values.reshape(loop_count, 2)
    except Exception:
        return None
    return {
        "triangle_loops": np.asarray(triangle_loops, dtype=np.int64).reshape(-1),
        "loop_vertex_indices": np.asarray(loop_vertex_indices, dtype=np.int64).reshape(-1),
        "vertex_positions": vertex_positions.reshape(vertex_count, 3),
        "vertex_normals": vertex_normals.reshape(vertex_count, 3),
        "loop_normals": loop_normals,
        "uvs": uvs,
        "triangle_count": triangle_count,
    }


def _capture_cage_soup(obj, obj_eval, mesh, uv_layer, smooth_normals: bool):
    """:func:`_capture_cage_source_triangles_from_arrays` as a :class:`cage_soup.CageSoup`
    (same float32 values, no per-corner objects), or None when the mesh cannot be read in
    bulk (the object path then runs)."""
    import numpy as np

    arrays = _mesh_corner_arrays_np(mesh, uv_layer, want_loop_normals=not smooth_normals)
    if arrays is None:
        return None
    triangle_count = arrays["triangle_count"]
    if triangle_count <= 0:
        return None
    matrix_world = obj_eval.matrix_world
    triangle_loops = arrays["triangle_loops"]
    loop_vertex_indices = arrays["loop_vertex_indices"]
    corner_vertices = loop_vertex_indices[triangle_loops]

    world_positions = _matrix_vector_f32(_matrix_rows_f32(matrix_world), arrays["vertex_positions"])
    normal_matrix = normal_matrix_3x3(matrix_world)
    loop_normals = arrays["loop_normals"]
    if (not smooth_normals) and loop_normals is not None:
        world_loop_normals = _transform_normals_f32(normal_matrix, loop_normals)
        corner_normals = world_loop_normals[triangle_loops]
    else:
        if smooth_normals:
            field = _smooth_cage_vertex_field_numpy(mesh, matrix_world, world_space=True)
            if field is not None:
                # Solved in world space already: the bake's field, no normal-matrix pass.
                corner_normals = np.ascontiguousarray(field[corner_vertices])
            else:
                groups = _average_split_normal_groups_loops_numpy(mesh)
                if groups is None:
                    return None
                averaged_normals, vertex_group_indices = groups
                source_normals = averaged_normals[vertex_group_indices].astype(np.float32, copy=False)
                corner_normals = _transform_normals_f32(normal_matrix, source_normals)[corner_vertices]
        else:
            source_normals = arrays["vertex_normals"]
            corner_normals = _transform_normals_f32(normal_matrix, source_normals)[corner_vertices]

    uvs = arrays["uvs"]
    corner_uvs = uvs[triangle_loops] if uvs is not None else np.zeros((triangle_count * 3, 2), dtype=np.float32)
    return cage_soup.CageSoup(
        [obj.name],
        np.zeros(triangle_count, dtype=np.int32),
        np.ascontiguousarray(world_positions[corner_vertices]),
        np.ascontiguousarray(corner_normals),
        np.ascontiguousarray(corner_uvs, dtype=np.float32),
    )


def capture_cage_source_triangles(obj, depsgraph, smooth_normals: bool, *args, **kwargs):
    """The cage triangles of the low, cut to its material inside a group scope.

    Captured whole first: a smooth cage's normals at a material border come from both sides.
    """
    from . import low_material_subset

    triangles = _capture_whole_cage_source_triangles(obj, depsgraph, smooth_normals, *args, **kwargs)
    return low_material_subset.subset_cage_triangles(obj, depsgraph, triangles)


def _capture_whole_cage_source_triangles(
    obj,
    depsgraph,
    smooth_normals: bool,
    uv_layer_name: str | None = None,
    uv_layer_required: bool = True,
    as_soup: bool = False,
) -> list[TriangleData]:
    """The low mesh's cage triangles. ``as_soup`` allows a :class:`cage_soup.CageSoup` (the same
    values as arrays, a sequence of the same TriangleData when walked) for the job build, which
    fits, offsets and writes the cage on the arrays."""
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(
        obj,
        depsgraph,
        preserve_all_data_layers=True,
    )
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")

    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        uv_layer = _resolve_uv_layer_data(
            mesh, uv_layer_name, object_name=obj.name, required=uv_layer_required
        )
        paint_offsets, paint_skews = _loop_paint_layers(mesh)
        if as_soup and paint_offsets is None and paint_skews is None:
            soup = _capture_cage_soup(obj, obj_eval, mesh, uv_layer, smooth_normals)
            if soup is not None:
                return soup
        averaged_normal_lookup = build_average_split_normal_lookup(mesh, obj_eval.matrix_world) if smooth_normals else None
        arrays = _mesh_corner_arrays(mesh, uv_layer, want_loop_normals=not smooth_normals)
        if arrays is not None:
            return _capture_cage_source_triangles_from_arrays(
                obj,
                obj_eval,
                arrays,
                smooth_normals=smooth_normals,
                averaged_normal_lookup=averaged_normal_lookup,
                paint_offsets=paint_offsets,
                paint_skews=paint_skews,
            )

        triangles: list[TriangleData] = []
        for loop_triangle in mesh.loop_triangles:
            corners: list[TriangleCorner] = []
            for loop_index in loop_triangle.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                base_position = obj_eval.matrix_world @ vertex.co
                offset_normal = _offset_normal(
                    vertex,
                    loop,
                    obj_eval.matrix_world,
                    smooth_normals,
                    averaged_normal_lookup,
                )
                corners.append(
                    TriangleCorner(
                        source_position=base_position,
                        position=base_position,
                        uv=_corner_uv(uv_layer, loop_index),
                        normal=offset_normal,
                        paint_offset=paint_offsets[loop_index] if paint_offsets is not None else None,
                        paint_skew=paint_skews[loop_index] if paint_skews is not None else None,
                    )
                )
            triangles.append(TriangleData(object_name=obj.name, corners=tuple(corners)))
        return triangles
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _capture_cage_source_triangles_from_arrays(
    obj,
    obj_eval,
    arrays,
    *,
    smooth_normals: bool,
    averaged_normal_lookup: dict[int, Vector] | None,
    paint_offsets=None,
    paint_skews=None,
) -> list[TriangleData]:
    (
        triangle_loops,
        loop_vertex_indices,
        vertex_positions,
        vertex_normals,
        loop_normals,
        uvs,
        triangle_count,
        vertex_count,
        _loop_count,
    ) = arrays

    matrix_world = obj_eval.matrix_world
    object_name = obj.name
    # Smooth Cage off: every corner offsets along its own split normal (what the bake
    # traces), so the cache is per loop there instead of per vertex.
    per_loop = (not smooth_normals) and loop_normals is not None
    loop_world_normals: dict[int, Vector] = {}
    # Both terms depend only on the vertex, so a closed mesh transformed ~3x more
    # vertices than it has. Same mathutils operation on the same inputs, just done once
    # per vertex -- the captured floats are unchanged.
    world_positions: list[Vector | None] = [None] * vertex_count
    world_normals: list[Vector | None] = [None] * vertex_count
    lookup = averaged_normal_lookup or {}

    triangles: list[TriangleData] = []
    corner_cursor = 0
    for _triangle_index in range(triangle_count):
        corners: list[TriangleCorner] = []
        for _corner_index in range(3):
            loop_index = triangle_loops[corner_cursor]
            corner_cursor += 1
            vertex_index = loop_vertex_indices[loop_index]

            base_position = world_positions[vertex_index]
            if base_position is None:
                base_position = matrix_world @ Vector(vertex_positions[vertex_index])
                world_positions[vertex_index] = base_position

            if per_loop:
                offset_normal = loop_world_normals.get(loop_index)
                if offset_normal is None:
                    offset_normal = _transformed_normal(matrix_world, Vector(loop_normals[loop_index]))
                    loop_world_normals[loop_index] = offset_normal
            else:
                offset_normal = world_normals[vertex_index]
            if offset_normal is None:
                source_normal = lookup.get(vertex_index) if smooth_normals else None
                if source_normal is None:
                    source_normal = Vector(vertex_normals[vertex_index])
                offset_normal = _transformed_normal(matrix_world, source_normal)
                world_normals[vertex_index] = offset_normal

            # source_position and position aliased one Vector per corner before; keep
            # that, but hand every corner its own copy of the shared cache entry.
            corner_position = base_position.copy()
            corners.append(
                TriangleCorner(
                    source_position=corner_position,
                    position=corner_position,
                    uv=uvs[loop_index] if uvs is not None else (0.0, 0.0),
                    normal=offset_normal.copy(),
                    paint_offset=paint_offsets[loop_index] if paint_offsets is not None else None,
                    paint_skew=paint_skews[loop_index] if paint_skews is not None else None,
                )
            )
        triangles.append(TriangleData(object_name=object_name, corners=tuple(corners)))
    return triangles


def capture_projection_ray_triangles(
    obj,
    depsgraph,
    uv_layer_name: str | None = None,
    uv_layer_required: bool = True,
    smooth_normals: bool = False,
) -> list[TriangleData]:
    """Low-mesh triangles carrying the normals the bake projects along.

    The exporter writes Blender's corner (split) normals for low meshes. With Smooth
    Cage off the backend traces along those with convex hard edges bridged (backend
    v15: concave hard edges and soft edges unchanged); with it on it welds them by
    position first (backend v12), which is the seam-averaged capture. Never the face
    normal. The skew needles read from this capture."""
    if smooth_normals:
        return capture_cage_source_triangles(
            obj, depsgraph, True, uv_layer_name=uv_layer_name, uv_layer_required=uv_layer_required
        )
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(
        obj,
        depsgraph,
        preserve_all_data_layers=True,
    )
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")

    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        uv_layer = _resolve_uv_layer_data(
            mesh, uv_layer_name, object_name=obj.name, required=uv_layer_required
        )
        matrix_world = obj_eval.matrix_world
        object_name = obj.name
        paint_offsets, paint_skews = _loop_paint_layers(mesh)

        arrays = _mesh_corner_arrays(mesh, uv_layer, want_loop_normals=True)
        if arrays is not None:
            (
                triangle_loops,
                loop_vertex_indices,
                vertex_positions,
                _vertex_normals,
                loop_normals,
                uvs,
                triangle_count,
                vertex_count,
                _loop_count,
            ) = arrays
            if loop_normals is None:
                arrays = None
        if arrays is not None:
            world_positions: list[Vector | None] = [None] * vertex_count
            triangles: list[TriangleData] = []
            corner_cursor = 0
            for _triangle_index in range(triangle_count):
                corners: list[TriangleCorner] = []
                for _corner_index in range(3):
                    loop_index = triangle_loops[corner_cursor]
                    corner_cursor += 1
                    vertex_index = loop_vertex_indices[loop_index]
                    base_position = world_positions[vertex_index]
                    if base_position is None:
                        base_position = matrix_world @ Vector(vertex_positions[vertex_index])
                        world_positions[vertex_index] = base_position
                    corner_position = base_position.copy()
                    corners.append(
                        TriangleCorner(
                            source_position=corner_position,
                            position=corner_position,
                            uv=uvs[loop_index] if uvs is not None else (0.0, 0.0),
                            normal=_transformed_normal(matrix_world, Vector(loop_normals[loop_index])),
                            paint_offset=paint_offsets[loop_index] if paint_offsets is not None else None,
                            paint_skew=paint_skews[loop_index] if paint_skews is not None else None,
                        )
                    )
                triangles.append(TriangleData(object_name=object_name, corners=tuple(corners)))
            return triangles

        triangles = []
        for loop_triangle in mesh.loop_triangles:
            corners = []
            for loop_index in loop_triangle.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                base_position = matrix_world @ vertex.co
                corners.append(
                    TriangleCorner(
                        source_position=base_position,
                        position=base_position,
                        uv=_corner_uv(uv_layer, loop_index),
                        normal=_transformed_normal(matrix_world, loop.normal),
                        paint_offset=paint_offsets[loop_index] if paint_offsets is not None else None,
                        paint_skew=paint_skews[loop_index] if paint_skews is not None else None,
                    )
                )
            triangles.append(TriangleData(object_name=object_name, corners=tuple(corners)))
        return triangles
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def capture_offset_triangles(
    obj,
    depsgraph,
    offset: float,
    smooth_normals: bool,
    uv_layer_name: str | None = None,
) -> list[TriangleData]:
    return offset_triangles(capture_cage_source_triangles(obj, depsgraph, smooth_normals, uv_layer_name=uv_layer_name), offset)


def capture_object_triangles(obj, depsgraph, uv_layer_name: str | None = None) -> list[TriangleData]:
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(
        obj,
        depsgraph,
        preserve_all_data_layers=True,
    )
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")

    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        uv_layer = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name)

        arrays = _mesh_corner_arrays(mesh, uv_layer, want_loop_normals=False)
        if arrays is not None:
            return _capture_object_triangles_from_arrays(obj, obj_eval, mesh, arrays)

        triangles: list[TriangleData] = []
        for loop_triangle in mesh.loop_triangles:
            corners: list[TriangleCorner] = []
            for loop_index in loop_triangle.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                world_position = obj_eval.matrix_world @ vertex.co
                corners.append(
                    TriangleCorner(
                        source_position=world_position,
                        position=world_position,
                        uv=_corner_uv(uv_layer, loop_index),
                        normal=_transformed_normal(obj_eval.matrix_world, loop.normal),
                    )
                )
            triangles.append(TriangleData(object_name=obj.name, corners=tuple(corners)))
        return triangles
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _capture_object_triangles_from_arrays(obj, obj_eval, mesh, arrays) -> list[TriangleData]:
    (
        triangle_loops,
        loop_vertex_indices,
        vertex_positions,
        _vertex_normals,
        _loop_normals,
        uvs,
        triangle_count,
        vertex_count,
        loop_count,
    ) = arrays

    matrix_world = obj_eval.matrix_world
    object_name = obj.name
    mesh_loops = mesh.loops
    # Position is per vertex, the split normal is per loop; both were recomputed for
    # every triangle corner that referenced them. Loop normals stay a lazy RNA read
    # (measured faster than bulk-reading and materialising every loop normal, since a
    # loop is referenced only ~1.5x on average).
    world_positions: list[Vector | None] = [None] * vertex_count
    world_normals: list[Vector | None] = [None] * loop_count

    triangles: list[TriangleData] = []
    corner_cursor = 0
    for _triangle_index in range(triangle_count):
        corners: list[TriangleCorner] = []
        for _corner_index in range(3):
            loop_index = triangle_loops[corner_cursor]
            corner_cursor += 1
            vertex_index = loop_vertex_indices[loop_index]

            world_position = world_positions[vertex_index]
            if world_position is None:
                world_position = matrix_world @ Vector(vertex_positions[vertex_index])
                world_positions[vertex_index] = world_position

            world_normal = world_normals[loop_index]
            if world_normal is None:
                world_normal = _transformed_normal(matrix_world, mesh_loops[loop_index].normal)
                world_normals[loop_index] = world_normal

            corner_position = world_position.copy()
            corners.append(
                TriangleCorner(
                    source_position=corner_position,
                    position=corner_position,
                    uv=uvs[loop_index] if uvs is not None else (0.0, 0.0),
                    normal=world_normal.copy(),
                )
            )
        triangles.append(TriangleData(object_name=object_name, corners=tuple(corners)))
    return triangles


# Maximum triangles to push to the GPU for the high-mesh display batch.
# Denser meshes are simplified into a clustered display proxy so the
# viewport keeps a coherent closed surface instead of dropping holes into
# the mesh by skipping triangles outright.
_HIGH_DISPLAY_MAX_TRIS = 50_000
_HIGH_DISPLAY_PROXY_SCALE_LADDER = (
    0.95,
    0.9,
    0.85,
    0.8,
    0.75,
    0.7,
    0.65,
    0.6,
    0.55,
    0.5,
    0.45,
    0.4,
    0.35,
    0.3,
    0.25,
    0.2,
    0.15,
    0.1,
)


def _high_display_proxy_axis_resolution(bounds_extent, target_triangle_count):
    import numpy as np

    safe_extent = np.maximum(
        np.asarray(bounds_extent, dtype=np.float32),
        np.float32(1.0e-6),
    )
    surface_area = float(
        (2.0 * safe_extent[0] * safe_extent[1])
        + (2.0 * safe_extent[1] * safe_extent[2])
        + (2.0 * safe_extent[2] * safe_extent[0])
    )
    if not math.isfinite(surface_area) or surface_area <= 1.0e-8:
        return np.array((2, 2, 2), dtype=np.int32)

    density = math.sqrt(max(1, int(target_triangle_count)) / max(surface_area, 1.0e-8))
    axis_resolution = np.maximum(1, np.rint(safe_extent * density).astype(np.int32))
    axis_resolution = np.where(safe_extent > 1.0e-5, np.maximum(axis_resolution, 2), 1)
    return axis_resolution.astype(np.int32, copy=False)


def _high_display_proxy_candidate_resolutions(base_axis_resolution, scale):
    import numpy as np

    desired = np.maximum(
        np.float32(1.0),
        base_axis_resolution.astype(np.float32) * np.float32(scale),
    )
    axis_candidates: list[tuple[int, ...]] = []
    for desired_axis in desired:
        axis_values = {
            max(1, int(math.floor(float(desired_axis)))),
            max(1, int(round(float(desired_axis)))),
            max(1, int(math.ceil(float(desired_axis)))),
        }
        axis_candidates.append(tuple(sorted(axis_values, reverse=True)))

    candidates: list[np.ndarray] = []
    seen: set[tuple[int, int, int]] = set()
    for axis_resolution in itertools.product(*axis_candidates):
        key = tuple(int(value) for value in axis_resolution)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(np.asarray(key, dtype=np.int32))
    candidates.sort(
        key=lambda value: (
            int(value[0]) * int(value[1]) * int(value[2]),
            int(value[0]) + int(value[1]) + int(value[2]),
        ),
        reverse=True,
    )
    return candidates


def _select_high_display_proxy_resolution(
    vertex_positions,
    triangle_vertex_indices,
    bounds_min,
    bounds_extent,
    max_triangles: int,
):
    import numpy as np

    if max_triangles <= 0:
        return None

    base_axis_resolution = _high_display_proxy_axis_resolution(bounds_extent, max_triangles)
    count_cache: dict[tuple[int, int, int], int] = {}

    def _count(axis_resolution):
        key = tuple(int(value) for value in axis_resolution)
        cached = count_cache.get(key)
        if cached is not None:
            return cached
        triangle_count, _cluster_positions, _tri_clusters = _clustered_display_triangles_np(
            vertex_positions,
            triangle_vertex_indices,
            bounds_min,
            bounds_extent,
            np.asarray(key, dtype=np.int32),
            include_positions=False,
        )
        count_cache[key] = int(triangle_count)
        return int(triangle_count)

    base_count = _count(base_axis_resolution)
    if 0 < base_count <= max_triangles:
        return base_axis_resolution.astype(np.int32, copy=True)

    best_resolution = None
    best_count = -1
    target_floor = max(1, int(max_triangles * 0.96))
    for scale in _HIGH_DISPLAY_PROXY_SCALE_LADDER:
        for candidate in _high_display_proxy_candidate_resolutions(base_axis_resolution, scale):
            candidate_count = _count(candidate)
            if 0 < candidate_count <= max_triangles and candidate_count > best_count:
                best_resolution = candidate.astype(np.int32, copy=True)
                best_count = candidate_count
        if best_count >= target_floor:
            break

    if best_resolution is not None:
        return best_resolution

    current_resolution = base_axis_resolution.astype(np.int32, copy=True)
    current_count = base_count
    while current_count > max_triangles and np.any(current_resolution > 1):
        next_resolution = None
        next_count = -1
        for axis_index in range(3):
            if current_resolution[axis_index] <= 1:
                continue
            candidate = current_resolution.astype(np.int32, copy=True)
            candidate[axis_index] -= 1
            candidate_count = _count(candidate)
            if candidate_count > next_count:
                next_resolution = candidate
                next_count = candidate_count
        if next_resolution is None or next_count <= 0:
            break
        current_resolution = next_resolution
        current_count = next_count
        if current_count <= max_triangles:
            return current_resolution

    best_cached = max(
        (
            (count, resolution_key)
            for resolution_key, count in count_cache.items()
            if 0 < count <= max_triangles
        ),
        default=None,
    )
    if best_cached is None:
        return None
    return np.asarray(best_cached[1], dtype=np.int32)


def _morton_expand_bits_10(values):
    import numpy as np

    expanded = np.asarray(values, dtype=np.uint32) & np.uint32(1023)
    expanded = (expanded | (expanded << np.uint32(16))) & np.uint32(0x030000FF)
    expanded = (expanded | (expanded << np.uint32(8))) & np.uint32(0x0300F00F)
    expanded = (expanded | (expanded << np.uint32(4))) & np.uint32(0x030C30C3)
    expanded = (expanded | (expanded << np.uint32(2))) & np.uint32(0x09249249)
    return expanded


def _spatial_sample_triangles_np(triangle_positions, max_triangles: int):
    import numpy as np

    triangle_count = int(triangle_positions.shape[0])
    if max_triangles <= 0 or triangle_count <= max_triangles:
        return triangle_positions

    centroids = triangle_positions.mean(axis=1)
    bounds_min = centroids.min(axis=0)
    bounds_extent = np.maximum(centroids.max(axis=0) - bounds_min, np.float32(1.0e-6))
    normalized = np.clip(
        (centroids - bounds_min) / bounds_extent,
        np.float32(0.0),
        np.nextafter(np.float32(1.0), np.float32(0.0)),
    )
    quantized = np.minimum(
        (normalized * np.float32(1024.0)).astype(np.uint32),
        np.uint32(1023),
    )
    morton_codes = _morton_expand_bits_10(quantized[:, 0])
    morton_codes |= _morton_expand_bits_10(quantized[:, 1]) << np.uint32(1)
    morton_codes |= _morton_expand_bits_10(quantized[:, 2]) << np.uint32(2)
    spatial_order = np.argsort(morton_codes, kind="stable")
    ordered_triangles = triangle_positions[spatial_order]

    sampled_indices = np.empty(max_triangles, dtype=np.int32)
    for sample_index in range(max_triangles):
        bucket_start = int((sample_index * triangle_count) / float(max_triangles))
        bucket_end = int(((sample_index + 1) * triangle_count) / float(max_triangles))
        bucket_end = max(bucket_start + 1, min(bucket_end, triangle_count))
        bucket_size = max(1, bucket_end - bucket_start)
        hash_value = ((sample_index * 1103515245) + 12345) & 0x7FFFFFFF
        sampled_indices[sample_index] = min(bucket_start + (hash_value % bucket_size), triangle_count - 1)
    return ordered_triangles[sampled_indices]


def _clustered_display_triangles_np(
    vertex_positions,
    triangle_vertex_indices,
    bounds_min,
    bounds_extent,
    axis_resolution,
    *,
    include_positions: bool,
):
    import numpy as np

    safe_extent = np.maximum(
        np.asarray(bounds_extent, dtype=np.float32),
        np.float32(1.0e-6),
    )
    resolution = np.maximum(1, np.asarray(axis_resolution, dtype=np.int64))
    scale = resolution.astype(np.float32) / safe_extent
    cell_coords = np.floor((vertex_positions - bounds_min) * scale).astype(np.int64)
    cell_coords = np.minimum(cell_coords, np.maximum(resolution - 1, 0))
    cell_coords = np.maximum(cell_coords, 0)

    stride_y = int(resolution[0] + 1)
    stride_z = int((resolution[0] + 1) * (resolution[1] + 1))
    cell_keys = (
        cell_coords[:, 0]
        + (cell_coords[:, 1] * stride_y)
        + (cell_coords[:, 2] * stride_z)
    )
    _unique_keys, inverse = np.unique(cell_keys, return_inverse=True)

    tri_clusters = inverse[triangle_vertex_indices].reshape(-1, 3)
    non_degenerate_mask = (
        (tri_clusters[:, 0] != tri_clusters[:, 1])
        & (tri_clusters[:, 1] != tri_clusters[:, 2])
        & (tri_clusters[:, 0] != tri_clusters[:, 2])
    )
    tri_clusters = tri_clusters[non_degenerate_mask]
    if tri_clusters.size == 0:
        return 0, None, None

    sorted_clusters = np.sort(tri_clusters, axis=1)
    view_dtype = np.dtype((np.void, sorted_clusters.dtype.itemsize * 3))
    structured_clusters = np.ascontiguousarray(sorted_clusters).view(view_dtype).ravel()
    _unique_tris, unique_indices = np.unique(structured_clusters, return_index=True)
    if unique_indices.size != tri_clusters.shape[0]:
        tri_clusters = tri_clusters[np.sort(unique_indices)]

    triangle_count = int(tri_clusters.shape[0])
    if not include_positions:
        return triangle_count, None, None

    cluster_count = int(_unique_keys.shape[0])
    counts = np.bincount(inverse, minlength=cluster_count).astype(np.float32)
    counts = np.maximum(counts, np.float32(1.0))
    cluster_positions = np.stack(
        [
            np.bincount(
                inverse,
                weights=vertex_positions[:, axis_index],
                minlength=cluster_count,
            ).astype(np.float32)
            / counts
            for axis_index in range(3)
        ],
        axis=1,
    )
    return (
        triangle_count,
        cluster_positions.astype(np.float32, copy=False),
        tri_clusters.astype(np.int32, copy=False),
    )


def _clustered_high_display_positions(vertex_positions, triangle_vertex_indices, matrix_world, max_triangles: int):
    import numpy as np

    triangle_count = int(len(triangle_vertex_indices) // 3)
    if triangle_count <= 0:
        return array("f")

    if max_triangles <= 0 or triangle_count <= max_triangles:
        tri_local_positions = vertex_positions[triangle_vertex_indices].reshape(-1, 3)
    else:
        bounds_min = vertex_positions.min(axis=0)
        bounds_max = vertex_positions.max(axis=0)
        bounds_extent = np.maximum(bounds_max - bounds_min, np.float32(1.0e-6))
        selected_resolution = _select_high_display_proxy_resolution(
            vertex_positions,
            triangle_vertex_indices,
            bounds_min,
            bounds_extent,
            max_triangles,
        )
        if selected_resolution is None:
            return array("f")

        proxy_triangle_count, cluster_positions, tri_clusters = _clustered_display_triangles_np(
            vertex_positions,
            triangle_vertex_indices,
            bounds_min,
            bounds_extent,
            selected_resolution,
            include_positions=True,
        )
        if proxy_triangle_count <= 0 or cluster_positions is None or tri_clusters is None:
            return array("f")

        tri_local_positions = cluster_positions[tri_clusters]
        if proxy_triangle_count > max_triangles:
            tri_local_positions = _spatial_sample_triangles_np(tri_local_positions, max_triangles)
        tri_local_positions = tri_local_positions.reshape(-1, 3)

    transform = np.asarray(matrix_world, dtype=np.float32)
    world_positions = (
        tri_local_positions @ transform[:3, :3].T
    ) + transform[:3, 3]
    out_positions: array = array("f")
    out_positions.frombytes(
        np.ascontiguousarray(world_positions.astype(np.float32, copy=False)).ravel().tobytes()
    )
    return out_positions


def build_high_mesh_display_buffers_from_data(
    vertex_positions,
    triangle_vertex_indices,
    matrix_world,
    *,
    max_triangles: int = _HIGH_DISPLAY_MAX_TRIS,
) -> tuple[array, array]:
    import numpy as np

    triangle_count = int(len(triangle_vertex_indices) // 3)
    if triangle_count <= 0:
        return array("f"), array("f")

    try:
        out_positions = _clustered_high_display_positions(
            vertex_positions,
            triangle_vertex_indices,
            matrix_world,
            max_triangles,
        )
        if out_positions:
            return out_positions, array("f")
    except Exception:
        # Keep the viewport alive even if proxy simplification fails on an
        # unusual mesh: fall back to lightweight triangle sampling.
        pass

    tri_positions = vertex_positions[triangle_vertex_indices].reshape(triangle_count, 3, 3)
    if triangle_count > max_triangles:
        tri_positions = _spatial_sample_triangles_np(tri_positions, max_triangles)
    transform = np.asarray(matrix_world, dtype=np.float32)
    tri_positions = (
        tri_positions.reshape(-1, 3) @ transform[:3, :3].T
    ) + transform[:3, 3]
    out_positions: array = array("f")
    out_positions.frombytes(
        np.ascontiguousarray(tri_positions.astype(np.float32, copy=False)).ravel().tobytes()
    )
    return out_positions, array("f")


def capture_high_mesh_display_source_data(
    obj,
    depsgraph,
):
    import numpy as np

    def _copy_mesh_source_data(mesh, matrix_world):
        if mesh is None:
            return None

        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()

        loop_triangles = getattr(mesh, "loop_triangles", None)
        vertices = getattr(mesh, "vertices", None)
        if loop_triangles is None or vertices is None:
            return None

        triangle_count = len(loop_triangles)
        if triangle_count <= 0:
            return None

        vertex_count = len(vertices)
        if vertex_count <= 0:
            return None

        triangle_vertex_indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("vertices", triangle_vertex_indices)
        triangle_vertex_indices = rna_buffers.as_i32(triangle_vertex_indices)

        vertex_positions_flat = np.empty(vertex_count * 3, dtype=np.float32)
        vertices.foreach_get("co", vertex_positions_flat)
        vertex_positions = vertex_positions_flat.reshape(vertex_count, 3)
        matrix_world_copy = tuple(
            tuple(float(component) for component in row)
            for row in matrix_world
        )
        return vertex_positions, triangle_vertex_indices, matrix_world_copy

    # A cleared copy, never obj.data or the evaluated mesh: reading those left an un-shared
    # position array and the corner-tri cache in Blender for the session (see mesh_read).
    with mesh_read.evaluated_mesh_copy(obj, depsgraph) as (obj_eval, mesh):
        return _copy_mesh_source_data(mesh, obj_eval.matrix_world)


def capture_high_mesh_fit_source_data(obj, depsgraph):
    """Vertices-only capture for the automatic-cage coverage fit.

    :func:`build_coverage_offsets` (via :func:`_high_world_vertices_from_source_data`) reads only
    the high-poly *vertex positions* and world matrix; it never touches the triangle indices. For a
    dense high mesh the ``loop_triangles.foreach_get`` copy is the whole cost of
    :func:`capture_high_mesh_display_source_data` (~1.5s for 10M tris) and is pure waste here, so
    this skips ``calc_loop_triangles`` entirely and grabs only ``vertices.co``. Returns a
    ``(vertex_positions, None, matrix_world)`` triple matching the shape the fit consumer expects
    (``None`` triangle slot is ignored downstream)."""
    import numpy as np

    def _copy_vertices(mesh, matrix_world):
        if mesh is None:
            return None
        vertices = getattr(mesh, "vertices", None)
        if vertices is None:
            return None
        vertex_count = len(vertices)
        if vertex_count <= 0:
            return None
        vertex_positions_flat = np.empty(vertex_count * 3, dtype=np.float32)
        if not mesh_read.read_positions_flat(mesh, vertex_positions_flat):
            vertices.foreach_get("co", vertex_positions_flat)
        matrix_world_copy = tuple(
            tuple(float(component) for component in row) for row in matrix_world
        )
        return vertex_positions_flat.reshape(vertex_count, 3), None, matrix_world_copy

    # A cleared copy, never obj.data or the evaluated mesh: a position read un-shares the
    # whole array on the mesh it reads, which stayed in Blender for the session (~0.5 GB over
    # SvAT's highs on every automatic-cage bake). See mesh_read.
    with mesh_read.evaluated_mesh_copy(obj, depsgraph) as (obj_eval, mesh):
        return _copy_vertices(mesh, obj_eval.matrix_world)


def capture_object_edge_lines(
    obj,
    depsgraph,
    *,
    smooth_normals: bool = True,
    with_uvs: bool = False,
    uv_layer_name: str | None = None,
    inflation_lookup: dict[tuple[str, tuple[float, float, float]], float] | None = None,
    digits: int = 6,
) -> OffsetBatchBuffers:
    if inflation_lookup is None:
        try:
            bulk = _capture_object_edge_lines_numpy(obj, depsgraph, smooth_normals, with_uvs, uv_layer_name)
        except Exception as exc:  # noqa: BLE001 - the loop version below stays the reference
            if _is_capture_input_error(exc):
                raise
            bulk = None
        if bulk is not None:
            return bulk
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(
        obj,
        depsgraph,
        preserve_all_data_layers=with_uvs,
    )
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")

    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        averaged_normal_lookup = build_average_split_normal_lookup(mesh, obj_eval.matrix_world) if smooth_normals else None

        # Build vertex-index → UV map so edge endpoints can be displaced by the paint texture.
        vertex_uv: dict[int, tuple[float, float]] = {}
        # Paint layer multiplier per loop and per vertex (first loop), for the same reason.
        loop_paint: list[float] | None = None
        vertex_paint: dict[int, float] = {}
        if with_uvs:
            layer_offsets, _layer_skews = _loop_paint_layers(mesh)
            if layer_offsets is not None:
                loop_paint = [max(0.0, 1.0 + float(value)) for value in layer_offsets]
                for loop in mesh.loops:
                    vertex_paint.setdefault(loop.vertex_index, loop_paint[loop.index])
        if with_uvs:
            # Same rule as the triangle captures: the paint canvas is sampled through
            # the group's bake UV Set when one is set, falling back to the active layer.
            uv_data = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name, required=False)
            if uv_data is not None:
                for loop in mesh.loops:
                    vi = loop.vertex_index
                    if vi not in vertex_uv:
                        uv_co = uv_data[loop.index].uv
                        vertex_uv[vi] = (float(uv_co.x), float(uv_co.y))

        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        paints: list[float] = []
        if not smooth_normals:
            # Smooth Cage off: the cage follows the corner normals the bake traces (convex
            # hard edges bridged, backend v15), so a concave hard edge draws once per side
            # (the cage really opens there) and a soft or bridged edge, whose corners
            # agree, draws once.
            seen: set = set()
            matrix_world = obj_eval.matrix_world
            bridged_normals = _try_build_convex_bridged_corner_normals_numpy(mesh)
            if bridged_normals is not None and bridged_normals.shape[0] != len(mesh.loops):
                bridged_normals = None
            for polygon in mesh.polygons:
                loop_ids = list(polygon.loop_indices)
                for i, loop_a in enumerate(loop_ids):
                    loop_b = loop_ids[(i + 1) % len(loop_ids)]
                    v0 = mesh.loops[loop_a].vertex_index
                    v1 = mesh.loops[loop_b].vertex_index
                    if bridged_normals is not None:
                        na = Vector(bridged_normals[loop_a].tolist())
                        nb = Vector(bridged_normals[loop_b].tolist())
                    else:
                        na = Vector(mesh.corner_normals[loop_a].vector) if hasattr(mesh, "corner_normals") else Vector(mesh.loops[loop_a].normal)
                        nb = Vector(mesh.corner_normals[loop_b].vector) if hasattr(mesh, "corner_normals") else Vector(mesh.loops[loop_b].normal)
                    if v0 > v1:
                        v0, v1, na, nb = v1, v0, nb, na
                    key = (v0, v1, tuple(round(c, 4) for c in na), tuple(round(c, 4) for c in nb))
                    if key in seen:
                        continue
                    seen.add(key)
                    world_a = matrix_world @ mesh.vertices[v0].co
                    world_b = matrix_world @ mesh.vertices[v1].co
                    normal_a = _transformed_normal(matrix_world, na)
                    normal_b = _transformed_normal(matrix_world, nb)
                    if inflation_lookup is not None:
                        normal_a = normal_a * inflation_lookup.get(_source_position_group_key(obj.name, world_a, digits=digits), 1.0)
                        normal_b = normal_b * inflation_lookup.get(_source_position_group_key(obj.name, world_b, digits=digits), 1.0)
                    positions.append((float(world_a.x), float(world_a.y), float(world_a.z)))
                    positions.append((float(world_b.x), float(world_b.y), float(world_b.z)))
                    normals.append((float(normal_a.x), float(normal_a.y), float(normal_a.z)))
                    normals.append((float(normal_b.x), float(normal_b.y), float(normal_b.z)))
                    if with_uvs:
                        uvs.append(vertex_uv.get(v0, (0.0, 0.0)))
                        uvs.append(vertex_uv.get(v1, (0.0, 0.0)))
                        if loop_paint is not None:
                            # v0/v1 may have been swapped with the loops above.
                            first, second = (loop_a, loop_b) if mesh.loops[loop_a].vertex_index == v0 else (loop_b, loop_a)
                            paints.append(loop_paint[first])
                            paints.append(loop_paint[second])
            return OffsetBatchBuffers(positions=positions, normals=normals, uvs=uvs, paints=paints)
        for edge in mesh.edges:
            v0, v1 = edge.vertices[0], edge.vertices[1]
            vertex_a = mesh.vertices[v0]
            vertex_b = mesh.vertices[v1]
            world_a = obj_eval.matrix_world @ vertex_a.co
            world_b = obj_eval.matrix_world @ vertex_b.co
            source_normal_a = (averaged_normal_lookup or {}).get(v0, vertex_a.normal)
            source_normal_b = (averaged_normal_lookup or {}).get(v1, vertex_b.normal)
            normal_a = _transformed_normal(obj_eval.matrix_world, source_normal_a)
            normal_b = _transformed_normal(obj_eval.matrix_world, source_normal_b)
            if inflation_lookup is not None:
                key_a = _source_position_group_key(obj.name, world_a, digits=digits)
                key_b = _source_position_group_key(obj.name, world_b, digits=digits)
                normal_a = normal_a * inflation_lookup.get(key_a, 1.0)
                normal_b = normal_b * inflation_lookup.get(key_b, 1.0)
            positions.append((float(world_a.x), float(world_a.y), float(world_a.z)))
            positions.append((float(world_b.x), float(world_b.y), float(world_b.z)))
            normals.append((float(normal_a.x), float(normal_a.y), float(normal_a.z)))
            normals.append((float(normal_b.x), float(normal_b.y), float(normal_b.z)))
            if with_uvs:
                uvs.append(vertex_uv.get(v0, (0.0, 0.0)))
                uvs.append(vertex_uv.get(v1, (0.0, 0.0)))
                if loop_paint is not None:
                    paints.append(vertex_paint.get(v0, 1.0))
                    paints.append(vertex_paint.get(v1, 1.0))
        return OffsetBatchBuffers(positions=positions, normals=normals, uvs=uvs, paints=paints)
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


# ---------------------------------------------------------------------------
# Bulk (numpy) overlay captures. The Distance preview draws one flat cage per low slot and
# the Auto-Build that follows invalidates every group at once, so the first viewport draw
# captured every group's low mesh through per-triangle / per-edge Python loops (73 groups:
# 3.3-6 s frozen). These read the same mesh layers with foreach_get and transform them as
# arrays; the buffers are the lists the loop versions returned, to float32 rounding.


def _is_capture_input_error(exc: Exception) -> bool:
    """An error the capture is MEANT to raise (the caller's input is wrong), which the bulk
    path must not swallow into the loop fallback."""
    text = str(exc)
    return isinstance(exc, ValueError) and ("requested UV set" in text or "Unable to evaluate" in text)


def _world_points_numpy(matrix_world, points):
    import numpy as np

    rows = np.array([[float(matrix_world[r][c]) for c in range(4)] for r in range(3)], dtype=np.float64)
    return (points.astype(np.float64) @ rows[:, :3].T + rows[:, 3]).astype(np.float32)


def _world_normals_numpy(matrix_world, normals):
    """_transformed_normal for every row: the normal matrix, then normalise (a row with no
    length stays as it is, like Vector.normalize guarded by length_squared)."""
    import numpy as np

    rows = np.array([[float(value) for value in row] for row in normal_matrix_3x3(matrix_world)], dtype=np.float64)
    moved = (normals.astype(np.float64) @ rows.T).astype(np.float32)
    squared = np.einsum("ij,ij->i", moved, moved)
    scale = np.where(squared != 0.0, 1.0 / np.sqrt(np.where(squared != 0.0, squared, 1.0)), 1.0)
    return (moved * scale[:, None]).astype(np.float32)


def _mesh_layers_numpy(mesh, *, want_loop_normals: bool, want_averaged: bool, matrix_world=None):
    """Per-vertex / per-loop layers as arrays, or None when the mesh cannot serve foreach_get.

    vertex_positions (V,3), loop_vertex (L,), loop_normals (L,3) with convex hard edges
    bridged (Smooth Cage off, else None), averaged (V,3): the Smooth Cage direction (the backend's field,
    object space; the old split-normal average without loop triangles), else None."""
    import numpy as np

    loops = getattr(mesh, "loops", None)
    vertices = getattr(mesh, "vertices", None)
    if loops is None or vertices is None:
        return None
    if not (hasattr(loops, "foreach_get") and hasattr(vertices, "foreach_get")):
        return None
    vertex_count = len(vertices)
    loop_count = len(loops)
    if vertex_count <= 0 or loop_count <= 0:
        return None

    vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
    vertices.foreach_get("co", vertex_positions)
    vertex_positions = vertex_positions.reshape(vertex_count, 3)

    loop_vertex = rna_buffers.empty_u32_for_rna(loop_count)
    corner_verts = getattr(mesh, "corner_verts", None)
    if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
        corner_verts.foreach_get("vertex", loop_vertex)
    else:
        loops.foreach_get("vertex_index", loop_vertex)
    loop_vertex = rna_buffers.as_i32(loop_vertex).astype(np.int64)

    plain_loop_normals = np.empty(loop_count * 3, dtype=np.float32)
    corner_normals = getattr(mesh, "corner_normals", None)
    if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
        corner_normals.foreach_get("vector", plain_loop_normals)
    else:
        loops.foreach_get("normal", plain_loop_normals)
    plain_loop_normals = plain_loop_normals.reshape(loop_count, 3)

    loop_normals = None
    if want_loop_normals:
        bridged = _try_build_convex_bridged_corner_normals_numpy(mesh)
        loop_normals = bridged if bridged is not None and bridged.shape[0] == loop_count else plain_loop_normals

    averaged = None
    if want_averaged:
        averaged = _smooth_cage_vertex_field_numpy(mesh, matrix_world)
        if averaged is None:
            keys = np.rint(vertex_positions * 1_000_000.0).astype(np.int64, copy=False)
            view_dtype = np.dtype((np.void, keys.dtype.itemsize * 3))
            structured = np.ascontiguousarray(keys).view(view_dtype).ravel()
            unique_keys, vertex_group = np.unique(structured, return_inverse=True)
            vertex_group = np.asarray(vertex_group).ravel()
            grouped = np.zeros((int(unique_keys.shape[0]), 3), dtype=np.float64)
            np.add.at(grouped, vertex_group[loop_vertex], plain_loop_normals.astype(np.float64, copy=False))
            group_normals = _normalized_rows_numpy(grouped.astype(np.float32, copy=False))
            averaged = group_normals[vertex_group]

    return {
        "vertex_positions": vertex_positions,
        "loop_vertex": loop_vertex,
        "loop_normals": loop_normals,
        "averaged": averaged,
    }


def _paint_values_numpy(mesh):
    """Per-loop paint offset multiplier max(0, 1 + value) as float64, or None without the layer."""
    try:
        from . import paint_sampling

        offsets = paint_sampling.read_loop_values(mesh, paint_sampling.OFFSET_ATTRIBUTE)
    except Exception:  # noqa: BLE001 - same silence as _loop_paint_layers
        return None
    if offsets is None:
        return None
    import numpy as np

    return np.maximum(0.0, 1.0 + offsets.astype(np.float64))


def _uv_values_numpy(uv_data, loop_count: int):
    import numpy as np

    if uv_data is None or not hasattr(uv_data, "foreach_get"):
        return None
    values = np.empty(loop_count * 2, dtype=np.float32)
    uv_data.foreach_get("uv", values)
    return values.reshape(loop_count, 2)


def _rows_as_tuples(rows):
    """list[tuple[float, ...]] from an (N, k) array: Python floats, one C-speed pass."""
    return list(zip(*[rows[:, index].tolist() for index in range(rows.shape[1])]))


def capture_cage_offset_buffers(
    obj,
    depsgraph,
    smooth_normals: bool,
    uv_layer_name: str | None = None,
    uv_layer_required: bool = True,
) -> OffsetBatchBuffers:
    """``offset_batch_buffers_from_triangles(capture_cage_source_triangles(...))`` without
    building a TriangleData per triangle (the flat Distance cage only draws the buffers)."""
    try:
        buffers = _capture_cage_offset_buffers_numpy(obj, depsgraph, smooth_normals, uv_layer_name, uv_layer_required)
    except Exception as exc:  # noqa: BLE001 - the triangle capture below stays the reference
        if _is_capture_input_error(exc):
            raise
        buffers = None
    if buffers is not None:
        return buffers
    return offset_batch_buffers_from_triangles(
        capture_cage_source_triangles(
            obj,
            depsgraph,
            smooth_normals=smooth_normals,
            uv_layer_name=uv_layer_name,
            uv_layer_required=uv_layer_required,
        )
    )


def _capture_cage_offset_buffers_numpy(obj, depsgraph, smooth_normals, uv_layer_name, uv_layer_required):
    import numpy as np

    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=True)
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")
    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        uv_data = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name, required=uv_layer_required)
        loop_triangles = getattr(mesh, "loop_triangles", None)
        if loop_triangles is None or not hasattr(loop_triangles, "foreach_get"):
            return None
        triangle_count = len(loop_triangles)
        layers = _mesh_layers_numpy(
            mesh,
            want_loop_normals=not smooth_normals,
            want_averaged=bool(smooth_normals),
            matrix_world=obj_eval.matrix_world,
        )
        if layers is None:
            return None
        loop_count = int(layers["loop_vertex"].shape[0])
        triangle_loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("loops", triangle_loops)
        corner_loops = rna_buffers.as_i32(triangle_loops).astype(np.int64)
        corner_vertices = layers["loop_vertex"][corner_loops]

        matrix_world = obj_eval.matrix_world
        world_positions = _world_points_numpy(matrix_world, layers["vertex_positions"])
        if smooth_normals:
            world_normals = _world_normals_numpy(matrix_world, layers["averaged"])[corner_vertices]
        else:
            world_normals = _world_normals_numpy(matrix_world, layers["loop_normals"])[corner_loops]

        uv_rows = _uv_values_numpy(uv_data, loop_count)
        paint = _paint_values_numpy(mesh)
        corner_count = int(corner_loops.shape[0])
        uvs = _rows_as_tuples(uv_rows[corner_loops]) if uv_rows is not None else [(0.0, 0.0)] * corner_count
        paints = paint[corner_loops].tolist() if paint is not None else [1.0] * corner_count
        return OffsetBatchBuffers(
            positions=_rows_as_tuples(world_positions[corner_vertices]),
            normals=_rows_as_tuples(world_normals),
            uvs=uvs,
            paints=paints,
        )
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def _capture_object_edge_lines_numpy(obj, depsgraph, smooth_normals, with_uvs, uv_layer_name):
    """Bulk capture_object_edge_lines (no inflation lookup); None when the mesh cannot
    serve the array reads."""
    import numpy as np

    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=with_uvs)
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {obj.name}")
    try:
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()
        layers = _mesh_layers_numpy(
            mesh,
            want_loop_normals=not smooth_normals,
            want_averaged=bool(smooth_normals),
            matrix_world=obj_eval.matrix_world,
        )
        if layers is None:
            return None
        loop_vertex = layers["loop_vertex"]
        loop_count = int(loop_vertex.shape[0])
        vertex_count = int(layers["vertex_positions"].shape[0])
        matrix_world = obj_eval.matrix_world
        world_positions = _world_points_numpy(matrix_world, layers["vertex_positions"])

        loop_paint = None
        vertex_uv = None
        vertex_paint = None
        if with_uvs:
            loop_paint = _paint_values_numpy(mesh)
            uv_data = _resolve_uv_layer_data(mesh, uv_layer_name, object_name=obj.name, required=False)
            uv_rows = _uv_values_numpy(uv_data, loop_count)
            # The first loop of each vertex supplies its UV and paint (the loop version's setdefault).
            seen_vertices, first_loop = np.unique(loop_vertex, return_index=True)
            if uv_rows is not None:
                vertex_uv = np.zeros((vertex_count, 2), dtype=np.float32)
                vertex_uv[seen_vertices] = uv_rows[first_loop]
            if loop_paint is not None:
                vertex_paint = np.ones(vertex_count, dtype=np.float64)
                vertex_paint[seen_vertices] = loop_paint[first_loop]

        paint_a = paint_b = None
        if smooth_normals:
            edges = mesh.edges
            edge_count = len(edges)
            edge_vertices = rna_buffers.empty_u32_for_rna(edge_count * 2)
            edges.foreach_get("vertices", edge_vertices)
            ends = rna_buffers.as_i32(edge_vertices).astype(np.int64).reshape(edge_count, 2)
            end_a = ends[:, 0]
            end_b = ends[:, 1]
            world_normals = _world_normals_numpy(matrix_world, layers["averaged"])
            normals_a = world_normals[end_a]
            normals_b = world_normals[end_b]
            if vertex_paint is not None:
                paint_a = vertex_paint[end_a]
                paint_b = vertex_paint[end_b]
        else:
            # Every half-edge once: (vertex pair, both corner normals) is the dedupe key, so a
            # concave hard edge keeps one line per side and a soft or bridged edge keeps one.
            polygons = mesh.polygons
            polygon_count = len(polygons)
            loop_start = rna_buffers.empty_u32_for_rna(polygon_count)
            polygons.foreach_get("loop_start", loop_start)
            loop_start = rna_buffers.as_i32(loop_start).astype(np.int64)
            loop_total = rna_buffers.empty_u32_for_rna(polygon_count)
            polygons.foreach_get("loop_total", loop_total)
            loop_total = rna_buffers.as_i32(loop_total).astype(np.int64)
            if polygon_count <= 0 or int(loop_total.sum()) != loop_count or bool(np.any(loop_start[1:] < loop_start[:-1])):
                return None
            loop_polygon = np.repeat(np.arange(polygon_count), loop_total)
            local = np.arange(loop_count) - loop_start[loop_polygon]
            loop_a = np.arange(loop_count)
            loop_b = loop_start[loop_polygon] + (local + 1) % loop_total[loop_polygon]
            vertex_first = loop_vertex[loop_a]
            vertex_second = loop_vertex[loop_b]
            normal_first = layers["loop_normals"][loop_a]
            normal_second = layers["loop_normals"][loop_b]
            swap = vertex_first > vertex_second
            low_vertex = np.where(swap, vertex_second, vertex_first)
            high_vertex = np.where(swap, vertex_first, vertex_second)
            low_normal = np.where(swap[:, None], normal_second, normal_first)
            high_normal = np.where(swap[:, None], normal_first, normal_second)
            key = np.concatenate(
                [
                    low_vertex[:, None],
                    high_vertex[:, None],
                    np.rint(low_normal.astype(np.float64) * 1.0e4).astype(np.int64),
                    np.rint(high_normal.astype(np.float64) * 1.0e4).astype(np.int64),
                ],
                axis=1,
            )
            _unique, first = np.unique(key, axis=0, return_index=True)
            keep = np.sort(first)
            end_a, end_b = low_vertex[keep], high_vertex[keep]
            normals_a = _world_normals_numpy(matrix_world, low_normal[keep])
            normals_b = _world_normals_numpy(matrix_world, high_normal[keep])
            if loop_paint is not None:
                paint_a = loop_paint[np.where(swap, loop_b, loop_a)[keep]]
                paint_b = loop_paint[np.where(swap, loop_a, loop_b)[keep]]

        edge_total = int(end_a.shape[0])
        positions = np.empty((edge_total * 2, 3), dtype=np.float32)
        positions[0::2] = world_positions[end_a]
        positions[1::2] = world_positions[end_b]
        normals = np.empty((edge_total * 2, 3), dtype=np.float32)
        normals[0::2] = normals_a
        normals[1::2] = normals_b
        uvs: list = []
        paints: list = []
        if with_uvs:
            uv_pairs = np.zeros((edge_total * 2, 2), dtype=np.float32)
            if vertex_uv is not None:
                uv_pairs[0::2] = vertex_uv[end_a]
                uv_pairs[1::2] = vertex_uv[end_b]
            uvs = _rows_as_tuples(uv_pairs)
            if paint_a is not None:
                paint_pairs = np.empty(edge_total * 2, dtype=np.float64)
                paint_pairs[0::2] = paint_a
                paint_pairs[1::2] = paint_b
                paints = paint_pairs.tolist()
        return OffsetBatchBuffers(
            positions=_rows_as_tuples(positions), normals=_rows_as_tuples(normals), uvs=uvs, paints=paints
        )
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def write_obj_from_triangles(
    object_name: str,
    triangles: list[TriangleData],
    destination: Path,
    *,
    world_to_object: list[float] | None = None,
    cache_key: str = "",
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
    payload_sink: list | None = None,
) -> protocol.ExportedMeshRef:
    """Write ``triangles`` as a triangle-soup mesh and return its ref. ``payload_sink``, when
    given, receives the built payload bytes (none if the payload could not be built), so a
    caller can write the same cage again with :func:`write_obj_from_payload`."""
    try:
        if isinstance(triangles, cage_soup.CageSoup):
            payload = mesh_transport.build_triangle_soup_mesh_payload_from_soup(triangles)
        else:
            payload = mesh_transport.build_triangle_soup_mesh_payload_from_corner_objects(triangles)
    except Exception:
        payload = None
    if payload is not None:
        if payload_sink is not None:
            payload_sink.append(payload)
        resolved_path = mesh_transport.write_triangle_soup_payload_ref(
            destination,
            payload,
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
        )
    else:
        resolved_path = mesh_transport.write_triangle_soup_mesh_ref(
            destination,
            triangles,
            workspace_key=workspace_key,
            use_shared_memory=use_shared_memory,
        )
    return protocol.ExportedMeshRef(
        name=naming.sanitize_token(object_name),
        object_name=object_name,
        role="",
        path=str(resolved_path),
        cache_key=str(cache_key or ""),
        world_to_object=list(world_to_object or []),
    )


def write_obj_from_payload(
    object_name: str,
    payload: bytes,
    destination: Path,
    *,
    world_to_object: list[float] | None = None,
    cache_key: str = "",
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> protocol.ExportedMeshRef:
    """:func:`write_obj_from_triangles` for a payload built earlier (same file, same ref)."""
    resolved_path = mesh_transport.write_triangle_soup_payload_ref(
        destination,
        payload,
        workspace_key=workspace_key,
        use_shared_memory=use_shared_memory,
    )
    return protocol.ExportedMeshRef(
        name=naming.sanitize_token(object_name),
        object_name=object_name,
        role="",
        path=str(resolved_path),
        cache_key=str(cache_key or ""),
        world_to_object=list(world_to_object or []),
    )


def mesh_geometry_from_triangles(
    triangles: list[TriangleData],
    *,
    digits: int = 6,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    positions: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertex_lookup: dict[tuple[str, tuple[float, float, float], tuple[float, float, float]], int] = {}

    for triangle in triangles:
        face: list[int] = []
        for corner in triangle.corners:
            key = (
                triangle.object_name,
                _vector_position_key(corner.source_position, digits=digits),
                _vector_position_key(corner.position, digits=digits),
            )
            vertex_index = vertex_lookup.get(key)
            if vertex_index is None:
                vertex_index = len(positions)
                vertex_lookup[key] = vertex_index
                positions.append(
                    (
                        float(corner.position.x),
                        float(corner.position.y),
                        float(corner.position.z),
                    )
                )
            face.append(vertex_index)
        faces.append((face[0], face[1], face[2]))

    return positions, faces


def _geometry_vertex_adjacency(vertex_count: int, faces: list[tuple[int, int, int]]) -> list[set[int]]:
    adjacency: list[set[int]] = [set() for _ in range(max(0, int(vertex_count)))]
    for face in faces:
        if len(face) != 3:
            continue
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        if min(a, b, c) < 0 or max(a, b, c) >= len(adjacency):
            continue
        adjacency[a].update((b, c))
        adjacency[b].update((a, c))
        adjacency[c].update((a, b))
    return adjacency


def _boundary_vertices(faces: list[tuple[int, int, int]]) -> set[int]:
    edge_use_count: dict[tuple[int, int], int] = {}
    for face in faces:
        if len(face) != 3:
            continue
        indices = (int(face[0]), int(face[1]), int(face[2]))
        for start_index, end_index in _TRIANGLE_EDGE_INDICES:
            edge = tuple(sorted((indices[start_index], indices[end_index])))
            edge_use_count[edge] = edge_use_count.get(edge, 0) + 1

    boundary: set[int] = set()
    for (vertex_a, vertex_b), use_count in edge_use_count.items():
        if use_count == 1:
            boundary.add(vertex_a)
            boundary.add(vertex_b)
    return boundary


def compute_vertex_normals_from_geometry(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
) -> list[Vector]:
    normals = [Vector((0.0, 0.0, 0.0)) for _ in range(len(positions))]
    for face in faces:
        if len(face) != 3:
            continue
        index_a, index_b, index_c = (int(face[0]), int(face[1]), int(face[2]))
        if min(index_a, index_b, index_c) < 0 or max(index_a, index_b, index_c) >= len(positions):
            continue
        point_a = Vector(positions[index_a])
        point_b = Vector(positions[index_b])
        point_c = Vector(positions[index_c])
        face_normal = (point_b - point_a).cross(point_c - point_a)
        if face_normal.length_squared <= 1.0e-12:
            continue
        normals[index_a] += face_normal
        normals[index_b] += face_normal
        normals[index_c] += face_normal

    return [_normalized(normal) for normal in normals]


def inflate_mesh_geometry(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    distance: float,
) -> list[tuple[float, float, float]]:
    if not positions or abs(float(distance)) <= 1.0e-12:
        return [tuple(position) for position in positions]

    vertex_normals = compute_vertex_normals_from_geometry(positions, faces)
    scaled_distance = float(distance)
    inflated_positions: list[tuple[float, float, float]] = []
    for position, normal in zip(positions, vertex_normals):
        inflated = Vector(position) + (normal * scaled_distance)
        inflated_positions.append((float(inflated.x), float(inflated.y), float(inflated.z)))
    return inflated_positions


def smooth_mesh_geometry(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    *,
    factor: float = 0.5,
    iterations: int = 1,
    preserve_boundary: bool = True,
) -> list[tuple[float, float, float]]:
    if not positions:
        return []

    adjacency = _geometry_vertex_adjacency(len(positions), faces)
    boundary_vertices = _boundary_vertices(faces) if preserve_boundary else set()
    clamped_factor = max(0.0, min(1.0, float(factor)))
    remaining_iterations = max(0, int(iterations))
    current_positions = [Vector(position) for position in positions]

    for _iteration in range(remaining_iterations):
        updated_positions = [position.copy() for position in current_positions]
        for vertex_index, neighbors in enumerate(adjacency):
            if not neighbors:
                continue
            if vertex_index in boundary_vertices:
                continue

            neighbor_average = Vector((0.0, 0.0, 0.0))
            for neighbor_index in neighbors:
                neighbor_average += current_positions[neighbor_index]
            neighbor_average *= 1.0 / float(len(neighbors))
            updated_positions[vertex_index] = (
                current_positions[vertex_index] * (1.0 - clamped_factor)
            ) + (neighbor_average * clamped_factor)
        current_positions = updated_positions

    return [(float(position.x), float(position.y), float(position.z)) for position in current_positions]


def cleanup_spike_vertices(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    *,
    spike_ratio: float = 2.5,
    blend: float = 0.85,
    preserve_boundary: bool = True,
) -> list[tuple[float, float, float]]:
    if not positions:
        return []

    adjacency = _geometry_vertex_adjacency(len(positions), faces)
    boundary_vertices = _boundary_vertices(faces) if preserve_boundary else set()
    current_positions = [Vector(position) for position in positions]
    clamped_ratio = max(1.0, float(spike_ratio))
    clamped_blend = max(0.0, min(1.0, float(blend)))
    cleaned_positions = [position.copy() for position in current_positions]

    for vertex_index, neighbors in enumerate(adjacency):
        if len(neighbors) < 3:
            continue
        if vertex_index in boundary_vertices:
            continue

        center = current_positions[vertex_index]
        neighbor_average = Vector((0.0, 0.0, 0.0))
        for neighbor_index in neighbors:
            neighbor = current_positions[neighbor_index]
            neighbor_average += neighbor
        neighbor_average *= 1.0 / float(len(neighbors))

        support_radius = 0.0
        for neighbor_index in neighbors:
            support_radius += float((current_positions[neighbor_index] - neighbor_average).length)
        support_radius /= float(len(neighbors))
        if support_radius <= 1.0e-12:
            continue

        deviation = float((center - neighbor_average).length)
        if deviation <= (support_radius * clamped_ratio):
            continue

        cleaned_positions[vertex_index] = (
            center * (1.0 - clamped_blend)
        ) + (neighbor_average * clamped_blend)

    return [(float(position.x), float(position.y), float(position.z)) for position in cleaned_positions]


def draw_buffers_from_triangles(
    triangles: list[TriangleData],
    include_lines: bool = True,
) -> DrawBuffers:
    fill_positions: list[tuple[float, float, float]] = []
    line_positions: list[tuple[float, float, float]] = []

    for triangle in triangles:
        positions = [corner.position for corner in triangle.corners]
        fill_positions.extend((float(pos.x), float(pos.y), float(pos.z)) for pos in positions)

        if include_lines:
            for start_index, end_index in _TRIANGLE_EDGE_INDICES:
                start = positions[start_index]
                end = positions[end_index]
                line_positions.append((float(start.x), float(start.y), float(start.z)))
                line_positions.append((float(end.x), float(end.y), float(end.z)))

    return DrawBuffers(
        fill_positions=fill_positions,
        line_positions=line_positions,
    )


def offset_batch_buffers_from_triangles(
    triangles: list[TriangleData],
    *,
    inflation_lookup: dict[tuple[str, tuple[float, float, float]], float] | None = None,
    digits: int = 6,
) -> OffsetBatchBuffers:
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    paints: list[float] = []
    for triangle in triangles:
        for corner in triangle.corners:
            source_position = corner.source_position
            normal = corner.normal
            if inflation_lookup is not None:
                key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
                inflation = inflation_lookup.get(key, 1.0)
                normal = normal * inflation
            positions.append((float(source_position.x), float(source_position.y), float(source_position.z)))
            normals.append((float(normal.x), float(normal.y), float(normal.z)))
            uvs.append(corner.uv)
            paints.append(_corner_paint_offset_multiplier(corner))
    return OffsetBatchBuffers(positions=positions, normals=normals, uvs=uvs, paints=paints)


def fitted_offset_batch_buffers_from_triangles(triangles: list[TriangleData]) -> OffsetBatchBuffers:
    """Offset-format buffers for an already-displaced cage (Automatic / Custom).

    Uses each corner's *final* position and its (smooth) normal so the cage can be drawn
    through the shared offset / offset-lit shaders at a zero displacement.  This lets the
    Automatic and Custom cages honour the same ``cage_lit_shading`` preference and colour
    uniforms as the Distance cage, instead of falling back to a flat unlit batch — so
    switching cage mode no longer swaps the shader used to draw the cage.
    """
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    for triangle in triangles:
        for corner in triangle.corners:
            position = corner.position
            normal = corner.normal
            positions.append((float(position.x), float(position.y), float(position.z)))
            normals.append((float(normal.x), float(normal.y), float(normal.z)))
            uvs.append(corner.uv)
    return OffsetBatchBuffers(positions=positions, normals=normals, uvs=uvs)


# ---------------------------------------------------------------------------
# Automatic cage as the bake traces it. A fitted corner is ``source + normal * d``, but the
# bake does not start its rays on the flat triangle between three such corners: every
# texel's ray leaves its low point along the INTERPOLATED low normal and reaches the
# INTERPOLATED cage distance (projection_ray_span, skew 0). Over a convex patch that surface
# bulges past the flat triangle, so drawing the flat triangles showed high detail poking
# "in front of" a cage that actually encloses it (and the coverage check, which tests the
# traced surface, correctly said blue). These helpers tessellate each fitted triangle and
# place every sample on the traced surface, for the fill and for the wireframe edges.
_BAKE_SURFACE_SEGMENTS = 3


def _bake_surface_point(triangle: TriangleData, w0: float, w1: float, w2: float):
    c0, c1, c2 = triangle.corners
    source = c0.source_position * w0 + c1.source_position * w1 + c2.source_position * w2
    normal = c0.normal * w0 + c1.normal * w1 + c2.normal * w2
    reach = (
        (c0.position - c0.source_position).length * w0
        + (c1.position - c1.source_position).length * w1
        + (c2.position - c2.source_position).length * w2
    )
    if normal.length_squared <= 1.0e-20:
        return source, normal
    unit = normal.normalized()
    return source + unit * reach, unit


def bake_surface_triangles(triangles: list[TriangleData], segments: int = _BAKE_SURFACE_SEGMENTS) -> list[TriangleData]:
    """Tessellate fitted cage triangles onto the surface the bake's rays start from."""
    n = max(1, int(segments))
    out: list[TriangleData] = []
    for triangle in triangles:
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                w1, w2 = i / n, j / n
                grid[(i, j)] = _bake_surface_point(triangle, 1.0 - w1 - w2, w1, w2)
        uv0, uv1, uv2 = (corner.uv for corner in triangle.corners)

        def corner(i, j):
            w1, w2 = i / n, j / n
            w0 = 1.0 - w1 - w2
            position, normal = grid[(i, j)]
            uv = (uv0[0] * w0 + uv1[0] * w1 + uv2[0] * w2, uv0[1] * w0 + uv1[1] * w1 + uv2[1] * w2)
            return TriangleCorner(source_position=position, position=position, uv=uv, normal=normal)

        for i in range(n):
            for j in range(n - i):
                out.append(TriangleData(object_name=triangle.object_name, corners=(corner(i, j), corner(i + 1, j), corner(i, j + 1))))
                if i + j < n - 1:
                    out.append(TriangleData(object_name=triangle.object_name, corners=(corner(i + 1, j), corner(i + 1, j + 1), corner(i, j + 1))))
    return out


def _triangle_corner_arrays(triangles: list[TriangleData]):
    """(source, position, normal, uv, paint) per corner as numpy arrays shaped (T, 3, k)."""
    import numpy as np

    count = len(triangles)
    flat = np.empty((count * 3, 12), dtype=np.float64)
    row = 0
    for triangle in triangles:
        for corner in triangle.corners:
            source = corner.source_position
            position = corner.position
            normal = corner.normal
            uv = corner.uv
            flat[row] = (
                source.x, source.y, source.z,
                position.x, position.y, position.z,
                normal.x, normal.y, normal.z,
                uv[0], uv[1],
                _corner_paint_offset_multiplier(corner),
            )
            row += 1
    flat = flat.reshape(count, 3, 12)
    return flat[:, :, 0:3], flat[:, :, 3:6], flat[:, :, 6:9], flat[:, :, 9:11], flat[:, :, 11]


def _bake_surface_grid(segments: int):
    """Barycentric weights (G, 3) of the tessellation grid and its sub-triangles (K, 3),
    in bake_surface_triangles' order."""
    import numpy as np

    n = max(1, int(segments))
    index = {}
    weights = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            index[(i, j)] = len(weights)
            w1, w2 = i / n, j / n
            weights.append((1.0 - w1 - w2, w1, w2))
    sub = []
    for i in range(n):
        for j in range(n - i):
            sub.append((index[(i, j)], index[(i + 1, j)], index[(i, j + 1)]))
            if i + j < n - 1:
                sub.append((index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]))
    return np.asarray(weights, dtype=np.float64), np.asarray(sub, dtype=np.int64)


def bake_surface_fill_buffers(triangles: list[TriangleData], segments: int = _BAKE_SURFACE_SEGMENTS) -> OffsetBatchBuffers:
    """fitted_offset_batch_buffers_from_triangles(bake_surface_triangles(triangles)), in numpy.

    The same tessellated traced surface, built without a Python object per sample: on a
    customer's 73-group gun the per-corner loops were ~15 s of every cage reload."""
    from array import array

    import numpy as np

    if not triangles:
        return OffsetBatchBuffers(positions=[], normals=[], uvs=[])
    source, position, normal, uv, _paint = _triangle_corner_arrays(triangles)
    weights, sub = _bake_surface_grid(segments)
    # weights (G, 3) against corners (T, 3, c): every triangle, every grid point.
    reach = np.linalg.norm(position - source, axis=2)
    base = np.einsum("gk,tkc->tgc", weights, source)
    blended = np.einsum("gk,tkc->tgc", weights, normal)
    distance = np.einsum("gk,tk->tg", weights, reach)
    length = np.sqrt((blended * blended).sum(axis=2))
    valid = (length * length) > 1.0e-20
    unit = np.where(valid[..., None], blended / np.where(valid, length, 1.0)[..., None], blended)
    points = np.where(valid[..., None], base + unit * distance[..., None], base)
    uvs = np.einsum("gk,tkc->tgc", weights, uv)
    order = sub.reshape(-1)
    return OffsetBatchBuffers(
        positions=array("f", points[:, order, :].astype(np.float32).tobytes()),
        normals=array("f", unit[:, order, :].astype(np.float32).tobytes()),
        uvs=array("f", uvs[:, order, :].astype(np.float32).tobytes()),
    )


def paint_offset_batch_buffers_from_cage(cage_triangles: list[TriangleData]) -> OffsetBatchBuffers:
    """paint_offset_batch_buffers_between_triangle_sets(sources, cage) for a cage whose
    corners carry their low source (offset_triangles_with_proximity_fit keeps it), in
    numpy and without capturing the low mesh a second time."""
    from array import array

    import numpy as np

    if not cage_triangles:
        return OffsetBatchBuffers(positions=[], normals=[], uvs=[])
    source, position, _normal, uv, paint = _triangle_corner_arrays(cage_triangles)
    return OffsetBatchBuffers(
        positions=array("f", source.astype(np.float32).tobytes()),
        normals=array("f", (position - source).astype(np.float32).tobytes()),
        uvs=array("f", uv.astype(np.float32).tobytes()),
        paints=array("f", paint.astype(np.float32).tobytes()),
    )


def bake_surface_edge_lines_numpy(
    triangles: list[TriangleData],
    segments: int = _BAKE_SURFACE_SEGMENTS,
    *,
    allowed_edges: set | None = None,
):
    """bake_surface_edge_lines in numpy: each edge once (first triangle that has it), only
    the mesh's real edges, bent onto the traced surface. Returns a flat ``array('f')``."""
    from array import array

    import numpy as np

    if not triangles:
        return array("f")
    n = max(1, int(segments))
    source, position, normal, _uv, _paint = _triangle_corner_arrays(triangles)
    names = [triangle.object_name for triangle in triangles]
    name_ids = {name: index for index, name in enumerate(dict.fromkeys(names))}
    name_of = np.asarray([name_ids[name] for name in names], dtype=np.int64)
    edge_pairs = np.asarray(_TRIANGLE_EDGE_INDICES, dtype=np.int64)  # (3, 2)
    a = np.round(source[:, edge_pairs[:, 0], :], 5)  # (T, 3, 3)
    b = np.round(source[:, edge_pairs[:, 1], :], 5)
    # Order each edge's endpoints like _edge_key (tuple comparison, a <= b).
    greater = (a[..., 0] > b[..., 0]) | (
        (a[..., 0] == b[..., 0]) & ((a[..., 1] > b[..., 1]) | ((a[..., 1] == b[..., 1]) & (a[..., 2] > b[..., 2])))
    )
    lo = np.where(greater[..., None], b, a)
    hi = np.where(greater[..., None], a, b)
    owner = np.repeat(name_of[:, None], 3, axis=1)[..., None].astype(np.float64)
    keys = np.concatenate([owner, lo, hi], axis=2).reshape(-1, 7)
    _unique, first = np.unique(keys, axis=0, return_index=True)
    first = np.sort(first)
    if allowed_edges is not None:
        names_by_id = list(name_ids)
        keep = []
        for flat_index in first.tolist():
            triangle_index, edge_index = divmod(flat_index, 3)
            corner_a, corner_b = _TRIANGLE_EDGE_INDICES[edge_index]
            corners = triangles[triangle_index].corners
            key = _edge_key(
                names_by_id[int(name_of[triangle_index])],
                corners[corner_a].source_position,
                corners[corner_b].source_position,
            )
            if key in allowed_edges:
                keep.append(flat_index)
        first = np.asarray(keep, dtype=np.int64)
    if first.size == 0:
        return array("f")
    triangle_index = first // 3
    edge_index = first % 3
    steps = np.arange(n + 1, dtype=np.float64) / n
    weights = np.zeros((first.size, n + 1, 3), dtype=np.float64)
    rows = np.arange(first.size)[:, None]
    weights[rows, np.arange(n + 1)[None, :], edge_pairs[edge_index, 0][:, None]] += 1.0 - steps[None, :]
    weights[rows, np.arange(n + 1)[None, :], edge_pairs[edge_index, 1][:, None]] += steps[None, :]
    src = source[triangle_index]
    pos = position[triangle_index]
    nrm = normal[triangle_index]
    reach = np.linalg.norm(pos - src, axis=2)
    base = np.einsum("egk,ekc->egc", weights, src)
    blended = np.einsum("egk,ekc->egc", weights, nrm)
    distance = np.einsum("egk,ek->eg", weights, reach)
    length = np.sqrt((blended * blended).sum(axis=2))
    valid = (length * length) > 1.0e-20
    unit = np.where(valid[..., None], blended / np.where(valid, length, 1.0)[..., None], blended)
    points = np.where(valid[..., None], base + unit * distance[..., None], base)
    lines = np.stack([points[:, :-1, :], points[:, 1:, :]], axis=2).reshape(-1, 3)
    return array("f", lines.astype(np.float32).tobytes())


def _edge_key(object_name: str, first: Vector, second: Vector, digits: int = 5):
    a = _vector_position_key(first, digits=digits)
    b = _vector_position_key(second, digits=digits)
    return (str(object_name or ""),) + ((a, b) if a <= b else (b, a))


def mesh_edge_keys(obj, depsgraph, digits: int = 5) -> set:
    """World-space keys of *obj*'s real mesh edges (no triangulation diagonals)."""
    obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph, preserve_all_data_layers=False)
    if mesh is None:
        return set()
    try:
        import numpy as np

        matrix = obj_eval.matrix_world
        # Each vertex transformed and keyed once (the same mathutils product and rounding
        # _edge_key applies), not twice per edge through RNA element lookups.
        vertex_keys = [_vector_position_key(matrix @ vertex.co, digits=digits) for vertex in mesh.vertices]
        edge_vertices = rna_buffers.empty_u32_for_rna(len(mesh.edges) * 2)
        mesh.edges.foreach_get("vertices", edge_vertices)
        name = str(obj.name or "")
        keys = set()
        for v0, v1 in edge_vertices.reshape(-1, 2).tolist():
            a, b = vertex_keys[v0], vertex_keys[v1]
            keys.add((name, a, b) if a <= b else (name, b, a))
        return keys
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()


def bake_surface_edge_lines(
    triangles: list[TriangleData],
    segments: int = _BAKE_SURFACE_SEGMENTS,
    *,
    allowed_edges: set | None = None,
) -> list[tuple[float, float, float]]:
    """The cage's edges bent onto the traced surface (LINES pairs).

    Each edge is drawn ONCE (a shared edge used to be emitted by both of its triangles,
    doubling a translucent line so the Automatic wire read brighter than the Distance
    wire), and with *allowed_edges* (``mesh_edge_keys``) only the mesh's real edges are
    drawn -- the Distance wire has no triangulation diagonals either.
    """
    n = max(1, int(segments))
    lines: list[tuple[float, float, float]] = []
    seen: set = set()
    for triangle in triangles:
        for a, b in _TRIANGLE_EDGE_INDICES:
            key = _edge_key(triangle.object_name, triangle.corners[a].source_position, triangle.corners[b].source_position)
            if key in seen:
                continue
            seen.add(key)
            if allowed_edges is not None and key not in allowed_edges:
                continue
            previous = None
            for step in range(n + 1):
                t = step / n
                weights = [0.0, 0.0, 0.0]
                weights[a] += 1.0 - t
                weights[b] += t
                point, _normal = _bake_surface_point(triangle, *weights)
                current = (float(point.x), float(point.y), float(point.z))
                if previous is not None:
                    lines.append(previous)
                    lines.append(current)
                previous = current
    return lines


def paint_offset_batch_buffers_between_triangle_sets(
    source_triangles: list[TriangleData],
    cage_triangles: list[TriangleData],
) -> OffsetBatchBuffers:
    """Buffers whose ``normal`` attribute is the full low-to-cage displacement.

    The paint-offset viewport shader multiplies this vector by the painted value
    and the group scale.  This makes Automatic and Custom cage previews use the
    same low-to-cage segment scaling as the baker instead of treating the paint
    map as a Distance-cage-only control.
    """
    if len(source_triangles) != len(cage_triangles):
        return OffsetBatchBuffers(positions=[], normals=[], uvs=[])

    positions: list[tuple[float, float, float]] = []
    displacements: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    paints: list[float] = []
    for source_triangle, cage_triangle in zip(source_triangles, cage_triangles):
        for source_corner, cage_corner in zip(source_triangle.corners, cage_triangle.corners):
            source_position = source_corner.position
            displacement = cage_corner.position - source_position
            positions.append((float(source_position.x), float(source_position.y), float(source_position.z)))
            displacements.append((float(displacement.x), float(displacement.y), float(displacement.z)))
            uvs.append(source_corner.uv)
            paints.append(_corner_paint_offset_multiplier(source_corner))
    return OffsetBatchBuffers(positions=positions, normals=displacements, uvs=uvs, paints=paints)


# Cage subdivision for the Distance + Smooth Cage display (and its coverage check).
#
# The bake fires each texel's ray from low_position + normalize(lerp(corner normals)) *
# offset * lerp(paint): the low position and the normal are interpolated LINEARLY over
# the low triangle, and only the direction is normalized (projection_hits.slang, the
# Distance branch). That cage bulges out of the flat triangle between offset corners
# wherever the corner normals differ. Subdividing with linear midpoints for every
# channel and normalizing the normals at the end reproduces it exactly at each
# subdivided vertex; the offset shader then adds normal * offset * paint. (The former
# weighted-Phong midpoints moved the BASE surface too, which the bake never does: on
# the BakeTester3 skull it drew 400 false red texels per 167k in the eye sockets and
# missed 152 real misses on the teeth, measured against a Height bake.)


def _unit(v: tuple) -> tuple:
    m = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if m < 1e-10:
        return v
    return (v[0]/m, v[1]/m, v[2]/m)


def _linear_midpoint(a: tuple, b: tuple) -> tuple:
    return tuple((x + y) * 0.5 for x, y in zip(a, b))


#: Input primitives (triangles / segments) subdivided per chunk. Each chunk's
#: temporaries scale with chunk * 4**iterations, so this bounds the transient
#: working set (~0.5 GB for 256k triangles at 2 iterations) independently of the
#: mesh size. The math is strictly per primitive, so chunking cannot change a bit.
_SUBDIVIDE_CHUNK_PRIMITIVES = 262_144


def _float32_array_of_length(length: int) -> array:
    # Sequence repetition allocates once and fills by memcpy doubling -- no
    # intermediate Python list or bytes object the size of the output.
    return array("f", [0.0]) * max(0, int(length))


def _subdivide_triangles_step_numpy(triangles, out=None):
    """One linear 1->4 split of (T, 3, C) float32 triangles, every channel at once.

    Writes into ``out`` (shape (T, 4, 3, C)) when given. Child order: (a, ab, ca),
    (ab, b, bc), (ca, bc, c), (ab, bc, ca).
    """
    import numpy as np

    a = triangles[:, 0, :]
    b = triangles[:, 1, :]
    c = triangles[:, 2, :]
    half = np.float32(0.5)
    ab = (a + b) * half
    bc = (b + c) * half
    ca = (c + a) * half
    if out is None:
        out = np.empty((len(triangles), 4, 3, triangles.shape[2]), dtype=triangles.dtype)
    out[:, 0, 0] = a
    out[:, 0, 1] = ab
    out[:, 0, 2] = ca
    out[:, 1, 0] = ab
    out[:, 1, 1] = b
    out[:, 1, 2] = bc
    out[:, 2, 0] = ca
    out[:, 2, 1] = bc
    out[:, 2, 2] = c
    out[:, 3, 0] = ab
    out[:, 3, 1] = bc
    out[:, 3, 2] = ca
    return out.reshape(-1, 3, triangles.shape[2])


def _subdivide_segments_step_numpy(segments, out=None):
    """One linear 1->2 split of (S, 2, C) float32 segments: (a, m), (m, b)."""
    import numpy as np

    a = segments[:, 0, :]
    b = segments[:, 1, :]
    m = (a + b) * np.float32(0.5)
    if out is None:
        out = np.empty((len(segments), 2, 2, segments.shape[2]), dtype=segments.dtype)
    out[:, 0, 0] = a
    out[:, 0, 1] = m
    out[:, 1, 0] = m
    out[:, 1, 1] = b
    return out.reshape(-1, 2, segments.shape[2])


def _subdivide_primitive_arrays(
    positions, normals, iterations: int, *, corners: int, chunk_primitives: int, extras=()
):
    """Subdivide a primitive soup; returns (positions, normals, [extras]) as flat float32
    arrays. Normals come back normalized (the bake's ray direction); *extras* (per-corner
    rows such as UVs or paint multipliers) are interpolated linearly."""
    import numpy as np

    positions = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
    normals = np.asarray(normals, dtype=np.float32).reshape(-1, 3)
    if len(positions) != len(normals) or (len(positions) % corners) != 0:
        raise ValueError("subdivide: positions/normals must be equal-length, whole primitives")
    extra_arrays = []
    for values in extras:
        values = np.asarray(values, dtype=np.float32).reshape(len(positions), -1)
        extra_arrays.append(values)
    widths = [3, 3] + [int(values.shape[1]) for values in extra_arrays]
    channels = sum(widths)
    iterations = max(0, int(iterations))
    growth = (4 if corners == 3 else 2) ** iterations
    step = _subdivide_triangles_step_numpy if corners == 3 else _subdivide_segments_step_numpy
    split = 4 if corners == 3 else 2
    primitive_count = len(positions) // corners
    output_rows = primitive_count * growth * corners
    outputs = [_float32_array_of_length(output_rows * width) for width in widths]
    if output_rows == 0:
        return outputs[0], outputs[1], outputs[2:]

    # Writable views over the output arrays: every chunk's last iteration is copied
    # straight into them, so the result exists once, already in the flat float32 layout
    # GPUVertBuf.attr_fill consumes without conversion.
    views = [
        np.frombuffer(output, dtype=np.float32).reshape(primitive_count * growth, corners, width)
        for output, width in zip(outputs, widths)
    ]
    sources = [positions, normals] + extra_arrays
    chunk = max(1, int(chunk_primitives))
    for start in range(0, primitive_count, chunk):
        end = min(start + chunk, primitive_count)
        rows = slice(start * corners, end * corners)
        stacked = np.concatenate([source[rows] for source in sources], axis=1).reshape(end - start, corners, channels)
        for iteration in range(iterations):
            out = np.empty((len(stacked), split, corners, channels), dtype=np.float32) if iteration == iterations - 1 else None
            stacked = step(stacked, out)
        offset = 0
        for view, width in zip(views, widths):
            view[start * growth:end * growth] = stacked[:, :, offset:offset + width]
            offset += width
        normal_rows = views[1][start * growth:end * growth].reshape(-1, 3)
        normal_rows[:] = _normalized_rows_numpy(normal_rows)
    del views
    return outputs[0], outputs[1], outputs[2:]


def subdivide_offset_arrays(
    positions,
    normals,
    iterations: int = 2,
    *,
    chunk_triangles: int = _SUBDIVIDE_CHUNK_PRIMITIVES,
    extras=(),
):
    """Subdivide a TRIS soup given as (N, 3) float32 corner rows (see the section note).

    Returns flat ``array('f')`` positions and normals (3 floats per corner), plus the
    interpolated *extras* list when any are given. Works in bounded chunks, so peak
    memory is output + one chunk of temporaries.
    """
    out_positions, out_normals, out_extras = _subdivide_primitive_arrays(
        positions, normals, iterations, corners=3, chunk_primitives=chunk_triangles, extras=extras
    )
    if extras:
        return out_positions, out_normals, out_extras
    return out_positions, out_normals


def subdivide_line_arrays(
    positions,
    normals,
    iterations: int = 2,
    *,
    chunk_segments: int = _SUBDIVIDE_CHUNK_PRIMITIVES,
    extras=(),
):
    """LINES counterpart of :func:`subdivide_offset_arrays` (2 corner rows per segment)."""
    out_positions, out_normals, out_extras = _subdivide_primitive_arrays(
        positions, normals, iterations, corners=2, chunk_primitives=chunk_segments, extras=extras
    )
    if extras:
        return out_positions, out_normals, out_extras
    return out_positions, out_normals


def _buffer_extras(buffers: OffsetBatchBuffers, vertex_count: int):
    """UV and paint rows that cover every corner, or None for each that does not."""
    uvs = getattr(buffers, "uvs", None)
    paints = getattr(buffers, "paints", None)
    uv_rows = _mesh_rows_to_numpy(uvs, 2) if uvs is not None and len(uvs) else None
    if uv_rows is not None and len(uv_rows) != vertex_count:
        uv_rows = None
    paint_rows = _mesh_rows_to_numpy(paints, 1) if paints is not None and len(paints) else None
    if paint_rows is not None and len(paint_rows) != vertex_count:
        paint_rows = None
    return uv_rows, paint_rows


def _subdivide_buffers_numpy(buffers: OffsetBatchBuffers, iterations: int, corners: int) -> OffsetBatchBuffers | None:
    positions = _mesh_rows_to_numpy(buffers.positions, 3)
    normals = _mesh_rows_to_numpy(buffers.normals, 3)
    if positions.size == 0 or normals.size == 0 or len(positions) != len(normals) or (len(positions) % corners) != 0:
        return None
    uv_rows, paint_rows = _buffer_extras(buffers, len(positions))
    extras = [values for values in (uv_rows, paint_rows) if values is not None]
    out_positions, out_normals, out_extras = _subdivide_primitive_arrays(
        positions, normals, iterations, corners=corners, chunk_primitives=_SUBDIVIDE_CHUNK_PRIMITIVES, extras=extras
    )
    result = OffsetBatchBuffers(positions=out_positions, normals=out_normals)
    remaining = list(out_extras)
    if uv_rows is not None:
        result.uvs = remaining.pop(0)
    if paint_rows is not None:
        result.paints = remaining.pop(0)
    return result


def _subdivide_offset_buffers_numpy(buffers: OffsetBatchBuffers, iterations: int) -> OffsetBatchBuffers | None:
    return _subdivide_buffers_numpy(buffers, iterations, 3)


def _subdivide_line_buffers_numpy(buffers: OffsetBatchBuffers, iterations: int) -> OffsetBatchBuffers | None:
    return _subdivide_buffers_numpy(buffers, iterations, 2)


def _subdivide_buffers_python(buffers: OffsetBatchBuffers, iterations: int, corners: int) -> OffsetBatchBuffers:
    """Pure-Python fallback of :func:`_subdivide_buffers_numpy` (positions and normals)."""
    positions = [tuple(row) for row in buffers.positions]
    normals = [tuple(row) for row in buffers.normals]
    for _ in range(iterations):
        new_positions: list[tuple] = []
        new_normals: list[tuple] = []
        for i in range(len(positions) // corners):
            p = positions[i * corners:(i + 1) * corners]
            n = normals[i * corners:(i + 1) * corners]
            if corners == 3:
                ab_p, bc_p, ca_p = _linear_midpoint(p[0], p[1]), _linear_midpoint(p[1], p[2]), _linear_midpoint(p[2], p[0])
                ab_n, bc_n, ca_n = _linear_midpoint(n[0], n[1]), _linear_midpoint(n[1], n[2]), _linear_midpoint(n[2], n[0])
                new_positions += [p[0], ab_p, ca_p, ab_p, p[1], bc_p, ca_p, bc_p, p[2], ab_p, bc_p, ca_p]
                new_normals += [n[0], ab_n, ca_n, ab_n, n[1], bc_n, ca_n, bc_n, n[2], ab_n, bc_n, ca_n]
            else:
                m_p, m_n = _linear_midpoint(p[0], p[1]), _linear_midpoint(n[0], n[1])
                new_positions += [p[0], m_p, m_p, p[1]]
                new_normals += [n[0], m_n, m_n, n[1]]
        positions = new_positions
        normals = new_normals
    return OffsetBatchBuffers(positions=positions, normals=[_unit(normal) for normal in normals])


#: Corner normals closer than this (1 - cos) count as equal: the bake cage over such a
#: primitive is exactly the flat one between its offset corners.
_CURVED_NORMAL_TOLERANCE = 1.0e-6


def _subdivide_buffers_where_curved_numpy(buffers: OffsetBatchBuffers, iterations: int, corners: int) -> OffsetBatchBuffers | None:
    """Subdivide only the primitives whose corner normals differ.

    Where every corner shares one normal, lerp(normal) never changes direction, so the
    bake's cage over that primitive is flat and drawing it unsubdivided is exact. An
    edge between a curved and a flat primitive has equal end normals, so its subdivided
    points stay on the straight edge: no cracks. Flat-shaded (hard-surface) lows, the
    usual Smooth Cage off case, then cost almost nothing extra.
    """
    import numpy as np

    positions = _mesh_rows_to_numpy(buffers.positions, 3)
    normals = _mesh_rows_to_numpy(buffers.normals, 3)
    if positions.size == 0 or normals.size == 0 or len(positions) != len(normals) or (len(positions) % corners) != 0:
        return None
    uv_rows, paint_rows = _buffer_extras(buffers, len(positions))
    channels = [positions, normals] + [values for values in (uv_rows, paint_rows) if values is not None]
    count = len(positions) // corners
    unit = _normalized_rows_numpy(normals).reshape(count, corners, 3)
    curved = np.zeros(count, dtype=bool)
    for i in range(corners):
        for j in range(i + 1, corners):
            curved |= (1.0 - np.einsum("ij,ij->i", unit[:, i], unit[:, j])) > _CURVED_NORMAL_TOLERANCE
    corner_mask = np.repeat(curved, corners)
    curved_rows = [channel[corner_mask] for channel in channels]
    flat_rows = [channel[~corner_mask] for channel in channels]
    sub_positions, sub_normals, sub_extras = _subdivide_primitive_arrays(
        curved_rows[0], curved_rows[1], iterations, corners=corners,
        chunk_primitives=_SUBDIVIDE_CHUNK_PRIMITIVES, extras=curved_rows[2:],
    )
    flat_rows[1] = _normalized_rows_numpy(flat_rows[1])
    merged = []
    for subdivided, flat in zip([sub_positions, sub_normals] + list(sub_extras), flat_rows):
        width = flat.shape[1] if flat.ndim == 2 else 1
        combined = np.concatenate([np.frombuffer(subdivided, dtype=np.float32).reshape(-1, width), flat.reshape(-1, width)])
        out = _float32_array_of_length(combined.size)
        np.frombuffer(out, dtype=np.float32)[:] = combined.reshape(-1)
        merged.append(out)
    result = OffsetBatchBuffers(positions=merged[0], normals=merged[1])
    remaining = merged[2:]
    if uv_rows is not None:
        result.uvs = remaining.pop(0)
    if paint_rows is not None:
        result.paints = remaining.pop(0)
    return result


def subdivide_offset_buffers_where_curved(buffers: OffsetBatchBuffers, iterations: int = 2) -> OffsetBatchBuffers:
    """:func:`subdivide_offset_buffers`, skipping triangles whose cage is already flat."""
    try:
        numpy_result = _subdivide_buffers_where_curved_numpy(buffers, iterations, 3)
    except Exception:
        numpy_result = None
    if numpy_result is not None:
        return numpy_result
    return subdivide_offset_buffers(buffers, iterations)


def subdivide_line_buffers_where_curved(buffers: OffsetBatchBuffers, iterations: int = 2) -> OffsetBatchBuffers:
    """:func:`subdivide_line_buffers`, skipping segments whose cage is already straight."""
    try:
        numpy_result = _subdivide_buffers_where_curved_numpy(buffers, iterations, 2)
    except Exception:
        numpy_result = None
    if numpy_result is not None:
        return numpy_result
    return subdivide_line_buffers(buffers, iterations)


def subdivide_offset_buffers(buffers: OffsetBatchBuffers, iterations: int = 2) -> OffsetBatchBuffers:
    """Subdivide a TRIS cage buffer into the bake's exact Distance cage (section note).

    UVs and paint multipliers that cover every corner are carried along, so a painted
    group draws the same dense cage through the paint shader.
    """
    try:
        numpy_result = _subdivide_offset_buffers_numpy(buffers, iterations)
    except Exception:
        numpy_result = None
    if numpy_result is not None:
        return numpy_result
    return _subdivide_buffers_python(buffers, iterations, 3)


def subdivide_line_buffers(buffers: OffsetBatchBuffers, iterations: int = 2) -> OffsetBatchBuffers:
    """LINES counterpart of :func:`subdivide_offset_buffers` (each segment split in two)."""
    try:
        numpy_result = _subdivide_line_buffers_numpy(buffers, iterations)
    except Exception:
        numpy_result = None
    if numpy_result is not None:
        return numpy_result
    return _subdivide_buffers_python(buffers, iterations, 2)


def sample_triangles(triangles: list[TriangleData], max_triangles: int) -> list[TriangleData]:
    if max_triangles <= 0 or len(triangles) <= max_triangles:
        return triangles

    triangle_count = len(triangles)
    sampled: list[TriangleData] = []
    for _index in range(max_triangles):
        bucket_start = int((_index * triangle_count) / float(max_triangles))
        bucket_end = int(((_index + 1) * triangle_count) / float(max_triangles))
        bucket_end = max(bucket_start + 1, min(bucket_end, triangle_count))
        bucket_size = max(1, bucket_end - bucket_start)
        # Deterministic stratified sampling avoids the visible striping caused by
        # taking every Nth triangle from mesh-order data.
        hash_value = ((_index * 1103515245) + 12345) & 0x7FFFFFFF
        bucket_offset = hash_value % bucket_size
        sampled.append(triangles[min(bucket_start + bucket_offset, triangle_count - 1)])
    return sampled


def _triangle_face_normal(triangle: TriangleData) -> Vector:
    point_a = triangle.corners[0].source_position
    point_b = triangle.corners[1].source_position
    point_c = triangle.corners[2].source_position
    return _normalized((point_b - point_a).cross(point_c - point_a))


def _triangle_area(triangle: TriangleData) -> float:
    point_a = triangle.corners[0].source_position
    point_b = triangle.corners[1].source_position
    point_c = triangle.corners[2].source_position
    return float(((point_b - point_a).cross(point_c - point_a)).length) * 0.5


#: Needle length floor as a fraction of the mesh's bounding diagonal, per unit of
#: line_length_scale. Needles scale with the triangle's own edge length, so a dense
#: low mesh (teeth, a rivet) got needles a few pixels long at any sane zoom while a
#: coarse one got long ones. The floor keeps them readable at model scale.
_SKEW_NEEDLE_BOUNDS_FLOOR = 0.25


def _triangle_set_bounds_diagonal(triangles: list[TriangleData]) -> float:
    lo = [math.inf, math.inf, math.inf]
    hi = [-math.inf, -math.inf, -math.inf]
    for triangle in triangles:
        for corner in triangle.corners:
            point = corner.source_position
            for axis, value in enumerate((float(point.x), float(point.y), float(point.z))):
                if value < lo[axis]:
                    lo[axis] = value
                if value > hi[axis]:
                    hi[axis] = value
    if lo[0] > hi[0]:
        return 0.0
    return math.sqrt(sum((hi[axis] - lo[axis]) ** 2 for axis in range(3)))


def _skew_needle_minimum_length(triangles: list[TriangleData], line_length_scale: float, minimum_line_length: float) -> float:
    requested = max(0.0, float(minimum_line_length))
    floor = float(line_length_scale) * _SKEW_NEEDLE_BOUNDS_FLOOR * _triangle_set_bounds_diagonal(triangles)
    return max(requested, floor)


def _triangle_average_edge_length(triangle: TriangleData) -> float:
    point_a = triangle.corners[0].source_position
    point_b = triangle.corners[1].source_position
    point_c = triangle.corners[2].source_position
    edge_lengths = (
        float((point_b - point_a).length),
        float((point_c - point_b).length),
        float((point_a - point_c).length),
    )
    return sum(edge_lengths) / 3.0


def _triangle_face_normal_at_positions(triangle: TriangleData) -> Vector:
    point_a = triangle.corners[0].position
    point_b = triangle.corners[1].position
    point_c = triangle.corners[2].position
    return _normalized((point_b - point_a).cross(point_c - point_a))


def _closest_point_on_triangle(point: Vector, triangle: TriangleData) -> Vector:
    vertex_a = triangle.corners[0].position
    vertex_b = triangle.corners[1].position
    vertex_c = triangle.corners[2].position

    edge_ab = vertex_b - vertex_a
    edge_ac = vertex_c - vertex_a
    offset_ap = point - vertex_a
    dot_ab_ap = edge_ab.dot(offset_ap)
    dot_ac_ap = edge_ac.dot(offset_ap)
    if dot_ab_ap <= 0.0 and dot_ac_ap <= 0.0:
        return vertex_a.copy()

    offset_bp = point - vertex_b
    dot_ab_bp = edge_ab.dot(offset_bp)
    dot_ac_bp = edge_ac.dot(offset_bp)
    if dot_ab_bp >= 0.0 and dot_ac_bp <= dot_ab_bp:
        return vertex_b.copy()

    barycentric_vc = (dot_ab_ap * dot_ac_bp) - (dot_ab_bp * dot_ac_ap)
    if barycentric_vc <= 0.0 and dot_ab_ap >= 0.0 and dot_ab_bp <= 0.0:
        edge_factor = dot_ab_ap / (dot_ab_ap - dot_ab_bp)
        return vertex_a + (edge_ab * edge_factor)

    offset_cp = point - vertex_c
    dot_ab_cp = edge_ab.dot(offset_cp)
    dot_ac_cp = edge_ac.dot(offset_cp)
    if dot_ac_cp >= 0.0 and dot_ab_cp <= dot_ac_cp:
        return vertex_c.copy()

    barycentric_vb = (dot_ab_cp * dot_ac_ap) - (dot_ab_ap * dot_ac_cp)
    if barycentric_vb <= 0.0 and dot_ac_ap >= 0.0 and dot_ac_cp <= 0.0:
        edge_factor = dot_ac_ap / (dot_ac_ap - dot_ac_cp)
        return vertex_a + (edge_ac * edge_factor)

    barycentric_va = (dot_ab_bp * dot_ac_cp) - (dot_ab_cp * dot_ac_bp)
    edge_bc = vertex_c - vertex_b
    if barycentric_va <= 0.0 and (dot_ac_bp - dot_ab_bp) >= 0.0 and (dot_ab_cp - dot_ac_cp) >= 0.0:
        edge_factor = (dot_ac_bp - dot_ab_bp) / ((dot_ac_bp - dot_ab_bp) + (dot_ab_cp - dot_ac_cp))
        return vertex_b + (edge_bc * edge_factor)

    denominator = 1.0 / (barycentric_va + barycentric_vb + barycentric_vc)
    weight_v = barycentric_vb * denominator
    weight_w = barycentric_vc * denominator
    return vertex_a + (edge_ab * weight_v) + (edge_ac * weight_w)


def _barycentric_grid_samples(resolution: int) -> list[tuple[float, float, float]]:
    """Return vertex positions of a regular barycentric grid at *resolution* subdivisions.

    At resolution N this produces (N+1)*(N+2)//2 evenly spaced sample points
    that form a clean triangular grid on the triangle surface.  This gives
    visually aligned, grid-like coverage rather than the earlier jittered layout.
    """
    n = max(1, int(resolution))
    inv = 1.0 / float(n)
    samples: list[tuple[float, float, float]] = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            wa = i * inv
            wb = j * inv
            wc = max(0.0, 1.0 - wa - wb)
            samples.append((wa, wb, wc))
    return samples


def _interpolate_position(triangle: TriangleData, weights: tuple[float, float, float]) -> Vector:
    result = Vector((0.0, 0.0, 0.0))
    for corner, weight in zip(triangle.corners, weights):
        result += corner.source_position * float(weight)
    return result


def _interpolate_cage_position(triangle: TriangleData, weights: tuple[float, float, float]) -> Vector:
    """Interpolated point on a cage triangle. Cage triangles keep the low point in
    source_position and the pushed-out point in position, so the cage lives here."""
    result = Vector((0.0, 0.0, 0.0))
    for corner, weight in zip(triangle.corners, weights):
        result += corner.position * float(weight)
    return result


def _interpolate_normal(triangle: TriangleData, weights: tuple[float, float, float]) -> Vector:
    result = Vector((0.0, 0.0, 0.0))
    for corner, weight in zip(triangle.corners, weights):
        result += corner.normal * float(weight)
    return _normalized(result)


def _interpolate_uv(triangle: TriangleData, weights: tuple[float, float, float]) -> tuple[float, float]:
    u = sum(corner.uv[0] * float(w) for corner, w in zip(triangle.corners, weights))
    v = sum(corner.uv[1] * float(w) for corner, w in zip(triangle.corners, weights))
    return (u, v)


def _blend_projection_direction(face_normal: Vector, correction_normal: Vector, correction_strength: float) -> Vector:
    clamped_strength = max(0.0, min(1.0, float(correction_strength)))
    if clamped_strength <= 0.0:
        return _normalized(face_normal)
    if clamped_strength >= 1.0:
        return _normalized(correction_normal)
    blended = (_normalized(face_normal) * (1.0 - clamped_strength)) + (_normalized(correction_normal) * clamped_strength)
    return _normalized(blended)


def _skew_deviation_color(face_normal: Vector, direction: Vector) -> tuple[float, float, float, float]:
    """Map deviation of *direction* from *face_normal* to a green→amber gradient.

    0° (aligned, no skew)  → bright green  (0.20, 0.95, 0.55, 0.90)
    90° (perpendicular)    → amber/orange  (1.00, 0.45, 0.08, 0.90)
    """
    dot = max(0.0, min(1.0, float(face_normal.dot(direction))))
    t = 1.0 - dot          # 0 = aligned → 1 = fully skewed
    t = min(1.0, t * 1.7)  # compress range so 60° already reads as fully amber
    r = 0.20 + t * 0.80
    g = 0.95 - t * 0.50
    b = 0.55 - t * 0.47
    return (r, g, b, 0.90)


def _skew_triangle_resolutions(triangle_areas, max_segments, max_triangle_resolution):
    """Allocate the bounded field across all faces before emitting any needles.

    Zero means a centroid sample, -1 means no sample. Reserve one needle per
    nondegenerate face when possible, then distribute the rest by desired density.
    If even centroids exceed the budget, space the selected faces across the mesh.
    """
    valid = [index for index, area in enumerate(triangle_areas) if area > 1.0e-12]
    resolutions = [-1] * len(triangle_areas)
    budget = max(0, int(max_segments))
    if not valid or not budget:
        return resolutions
    if budget < len(valid):
        for sample in range(budget):
            resolutions[valid[((2 * sample + 1) * len(valid)) // (2 * budget)]] = 0
        return resolutions

    reference_area = sum(triangle_areas[index] for index in valid) / len(valid)
    max_resolution = max(1, int(max_triangle_resolution))
    desired = [
        min(max_resolution, max(12, round(10.5 * (triangle_areas[index] / reference_area) ** 0.5 + 4.0)))
        for index in valid
    ]
    extras = [(resolution + 1) * (resolution + 2) // 2 - 1 for resolution in desired]
    total_extra = sum(extras)
    available_extra = min(total_extra, budget - len(valid))
    cumulative = allocated = 0
    for index, resolution, extra in zip(valid, desired, extras):
        cumulative += extra
        next_allocated = cumulative * available_extra // total_extra
        quota = 1 + next_allocated - allocated
        allocated = next_allocated
        # Keep a regular grid over the entire face instead of truncating one edge.
        resolutions[index] = min(resolution, max(0, int((math.sqrt(8 * quota + 1) - 3) / 2)))
    return resolutions


def _skew_grid_samples(resolution):
    if resolution == 0:
        return [(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)]
    return _barycentric_grid_samples(resolution)


def udim_tile_of_uv(u: float, v: float) -> int:
    """UDIM tile number of a global UV (1001 for the 0-1 square)."""
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v))


def sample_skew_correction(tiles, uvs):
    """Painted skew correction (0..1) at each global UV, exactly as the backend samples it.

    *tiles* maps a UDIM tile to (width, height, float32 HxW array, row 0 = v bottom), the
    paint_sampling.skew_correction_tiles contract. Bilinear, texel-centre convention, clamp
    to edge: map pixel (i, j) is centred at tile-local (i + 0.5) / w, (j + 0.5) / h, which is
    backend_skew_correction.cpp build_skew_correction_words. 0 where a tile has no map.
    """
    import numpy as np

    uvs = np.asarray(uvs, dtype=np.float64).reshape(-1, 2)
    out = np.zeros(len(uvs), dtype=np.float32)
    if not tiles or len(uvs) == 0:
        return out
    floor_u = np.floor(uvs[:, 0])
    floor_v = np.floor(uvs[:, 1])
    tile_ids = 1001 + floor_u.astype(np.int64) + 10 * floor_v.astype(np.int64)
    for tile, entry in tiles.items():
        mask = tile_ids == int(tile)
        if not mask.any():
            continue
        width, height, values = int(entry[0]), int(entry[1]), np.asarray(entry[2], dtype=np.float32)
        if width <= 0 or height <= 0 or values.size < width * height:
            continue
        grid = values.reshape(height, width)
        fx = (uvs[mask, 0] - floor_u[mask]) * width - 0.5
        fy = (uvs[mask, 1] - floor_v[mask]) * height - 0.5
        x0 = np.floor(fx)
        y0 = np.floor(fy)
        tx = (fx - x0).astype(np.float32)
        ty = (fy - y0).astype(np.float32)
        xi0 = np.clip(x0.astype(np.int64), 0, width - 1)
        xi1 = np.clip(x0.astype(np.int64) + 1, 0, width - 1)
        yi0 = np.clip(y0.astype(np.int64), 0, height - 1)
        yi1 = np.clip(y0.astype(np.int64) + 1, 0, height - 1)
        sampled = (
            grid[yi0, xi0] * (1.0 - tx) * (1.0 - ty)
            + grid[yi0, xi1] * tx * (1.0 - ty)
            + grid[yi1, xi0] * (1.0 - tx) * ty
            + grid[yi1, xi1] * tx * ty
        )
        out[mask] = np.clip(sampled, 0.0, 1.0)
    return out


def apply_skew_correction(base_dirs, face_normals, corrections, orient_normals):
    """Painter / Marmoset skew correction: bend each ray from *base_dirs* toward the low
    triangle's flat face normal by the painted correction (0 = unchanged, 1 = straight off
    the face). Each face normal is first flipped onto the side of *orient_normals* (the low
    projection normals), matching projection_apply_skew_correction in the shaders."""
    import numpy as np

    base = np.asarray(base_dirs, dtype=np.float64).reshape(-1, 3)
    face = np.asarray(face_normals, dtype=np.float64).reshape(-1, 3)
    orient = np.asarray(orient_normals, dtype=np.float64).reshape(-1, 3)
    c = np.clip(np.asarray(corrections, dtype=np.float64).reshape(-1), 0.0, 1.0)[:, None]
    face = np.where((np.einsum("ij,ij->i", face, orient) < 0.0)[:, None], -face, face)
    blended = base * (1.0 - c) + face * c
    lengths = np.sqrt(np.einsum("ij,ij->i", blended, blended))[:, None]
    safe = np.where(lengths > 1.0e-12, blended / np.where(lengths > 1.0e-12, lengths, 1.0), base)
    return safe


def _painted_corner_skews(triangles: list[TriangleData], paint_image, strength: float):
    """Legacy 1.0.x Paint Skew image, per corner (canvas red x Skew Amount), clamped 0..1,
    the way the exporter writes vertex.paint_skew (paint_sampling.sample_image_red_channel_numpy).
    With no canvas the Skew Amount applies everywhere, as the backend's group fallback does.
    Only Custom / Automatic cages bend toward the cage by it; the bake only ever sees these
    corner values (interpolated across the triangle), so the needles must too."""
    import numpy as np

    corner_count = len(triangles) * 3
    skews = None
    if paint_image is not None:
        from .paint_sampling import sample_image_red_channel_numpy

        corner_uvs = np.fromiter(
            (component for triangle in triangles for corner in triangle.corners for component in corner.uv),
            dtype=np.float32,
            count=corner_count * 2,
        )
        skews = sample_image_red_channel_numpy(paint_image, corner_uvs)
    if skews is None:
        skews = np.ones(corner_count, dtype=np.float32)
    return np.clip(np.asarray(skews, dtype=np.float32) * float(strength), 0.0, 1.0)


def _emit_corrected_needles(records, skew_correction_tiles, max_segments: int) -> OffsetBatchBuffers:
    """Finish a needle field: bend each base ray toward its triangle's face normal by the
    per-pixel Paint Skew correction at the needle's UV (sample_skew_correction +
    apply_skew_correction, the backend's projection_skew_correction_at +
    projection_apply_skew_correction), then build the line buffers.

    *records*: (start, base_direction, face_normal, orient_normal, uv, base_length) per needle."""
    import numpy as np

    records = records[: max(0, int(max_segments))]
    if not records:
        return OffsetBatchBuffers(positions=[], normals=[])
    directions = np.array([(r[1].x, r[1].y, r[1].z) for r in records], dtype=np.float64)
    if skew_correction_tiles:
        corrections = sample_skew_correction(skew_correction_tiles, [r[4] for r in records])
        if np.any(corrections > 0.0):
            faces = np.array([(r[2].x, r[2].y, r[2].z) for r in records], dtype=np.float64)
            orients = np.array([(r[3].x, r[3].y, r[3].z) for r in records], dtype=np.float64)
            corrected = apply_skew_correction(directions, faces, corrections, orients)
            directions = np.where((corrections > 0.0)[:, None], corrected, directions)

    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    colors: list[tuple[float, float, float, float]] = []
    for record, row in zip(records, directions):
        start, _base, face_normal, orient, _uv, base_length = record
        direction = Vector((float(row[0]), float(row[1]), float(row[2])))
        end = start + direction * base_length
        # Colour is the tilt away from the flat face (flipped onto the ray's side): green =
        # straight off the face, amber = skewed (by Smooth Cage at hard corners, by the cage
        # direction, or left in place where no correction is painted).
        face = face_normal if face_normal.dot(orient) >= 0.0 else face_normal * -1.0
        color = _skew_deviation_color(face, direction)
        positions.append((float(start.x), float(start.y), float(start.z)))
        positions.append((float(end.x), float(end.y), float(end.z)))
        normals.append((float(direction.x), float(direction.y), float(direction.z)))
        normals.append((float(direction.x), float(direction.y), float(direction.z)))
        colors.append(color)
        colors.append(color)
    return OffsetBatchBuffers(positions=positions, normals=normals, colors=colors)


def skew_direction_field_buffers_from_triangles(
    triangles: list[TriangleData],
    *,
    max_segments: int = 4096,
    max_triangle_resolution: int = 4,
    line_length_scale: float = 0.18,
    minimum_line_length: float = 0.0,
    correction_strength: float = 1.0,
    paint_image=None,
    smooth_normals: bool = True,
    skew_correction_tiles=None,
) -> OffsetBatchBuffers:
    """Needles for a distance cage. The bake ray is the interpolated normal the
    *triangles* carry (capture_projection_ray_triangles: welded with Smooth Cage on,
    split corner normals off), bent toward the face normal by the per-pixel Paint Skew
    correction (*skew_correction_tiles*, paint_sampling.skew_correction_tiles). A legacy
    1.0.x skew image never applied to Distance cages, so *paint_image* and
    *correction_strength* are accepted for the sibling builder's signature and ignored
    (the canvas pixels are never read); *smooth_normals* is kept for callers."""
    del paint_image, correction_strength
    if not triangles or max_segments <= 0:
        return OffsetBatchBuffers(positions=[], normals=[])

    triangle_areas = [_triangle_area(triangle) for triangle in triangles]
    resolutions = _skew_triangle_resolutions(triangle_areas, max_segments, max_triangle_resolution)
    clamped_line_length_scale = max(0.01, float(line_length_scale))
    minimum_length = _skew_needle_minimum_length(triangles, clamped_line_length_scale, minimum_line_length)

    records = []
    for triangle, resolution in zip(triangles, resolutions):
        if resolution < 0:
            continue
        average_edge_length = _triangle_average_edge_length(triangle)
        if average_edge_length <= 1.0e-12:
            continue
        base_length = max(average_edge_length * clamped_line_length_scale, minimum_length)
        if base_length <= 1.0e-12:
            continue
        face_normal = _triangle_face_normal(triangle)
        for weights in _skew_grid_samples(resolution):
            # Distance cage: the bake traces along the projection normal
            # (projection_low_normal, the interpolated vertex normal in both modes).
            direction = _normalized(_interpolate_normal(triangle, weights))
            if direction.length_squared <= 1.0e-12:
                continue
            records.append((
                _interpolate_position(triangle, weights), direction, face_normal, direction,
                _interpolate_uv(triangle, weights), base_length,
            ))
            if len(records) >= max_segments:
                return _emit_corrected_needles(records, skew_correction_tiles, max_segments)
    return _emit_corrected_needles(records, skew_correction_tiles, max_segments)


def skew_direction_field_buffers_between_triangle_sets(
    source_triangles: list[TriangleData],
    target_triangles: list[TriangleData],
    *,
    max_segments: int = 4096,
    max_triangle_resolution: int = 4,
    line_length_scale: float = 0.18,
    minimum_line_length: float = 0.0,
    correction_strength: float = 1.0,
    paint_image=None,
    smooth_normals: bool = True,
    skew_correction_tiles=None,
) -> OffsetBatchBuffers:
    """Needles for a custom or automatic cage: the bake ray starts from the projection
    normal (welded with Smooth Cage on, split corner normal off), blends toward the
    direction to the matching cage point by a legacy 1.0.x skew image (*paint_image* x
    *correction_strength*, per corner), then bends toward the face normal by the per-pixel
    Paint Skew correction (*skew_correction_tiles*)."""
    if not source_triangles or not target_triangles or len(source_triangles) != len(target_triangles) or max_segments <= 0:
        return OffsetBatchBuffers(positions=[], normals=[])

    triangle_areas = [_triangle_area(triangle) for triangle in source_triangles]
    resolutions = _skew_triangle_resolutions(triangle_areas, max_segments, max_triangle_resolution)

    # Legacy per-corner skew, interpolated per needle: exactly what the bake uses
    # (interpolate_projection_paint_skew over the exported vertex.paint_skew). Only a 1.0.x
    # skew image carries it; without one the Skew Amount alone is the group fallback.
    corner_skews = (
        _painted_corner_skews(source_triangles, paint_image, float(correction_strength))
        if float(correction_strength) > 0.0
        else None
    )
    clamped_line_length_scale = max(0.01, float(line_length_scale))
    minimum_length = _skew_needle_minimum_length(source_triangles, clamped_line_length_scale, minimum_line_length)

    records = []
    for triangle_index, (source_triangle, target_triangle, resolution) in enumerate(
        zip(source_triangles, target_triangles, resolutions)
    ):
        if resolution < 0:
            continue
        average_edge_length = _triangle_average_edge_length(source_triangle)
        if average_edge_length <= 1.0e-12:
            continue
        base_length = max(average_edge_length * clamped_line_length_scale, minimum_length)
        face_normal = _triangle_face_normal(source_triangle)
        triangle_skews = (
            corner_skews[triangle_index * 3 : triangle_index * 3 + 3] if corner_skews is not None else (0.0, 0.0, 0.0)
        )
        for weights in _skew_grid_samples(resolution):
            start = _interpolate_position(source_triangle, weights)
            # What the bake does for a custom or automatic cage (projection_ray_span, cage
            # kind 1): start from the projection normal and blend toward the direction from
            # this point to the matching cage point by the legacy skew.
            projection_normal = _normalized(_interpolate_normal(source_triangle, weights))
            cage_direction = _interpolate_cage_position(target_triangle, weights) - start
            if cage_direction.length_squared <= 1.0e-12:
                cage_direction = projection_normal
            skew = sum(float(corner_skew) * float(weight) for corner_skew, weight in zip(triangle_skews, weights))
            direction = _blend_projection_direction(projection_normal, cage_direction, skew)
            if direction.length_squared <= 1.0e-12:
                continue
            records.append((
                start, direction, face_normal, projection_normal,
                _interpolate_uv(source_triangle, weights), base_length,
            ))
            if len(records) >= max_segments:
                return _emit_corrected_needles(records, skew_correction_tiles, max_segments)
    return _emit_corrected_needles(records, skew_correction_tiles, max_segments)


def skew_needle_vertex_streams(buffers):
    """Split (start, end) line pairs into the skew shader's streams: every vertex
    sits at the needle's start, the tip carries the needle vector so the shader can
    scale it by the live length slider, and both vertices carry the unit needle
    direction so the shader can light the needle by its orientation (the base
    vertex's needle vector is zero, so it cannot be used for that)."""
    positions = list(buffers.positions)
    colors = list(buffers.colors)
    n = len(positions) - (len(positions) % 2)
    pos_stream: list[tuple[float, float, float]] = []
    needle_stream: list[tuple[float, float, float]] = []
    color_stream: list[tuple[float, float, float, float]] = []
    dir_stream: list[tuple[float, float, float]] = []
    for index in range(0, n, 2):
        start = positions[index]
        end = positions[index + 1]
        needle = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
        length = math.sqrt(needle[0] * needle[0] + needle[1] * needle[1] + needle[2] * needle[2])
        direction = (
            (needle[0] / length, needle[1] / length, needle[2] / length) if length > 1.0e-12 else (0.0, 0.0, 1.0)
        )
        pos_stream.append(tuple(start))
        needle_stream.append((0.0, 0.0, 0.0))
        pos_stream.append(tuple(start))
        needle_stream.append(needle)
        color_stream.append(tuple(colors[index]))
        color_stream.append(tuple(colors[index + 1]))
        dir_stream.append(direction)
        dir_stream.append(direction)
    return pos_stream, needle_stream, color_stream, dir_stream


def build_triangle_bvh(triangles: list[TriangleData]):
    if not triangles:
        return None
    try:
        from mathutils.bvhtree import BVHTree
    except Exception:
        return None

    vertices: list[tuple[float, float, float]] = []
    polygons: list[tuple[int, int, int]] = []
    for triangle in triangles:
        face_indices: list[int] = []
        for corner in triangle.corners:
            position = corner.position
            vertices.append((float(position.x), float(position.y), float(position.z)))
            face_indices.append(len(vertices) - 1)
        polygons.append((face_indices[0], face_indices[1], face_indices[2]))
    try:
        return BVHTree.FromPolygons(vertices, polygons, all_triangles=True)
    except Exception:
        return None


_HIGH_BVH_CACHE: dict = {}
_HIGH_BVH_CACHE_ORDER: list = []
_HIGH_BVH_CACHE_MAX = 8


def get_or_build_high_mesh_bvh(cache_key, builder):
    """Memoize the world-space high-mesh BVHTree keyed by a geometry+transform signature.

    Building the tree dominates automatic-cage preview cost (multiple seconds for a
    multi-million-triangle high mesh).  The overlay static cache is rebuilt on many
    interactions that leave the high geometry untouched — most importantly toggling a bake
    group's cage visibility — so memoizing the tree keeps those rebuilds near-instant.
    Pass ``cache_key=None`` to bypass the cache.
    """
    if cache_key is not None:
        cached = _HIGH_BVH_CACHE.get(cache_key)
        if cached is not None:
            return cached
    bvh = builder()
    if cache_key is not None and bvh is not None:
        _HIGH_BVH_CACHE[cache_key] = bvh
        _HIGH_BVH_CACHE_ORDER.append(cache_key)
        while len(_HIGH_BVH_CACHE_ORDER) > _HIGH_BVH_CACHE_MAX:
            evicted = _HIGH_BVH_CACHE_ORDER.pop(0)
            _HIGH_BVH_CACHE.pop(evicted, None)
    return bvh


_AUTO_CAGE_FIT_CACHE: dict = {}
_AUTO_CAGE_FIT_ORDER: list = []
_AUTO_CAGE_FIT_MAX = 12


def clear_geometry_caches() -> None:
    """Drop the memoized high-mesh BVHs and fitted auto-cages.

    Nothing cleared these: not a file load, not addon unregister. Their keys lead with
    obj.as_pointer(), a runtime address, so a freshly opened file could be served an
    entry built for the PREVIOUS file's mesh at the same address - and until 8/12 newer
    entries pushed them out, the trees for deleted meshes stayed resident. Called from
    the overlay load_post.
    """
    _HIGH_BVH_CACHE.clear()
    _HIGH_BVH_CACHE_ORDER.clear()
    end_high_tree_pool()
    _AUTO_CAGE_FIT_CACHE.clear()
    _AUTO_CAGE_FIT_ORDER.clear()


def peek_auto_cage_fitted(cache_key):
    """The memoized fit for ``cache_key``, or None (never builds)."""
    if cache_key is None:
        return None
    return _AUTO_CAGE_FIT_CACHE.get(cache_key)


def get_or_build_auto_cage_fitted(cache_key, builder):
    """Memoize the fitted automatic-cage triangles for a bake group by geometry signature.

    Fitting re-runs a per-vertex nearest-surface query over the low mesh, which is ~1s for a
    dense mesh (``BVHTree.find_nearest`` is GIL-bound Python).  That cost is pure waste on a
    cage-visibility toggle — the geometry is unchanged — so caching the fitted result keeps
    toggling instant: only the cheap GPU batch upload is redone.  The key must fold in the low
    and high geometry+transform signatures and any parameter that changes the fit (average
    normals, dilation).  Pass ``cache_key=None`` to bypass.
    """
    if cache_key is not None:
        cached = _AUTO_CAGE_FIT_CACHE.get(cache_key)
        if cached is not None:
            return cached
    fitted = builder()
    if cache_key is not None and fitted:
        _AUTO_CAGE_FIT_CACHE[cache_key] = fitted
        _AUTO_CAGE_FIT_ORDER.append(cache_key)
        while len(_AUTO_CAGE_FIT_ORDER) > _AUTO_CAGE_FIT_MAX:
            evicted = _AUTO_CAGE_FIT_ORDER.pop(0)
            _AUTO_CAGE_FIT_CACHE.pop(evicted, None)
    return fitted


HIGH_SURFACE_INDEX_KEY_PREFIX = "high_surface_index_v1"


def high_surface_index_key(high_objects):
    """Memo key for :func:`build_high_surface_index` over ``high_objects``.

    Shared by the Cage Check overlay and the cage-offset estimator so one
    ``BVHTree.FromObject`` build per high mesh serves both. ``None`` when a
    signature cannot be taken (the callers then bypass the memo)."""
    try:
        from .overlay_keys import object_cache_signature

        return (
            HIGH_SURFACE_INDEX_KEY_PREFIX,
            tuple(object_cache_signature(obj) for obj in high_objects if obj is not None),
        )
    except Exception:
        return None


def build_high_surface_index(high_objects, depsgraph):
    """One OBJECT-space ``BVHTree.FromObject`` per high mesh plus its world matrix.

    Returns a tuple of ``(tree, matrix_world, matrix_world_inverse)`` entries or
    ``None`` when nothing could be built. ``FromObject`` builds C-side straight
    from the evaluated mesh: ~2.4 s for a 9 M-triangle high. The previous merged
    world-space builder looped every high vertex and triangle in Python before
    ``FromPolygons`` (16.4 s on the same mesh, 28.5 s for the 16.4 M-tri
    BakeTester3 set) and froze the main thread on every Height-map bake launch.
    Queries go through the inverse and distances are measured between WORLD
    points (:func:`nearest_surface_distance`), so scaled transforms stay exact.
    Never fall back to a Python merge builder here."""
    try:
        from mathutils.bvhtree import BVHTree
    except Exception:
        return None

    entries = []
    for obj in high_objects:
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        try:
            tree = BVHTree.FromObject(obj, depsgraph)
        except Exception:
            continue
        if tree is None:
            continue
        try:
            matrix = obj.matrix_world.copy()
            entries.append((tree, matrix, matrix.inverted()))
        except Exception:
            continue
    return tuple(entries) or None


def iter_high_surface_trees(high_objects, depsgraph):
    """Yield ``(obj, tree, matrix_world, matrix_world_inverse)`` one high at a time.

    Same trees and skip rules as :func:`build_high_surface_index`, but the caller holds
    only the current tree, so peak memory is the largest single high instead of all of
    them (the index keeps every tree alive at once)."""
    try:
        from mathutils.bvhtree import BVHTree
    except Exception:
        return
    for obj in high_objects:
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        try:
            tree = BVHTree.FromObject(obj, depsgraph)
        except Exception:
            continue
        if tree is None:
            continue
        try:
            matrix = obj.matrix_world.copy()
            matrix_inv = matrix.inverted()
        except Exception:
            continue
        yield obj, tree, matrix, matrix_inv
        del tree


def get_or_build_high_surface_index(high_objects, depsgraph, *, retain: bool = True):
    """Memoized :func:`build_high_surface_index` keyed by :func:`high_surface_index_key`.

    ``retain=False`` reuses an index the Cage Check overlay already memoized but never
    stores a new one: the trees are C-side (``BVHTree.FromObject``), ~140 B per high
    triangle, and a one-shot caller such as the bake launch left ~12 GB resident in
    Blender on an 87 M-triangle scene until the next file load (2026-09-28)."""
    objects = tuple(obj for obj in high_objects if obj is not None)
    if not objects:
        return None
    key = high_surface_index_key(objects)
    if retain:
        return get_or_build_high_mesh_bvh(key, lambda: build_high_surface_index(objects, depsgraph))
    if key is not None:
        cached = _HIGH_BVH_CACHE.get(key)
        if cached is not None:
            return cached
    if _TREE_POOL is not None:
        pooled = _pooled_high_surface_index(objects, depsgraph)
        if pooled is not False:
            return pooled
    return build_high_surface_index(objects, depsgraph)


#: Trees kept for the length of one multi-group fit run (the bake's cage prefit), so a high
#: mesh several groups share is built once instead of once per group (a 3.5 M-triangle
#: high shared by 40 groups: 11.9 s against 1.5 s). ``None`` outside a run, so nothing is
#: retained between runs. A tree is kept only while a later group in the run still uses
#: it, and only within a triangle budget, so peak memory stays near one big group's.
_TREE_POOL: dict | None = None
_TREE_POOL_USES: dict = {}
_TREE_POOL_TRIS: dict = {}
_TREE_POOL_BUDGET_TRIS = 4_000_000
_TREE_POOL_IDLE_SECONDS = 120.0
_TREE_POOL_STAMP = 0.0


def _pool_object_key(obj):
    try:
        from .overlay_keys import object_cache_signature, object_revision_signature

        return (object_revision_signature(obj), object_cache_signature(obj))
    except Exception:
        return None


def _pool_triangle_estimate(obj) -> int:
    data = getattr(obj, "data", None)
    return int(mesh_read.element_count(data, "polygons") * 1.5) if data is not None else 0


def begin_high_tree_pool(object_groups) -> None:
    """Start sharing high trees across the groups of one fit run.

    ``object_groups`` is one sequence of high objects per group about to be fitted. Only
    objects used by more than one of them are ever kept."""
    global _TREE_POOL, _TREE_POOL_STAMP
    end_high_tree_pool()
    uses: dict = {}
    for objects in object_groups:
        seen = set()
        for obj in objects:
            if obj is None or getattr(obj, "type", None) != "MESH":
                continue
            key = _pool_object_key(obj)
            if key is None or key in seen:
                continue
            seen.add(key)
            uses[key] = uses.get(key, 0) + 1
    shared = {key: count for key, count in uses.items() if count > 1}
    if not shared:
        return
    _TREE_POOL = {}
    _TREE_POOL_USES.update(shared)
    _TREE_POOL_STAMP = time.monotonic()


def end_high_tree_pool() -> None:
    global _TREE_POOL
    _TREE_POOL = None
    _TREE_POOL_USES.clear()
    _TREE_POOL_TRIS.clear()


def _pooled_high_surface_index(objects, depsgraph):
    """:func:`build_high_surface_index` over ``objects`` with shared trees reused, or
    ``False`` when the pool is stale (the caller then builds as usual)."""
    global _TREE_POOL_STAMP
    if _TREE_POOL is None:
        return False
    now = time.monotonic()
    if now - _TREE_POOL_STAMP > _TREE_POOL_IDLE_SECONDS:
        end_high_tree_pool()  # an abandoned run must not hold its trees
        return False
    _TREE_POOL_STAMP = now
    entries = []
    for obj in objects:
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        key = _pool_object_key(obj)
        remaining = _TREE_POOL_USES.get(key, 0) if key is not None else 0
        entry = _TREE_POOL.get(key) if remaining else None
        if entry is None:
            built = build_high_surface_index((obj,), depsgraph)
            if not built:
                continue
            entry = built[0]
            if remaining > 1:
                tris = _pool_triangle_estimate(obj)
                if sum(_TREE_POOL_TRIS.values()) + tris <= _TREE_POOL_BUDGET_TRIS:
                    _TREE_POOL[key] = entry
                    _TREE_POOL_TRIS[key] = tris
        if remaining:
            _TREE_POOL_USES[key] = remaining - 1
            if remaining - 1 <= 0:
                _TREE_POOL.pop(key, None)
                _TREE_POOL_TRIS.pop(key, None)
        entries.append(entry)
    return tuple(entries) or None


def nearest_surface_distance(surface_index, world_point):
    """World-space distance from ``world_point`` to the nearest high surface, or ``None``."""
    if not surface_index:
        return None
    best = None
    for tree, matrix, matrix_inv in surface_index:
        try:
            near = tree.find_nearest(matrix_inv @ world_point)
        except Exception:
            continue
        if near is None or near[0] is None:
            continue
        distance = ((matrix @ near[0]) - world_point).length
        if best is None or distance < best:
            best = distance
    return best


def _scene_reach_from_triangles(source_triangles: list[TriangleData]) -> float:
    """Estimate a safe outward ray distance from the source triangle bounding box."""
    if not source_triangles:
        return 10.0
    xs = ys = zs = None
    for tri in source_triangles:
        for c in tri.corners:
            p = c.source_position
            if xs is None:
                xs = [p.x, p.x]; ys = [p.y, p.y]; zs = [p.z, p.z]
            else:
                if p.x < xs[0]: xs[0] = p.x
                if p.x > xs[1]: xs[1] = p.x
                if p.y < ys[0]: ys[0] = p.y
                if p.y > ys[1]: ys[1] = p.y
                if p.z < zs[0]: zs[0] = p.z
                if p.z > zs[1]: zs[1] = p.z
    if xs is None:
        return 10.0
    diag = ((xs[1]-xs[0])**2 + (ys[1]-ys[0])**2 + (zs[1]-zs[0])**2)**0.5
    return max(1.0, diag * 3.0)


def outward_clearance_distance(position, normal, high_bvh, max_reach: float) -> float:
    """Measure how far the high mesh extends outward from *position* along *normal*.

    Casts a ray from ``position + normal * max_reach`` inward (along ``-normal``) to find
    the outermost high-poly surface point in the normal direction.  The clearance is the
    component of the hit vector projected onto the normal, which is the correct offset
    needed to push the cage vertex outside the high mesh along that normal.

    Returns 0.0 if no surface is found in the outward direction.
    """
    ray_start = position + normal * max_reach
    try:
        result = high_bvh.ray_cast(ray_start, -normal, max_reach * 2.0)
    except Exception:
        result = (None,)
    if result[0] is not None:
        to_hit = result[0] - position
        clearance = float(to_hit.dot(normal))
        if clearance > 0.0:
            return clearance
    return 0.0


_AUTO_CAGE_DILATION_ITERATIONS = 4
# Coverage safety margin as a fraction of the low-mesh diagonal. The per-vertex nearest
# distance fits each point tightly, but fine high-poly detail can still poke through a coarse
# low-poly *face* between vertices; a small model-relative margin lifts the cage just past
# that boundary without inflating it into a uniform offset.
_AUTO_CAGE_PADDING_DIAG_FRACTION = 0.0015
# Cap only for the CPU BVH fallback fit (GIL-bound find_nearest loop, ~seconds
# for millions of verts). The GPU path uses all vertices; this bounds the rare
# headless / no-compute-shader fallback so it stays interactive.
_CPU_FIT_MAX_SAMPLES = 1_200_000

# --- Cross-part contamination guards for the coverage fit -------------------------------
#
# build_coverage_offsets() binds every high vertex to its GLOBALLY nearest low face. In a
# nested assembly -- a housing with pipes and panels sitting a millimetre apart -- that
# answer is wrong wherever two parts are closer to each other than a part is to its own
# high: the high vertex scatters its full reach onto a NEIGHBOUR's face, and the two rings
# of dilation below spread it further. The neighbour's cage balloons by the gap between the
# parts, its bake rays run that far, and the neighbouring part's surface is stamped into its
# map -- hard-edged patches bounded by the low poly's own triangulation. The same mis-binding
# starves the correct low, whose detail then pokes through its own cage and misses.
#
# Two guards, in order of how completely they fix it:
#   * Match By Isolation partitions the fit so a high can only bind to the low it is named
#     for. Exact, and it is already what the backend traces (find_isolation_source_name in
#     backend/src/master_baker_backend.cpp). The fit used to ignore the flag entirely, so the
#     cage and the rays disagreed about which high a low was being projected from.
#   * Failing that, the outlier clamp bounds the blast radius. Legitimate detail never reaches
#     a large multiple of a mesh's own detail height, so a reach far past a low object's own
#     robust upper quantile is a different part and is clamped before it can dilate. Loose on
#     purpose: clamping real detail would cost bake coverage.
_AUTO_CAGE_OUTLIER_QUANTILE = 0.95
_AUTO_CAGE_OUTLIER_MULTIPLE = 8.0
#: Below this many fitted vertices an object has no distribution to speak of, and a threshold
#: fitted to a handful of samples would clamp real detail. Leave those objects alone.
_AUTO_CAGE_OUTLIER_MIN_SAMPLES = 32

#: The fit pairs on exactly the rule the backend traces on -- see
#: :func:`matching.isolation_high_index_for_low`.
isolation_high_index_for_low = matching.isolation_high_index_for_low


def _clamp_cross_part_reach(offsets_array, key_list, diagnostics) -> int:
    """Clamp each low object's reach outliers, before dilation can spread them.

    Runs per low OBJECT because parts in one group have wildly different scales: a bolt's
    detail height says nothing about a hull's. Returns the number of clamped vertices.
    """
    import numpy as np

    indices_by_object: dict = {}
    for index, key in enumerate(key_list):
        indices_by_object.setdefault(key[0], []).append(index)

    clamped_total = 0
    for object_name, indices in indices_by_object.items():
        selection = np.asarray(indices, dtype=np.int64)
        values = offsets_array[selection]
        # Zeros mean "no high detail bound here", not "detail of height zero", and letting
        # them into the quantile would drag the limit toward nothing on any low mesh whose
        # high only covers part of it.
        positive = values[values > 0.0]
        if positive.size < _AUTO_CAGE_OUTLIER_MIN_SAMPLES:
            continue
        limit = float(np.quantile(positive, _AUTO_CAGE_OUTLIER_QUANTILE)) * _AUTO_CAGE_OUTLIER_MULTIPLE
        if not (limit > 0.0):
            continue
        over = values > limit
        count = int(np.count_nonzero(over))
        if count <= 0:
            continue
        peak = float(values[over].max())
        values[over] = limit
        offsets_array[selection] = values
        clamped_total += count
        if diagnostics is not None:
            diagnostics.setdefault("clamped_objects", {})[str(object_name)] = {
                "vertices": count,
                "fitted_vertices": int(selection.size),
                "limit": limit,
                "peak": peak,
            }
    if diagnostics is not None and clamped_total:
        diagnostics["clamped_vertices"] = int(diagnostics.get("clamped_vertices", 0)) + clamped_total
    return clamped_total


def _high_world_vertices_from_source_data(high_mesh_source_data, max_samples: int):
    import numpy as np

    chunks = []
    for source_data in high_mesh_source_data:
        if source_data is None or len(source_data) != 3:
            continue
        vertex_positions, _triangle_vertex_indices, matrix_world = source_data
        if vertex_positions is None:
            continue
        positions = np.asarray(vertex_positions, dtype=np.float32).reshape(-1, 3)
        if positions.shape[0] == 0:
            continue
        transform = np.asarray(matrix_world, dtype=np.float32)
        chunks.append((positions @ transform[:3, :3].T) + transform[:3, 3])
    if not chunks:
        return None
    world = np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]
    if max_samples and world.shape[0] > max_samples:
        step = int(world.shape[0] // max_samples) + 1
        world = world[::step]
    return world


def build_coverage_offsets(
    source_triangles: list[TriangleData],
    high_mesh_source_data,
    *,
    digits: int = 6,
    dilation_iterations: int = 2,
    padding_fraction: float = _AUTO_CAGE_PADDING_DIAG_FRACTION,
    # The GPU nearest-face path handles tens of millions of high vertices in a
    # fraction of a second, so the fit uses (nearly) ALL of them. The old
    # 1.2M cap strided a dense high mesh (e.g. a 5M-vert skull -> every 5th
    # vertex), fitting the cage to only ~20% of the detail; measured, that left
    # the cage too tight on ~72% of its vertices, so high detail in the skipped
    # verts poked THROUGH it and the bake ray (which stops at the cage) missed
    # there — an obvious region-miss that Distance (uniform offset) never had.
    # 33M stays well under the GPU texture capacity (8192*16384 = 134M); the CPU
    # fallback re-strides to _CPU_FIT_MAX_SAMPLES for its slow BVH loop.
    max_high_samples: int = 33_000_000,
    diagnostics: dict | None = None,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Per-vertex cage offset that makes the cage envelope contain every high-poly point.

    The bake casts a ray from each low point along its (blended) normal up to the cage distance, so a
    texel is covered iff its ray reaches the high within that distance. This maps every high-poly
    vertex back to its nearest low face and records how far it lies OUTWARD of the low there; each low
    vertex's offset is the max over the high detail that projects onto it, so every high point ends up
    inside the cage envelope -> 100% ray coverage / no bake misses. Cage self-intersection is
    irrelevant to the projection (it interpolates per triangle), so no smoothing is needed.
    Unlike the nearest-surface fit it reaches the *outermost* local detail; unlike an outward ray it
    cannot spike across voids because it is driven by real high vertices, not a normal line.

    Nearest-face binding is only as good as the assumption that the nearest low IS the low a
    high vertex belongs to, which nested parts break; ``_clamp_cross_part_reach`` bounds what
    a mis-binding can do. Pass ``diagnostics`` to find out whether it had to.
    """
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    if not source_triangles:
        return {}

    # Flatten the low surface, coalescing shared vertices by quantized key so each low vertex carries
    # a single offset (the cage is low + offset * corner_normal, shared across incident faces).
    soup = source_triangles if isinstance(source_triangles, cage_soup.CageSoup) and int(digits) == 6 else None
    if soup is not None:
        # The arrays of a captured soup hold what the walk below collects, in the same order.
        (key_list, low_positions, face_corner_global, soup_corner_normals) = soup.coverage_structure()
        low_polygons = None
        face_total = len(soup)
    else:
        key_to_index: dict = {}
        key_list: list = []
        corner_normal_by_index: dict = {}
        low_positions: list[tuple[float, float, float]] = []
        low_polygons: list[tuple[int, int, int]] = []
        face_corner_global: list[tuple[int, int, int]] = []
        adjacency: dict = {}
        for triangle in source_triangles:
            base = len(low_positions)
            globals_row = []
            for corner in triangle.corners:
                position = corner.source_position
                low_positions.append((float(position.x), float(position.y), float(position.z)))
                key = _source_position_group_key(triangle.object_name, position, digits=digits)
                index = key_to_index.get(key)
                if index is None:
                    index = len(key_list)
                    key_to_index[key] = index
                    key_list.append(key)
                    corner_normal_by_index[index] = (corner.normal.x, corner.normal.y, corner.normal.z)
                globals_row.append(index)
            low_polygons.append((base, base + 1, base + 2))
            face_corner_global.append((globals_row[0], globals_row[1], globals_row[2]))
        face_total = len(low_polygons)

    vertex_count = len(key_list)
    offsets_array = np.zeros(vertex_count, dtype=np.float64)

    def _low_bvh():
        # Only the CPU fallback below needs the tree; built there, not for every fit.
        polygons = low_polygons if low_polygons is not None else [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(face_total)]
        points = low_positions if low_polygons is not None else low_positions.tolist()
        try:
            return BVHTree.FromPolygons(points, polygons, all_triangles=True)
        except Exception:
            return None

    high_world = _high_world_vertices_from_source_data(high_mesh_source_data, max_high_samples)
    gpu_done = False
    if high_world is not None and high_world.shape[0]:
        face_count = face_total
        positions_by_face = np.asarray(low_positions, dtype=np.float64).reshape(face_count, 3, 3)
        face_corner_global_np = np.asarray(face_corner_global, dtype=np.int64)
        if soup is not None:
            corner_normals_np = soup_corner_normals
        else:
            corner_normals_np = np.zeros((vertex_count, 3), dtype=np.float64)
            for index, normal in corner_normal_by_index.items():
                corner_normals_np[index] = normal

        # GPU fast path: brute-force the nearest low-cage triangle + bake-accurate reach for every
        # high vertex on the GPU (the CPU BVH.find_nearest loop below is GIL-bound and dominates the
        # automatic-cage build — seconds for a dense high mesh). The reach is computed identically to
        # the CPU block, so the fitted cage is unchanged. Falls back to the CPU path when the compute
        # shader is unavailable (headless export, older GPU/backend).
        gpu_done = False
        try:
            from . import overlay_cage_check_gpu as _cc

            corner_normals_by_face = corner_normals_np[face_corner_global_np]  # (face, 3, 3)
            gpu_result = _cc.compute_coverage_nearest_gpu(
                positions_by_face, corner_normals_by_face, high_world
            )
        except Exception:
            gpu_result = None
        if gpu_result is not None:
            gpu_required, gpu_tri_index = gpu_result
            gpu_valid = (gpu_tri_index >= 0) & (gpu_tri_index < face_count)
            gpu_gather = np.where(gpu_valid, gpu_tri_index, 0)
            gpu_corner_index = face_corner_global_np[gpu_gather]
            gpu_reach = np.where(gpu_valid, gpu_required.astype(np.float64), 0.0)
            np.maximum.at(offsets_array, gpu_corner_index.reshape(-1), np.repeat(gpu_reach, 3))
            gpu_done = True

    low_bvh = _low_bvh() if (not gpu_done and high_world is not None and high_world.shape[0]) else None
    if not gpu_done and low_bvh is not None and high_world is not None and high_world.shape[0]:
        # GPU path unavailable/failed: the Python BVH find_nearest loop below is
        # GIL-bound (~seconds for millions of verts), so re-stride here — this is
        # the only place the cap applies now (the GPU path already used every
        # vertex). Headless/older-GPU only; the dilation + margin still cover
        # most between-sample detail on the reduced set.
        if high_world.shape[0] > _CPU_FIT_MAX_SAMPLES:
            cpu_step = int(high_world.shape[0] // _CPU_FIT_MAX_SAMPLES) + 1
            high_world = high_world[::cpu_step]
        find_nearest = low_bvh.find_nearest
        sample_count = int(high_world.shape[0])
        locations = np.zeros((sample_count, 3), dtype=np.float64)
        face_indices = np.empty(sample_count, dtype=np.int64)
        for sample_index in range(sample_count):
            row = high_world[sample_index]
            location, _normal, face_index, _distance = find_nearest(
                Vector((float(row[0]), float(row[1]), float(row[2])))
            )
            if location is None or face_index is None or not (0 <= face_index < face_count):
                face_indices[sample_index] = -1
            else:
                locations[sample_index] = (location[0], location[1], location[2])
                face_indices[sample_index] = int(face_index)

        valid = face_indices >= 0
        gather = np.where(valid, face_indices, 0)
        corner_index = face_corner_global_np[gather]
        corner_a = positions_by_face[gather, 0]
        corner_b = positions_by_face[gather, 1]
        corner_c = positions_by_face[gather, 2]
        normal_a = corner_normals_np[corner_index[:, 0]]
        normal_b = corner_normals_np[corner_index[:, 1]]
        normal_c = corner_normals_np[corner_index[:, 2]]

        # Barycentric weights + projected-normal reach measured IDENTICALLY to the coverage compute
        # (_distance_check_compute_chunk), so the fitted offset and the bake/overlay reach share units
        # and every high vertex ends up covered by construction (offset >= its required reach).
        edge_0 = corner_b - corner_a
        edge_1 = corner_c - corner_a
        edge_2 = locations - corner_a
        d00 = (edge_0 * edge_0).sum(1)
        d01 = (edge_0 * edge_1).sum(1)
        d11 = (edge_1 * edge_1).sum(1)
        d20 = (edge_2 * edge_0).sum(1)
        d21 = (edge_2 * edge_1).sum(1)
        denom = d00 * d11 - d01 * d01
        denom_ok = np.abs(denom) > 1.0e-20
        safe_denom = np.where(denom_ok, denom, 1.0)
        weight_v = np.where(denom_ok, (d11 * d20 - d01 * d21) / safe_denom, 0.0)
        weight_w = np.where(denom_ok, (d00 * d21 - d01 * d20) / safe_denom, 0.0)
        weight_u = np.where(denom_ok, 1.0 - weight_v - weight_w, 1.0)

        projected = weight_u[:, None] * normal_a + weight_v[:, None] * normal_b + weight_w[:, None] * normal_c
        projected_len_sq = (projected * projected).sum(1)
        face_normal = np.cross(edge_0, edge_1)
        face_len = np.sqrt((face_normal * face_normal).sum(1))
        face_len_ok = face_len > 1.0e-6
        face_unit = np.where(
            face_len_ok[:, None],
            face_normal / np.where(face_len_ok[:, None], face_len[:, None], 1.0),
            face_normal,
        )
        # A blend shorter than half a unit normal means the corners disagree by >120
        # degrees. With Smooth Cage off a coalesced vertex keeps its first face's normal,
        # so a thin cylinder cap blends near-opposite side normals and reach =
        # distance / |blend| sent a customer's cage out ~160 units (2026-10-27). Measure
        # those along the face's own normal; every other blend is untouched.
        degenerate = projected_len_sq < _COVERAGE_MIN_BLEND_SQ
        projected = np.where(degenerate[:, None], face_unit, projected)
        scale = np.sqrt((projected * projected).sum(1))
        scale_ok = scale > 1.0e-12
        direction = np.where(scale_ok[:, None], projected / np.where(scale_ok[:, None], scale[:, None], 1.0), 0.0)

        point = high_world.astype(np.float64)
        required = np.maximum(0.0, ((point - locations) * direction).sum(1) / np.where(scale_ok, scale, 1.0))
        required = np.where(scale_ok & valid, required, 0.0)

        # Scatter the max reach onto each nearest face's three coalesced corners.
        np.maximum.at(offsets_array, corner_index.reshape(-1), np.repeat(required, 3))

    # Clamp BEFORE dilating: dilation is a plain max over the neighbourhood, so a single
    # cross-part reach that survives to this point is spread over two rings of low vertices and
    # takes a whole patch of cage with it.
    _clamp_cross_part_reach(offsets_array, key_list, diagnostics)

    # Neighbourhood dilation covers detail poking through the middle of a coarse low face between
    # its vertices (the vertex-nearest samples cannot see it directly).
    # A vertex takes the max over itself and the vertices it shares a triangle with: the
    # same values as walking an adjacency dict, as one scatter-max over the edge list.
    if int(dilation_iterations) > 0 and len(face_corner_global):
        faces = np.asarray(face_corner_global, dtype=np.int64).reshape(-1, 3)
        edge_from = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 0], faces[:, 2], faces[:, 1], faces[:, 2]])
        edge_to = np.concatenate([faces[:, 1], faces[:, 0], faces[:, 2], faces[:, 0], faces[:, 2], faces[:, 1]])
        for _iteration in range(int(dilation_iterations)):
            dilated = offsets_array.copy()
            np.maximum.at(dilated, edge_from, offsets_array[edge_to])
            offsets_array = dilated

    diagonal = _source_triangles_diagonal(source_triangles)
    margin = max(0.0005, diagonal * float(padding_fraction))
    values = (offsets_array + margin).tolist()
    return dict(zip(key_list, values))


#: Squared length below which a blended corner normal is replaced by the face normal in
#: the coverage reach (build_coverage_offsets; the GPU compute uses the same 0.25).
_COVERAGE_MIN_BLEND_SQ = 0.25


def _source_triangles_diagonal(source_triangles: list[TriangleData]) -> float:
    if isinstance(source_triangles, cage_soup.CageSoup):
        return source_triangles.diagonal()
    bounds_min = None
    bounds_max = None
    for triangle in source_triangles:
        for corner in triangle.corners:
            position = corner.source_position
            if bounds_min is None:
                bounds_min = [position.x, position.y, position.z]
                bounds_max = [position.x, position.y, position.z]
                continue
            if position.x < bounds_min[0]: bounds_min[0] = position.x
            if position.y < bounds_min[1]: bounds_min[1] = position.y
            if position.z < bounds_min[2]: bounds_min[2] = position.z
            if position.x > bounds_max[0]: bounds_max[0] = position.x
            if position.y > bounds_max[1]: bounds_max[1] = position.y
            if position.z > bounds_max[2]: bounds_max[2] = position.z
    if bounds_min is None:
        return 0.0
    return (
        (bounds_max[0] - bounds_min[0]) ** 2
        + (bounds_max[1] - bounds_min[1]) ** 2
        + (bounds_max[2] - bounds_min[2]) ** 2
    ) ** 0.5


def build_proximity_distances(
    source_triangles: list[TriangleData],
    high_bvh,
    *,
    digits: int = 6,
    padding_scale: float = 0.05,
    minimum_padding: float = 0.0005,
    dilation_iterations: int = _AUTO_CAGE_DILATION_ITERATIONS,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Per-vertex cage clearance from nearest-surface distance + neighbourhood dilation.

    For each unique low-poly vertex the clearance is the distance to the *nearest*
    high-poly surface point (``BVHTree.find_nearest``).  This is a robust, concavity-safe
    measure of how far the cage must sit off the low surface locally.

    An outward ray (the previous approach) is deliberately avoided: on concave shapes and
    multi-part groups the normal line spans internal cavities and the empty gap between
    parts, so the ray jumps to a distant surface and inflates that vertex's offset into a
    spike — while well-fitting vertices get no outward hit at all and stay un-enclosed.
    The nearest surface always refers to the locally corresponding geometry, so it never
    spikes.  A few max-dilation passes over the mesh-edge graph then lift each vertex to
    the largest clearance in its neighbourhood, so high detail that protrudes *between*
    low vertices stays enclosed by the cage.
    """
    # Unique vertices (deduped by rounded source position) and the mesh-edge adjacency
    # between them, built from the shared triangle corners.
    raw_clearance: dict[tuple[str, tuple[float, float, float]], float] = {}
    adjacency: dict[tuple[str, tuple[float, float, float]], set[tuple[str, tuple[float, float, float]]]] = {}
    for triangle in source_triangles:
        corner_keys = [
            _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            for corner in triangle.corners
        ]
        for key, corner in zip(corner_keys, triangle.corners):
            if key not in raw_clearance:
                try:
                    location, _normal, _index, distance = high_bvh.find_nearest(corner.source_position)
                except Exception:
                    location = distance = None
                raw_clearance[key] = float(distance) if (location is not None and distance is not None) else 0.0
        for first in range(3):
            for second in range(3):
                if first != second:
                    adjacency.setdefault(corner_keys[first], set()).add(corner_keys[second])

    # Max-dilate the clearance over the edge graph so protruding high detail between low
    # vertices is covered without letting any single value grow into a spike.
    for _iteration in range(max(0, int(dilation_iterations))):
        dilated = dict(raw_clearance)
        for key, neighbours in adjacency.items():
            largest = raw_clearance[key]
            for neighbour in neighbours:
                neighbour_value = raw_clearance.get(neighbour, 0.0)
                if neighbour_value > largest:
                    largest = neighbour_value
            dilated[key] = largest
        raw_clearance = dilated

    # Model-relative coverage margin: the tight nearest-distance fit leaves fine detail
    # poking through coarse faces, so floor the padding at a small fraction of the diagonal.
    diagonal = _source_triangles_diagonal(source_triangles)
    effective_minimum_padding = max(float(minimum_padding), diagonal * _AUTO_CAGE_PADDING_DIAG_FRACTION)

    distances: dict[tuple[str, tuple[float, float, float]], float] = {}
    for key, raw in raw_clearance.items():
        padding = max(effective_minimum_padding, raw * float(padding_scale))
        distances[key] = raw + padding
    return distances


def backend_build_proximity_distances(
    source_triangles: list[TriangleData],
    high_mesh_refs: list[protocol.ExportedMeshRef],
    backend_exe: str | Path,
    *,
    digits: int = 6,
    padding_scale: float = 0.05,
    minimum_padding: float = 0.0005,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Compute per-vertex cage clearances using the Embree-accelerated backend.

    Collects unique low-poly vertices, serializes them with the already-exported
    high mesh file refs, calls ``backend cage-fit``, and maps the returned
    clearances back to the same key format used by ``build_proximity_distances``.
    Raises ``RuntimeError`` if the backend call fails.
    """
    # Collect unique vertices in insertion order
    ordered_keys: list[tuple[str, tuple[float, float, float]]] = []
    seen: set[tuple[str, tuple[float, float, float]]] = set()
    for triangle in source_triangles:
        for corner in triangle.corners:
            key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            if key not in seen:
                seen.add(key)
                ordered_keys.append(key)

    if not ordered_keys:
        return {}

    # Build vertex list: [x, y, z, nx, ny, nz] using actual (unrounded) positions
    key_to_vertex: dict[tuple[str, tuple[float, float, float]], tuple[Vector, Vector]] = {}
    for triangle in source_triangles:
        for corner in triangle.corners:
            key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            if key not in key_to_vertex:
                key_to_vertex[key] = (corner.source_position, corner.normal)

    vertex_list = []
    for key in ordered_keys:
        pos, normal = key_to_vertex[key]
        vertex_list.append([float(pos.x), float(pos.y), float(pos.z),
                            float(normal.x), float(normal.y), float(normal.z)])

    # Estimate max_reach from source triangle bounding box
    max_reach = _scene_reach_from_triangles(source_triangles)

    # Build high_meshes list for JSON
    high_meshes_json = []
    for ref in high_mesh_refs:
        entry = {
            "name": ref.name,
            "object_name": ref.object_name,
            "role": ref.role,
            "path": str(ref.path),
            "cache_key": ref.cache_key or "",
            "material_name": ref.material_name or "",
            "collection_name": ref.collection_name or "",
        }
        if ref.world_to_object:
            entry["world_to_object"] = list(ref.world_to_object)
        high_meshes_json.append(entry)

    query = {
        "high_meshes": high_meshes_json,
        "vertices": vertex_list,
        "max_reach": float(max_reach),
    }

    with tempfile.TemporaryDirectory(prefix="mb_cage_fit_") as tmpdir:
        input_path = Path(tmpdir) / "cage_fit_query.json"
        output_path = Path(tmpdir) / "cage_fit_result.json"
        input_path.write_text(json.dumps(query), encoding="utf-8")

        from .runtime_bake_worker import spawn_feedback_suppression_kwargs

        result = subprocess.run(
            [str(backend_exe), "cage-fit", "--input", str(input_path), "--output", str(output_path)],
            capture_output=True,
            timeout=120,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            **spawn_feedback_suppression_kwargs(subprocess),
        )
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"cage-fit backend failed (exit {result.returncode}): {stderr}")

        data = json.loads(output_path.read_text(encoding="utf-8"))

    raw_clearances: list[float] = data["clearances"]
    if len(raw_clearances) != len(ordered_keys):
        raise RuntimeError(
            f"cage-fit backend returned {len(raw_clearances)} clearances for {len(ordered_keys)} vertices"
        )

    distances: dict[tuple[str, tuple[float, float, float]], float] = {}
    for key, raw in zip(ordered_keys, raw_clearances):
        padding = max(float(minimum_padding), raw * float(padding_scale))
        distances[key] = raw + padding
    return distances


def build_group_coverage_offsets(
    low_triangle_groups,
    high_mesh_source_data,
    *,
    dilation_iterations: int = 2,
    high_object_names=None,
    match_by_isolation: bool = False,
    diagnostics: dict | None = None,
    high_surface_index=None,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """See _build_group_coverage_offsets. With ``high_surface_index`` (a
    :func:`get_or_build_high_surface_index` result), the fit is then checked against the
    bake's own rays (:func:`raise_offsets_to_ray_reach`)."""
    offsets = _build_group_coverage_offsets(
        low_triangle_groups,
        high_mesh_source_data,
        dilation_iterations=dilation_iterations,
        high_object_names=high_object_names,
        match_by_isolation=match_by_isolation,
        diagnostics=diagnostics,
    )
    if offsets and high_surface_index and RAY_REACH_CHECK:
        triangles = cage_soup.flatten(low_triangle_groups)
        raised = raise_offsets_to_ray_reach(triangles, offsets, high_surface_index, diagnostics=diagnostics)
        if diagnostics is not None and raised:
            diagnostics["ray_raised_vertices"] = int(diagnostics.get("ray_raised_vertices", 0)) + raised
    return offsets


#: Check every automatic cage against the bake's own rays (raise_offsets_to_ray_reach).
#: Off until Glow weighs it: on a customer's 73-group gun it took the fit from ~10 s to
#: ~40 s (high BVHs 19 s, rays 11 s) and made every changed map match a tight Distance
#: reference (2026-10-27).
RAY_REACH_CHECK = True

#: Count the still-short samples over EVERY triangle (the old, exact, ~3x slower count).
#: Only tests and measurements set this; the warning count is the same to within the
#: triangles that are not close calls.
_RAY_SHORT_EXACT_CHECK = False

#: Farthest a ray-found exit may push the cage, as a fraction of the low's diagonal. A ray
#: that starts inside a thick high crosses it and exits on the far side; uncapped, that
#: pushed one part's cage out to 40% of its size. 20% already baked visibly worse AO on
#: a customer's gun (Box, Cylinder_022) than 10%.
_RAY_REACH_WINDOW_FRACTION = 0.1

#: How the ray check keeps the cage even: "median" caps raised corners at a multiple of
#: the part's median offset; "slope" lifts neighbours so the cage rises at most
#: _RAY_REACH_SLOPE per unit edge length.
_RAY_REACH_EVEN_MODE = "slope"
_RAY_REACH_SLOPE = 0.5
_RAY_REACH_SLOPE_ITERATIONS = 12

#: No raised corner ends past this many times the part's median (raised) offset.
_RAY_REACH_TYPICAL_FACTOR = 3.0

#: A ray-check raise stops at this many times the corner's mean edge length.
_RAY_REACH_LOCAL_EDGE_FACTOR = 1.0

#: How far the dense follow-up LOOKS for an exit. The cage itself never passes the
#: window above: letting short spots reach this far fixed their coverage numbers but
#: baked wrong surfaces on a customer's gun (a blue sliver on Box, orange blocks on
#: Cylinder_022), so those spots stay short and the bake warns about them instead.
_RAY_REACH_WIDE_FRACTION = 0.5

#: Barycentric samples per low triangle for the ray check: corners, edge midpoints, centre.
_RAY_REACH_SAMPLES = (
    (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
    (0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5),
    (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    (2.0 / 3.0, 1.0 / 6.0, 1.0 / 6.0), (1.0 / 6.0, 2.0 / 3.0, 1.0 / 6.0), (1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0),
)


#: Denser grid for the follow-up check: any triangle still short on it is fixed again.
_RAY_REACH_DENSE_SAMPLES = tuple(
    (a / 6.0, b / 6.0, 1.0 - a / 6.0 - b / 6.0) for a in range(7) for b in range(7 - a)
)


def get_or_build_fit_high_index(high_objects, depsgraph):
    """The high index for the Automatic fit's ray check.

    With the GPU cage fit on (``FYR_GPU_CAGE=1``, see cage_gpu) and every high's native
    ``.fymesh`` already written, a :class:`cage_gpu_fit.GpuHighIndex`: no BVH is built and the
    rays are answered by ``fyr_cage_gpu.exe``. Otherwise the BVH trees of
    :func:`get_or_build_high_surface_index` (``retain=False``)."""
    import threading

    objects = tuple(obj for obj in high_objects if obj is not None)
    if not objects:
        return None
    try:
        from . import cage_gpu_fit

        index = cage_gpu_fit.build_index(
            objects,
            fallback=lambda: get_or_build_high_surface_index(objects, depsgraph, retain=False),
            export_missing=threading.current_thread() is threading.main_thread(),
            depsgraph=depsgraph,
        )
    except Exception:
        index = None
    if index is not None:
        return index
    return get_or_build_high_surface_index(objects, depsgraph, retain=False)


def _raise_offsets_to_ray_reach_gpu(source_triangles, offsets, index, *, passes, diagnostics):
    """:func:`raise_offsets_to_ray_reach` on the GPU. A GPU failure turns the GPU path off for
    the session; on the main thread the CPU check then still runs for this fit."""
    import threading

    from . import cage_gpu_fit

    try:
        return cage_gpu_fit.raise_offsets_to_ray_reach(
            source_triangles, offsets, index, passes=passes, diagnostics=diagnostics
        )
    except Exception as error:
        cage_gpu_fit.disable(f"{type(error).__name__}: {error}")
        if index.fallback is not None and threading.current_thread() is threading.main_thread():
            cpu_index = index.fallback()
            if cpu_index:
                return raise_offsets_to_ray_reach(
                    source_triangles, offsets, cpu_index, passes=passes, diagnostics=diagnostics
                )
        raise


def raise_offsets_to_ray_reach(
    source_triangles, offsets, high_surface_index, *, passes: int = 2, diagnostics: dict | None = None
) -> int:
    """Raise fitted offsets until the bake's own rays reach the high they leave from.

    The coverage fit binds each high VERTEX to its nearest low face. Along a bake ray the
    outermost high can belong to a neighbouring face's vertices, so on a customer's gun
    0.5 to 2.7% of the cage sat inside the high (a ray then starts under the surface it
    should find), hidden until 2026-10-27 by the GPU readback bug inflating those cages at
    random. A sample's ray is the bake's: from the cage point (low + sum w*offset*normal)
    straight to the low point. It is cast outward from the low; only an EXIT hit (the
    high's surface seen from inside) counts, so a neighbouring part outside the low never
    pulls the cage out to it. A short sample scales its corners' offsets, which lengthens
    the ray without turning it. A sparse pass over every triangle is followed by a dense
    check that re-fixes only the triangles still short. Returns corner offsets raised;
    ``diagnostics["ray_short_samples"]`` / ``["ray_samples"]`` count what is still short."""
    if not source_triangles or not offsets or not high_surface_index:
        return 0
    from . import cage_gpu_fit

    if isinstance(high_surface_index, cage_gpu_fit.GpuHighIndex):
        return _raise_offsets_to_ray_reach_gpu(
            source_triangles, offsets, high_surface_index, passes=passes, diagnostics=diagnostics
        )
    diagonal = _source_triangles_diagonal(source_triangles)
    window = _RAY_REACH_WINDOW_FRACTION * diagonal
    if not (window > 0.0):
        return 0
    margin = max(0.0005, diagonal * float(_AUTO_CAGE_PADDING_DIAG_FRACTION))
    ceiling = window + margin
    trees = []
    for tree, matrix, matrix_inv in high_surface_index:
        trees.append((tree, matrix, matrix_inv, matrix_inv.to_3x3(), matrix_inv.to_3x3().transposed()))

    def outward_exit(point, direction, window):
        nearest = None
        for tree, matrix, matrix_inv, inv3, normal_matrix in trees:
            local_direction = inv3 @ direction
            local_length = local_direction.length
            if local_length <= 0.0:
                continue
            # The tree is in object space: a world distance spans local_length times as
            # many object units (a 0.01-scaled sword's rays stopped 100x short).
            hit, hit_normal, _index, _distance = tree.ray_cast(
                matrix_inv @ point, local_direction * (1.0 / local_length), window * 4.0 * local_length
            )
            if hit is None:
                continue
            along = ((matrix @ hit) - point).dot(direction)
            if along <= 0.0 or along > window:
                continue
            if nearest is None or along < nearest[0]:
                nearest = (along, (normal_matrix @ hit_normal).dot(direction) > 0.0)
        if nearest is None or not nearest[1]:
            return None
        return nearest[0]

    def shared_sample_key(corners, keys, weights):
        """Identity of a sample shared with neighbouring triangles (a corner, or an edge
        midpoint): the same ray from the same corners, so one cast per pass covers all of
        them. None for an interior sample."""
        used = [index for index, weight in enumerate(weights) if weight > 0.0]
        if len(used) == 1 or (len(used) == 2 and weights[used[0]] == weights[used[1]]):
            # Exact normals: corners sharing a vertex carry copies of the same normal.
            if len(used) == 1:
                index = used[0]
                normal = corners[index].normal
                return (keys[index], (normal.x, normal.y, normal.z))
            first, second = used
            n1, n2 = corners[first].normal, corners[second].normal
            pair = ((keys[first], (n1.x, n1.y, n1.z)), (keys[second], (n2.x, n2.y, n2.z)))
            return pair if pair[0] <= pair[1] else (pair[1], pair[0])
        return None

    def fix(
        triangle, keys, samples, *, fix_short: bool, window=window, ceiling=ceiling, seen=None
    ) -> tuple[int, int, bool]:
        """(offsets raised, samples still short, close call) for one triangle. A close call
        has the high's exit beyond 60% of the cage's reach somewhere; only those (and
        triangles touching a raised corner) need the dense re-check. ``seen`` skips shared
        samples (corners, edge midpoints) another triangle already cast this pass."""
        corners = triangle.corners
        raised = short = 0
        near = False
        for weights in samples:
            shared = shared_sample_key(corners, keys, weights) if seen is not None else None
            if shared is not None:
                if shared in seen:
                    near = near or seen[shared]
                    continue
                seen[shared] = False
            point = corners[0].source_position * weights[0] + corners[1].source_position * weights[1] + corners[2].source_position * weights[2]
            reach = (
                corners[0].normal * (offsets[keys[0]] * weights[0])
                + corners[1].normal * (offsets[keys[1]] * weights[1])
                + corners[2].normal * (offsets[keys[2]] * weights[2])
            )
            length = reach.length
            if length < 1.0e-9:
                continue
            direction = reach * (1.0 / length)
            exit_along = outward_exit(point, direction, window)
            if exit_along is None:
                continue
            if exit_along > 0.6 * length:
                near = True
                if shared is not None:
                    seen[shared] = True
            if exit_along + margin * 0.5 <= length:
                continue
            if not fix_short:
                short += 1
                continue
            # Scale the PLAIN fit's corners so this ray just reaches the exit. Scaling the
            # current offsets compounded: a corner shared by dozens of long fan triangles
            # (a customer receiver's flat front cap) was multiplied once per short sample
            # and ran from 0.02 to 0.29, 40x its typical cage (2026-10-28). From the
            # plain fit, a corner only ever rises to what one ray actually needs.
            plain_reach = (
                corners[0].normal * (original[keys[0]] * weights[0])
                + corners[1].normal * (original[keys[1]] * weights[1])
                + corners[2].normal * (original[keys[2]] * weights[2])
            ).length
            if plain_reach < 1.0e-9:
                continue
            scale = (exit_along + margin) / plain_reach
            for key, weight in zip(keys, weights):
                if weight <= 0.0:
                    continue
                target = min(original[key] * scale, min(ceiling, local_ceiling.get(key, ceiling)))
                if target > offsets[key]:
                    offsets[key] = target
                    raised += 1
        return raised, short, near

    keyed = []
    for triangle in source_triangles:
        keys = [
            _source_position_group_key(triangle.object_name, corner.source_position, digits=6)
            for corner in triangle.corners
        ]
        if all(key in offsets for key in keys):
            keyed.append((triangle, keys))

    original = dict(offsets)
    # Each corner may only grow by about its own edge length: a cap scaled to the whole
    # part (10% of its diagonal) let single corners of small features -- a sight ring, a
    # trigger guard -- spike far out while their neighbours stayed put (2026-10-27).
    edge_sum: dict = {}
    edge_count: dict = {}
    for triangle, keys in keyed:
        positions = [corner.source_position for corner in triangle.corners]
        for i in range(3):
            j = (i + 1) % 3
            edge = (positions[i] - positions[j]).length
            for key in (keys[i], keys[j]):
                edge_sum[key] = edge_sum.get(key, 0.0) + edge
                edge_count[key] = edge_count.get(key, 0) + 1
    local_ceiling = {
        key: max(original[key], min(ceiling, _RAY_REACH_LOCAL_EDGE_FACTOR * edge_sum[key] / edge_count[key]))
        for key in edge_sum
    }
    # The sparse passes look over the wide window, so an exit just past the normal one
    # is seen (and capped by the same ceiling) -- and so a close call is never missed.
    wide = {"window": _RAY_REACH_WIDE_FRACTION * diagonal, "ceiling": ceiling}
    raised = 0
    close_calls: set = set()
    candidates = keyed
    for _pass in range(max(1, int(passes))):
        raised_this_pass = 0
        touched = []
        seen_this_pass: dict = {}
        for index, (t, k) in enumerate(candidates):
            raised_here, _short, near = fix(t, k, _RAY_REACH_SAMPLES, fix_short=True, seen=seen_this_pass, **wide)
            raised_this_pass += raised_here
            if near or raised_here:
                touched.append((t, k))
                close_calls.add(id(t))
        raised += raised_this_pass
        if not raised_this_pass:
            break
        # A second pass only re-reads what moved or nearly needed to.
        candidates = touched
    # Dense follow-up, only where the sparse samples saw a close call or a corner moved
    # (on the customer's gun most triangles sit far inside their cage: re-checking every
    # one of them on the fine grid was 5.6 M ray casts and most of the fit's time).
    raised_keys = {key for key in offsets if offsets[key] > original[key]}
    pending = [
        (t, k) for t, k in keyed if id(t) in close_calls or any(key in raised_keys for key in k)
    ]
    for _round in range(4):
        short_triangles = [(t, k) for t, k in pending if fix(t, k, _RAY_REACH_DENSE_SAMPLES, fix_short=False, **wide)[1]]
        if not short_triangles:
            pending = []
            break
        for t, k in short_triangles:
            raised += fix(t, k, _RAY_REACH_DENSE_SAMPLES, fix_short=True, **wide)[0]
        pending = short_triangles
    # A raised corner must not push the cage into other geometry: between the low and
    # the cage, a bake ray may leave the high but never ENTER a surface from outside
    # (a neighbouring tooth, a nearby part of the same high). Such an entry is where the
    # inward bake ray hits the wrong surface -- white specks on a skull's lower teeth
    # (2026-10-27) -- so those corners go back to the coverage fit's value.
    try:
        from mathutils.bvhtree import BVHTree

        low_positions = [corner.source_position for triangle, _keys in keyed for corner in triangle.corners]
        low_tree = BVHTree.FromPolygons(
            low_positions, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(keyed))], all_triangles=True
        )
    except Exception:
        low_tree = None

    # Connected low pieces, by shared corner keys (union-find over the keyed triangles).
    parent: dict = {}

    def root(key):
        while parent.setdefault(key, key) != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for _triangle, keys in keyed:
        first = root(keys[0])
        for key in keys[1:]:
            other = root(key)
            if other != first:
                parent[other] = first
    island = [root(keys[0]) for _triangle, keys in keyed]

    def enters_geometry(point, direction, length, own_island) -> bool:
        for tree, matrix, matrix_inv, inv3, normal_matrix in trees:
            local_direction = inv3 @ direction
            local_length = local_direction.length
            if local_length <= 0.0:
                continue
            local_direction = local_direction * (1.0 / local_length)
            origin = matrix_inv @ point
            start = length * local_length * 1.0e-3
            reach = length * local_length
            travelled = 0.0
            for _hit in range(6):
                hit, hit_normal, _index, distance = tree.ray_cast(
                    origin + local_direction * start, local_direction, reach - travelled - start
                )
                if hit is None:
                    break
                travelled += start + distance
                if (normal_matrix @ hit_normal).dot(direction) < 0.0 and low_tree is not None:
                    # An overlapping shell of this spot's own high is fine (sculpts are
                    # full of unmerged parts); a surface whose nearest low is somewhere
                    # else -- the next tooth -- is not.
                    world_hit = matrix @ hit
                    nearest = low_tree.find_nearest(world_hit)
                    # The surface belongs to whichever low piece is nearest to it: another
                    # connected piece (the next tooth) means the cage reached into it.
                    if nearest is not None and nearest[2] is not None and island[nearest[2]] != own_island:
                        return True
                origin = hit
                if travelled >= reach:
                    break
        return False

    # Keep the cage even: no raised corner past a few times the raised cage's typical
    # distance. Even capped by edge length, single patches sat 10-40x further out than the
    # rest of the cage on 13 of a customer gun's 71 parts (Glow, 2026-10-28), where the
    # plain fit had none. A part that needs a bigger cage everywhere still gets it, since
    # its whole cage (and so the median) rises.
    if _RAY_REACH_EVEN_MODE == "median":
        values = sorted(offsets.values())
        even_ceiling = _RAY_REACH_TYPICAL_FACTOR * values[len(values) // 2] if values else 0.0
        for key, value in offsets.items():
            if value > original[key] and value > even_ceiling:
                offsets[key] = max(original[key], even_ceiling)
    else:
        # Slope limit: a raised corner lifts its neighbours so the cage never climbs more
        # than _RAY_REACH_SLOPE per unit of edge length -- a smooth bump over the detail
        # that needs it instead of a spike, and no cap tied to the part's typical distance
        # (which left a big, mostly tight receiver's cage inside its high).
        edges = {}
        for triangle, keys in keyed:
            positions = [corner.source_position for corner in triangle.corners]
            for i in range(3):
                j = (i + 1) % 3
                pair = (keys[i], keys[j]) if keys[i] <= keys[j] else (keys[j], keys[i])
                if pair not in edges:
                    edges[pair] = (positions[i] - positions[j]).length
        for _iteration in range(_RAY_REACH_SLOPE_ITERATIONS):
            changed = False
            for (first, second), length in edges.items():
                limit = _RAY_REACH_SLOPE * length
                high, low = (first, second) if offsets[first] >= offsets[second] else (second, first)
                if offsets[high] <= original[high]:
                    continue  # only raised corners pull their neighbours up
                floor = min(ceiling, offsets[high] - limit)
                if offsets[low] < floor:
                    offsets[low] = floor
                    changed = True
            if not changed:
                break

    reverted = 0
    for _round in range(3):
        to_revert = set()
        for triangle_index, (triangle, keys) in enumerate(keyed):
            if all(offsets[key] <= original[key] for key in keys):
                continue
            corners = triangle.corners
            for weights in _RAY_REACH_DENSE_SAMPLES:
                point = corners[0].source_position * weights[0] + corners[1].source_position * weights[1] + corners[2].source_position * weights[2]
                reach = (
                    corners[0].normal * (offsets[keys[0]] * weights[0])
                    + corners[1].normal * (offsets[keys[1]] * weights[1])
                    + corners[2].normal * (offsets[keys[2]] * weights[2])
                )
                length = reach.length
                if length < 1.0e-9:
                    continue
                if enters_geometry(point, reach * (1.0 / length), length, island[triangle_index]):
                    for key, weight in zip(keys, weights):
                        if weight > 0.0 and offsets[key] > original[key]:
                            to_revert.add(key)
        if not to_revert:
            break
        for key in to_revert:
            offsets[key] = original[key]
        reverted += len(to_revert)
    if diagnostics is not None:
        diagnostics["ray_reverted_vertices"] = int(diagnostics.get("ray_reverted_vertices", 0)) + reverted
    if diagnostics is not None:
        # Count what is still short on the fine grid. Only close calls and triangles that
        # touch a corner that moved (raised, lifted by the slope limit, or reverted) can be
        # short, the same rule that picked the dense follow-up above; re-casting all 28
        # samples of every OTHER triangle was ~3.2 M of a customer gun's 4.3 M cage rays
        # and only fed this warning count. Offsets are not affected.
        moved_keys = {key for key in offsets if offsets[key] != original[key]} | raised_keys
        pending = (
            keyed
            if _RAY_SHORT_EXACT_CHECK
            else [(t, k) for t, k in keyed if id(t) in close_calls or any(key in moved_keys for key in k)]
        )
        short = sum(fix(t, k, _RAY_REACH_DENSE_SAMPLES, fix_short=False, **wide)[1] for t, k in pending)
        diagnostics["ray_short_samples"] = int(diagnostics.get("ray_short_samples", 0)) + short
        diagnostics["ray_samples"] = int(diagnostics.get("ray_samples", 0)) + len(keyed) * len(_RAY_REACH_DENSE_SAMPLES)
    return raised


def _build_group_coverage_offsets(
    low_triangle_groups,
    high_mesh_source_data,
    *,
    dilation_iterations: int = 2,
    high_object_names=None,
    match_by_isolation: bool = False,
    diagnostics: dict | None = None,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Coverage fit for a whole bake group's low meshes AT ONCE.

    Fitting each low mesh in isolation against the group's full high set lets one low mesh balloon
    outward to "reach" another mesh's high detail: e.g. every ``Teeth_Lower_low`` vertex maps to its
    nearest lower-tooth face but is driven by the ``Teeth_Upper_high`` vertices ~1/3 of the group
    diagonal away, inflating the lower cage up into the upper teeth (and vice versa). Concatenating
    the low meshes means every high vertex maps to its GLOBALLY nearest low face, so upper-high drives
    upper-low and lower-high drives lower-low and each cage stays tight. Separate objects share no
    vertices, so the neighbourhood dilation never bleeds across meshes. The returned offsets are keyed
    by ``(object_name, position)``, so callers extract each low object's cage from the shared result.

    Concatenating is the right default only while every low mesh has a high of its own. With
    Match By Isolation the backend restricts each low to the high it is named for, so the fit
    partitions to match -- see :func:`_build_isolated_coverage_offsets`.
    """
    groups = [group for group in low_triangle_groups if group]
    if not groups:
        return {}

    if match_by_isolation and high_object_names:
        return _build_isolated_coverage_offsets(
            groups,
            high_mesh_source_data,
            list(high_object_names),
            dilation_iterations=dilation_iterations,
            diagnostics=diagnostics,
        )

    if cage_soup.all_soups(groups):
        combined = cage_soup.CageSoup.concat(groups)
    else:
        combined = []
        for group in groups:
            combined.extend(group)
    return build_coverage_offsets(
        combined,
        high_mesh_source_data,
        dilation_iterations=dilation_iterations,
        diagnostics=diagnostics,
    )


def _build_isolated_coverage_offsets(
    low_triangle_groups,
    high_mesh_source_data,
    high_object_names,
    *,
    dilation_iterations: int,
    diagnostics: dict | None,
) -> dict[tuple[str, tuple[float, float, float]], float]:
    """Fit each Match By Isolation pair on its own; fit whatever is left over together.

    With isolation on the backend only traces a low mesh against the high mesh it is named for
    (``find_isolation_source_name``), so fitting against the whole group's high set is wrong in
    both directions. A neighbouring high inflates a cage whose rays can never reach it, and --
    the damaging half -- the low's OWN high detail binds to a neighbouring low face, leaving
    this cage short there so the detail pokes through and the texel misses with no cage
    distance that could have caught it.

    Partitioning also makes the fit cheaper, not dearer: sum(V_i * F_i) rather than V * F over
    the whole group.
    """
    combined_offsets: dict[tuple[str, tuple[float, float, float]], float] = {}
    unisolated: list[TriangleData] = []
    isolated_pairs: list[tuple[str, str]] = []
    # Keyed by high index, NOT one partition per low mesh: several lows can legitimately
    # pair with the same high (``Wheel_low`` and ``Wheel_lp`` both strip to ``Wheel``).
    # Fitting those separately would give back the very ballooning the group-combined fit
    # exists to prevent -- each would reach across to the far side of the shared high --
    # so lows that share a high are still fitted together.
    lows_by_high: dict[int, list[TriangleData]] = {}

    for group in low_triangle_groups:
        object_names = {triangle.object_name for triangle in group}
        low_name = next(iter(object_names)) if len(object_names) == 1 else None
        high_index = (
            isolation_high_index_for_low(low_name, high_object_names) if low_name else None
        )
        in_range = high_index is not None and 0 <= high_index < len(high_mesh_source_data)
        if not in_range or high_mesh_source_data[high_index] is None:
            unisolated.extend(group)
            continue
        isolated_pairs.append((str(low_name), str(high_object_names[high_index])))
        lows_by_high.setdefault(high_index, []).extend(group)

    for high_index, low_triangles in lows_by_high.items():
        combined_offsets.update(
            build_coverage_offsets(
                low_triangles,
                [high_mesh_source_data[high_index]],
                dilation_iterations=dilation_iterations,
                diagnostics=diagnostics,
            )
        )

    if unisolated:
        combined_offsets.update(
            build_coverage_offsets(
                unisolated,
                high_mesh_source_data,
                dilation_iterations=dilation_iterations,
                diagnostics=diagnostics,
            )
        )

    if diagnostics is not None:
        diagnostics["isolated_pairs"] = isolated_pairs
        diagnostics["unisolated_low_objects"] = sorted(
            {triangle.object_name for triangle in unisolated}
        )
    return combined_offsets


def offset_triangles_with_proximity_fit(
    triangles: list[TriangleData],
    proximity_distances: dict[tuple[str, tuple[float, float, float]], float],
    *,
    digits: int = 6,
    minimum_offset: float = 0.0,
) -> list[TriangleData]:
    """Offset each low-poly vertex along its normal by its measured surface-proximity distance.

    Unlike ``offset_triangles_with_local_inflation`` (which scales a single global offset),
    this applies per-vertex absolute distances derived from BVH nearest-point queries so the
    resulting cage tightly wraps the high-poly surface everywhere.
    """
    if isinstance(triangles, cage_soup.CageSoup) and int(digits) == 6:
        return triangles.offset(proximity_distances, minimum_offset=minimum_offset)
    min_off = float(minimum_offset)
    result: list[TriangleData] = []
    for triangle in triangles:
        new_corners = []
        for corner in triangle.corners:
            key = _source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
            dist = max(min_off, proximity_distances.get(key, min_off))
            new_corners.append(TriangleCorner(
                source_position=corner.source_position.copy(),
                position=corner.source_position + corner.normal * dist,
                uv=corner.uv,
                normal=corner.normal.copy(),
                paint_offset=corner.paint_offset,
                paint_skew=corner.paint_skew,
            ))
        result.append(TriangleData(object_name=triangle.object_name, corners=tuple(new_corners)))
    return result


def _ray_hits_triangle(origin: Vector, direction: Vector, max_distance: float, triangle: TriangleData, *, epsilon: float = 1.0e-6) -> bool:
    vertex_0 = triangle.corners[0].position
    vertex_1 = triangle.corners[1].position
    vertex_2 = triangle.corners[2].position

    edge_1 = vertex_1 - vertex_0
    edge_2 = vertex_2 - vertex_0
    cross = direction.cross(edge_2)
    determinant = edge_1.dot(cross)
    if abs(float(determinant)) <= float(epsilon):
        return False

    inverse_determinant = 1.0 / float(determinant)
    vertex_offset = origin - vertex_0
    barycentric_u = inverse_determinant * float(vertex_offset.dot(cross))
    if barycentric_u < 0.0 or barycentric_u > 1.0:
        return False

    offset_cross = vertex_offset.cross(edge_1)
    barycentric_v = inverse_determinant * float(direction.dot(offset_cross))
    if barycentric_v < 0.0 or (barycentric_u + barycentric_v) > 1.0:
        return False

    distance = inverse_determinant * float(edge_2.dot(offset_cross))
    return float(epsilon) < distance <= (float(max_distance) + float(epsilon))


def _ray_hits_any_triangle(
    origin: Vector,
    direction: Vector,
    max_distance: float,
    high_triangles: list[TriangleData],
    *,
    high_bvh=None,
    epsilon: float = 1.0e-5,
) -> bool:
    ray_origin = origin + direction * float(epsilon)
    ray_distance = max(0.0, float(max_distance)) + float(epsilon)

    if high_bvh is not None:
        try:
            hit_location, _hit_normal, _face_index, _distance = high_bvh.ray_cast(ray_origin, direction, ray_distance)
            if hit_location is not None:
                return True
        except Exception:
            pass

    for triangle in high_triangles:
        if _ray_hits_triangle(ray_origin, direction, ray_distance, triangle, epsilon=epsilon):
            return True
    return False


def _sample_triangle_resolution(triangle_areas: list[float], max_triangle_resolution: int) -> list[int]:
    nonzero_areas = [area for area in triangle_areas if area > 1.0e-12]
    reference_area = (sum(nonzero_areas) / float(len(nonzero_areas))) if nonzero_areas else 1.0
    max_resolution = max(1, int(max_triangle_resolution))
    resolutions: list[int] = []
    for triangle_area in triangle_areas:
        area_scale = 1.0
        if triangle_area > 1.0e-12 and reference_area > 1.0e-12:
            area_scale = (triangle_area / reference_area) ** 0.5
        resolutions.append(max(1, min(max_resolution, int(round(1.5 * area_scale + 0.5)))))
    return resolutions


def ray_miss_line_positions_from_offset_triangles(
    source_triangles: list[TriangleData],
    projection_triangles: list[TriangleData],
    high_triangles: list[TriangleData],
    *,
    offset_distance: float,
    high_bvh=None,
    max_segments: int = 384,
    max_triangle_resolution: int = 4,
) -> list[tuple[float, float, float]]:
    if (
        not source_triangles
        or not projection_triangles
        or not high_triangles
        or len(source_triangles) != len(projection_triangles)
        or max_segments <= 0
        or float(offset_distance) <= 1.0e-6
    ):
        return []

    positions: list[tuple[float, float, float]] = []
    segment_count = 0
    resolutions = _sample_triangle_resolution(
        [_triangle_area(triangle) for triangle in source_triangles],
        max_triangle_resolution,
    )
    ray_distance = float(offset_distance)

    for source_triangle, projection_triangle, resolution in zip(source_triangles, projection_triangles, resolutions):
        face_normal = _triangle_face_normal(source_triangle)
        for weights in _barycentric_grid_samples(resolution):
            start = _interpolate_position(source_triangle, weights)
            correction_normal = _interpolate_normal(projection_triangle, weights)
            direction = _blend_projection_direction(face_normal, correction_normal, 1.0)
            if direction.length_squared <= 1.0e-12:
                continue
            end = start + direction * ray_distance
            if _ray_hits_any_triangle(start, direction, ray_distance, high_triangles, high_bvh=high_bvh):
                continue
            positions.append((float(start.x), float(start.y), float(start.z)))
            positions.append((float(end.x), float(end.y), float(end.z)))
            segment_count += 1
            if segment_count >= max_segments:
                return positions
    return positions


def ray_miss_line_positions_between_triangle_sets(
    source_triangles: list[TriangleData],
    target_triangles: list[TriangleData],
    high_triangles: list[TriangleData],
    *,
    high_bvh=None,
    max_segments: int = 384,
    max_triangle_resolution: int = 4,
) -> list[tuple[float, float, float]]:
    if (
        not source_triangles
        or not target_triangles
        or not high_triangles
        or len(source_triangles) != len(target_triangles)
        or max_segments <= 0
    ):
        return []

    positions: list[tuple[float, float, float]] = []
    segment_count = 0
    resolutions = _sample_triangle_resolution(
        [_triangle_area(triangle) for triangle in source_triangles],
        max_triangle_resolution,
    )

    for source_triangle, target_triangle, resolution in zip(source_triangles, target_triangles, resolutions):
        for weights in _barycentric_grid_samples(resolution):
            start = _interpolate_position(source_triangle, weights)
            target = _interpolate_position(target_triangle, weights)
            raw_direction = target - start
            ray_distance = float(raw_direction.length)
            if ray_distance <= 1.0e-6:
                continue
            direction = _normalized(raw_direction)
            if _ray_hits_any_triangle(start, direction, ray_distance, high_triangles, high_bvh=high_bvh):
                continue
            positions.append((float(start.x), float(start.y), float(start.z)))
            positions.append((float(target.x), float(target.y), float(target.z)))
            segment_count += 1
            if segment_count >= max_segments:
                return positions
    return positions


def triangle_projection_risk(source_triangle: TriangleData, correction_triangle: TriangleData | None = None) -> float:
    face_normal = _triangle_face_normal(source_triangle)
    if face_normal.length_squared == 0.0:
        return 0.0

    if correction_triangle is None:
        correction_corners = source_triangle.corners
    else:
        correction_corners = correction_triangle.corners

    risk_total = 0.0
    for correction_corner in correction_corners:
        correction_normal = _normalized(correction_corner.normal)
        alignment = max(-1.0, min(1.0, float(face_normal.dot(correction_normal))))
        risk_total += 1.0 - max(0.0, alignment)
    return risk_total / 3.0


def bucket_projection_heatmap_triangles(
    source_triangles: list[TriangleData],
    correction_triangles: list[TriangleData] | None = None,
    *,
    low_threshold: float = 0.10,
    high_threshold: float = 0.33,
) -> tuple[list[TriangleData], list[TriangleData], list[TriangleData]]:
    low_risk: list[TriangleData] = []
    medium_risk: list[TriangleData] = []
    high_risk: list[TriangleData] = []

    use_correction_set = correction_triangles is not None and len(source_triangles) == len(correction_triangles)
    correction_iterable = correction_triangles if use_correction_set else [None] * len(source_triangles)

    for source_triangle, correction_triangle in zip(source_triangles, correction_iterable):
        risk = triangle_projection_risk(source_triangle, correction_triangle)
        if risk >= float(high_threshold):
            high_risk.append(source_triangle)
        elif risk >= float(low_threshold):
            medium_risk.append(source_triangle)
        else:
            low_risk.append(source_triangle)
    return low_risk, medium_risk, high_risk


def bucket_projection_heatmap_triangle_pairs(
    source_triangles: list[TriangleData],
    target_triangles: list[TriangleData],
    *,
    low_threshold: float = 0.10,
    high_threshold: float = 0.33,
) -> tuple[list[TriangleData], list[TriangleData], list[TriangleData]]:
    if len(source_triangles) != len(target_triangles):
        return [], [], []

    low_risk: list[TriangleData] = []
    medium_risk: list[TriangleData] = []
    high_risk: list[TriangleData] = []
    for source_triangle, target_triangle in zip(source_triangles, target_triangles):
        risk = triangle_projection_risk(source_triangle, target_triangle)
        if risk >= float(high_threshold):
            high_risk.append(target_triangle)
        elif risk >= float(low_threshold):
            medium_risk.append(target_triangle)
        else:
            low_risk.append(target_triangle)
    return low_risk, medium_risk, high_risk


def _nearest_cage_sample(point: Vector, cage_triangles: list[TriangleData], cage_bvh=None) -> tuple[Vector, Vector] | None:
    if cage_bvh is not None:
        try:
            location, normal, face_index, _distance = cage_bvh.find_nearest(point)
        except Exception:
            location = normal = face_index = None
        if location is not None:
            if face_index is not None and 0 <= int(face_index) < len(cage_triangles):
                face_normal = _triangle_face_normal_at_positions(cage_triangles[int(face_index)])
            else:
                face_normal = _normalized(normal) if normal is not None else None
            if face_normal is not None and face_normal.length_squared > 1.0e-12:
                return location, face_normal

    nearest_point = None
    nearest_normal = None
    nearest_distance_squared = None
    for cage_triangle in cage_triangles:
        candidate_point = _closest_point_on_triangle(point, cage_triangle)
        delta = point - candidate_point
        distance_squared = float(delta.length_squared)
        if nearest_distance_squared is None or distance_squared < nearest_distance_squared:
            nearest_distance_squared = distance_squared
            nearest_point = candidate_point
            nearest_normal = _triangle_face_normal_at_positions(cage_triangle)
    if nearest_point is None or nearest_normal is None:
        return None
    return nearest_point, nearest_normal


def bucket_high_triangles_outside_cage(
    high_triangles: list[TriangleData],
    cage_triangles: list[TriangleData],
    *,
    low_threshold: float = 0.02,
    high_threshold: float = 0.08,
    max_triangle_resolution: int = 2,
) -> tuple[list[TriangleData], list[TriangleData], list[TriangleData]]:
    if not high_triangles or not cage_triangles:
        return [], [], []

    cage_bvh = build_triangle_bvh(cage_triangles)
    triangle_areas = [_triangle_area(triangle) for triangle in high_triangles]
    resolutions = _sample_triangle_resolution(triangle_areas, max_triangle_resolution)

    low_risk: list[TriangleData] = []
    medium_risk: list[TriangleData] = []
    high_risk: list[TriangleData] = []
    for high_triangle, resolution in zip(high_triangles, resolutions):
        local_scale = max(_triangle_average_edge_length(high_triangle), 1.0e-6)
        worst_severity = 0.0
        for weights in _barycentric_grid_samples(resolution):
            point = _interpolate_position(high_triangle, weights)
            nearest_sample = _nearest_cage_sample(point, cage_triangles, cage_bvh=cage_bvh)
            if nearest_sample is None:
                continue
            nearest_point, nearest_normal = nearest_sample
            signed_distance = float((point - nearest_point).dot(nearest_normal))
            if signed_distance <= 0.0:
                continue
            worst_severity = max(worst_severity, signed_distance / local_scale)

        if worst_severity >= float(high_threshold):
            high_risk.append(high_triangle)
        elif worst_severity >= float(low_threshold):
            medium_risk.append(high_triangle)
        else:
            low_risk.append(high_triangle)

    return low_risk, medium_risk, high_risk

