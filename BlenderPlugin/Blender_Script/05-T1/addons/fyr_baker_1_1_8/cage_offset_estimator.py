from __future__ import annotations

from . import mesh_read
from . import constants


_ESTIMATE_CACHE: dict = {}
_ESTIMATE_CACHE_ORDER: list = []
_ESTIMATE_CACHE_MAX = 4096  # one float per low; must exceed the largest project's group count


def clear_estimate_cache() -> None:
    _ESTIMATE_CACHE.clear()
    _ESTIMATE_CACHE_ORDER.clear()


# Estimates that survive the session (2026-09-29). The in-memory cache above is keyed on
# object pointers, so every file open measured again: one BVHTree.FromObject per high,
# ~140 B per triangle, 5.8 GB of Blender RAM for SvAT's 41 M-triangle Body_Main on each
# open, a minute before the prewarm. On disk the key is geometry CONTENT: the evaluated
# vertex positions, topology and world matrix of the low and of every high, so an edit
# made anywhere (even with the add-on off) is a different key. Hashing costs ~12 B per
# high vertex, transiently, and only when the in-memory cache misses.
_PERSISTENT_ESTIMATES_FILE = "cage_offset_estimates_v1.json"
_PERSISTENT_ESTIMATES_MAX = 4096  # one entry per low or group; 256 cycled on a 300-group project


def _persistent_estimates_path():
    try:
        from . import high_mesh_cache

        return high_mesh_cache.persistent_cache_root_path() / _PERSISTENT_ESTIMATES_FILE
    except Exception:
        return None


def _load_persistent_estimates() -> dict:
    import json

    path = _persistent_estimates_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def _store_persistent_estimates(new_entries: dict) -> None:
    import json
    import os

    path = _persistent_estimates_path()
    if path is None or not new_entries:
        return
    entries = _load_persistent_estimates()
    for key, value in new_entries.items():
        entries.pop(key, None)
        entries[key] = float(value)
    while len(entries) > _PERSISTENT_ESTIMATES_MAX:
        entries.pop(next(iter(entries)))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temp.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        os.replace(temp, path)
    except Exception:
        pass


def _mesh_content_digest(obj, depsgraph, digest, *, corner_normals: bool = False) -> bool:
    """Feed an object's evaluated geometry (positions, polygon corners, world matrix) into
    ``digest``. Reads a to_mesh copy of the evaluated mesh; False when unavailable.

    The copy is cheap (implicitly shared, no modifier re-evaluation) and is what makes the
    read free afterwards: an RNA position read takes write access, which un-shares a full
    position array on whichever mesh it reads. On the evaluated mesh that copy stayed in
    Blender for the session (~0.9 GB over SvAT's highs); on the copy, to_mesh_clear frees it.
    """
    import numpy as np

    try:
        obj_eval = obj.evaluated_get(depsgraph) if depsgraph is not None else obj
        if getattr(obj_eval, "data", None) is None or getattr(obj_eval, "type", None) != "MESH":
            return False
        mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    except Exception:
        return False
    try:
        if mesh is None:
            return False
        import zlib

        vertices = mesh.vertices
        attributes = getattr(mesh, "attributes", None)
        positions = np.empty(len(vertices) * 3, dtype=np.float32)
        position_attribute = attributes.get("position") if attributes is not None else None
        if position_attribute is not None:
            position_attribute.data.foreach_get("vector", positions)
        else:
            vertices.foreach_get("co", positions)
        # Every position, checksummed (crc32 + adler32: 0.09 s for SvAT Body_Main's 20.7 M
        # vertices; blake2b over the same bytes cost 0.6 s). Topology by its counts only:
        # the corner->vertex array is 2.5 s through RNA on the same mesh, and an edit that
        # rewires faces while keeping every vertex, edge, face and corner count AND every
        # position unchanged is not something a sculpt or a remesh produces.
        raw = memoryview(positions).cast("B")
        counts = (
            len(vertices),
            mesh_read.element_count(mesh, "edges"),
            mesh_read.element_count(mesh, "polygons"),
            mesh_read.element_count(mesh, "loops"),
        )
        digest.update(repr((counts, zlib.crc32(raw), zlib.adler32(raw))).encode("ascii"))
        del raw, positions
        if corner_normals:
            # The cage leans along the low's corner normals: sharp edges or custom normals
            # edited with every position unchanged are a different fit (lows are small).
            normals = np.empty(counts[3] * 3, dtype=np.float32)
            corner_normal_data = getattr(mesh, "corner_normals", None)
            if corner_normal_data is not None:
                corner_normal_data.foreach_get("vector", normals)
            else:
                mesh.loops.foreach_get("normal", normals)
            digest.update(repr(("normals", zlib.crc32(memoryview(normals).cast("B")))).encode("ascii"))
            del normals
        digest.update(repr(_matrix_signature(obj_eval.matrix_world)).encode("utf-8"))
        return True
    except Exception:
        return False
    finally:
        try:
            obj_eval.to_mesh_clear()
        except Exception:
            pass


