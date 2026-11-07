"""Array form of the cage triangle soup the Automatic cage path builds per low mesh.

The bake's job build captures every low mesh as ``TriangleData`` objects (three
``TriangleCorner`` with mathutils Vectors each), fits the cage against them, offsets
them and serialises them. On a 300-group job that is ~450k corner objects walked in
Python several times. :class:`CageSoup` carries the same float32 values as three flat
arrays instead, and the consumers that know it (the plain coverage fit, the ray-check
job, the offset step, the payload writer) work on the arrays. Everything else still
sees a sequence of ``TriangleData``: iterating or indexing a soup builds the objects
once, from the very same float32 values, so an unaware consumer is slower, never wrong.

Exactness contract (checked against mathutils on real and random data, see
tests/test_cage_soup.py): every value a soup holds is the float32 the object path holds;
the keys (``(object, position rounded to 6 digits)``) and every derived array equal what
``cage_gpu_fit.prepare_arrays`` / ``cage.build_coverage_offsets`` derived from the
objects, because the corner positions are float32 and ``rint(x * 1e6)`` is exact for them.
"""

from __future__ import annotations

import struct

import numpy as np

_F32 = np.float32


def unique_rows(rows):
    """``(first, inverse)`` of ``np.unique(rows, axis=0, return_index=True, return_inverse=True)`` for an
    (n, k) integer array: rows ordered lexicographically, ``first`` the first occurrence of each distinct
    row, ``inverse`` the distinct-row index of every row. A stable lexsort instead of np.unique's structured
    view, which sorts through a generic comparison (3-5x slower on these sizes)."""
    count = rows.shape[0]
    if count == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    order = np.lexsort(rows.T[::-1])
    ordered = rows[order]
    fresh = np.empty(count, dtype=bool)
    fresh[0] = True
    np.any(ordered[1:] != ordered[:-1], axis=1, out=fresh[1:])
    inverse = np.empty(count, dtype=np.int64)
    inverse[order] = np.cumsum(fresh) - 1
    return order[fresh], inverse


SMOOTH_CAGE_MIN_COS = 0.17364818  # cos(80 degrees)


def _entry_rounds(entry_ids, entry_groups):
    """Split entries into rounds: round k holds the k-th entry (in the given order) of every
    group that has one, so a per-group sequential walk runs all groups side by side."""
    order = np.argsort(entry_groups, kind="stable")
    ids = entry_ids[order]
    owners = entry_groups[order]
    position = np.arange(ids.shape[0])
    first = np.empty(ids.shape[0], dtype=bool)
    first[0] = True
    first[1:] = owners[1:] != owners[:-1]
    rank = position - np.maximum.accumulate(np.where(first, position, 0))
    by_rank = np.argsort(rank, kind="stable")
    bounds = np.searchsorted(rank[by_rank], np.arange(int(rank.max()) + 2))
    return [ids[by_rank[bounds[k]:bounds[k + 1]]] for k in range(int(rank.max()) + 1)]


def _unit_rows(vectors):
    norm = np.sqrt(np.einsum("ij,ij->i", vectors, vectors))
    good = norm > 1.0e-12
    return np.where(good[:, None], vectors / np.where(good, norm, 1.0)[:, None], vectors)


import os as _os

# numpy releases the GIL inside its array kernels, so chunks of the per-triangle phase overlap.
_POOL_WORKERS = max(1, min(4, (_os.cpu_count() or 1)))


