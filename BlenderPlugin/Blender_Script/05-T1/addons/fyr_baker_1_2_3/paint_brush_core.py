"""Numpy core of the Paint Offset / Paint Skew brush (no bpy import).

The brush edits *points*: face corners welded by world position across every low mesh of
the bake group, so a stroke crosses UV seams, hard edges and mesh boundaries the way the
artist sees the surface. Values are stored per corner (paint_sampling layers); a dab sets
every corner of a touched point to that point's new value and leaves untouched corners
exactly as they were.

Everything here is plain numpy so it can be tested without Blender; paint_brush.py is the
thin bpy/gpu shell around it.
"""

from __future__ import annotations

import numpy as np

MODE_ADD = "ADD"
MODE_SUBTRACT = "SUBTRACT"
MODE_SMOOTH = "SMOOTH"
MODE_SET = "SET"
MODE_ERASE = "ERASE"
MODES = (MODE_ADD, MODE_SUBTRACT, MODE_SMOOTH, MODE_SET, MODE_ERASE)

FALLOFF_SMOOTH = "SMOOTH"
FALLOFF_SPHERE = "SPHERE"
FALLOFF_ROOT = "ROOT"
FALLOFF_SHARP = "SHARP"
FALLOFF_LINEAR = "LINEAR"
FALLOFF_CONSTANT = "CONSTANT"
FALLOFFS = (FALLOFF_SMOOTH, FALLOFF_SPHERE, FALLOFF_ROOT, FALLOFF_SHARP, FALLOFF_LINEAR, FALLOFF_CONSTANT)

#: Value added per dab at strength 1 in the brush centre. With the default 10% spacing a
#: stroke across the brush lays down ~10 dabs, so one pass moves a value by ~0.5 there.
ADD_RATE = 0.05

#: Paint Offset Add / Subtract: what ONE stroke pass at strength 1 lays down along the
#: centre of the stroke with the Smooth falloff, whatever the Spacing: +1.0 = +100% of
#: the cage offset (Painter / Marmoset feel). See pass_normalized_rate.
PASS_ADD_RATE = 1.0


def pass_normalized_rate(spacing_px: float, radius_px: float, per_pass: float = PASS_ADD_RATE) -> float:
    """Add/Subtract amount per dab so one pass sums to *per_pass* on the stroke's centre line.

    Dabs land *spacing_px* apart, so a point on the centre line collects one dab per
    spacing over the brush diameter: the sum is rate * (radius / spacing) * integral of the
    falloff over [-1, 1], and that integral is 1 for the Smooth curve. A finer Spacing
    lays more, smaller dabs instead of a stronger stroke.
    """
    return float(per_pass) * max(float(spacing_px), 1.0) / max(float(radius_px), 1.0)


def inverted_mode(mode: str) -> str:
    """Ctrl: Add <-> Subtract, Set -> Erase; Smooth and Erase have no opposite."""
    return {MODE_ADD: MODE_SUBTRACT, MODE_SUBTRACT: MODE_ADD, MODE_SET: MODE_ERASE}.get(mode, mode)


def modifier_mode(mode: str, *, shift: bool, ctrl: bool) -> str:
    """The mode a dab uses while modifiers are held, as in Blender's Sculpt and paint
    modes: Shift smooths, Ctrl inverts. Checked on every dab, so pressing or releasing a
    key mid-stroke switches immediately."""
    if shift:
        return MODE_SMOOTH
    if ctrl:
        return inverted_mode(mode)
    return mode


def falloff_weights(distance_norm, preset: str = FALLOFF_SMOOTH, hardness: float = 0.0):
    """Brush weight for a distance normalised to the radius (0 centre, 1 rim, >1 outside).

    *hardness* keeps full strength out to that fraction of the radius, then the preset
    curve runs over the rest, like Blender's brush hardness.
    """
    t = np.asarray(distance_norm, dtype=np.float32)
    hardness = float(min(max(hardness, 0.0), 0.999))
    x = np.clip((t - hardness) / (1.0 - hardness), 0.0, 1.0)
    if preset == FALLOFF_SPHERE:
        weights = np.sqrt(np.maximum(1.0 - x * x, 0.0))
    elif preset == FALLOFF_ROOT:
        weights = 1.0 - np.sqrt(x)
    elif preset == FALLOFF_SHARP:
        weights = (1.0 - x) ** 2
    elif preset == FALLOFF_LINEAR:
        weights = 1.0 - x
    elif preset == FALLOFF_CONSTANT:
        weights = np.ones_like(x)
    else:
        weights = 1.0 - (3.0 * x * x - 2.0 * x * x * x)
    weights = np.where(t <= 1.0, weights, 0.0)
    return weights.astype(np.float32, copy=False)