# Shared-high fit scope. Many bake groups can share one high (a customer's 40 groups on one
# 3.5 M-triangle high): every group's fit re-digested the high (to_mesh + crc) and re-captured
# and re-transformed its world vertices, 3 of the 5 seconds the 40 fits took. While a scope is
# open (the Distance fit queue opens one and closes it when it drains) the digest prefix and
# the world vertex array are kept per high set. The key carries every high's full object
# signature including its depsgraph update stamp, so an edit between two fits is a different
# key and measured again, exactly as the per-fit content digest would have caught it. The
# cache is bounded by bytes and dropped when the scope closes. A high set is only held from
# its SECOND group on (``warm``), so a project whose groups each have their own high (a
# customer's 71-group gun) holds nothing extra while it fits. The budget counts each held
# world array twice: its uploaded GPU texture is 16 bytes per vertex against 12.
_SHARE_MAX_BYTES = 384 * 1024 * 1024
_SHARE_MAX_SEEN = 4096
_SHARE: dict | None = None


def begin_shared_fit() -> None:
    """Open the shared-high scope (idempotent)."""
    global _SHARE
    if _SHARE is None:
        _SHARE = {"entries": {}, "bytes": 0, "seen": set()}


def end_shared_fit() -> None:
    """Close the scope and free everything it held."""
    global _SHARE
    _SHARE = None


def shared_fit_active() -> bool:
    return _SHARE is not None


def _share_key(highs):
    """Identity + content-stamp key of a high set; None outside a scope or when a signature fails."""
    if _SHARE is None:
        return None
    try:
        from .overlay_keys import object_signature

        return tuple(object_signature(high) for high in highs)
    except Exception:
        return None


def _share_touch(highs) -> None:
    """Note one more group fitting against ``highs``; its second turns the entry warm."""
    key = _share_key(highs)
    if key is None:
        return
    seen = _SHARE["seen"]
    if key in seen:
        entry = _share_entry(key)
        if entry is not None:
            entry["warm"] = True
    elif len(seen) < _SHARE_MAX_SEEN:
        seen.add(key)


def _share_entry(key):
    if _SHARE is None or key is None:
        return None
    entries = _SHARE["entries"]
    entry = entries.pop(key, None)
    if entry is None:
        entry = {"digests": {}, "world": None, "bytes": 0, "warm": False}
    entries[key] = entry  # most recently used last
    return entry


def _share_store_world(key, entry, world) -> None:
    if _SHARE is None or entry is None or world is None or not entry["warm"]:
        return
    size = int(getattr(world, "nbytes", 0)) * 2
    if size > _SHARE_MAX_BYTES:
        return
    entries = _SHARE["entries"]
    while entries and _SHARE["bytes"] + size > _SHARE_MAX_BYTES:
        oldest = next(iter(entries))
        if oldest == key:
            break
        evicted = entries.pop(oldest)
        _SHARE["bytes"] -= int(evicted["bytes"])
    entry["world"] = world
    entry["bytes"] = size
    _SHARE["bytes"] += size


def _shared_gpu_cache(highs):
    """Dict the GPU pass keeps the high's uploaded texture in; None outside a scope."""
    entry = _share_entry(_share_key(highs))
    if entry is None or not entry["warm"] or entry["world"] is None:
        return None
    return entry.setdefault("gpu", {})


def _shared_high_world(highs, depsgraph):
    """The highs' world-space vertices (fit capture), captured once per high set in a scope."""
    from . import cage as _cage

    key = _share_key(highs)
    entry = _share_entry(key)
    if entry is not None and entry["world"] is not None:
        return entry["world"]
    sources = [_cage.capture_high_mesh_fit_source_data(obj, depsgraph) for obj in highs]
    world = _cage._high_world_vertices_from_source_data(
        [source for source in sources if source is not None], 33_000_000
    )
    del sources
    if world is not None and world.shape[0]:
        _share_store_world(key, entry, world)
    return world


def _persistent_group_keys(lows, highs, depsgraph) -> list:
    """One content key per low against ``highs`` (None where a digest could not be taken)."""
    import hashlib

    high_digest = hashlib.blake2b(digest_size=20)
    high_digest.update(b"cage_offset_estimate_v1|highs")
    for high in highs:
        if not _mesh_content_digest(high, depsgraph, high_digest):
            return [None] * len(lows)
    high_hex = high_digest.hexdigest()
    keys = []
    for low in lows:
        low_digest = hashlib.blake2b(digest_size=20)
        low_digest.update(b"cage_offset_estimate_v1|low|" + high_hex.encode("ascii"))
        keys.append(low_digest.hexdigest() if _mesh_content_digest(low, depsgraph, low_digest) else None)
    return keys


