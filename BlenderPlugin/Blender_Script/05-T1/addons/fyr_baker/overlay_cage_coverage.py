"""Geometry shared by the CPU and GPU cage enclosure checks.

Signs use feature pseudonormals (Baerentzen & Aanaes, 2005), rather than
shading normals, which can point across the wrong side of a sharp edge.
https://www2.imm.dtu.dk/pubdb/edoc/imm3578.pdf
"""
from __future__ import annotations


def shell_pseudonormals(corners, slots, orientation=1.0):
    import numpy as np

    corners = np.asarray(corners, dtype=np.float64)
    edges = np.roll(corners, -1, axis=1) - corners
    cross = np.cross(edges[:, 0], -edges[:, 2])
    lengths = np.linalg.norm(cross, axis=1)
    faces = cross / np.maximum(lengths[:, None], 1.0e-30)
    faces *= np.asarray(orientation).reshape(-1, 1)
    # Weld only within a low slot: independent cages must not share normals.
    keys = np.column_stack((np.repeat(slots, 3), corners.reshape(-1, 3)))
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    ids = inverse.reshape(-1, 3)
    previous = -np.roll(edges, 1, axis=1)
    angles = np.arctan2(np.linalg.norm(np.cross(edges, previous), axis=2),
                        np.sum(edges * previous, axis=2))
    vertices = np.zeros((int(inverse.max()) + 1, 3), dtype=np.float64)
    np.add.at(vertices, inverse, (faces[:, None, :] * angles[:, :, None]).reshape(-1, 3))
    edge_keys = np.sort(np.stack((ids, np.roll(ids, -1, axis=1)), axis=2), axis=2)
    _, edge_inverse = np.unique(edge_keys.reshape(-1, 2), axis=0, return_inverse=True)
    edge_normals = np.zeros((int(edge_inverse.max()) + 1, 3), dtype=np.float64)
    np.add.at(edge_normals, edge_inverse, np.repeat(faces, 3, axis=0))
    return faces, vertices[ids], edge_normals[edge_inverse].reshape(-1, 3, 3)


def signed_shell_distance(delta, weights, face_indices, faces, vertices, edges):
    import numpy as np

    # Edges are AB, BC, CA; corners are A, B, C. Only the nearest feature's
    # normal determines the sign, never a barycentric shading-normal blend.
    near = weights <= 1.0e-5
    normal = faces[face_indices].copy()
    for edge, opposite in enumerate((2, 0, 1)):
        use = near[:, opposite]
        normal[use] = edges[face_indices[use], edge]
    vertex = np.argmax(weights, axis=1)
    use = np.count_nonzero(near, axis=1) >= 2
    normal[use] = vertices[face_indices[use], vertex[use]]
    distance = np.linalg.norm(delta, axis=1)
    return np.where(np.sum(delta * normal, axis=1) <= 0.0, -distance, distance)
