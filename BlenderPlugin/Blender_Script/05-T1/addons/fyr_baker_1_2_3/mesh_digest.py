"""Mesh-shape digests, shared and deliberately free of ``bpy``.

Two callers need the same answer to "did this geometry move": the live dirty
tracker, which runs per depsgraph tick, and the Rebuild Changed Maps state in
``map_rebuild``, which runs on a button press. ``dirty_tracker`` imports ``bpy``
at module scope and ``map_rebuild`` loads before that is safe, so the digest
lives here where both can reach it and where it can be tested without Blender.

The policy below is the one priced for the live tracker: exact under the vertex
cap, strided above it.
"""

from __future__ import annotations

#: Vertex budget for the exact shape digest. At the cap, foreach_get copies
#: 262144 * 3 float32 = 3 MiB and blake2b hashes it in ~4 ms (measured), the same order
#: as the UV digest the dirty-tracker handler already pays for every low mesh. Every
#: production low and every small high sits far below it, so the common case is exact.
EXACT_SHAPE_DIGEST_MAX_VERTS = 262144

#: Sampled positions for meshes over that cap. The exact path is not an option there: a
#: 41.8M-triangle high is ~20M vertices, so it would move 240 MiB and spend ~295 ms
#: (measured) hashing them on EVERY depsgraph tick of a sculpt stroke. Reading verts[i].co
#: through RNA costs about a microsecond, so 1024 samples is ~1 ms of reads plus ~0.5 ms
#: of hashing.
#:
#: Known limit, priced deliberately: on a mesh above the cap a single moved vertex can
#: still land between samples (~1024/N odds). A sculpt stroke, a boolean, a smooth, or any
#: other edit that moves a contiguous patch cannot -- which is the failure this replaced.
SAMPLED_SHAPE_VERTS = 1024


def mesh_shape_digest_from_vertices(verts, v_count: int) -> str:
    """Digest of ``verts``' coordinates: exact under the cap, strided over it.

    This used to be five FIXED indices (0, n/4, n/2, 3n/4, n-1). Together with counts and
    a bounding box rounded to 4 decimals that meant any edit which kept the counts, stayed
    inside the rounded bounds and missed those five vertices compared EQUAL: sculpt a
    recess into the middle of a high, or nudge one interior vertex of a low, and the live
    session served the previous Normal/AO/Curvature with nothing in the log.
    """
    if verts is None or v_count <= 0:
        return ""

    import hashlib

    if v_count <= EXACT_SHAPE_DIGEST_MAX_VERTS:
        try:
            import numpy as np

            buffer = np.empty(v_count * 3, dtype=np.float32)
            verts.foreach_get("co", buffer)
            return "x" + hashlib.blake2b(buffer, digest_size=8).hexdigest()
        except Exception:
            # No numpy, or a mesh view without foreach_get: fall through to the sampled
            # path rather than lose the coordinate term altogether.
            pass

    stride = max(1, -(-v_count // SAMPLED_SHAPE_VERTS))
    indices = list(range(0, v_count, stride))
    if indices[-1] != v_count - 1:
        indices.append(v_count - 1)

    digest = hashlib.blake2b(digest_size=8)
    for index in indices:
        try:
            co = verts[index].co
            try:
                triple = (co.x, co.y, co.z)
            except AttributeError:
                triple = (co[0], co[1], co[2])
            digest.update(f"{triple[0]:.6g},{triple[1]:.6g},{triple[2]:.6g};".encode("ascii", "replace"))
        except Exception:
            digest.update(b"?;")
    return "s" + digest.hexdigest()


def mesh_shape_digest(obj) -> str:
    """Digest of ``obj``'s mesh vertex coordinates, "" when it has none."""
    data = getattr(obj, "data", None) if obj is not None else None
    verts = getattr(data, "vertices", None)
    if verts is None:
        return ""
    try:
        return mesh_shape_digest_from_vertices(verts, len(verts))
    except Exception:
        return ""