def _persistent_reach_key(lows, highs, depsgraph, smooth_normals) -> str | None:
    """One content key for a whole group's reach estimate (see estimate_group_reach)."""
    import hashlib

    smooth_normals = bool(smooth_normals)
    entry = _share_entry(_share_key(highs))
    prefix = entry["digests"].get(smooth_normals) if entry is not None else None
    if prefix is not None:
        digest = prefix.copy()
    else:
        digest = hashlib.blake2b(digest_size=20)
        digest.update(repr(("cage_offset_reach_v2", smooth_normals)).encode("ascii"))
        for high in highs:
            if not _mesh_content_digest(high, depsgraph, digest):
                return None
        digest.update(b"|lows")
        if entry is not None:
            entry["digests"][smooth_normals] = digest.copy()
    for low in lows:
        if not _mesh_content_digest(low, depsgraph, digest, corner_normals=True):
            return None
    return digest.hexdigest()


def _matrix_signature(matrix) -> tuple:
    if matrix is None:
        return ()
    try:
        return tuple(round(float(value), 6) for row in matrix for value in row)
    except Exception:
        return ()


def _low_object_signature(low_object) -> tuple | None:
    """Cheap identity + shape signature for the low-mesh half of the estimate key.

    Pointers and counts catch re-creation and topology edits, the world matrix
    catches transforms, the bound box catches deformation, and the modifier stack
    catches evaluated-shape changes that leave the base mesh alone.
    """
    try:
        from .modifier_signature import modifier_stack_signature

        data = getattr(low_object, "data", None)
        bound_box = getattr(low_object, "bound_box", None)
        bounds = ()
        if bound_box is not None:
            bounds = tuple(
                tuple(round(float(component), 6) for component in corner[:3]) for corner in bound_box
            )
        return (
            int(low_object.as_pointer()) if hasattr(low_object, "as_pointer") else id(low_object),
            int(data.as_pointer()) if data is not None and hasattr(data, "as_pointer") else 0,
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "polygons"),
            bool(getattr(data, "is_editmode", False)) if data is not None else False,
            _matrix_signature(getattr(low_object, "matrix_world", None)),
            bounds,
            modifier_stack_signature(low_object),
        )
    except Exception:
        return None


