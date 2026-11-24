"""Cycles-exact ``Pointiness`` and ``Random Per Island`` for a Blender mesh.

Both values are returned indexed by LOOP TRIANGLE, not by vertex or by loop, so
they survive an export that splits vertices: a corner-indexed array can always be
re-emitted per split vertex, while a vertex-indexed array cannot be recovered once
the exporter has duplicated a vertex for a UV/normal seam.

Source
------
Ported from Blender's own renderer -- ``intern/cycles`` is Apache-2.0, so this is
a licensed port, not a reimplementation.  Fetched 2026-08-11 from the ``main``
branch at ``https://projects.blender.org/blender/blender``:

* ``intern/cycles/blender/mesh.cpp``
  - ``attr_create_pointiness()``        -> :func:`pointiness_per_vertex`
  - ``VertexAverageComparator``         -> :func:`_welded_vertex_index`
  - ``attr_create_random_per_island()`` -> :func:`island_random_per_triangle`
* ``intern/cycles/util/disjoint_set.h`` -- ``DisjointSet::find`` / ``::join``
* ``intern/cycles/util/hash.h``         -- ``hash_uint``, ``uint_to_float_incl``
* ``intern/cycles/blender/util.h``      -- ``EdgeMap`` (undirected edge dedup)
* ``intern/cycles/util/math_float3.h``  -- ``normalize``, ``safe_normalize``, ``len``
* ``intern/cycles/util/math_base.h``    -- ``safe_acosf``, ``M_1_PI_F``

SPDX-FileCopyrightText: 2011-2022 Blender Foundation
SPDX-License-Identifier: Apache-2.0

What Cycles actually does (and why this file is longer than the formula)
-----------------------------------------------------------------------
Pointiness is not "angle between the normal and the average edge direction" and
nothing else.  Cycles first WELDS coincident vertices (a positional dedup, so a
seam-split vertex does not read as a spike), accumulates normals across the weld,
dedups edges as an UNDIRECTED set, computes the raw one-ring value, then runs
exactly ONE blur pass that approximates a two-ring neighbourhood, and finally
copies the result back out to the welded duplicates.  Skipping any of those steps
gives a plausible-looking but wrong image, so all of them are ported literally,
including the order in which floats are accumulated (see the ``np.add.at`` notes).

Random-per-island is a union-find over mesh EDGES only (faces are irrelevant --
two faces sharing only a vertex are two islands), and the per-triangle value is
``hash_uint_to_float(find(first corner's vertex))``.  The *numeric root index* is
what gets hashed, so the union-by-rank tie-breaking in Cycles' ``DisjointSet`` is
load-bearing: a different but equally-valid union-find implementation yields a
different root and therefore a completely different random value.  That is why
:func:`_island_roots` is a literal transcription rather than a call out to a
generic connected-components routine.

Input mesh
----------
Every public function accepts a ``bpy.types.Object`` or a ``bpy.types.Mesh``.
The mesh used is the object's AUTHORED ``obj.data`` -- Cycles bakes the
DEPSGRAPH-EVALUATED mesh, so for an object carrying modifiers the caller must
pass the evaluated mesh (``obj.evaluated_get(depsgraph).data``) or the vertex
count and triangle order will not line up with a Cycles bake.

Verification plan (engine-vs-engine, to be run in Blender by the lead agent)
----------------------------------------------------------------------------
These numbers are only worth anything if they match Cycles, so verify against
Cycles itself -- never against a transcribed formula:

1. Test object: one mesh with at least two DISCONNECTED shells (join a Suzanne,
   a cube and a UV sphere), UV-unwrapped, no modifiers, no shape keys.
2. Material: Emission, Color driven by the Geometry node's ``Pointiness`` output
   for bake #1 and its ``Random Per Island`` output for bake #2.  Bake type EMIT,
   1 sample, denoise OFF, 32-bit float EXR, Non-Color -- a view transform on a
   [0,1] data value invalidates the comparison.
3. Rasterize this module's output into the same UV layout:
   * pointiness: barycentric-interpolate :func:`pointiness_per_corner` across
     each loop triangle's UVs.  Cycles stores POINTINESS per VERTEX and lets the
     triangle interpolate it, so corner values + barycentric lerp is the same
     function of the surface point.
   * island random: flat-fill each loop triangle's UV triangle with
     :func:`island_random_per_triangle`\\ ``[i]``.  Cycles stores this per
     corner-triangle -- it is constant across the triangle, with a hard
     discontinuity at an island boundary.
4. Diff.  Expected max |delta| is the bake's own quantization floor (~1e-6).
   Failure signatures worth knowing: a smooth global offset on pointiness means a
   different vertex-normal source (custom split normals were used instead of
   ``mesh.vertex_normals``); a blurrier/sharper image means the blur pass count is
   wrong; an island mismatch is never small -- a wrong union-find root produces an
   unrelated hash, so it shows up as a completely different flat value.
5. Cheap sanity checks that need no bake: a default cube has all 8 vertices
   identical, a UV sphere sits near 0.5 everywhere, and a mesh of N separate
   shells produces exactly N distinct values in the island array
   (:func:`describe` reports that count).

Known deviations from the C++ (all sub-ULP or explicitly unspecified upstream)
------------------------------------------------------------------------------
* ``np.arccos`` on float32 may differ from libm ``acosf`` by well under 1 ULP.
* ``dot``/``len`` are ported as the scalar ``x*x + y*y + z*z`` form; a Cycles
  build with ``__KERNEL_SSE42__`` uses ``_mm_dp_ps``, whose internal rounding can
  differ in the last bit.
* ``std::sort`` with ``VertexAverageComparator`` leaves the relative order of two
  DIFFERENT positions that share a coordinate sum unspecified.  This port uses
  (sum ascending, vertex index descending), which is a legal output of that
  comparator and reproduces its explicit equal-position tie-break exactly.
* Adaptive-subdivision meshes take Cycles' ``subdivision`` branch (attributes on
  faces, not corner-triangles).  Not emulated -- this module is the non-subdivided
  path only.

Cost
----
The accumulation passes use ``np.add.at`` rather than ``np.bincount`` because
``add.at`` applies its index array IN ORDER, which is what reproduces Cycles'
float summation order.  Do not "optimize" that to a buffered add without
re-verifying.  Measured (this machine, off-Blender harness): 160k verts / 319k
edges / 160k triangles costs 0.12 s for pointiness and 0.08 s for islands, so a
million-edge mesh lands well under a second.  The island pass is a Python loop by
necessity (see :func:`_island_roots`) and is the part that scales worst.

Verified before hand-off (no Blender required, ``numpy`` only): the vectorized
implementation was diffed against a line-by-line scalar transcription of the C++
on an irregular mesh (mixed valences, shuffled edge order, exact-duplicate
vertices) -- max |delta| 8e-8, i.e. the float32 rounding floor.  A cube's
pointiness matches the analytic ``acos(-1/sqrt(3)) / pi`` = 0.69591328 to 3e-8,
and ``_hash_uint`` matches an independent scalar lookup3 reference bit-for-bit.
What that does NOT cover is agreement with Cycles itself; that is what the
verification plan above is for.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from . import rna_buffers

# ---------------------------------------------------------------------------
# Constants lifted from the C++ side
# ---------------------------------------------------------------------------

#: ``FLT_EPSILON`` -- 2**-23, the float32 machine epsilon the C++ compares against.
_FLT_EPSILON = np.float32(1.1920928955078125e-07)

#: ``3 * FLT_EPSILON`` -- the coordinate-sum window that ends the duplicate scan.
#: Exactly representable (3 * 2**-23), so there is no ambiguity about how the C++
#: compiler folded the constant.
_SUM_EPSILON = np.float32(3.0) * _FLT_EPSILON

#: ``M_1_PI_F`` from ``util/math_base.h``.
_M_1_PI_F = np.float32(0.3183098861837067)

#: ``1.0f / (float)0xFFFFFFFFu`` from ``uint_to_float_incl``.  Note that
#: ``(float)0xFFFFFFFFu`` rounds UP to 4294967296.0f, so the reciprocal is exactly
#: 2**-32 -- using 1/4294967295.0 here would be a (tiny) mismatch with Cycles.
_UINT_TO_FLOAT_INCL = np.float32(1.0 / 4294967296.0)

#: Pointer-doubling safety cap.  Both the weld chain and the union-find forest are
#: acyclic with depth << 2**64; the cap only stops a corrupt mesh from hanging
#: Blender the way the upstream ``while`` loops would.
_MAX_POINTER_DOUBLING_STEPS = 64


class _MeshArrays(NamedTuple):
    """Everything the two algorithms read, pulled out of RNA exactly once."""

    vertex_count: int
    positions: np.ndarray  # (V, 3) float32 -- ``b_mesh.vert_positions()``
    vertex_normals: np.ndarray  # (V, 3) float32 -- ``b_mesh.vert_normals()``
    edges: np.ndarray  # (E, 2) int32 -- ``b_mesh.edges()``
    triangle_vertices: np.ndarray  # (T, 3) int32 -- corner_verts[corner_tris]


# ---------------------------------------------------------------------------
# Mesh access
# ---------------------------------------------------------------------------


def _resolve_mesh(obj):
    """Return the ``Mesh`` datablock for *obj*, which may already be one."""
    mesh = getattr(obj, "data", None)
    if mesh is not None and hasattr(mesh, "vertices"):
        return mesh
    if hasattr(obj, "vertices") and hasattr(obj, "edges"):
        return obj
    return None


def _as_arrays(obj) -> _MeshArrays | None:
    """Accept an Object, a Mesh, or an already-extracted :class:`_MeshArrays`.

    The pass-through case lets a caller (or :func:`describe`) read RNA once and
    then compute both attributes without paying for a second ``foreach_get``.
    """
    if isinstance(obj, _MeshArrays):
        return obj
    return _read_mesh_arrays(obj)


def _read_mesh_arrays(obj) -> _MeshArrays | None:
    """Copy positions / normals / edges / loop triangles into numpy.

    ``foreach_get`` is the only fast path out of RNA; a Python-level iteration over
    ``mesh.vertices`` costs roughly two orders of magnitude more on a dense mesh.
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return None

    vertices = getattr(mesh, "vertices", None)
    edges = getattr(mesh, "edges", None)
    if vertices is None or edges is None:
        return None

    vertex_count = len(vertices)
    if vertex_count <= 0:
        return _MeshArrays(
            vertex_count=0,
            positions=np.empty((0, 3), dtype=np.float32),
            vertex_normals=np.empty((0, 3), dtype=np.float32),
            edges=np.empty((0, 2), dtype=np.int32),
            triangle_vertices=np.empty((0, 3), dtype=np.int32),
        )

    positions_flat = np.empty(vertex_count * 3, dtype=np.float32)
    vertices.foreach_get("co", positions_flat)
    positions = positions_flat.reshape(vertex_count, 3)

    # ``mesh.vertex_normals`` is the RNA name for the C++ ``vert_normals()`` span
    # that Cycles passes to attr_create_pointiness.  Custom split (corner) normals
    # are deliberately NOT used -- Cycles does not use them here either.
    normals_flat = np.empty(vertex_count * 3, dtype=np.float32)
    vertex_normals_source = getattr(mesh, "vertex_normals", None)
    if vertex_normals_source is not None and hasattr(vertex_normals_source, "foreach_get"):
        vertex_normals_source.foreach_get("vector", normals_flat)
    else:
        vertices.foreach_get("normal", normals_flat)
    vertex_normals = normals_flat.reshape(vertex_count, 3)

    edge_count = len(edges)
    if edge_count > 0:
        edges_flat = rna_buffers.empty_u32_for_rna(edge_count * 2)
        edges.foreach_get("vertices", edges_flat)
        edges_flat = rna_buffers.as_i32(edges_flat)
        edge_pairs = edges_flat.reshape(edge_count, 2)
    else:
        edge_pairs = np.empty((0, 2), dtype=np.int32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count > 0:
        triangle_flat = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        loop_triangles.foreach_get("vertices", triangle_flat)
        triangle_flat = rna_buffers.as_i32(triangle_flat)
        triangle_vertices = triangle_flat.reshape(triangle_count, 3)
    else:
        triangle_vertices = np.empty((0, 3), dtype=np.int32)

    return _MeshArrays(
        vertex_count=vertex_count,
        positions=positions,
        vertex_normals=vertex_normals,
        edges=edge_pairs,
        triangle_vertices=triangle_vertices,
    )


# ---------------------------------------------------------------------------
# Cycles float3 primitives, row-wise
# ---------------------------------------------------------------------------


def _dot_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``dot(float3, float3)`` -- written out so the summation order is fixed."""
    return a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1] + a[:, 2] * b[:, 2]


def _length_rows(vectors: np.ndarray) -> np.ndarray:
    """``len(float3)`` == ``sqrtf(dot(a, a))``."""
    return np.sqrt(_dot_rows(vectors, vectors))


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """``normalize(float3)`` == ``a / len(a)``.

    Unguarded division, exactly like the C++: a zero-length input yields inf/nan
    there too.  Blender only hands out a zero vertex normal for genuinely
    degenerate geometry, and silently substituting a fake normal would hide that.
    """
    lengths = _length_rows(vectors)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (vectors / lengths[:, None]).astype(np.float32, copy=False)


def _safe_normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """``safe_normalize(float3)`` == ``(t != 0) ? a * (1/t) : a``.

    Note the RECIPROCAL MULTIPLY -- ``normalize`` divides, ``safe_normalize``
    multiplies by the reciprocal, and the two round differently in the last bit.
    """
    lengths = _length_rows(vectors)
    scale = np.divide(
        np.float32(1.0),
        lengths,
        out=np.ones_like(lengths),
        where=lengths != np.float32(0.0),
    )
    return (vectors * scale[:, None]).astype(np.float32, copy=False)


def _safe_acos(values: np.ndarray) -> np.ndarray:
    """``safe_acosf`` == ``acosf(clamp(a, -1.0f, 1.0f))``."""
    clamped = np.clip(values, np.float32(-1.0), np.float32(1.0))
    return np.arccos(clamped).astype(np.float32, copy=False)


def _resolve_to_roots(parents: np.ndarray) -> np.ndarray:
    """Follow a parent array to its fixed point (pointer doubling).

    The C++ walks each chain one link at a time while mutating the array in place;
    the fixed point is identical either way, and doubling gets there in O(log n)
    vectorized steps instead of a Python loop.
    """
    current = parents
    for _ in range(_MAX_POINTER_DOUBLING_STEPS):
        following = current[current]
        if np.array_equal(following, current):
            return current
        current = following
    return current


# ---------------------------------------------------------------------------
# Pointiness -- attr_create_pointiness()
# ---------------------------------------------------------------------------


def _welded_vertex_index(positions: np.ndarray) -> np.ndarray:
    """STEP 1: map every vertex to the single original vertex it duplicates.

    Port of the ``VertexAverageComparator`` sort plus the forward scan.  Cycles
    sorts vertices by ``x + y + z``, then for each vertex scans FORWARD only while
    the sum difference stays within ``3 * FLT_EPSILON``, taking the first vertex
    within ``FLT_EPSILON`` squared distance as its "original".  The scan direction
    is why the representative of a duplicate group is the group's LAST member in
    sorted order (i.e. its lowest vertex index, given the comparator's
    equal-position tie-break of descending index).
    """
    vertex_count = positions.shape[0]
    vert_orig_index = np.arange(vertex_count, dtype=np.int64)
    if vertex_count <= 1:
        return vert_orig_index

    # Sum in float32, left to right, matching ``vert_a.x + vert_a.y + vert_a.z``.
    sums = (positions[:, 0] + positions[:, 1]) + positions[:, 2]

    # Primary key: the coordinate sum.  Secondary key: descending vertex index,
    # which is the comparator's explicit "special case for doubles, so we ensure
    # ordering" branch.  lexsort takes the primary key last.
    index = np.arange(vertex_count, dtype=np.int64)
    order = np.lexsort((-index, sums))

    sorted_sums = sums[order]
    sorted_positions = positions[order]

    # Candidate window per sorted vertex.  The real break test is the float32
    # subtraction below; this searchsorted only has to produce a SUPERSET, so the
    # bound is padded by a relative ULP to absorb the difference between
    # "fl(s_j - s_i) > T" and "s_j > s_i + T".
    sorted_sums_wide = sorted_sums.astype(np.float64)
    window_end = np.searchsorted(
        sorted_sums_wide,
        sorted_sums_wide + float(_SUM_EPSILON) * 1.000001,
        side="right",
    )

    sorted_index_range = np.arange(vertex_count, dtype=np.int64)
    candidates = np.flatnonzero(window_end > sorted_index_range + 1)
    if candidates.size == 0:
        # No two vertices are even close in coordinate sum -- no duplicates exist.
        return vert_orig_index

    for sorted_index in candidates.tolist():
        start = sorted_index + 1
        stop = int(window_end[sorted_index])
        # Exact C++ break condition, in float32: stop at the first vertex whose
        # sum is more than 3*FLT_EPSILON away.  fl(a - c) is monotonic in a, so
        # the surviving entries are a prefix and a count is enough.
        deltas = sorted_sums[start:stop] - sorted_sums[sorted_index]
        span = int(np.count_nonzero(deltas <= _SUM_EPSILON))
        if span <= 0:
            continue
        offsets = sorted_positions[start : start + span] - sorted_positions[sorted_index]
        distances_squared = (
            offsets[:, 0] * offsets[:, 0]
            + offsets[:, 1] * offsets[:, 1]
            + offsets[:, 2] * offsets[:, 2]
        )
        hits = np.flatnonzero(distances_squared < _FLT_EPSILON)
        if hits.size == 0:
            continue
        # First hit wins, exactly like the C++ ``break``.
        vert_orig_index[order[sorted_index]] = order[start + int(hits[0])]

    # "Make sure we always points to the very first orig vertex."  The mapping only
    # ever points forward in sorted order, so the chain is acyclic and terminates.
    return _resolve_to_roots(vert_orig_index)


def _welded_vertex_normals(vertex_normals: np.ndarray, vert_orig_index: np.ndarray) -> np.ndarray:
    """STEP 2: accumulate normals onto the weld representative, then normalize.

    The C++ loop writes into ``vert_normal`` while still reading from it, so a
    duplicate whose representative has a LOWER index reads an already-normalized
    vector and normalizes it a second time.  ``normalize(normalize(v))`` is not
    bit-identical to ``normalize(v)``, so that double pass is reproduced here
    rather than quietly collapsed.
    """
    vertex_count = vertex_normals.shape[0]
    accumulated = np.zeros((vertex_count, 3), dtype=np.float32)
    # ``add.at`` applies indices in order, matching the C++ accumulation order.
    np.add.at(accumulated, vert_orig_index, vertex_normals)

    normalized = _normalize_rows(accumulated)
    result = normalized[vert_orig_index]

    index = np.arange(vertex_count, dtype=np.int64)
    already_written = np.flatnonzero(vert_orig_index < index)
    if already_written.size:
        result[already_written] = _normalize_rows(result[already_written])
    return result


def _unique_edge_endpoints(
    edges: np.ndarray,
    vert_orig_index: np.ndarray,
    vertex_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Port of Cycles' ``EdgeMap`` dedup over weld-remapped edges.

    ``EdgeMap`` keys on the SORTED vertex pair (undirected), but passes its
    arguments by value -- so the accumulation below still uses the edge's original
    endpoint order.  First occurrence wins, and first-occurrence order is preserved
    so the later ``np.add.at`` passes accumulate in the C++'s edge order.
    """
    if edges.shape[0] == 0:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty

    first = vert_orig_index[edges[:, 0].astype(np.int64)]
    second = vert_orig_index[edges[:, 1].astype(np.int64)]

    low = np.minimum(first, second)
    high = np.maximum(first, second)
    keys = low * np.int64(max(vertex_count, 1)) + high
    _, first_occurrence = np.unique(keys, return_index=True)
    keep = np.sort(first_occurrence)
    return first[keep], second[keep]


def pointiness_per_vertex(obj) -> np.ndarray:
    """Cycles' ``ATTR_STD_POINTINESS``, one float32 per mesh vertex.

    This is the attribute exactly as Cycles stores it; the renderer then linearly
    interpolates it across each triangle.  Returns an empty array for a mesh with
    no vertices (Cycles adds no attribute at all in that case).
    """
    arrays = _as_arrays(obj)
    if arrays is None:
        return np.empty(0, dtype=np.float32)
    return _pointiness_per_vertex_arrays(arrays)


def _pointiness_per_vertex_arrays(arrays: _MeshArrays) -> np.ndarray:
    vertex_count = arrays.vertex_count
    if vertex_count <= 0:
        return np.empty(0, dtype=np.float32)

    positions = arrays.positions
    vert_orig_index = _welded_vertex_index(positions)
    vertex_normals = _welded_vertex_normals(arrays.vertex_normals, vert_orig_index)

    first, second = _unique_edge_endpoints(arrays.edges, vert_orig_index, vertex_count)

    # STEP 3: one-ring edge accumulation.
    edge_accumulator = np.zeros((vertex_count, 3), dtype=np.float32)
    counter = np.zeros(vertex_count, dtype=np.int64)
    targets = np.empty(0, dtype=np.int64)
    if first.size:
        edge_directions = _safe_normalize_rows(positions[second] - positions[first])
        # Interleave (v0, v1) per edge so ``add.at`` reproduces the C++'s
        # "edge_accum[v0] += edge; edge_accum[v1] += -edge;" ordering exactly.
        targets = np.empty(first.size * 2, dtype=np.int64)
        targets[0::2] = first
        targets[1::2] = second
        contributions = np.empty((first.size * 2, 3), dtype=np.float32)
        contributions[0::2] = edge_directions
        contributions[1::2] = -edge_directions
        np.add.at(edge_accumulator, targets, contributions)
        # A weld-degenerate edge (both endpoints collapsed onto one vertex) still
        # bumps the counter twice in the C++; bincount over the same interleaved
        # index array preserves that.
        counter = np.bincount(targets, minlength=vertex_count).astype(np.int64)

    raw_data = np.zeros(vertex_count, dtype=np.float32)
    index = np.arange(vertex_count, dtype=np.int64)
    # Duplicates are skipped here and overwritten in STEP 4 instead.
    representatives = (vert_orig_index == index) & (counter > 0)
    if np.any(representatives):
        mean_edge = (
            edge_accumulator[representatives]
            / counter[representatives].astype(np.float32)[:, None]
        )
        cosine = _dot_rows(vertex_normals[representatives], mean_edge)
        raw_data[representatives] = (_safe_acos(cosine) * _M_1_PI_F).astype(
            np.float32, copy=False
        )

    # STEP 3b: a SINGLE blur pass -- "Blur vertices to approximate 2 ring
    # neighborhood".  One pass, not two; the neighbour values read are the
    # pre-blur raw values, and the divisor is the ring count plus self.
    data = raw_data.copy()
    if first.size:
        blur_contributions = np.empty(first.size * 2, dtype=np.float32)
        blur_contributions[0::2] = raw_data[second]
        blur_contributions[1::2] = raw_data[first]
        np.add.at(data, targets, blur_contributions)
    data /= (counter + 1).astype(np.float32)

    # STEP 4: copy the representative's value out to its welded duplicates.
    return data[vert_orig_index].astype(np.float32, copy=False)


def pointiness_per_corner(obj) -> np.ndarray:
    """Cycles' pointiness at every loop-triangle corner.

    Returns ``(num_loop_triangles, 3)`` float32, column *j* holding the value at
    ``loop_triangle.vertices[j]``.  Cycles stores pointiness per vertex and
    interpolates it barycentrically, so these three corner values plus a
    barycentric lerp reproduce the shaded value anywhere inside the triangle.

    Returns an empty ``(0, 3)`` array for a mesh with no polygons.
    """
    arrays = _as_arrays(obj)
    if arrays is None or arrays.triangle_vertices.shape[0] == 0:
        return np.empty((0, 3), dtype=np.float32)

    per_vertex = _pointiness_per_vertex_arrays(arrays)
    if per_vertex.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    return per_vertex[arrays.triangle_vertices.astype(np.int64)]


# ---------------------------------------------------------------------------
# Random per island -- attr_create_random_per_island()
# ---------------------------------------------------------------------------


def _hash_uint(values: np.ndarray) -> np.ndarray:
    """Cycles' ``hash_uint`` (``util/hash.h``), the lookup3 ``final()`` mix.

    Vectorized over a uint32 array.  ``hash_uint`` -- one input word -- is what the
    island code calls; ``hash_uint2`` seeds differently and would give a different
    (wrong) value here.
    """
    keys = np.asarray(values, dtype=np.uint32)
    seed = np.uint32(0xDEADBEEF + (1 << 2) + 13)

    def rot(word: np.ndarray, bits: int) -> np.ndarray:
        shift = np.uint32(bits)
        counter_shift = np.uint32(32 - bits)
        return (word << shift) | (word >> counter_shift)

    with np.errstate(over="ignore"):
        a = np.full(keys.shape, seed, dtype=np.uint32)
        b = np.full(keys.shape, seed, dtype=np.uint32)
        c = np.full(keys.shape, seed, dtype=np.uint32)
        a = a + keys

        # final(a, b, c)
        c = c ^ b
        c = c - rot(b, 14)
        a = a ^ c
        a = a - rot(c, 11)
        b = b ^ a
        b = b - rot(a, 25)
        c = c ^ b
        c = c - rot(b, 16)
        a = a ^ c
        a = a - rot(c, 4)
        b = b ^ a
        b = b - rot(a, 14)
        c = c ^ b
        c = c - rot(b, 24)
    return c


def _hash_uint_to_float(values: np.ndarray) -> np.ndarray:
    """``hash_uint_to_float`` == ``uint_to_float_incl(hash_uint(kx))``, in [0, 1]."""
    hashed = _hash_uint(values)
    return (hashed.astype(np.float32) * _UINT_TO_FLOAT_INCL).astype(np.float32, copy=False)


#: Edges converted to Python ints per slice of the union-find walk. Bounds that list at
#: a few MB instead of the whole edge array.
_EDGE_WALK_CHUNK = 1 << 18


def _island_roots(vertex_count: int, edges: np.ndarray) -> np.ndarray:
    """Union-find over mesh EDGES, transcribed from ``util/disjoint_set.h``.

    Faces play no part: two faces that touch at a single vertex with no shared edge
    are two islands, which is exactly what artists see from the Geometry node.

    The union-by-rank tie-break and the path compression are reproduced literally
    because the hash is fed the ROOT INDEX -- swap in a different (equally correct)
    union-find and every island gets a different random value.  This is a Python
    loop for that reason; there is no vectorization of it that preserves the root
    choice.
    """
    parents = list(range(vertex_count))
    ranks = [0] * vertex_count
    if edges.shape[0] == 0 or vertex_count == 0:
        return np.arange(vertex_count, dtype=np.int64)

    # Walked in bounded slices of the int32 edge array rather than one
    # `edges.tolist()`: that list of Python ints cost ~1.2 GB at 15M edges and stayed
    # alive for the whole loop. Edges are visited in the same order, so every union and
    # every root is unchanged.
    pairs = edges.reshape(-1, 2)
    for start in range(0, pairs.shape[0], _EDGE_WALK_CHUNK):
        flat = pairs[start:start + _EDGE_WALK_CHUNK].reshape(-1).tolist()
        for x, y in zip(flat[0::2], flat[1::2]):
            # DisjointSet::find(x), with the same path compression.
            x_root = x
            while parents[x_root] != x_root:
                x_root = parents[x_root]
            node = x
            while parents[node] != x_root:
                parent = parents[node]
                parents[node] = x_root
                node = parent

            # DisjointSet::find(y)
            y_root = y
            while parents[y_root] != y_root:
                y_root = parents[y_root]
            node = y
            while parents[node] != y_root:
                parent = parents[node]
                parents[node] = y_root
                node = parent

            if x_root == y_root:
                continue
            if ranks[x_root] < ranks[y_root]:
                x_root, y_root = y_root, x_root
            parents[y_root] = x_root
            if ranks[x_root] == ranks[y_root]:
                ranks[x_root] += 1

    # A final find() for every vertex; roots are unaffected by compression.
    return _resolve_to_roots(np.asarray(parents, dtype=np.int64))


def island_random_per_triangle(obj) -> np.ndarray:
    """Cycles' ``ATTR_STD_RANDOM_PER_ISLAND``, one float32 per loop triangle.

    Cycles stores this per corner-triangle and takes the island of the triangle's
    FIRST corner (``corner_verts[corner_tris[i][0]]``), i.e. ``vertices[0]`` of the
    Blender loop triangle.  The value is constant across the triangle and across
    the island, with a hard discontinuity at an island boundary.

    Returns an empty array for a mesh with no polygons or no vertices.
    """
    arrays = _as_arrays(obj)
    if arrays is None or arrays.vertex_count == 0:
        return np.empty(0, dtype=np.float32)
    triangle_vertices = arrays.triangle_vertices
    if triangle_vertices.shape[0] == 0:
        return np.empty(0, dtype=np.float32)

    roots = _island_roots(arrays.vertex_count, arrays.edges)
    first_corner_vertex = triangle_vertices[:, 0].astype(np.int64)
    return _hash_uint_to_float(roots[first_corner_vertex])


# ---------------------------------------------------------------------------
# Self-test helpers
# ---------------------------------------------------------------------------


def _summarize(array: np.ndarray) -> dict:
    """Shape/min/max/mean plus a non-finite count, safe on empty input."""
    summary: dict = {
        "shape": tuple(int(size) for size in array.shape),
        "dtype": str(array.dtype),
        "count": int(array.size),
    }
    if array.size == 0:
        summary.update({"min": None, "max": None, "mean": None, "non_finite": 0})
        return summary
    finite = np.isfinite(array)
    summary["non_finite"] = int(array.size - int(np.count_nonzero(finite)))
    values = array[finite]
    if values.size == 0:
        summary.update({"min": None, "max": None, "mean": None})
        return summary
    summary["min"] = float(values.min())
    summary["max"] = float(values.max())
    summary["mean"] = float(values.mean())
    return summary


def describe(obj) -> dict:
    """Quick live verification snapshot for both attributes.

    Meant to be printed from Blender's console right after computing, before any
    bake comparison, to catch the obvious failures cheaply:

    * ``pointiness`` outside [0, 1] or a non-zero ``non_finite`` count means a
      degenerate vertex normal reached ``normalize`` -- inspect the mesh, do not
      clamp the output.
    * ``island_random`` should have exactly as many distinct values as the mesh has
      edge-connected shells (``distinct_island_values``); a default cube joined
      with a sphere must report 2.
    * ``triangle_count`` must match the triangle count the exporter sees, otherwise
      the arrays are indexed against a different topology (usually: modifiers, so
      an evaluated mesh should have been passed instead of ``obj.data``).
    """
    arrays = _as_arrays(obj)
    if arrays is None:
        return {"error": "not a mesh", "object": getattr(obj, "name", None)}

    triangle_count = int(arrays.triangle_vertices.shape[0])
    per_vertex = _pointiness_per_vertex_arrays(arrays)
    if triangle_count and per_vertex.size:
        per_corner = per_vertex[arrays.triangle_vertices.astype(np.int64)]
    else:
        per_corner = np.empty((0, 3), dtype=np.float32)
    islands = island_random_per_triangle(arrays)

    report: dict = {
        "object": getattr(obj, "name", None),
        "vertex_count": int(arrays.vertex_count),
        "edge_count": int(arrays.edges.shape[0]),
        "triangle_count": triangle_count,
        "pointiness_per_vertex": _summarize(per_vertex),
        "pointiness_per_corner": _summarize(per_corner),
        "island_random_per_triangle": _summarize(islands),
        "distinct_island_values": int(np.unique(islands).size) if islands.size else 0,
    }
    if arrays.vertex_count:
        # How many vertices Cycles considers positional duplicates.  A UV-seamed
        # mesh exported and re-imported often has thousands; the authored mesh in
        # Blender usually has zero, and a surprise here explains a pointiness
        # difference against a bake of a different version of the same asset.
        welded = _welded_vertex_index(arrays.positions)
        report["welded_duplicate_vertices"] = int(
            np.count_nonzero(welded != np.arange(arrays.vertex_count, dtype=np.int64))
        )
    return report


# ---------------------------------------------------------------------------
# Colour attributes -- attr_create_generic() for a colour layer
# ---------------------------------------------------------------------------


def color_attribute_per_corner(obj, name: str) -> np.ndarray:
    """A named colour attribute at every loop-triangle corner.

    Returns ``(num_loop_triangles, 3, 4)`` float32: for triangle *t*, corner *j*,
    the RGBA the shader sees at ``loop_triangle.loops[j]``. Cycles interpolates a
    colour attribute barycentrically exactly like pointiness, so these three
    corner values plus the barycentric lerp reproduce the shaded value anywhere in
    the triangle.

    Handles both domains Blender allows for a colour layer:

    * ``CORNER`` -- one value per loop, read through ``loop_triangles.loops``.
    * ``POINT`` -- one value per vertex, read through ``loop_triangles.vertices``.

    ``BYTE_COLOR`` layers store sRGB-encoded bytes and Blender's RNA hands them
    back already converted to scene-linear floats, which is the value Cycles
    shades with, so no transfer function is applied here.

    Returns an empty ``(0, 3, 4)`` array when the mesh has no triangles or carries
    no such attribute; the caller treats that as Cycles does, i.e. zero.
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return np.empty((0, 3, 4), dtype=np.float32)

    attributes = getattr(mesh, "attributes", None)
    layer = attributes.get(str(name or "")) if attributes is not None else None
    if layer is None:
        return np.empty((0, 3, 4), dtype=np.float32)
    data = getattr(layer, "data", None)
    if data is None or len(data) == 0:
        return np.empty((0, 3, 4), dtype=np.float32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count <= 0:
        return np.empty((0, 3, 4), dtype=np.float32)

    element_count = len(data)
    values = np.empty(element_count * 4, dtype=np.float32)
    try:
        data.foreach_get("color", values)
    except (TypeError, RuntimeError):
        # A non-colour attribute of the same name (float / vector). Not a colour
        # layer, so there is nothing honest to read.
        return np.empty((0, 3, 4), dtype=np.float32)
    values = values.reshape(element_count, 4)

    domain = str(getattr(layer, "domain", "") or "").strip().upper()
    index_attr = "loops" if domain == "CORNER" else "vertices"
    indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
    loop_triangles.foreach_get(index_attr, indices)
    indices = rna_buffers.as_i32(indices)
    indices = np.clip(indices.astype(np.int64), 0, element_count - 1)
    return values[indices].reshape(triangle_count, 3, 4)


#: Attribute domains a scalar sidecar can reproduce.
#:
#: POINT and CORNER are what the barycentric fetch is for. FACE is constant across
#: the triangle, which the same fetch gives for free by writing the face value to all
#: three corners. EDGE is deliberately absent: there is no correct corner value for
#: it, and inventing one would silently bake something Cycles never shades.
_SCALAR_ATTRIBUTE_DOMAINS = {"POINT", "CORNER", "FACE"}


def float_attribute_per_corner(obj, name: str) -> np.ndarray:
    """A named scalar FLOAT attribute at every loop-triangle corner.

    Returns ``(num_loop_triangles, 3)`` float32: for triangle *t*, corner *j*, the
    value the shader sees at that corner. Cycles interpolates a float attribute
    barycentrically exactly like a colour one, so these three corner values plus the
    barycentric lerp reproduce the shaded value anywhere in the triangle -- and a
    scalar needs one sidecar where a colour needs three.

    Restricted to ``FLOAT``. INT and BOOLEAN attributes of the same shape are left to
    Cycles on purpose: they are not simply floats to Cycles, and guessing at the
    conversion would silently bake a value nothing authored.

    Returns an empty ``(0, 3)`` array when the mesh has no triangles, carries no such
    attribute, or carries one this cannot honestly reproduce. The caller treats that
    as "no sidecar exists" and routes the channel to Cycles rather than reading a
    neighbouring object's corners.
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return np.empty((0, 3), dtype=np.float32)

    attributes = getattr(mesh, "attributes", None)
    layer = attributes.get(str(name or "")) if attributes is not None else None
    if layer is None:
        return np.empty((0, 3), dtype=np.float32)
    if str(getattr(layer, "data_type", "") or "").strip().upper() != "FLOAT":
        return np.empty((0, 3), dtype=np.float32)
    domain = str(getattr(layer, "domain", "") or "").strip().upper()
    if domain not in _SCALAR_ATTRIBUTE_DOMAINS:
        return np.empty((0, 3), dtype=np.float32)
    data = getattr(layer, "data", None)
    if data is None or len(data) == 0:
        return np.empty((0, 3), dtype=np.float32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count <= 0:
        return np.empty((0, 3), dtype=np.float32)

    element_count = len(data)
    values = np.empty(element_count, dtype=np.float32)
    try:
        data.foreach_get("value", values)
    except (TypeError, RuntimeError):
        return np.empty((0, 3), dtype=np.float32)

    if domain == "FACE":
        # One value per face, held by all three corners so the barycentric lerp of
        # equal values reproduces the flat shading Cycles gives.
        face_index = rna_buffers.empty_u32_for_rna(triangle_count)
        loop_triangles.foreach_get("polygon_index", face_index)
        face_index = rna_buffers.as_i32(face_index)
        face_index = np.clip(face_index.astype(np.int64), 0, element_count - 1)
        return np.repeat(values[face_index][:, None], 3, axis=1)

    index_attr = "loops" if domain == "CORNER" else "vertices"
    indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
    loop_triangles.foreach_get(index_attr, indices)
    indices = rna_buffers.as_i32(indices)
    indices = np.clip(indices.astype(np.int64), 0, element_count - 1)
    return values[indices].reshape(triangle_count, 3)


def uv_layer_per_corner(obj, name: str) -> np.ndarray:
    """A named UV layer at every loop-triangle corner.

    Returns ``(num_loop_triangles, 3, 2)`` float32: for triangle *t*, corner *j*,
    the (u, v) the shader sees at ``loop_triangle.loops[j]``. Cycles interpolates a
    UV layer barycentrically exactly like a colour attribute, so these three corner
    pairs plus the barycentric lerp reproduce the coordinate anywhere in the
    triangle.

    UV layers are always on the CORNER domain, so unlike
    :func:`color_attribute_per_corner` there is no POINT branch: a UV seam is
    precisely two corners of the same vertex holding different values, which is the
    thing a vertex-indexed read would destroy.

    Returns an empty ``(0, 3, 2)`` array when the mesh has no triangles or carries
    no such layer; the caller treats that as "no honest sidecar exists" and routes
    the channel to Cycles rather than reading a neighbour's corners.
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return np.empty((0, 3, 2), dtype=np.float32)

    uv_layers = getattr(mesh, "uv_layers", None)
    layer = None
    if uv_layers is not None:
        try:
            layer = uv_layers.get(str(name or ""))
        except (AttributeError, TypeError):
            layer = next(
                (item for item in uv_layers if str(getattr(item, "name", "")) == str(name or "")),
                None,
            )
    if layer is None:
        return np.empty((0, 3, 2), dtype=np.float32)
    data = getattr(layer, "data", None)
    if data is None or len(data) == 0:
        return np.empty((0, 3, 2), dtype=np.float32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count <= 0:
        return np.empty((0, 3, 2), dtype=np.float32)

    loop_count = len(data)
    values = np.empty(loop_count * 2, dtype=np.float32)
    data.foreach_get("uv", values)
    values = values.reshape(loop_count, 2)

    loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
    loop_triangles.foreach_get("loops", loops)
    loops = rna_buffers.as_i32(loops)
    loops = np.clip(loops.astype(np.int64), 0, loop_count - 1)
    return values[loops].reshape(triangle_count, 3, 2)


def uv_tangent_per_corner(obj, name: str) -> np.ndarray:
    """MikkTSpace tangents for a named UV layer, at every loop-triangle corner.

    Returns ``(num_loop_triangles, 3, 4)`` float32: the OBJECT-space tangent xyz
    plus the bitangent sign, for the corner at ``loop_triangle.loops[j]``.

    A Normal Map node whose ``uv_map`` names a layer builds its tangent frame from
    THAT layer, not the active one. The frame is not derivable from the UVs at
    shading time -- MikkTSpace is a per-corner solve over the whole mesh with
    specific splitting rules -- so it has to be computed here and carried, exactly
    like the UV values themselves. Blender computes the same basis Cycles consumes,
    so `calc_tangents` is the source of truth rather than anything reimplemented.

    The sign rides along as a fourth component because Cycles needs it to orient the
    bitangent: ``B = sign * cross(normal, tangent)`` (svm_node_normal_map). Deriving
    it from the UV winding here would be a second implementation of the thing
    MikkTSpace already decided.

    Returns an empty ``(0, 3, 4)`` array when the mesh has no triangles, carries no
    such layer, or the tangent solve fails; the caller treats that as "no honest
    sidecar exists" and routes the channel to Cycles.
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return np.empty((0, 3, 4), dtype=np.float32)

    layer_name = str(name or "")
    uv_layers = getattr(mesh, "uv_layers", None)
    if uv_layers is None:
        return np.empty((0, 3, 4), dtype=np.float32)
    try:
        has_layer = uv_layers.get(layer_name) is not None
    except (AttributeError, TypeError):
        has_layer = any(
            str(getattr(item, "name", "")) == layer_name for item in uv_layers
        )
    if not has_layer:
        return np.empty((0, 3, 4), dtype=np.float32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count <= 0:
        return np.empty((0, 3, 4), dtype=np.float32)

    loops = getattr(mesh, "loops", None)
    loop_count = len(loops) if loops is not None else 0
    if loop_count <= 0:
        return np.empty((0, 3, 4), dtype=np.float32)

    # calc_tangents raises on a mesh it cannot solve (no faces, degenerate UVs, an
    # ngon it cannot triangulate consistently). That is a legitimate "no sidecar",
    # not a bake failure.
    try:
        mesh.calc_tangents(uvmap=layer_name)
    except (RuntimeError, TypeError, ValueError):
        return np.empty((0, 3, 4), dtype=np.float32)

    try:
        tangents = np.empty(loop_count * 3, dtype=np.float32)
        loops.foreach_get("tangent", tangents)
        signs = np.empty(loop_count, dtype=np.float32)
        loops.foreach_get("bitangent_sign", signs)
    except (AttributeError, RuntimeError, TypeError):
        return np.empty((0, 3, 4), dtype=np.float32)
    finally:
        # The tangent arrays are mesh-resident until freed, and this runs over
        # multi-million-corner highs.
        free_tangents = getattr(mesh, "free_tangents", None)
        if callable(free_tangents):
            try:
                free_tangents()
            except RuntimeError:
                pass

    values = np.empty((loop_count, 4), dtype=np.float32)
    values[:, :3] = tangents.reshape(loop_count, 3)
    values[:, 3] = signs

    indices = rna_buffers.empty_u32_for_rna(triangle_count * 3)
    loop_triangles.foreach_get("loops", indices)
    indices = rna_buffers.as_i32(indices)
    indices = np.clip(indices.astype(np.int64), 0, loop_count - 1)
    return values[indices].reshape(triangle_count, 3, 4)


def material_index_per_corner(obj, slot_to_index) -> np.ndarray:
    """A per-triangle material index, expanded to every loop-triangle corner.

    ``slot_to_index`` maps this mesh's material-slot index to the position the
    caller's program expects (``-1`` for a slot the program does not cover).
    Returns ``(num_loop_triangles, 3)`` float32.

    All three corners of a triangle carry the same value, so the barycentric blend
    the sidecar fetch performs is exact everywhere inside the triangle. That is the
    whole reason this is a corner attribute rather than the UV-space detail mask,
    which is bounded by one texel wherever two materials meet.

    Returns an empty ``(0, 3)`` array when the mesh has no triangles; the caller
    treats that as "no honest sidecar exists".
    """
    mesh = _resolve_mesh(obj)
    if mesh is None:
        return np.empty((0, 3), dtype=np.float32)

    calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
    if callable(calc_loop_triangles):
        calc_loop_triangles()
    loop_triangles = getattr(mesh, "loop_triangles", None)
    triangle_count = len(loop_triangles) if loop_triangles is not None else 0
    if triangle_count <= 0:
        return np.empty((0, 3), dtype=np.float32)

    lookup = np.asarray(list(slot_to_index) or [-1], dtype=np.int64)
    polygons = getattr(mesh, "polygons", None)
    polygon_count = len(polygons) if polygons is not None else 0
    polygon_material = rna_buffers.zeros_u32_for_rna(max(1, polygon_count))
    if polygon_count:
        polygons.foreach_get("material_index", polygon_material)
    polygon_material = rna_buffers.as_i32(polygon_material)

    polygon_index = rna_buffers.empty_u32_for_rna(triangle_count)
    loop_triangles.foreach_get("polygon_index", polygon_index)
    polygon_index = rna_buffers.as_i32(polygon_index)
    per_triangle = lookup[
        np.clip(polygon_material[np.clip(polygon_index, 0, max(0, polygon_count - 1))],
                0, len(lookup) - 1)
    ]
    return np.repeat(per_triangle[:, None], 3, axis=1).astype(np.float32)
