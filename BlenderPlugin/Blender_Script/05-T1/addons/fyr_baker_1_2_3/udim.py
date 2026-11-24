"""UDIM tile occupancy discovery and effective-tile resolution.

Two halves, deliberately separated:

* the geometry and selection logic is pure Python over plain tuples, so it is testable
  without Blender;
* :func:`detect_occupied_tiles` walks evaluated meshes and imports ``bpy`` lazily.

Occupancy is decided by real triangle/tile intersection, not by UV vertices and not by the
triangle's bounding box. A long thin diagonal triangle spanning a tile corner has a bounding
box covering four tiles while genuinely touching only two, and every spurious tile costs a
full set of output images.
"""

from __future__ import annotations

import math
import os
from pathlib import Path as _Path, PurePath as _PurePath

from . import rna_buffers
from . import constants
from . import naming


class UdimOccupancyError(ValueError):
    """UV data cannot be resolved to a usable tile set."""


# --------------------------------------------------------------------------------------
# Path shapes
#
# Two forms of the same result, and they must never be confused:
#
# * the *concrete* path is a real file on disk -- ``Asset_Normal.1001.png``;
# * the *logical* path carries ``constants.UDIM_PATH_TOKEN`` in the tile's place --
#   ``Asset_Normal.<UDIM>.png`` -- and is what Blender, Arnold and V-Ray are handed.
#
# An untiled output has no tile segment at all and both forms are the same string, which is
# what keeps single-tile projects byte-identical to their pre-UDIM behaviour.
# --------------------------------------------------------------------------------------


def tile_from_path(file_path) -> int:
    """Tile number encoded in a concrete path, or ``0`` when the path carries no tile."""
    text = str(file_path or "").strip()
    if not text:
        return 0
    stem = _PurePath(text).stem
    _base, token = naming.split_udim_tile_suffix(stem)
    return int(token) if token is not None else 0


def logical_udim_path(file_path) -> str:
    """Concrete path -> the ``<UDIM>`` form. A path with no tile comes back unchanged."""
    text = str(file_path or "").strip()
    if not text:
        return ""
    path = _PurePath(text)
    base, token = naming.split_udim_tile_suffix(path.stem)
    if token is None:
        return text
    return str(path.with_name(f"{base}.{constants.UDIM_PATH_TOKEN}{path.suffix}"))


def concrete_udim_path(logical_path, udim_tile) -> str:
    """``<UDIM>`` form -> the concrete path for one tile.

    Raises :class:`naming.InvalidUdimTileError` for an unusable tile rather than emitting a
    path with the token still in it, which would silently become a filename containing
    literal angle brackets.
    """
    text = str(logical_path or "").strip()
    if not text:
        return ""
    token = naming.normalize_udim_tile(udim_tile)
    if token is None:
        return text
    if constants.UDIM_PATH_TOKEN not in text:
        return text
    return text.replace(constants.UDIM_PATH_TOKEN, token)


def is_logical_udim_path(file_path) -> bool:
    return constants.UDIM_PATH_TOKEN in str(file_path or "")


def directory_file_names(logical_path) -> list[str]:
    """File names beside a logical path. Split out so one listing serves many maps.

    Stale detection runs on every progress update; re-listing the output directory once per
    map per tick is the difference between a free check and a visible hitch on a texture set
    with a dozen maps.
    """
    text = str(logical_path or "").strip()
    if not text:
        return []
    parent = _Path(text).parent

    def compute() -> tuple[str, ...]:
        try:
            # scandir: on Windows the directory read already carries the file/dir flag, so
            # listing 1,500 outputs costs no per-entry stat (Path.iterdir + is_file did one each).
            with os.scandir(parent) as entries:
                return tuple(sorted(entry.name for entry in entries if entry.is_file()))
        except OSError:
            return ()

    # Most callers do not pass a listing in, so one progress update listed (and stat'ed)
    # the same output directory ~1,170 times on Ubrion. Inside
    # runtime_output_images.normalized_path_cache() each directory is listed once per call.
    from . import runtime_output_images

    return list(runtime_output_images.cached_normalized_path("dirlist", str(parent), compute))