class CageOffsetEstimator:
    """Estimates a scalar cage offset for Distance-mode cage generation.

    The estimate is the minimum uniform offset needed so that the cage (every
    low-poly vertex pushed outward along its normal by *offset*) fully envelops
    the high-poly surface.

    Two strategies are tried in order:
    1. Surface — per-vertex nearest-distance queries against the high-mesh
       surface index (one ``BVHTree.FromObject`` per high mesh, memoized in
       ``cage.py`` and shared with the Cage Check overlay).  Uses the
       area-weighted 99th-percentile clearance so a single outlier vertex
       (spike, degenerate normal) cannot inflate the result.
    2. Bounds — conservative fallback using a fraction of the larger of the
       low/high mesh diagonals.  Simple and never wildly wrong.

    Surface results are cached per (low shape, high-set shape): the bake launch
    resolves an automatic Height range through this estimator for every
    cage-mesh group, so repeat launches on an unchanged scene must cost nothing.
    """

    PADDING_SCALE: float = 0.10
    MINIMUM_PADDING: float = 0.001
    MINIMUM_OFFSET: float = constants.DEFAULT_CAGE_OFFSET
    PERCENTILE: float = 0.99
    BOUNDS_DIAGONAL_SCALE: float = 0.05

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def estimate(
        self,
        low_object,
        high_objects,
        depsgraph=None,
        *,
        low_bounds=None,
        high_bounds=None,
        surface_index=None,
    ) -> float | None:
        """Return the best available offset estimate.

        *low_object* and *high_objects* are Blender mesh objects used for the
        surface pass.  *surface_index* is an optional prebuilt
        :func:`cage.build_high_surface_index` result so callers that estimate
        several lows against one high set (the bake launch) build it once.
        *low_bounds* / *high_bounds* are each a ``(minimum, maximum)`` tuple of
        world-space AABB corners, used only for the bounds fallback.

        Returns ``None`` if insufficient geometry is available.
        """
        if not high_objects:
            return None

        if depsgraph is not None:
            result = self._cached_surface_estimate(
                low_object, list(high_objects), depsgraph, surface_index=surface_index
            )
            if result is not None:
                return result

        if low_bounds is None:
            return None
        return self._bounds_estimate(low_bounds, high_bounds)

    # ---------------------------------------------------------------------------
    # Surface estimation (primary)
    # ---------------------------------------------------------------------------

    @staticmethod
    def _estimate_cache_key(low_object, high_objects):
        from . import cage as _cage

        high_key = _cage.high_surface_index_key(high_objects)
        low_key = _low_object_signature(low_object)
        if high_key is None or low_key is None:
            return None
        return ("cage_offset_estimate_v1", low_key, high_key)

    @staticmethod
    def _store_estimate(cache_key, result) -> None:
        if cache_key is None or result is None:
            return
        _ESTIMATE_CACHE[cache_key] = result
        _ESTIMATE_CACHE_ORDER.append(cache_key)
        while len(_ESTIMATE_CACHE_ORDER) > _ESTIMATE_CACHE_MAX:
            evicted = _ESTIMATE_CACHE_ORDER.pop(0)
            _ESTIMATE_CACHE.pop(evicted, None)

    def _cached_surface_estimate(self, low_object, high_objects, depsgraph, *, surface_index=None) -> float | None:
        cache_key = self._estimate_cache_key(low_object, high_objects)
        if cache_key is not None:
            cached = _ESTIMATE_CACHE.get(cache_key)
            if cached is not None:
                return cached

        result = self._surface_estimate(low_object, high_objects, depsgraph, surface_index=surface_index)
        self._store_estimate(cache_key, result)
        return result

    def estimate_group(self, low_objects, high_objects, depsgraph) -> list:
        """:meth:`estimate` for every low of one group against the same highs, one result each.

        Same values as calling ``estimate(low, highs, depsgraph)`` per low, but built for the
        bake launch on heavy highs (2026-09-28, SvAT 87 M triangles):

        - lows already in the estimate cache cost nothing, and when every low is cached no
          BVH is built at all (the launch used to build the whole surface index first and
          only then ask the cache: ~2 min and ~12 GB on SvAT for a number it already had);
        - an index the Cage Check overlay memoized is reused as before;
        - otherwise the highs are visited ONE ``BVHTree`` at a time, keeping each sample's
          running minimum distance. The nearest surface over all highs is the minimum over
          the per-high nearest distances, so the result is identical to querying the whole
          index, with only the largest single tree alive instead of every tree at once.
        """
        from . import cage as _cage

        lows = list(low_objects or ())
        highs = [obj for obj in (high_objects or ()) if obj is not None]
        results: list = [None] * len(lows)
        if not lows or not highs:
            return results

        keys = [self._estimate_cache_key(low, highs) for low in lows]
        missing = []
        for index, key in enumerate(keys):
            cached = _ESTIMATE_CACHE.get(key) if key is not None else None
            if cached is not None:
                results[index] = cached
            else:
                missing.append(index)
        if not missing:
            return results

        persistent_keys = _persistent_group_keys([lows[index] for index in missing], highs, depsgraph)
        persistent = _load_persistent_estimates() if any(persistent_keys) else {}
        still_missing = []
        for index, persistent_key in zip(missing, persistent_keys):
            value = persistent.get(persistent_key) if persistent_key is not None else None
            if isinstance(value, (int, float)):
                self._store_estimate(keys[index], float(value))
                results[index] = float(value)
            else:
                still_missing.append(index)
        persistent_key_by_index = dict(zip(missing, persistent_keys))
        missing = still_missing
        if not missing:
            return results
        try:
            return self._measure_missing(lows, highs, depsgraph, keys, missing, results)
        finally:
            _store_persistent_estimates({
                persistent_key_by_index[index]: results[index]
                for index in missing
                if persistent_key_by_index.get(index) is not None and results[index] is not None
            })

    # ---------------------------------------------------------------------------
    # Reach estimation (GPU, Distance fit)
    # ---------------------------------------------------------------------------

    #: Share of the high's vertices the fitted offset must reach: 1 in 10 000 may stay out,
    #: so a few stray vertices cannot blow the whole group's cage out.
    REACH_QUANTILE: float = 0.9999

    def estimate_group_reach(self, low_objects, high_objects, depsgraph, *, smooth_normals=True):
        """The Distance offset whose cage reaches the high, measured from the high's side.

        Every high vertex finds its nearest low triangle on the GPU (the Automatic fit's
        compute pass) and how far out along the cage normal the cage must sit to reach it.
        The nearest-distance estimate measures from the low's side instead, so detail
        standing proud of the low between its samples went unseen (a customer's gun: two
        parts needing 0.087 and 0.0275 sat on the 0.02 default), and it built a BVH per high
        (22 to 38 s on that gun against 2 to 4 s here). Only the outward side is measured: the
        rays reach at least 5% of the low's size behind it whatever the offset, and a high's
        hidden inner parts sit behind its own outer surface, which the ray hits first.

        Returns ``None`` when the GPU pass is unavailable (background Blender) so the caller
        falls back to the surface estimate.
        """
        import numpy as np

        from . import cage as _cage
        from . import overlay_cage_check_gpu as _cc

        lows = [obj for obj in (low_objects or ()) if obj is not None]
        highs = [obj for obj in (high_objects or ()) if obj is not None]
        if not lows or not highs or depsgraph is None:
            return None
        smooth_normals = bool(smooth_normals)
        if _SHARE is not None:
            _share_touch(highs)
        low_keys = [_low_object_signature(low) for low in lows]
        high_key = _cage.high_surface_index_key(highs)
        cache_key = None
        if high_key is not None and all(key is not None for key in low_keys):
            cache_key = ("cage_offset_reach_v2", tuple(low_keys), high_key, smooth_normals)
            cached = _ESTIMATE_CACHE.get(cache_key)
            if cached is not None:
                return cached
        persistent_key = _persistent_reach_key(lows, highs, depsgraph, smooth_normals)
        if persistent_key is not None:
            value = _load_persistent_estimates().get(persistent_key)
            if isinstance(value, (int, float)):
                self._store_estimate(cache_key, float(value))
                return float(value)

        positions, normals = [], []
        for low in lows:
            try:
                triangles = _cage.capture_cage_source_triangles(
                    low, depsgraph, smooth_normals=smooth_normals, uv_layer_name=None, uv_layer_required=False
                ) or []
            except Exception:
                return None
            if not triangles:
                continue
            low_positions = np.array(
                [[tuple(corner.source_position) for corner in triangle.corners] for triangle in triangles],
                dtype=np.float32,
            )
            positions.append(low_positions)
            normals.append(np.array(
                [[tuple(corner.normal) for corner in triangle.corners] for triangle in triangles],
                dtype=np.float32,
            ))
        high_world = _shared_high_world(highs, depsgraph)
        if not positions or high_world is None or not high_world.shape[0]:
            return None
        positions = np.concatenate(positions)
        normals = np.concatenate(normals)
        if smooth_normals:
            # The direction the bake projects along (see projection_field_normals), not the
            # add-on's per-loop average: the reach is measured along the ray that must clear it.
            normals = projection_field_normals(positions, normals)
        gpu_cache = _shared_gpu_cache(highs)
        if gpu_cache is None:
            result = _cc.compute_coverage_nearest_gpu(positions, normals, high_world)
        else:
            result = _cc.compute_coverage_nearest_gpu(positions, normals, high_world, high_cache=gpu_cache)
        if result is None:
            # No GPU pass (background Blender, no compute shaders): the same measurement on the
            # CPU, high side, over as many vertices as the budget allows (a stride past it).
            result = _reach_nearest_cpu(positions, normals, high_world)
        if result is None:
            return None
        required, tri_index = result
        valid = (tri_index >= 0) & (tri_index < positions.shape[0])
        if not valid.any():
            return None
        # The farthest vertex decides (a cage has to enclose the high, small raised detail
        # included: a percentile left a 0.04 boss out of a 0.0403 offset), short of a stray
        # part far from the low (a quarter of the low's own size is the sanity limit).
        flat = positions.reshape(-1, 3)
        diagonal = float(np.linalg.norm(flat.max(axis=0) - flat.min(axis=0)))
        limit = max(0.25 * diagonal, float(self.MINIMUM_OFFSET))
        valid_index = np.nonzero(valid)[0]
        measured = required[valid_index]
        sane = measured <= limit
        if sane.any():
            valid_index, measured = valid_index[sane], measured[sane]
        representative = float(measured.max())
        if smooth_normals:
            # Widened to the face-normal clearance (face_clearance_from_reach): at most 2x, so a
            # vertex under half the farthest reach cannot decide; only the rest is converted.
            near = measured >= 0.5 * representative
            candidates = valid_index[near]
            widened = face_clearance_from_reach(
                required[candidates], tri_index[candidates], positions, normals, high_world[candidates]
            )
            representative = max(representative, float(widened.max()))
        estimate = float(self.MINIMUM_OFFSET)
        if representative > 0.0:
            padding = max(float(self.MINIMUM_PADDING), representative * float(self.PADDING_SCALE))
            estimate = max(estimate, representative + padding)
        self._store_estimate(cache_key, estimate)
        if persistent_key is not None:
            _store_persistent_estimates({persistent_key: estimate})
        return estimate

    def _measure_missing(self, lows, highs, depsgraph, keys, missing, results) -> list:
        from . import cage as _cage

        memo_key = _cage.high_surface_index_key(tuple(highs))
        memoized = _cage._HIGH_BVH_CACHE.get(memo_key) if memo_key is not None else None
        if memoized is not None:
            for index in missing:
                result = self._surface_estimate(lows[index], highs, depsgraph, surface_index=memoized)
                self._store_estimate(keys[index], result)
                results[index] = result
            return results

        samples = {}
        for index in missing:
            sampled = self._sample_low(lows[index], depsgraph)
            if sampled is not None:
                points, weights = sampled
                samples[index] = (points, weights, [None] * len(points))

        trees_built = 0
        for obj, tree, matrix, matrix_inv in _cage.iter_high_surface_trees(highs, depsgraph):
            trees_built += 1
            for points, _weights, best in samples.values():
                for i, point in enumerate(points):
                    try:
                        near = tree.find_nearest(matrix_inv @ point)
                    except Exception:
                        continue
                    if near is None or near[0] is None:
                        continue
                    distance = ((matrix @ near[0]) - point).length
                    if best[i] is None or distance < best[i]:
                        best[i] = distance
            del tree
        if trees_built == 0:
            return results

        for index, (points, weights, best) in samples.items():
            clearances: list[float] = []
            kept_weights: list[float] = []
            for distance, weight in zip(best, weights):
                if distance is None or distance <= 0.0:
                    continue
                clearances.append(float(distance))
                kept_weights.append(weight)
            result = self._finalize_estimate(clearances, kept_weights)
            self._store_estimate(keys[index], result)
            results[index] = result
        return results

    def _sample_low(self, low_object, depsgraph):
        """World-space sample points + weights of one low (see :meth:`_sample_points`)."""
        obj_eval = None
        try:
            obj_eval = low_object.evaluated_get(depsgraph)
            mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
            if mesh is None:
                return None
            return self._sample_points(mesh, obj_eval.matrix_world)
        except Exception:
            return None
        finally:
            if obj_eval is not None:
                try:
                    obj_eval.to_mesh_clear()
                except Exception:
                    pass

    def _surface_estimate(self, low_object, high_objects, depsgraph, *, surface_index=None) -> float | None:
        """Nearest-surface per-vertex clearances; aggregate via area-weighted percentile."""
        from . import cage as _cage

        if surface_index is None:
            surface_index = _cage.get_or_build_high_surface_index(high_objects, depsgraph)
        if not surface_index:
            return None

        obj_eval = None
        try:
            obj_eval = low_object.evaluated_get(depsgraph)
            mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
            if mesh is None:
                return None
            matrix = obj_eval.matrix_world
            clearances, weights = self._collect_clearances(mesh, matrix, surface_index)
        except Exception:
            return None
        finally:
            if obj_eval is not None:
                try:
                    obj_eval.to_mesh_clear()
                except Exception:
                    pass

        return self._finalize_estimate(clearances, weights)

    def _finalize_estimate(self, clearances, weights) -> float:
        if not clearances:
            return float(self.MINIMUM_OFFSET)

        representative = self._weighted_percentile(clearances, weights, self.PERCENTILE)
        if representative <= 0.0:
            return float(self.MINIMUM_OFFSET)

        padding = max(float(self.MINIMUM_PADDING), representative * float(self.PADDING_SCALE))
        return max(float(self.MINIMUM_OFFSET), representative + padding)

    def _collect_clearances(self, mesh, matrix, surface_index) -> tuple[list[float], list[float]]:
        """Return (deviations, area_weights) for each low-poly vertex AND face centroid.

        Each value is the distance from the sample point to the *nearest*
        high-poly surface — i.e. the local low↔high envelope gap.  A vertex is
        weighted by the total area of the faces touching it, a centroid by its
        own face's area, so high-detail regions count more than isolated verts.

        Centroids matter on a coarse low: the sculpt bulges between the vertices
        of a big flat face, and the vertices alone never see it. On the donated
        axe (2026-09-15) a 1311-vertex part measured a 99th-percentile vertex
        clearance of 0.013 (so the 0.02 floor) while its face centroids sat up
        to 0.10 inside the sculpt, and a quarter of its texels missed.

        Nearest-surface distance is used deliberately in place of an outward ray
        to the *outermost* surface.  An outward ray spans internal cavities (eye
        sockets, cranial voids, an open jaw) and jumps across the empty gap to a
        different part of a multi-mesh group (upper vs. lower teeth) — both
        inflate the estimate to roughly the object's own size.  The nearest
        surface is always the locally corresponding one, so the estimate stays a
        true clearance regardless of concavity or multi-part groups.
        """
        from . import cage as _cage

        points, point_weights = self._sample_points(mesh, matrix)
        clearances: list[float] = []
        weights: list[float] = []
        nearest_surface_distance = _cage.nearest_surface_distance
        for point, weight in zip(points, point_weights):
            distance = nearest_surface_distance(surface_index, point)
            if distance is None or distance <= 0.0:
                continue
            clearances.append(float(distance))
            weights.append(weight)
        return clearances, weights

    @staticmethod
    def _sample_points(mesh, matrix) -> tuple[list, list[float]]:
        """World-space sample points of a low (every vertex, then every face centroid)
        and their area weights, in the order :meth:`_collect_clearances` measures them."""
        n_verts = len(mesh.vertices)
        if n_verts <= 0:
            return [], []

        area_weight: list[float] = [0.0] * n_verts

        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            face_area = tri.area
            for vi in tri.vertices:
                area_weight[vi] += face_area

        points = []
        weights: list[float] = []
        for v in mesh.vertices:
            points.append(matrix @ v.co)
            weights.append(max(area_weight[v.index], 1e-12))

        vertices = mesh.vertices
        for tri in mesh.loop_triangles:
            a, b, c = tri.vertices
            centroid = (vertices[a].co + vertices[b].co + vertices[c].co) / 3.0
            points.append(matrix @ centroid)
            weights.append(max(float(tri.area), 1e-12))
        return points, weights

    # ---------------------------------------------------------------------------
    # Bounds fallback (secondary)
    # ---------------------------------------------------------------------------

    def _bounds_estimate(self, low_bounds, high_bounds=None) -> float:
        """Conservative offset from mesh diagonal.

        Uses the larger of the low/high mesh diagonals scaled by
        BOUNDS_DIAGONAL_SCALE.  Including the high-mesh diagonal guards against
        cases where the high mesh is substantially larger than the low mesh.
        """
        low_minimum, low_maximum = low_bounds
        low_diagonal = (
            (float(low_maximum[0]) - float(low_minimum[0])) ** 2
            + (float(low_maximum[1]) - float(low_minimum[1])) ** 2
            + (float(low_maximum[2]) - float(low_minimum[2])) ** 2
        ) ** 0.5

        high_diagonal = 0.0
        if high_bounds is not None:
            high_minimum, high_maximum = high_bounds
            high_diagonal = (
                (float(high_maximum[0]) - float(high_minimum[0])) ** 2
                + (float(high_maximum[1]) - float(high_minimum[1])) ** 2
                + (float(high_maximum[2]) - float(high_minimum[2])) ** 2
            ) ** 0.5

        diagonal = max(low_diagonal, high_diagonal)
        estimate = diagonal * float(self.BOUNDS_DIAGONAL_SCALE)
        return max(float(self.MINIMUM_OFFSET), estimate)

    # ---------------------------------------------------------------------------
    # Statistics helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _weighted_percentile(values: list[float], weights: list[float], p: float) -> float:
        """Return the weighted p-th percentile (0–1) of *values*.

        Uses the standard weighted-CDF interpolation.  Falls back to the
        unweighted sorted percentile if weights are degenerate.
        """
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]

        paired = sorted(zip(values, weights), key=lambda x: x[0])
        total_weight = sum(w for _, w in paired)
        if total_weight <= 0.0:
            idx = max(0, min(len(values) - 1, int(p * len(values))))
            return sorted(values)[idx]

        target = p * total_weight
        cumulative = 0.0
        for v, w in paired:
            cumulative += w
            if cumulative >= target:
                return v
        return paired[-1][0]