def weld_corners(corner_positions, tolerance: float):
    """Group corners that share a world position.

    Returns (point_of_corner int32 [N], point_positions float32 [P, 3]).
    """
    positions = np.asarray(corner_positions, dtype=np.float64).reshape(-1, 3)
    if positions.shape[0] == 0:
        return np.empty(0, dtype=np.int32), np.empty((0, 3), dtype=np.float32)
    step = max(float(tolerance), 1.0e-9)
    keys = np.round(positions / step).astype(np.int64)
    _unique, point_of_corner = np.unique(keys, axis=0, return_inverse=True)
    point_of_corner = point_of_corner.reshape(-1).astype(np.int32)
    point_count = int(point_of_corner.max()) + 1
    counts = np.bincount(point_of_corner, minlength=point_count).astype(np.float64)
    point_positions = np.empty((point_count, 3), dtype=np.float64)
    for axis in range(3):
        point_positions[:, axis] = np.bincount(point_of_corner, weights=positions[:, axis], minlength=point_count)
    point_positions /= np.maximum(counts, 1.0)[:, None]
    return point_of_corner, point_positions.astype(np.float32)


def point_adjacency(triangle_points, point_count: int):
    """CSR neighbours of each point from triangle edges. *triangle_points* is [T, 3]."""
    tris = np.asarray(triangle_points, dtype=np.int64).reshape(-1, 3)
    if tris.shape[0] == 0 or point_count <= 0:
        return np.zeros(max(point_count, 0) + 1, dtype=np.int64), np.empty(0, dtype=np.int32)
    a = np.concatenate([tris[:, 0], tris[:, 1], tris[:, 2], tris[:, 1], tris[:, 2], tris[:, 0]])
    b = np.concatenate([tris[:, 1], tris[:, 2], tris[:, 0], tris[:, 0], tris[:, 1], tris[:, 2]])
    keep = a != b
    pairs = np.unique(a[keep] * np.int64(point_count) + b[keep])
    src = pairs // point_count
    dst = (pairs % point_count).astype(np.int32)
    indptr = np.zeros(point_count + 1, dtype=np.int64)
    np.add.at(indptr, src + 1, 1)
    np.cumsum(indptr, out=indptr)
    return indptr, dst


def connected_components(point_count: int, indptr, indices):
    """Label of the connected piece each point belongs to (smallest point index in it)."""
    labels = np.arange(point_count, dtype=np.int64)
    if point_count == 0 or len(indices) == 0:
        return labels
    src = np.repeat(np.arange(point_count, dtype=np.int64), np.diff(indptr))
    dst = np.asarray(indices, dtype=np.int64)
    while True:
        previous = labels
        edge_min = np.minimum(labels[src], labels[dst])
        labels = labels.copy()
        np.minimum.at(labels, src, edge_min)
        np.minimum.at(labels, dst, edge_min)
        # Pointer jumping collapses long chains in a few rounds.
        while True:
            jumped = labels[labels]
            if np.array_equal(jumped, labels):
                break
            labels = jumped
        if np.array_equal(labels, previous):
            return labels


def neighbour_means(values, points, indptr, indices):
    """Mean neighbour value of each of *points* (its own value where it has none)."""
    values = np.asarray(values, dtype=np.float32)
    points = np.asarray(points, dtype=np.int64)
    if points.size == 0:
        return np.empty(0, dtype=np.float32)
    starts = indptr[points]
    counts = (indptr[points + 1] - starts).astype(np.int64)
    total = int(counts.sum())
    if total == 0:
        return values[points].copy()
    owner = np.repeat(np.arange(points.size), counts)
    offsets = np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
    neighbour_values = values[indices[np.repeat(starts, counts) + offsets]]
    sums = np.bincount(owner, weights=neighbour_values, minlength=points.size)
    means = np.where(counts > 0, sums / np.maximum(counts, 1), values[points])
    return means.astype(np.float32)


def points_in_sphere(point_positions, center, radius: float):
    """(indices, distance / radius) of the points within *radius* of *center*."""
    if radius <= 0.0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
    delta = np.asarray(point_positions, dtype=np.float32) - np.asarray(center, dtype=np.float32)
    dist_sq = np.einsum("ij,ij->i", delta, delta)
    inside = np.flatnonzero(dist_sq <= radius * radius)
    return inside, (np.sqrt(dist_sq[inside]) / radius).astype(np.float32)


