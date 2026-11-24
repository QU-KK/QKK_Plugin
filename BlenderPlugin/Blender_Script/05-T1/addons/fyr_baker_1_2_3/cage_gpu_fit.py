"""GPU ray check for the Automatic cage fit.

``cage.raise_offsets_to_ray_reach`` checks a fitted cage against the bake's own rays and raises
the offsets that fall short. On a customer's 73-group gun that was two thirds of a cold fit:
a ``BVHTree.FromObject`` per high (GIL-bound) plus millions of Python ``ray_cast`` calls.

This module does the same check with whole arrays of rays answered by ``fyr_cage_gpu.exe``
(see :mod:`cage_gpu`), the way Toolbag's ``cageEstimate`` pass casts one ray per low surface
sample and keeps the hit distance. The algorithm and its constants are the CPU function's; only
the order of evaluation differs: each pass casts every sample against the offsets at the START
of the pass (the CPU version updates offsets sample by sample), and raises are a scatter-max, so
the result does not depend on triangle order.

Nothing here touches Blender data, so it runs on the preview's worker thread.
"""

from __future__ import annotations

import collections
import threading
import time

import numpy as np

from . import cage_gpu
from . import cage_soup

#: Resident scenes kept between fits (VRAM budget, by the tool's own byte count).
_SCENE_BUDGET_BYTES = 1_600_000_000
#: Ray count per tool call; keeps the transfer buffers and the GPU dispatch bounded.
_MAX_RAYS_PER_CALL = 1_500_000

#: Triangles per sequential chunk of the raise passes (see raise_offsets_to_ray_reach).
_SEQUENTIAL_CHUNK = 1000
_DISABLED = False
_PROBED: bool | None = None
_LOCK = threading.RLock()
_SCENES: "collections.OrderedDict[tuple, tuple]" = collections.OrderedDict()
STATS = {"load_s": 0.0, "trace_s": 0.0, "rays": 0, "loads": 0, "traces": 0, "read_ms": 0.0, "build_ms": 0.0, "triangles": 0}


class GpuHighIndex:
    """A high scene for the GPU ray check, in place of a tuple of BVH trees.

    ``entries`` are ``(fymesh path, 16 floats object-to-world)`` per high object. ``fallback``,
    when set, builds the CPU BVH index (main thread only) for a fit the GPU cannot serve."""

    __slots__ = ("_entries", "_settled", "key", "fallback", "names")

    def __init__(self, entries, fallback=None, names=None):
        self._entries = tuple((str(path), tuple(float(v) for v in matrix)) for path, matrix in entries)
        self._settled = False
        self.key = self._entries
        self.fallback = fallback
        #: Object name per entry (Match By Isolation pairs lows with highs by name).
        self.names = tuple(str(name) for name in (names or ()))

    @property
    def entries(self):
        """The ``(path, matrix)`` pairs. A file the add-on is still writing on a worker thread
        (the fit exports FYRGEOM1 and moves on) is complete once this returns."""
        if not self._settled:
            from . import indexed_geometry

            for path, _matrix in self._entries:
                indexed_geometry.wait_for_canonical_path(path)
            self._settled = True
        return self._entries

    def __bool__(self) -> bool:
        return bool(self._entries)


def disable(reason: str = "") -> None:
    """Stop using the GPU ray check for the rest of the session (a failed fit falls back)."""
    global _DISABLED
    _DISABLED = True
    if reason:
        print(f"[MasterBaker] GPU cage fit unavailable, using the Python fit: {reason}")


def available() -> bool:
    """True when the GPU fit can serve: not switched off (FYR_GPU_CAGE=0), tool installed, and the
    tool started once on a DXR adapter. A failed start or fit turns it off for the session."""
    global _PROBED
    if _DISABLED or not cage_gpu.gpu_cage_enabled() or cage_gpu.executable_path() is None:
        return False
    if _PROBED is None:
        try:
            worker = cage_gpu.shared_worker()
            if worker is None:
                raise cage_gpu.CageGpuError("fyr_cage_gpu.exe not found")
            worker.start()
            _PROBED = True
        except Exception as error:
            _PROBED = False
            disable(f"{type(error).__name__}: {error}")
    return bool(_PROBED) and not _DISABLED