# ---------------------------------------------------------------------------
# Smooth Cage projection field (mirrors the backend's welded normals, Toolbag's smooth cage)
# ---------------------------------------------------------------------------

def projection_field_normals(corner_positions, corner_normals, digits: int = 6):
    """The averaged projection direction at every triangle corner, as the backend packs it for
    Smooth Cage on: vertices welded by position, unit geometric face normals weighted by the
    corner angle (independent of how a quad is triangulated), pushed back within 80 degrees of
    every incident face (8 passes) and out from behind any of them. ``corner_positions`` and
    ``corner_normals`` are ``(T, 3, 3)`` float arrays (the normals only orient each face).
    Returns ``(T, 3, 3)`` float32 unit directions; a corner whose faces cancel keeps its own
    normal."""
    import numpy as np

    from . import cage_soup

    positions = np.asarray(corner_positions, dtype=np.float64).reshape(-1, 3, 3)
    own = np.asarray(corner_normals, dtype=np.float64).reshape(-1, 3, 3)
    count = positions.shape[0]
    if count == 0:
        return own.astype(np.float32)
    flat_positions = positions.reshape(-1, 3)
    keys = np.rint(flat_positions * (10.0 ** digits)).astype(np.int64)
    _first, group = cage_soup.unique_rows(keys)
    group_count = int(group.max()) + 1
    triangles = np.arange(count * 3, dtype=np.int64).reshape(count, 3)
    direction, ok = cage_soup.smooth_cage_field(flat_positions, triangles, own.sum(1), group, group_count)
    result = direction[group].reshape(count, 3, 3)
    fallback = ~ok[group].reshape(count, 3)
    result = np.where(fallback[..., None], own, result)
    return result.astype(np.float32)