def _triangle_terms(positions, triangles, orient, span, face, weights, usable):
    """Unit face normals (oriented by ``orient``), corner angles and the usable flag of the
    triangles ``span`` = (lo, hi), written into the output arrays."""
    lo, hi = span
    tri = triangles[lo:hi]
    p0 = positions[tri[:, 0]]
    p1 = positions[tri[:, 1]]
    p2 = positions[tri[:, 2]]
    # Edges once: e0 = p0 -> p1, e1 = p1 -> p2, e2 = p2 -> p0 (the corner angles reuse them).
    e0 = p1 - p0
    e1 = p2 - p1
    e2 = p0 - p2
    cross = np.cross(e0, -e2)
    length = np.sqrt(np.einsum("ij,ij->i", cross, cross))
    ok_face = length > 1.0e-20
    unit = cross / np.where(ok_face, length, 1.0)[:, None]
    flip = np.einsum("ij,ij->i", unit, orient[lo:hi]) < 0.0
    unit[flip] *= -1.0
    face[lo:hi] = unit
    usable[lo:hi] = ok_face
    edges = (e0, e1, e2)
    edge_len = [np.sqrt(np.einsum("ij,ij->i", e, e)) for e in edges]
    # Corner 0 sits between e0 and -e2, corner 1 between e1 and -e0, corner 2 between e2 and -e1.
    for corner in range(3):
        la = edge_len[corner]
        lb = edge_len[(corner + 2) % 3]
        good = ok_face & (la > 1.0e-20) & (lb > 1.0e-20)
        cosine = -np.einsum("ij,ij->i", edges[corner], edges[(corner + 2) % 3]) / np.where(good, la * lb, 1.0)
        weights[lo:hi, corner] = np.where(good, np.arccos(np.clip(cosine, -1.0, 1.0)), 0.0)