def build_index(high_objects, *, fallback=None, export_missing: bool = False, depsgraph=None):
    """A :class:`GpuHighIndex` for ``high_objects``, or None when the GPU path cannot serve them
    (not enabled, tool missing, a high without a native ``.fymesh``).

    With ``export_missing`` (main thread only) a high that is not written yet is exported now:
    the bake needs that file next anyway, and writing it is far cheaper than a BVH build."""
    if not available():
        return None
    from . import high_mesh_cache

    entries = []
    names = []
    for obj in high_objects:
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        path = high_mesh_cache.warm_high_mesh_path(obj)
        if path is None and export_missing and depsgraph is not None:
            # With the FYRGEOM1 transport the bake needs this same capture next: one export,
            # not a .fymesh for the tool plus an FYRGEOM1 for the bake.
            path = high_mesh_cache.export_indexed_canonical(obj, depsgraph)
            if path is None:
                try:
                    high_mesh_cache.resolve_high_mesh_ref(obj, depsgraph)
                except Exception:
                    return None
                path = high_mesh_cache.warm_high_mesh_path(obj)
        if path is None or str(path.suffix).lower() not in {".fymesh", ".fyrgeom"}:
            return None
        try:
            matrix = [float(v) for row in obj.matrix_world for v in row]
        except Exception:
            return None
        entries.append((path, matrix))
        names.append(str(getattr(obj, "name", "")))
    if not entries:
        return None
    return GpuHighIndex(entries, fallback=fallback, names=names)


def clear_scenes() -> None:
    worker = cage_gpu.shared_worker() if cage_gpu.executable_path() is not None else None
    with _LOCK:
        scenes = list(_SCENES.values())
        _SCENES.clear()
    if worker is not None:
        for _generation, scene_id, _bytes in scenes:
            worker.free_scene(scene_id)


def _scene(index: GpuHighIndex):
    worker = cage_gpu.shared_worker()
    if worker is None:
        raise cage_gpu.CageGpuError("fyr_cage_gpu.exe not found")
    with _LOCK:
        entry = _SCENES.get(index.key)
        if entry is not None and entry[0] == worker.generation:
            _SCENES.move_to_end(index.key)
            return worker, entry[1]
        started = time.perf_counter()
        scene_id, report = worker.load_scene(index.entries)
        STATS["load_s"] += time.perf_counter() - started
        STATS["loads"] += 1
        STATS["read_ms"] += float(report.get("read_ms", 0.0))
        STATS["build_ms"] += float(report.get("build_ms", 0.0))
        STATS["triangles"] += int(report.get("triangles", 0))
        _SCENES[index.key] = (worker.generation, scene_id, int(report.get("bytes", 0)))
        total = sum(item[2] for item in _SCENES.values())
        while total > _SCENE_BUDGET_BYTES and len(_SCENES) > 1:
            old_key, (generation, old_id, old_bytes) = next(iter(_SCENES.items()))
            if old_key == index.key:
                break
            del _SCENES[old_key]
            total -= old_bytes
            if generation == worker.generation:
                worker.free_scene(old_id)
        return worker, scene_id


def _trace(index: GpuHighIndex, origins, directions, tmax):
    """(distance, facing) per ray; distance -1 on a miss."""
    count = int(origins.shape[0])
    if count == 0:
        empty = np.zeros(0, dtype=np.float32)
        return empty, empty
    worker, scene_id = _scene(index)
    rays = np.empty((count, 8), dtype=np.float32)
    rays[:, 0:3] = origins
    rays[:, 3] = 0.0
    rays[:, 4:7] = directions
    rays[:, 7] = tmax
    started = time.perf_counter()
    distance, facing = worker.trace(scene_id, rays)
    STATS["trace_s"] += time.perf_counter() - started
    STATS["rays"] += count
    STATS["traces"] += 1
    return distance, facing