def sibling_tile_paths(logical_path, *, directory_names=None) -> list[tuple[int, str]]:
    """Every concrete tile file matching a logical ``<UDIM>`` path, ascending.

    Used to find files left behind by an earlier bake. Discovery only -- nothing here
    deletes, because §1.4 forbids removing a de-occupied tile's file silently.
    """
    text = str(logical_path or "").strip()
    if not text or constants.UDIM_PATH_TOKEN not in text:
        return []
    path = _Path(text)
    prefix, _token, remainder = path.name.partition(constants.UDIM_PATH_TOKEN)
    names = directory_file_names(text) if directory_names is None else list(directory_names)
    found: list[tuple[int, str]] = []
    for name in names:
        if not name.startswith(prefix) or not name.endswith(remainder):
            continue
        middle = name[len(prefix): len(name) - len(remainder)] if remainder else name[len(prefix):]
        if not middle.isdigit():
            continue
        try:
            token = naming.normalize_udim_tile(middle)
        except naming.InvalidUdimTileError:
            continue
        if token is None:
            continue
        found.append((int(token), str(path.with_name(name))))
    return sorted(found)


def tile_origin(udim_tile: int) -> tuple[int, int]:
    """Integer UV cell origin ``(tile_u, tile_v)`` for a tile number."""
    return naming.udim_tile_to_coords(udim_tile)


def _finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def _cell_range(low: float, high: float) -> tuple[int, int]:
    """Half-open integer cell span covering ``[low, high]``.

    A coordinate sitting exactly on an integer boundary belongs to the cell it opens, so a
    triangle whose edge lies exactly on ``u = 1.0`` does not gain a zero-area tile to its left.
    """
    first = int(math.floor(low))
    last = int(math.ceil(high)) - 1
    if last < first:
        last = first
    return first, last


def _separated(triangle_values: tuple[float, float, float], box_min: float, box_max: float) -> bool:
    # Non-strict on purpose: a shared edge or a single touching vertex is contact with zero
    # overlap area, which must not claim the tile.
    return max(triangle_values) <= box_min or min(triangle_values) >= box_max


def triangle_overlaps_cell(
    uv0: tuple[float, float],
    uv1: tuple[float, float],
    uv2: tuple[float, float],
    cell_u: int,
    cell_v: int,
) -> bool:
    """True when the triangle overlaps the unit cell with positive area.

    Separating-axis test over the two box axes plus the three triangle edge normals, which is
    exact for a triangle against an axis-aligned square.
    """
    min_u = float(cell_u)
    max_u = float(cell_u + 1)
    min_v = float(cell_v)
    max_v = float(cell_v + 1)

    if _separated((uv0[0], uv1[0], uv2[0]), min_u, max_u):
        return False
    if _separated((uv0[1], uv1[1], uv2[1]), min_v, max_v):
        return False

    corners = ((min_u, min_v), (max_u, min_v), (max_u, max_v), (min_u, max_v))
    triangle = (uv0, uv1, uv2)
    for index in range(3):
        start = triangle[index]
        end = triangle[(index + 1) % 3]
        # Outward normal of this edge; degenerate edges contribute no separating axis.
        axis_u = -(end[1] - start[1])
        axis_v = end[0] - start[0]
        if axis_u == 0.0 and axis_v == 0.0:
            continue
        triangle_projections = tuple(axis_u * point[0] + axis_v * point[1] for point in triangle)
        corner_projections = [axis_u * point[0] + axis_v * point[1] for point in corners]
        if _separated(triangle_projections, min(corner_projections), max(corner_projections)):
            return False
    return True