def smooth_cage_field(positions, triangles, orient, group, group_count):
    """Toolbag's smooth-cage direction per welded point: the backend's field (master_baker_backend.cpp,
    ``average_normals``) line for line, vectorized.

    ``positions`` (V, 3) vertex positions, ``triangles`` (T, 3) their indices, ``orient`` (T, 3) the
    sum of each triangle's own corner normals (only its sign against the geometric normal is used:
    the face is flipped onto the side the mesh's normals point to), ``group`` (V,) the weld group of
    every vertex and ``group_count`` how many groups there are.

    Per group: the unit geometric face normals of the incident triangles summed with the corner
    angle as weight and normalized; then up to 8 passes in which every incident face (triangle
    order, then corner order) whose dot with the direction is below cos 80 degrees pulls the
    direction toward it by ``face * (cos80 - dot)``, renormalized after each pull like the C++ loop,
    a pass that moves nothing ending the loop; then every face the direction points behind is
    projected out in turn; then normalize. Returns ``(direction (G, 3) float64, ok (G,) bool)``; a
    group whose faces cancel (or with no usable triangle) is not ok and its direction is zero."""
    positions = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    triangles = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    orient = np.asarray(orient, dtype=np.float64).reshape(-1, 3)
    group = np.asarray(group, dtype=np.int64)
    count = triangles.shape[0]
    if count == 0 or group_count == 0:
        return np.zeros((group_count, 3), dtype=np.float64), np.zeros(group_count, dtype=bool)

    face = np.empty((count, 3), dtype=np.float64)
    weights = np.empty((count, 3), dtype=np.float64)
    usable = np.empty(count, dtype=bool)
    chunk = 131072
    spans = [(lo, min(count, lo + chunk)) for lo in range(0, count, chunk)]
    if len(spans) > 1 and _POOL_WORKERS > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=_POOL_WORKERS) as pool:
            list(pool.map(lambda span: _triangle_terms(positions, triangles, orient, span, face, weights, usable), spans))
    else:
        for span in spans:
            _triangle_terms(positions, triangles, orient, span, face, weights, usable)
    all_usable = bool(usable.all())

    # Welded group of every triangle corner; the entries (triangle order, then corner order, the
    # C++ push order) are the flat ids t * 3 + c.
    corner_group = group[triangles]
    total = np.zeros((group_count, 3), dtype=np.float64)
    for corner in range(3):
        for axis in range(3):
            total[:, axis] += np.bincount(
                corner_group[:, corner], weights=face[:, axis] * weights[:, corner], minlength=group_count
            )
    total_len = np.sqrt(np.einsum("ij,ij->i", total, total))
    ok = total_len > 1.0e-12
    direction = np.where(ok[:, None], total / np.where(ok, total_len, 1.0)[:, None], 0.0)
    flat_group = corner_group.reshape(-1)

    def _groups_where(threshold_test):
        """Groups for which some usable incident face makes ``threshold_test(dot)`` true."""
        hit = np.zeros(group_count, dtype=bool)
        for corner in range(3):
            owners = corner_group[:, corner]
            dots = np.einsum("ij,ij->i", direction[owners], face)
            flagged = threshold_test(dots)
            if not all_usable:
                flagged &= usable
            hit[owners[flagged]] = True
        return hit & ok

    def _rounds_for(groups):
        ids = np.flatnonzero(groups[flat_group])
        if not all_usable:
            ids = ids[usable[ids // 3]]
        return ids, _entry_rounds(ids, flat_group[ids])

    # Fix-up. Only a group that starts with a face below the threshold can move at all.
    active = _groups_where(lambda d: d < SMOOTH_CAGE_MIN_COS)
    started_below = bool(active.any())
    if started_below:
        ids_all, rounds = _rounds_for(active)
        round_faces = [face[ids // 3] for ids in rounds]
        round_owners = [flat_group[ids] for ids in rounds]
        for _ in range(8):
            moved = np.zeros(group_count, dtype=bool)
            for f, owners in zip(round_faces, round_owners):
                live = active[owners]
                if not live.all():
                    f = f[live]
                    owners = owners[live]
                if owners.shape[0] == 0:
                    continue
                d = np.einsum("ij,ij->i", direction[owners], f)
                pull = d < SMOOTH_CAGE_MIN_COS
                if pull.any():
                    pulled = owners[pull]
                    direction[pulled] = _unit_rows(direction[pulled] + f[pull] * (SMOOTH_CAGE_MIN_COS - d[pull])[:, None])
                    moved[pulled] = True
            active &= moved
            if not active.any():
                break

    # Cleanup: project out every face the direction still points behind, in turn.
    # A face behind the direction is also below the threshold, so a mesh with no group below the
    # threshold at the start has nothing behind either (and the fix-up only moves toward faces).
    behind = _groups_where(lambda d: d < 0.0) if started_below else None
    if behind is not None and behind.any():
        _ids, rounds = _rounds_for(behind)
        for ids in rounds:
            owners = flat_group[ids]
            f = face[ids // 3]
            d = np.einsum("ij,ij->i", direction[owners], f)
            hit = d < 0.0
            if hit.any():
                direction[owners[hit]] = direction[owners[hit]] - f[hit] * d[hit][:, None]

    norm = np.sqrt(np.einsum("ij,ij->i", direction, direction))
    ok &= norm > 1.0e-12
    direction = np.where(ok[:, None], direction / np.where(ok, norm, 1.0)[:, None], 0.0)
    return direction, ok


class CageSoup:
    """Corner arrays of one or more low meshes' triangles, in triangle order.

    ``positions`` / ``normals`` are ``(3T, 3)`` float32 (world space), ``uvs`` is ``(3T, 2)``
    float32. ``tri_object`` (``(T,)`` int32) indexes ``names`` (an object name per distinct
    object, in order of first appearance). ``source_positions`` is the capture position when
    ``positions`` has been offset (the cage); it is ``positions`` itself for a capture."""

    __slots__ = (
        "names",
        "tri_object",
        "positions",
        "normals",
        "uvs",
        "source_positions",
        "_objects",
        "_prepared",
        "_keys",
        "_key_list",
    )

    def __init__(self, names, tri_object, positions, normals, uvs, source_positions=None):
        self.names = list(names)
        self.tri_object = tri_object
        self.positions = positions
        self.normals = normals
        self.uvs = uvs
        self.source_positions = positions if source_positions is None else source_positions
        self._objects = None
        self._prepared = None
        self._keys = None
        self._key_list = None

    # ---- sequence of TriangleData (compatibility for consumers that do not know soups) ----
    def __len__(self) -> int:
        return int(self.positions.shape[0]) // 3

    def __bool__(self) -> bool:
        return self.positions.shape[0] > 0

    def triangles(self):
        if self._objects is None:
            from mathutils import Vector

            from . import cage

            corner_cls = cage.TriangleCorner
            triangle_cls = cage.TriangleData
            source = self.source_positions.astype(np.float64).tolist()
            same = self.source_positions is self.positions
            position = source if same else self.positions.astype(np.float64).tolist()
            normal = self.normals.astype(np.float64).tolist()
            uv = self.uvs.astype(np.float64).tolist()
            objects = []
            object_ids = self.tri_object.tolist()
            for triangle in range(len(self)):
                corners = []
                for corner in range(triangle * 3, triangle * 3 + 3):
                    source_vector = Vector(source[corner])
                    corners.append(
                        corner_cls(
                            source_position=source_vector,
                            position=source_vector if same else Vector(position[corner]),
                            uv=(uv[corner][0], uv[corner][1]),
                            normal=Vector(normal[corner]),
                        )
                    )
                objects.append(triangle_cls(object_name=self.names[object_ids[triangle]], corners=tuple(corners)))
            self._objects = objects
        return self._objects

    def __iter__(self):
        return iter(self.triangles())

    def __getitem__(self, index):
        return self.triangles()[index]

    # ---- derived arrays ----
    @classmethod
    def concat(cls, soups):
        """One soup of ``soups`` in order (the same list as concatenating their triangles)."""
        soups = [soup for soup in soups if soup is not None and len(soup)]
        if len(soups) == 1:
            return soups[0]
        names: list = []
        ids: dict = {}
        remapped = []
        for soup in soups:
            table = np.empty(len(soup.names), dtype=np.int32)
            for local, name in enumerate(soup.names):
                table[local] = ids.setdefault(name, len(ids))
                if table[local] == len(names):
                    names.append(name)
            remapped.append(table[soup.tri_object])
        if not soups:
            return cls([], np.empty(0, np.int32), np.empty((0, 3), _F32), np.empty((0, 3), _F32), np.empty((0, 2), _F32))
        same = all(soup.source_positions is soup.positions for soup in soups)
        return cls(
            names,
            np.concatenate(remapped),
            np.concatenate([soup.positions for soup in soups]),
            np.concatenate([soup.normals for soup in soups]),
            np.concatenate([soup.uvs for soup in soups]),
            None if same else np.concatenate([soup.source_positions for soup in soups]),
        )

    def key_rows(self):
        """``(3T, 4)`` int64: the rounded source position (x1e6) and the object id of every corner."""
        rows = np.empty((self.source_positions.shape[0], 4), dtype=np.int64)
        rows[:, :3] = np.rint(self.source_positions.astype(np.float64) * 1.0e6).astype(np.int64)
        rows[:, 3] = np.repeat(self.tri_object.astype(np.int64), 3)
        return rows

    def unique_keys(self):
        """``(first, inverse)`` of ``np.unique(key_rows, axis=0)``: the flat corner of the first
        occurrence of each fit key (keys in sorted order) and the key index of every corner."""
        if self._keys is None:
            self._keys = unique_rows(self.key_rows())
        return self._keys

    def key_tuples(self, flat_corners):
        """The offsets-dict key ``(object_name, (x, y, z))`` of each flat corner row, positions
        rounded to 6 digits like ``cage._source_position_group_key``."""
        flat_corners = np.asarray(flat_corners, dtype=np.int64)
        rounded = (
            np.rint(self.source_positions[flat_corners].astype(np.float64) * 1.0e6) / 1.0e6
        ).tolist()
        names = self.names
        object_ids = self.tri_object[flat_corners // 3].tolist()
        return [(names[o], (x, y, z)) for o, (x, y, z) in zip(object_ids, rounded)]

    def sorted_key_tuples(self):
        """``key_tuples`` of the first corner of every fit key, in ``unique_keys`` order."""
        if self._key_list is None:
            self._key_list = self.key_tuples(self.unique_keys()[0])
        return self._key_list

    def coverage_structure(self):
        """What ``cage.build_coverage_offsets`` collects while walking the triangles:
        ``(key_list, low_positions, face_corner_global, corner_normals)``. ``key_list`` holds the fit keys
        in order of first appearance, ``low_positions`` is every corner's source position (C, 3) float64,
        ``face_corner_global`` the key index of each triangle's corners (T, 3) and ``corner_normals`` the
        normal of the first corner of each key (K, 3) float64."""
        first_sorted, inverse = self.unique_keys()
        order = np.argsort(first_sorted, kind="stable")
        rank = np.empty_like(order)
        rank[order] = np.arange(order.shape[0])
        first_flat = first_sorted[order]
        sorted_keys = self.sorted_key_tuples()
        return (
            [sorted_keys[index] for index in order.tolist()],
            self.source_positions.astype(np.float64),
            rank[inverse].reshape(-1, 3),
            self.normals.astype(np.float64)[first_flat],
        )

    def prepare_arrays(self):
        """What ``cage_gpu_fit.prepare_arrays`` derives from the objects (same arrays)."""
        if self._prepared is None:
            count = len(self)
            first, inverse = self.unique_keys()
            self._prepared = {
                "positions": self.source_positions.astype(np.float64).reshape(count, 3, 3),
                "normals": self.normals.astype(np.float64).reshape(count, 3, 3),
                "tri_object": self.tri_object.astype(np.int64),
                "key_index": inverse.reshape(count, 3),
                "first": first,
                "key_count": int(first.shape[0]),
                "object_names": list(self.names),
            }
        return self._prepared

    def diagonal(self) -> float:
        """``cage._source_triangles_diagonal``: the bounds diagonal of the source positions."""
        if not len(self):
            return 0.0
        low = self.source_positions.min(axis=0).tolist()
        high = self.source_positions.max(axis=0).tolist()
        return ((high[0] - low[0]) ** 2 + (high[1] - low[1]) ** 2 + (high[2] - low[2]) ** 2) ** 0.5

    # ---- offsets ----
    def offset(self, distances: dict, *, minimum_offset: float = 0.0) -> "CageSoup":
        """``cage.offset_triangles_with_proximity_fit`` on the arrays: every corner moves along its
        normal by the distance of its fit key (``position = source + normal * float32(distance)``,
        each step rounded to float32 like the mathutils Vector arithmetic)."""
        first, inverse = self.unique_keys()
        minimum = float(minimum_offset)
        keys = self.sorted_key_tuples()
        per_key = np.fromiter(
            (max(minimum, distances.get(key, minimum)) for key in keys), dtype=np.float64, count=len(keys)
        )
        scale = per_key.astype(_F32)[inverse][:, None]
        moved = (self.source_positions + (self.normals * scale).astype(_F32)).astype(_F32)
        return CageSoup(
            self.names, self.tri_object, moved, self.normals, self.uvs, source_positions=self.source_positions
        )

    # ---- payload ----
    def payload(self, header: struct.Struct, magic, reserved) -> bytes:
        """The V2 triangle-soup payload ``mesh_transport.build_triangle_soup_mesh_payload_from_corner_objects``
        builds for this soup's corners (white colour)."""
        count = int(self.positions.shape[0])
        if count == 0 or count % 3:
            raise ValueError("Binary mesh transport only supports triangle soup")
        data = np.empty((count, 11), dtype="<f4")
        data[:, 0:3] = self.positions
        data[:, 3:6] = self.normals
        data[:, 6:8] = self.uvs
        data[:, 8:11] = 1.0
        return header.pack(magic, count // 3, reserved) + data.tobytes()


def is_soup(value) -> bool:
    return isinstance(value, CageSoup)


def all_soups(groups) -> bool:
    groups = [group for group in groups if group]
    return bool(groups) and all(isinstance(group, CageSoup) for group in groups)


def flatten(groups):
    """The non-empty ``groups`` as one soup when all are soups, else as one list of triangles."""
    groups = [group for group in groups if group]
    if groups and all(isinstance(group, CageSoup) for group in groups):
        return CageSoup.concat(groups)
    return [triangle for group in groups for triangle in group]