def raise_offsets_to_ray_reach(
    source_triangles, offsets, index: GpuHighIndex, *, passes: int = 2, diagnostics: dict | None = None
) -> int:
    """GPU twin of ``cage.raise_offsets_to_ray_reach`` (same contract and constants)."""
    from . import cage

    if native_enabled():
        return native_raise_offsets_to_ray_reach(
            source_triangles, offsets, index, passes=passes, diagnostics=diagnostics
        )

    if not source_triangles or not offsets or not index:
        return 0
    diagonal = cage._source_triangles_diagonal(source_triangles)
    window = cage._RAY_REACH_WINDOW_FRACTION * diagonal
    if not (window > 0.0):
        return 0
    margin = max(0.0005, diagonal * float(cage._AUTO_CAGE_PADDING_DIAG_FRACTION))
    ceiling = window + margin
    wide_window = cage._RAY_REACH_WIDE_FRACTION * diagonal
    sparse = np.asarray(cage._RAY_REACH_SAMPLES, dtype=np.float64)
    dense = np.asarray(cage._RAY_REACH_DENSE_SAMPLES, dtype=np.float64)

    # ---- arrays -----------------------------------------------------------------------
    key_index: dict = {}
    key_list: list = []
    tri_keys: list = []
    positions: list = []
    normals: list = []
    key_of = cage._source_position_group_key
    for triangle in source_triangles:
        corners = triangle.corners
        keys = [key_of(triangle.object_name, corner.source_position, digits=6) for corner in corners]
        if not (keys[0] in offsets and keys[1] in offsets and keys[2] in offsets):
            continue
        row = []
        for key in keys:
            slot = key_index.get(key)
            if slot is None:
                slot = len(key_list)
                key_index[key] = slot
                key_list.append(key)
            row.append(slot)
        tri_keys.append(row)
        for corner in corners:
            p = corner.source_position
            n = corner.normal
            positions.append((p.x, p.y, p.z))
            normals.append((n.x, n.y, n.z))
    triangle_count = len(tri_keys)
    if triangle_count == 0:
        return 0
    KI = np.asarray(tri_keys, dtype=np.int64)
    P = np.asarray(positions, dtype=np.float64).reshape(triangle_count, 3, 3)
    N = np.asarray(normals, dtype=np.float64).reshape(triangle_count, 3, 3)
    original = np.array([offsets[key] for key in key_list], dtype=np.float64)
    current = original.copy()
    key_count = len(key_list)

    # A corner may only grow by about its own edge length (cage._RAY_REACH_LOCAL_EDGE_FACTOR).
    edge_sum = np.zeros(key_count)
    edge_count = np.zeros(key_count)
    edges_a: list = []
    edges_b: list = []
    edges_len: list = []
    for i in range(3):
        j = (i + 1) % 3
        length = np.linalg.norm(P[:, i] - P[:, j], axis=1)
        np.add.at(edge_sum, KI[:, i], length)
        np.add.at(edge_sum, KI[:, j], length)
        np.add.at(edge_count, KI[:, i], 1.0)
        np.add.at(edge_count, KI[:, j], 1.0)
        edges_a.append(KI[:, i])
        edges_b.append(KI[:, j])
        edges_len.append(length)
    mean_edge = edge_sum / np.maximum(edge_count, 1.0)
    local_ceiling = np.maximum(original, np.minimum(ceiling, cage._RAY_REACH_LOCAL_EDGE_FACTOR * mean_edge))
    ceiling_per_key = np.minimum(ceiling, local_ceiling)

    # ---- one evaluation of a batch of samples -----------------------------------------
    def evaluate(tri_index, weights, offsets_now, look):
        """For ``tri_index`` x ``weights``: exit distance (nan = no exit seen), the ray's
        length (the cage reach there), and whether the sample has a ray at all."""
        count = int(tri_index.shape[0])
        samples = int(weights.shape[0])
        exit_along = np.full((count, samples), np.nan)
        reach_length = np.zeros((count, samples))
        valid = np.zeros((count, samples), dtype=bool)
        step = max(1, _MAX_RAYS_PER_CALL // max(1, samples))
        for first in range(0, count, step):
            chunk = tri_index[first : first + step]
            m = int(chunk.shape[0])
            points = np.einsum("sj,mjc->msc", weights, P[chunk])
            scaled = offsets_now[KI[chunk]]
            reach = np.einsum("sj,mj,mjc->msc", weights, scaled, N[chunk])
            length = np.linalg.norm(reach, axis=2)
            ok = length >= 1.0e-9
            direction = reach / np.where(ok, length, 1.0)[:, :, None]
            flat = ok.reshape(-1)
            ids = np.nonzero(flat)[0]
            if ids.size:
                distance, facing = _trace(
                    index, points.reshape(-1, 3)[ids], direction.reshape(-1, 3)[ids], np.float32(look)
                )
                found = (distance > 0.0) & (facing > 0.0)
                along = np.full(flat.shape, np.nan)
                along[ids] = np.where(found, distance, np.nan)
                exit_along[first : first + m] = along.reshape(m, samples)
            reach_length[first : first + m] = length
            valid[first : first + m] = ok
        return exit_along, reach_length, valid

    def raise_from(tri_index, weights, exit_along, short):
        """Scatter-max the targets of the short samples into ``current``. Returns the number
        of corner raises and, per triangle, whether any happened."""
        count = int(tri_index.shape[0])
        raised_here = np.zeros(count, dtype=bool)
        if not short.any():
            return 0, raised_here
        rows, cols = np.nonzero(short)
        tri = tri_index[rows]
        w = weights[cols]  # (k, 3)
        plain = np.einsum("kj,kj,kjc->kc", w, original[KI[tri]], N[tri])
        plain_reach = np.linalg.norm(plain, axis=1)
        good = plain_reach >= 1.0e-9
        if not good.any():
            return 0, raised_here
        rows, tri, w = rows[good], tri[good], w[good]
        scale = (exit_along[rows, cols[good]] + margin) / plain_reach[good]
        events = 0
        target_all = np.zeros(key_count)
        for corner in range(3):
            keys = KI[tri, corner]
            used = w[:, corner] > 0.0
            target = np.minimum(original[keys] * scale, ceiling_per_key[keys])
            gain = used & (target > current[keys])
            if gain.any():
                events += int(gain.sum())
                raised_here[rows[gain]] = True
                np.maximum.at(target_all, keys[gain], target[gain])
        np.maximum(current, target_all, out=current)
        return events, raised_here

    # ---- sparse passes ----------------------------------------------------------------
    # Triangles go through in order, a chunk at a time, each chunk cast against the offsets the
    # chunks before it left: the CPU check updates offsets sample by sample, and a neighbour
    # that an earlier raise already covers must not raise again.
    all_tris = np.arange(triangle_count)
    close = np.zeros(triangle_count, dtype=bool)
    raised = 0
    candidates = all_tris
    for _pass in range(max(1, int(passes))):
        touched = np.zeros(candidates.shape[0], dtype=bool)
        events = 0
        for first in range(0, candidates.shape[0], _SEQUENTIAL_CHUNK):
            sub = candidates[first : first + _SEQUENTIAL_CHUNK]
            exit_along, length, valid = evaluate(sub, sparse, current, wide_window)
            with np.errstate(invalid="ignore"):
                seen = valid & np.isfinite(exit_along)
                near = seen & (exit_along > 0.6 * length)
                short = seen & (exit_along + margin * 0.5 > length)
            chunk_events, raised_here = raise_from(sub, sparse, exit_along, short)
            events += chunk_events
            touched[first : first + sub.shape[0]] = near.any(axis=1) | raised_here
        close[candidates[touched]] = True
        raised += events
        if not events:
            break
        candidates = candidates[touched]
        if candidates.size == 0:
            break

    # ---- dense follow-up --------------------------------------------------------------
    raised_keys = current > original
    pending = np.nonzero(close | raised_keys[KI].any(axis=1))[0]
    for _round in range(4):
        if pending.size == 0:
            break
        tri_short = np.zeros(pending.shape[0], dtype=bool)
        for first in range(0, pending.shape[0], _SEQUENTIAL_CHUNK * 4):
            sub = pending[first : first + _SEQUENTIAL_CHUNK * 4]
            exit_along, length, valid = evaluate(sub, dense, current, wide_window)
            with np.errstate(invalid="ignore"):
                short = valid & np.isfinite(exit_along) & (exit_along + margin * 0.5 > length)
            tri_short[first : first + sub.shape[0]] = short.any(axis=1)
        if not tri_short.any():
            pending = pending[:0]
            break
        pending = pending[tri_short]
        for first in range(0, pending.shape[0], _SEQUENTIAL_CHUNK):
            sub = pending[first : first + _SEQUENTIAL_CHUNK]
            exit_along, length, valid = evaluate(sub, dense, current, wide_window)
            with np.errstate(invalid="ignore"):
                short = valid & np.isfinite(exit_along) & (exit_along + margin * 0.5 > length)
            chunk_events, _ = raise_from(sub, dense, exit_along, short)
            raised += chunk_events

    stage_counts = {"after_dense": int((current > original).sum())}
    # ---- keep the cage even: slope limit ----------------------------------------------
    if cage._RAY_REACH_EVEN_MODE == "median":
        values = np.sort(current)
        even_ceiling = cage._RAY_REACH_TYPICAL_FACTOR * float(values[len(values) // 2])
        capped = (current > original) & (current > even_ceiling)
        current[capped] = np.maximum(original[capped], even_ceiling)
    else:
        a = np.concatenate(edges_a)
        b = np.concatenate(edges_b)
        lengths = np.concatenate(edges_len)
        low_key = np.minimum(a, b)
        high_key = np.maximum(a, b)
        _, first = np.unique(low_key * key_count + high_key, return_index=True)
        a, b, lengths = low_key[first], high_key[first], lengths[first]
        limit = cage._RAY_REACH_SLOPE * lengths
        for _iteration in range(int(cage._RAY_REACH_SLOPE_ITERATIONS) * 4):
            a_high = current[a] >= current[b]
            hi = np.where(a_high, a, b)
            lo = np.where(a_high, b, a)
            active = current[hi] > original[hi]
            floor = np.minimum(ceiling, current[hi] - limit)
            lift = active & (current[lo] < floor)
            if not lift.any():
                break
            np.maximum.at(current, lo[lift], floor[lift])

    stage_counts["after_slope"] = int((current > original).sum())
    # ---- revert raises that push the cage into another piece --------------------------
    reverted = _revert_entering(
        index, source_triangles, KI, P, N, current, original, dense, ceiling, key_count
    )

    stage_counts["after_revert"] = int((current > original).sum())
    if diagnostics is not None:
        diagnostics["stage_after_dense"] = stage_counts["after_dense"]
        diagnostics["stage_after_slope"] = stage_counts["after_slope"]
        diagnostics["stage_after_revert"] = stage_counts["after_revert"]
        diagnostics["ray_reverted_vertices"] = int(diagnostics.get("ray_reverted_vertices", 0)) + reverted
        moved = (current != original) | raised_keys
        pending = np.nonzero(close | moved[KI].any(axis=1))[0]
        short_count = 0
        if pending.size:
            exit_along, length, valid = evaluate(pending, dense, current, wide_window)
            with np.errstate(invalid="ignore"):
                short_count = int((valid & np.isfinite(exit_along) & (exit_along + margin * 0.5 > length)).sum())
        diagnostics["ray_short_samples"] = int(diagnostics.get("ray_short_samples", 0)) + short_count
        diagnostics["ray_samples"] = int(diagnostics.get("ray_samples", 0)) + triangle_count * int(dense.shape[0])

    changed = np.nonzero(current != original)[0]
    for slot in changed.tolist():
        offsets[key_list[slot]] = float(current[slot])
    return raised


def _revert_entering(index, source_triangles, KI, P, N, current, original, dense, ceiling, key_count):
    """Put raised corners back to the plain fit where the cage segment ENTERS a surface that
    belongs to another connected low piece (cage.raise_offsets_to_ray_reach's last step).
    Returns the number of corners put back."""
    triangle_count = int(KI.shape[0])
    # Connected low pieces: union-find over shared corner keys.
    parent = np.arange(key_count)

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    low_tree = None
    island = None
    reverted_total = 0
    for _round in range(3):
        moved = np.nonzero((current > original)[KI].any(axis=1))[0]
        if moved.size == 0:
            break
        if low_tree is None:
            island, low_tree = _low_pieces(KI, P, root, parent)
            if low_tree is None:
                break
        samples = int(dense.shape[0])
        points = np.einsum("sj,mjc->msc", dense, P[moved])
        reach = np.einsum("sj,mj,mjc->msc", dense, current[KI[moved]], N[moved])
        length = np.linalg.norm(reach, axis=2)
        ok = (length >= 1.0e-9).reshape(-1)
        length_flat = length.reshape(-1)
        direction = (reach / np.where(length >= 1.0e-9, length, 1.0)[:, :, None]).reshape(-1, 3)
        point_flat = points.reshape(-1, 3)
        tri_of = np.repeat(moved, samples)
        sample_of = np.tile(np.arange(samples), moved.size)
        ray_ids = np.nonzero(ok)[0]
        start = length_flat[ray_ids] * 1.0e-3
        reach_len = length_flat[ray_ids]
        direction = direction[ray_ids]
        cursor = point_flat[ray_ids] + direction * start[:, None]
        travelled = np.zeros(ray_ids.size)
        own = island[tri_of[ray_ids]]
        flagged = np.zeros(ray_ids.size, dtype=bool)
        alive = np.ones(ray_ids.size, dtype=bool)
        for _hit in range(8):
            active = np.nonzero(alive & ~flagged)[0]
            if active.size == 0:
                break
            tmax = reach_len[active] - travelled[active] - start[active]
            spent = tmax <= 0.0
            alive[active[spent]] = False
            active, tmax = active[~spent], tmax[~spent]
            if active.size == 0:
                break
            distance, facing = _trace(index, cursor[active], direction[active], tmax.astype(np.float32))
            hit = distance >= 0.0
            miss_ids = active[~hit]
            alive[miss_ids] = False
            hit_ids = active[hit]
            if hit_ids.size == 0:
                break
            hit_distance = distance[hit].astype(np.float64)
            hit_point = cursor[hit_ids] + direction[hit_ids] * hit_distance[:, None]
            travelled[hit_ids] += start[hit_ids] + hit_distance
            entering = facing[hit] < 0.0
            for local in np.nonzero(entering)[0].tolist():
                ray = hit_ids[local]
                found = low_tree.find_nearest(tuple(hit_point[local]))
                if found is not None and found[2] is not None and island[found[2]] != own[ray]:
                    flagged[ray] = True
            cursor[hit_ids] = hit_point + direction[hit_ids] * start[hit_ids][:, None]
            alive[hit_ids[travelled[hit_ids] >= reach_len[hit_ids]]] = False
        if not flagged.any():
            break
        bad = ray_ids[flagged]
        to_revert = np.zeros(key_count, dtype=bool)
        weights = dense[sample_of[bad]]
        for corner in range(3):
            keys = KI[tri_of[bad], corner]
            used = (weights[:, corner] > 0.0) & (current[keys] > original[keys])
            to_revert[keys[used]] = True
        count = int(to_revert.sum())
        if not count:
            break
        current[to_revert] = original[to_revert]
        reverted_total += count
    return reverted_total


def _low_pieces(KI, P, root, parent):
    """(piece id per triangle, BVH of the low triangles) for the revert step."""
    try:
        from mathutils.bvhtree import BVHTree
    except Exception:
        return None, None
    for row in KI.tolist():
        first = root(row[0])
        for k in row[1:]:
            other = root(k)
            if other != first:
                parent[other] = first
    island = np.array([root(row[0]) for row in KI.tolist()], dtype=np.int64)
    count = int(KI.shape[0])
    flat = P.reshape(-1, 3).tolist()
    try:
        tree = BVHTree.FromPolygons(flat, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(count)], all_triangles=True)
    except Exception:
        return None, None
    return island, tree


# ---------------------------------------------------------------------------------------------
# Native fit: the whole ray check runs inside fyr_cage_gpu.exe (CMD_FITBATCH). Python only builds
# arrays (numpy, no per-vertex loops) and maps the answer back onto the offsets dict.
# ---------------------------------------------------------------------------------------------
def native_enabled() -> bool:
    """On by default once the GPU cage is enabled; FYR_GPU_CAGE_NATIVE=0 keeps the numpy port."""
    import os

    return os.environ.get("FYR_GPU_CAGE_NATIVE", "1").strip().lower() not in {"0", "off", "false", "no"}


def _slope_iterations() -> int:
    import os

    value = os.environ.get("FYR_CAGE_SLOPE_ITERS")
    return int(value) if value else int(cage_slope_iterations())


def cage_slope_iterations() -> int:
    from . import cage

    return int(cage._RAY_REACH_SLOPE_ITERATIONS) * 4


def prepare_arrays(source_triangles):
    """Numpy arrays of a group's low triangles and their fit keys (shared by the coverage and
    the ray-check requests). Returns None for an empty group, else a dict:

    ``positions`` / ``normals`` (T, 3, 3) float64, ``tri_object`` (T,) object index, ``key_index``
    (T, 3) int64 (a fit key is one per (object, position rounded to 6 digits), like
    ``cage._source_position_group_key``), ``first`` (K,) flat corner row of each key's first
    corner, ``key_count``, and ``object_names`` (by object index)."""
    count = len(source_triangles)
    if not count:
        return None
    if isinstance(source_triangles, cage_soup.CageSoup):
        return source_triangles.prepare_arrays()
    object_ids: dict = {}
    tri_object = np.fromiter(
        (object_ids.setdefault(triangle.object_name, len(object_ids)) for triangle in source_triangles),
        dtype=np.int64,
        count=count,
    )
    positions = np.array(
        [(p.x, p.y, p.z) for triangle in source_triangles for corner in triangle.corners for p in (corner.source_position,)],
        dtype=np.float64,
    ).reshape(count, 3, 3)
    normals = np.array(
        [(n.x, n.y, n.z) for triangle in source_triangles for corner in triangle.corners for n in (corner.normal,)],
        dtype=np.float64,
    ).reshape(count, 3, 3)
    rows = np.empty((count * 3, 4), dtype=np.int64)
    rows[:, :3] = np.rint(positions.reshape(-1, 3) * 1.0e6).astype(np.int64)
    rows[:, 3] = np.repeat(tri_object, 3)
    _unique, first, inverse = np.unique(rows, axis=0, return_index=True, return_inverse=True)
    inverse = np.asarray(inverse).reshape(-1)
    return {
        "positions": positions,
        "normals": normals,
        "tri_object": tri_object,
        "key_index": inverse.reshape(count, 3),
        "first": first,
        "key_count": int(first.shape[0]),
        "object_names": list(object_ids),
    }


def unique_keys_of(arrays, source_triangles):
    """The offsets-dict key of every fit key (``cage._source_position_group_key``)."""
    from . import cage

    if isinstance(source_triangles, cage_soup.CageSoup):
        return list(source_triangles.sorted_key_tuples())
    key_of = cage._source_position_group_key
    keys = []
    for corner_row in arrays["first"].tolist():
        triangle = source_triangles[corner_row // 3]
        keys.append(key_of(triangle.object_name, triangle.corners[corner_row % 3].source_position, digits=6))
    return keys


def _fit_params(positions, cage_module):
    """(diagonal, window, margin) of a set of low corner positions, like the CPU fit."""
    flat = positions.reshape(-1, 3)
    diagonal = float(np.linalg.norm(flat.max(axis=0) - flat.min(axis=0)))
    margin = max(0.0005, diagonal * float(cage_module._AUTO_CAGE_PADDING_DIAG_FRACTION))
    return diagonal, cage_module._RAY_REACH_WINDOW_FRACTION * diagonal, margin


def prepare_fit_job(source_triangles, offsets, index: "GpuHighIndex"):
    """Arrays for one group's native ray check, or None when there is nothing to check.

    Returns ``(job, unique_keys)``: ``job`` is the dict ``CageGpuWorker.fit_batch`` takes, and
    ``unique_keys[i]`` is the offsets-dict key of fit key ``i``."""
    if not source_triangles or not offsets or not index:
        return None
    arrays = prepare_arrays(source_triangles)
    if arrays is None:
        return None
    unique_keys = unique_keys_of(arrays, source_triangles)
    original = np.full(arrays["key_count"], np.nan, dtype=np.float64)
    for slot, key in enumerate(unique_keys):
        value = offsets.get(key)
        if value is not None:
            original[slot] = value
    return fit_job_from_arrays(arrays, original, index), unique_keys


def fit_job_from_arrays(arrays, original, index: "GpuHighIndex"):
    """The native ray-check job for prepared arrays and the plain-fit offsets ``original`` (NaN =
    no offset for that key; triangles touching one are left out). None when nothing is left."""
    from . import cage

    positions = arrays["positions"]
    normals = arrays["normals"]
    key_index = arrays["key_index"]
    diagonal, window, margin = _fit_params(positions, cage)
    if not (window > 0.0):
        return None
    usable = np.isfinite(original)[key_index].all(axis=1)
    if not usable.any():
        return None
    if not usable.all():
        key_index = key_index[usable]
        positions = positions[usable]
        normals = normals[usable]
    original = np.where(np.isfinite(original), original, 0.0)
    return {
        "meshes": index.entries,
        "key_index": key_index.astype(np.int32),
        "positions": positions.astype(np.float32),
        "normals": normals.astype(np.float32),
        "original": original.astype(np.float32),
        "params": (
            float(window),
            float(cage._RAY_REACH_WIDE_FRACTION * diagonal),
            float(margin),
            float(window + margin),
            float(cage._RAY_REACH_SLOPE),
            float(cage._RAY_REACH_LOCAL_EDGE_FACTOR),
            _slope_iterations(),
            2,
        ),
    }


# ---------------------------------------------------------------------------------------------
# Plain coverage fit in the tool (CMD_COVERBATCH): cage.build_group_coverage_offsets' binding of
# every high vertex to its nearest low face runs natively from the same .fymesh files; the clamp,
# dilation and margin stay numpy here (they are cheap and need the per-object bookkeeping).
# ---------------------------------------------------------------------------------------------
def coverage_enabled() -> bool:
    """On with the native fit; FYR_GPU_CAGE_COVERAGE=0 keeps the plain coverage fit in Python."""
    import os

    return native_enabled() and os.environ.get("FYR_GPU_CAGE_COVERAGE", "1").strip().lower() not in {
        "0",
        "off",
        "false",
        "no",
    }


def coverage_partitions(low_triangle_groups, index: "GpuHighIndex", *, match_by_isolation: bool, diagnostics=None):
    """Which triangles are fitted against which highs, as ``cage._build_group_coverage_offsets`` does.

    ``low_triangle_groups`` is the same list of per-object triangle lists the CPU fit takes; the
    arrays of :func:`prepare_arrays` follow their concatenation. Returns a list of
    ``(triangle index array, tuple of index entry numbers)``."""
    from . import cage

    groups = [group for group in low_triangle_groups if group]
    sizes = [len(group) for group in groups]
    starts = np.concatenate([[0], np.cumsum(sizes)]).astype(np.int64)
    everything = tuple(range(len(index.entries)))
    if not (match_by_isolation and index.names):
        return [(np.arange(int(starts[-1]), dtype=np.int64), everything)]
    names = list(index.names)
    by_high: dict = {}
    unisolated: list = []
    unisolated_objects: set = set()
    isolated_pairs: list = []
    for number, group in enumerate(groups):
        object_names = {triangle.object_name for triangle in group}
        low_name = next(iter(object_names)) if len(object_names) == 1 else None
        high_index = cage.isolation_high_index_for_low(low_name, names) if low_name else None
        rows = np.arange(int(starts[number]), int(starts[number + 1]), dtype=np.int64)
        if high_index is None or not (0 <= high_index < len(names)):
            unisolated.append(rows)
            unisolated_objects.update(object_names)
            continue
        isolated_pairs.append((str(low_name), str(names[high_index])))
        by_high.setdefault(high_index, []).append(rows)
    partitions = [(np.concatenate(rows), (high_index,)) for high_index, rows in by_high.items()]
    if unisolated:
        partitions.append((np.concatenate(unisolated), everything))
    if diagnostics is not None:
        diagnostics["isolated_pairs"] = isolated_pairs
        diagnostics["unisolated_low_objects"] = sorted(unisolated_objects)
    return partitions


def coverage_items(arrays, partitions, index: "GpuHighIndex"):
    """The CMD_COVERBATCH items (one per partition) for prepared arrays."""
    key_index = arrays["key_index"]
    positions = arrays["positions"]
    normals = arrays["normals"]
    # Every corner binds with the normal of its KEY's first corner (cage.build_coverage_offsets).
    key_normal = normals.reshape(-1, 3)[arrays["first"]]
    corner_normals = key_normal[key_index]
    items = []
    for rows, entry_numbers in partitions:
        items.append(
            {
                "meshes": [index.entries[number] for number in entry_numbers],
                "key_index": key_index[rows].astype(np.int32),
                "positions": positions[rows].astype(np.float32),
                "normals": corner_normals[rows].astype(np.float32),
                "key_count": arrays["key_count"],
            }
        )
    return items


def finish_coverage(arrays, unique_keys, partitions, results, *, dilation_iterations: int = 2, diagnostics=None):
    """Offsets (float64, one per fit key) from the tool's reach arrays: per partition the cross-part
    outlier clamp, the neighbourhood dilation and the model-relative margin, exactly the tail of
    ``cage.build_coverage_offsets``."""
    from . import cage

    key_index = arrays["key_index"]
    positions = arrays["positions"]
    offsets = np.zeros(arrays["key_count"], dtype=np.float64)
    for (rows, _entries), result in zip(partitions, results):
        ki = key_index[rows]
        keys_here = np.unique(ki)
        values = np.asarray(result["reach"], dtype=np.float32)[keys_here].astype(np.float64)
        cage._clamp_cross_part_reach(values, [unique_keys[k] for k in keys_here.tolist()], diagnostics)
        if int(dilation_iterations) > 0:
            local = np.searchsorted(keys_here, ki)
            edge_from = np.concatenate([local[:, 0], local[:, 1], local[:, 0], local[:, 2], local[:, 1], local[:, 2]])
            edge_to = np.concatenate([local[:, 1], local[:, 0], local[:, 2], local[:, 0], local[:, 2], local[:, 1]])
            for _iteration in range(int(dilation_iterations)):
                dilated = values.copy()
                np.maximum.at(dilated, edge_from, values[edge_to])
                values = dilated
        _diagonal, _window, margin = _fit_params(positions[rows], cage)
        offsets[keys_here] = values + margin
    return offsets


def apply_fit_result(offsets, unique_keys, job, result, diagnostics) -> int:
    """Write a native fit's offsets back into ``offsets`` and the diagnostics; returns raised corners."""
    new = result["offsets"]
    changed = np.nonzero(new != job["original"])[0]
    for slot in changed.tolist():
        offsets[unique_keys[slot]] = float(new[slot])
    raised, reverted, short, samples = result["stats"][:4]
    if diagnostics is not None:
        diagnostics["ray_reverted_vertices"] = int(diagnostics.get("ray_reverted_vertices", 0)) + int(reverted)
        diagnostics["ray_short_samples"] = int(diagnostics.get("ray_short_samples", 0)) + int(short)
        diagnostics["ray_samples"] = int(diagnostics.get("ray_samples", 0)) + int(samples)
    STATS["rays"] += int(result["stats"][7])
    STATS["traces"] += int(result["stats"][8])
    STATS["load_s"] += float(result["load_ms"]) / 1000.0
    STATS["trace_s"] += float(result["fit_ms"]) / 1000.0
    return int(raised)


def native_raise_offsets_to_ray_reach(source_triangles, offsets, index, *, passes=2, diagnostics=None) -> int:
    """One group's ray check on the native path (see :func:`raise_offsets_to_ray_reach`)."""
    prepared = prepare_fit_job(source_triangles, offsets, index)
    if prepared is None:
        return 0
    job, unique_keys = prepared
    worker = cage_gpu.shared_worker()
    if worker is None:
        raise cage_gpu.CageGpuError("fyr_cage_gpu.exe not found")
    result = worker.fit_batch([job])[0]
    return apply_fit_result(offsets, unique_keys, job, result, diagnostics)