def tiles_for_triangle(
    uv0: tuple[float, float],
    uv1: tuple[float, float],
    uv2: tuple[float, float],
    *,
    max_tiles: int = constants.UDIM_MAX_TILES_PER_TRIANGLE,
) -> list[int]:
    """Tile numbers a single UV triangle occupies, ascending.

    Raises :class:`UdimOccupancyError` for non-finite UVs, negative tiles, columns beyond the
    ten-column convention, tiles past the supported maximum, or a triangle spanning more tiles
    than ``max_tiles`` (which means broken UVs, not a legitimate layout).
    """
    coordinates = (uv0[0], uv0[1], uv1[0], uv1[1], uv2[0], uv2[1])
    if not _finite(*coordinates):
        raise UdimOccupancyError("UV coordinates are not finite")

    first_u, last_u = _cell_range(min(uv0[0], uv1[0], uv2[0]), max(uv0[0], uv1[0], uv2[0]))
    first_v, last_v = _cell_range(min(uv0[1], uv1[1], uv2[1]), max(uv0[1], uv1[1], uv2[1]))

    if first_u < 0 or first_v < 0:
        raise UdimOccupancyError(
            "UVs extend into negative tile space, which the UDIM scheme cannot express"
        )
    if last_u >= constants.UDIM_TILE_COLUMNS:
        raise UdimOccupancyError(
            f"UVs extend past the {constants.UDIM_TILE_COLUMNS}-column UDIM convention "
            f"(column {last_u})"
        )

    candidate_count = (last_u - first_u + 1) * (last_v - first_v + 1)
    if candidate_count > max_tiles:
        raise UdimOccupancyError(
            f"a single triangle spans {candidate_count} UV tiles (limit {max_tiles}); "
            "this is broken UV geometry rather than a multi-tile layout"
        )

    tiles: list[int] = []
    for cell_v in range(first_v, last_v + 1):
        for cell_u in range(first_u, last_u + 1):
            if not triangle_overlaps_cell(uv0, uv1, uv2, cell_u, cell_v):
                continue
            tile = naming.udim_tile_from_coords(cell_u, cell_v)
            if tile > constants.UDIM_TILE_MAX:
                raise UdimOccupancyError(
                    f"UV tile {tile} is past the supported maximum {constants.UDIM_TILE_MAX}"
                )
            tiles.append(tile)

    if len(tiles) > max_tiles:
        raise UdimOccupancyError(
            f"a single triangle occupies {len(tiles)} UV tiles (limit {max_tiles})"
        )
    return sorted(tiles)


def tiles_for_triangles(triangles, *, max_tiles: int = constants.UDIM_MAX_TILES_PER_TRIANGLE):
    """Union of occupied tiles over an iterable of ``(uv0, uv1, uv2)`` triples.

    Returns ``(tiles, crossing_count)``: the sorted tile numbers, and how many triangles
    straddled a tile border. Crossing triangles are baked correctly into every tile they touch,
    but they are also an authoring defect worth reporting -- no baker can make a border-crossing
    island filter seamlessly, because each UDIM tile is an independently sampled texture.
    """
    occupied: set[int] = set()
    crossing_count = 0
    for uv0, uv1, uv2 in triangles:
        tiles = tiles_for_triangle(uv0, uv1, uv2, max_tiles=max_tiles)
        if len(tiles) > 1:
            crossing_count += 1
        occupied.update(tiles)
    return sorted(occupied), crossing_count


class TileSpec:
    """One tile Fyr will actually bake, with its effective physical size."""

    __slots__ = ("udim_tile", "width", "height", "detected", "included", "resolution_overridden")

    def __init__(
        self,
        udim_tile: int,
        width: int,
        height: int,
        *,
        detected: bool = False,
        included: bool = False,
        resolution_overridden: bool = False,
    ) -> None:
        self.udim_tile = int(udim_tile)
        self.width = int(width)
        self.height = int(height)
        self.detected = bool(detected)
        self.included = bool(included)
        self.resolution_overridden = bool(resolution_overridden)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"TileSpec(udim_tile={self.udim_tile}, width={self.width}, height={self.height}, "
            f"detected={self.detected}, included={self.included})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, TileSpec):
            return NotImplemented
        return (
            self.udim_tile == other.udim_tile
            and self.width == other.width
            and self.height == other.height
        )


def _tile_rows(texture_set):
    for row in getattr(texture_set, "udim_tiles", []) or []:
        try:
            number = int(getattr(row, "number", 0) or 0)
        except (TypeError, ValueError):
            continue
        if number < constants.UDIM_TILE_MIN or number > constants.UDIM_TILE_MAX:
            continue
        yield number, row


