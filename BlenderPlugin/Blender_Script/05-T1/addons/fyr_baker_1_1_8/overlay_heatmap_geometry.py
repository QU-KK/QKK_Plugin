from __future__ import annotations

import math

from . import cage, constants


def estimate_low_depth_epsilon(
    low_triangle_sets: list[list[cage.TriangleData]],
    *,
    epsilon_min: float,
    epsilon_max: float,
    bounds_factor: float,
    edge_factor: float,
) -> float:
    min_x = math.inf
    min_y = math.inf
    min_z = math.inf
    max_x = -math.inf
    max_y = -math.inf
    max_z = -math.inf
    total_triangles = sum(len(triangles) for triangles in low_triangle_sets)
    if total_triangles <= 0:
        return epsilon_min

    sample_stride = max(1, total_triangles // 512)
    sampled_edge_lengths: list[float] = []
    triangle_index = 0
    for triangles in low_triangle_sets:
        for triangle in triangles:
            points = tuple(corner.source_position for corner in triangle.corners)
            for point in points:
                x = float(point.x)
                y = float(point.y)
                z = float(point.z)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                min_z = min(min_z, z)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                max_z = max(max_z, z)
            if triangle_index % sample_stride == 0:
                for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
                    edge_length = float((points[end_index] - points[start_index]).length)
                    if edge_length > 1.0e-9:
                        sampled_edge_lengths.append(edge_length)
            triangle_index += 1

    if not math.isfinite(min_x):
        return epsilon_min

    bounds_diagonal = math.sqrt(
        (max_x - min_x) * (max_x - min_x)
        + (max_y - min_y) * (max_y - min_y)
        + (max_z - min_z) * (max_z - min_z)
    )
    sampled_edge_lengths.sort()
    median_edge_length = (
        sampled_edge_lengths[len(sampled_edge_lengths) // 2]
        if sampled_edge_lengths
        else 0.0
    )
    epsilon = max(
        bounds_diagonal * bounds_factor,
        median_edge_length * edge_factor,
    )
    return max(epsilon_min, min(epsilon_max, epsilon))


def visible_viewport_triangles(triangles: list[cage.TriangleData], *, role: str):
    if role != constants.OBJECT_ROLE_HIGH:
        return triangles
    return cage.sample_triangles(triangles, constants.VIEWPORT_HIGH_TRIANGLE_BUDGET)