def facing_mask(point_positions, point_normals, eye, is_perspective: bool, view_direction):
    """True where the point's normal faces the viewer."""
    normals = np.asarray(point_normals, dtype=np.float32)
    if is_perspective:
        to_eye = np.asarray(eye, dtype=np.float32) - np.asarray(point_positions, dtype=np.float32)
    else:
        to_eye = np.broadcast_to(-np.asarray(view_direction, dtype=np.float32), normals.shape)
    return np.einsum("ij,ij->i", normals, to_eye) > 0.0


def apply_dab(
    values,
    points,
    weights,
    mode: str,
    strength: float,
    *,
    lower: float,
    upper: float,
    target: float = 0.0,
    indptr=None,
    indices=None,
    rate: float = ADD_RATE,
):
    """New values for *points* after one dab (does not modify *values*)."""
    values = np.asarray(values, dtype=np.float32)
    points = np.asarray(points, dtype=np.int64)
    current = values[points]
    w = np.clip(np.asarray(weights, dtype=np.float32) * float(strength), 0.0, 1.0)
    if mode == MODE_ADD:
        updated = current + w * float(rate)
    elif mode == MODE_SUBTRACT:
        updated = current - w * float(rate)
    elif mode == MODE_SMOOTH:
        if indptr is None or indices is None:
            return current.copy()
        updated = current + w * (neighbour_means(values, points, indptr, indices) - current)
    elif mode == MODE_SET:
        updated = current + w * (float(target) - current)
    elif mode == MODE_ERASE:
        updated = current - w * current
    else:
        return current.copy()
    return np.clip(updated, lower, upper).astype(np.float32)


def point_values_from_corners(corner_values, point_of_corner, point_count: int):
    """Mean corner value per point."""
    corner_values = np.asarray(corner_values, dtype=np.float64)
    counts = np.bincount(point_of_corner, minlength=point_count).astype(np.float64)
    sums = np.bincount(point_of_corner, weights=corner_values, minlength=point_count)
    return (sums / np.maximum(counts, 1.0)).astype(np.float32)