def resolve_effective_tiles(
    texture_set,
    detected_tiles,
    project_width: int,
    project_height: int,
    *,
    occupancy_known: bool = True,
):
    """Combine detected occupancy with the artist's tile rows.

    Returns ``(specs, warnings)``. ``specs`` is ordered by tile number; ``warnings`` are
    human-readable strings for the caller to surface at preflight.

    A texture set that resolves to exactly tile 1001 with no artist configuration keeps the
    legacy untiled behaviour -- see :func:`uses_tokenized_naming`.
    """
    warnings: list[str] = []
    detected = {int(tile) for tile in detected_tiles or ()}
    rows = dict(_tile_rows(texture_set))
    mode = str(getattr(texture_set, "udim_mode", constants.UDIM_MODE_AUTOMATIC) or "").upper()
    set_name = str(getattr(texture_set, "name", "") or "texture set")

    if mode == constants.UDIM_MODE_EXPLICIT:
        selected = {
            number
            for number, row in rows.items()
            if getattr(row, "override", "") != constants.UDIM_TILE_OVERRIDE_EXCLUDE
        }
        if not selected:
            warnings.append(
                f"Texture set '{set_name}' is in Explicit UDIM mode with no tiles listed; "
                "falling back to tile 1001."
            )
            selected = {constants.UDIM_TILE_MIN}
        if occupancy_known:
            for tile in sorted(selected - detected):
                warnings.append(
                    f"Texture set '{set_name}' tile {tile} has no geometry; it will be written "
                    "using each map's default fill."
                )
            # The mirror case used to pass silently: geometry in a tile the artist
            # forgot to list baked nothing for that tile with a clean preflight.
            for tile in sorted(detected - selected):
                warnings.append(
                    f"Texture set '{set_name}' tile {tile} is occupied by geometry but is not "
                    "listed in Explicit UDIM mode; add the tile or its texels will not be baked."
                )
    else:
        selected = set(detected)
        for number, row in rows.items():
            override = getattr(row, "override", constants.UDIM_TILE_OVERRIDE_NONE)
            if override == constants.UDIM_TILE_OVERRIDE_INCLUDE:
                selected.add(number)
                if occupancy_known and number not in detected:
                    warnings.append(
                        f"Texture set '{set_name}' tile {number} is force-included but no "
                        "geometry occupies it; it will be written using each map's default fill."
                    )
            elif override == constants.UDIM_TILE_OVERRIDE_EXCLUDE:
                if number in detected:
                    warnings.append(
                        f"Texture set '{set_name}' tile {number} is occupied by geometry but "
                        "excluded; that geometry will not be baked."
                    )
                selected.discard(number)
        if not selected:
            selected = {constants.UDIM_TILE_MIN}

    fallback_width = max(1, int(project_width))
    fallback_height = max(1, int(project_height))

    specs: list[TileSpec] = []
    for tile in sorted(selected):
        row = rows.get(tile)
        width = fallback_width
        height = fallback_height
        overridden = False
        if row is not None and bool(getattr(row, "use_resolution_override", False)):
            width = max(1, int(getattr(row, "resolution_x", fallback_width) or fallback_width))
            height = max(1, int(getattr(row, "resolution_y", fallback_height) or fallback_height))
            overridden = True
        specs.append(
            TileSpec(
                tile,
                width,
                height,
                detected=tile in detected,
                included=row is not None
                and getattr(row, "override", "") == constants.UDIM_TILE_OVERRIDE_INCLUDE,
                resolution_overridden=overridden,
            )
        )
    return specs, warnings


def uses_tokenized_naming(texture_set, specs) -> bool:
    """Whether outputs for this texture set carry a ``.NNNN`` tile suffix.

    A plain single-tile project must keep its legacy filenames, so tokenized naming turns on
    only when the project is genuinely multi-tile or the artist has taken manual control:

    * any tile other than 1001 is being baked, or
    * the texture set is in Explicit mode, or
    * the artist configured any tile row.
    """
    tiles = [spec.udim_tile for spec in specs]
    if any(tile != constants.UDIM_TILE_MIN for tile in tiles):
        return True
    mode = str(getattr(texture_set, "udim_mode", constants.UDIM_MODE_AUTOMATIC) or "").upper()
    if mode == constants.UDIM_MODE_EXPLICIT:
        return True
    # A row must actually DO something to count as taking manual control. Merely adding an
    # empty row -- which is what clicking "Add Tile" produces before the artist picks an
    # override or a resolution -- must not silently rename every output in the set.
    for _number, row in _tile_rows(texture_set):
        if getattr(row, "override", constants.UDIM_TILE_OVERRIDE_NONE) != constants.UDIM_TILE_OVERRIDE_NONE:
            return True
        if bool(getattr(row, "use_resolution_override", False)):
            return True
    return False