def face_clearance_from_reach(required, tri_index, corner_positions, corner_normals, high_points):
    """Convert the reach measured along the averaged direction into the face-normal clearance
    the Distance offset stands for. The bake raises the origin of a hard-edge triangle by
    1 / cos(lean) (capped at 2), so an offset d clears a detail ``d`` above the face: a reach
    ``r`` along a direction tilted ``theta`` off its face needs ``d = r / cos(theta)``.
    The tilt is the widest of the nearest triangle's corners."""
    import numpy as np

    positions = np.asarray(corner_positions, dtype=np.float64).reshape(-1, 3, 3)
    normals = np.asarray(corner_normals, dtype=np.float64).reshape(-1, 3, 3)
    cross = np.cross(positions[:, 1] - positions[:, 0], positions[:, 2] - positions[:, 0])
    length = np.sqrt((cross * cross).sum(1))
    face = cross / np.where(length > 1.0e-20, length, 1.0)[:, None]
    flip = (face * normals.sum(1)).sum(1) < 0.0
    face = np.where(flip[:, None], -face, face)
    corner_cos = np.abs((normals * face[:, None, :]).sum(2))
    worst = np.clip(corner_cos.min(1), 0.5, 1.0)
    valid = (tri_index >= 0) & (tri_index < positions.shape[0])
    gather = np.where(valid, tri_index, 0)
    reach = np.where(valid, np.asarray(required, dtype=np.float64), 0.0)
    # Never more than the point's height above the nearest face's plane: a vertex beside the
    # low's silhouette (a part overhanging an edge) is far along the tilted direction but only
    # a little above the face, and the old reach already covers it.
    points = np.asarray(high_points, dtype=np.float64).reshape(-1, 3)
    plane_height = ((points - positions[gather, 0]) * face[gather]).sum(1)
    plane_height = np.abs(plane_height)
    widened = np.minimum(reach / worst[gather], plane_height)
    return np.where(valid, np.maximum(reach, widened), 0.0)