def dab_spacing_positions(previous, current, spacing: float):
    """Dab centres from *previous* (exclusive) toward *current*, *spacing* apart (screen px).

    Returns (positions [K, 2], leftover distance) so a slow mouse lays the same density as
    a fast one.
    """
    previous = np.asarray(previous, dtype=np.float32)
    current = np.asarray(current, dtype=np.float32)
    delta = current - previous
    distance = float(np.hypot(delta[0], delta[1]))
    spacing = max(float(spacing), 1.0)
    count = int(distance // spacing)
    if count <= 0:
        return np.empty((0, 2), dtype=np.float32)
    steps = (np.arange(1, count + 1, dtype=np.float32) * spacing / distance)[:, None]
    return previous + delta * steps


def triangle_needle_samples(resolutions, grid_samples_fn):
    """Flatten per-triangle needle resolutions into (triangle index [K], weights [K, 3])."""
    tri_indices = []
    weights = []
    for tri_index, resolution in enumerate(resolutions):
        if resolution < 0:
            continue
        for sample in grid_samples_fn(resolution):
            tri_indices.append(tri_index)
            weights.append(sample)
    if not tri_indices:
        return np.empty(0, dtype=np.int64), np.empty((0, 3), dtype=np.float32)
    return np.asarray(tri_indices, dtype=np.int64), np.asarray(weights, dtype=np.float32)


def normalize_rows(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return np.where(lengths > 1.0e-12, vectors / np.maximum(lengths, 1.0e-12), vectors).astype(np.float32)


def skew_blend(base_directions, target_directions, skews):
    """normalize(base x (1 - s) + target x s), base kept where the blend degenerates or s <= 0.

    The backend's pack for a Distance cage (split normal toward welded normal) and the
    caged ray (projection normal toward the cage point) both reduce to this.
    """
    base = np.asarray(base_directions, dtype=np.float32)
    target = normalize_rows(target_directions)
    s = np.clip(np.asarray(skews, dtype=np.float32), 0.0, 1.0)[:, None]
    blended = base * (1.0 - s) + target * s
    lengths = np.linalg.norm(blended, axis=-1, keepdims=True)
    ok = (lengths > 1.0e-6) & (s > 0.0)
    return np.where(ok, blended / np.maximum(lengths, 1.0e-12), base).astype(np.float32)


def skew_deviation_colors(face_normals, directions):
    """Vectorised cage._skew_deviation_color: green along the face normal, amber tilted."""
    dot = np.clip(np.einsum("ij,ij->i", np.asarray(face_normals, dtype=np.float32), directions), 0.0, 1.0)
    t = np.minimum(1.0, (1.0 - dot) * 1.7)
    colors = np.empty((t.shape[0], 4), dtype=np.float32)
    colors[:, 0] = 0.20 + t * 0.80
    colors[:, 1] = 0.95 - t * 0.50
    colors[:, 2] = 0.55 - t * 0.47
    colors[:, 3] = 0.90
    return colors


def triangle_bounds(triangle_positions):
    """Per-triangle (min, max) corners, for containing_triangle's broad phase."""
    tris = np.asarray(triangle_positions, dtype=np.float32)
    return tris.min(axis=1), tris.max(axis=1)


def containing_triangle(triangle_positions, point, tolerance: float, bounds=None):
    """(triangle index, barycentric weights) of the triangle *point* lies on, or (-1, None).

    *triangle_positions* is [T, 3, 3]; *bounds* is triangle_bounds() of it (computed when
    not given). Picks the triangle whose plane is nearest among those whose barycentric
    coordinates contain the point (within *tolerance* of it).
    """
    tris = np.asarray(triangle_positions)
    p = np.asarray(point, dtype=np.float64)
    if tris.shape[0] == 0:
        return -1, None
    lo, hi = bounds if bounds is not None else triangle_bounds(tris)
    pf = p.astype(np.float32)
    near = np.flatnonzero(np.all((pf >= lo - tolerance) & (pf <= hi + tolerance), axis=1))
    if near.size == 0:
        return -1, None
    candidates = tris[near].astype(np.float64)
    a = candidates[:, 0]
    v0 = candidates[:, 1] - a
    v1 = candidates[:, 2] - a
    v2 = p - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    denom = d00 * d11 - d01 * d01
    ok = np.abs(denom) > 1.0e-30
    safe = np.where(ok, denom, 1.0)
    v = (d11 * d20 - d01 * d21) / safe
    w = (d00 * d21 - d01 * d20) / safe
    u = 1.0 - v - w
    slack = 1.0e-4
    inside = ok & (u >= -slack) & (v >= -slack) & (w >= -slack)
    if not inside.any():
        return -1, None
    normal = np.cross(v0, v1)
    plane = np.abs(np.einsum("ij,ij->i", v2, normal)) / np.maximum(np.linalg.norm(normal, axis=1), 1.0e-30)
    plane = np.where(inside, plane, np.inf)
    best = int(np.argmin(plane))
    if plane[best] > tolerance:
        return -1, None
    weights = np.clip(np.array([u[best], v[best], w[best]], dtype=np.float32), 0.0, 1.0)
    weights /= max(float(weights.sum()), 1.0e-12)
    return int(near[best]), weights


def merge_face_corners(points, weights, corner_points, corner_weights):
    """Add the hit face's corner points with their barycentric weight (max with any
    falloff weight they already have), so a brush smaller than a face still reaches it."""
    points = np.asarray(points, dtype=np.int64)
    weights = np.asarray(weights, dtype=np.float32)
    merged = dict(zip(points.tolist(), weights.tolist()))
    for point, weight in zip(np.asarray(corner_points).tolist(), np.asarray(corner_weights).tolist()):
        merged[point] = max(merged.get(point, 0.0), float(weight))
    keys = np.fromiter(merged.keys(), dtype=np.int64, count=len(merged))
    values = np.fromiter(merged.values(), dtype=np.float32, count=len(merged))
    return keys, values


# ---------------------------------------------------------------------------
# Texel painting (Paint Skew correction maps)
# ---------------------------------------------------------------------------


def rasterize_uv_triangles(tri_uvs, width: int, height: int, *, max_candidates: int = 4_000_000):
    """Texels whose centre lies inside a UV triangle.

    *tri_uvs* is [T, 3, 2] in tile-local UV (0..1). Texel (i, j) is centred at
    ((i + 0.5) / width, (j + 0.5) / height), row j from v = 0, the correction-map
    convention. Returns (flat texel index j * width + i [N], triangle [N], barycentric [N, 3]);
    where islands overlap, the later triangle wins.
    """
    uvs = np.asarray(tri_uvs, dtype=np.float64).reshape(-1, 3, 2)
    empty = (np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64), np.empty((0, 3), dtype=np.float32))
    if uvs.shape[0] == 0 or width <= 0 or height <= 0:
        return empty
    px = uvs[:, :, 0] * width - 0.5
    py = uvs[:, :, 1] * height - 0.5
    xmin = np.clip(np.ceil(px.min(axis=1)), 0, width - 1).astype(np.int64)
    xmax = np.clip(np.floor(px.max(axis=1)), -1, width - 1).astype(np.int64)
    ymin = np.clip(np.ceil(py.min(axis=1)), 0, height - 1).astype(np.int64)
    ymax = np.clip(np.floor(py.max(axis=1)), -1, height - 1).astype(np.int64)
    nx = np.maximum(xmax - xmin + 1, 0)
    ny = np.maximum(ymax - ymin + 1, 0)
    counts = nx * ny
    live = np.flatnonzero(counts > 0)
    texels, tris, barys = [], [], []
    start = 0
    while start < live.size:
        cumulative = np.cumsum(counts[live[start:]])
        stop = start + max(1, int(np.searchsorted(cumulative, max_candidates, side="right")))
        chunk = live[start:stop]
        start = stop
        chunk_counts = counts[chunk]
        owner = np.repeat(chunk, chunk_counts)
        local = np.arange(int(chunk_counts.sum()), dtype=np.int64) - np.repeat(np.cumsum(chunk_counts) - chunk_counts, chunk_counts)
        x = xmin[owner] + local % nx[owner]
        y = ymin[owner] + local // nx[owner]
        cx = (x + 0.5) / width
        cy = (y + 0.5) / height
        a = uvs[owner, 0]
        v0 = uvs[owner, 1] - a
        v1 = uvs[owner, 2] - a
        d20 = cx - a[:, 0]
        d21 = cy - a[:, 1]
        denom = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(denom) > 1.0e-18
        safe = np.where(ok, denom, 1.0)
        b1 = (d20 * v1[:, 1] - v1[:, 0] * d21) / safe
        b2 = (v0[:, 0] * d21 - d20 * v0[:, 1]) / safe
        b0 = 1.0 - b1 - b2
        slack = -1.0e-7
        inside = ok & (b0 >= slack) & (b1 >= slack) & (b2 >= slack)
        texels.append((y * width + x)[inside])
        tris.append(owner[inside])
        barys.append(np.stack([b0, b1, b2], axis=1)[inside].astype(np.float32))
    if not texels:
        return empty
    texel = np.concatenate(texels)
    tri = np.concatenate(tris)
    bary = np.concatenate(barys)
    # Keep one owner per texel (the last, as a raster would).
    reverse = texel[::-1]
    _unique, first_in_reverse = np.unique(reverse, return_index=True)
    keep = texel.size - 1 - first_in_reverse
    return texel[keep], tri[keep], bary[keep]


def dilation_sources(covered_mask, radius: int):
    """For texels within *radius* steps of the covered area: (destination, source) flat
    indices, source being a covered texel reached by growing the coverage one ring at a
    time (8-neighbour). Filling values[dst] = values[src] pads the islands so bilinear taps
    at their borders read painted values, not zeros."""
    mask = np.asarray(covered_mask, dtype=bool)
    height, width = mask.shape
    source = np.where(mask.reshape(-1), np.arange(mask.size), -1).reshape(height, width)
    destinations, sources = [], []
    for _ring in range(max(0, int(radius))):
        grown = source.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                shifted = np.full_like(source, -1)
                ys = slice(max(dy, 0), height + min(dy, 0))
                yd = slice(max(-dy, 0), height + min(-dy, 0))
                xs = slice(max(dx, 0), width + min(dx, 0))
                xd = slice(max(-dx, 0), width + min(-dx, 0))
                shifted[yd, xd] = source[ys, xs]
                take = (grown < 0) & (shifted >= 0)
                grown[take] = shifted[take]
        new = (source < 0) & (grown >= 0)
        if not new.any():
            break
        destinations.append(np.flatnonzero(new.reshape(-1)))
        sources.append(grown.reshape(-1)[new.reshape(-1)])
        source = grown
    if not destinations:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    return np.concatenate(destinations), np.concatenate(sources)


def masked_neighbour_means(values, covered_mask, flat_indices):
    """Mean of the covered 8-neighbours (and the texel itself) of each flat texel index."""
    grid = np.asarray(values, dtype=np.float32)
    mask = np.asarray(covered_mask, dtype=bool)
    height, width = mask.shape
    flat = np.asarray(flat_indices, dtype=np.int64)
    ys, xs = np.divmod(flat, width)
    total = np.zeros(flat.size, dtype=np.float64)
    count = np.zeros(flat.size, dtype=np.float64)
    flat_grid = grid.reshape(-1)
    flat_mask = mask.reshape(-1)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ny = ys + dy
            nx = xs + dx
            inside = (ny >= 0) & (ny < height) & (nx >= 0) & (nx < width)
            index = np.where(inside, ny * width + nx, 0)
            use = inside & flat_mask[index]
            total += np.where(use, flat_grid[index], 0.0)
            count += use
    return np.where(count > 0, total / np.maximum(count, 1.0), flat_grid[flat]).astype(np.float32)