def _fast_single_cell_tiles(mesh, uv_data):
    """Vectorised occupancy for the common case where no triangle crosses a tile border.

    Returns the set of occupied tiles, or ``None`` when anything at all is unusual (a
    border-crossing triangle, a non-finite UV, negative/overflowing tile space, or no
    numpy) so the caller runs the exact per-triangle path and produces the identical
    result and error message. Walking 15k triangles in Python cost ~0.35s per bake.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    loop_triangles = getattr(mesh, "loop_triangles", None)
    if loop_triangles is None:
        return None
    tri_count = len(loop_triangles)
    if tri_count == 0:
        return set()
    try:
        # foreach_get needs an exactly typed buffer: int32 for the loop indices,
        # float32 for the UVs (Blender stores both at those widths).
        loops = rna_buffers.empty_u32_for_rna(tri_count * 3)
        loop_triangles.foreach_get("loops", loops)
        loops = rna_buffers.as_i32(loops)
        uvs = np.empty(len(uv_data) * 2, dtype=np.float32)
        uv_data.foreach_get("uv", uvs)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    uvs = uvs.reshape(-1, 2).astype(np.float64)
    if loops.min() < 0 or loops.max() >= uvs.shape[0]:
        return None
    triangle_uv = uvs[loops].reshape(tri_count, 3, 2)
    if not np.isfinite(triangle_uv).all():
        return None
    low = triangle_uv.min(axis=1)
    high = triangle_uv.max(axis=1)
    # Mirrors _cell_range: first = floor(low), last = max(ceil(high) - 1, first).
    first = np.floor(low).astype(np.int64)
    last = np.maximum(np.ceil(high).astype(np.int64) - 1, first)
    if not np.array_equal(first, last):
        return None
    if first.min() < 0:
        return None
    if first[:, 0].max() >= constants.UDIM_TILE_COLUMNS:
        return None
    tiles = constants.UDIM_TILE_MIN + first[:, 0] + 10 * first[:, 1]
    if int(tiles.max()) > constants.UDIM_TILE_MAX:
        return None
    return {int(tile) for tile in np.unique(tiles)}


def detect_occupied_tiles(objects, uv_layer_name: str | None = None, *, depsgraph=None):
    """Union of occupied tiles across ``objects``, using each mesh's active render UV layer.

    Returns ``(tiles, crossing_count, errors)``. Errors are per-object strings rather than
    raised, so preflight can report every offending object in one pass instead of stopping at
    the first.
    """
    import bpy  # noqa: F401  (Blender-only; imported lazily so this module stays testable)

    from . import low_material_subset

    tiles: set[int] = set()
    crossing_total = 0
    errors: list[str] = []

    for obj in objects or ():
        if obj is None or getattr(obj, "type", "") != "MESH":
            continue
        evaluated = obj
        if depsgraph is not None:
            try:
                evaluated = obj.evaluated_get(depsgraph)
            except (AttributeError, RuntimeError):
                evaluated = obj
        try:
            mesh = evaluated.to_mesh()
        except (AttributeError, RuntimeError) as exc:
            errors.append(f"{getattr(obj, 'name', '?')}: could not evaluate mesh ({exc})")
            continue
        try:
            uv_layers = getattr(mesh, "uv_layers", None)
            layer = None
            if uv_layers:
                if uv_layer_name:
                    layer = uv_layers.get(uv_layer_name)
                if layer is None:
                    layer = getattr(uv_layers, "active", None)
            if layer is None:
                errors.append(f"{getattr(obj, 'name', '?')}: no UV layer to read tiles from")
                continue
            uv_data = layer.data
            try:
                mesh.calc_loop_triangles()
            except (AttributeError, RuntimeError):
                pass
            material_mask = low_material_subset.triangle_mask(obj, mesh)
            fast_tiles = None if material_mask is not None else _fast_single_cell_tiles(mesh, uv_data)
            if fast_tiles is not None:
                tiles.update(fast_tiles)
                continue
            triangles = []
            for tri_index, tri in enumerate(getattr(mesh, "loop_triangles", ()) or ()):
                if material_mask is not None and not material_mask[tri_index]:
                    continue
                loops = tri.loops
                triangles.append(
                    (
                        tuple(uv_data[loops[0]].uv),
                        tuple(uv_data[loops[1]].uv),
                        tuple(uv_data[loops[2]].uv),
                    )
                )
            try:
                object_tiles, crossing = tiles_for_triangles(triangles)
            except UdimOccupancyError as exc:
                errors.append(f"{getattr(obj, 'name', '?')}: {exc}")
                continue
            tiles.update(object_tiles)
            crossing_total += crossing
        finally:
            try:
                evaluated.to_mesh_clear()
            except (AttributeError, RuntimeError):
                pass

    return sorted(tiles), crossing_total, errors


# --------------------------------------------------------------------------------------
# Sampler-side tile occupancy (Material IR UDIM tables)
#
# A different question from the output-tile detection above. That one asks which tiles a
# bake WRITES and refuses negative or out-of-convention UVs. This one asks which tiles of a
# SOURCE image the backend sampler will READ, keyed the way Cycles' kernel_image_udim_map
# keys them: by C truncation, not floor. So u in (-1, 1) is column 0 (tile 1001, sampled
# with the image's own extension), and u <= -1 or column >= 10 is a miss that reads the
# missing colour. Nothing here raises: odd UVs just read no tile.
# --------------------------------------------------------------------------------------

#: How far each vertex UV moves toward its triangle's centroid before the tile test, so a
#: vertex sitting exactly on a tile border does not claim the neighbouring tile.
SAMPLER_TILE_NUDGE = 1e-4


def _floor_cell_to_sampler_column(cells):
    """Floor cell index -> truncation column. Floor cell -1 is (-1, 0), truncating to 0."""
    import numpy as np

    return np.where(cells == -1, 0, cells)


def sampler_tiles_by_group(triangle_uv, groups=None, *, nudge: float = SAMPLER_TILE_NUDGE):
    """Tiles a sampler reads for ``(N, 3, 2)`` hit-UV triangles, per group.

    ``groups`` is an optional length-N integer array (a material slot, say); every triangle
    falls in group 0 without it. Returns ``{group: set(tile numbers)}``. A triangle inside
    one cell is resolved vectorised; one crossing cells is tested cell by cell with the exact
    positive-area overlap test, so a thin diagonal sliver does not claim its bounding box.
    """
    import numpy as np

    tri = np.asarray(triangle_uv, dtype=np.float64).reshape(-1, 3, 2)
    count = tri.shape[0]
    result: dict[int, set[int]] = {}
    if count == 0:
        return result
    if groups is None:
        group_ids = np.zeros(count, dtype=np.int64)
    else:
        group_ids = np.asarray(groups, dtype=np.int64).reshape(-1)
        if group_ids.shape[0] != count:
            raise ValueError("groups must have one entry per triangle")

    finite = np.isfinite(tri).all(axis=(1, 2))
    if not finite.all():
        tri = tri[finite]
        group_ids = group_ids[finite]
        count = tri.shape[0]
        if count == 0:
            return result
    centroid = tri.mean(axis=1, keepdims=True)
    tri = tri + (centroid - tri) * float(nudge)
    cells = np.floor(tri)
    low = cells.min(axis=1)
    high = cells.max(axis=1)
    single = (low == high).all(axis=1)

    # One cell: the whole triangle reads one tile (or misses).
    column = _floor_cell_to_sampler_column(low[single, 0].astype(np.int64))
    row = _floor_cell_to_sampler_column(low[single, 1].astype(np.int64))
    single_groups = group_ids[single]
    valid = (column >= 0) & (column < constants.UDIM_TILE_COLUMNS) & (row >= 0)
    tiles = constants.UDIM_TILE_MIN + column[valid] + 10 * row[valid]
    if tiles.size:
        pairs = np.unique(np.stack((single_groups[valid], tiles), axis=1), axis=0)
        for group, tile in pairs.tolist():
            result.setdefault(int(group), set()).add(int(tile))

    # Several cells: exact overlap per floor cell, then truncation-keyed.
    for index in np.nonzero(~single)[0].tolist():
        uv0, uv1, uv2 = (tuple(float(c) for c in tri[index, k]) for k in range(3))
        first_u, last_u = int(low[index, 0]), int(high[index, 0])
        first_v, last_v = int(low[index, 1]), int(high[index, 1])
        # Broken UVs spanning a huge area are not a layout; clip to the tile grid a
        # sampler can actually read (columns -1..9, rows -1 and up) and give up past
        # the per-triangle budget rather than walking millions of cells.
        first_u, last_u = max(first_u, -1), min(last_u, constants.UDIM_TILE_COLUMNS - 1)
        first_v = max(first_v, -1)
        if last_u < first_u or last_v < first_v:
            continue
        if (last_u - first_u + 1) * (last_v - first_v + 1) > constants.UDIM_MAX_TILES_PER_TRIANGLE:
            continue
        group = int(group_ids[index])
        for cell_v in range(first_v, last_v + 1):
            for cell_u in range(first_u, last_u + 1):
                if not triangle_overlaps_cell(uv0, uv1, uv2, cell_u, cell_v):
                    continue
                sampler_u = 0 if cell_u == -1 else cell_u
                sampler_v = 0 if cell_v == -1 else cell_v
                result.setdefault(group, set()).add(
                    constants.UDIM_TILE_MIN + sampler_u + 10 * sampler_v
                )
    return result