_CPU_REACH_MAX_SAMPLES = 400_000


def _reach_nearest_cpu(corner_positions, corner_normals, high_world):
    """CPU twin of ``overlay_cage_check_gpu.compute_coverage_nearest_gpu``: for every high vertex
    the nearest low triangle and the reach along the interpolated projection direction.
    Returns ``(required, tri_index)`` or ``None`` (no vertices / no tree)."""
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    positions = np.asarray(corner_positions, dtype=np.float64).reshape(-1, 3, 3)
    normals = np.asarray(corner_normals, dtype=np.float64).reshape(-1, 3, 3)
    triangle_count = positions.shape[0]
    points = np.asarray(high_world, dtype=np.float64).reshape(-1, 3)
    if triangle_count == 0 or points.shape[0] == 0:
        return None
    try:
        tree = BVHTree.FromPolygons(
            positions.reshape(-1, 3).tolist(),
            [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(triangle_count)],
            all_triangles=True,
        )
    except Exception:
        return None
    step = int(points.shape[0] // _CPU_REACH_MAX_SAMPLES) + 1
    sampled = points[::step]
    count = sampled.shape[0]
    location = np.zeros((count, 3))
    tri = np.full(count, -1, dtype=np.int64)
    find_nearest = tree.find_nearest
    for i in range(count):
        row = sampled[i]
        hit = find_nearest(Vector((float(row[0]), float(row[1]), float(row[2]))))
        if hit is None or hit[0] is None or hit[2] is None or not (0 <= hit[2] < triangle_count):
            continue
        location[i] = (hit[0][0], hit[0][1], hit[0][2])
        tri[i] = int(hit[2])
    ok = tri >= 0
    g = np.where(ok, tri, 0)
    a, b, c = positions[g, 0], positions[g, 1], positions[g, 2]
    e0, e1, e2 = b - a, c - a, location - a
    d00, d01, d11 = (e0 * e0).sum(1), (e0 * e1).sum(1), (e1 * e1).sum(1)
    d20, d21 = (e2 * e0).sum(1), (e2 * e1).sum(1)
    denom = d00 * d11 - d01 * d01
    good = np.abs(denom) > 1.0e-20
    safe = np.where(good, denom, 1.0)
    wv = np.where(good, (d11 * d20 - d01 * d21) / safe, 0.0)
    ww = np.where(good, (d00 * d21 - d01 * d20) / safe, 0.0)
    wu = np.where(good, 1.0 - wv - ww, 1.0)
    projected = wu[:, None] * normals[g, 0] + wv[:, None] * normals[g, 1] + ww[:, None] * normals[g, 2]
    scale = np.sqrt((projected * projected).sum(1))
    direction = projected / np.where(scale > 1.0e-12, scale, 1.0)[:, None]
    reach = ((sampled - location) * direction).sum(1) / np.where(scale > 1.0e-12, scale, 1.0)
    reach = np.where(ok & (scale > 1.0e-12), np.maximum(reach, 0.0), 0.0)
    return reach.astype(np.float32), tri.astype(np.int32)
