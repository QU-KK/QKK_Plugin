"""Paint Offset / Paint Skew values shared by the exporter, the cage display and the skew
needles (no bpy import): the legacy canvas sampler and the per-corner paint layers.

The exporter bakes the Paint Offset / Paint Skew canvases into per-corner values
(vertex.paint_offset / vertex.paint_skew) with this sampler, and the backend only ever
interpolates those corner values. The viewport needles sample through the same function so
they show exactly the rays the bake traces.
"""

from . import rna_buffers

def sample_image_red_channel_numpy(image, corner_uvs):
    """Bilinear red channel of *image* at each (u, v) in *corner_uvs* (flat or Nx2), or None."""
    import numpy as np

    if image is None:
        return None
    width = int(getattr(image, "size", (0, 0))[0])
    height = int(getattr(image, "size", (0, 0))[1])
    if width <= 0 or height <= 0:
        return None
    pixels = getattr(image, "pixels", None)
    if pixels is None or not hasattr(pixels, "foreach_get"):
        return None

    pixels_flat = np.empty(width * height * 4, dtype=np.float32)
    pixels.foreach_get(pixels_flat)
    red = pixels_flat.reshape(height * width, 4)[:, 0]
    uvs = np.asarray(corner_uvs, dtype=np.float32).reshape(-1, 2)
    if uvs.size == 0:
        return np.empty(0, dtype=np.float32)

    if width <= 1:
        fx = np.zeros(uvs.shape[0], dtype=np.float32)
    else:
        fx = np.mod(uvs[:, 0], 1.0).astype(np.float32, copy=False) * float(width - 1)
    if height <= 1:
        fy = np.zeros(uvs.shape[0], dtype=np.float32)
    else:
        fy = np.mod(uvs[:, 1], 1.0).astype(np.float32, copy=False) * float(height - 1)

    x0 = np.floor(fx).astype(np.int32, copy=False)
    y0 = np.floor(fy).astype(np.int32, copy=False)
    x1 = np.minimum(x0 + 1, max(width - 1, 0))
    y1 = np.minimum(y0 + 1, max(height - 1, 0))
    tx = fx - x0.astype(np.float32, copy=False)
    ty = fy - y0.astype(np.float32, copy=False)

    row_width = int(width)
    idx00 = y0 * row_width + x0
    idx10 = y0 * row_width + x1
    idx01 = y1 * row_width + x0
    idx11 = y1 * row_width + x1
    return (
        red[idx00] * (1.0 - tx) * (1.0 - ty)
        + red[idx10] * tx * (1.0 - ty)
        + red[idx01] * (1.0 - tx) * ty
        + red[idx11] * tx * ty
    ).astype(np.float32, copy=False)


# ---------------------------------------------------------------------------
# Paint Offset layer: stored on the low mesh
# ---------------------------------------------------------------------------
#
# The Fyr paint brush stores Paint Offset as a FLOAT attribute on each low mesh, one
# value per face corner, instead of in a group image. It needs no UVs, carries signed
# values, and holds exactly what the bake reads (the bake only ever saw per-corner samples
# of the image). The leading dot keeps it out of the Attributes panel; Blender still
# propagates it through modifiers, joins and topology edits (verified on 5.1 for
# Mirror, Subdivision, Triangulate, Weighted Normal, Solidify, Bevel, Array, Decimate).
#
# The layer is 0 where nothing is painted, and a missing attribute reads as 0, so joining
# an unpainted mesh or adding a low to the group changes nothing: the exported multiplier
# is Offset Scale x max(0, 1 + r); -1 puts the cage on the surface, +1 doubles it.
# A group whose lows carry the layer ("layer mode") ignores its legacy offset image; the
# brush unlinks the image when it converts it, so the two never mix.
#
# Paint Skew is a per-texel correction map instead (see "Skew correction maps" below).

OFFSET_ATTRIBUTE = ".fyr_paint_offset"
PAINT_ATTRIBUTES = (OFFSET_ATTRIBUTE,)

#: Offset values below -1 would ask for a negative cage distance the backend clamps
#: anyway; the upper bound keeps a runaway stroke from pushing rays across the scene.
OFFSET_VALUE_MIN = -1.0
OFFSET_VALUE_MAX = 9.0

_LAYER_DOMAINS = ("CORNER", "POINT")


def find_paint_layer(mesh, name: str):
    """The mesh's paint attribute *name* when it is a usable FLOAT layer, else None."""
    attributes = getattr(mesh, "attributes", None) if mesh is not None else None
    if attributes is None:
        return None
    try:
        layer = attributes.get(name)
    except Exception:
        return None
    if layer is None:
        return None
    if str(getattr(layer, "data_type", "") or "").upper() != "FLOAT":
        return None
    if str(getattr(layer, "domain", "") or "").upper() not in _LAYER_DOMAINS:
        return None
    return layer


def has_paint_layer(mesh, name: str) -> bool:
    return find_paint_layer(mesh, name) is not None


def read_loop_values(mesh, name: str, loop_vertex_indices=None):
    """Per-loop (face corner) values of paint layer *name*, float32, or None when absent.

    A POINT-domain layer (for instance one an artist made by hand) is spread to its
    corners through *loop_vertex_indices* (read from the mesh when not given).
    """
    import numpy as np

    layer = find_paint_layer(mesh, name)
    if layer is None:
        return None
    data = getattr(layer, "data", None)
    if data is None or not hasattr(data, "foreach_get"):
        return None
    count = len(data)
    values = np.empty(count, dtype=np.float32)
    if count:
        data.foreach_get("value", values)
    if str(getattr(layer, "domain", "") or "").upper() == "CORNER":
        return values
    if loop_vertex_indices is None:
        loop_vertex_indices = _loop_vertex_indices(mesh)
        if loop_vertex_indices is None:
            return None
    return values[np.asarray(loop_vertex_indices, dtype=np.int64)]


def _loop_vertex_indices(mesh):
    import numpy as np

    loops = getattr(mesh, "loops", None)
    if loops is None or not hasattr(loops, "foreach_get"):
        return None
    indices = rna_buffers.empty_u32_for_rna(len(loops))
    corner_verts = getattr(mesh, "corner_verts", None)
    if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
        corner_verts.foreach_get("vertex", indices)
    else:
        loops.foreach_get("vertex_index", indices)
    return rna_buffers.as_i32(indices)


def offset_multipliers_from_values(values):
    """Layer offset values -> the per-corner multiplier the backend applies (>= 0)."""
    import numpy as np

    return np.maximum(np.asarray(values, dtype=np.float32) + np.float32(1.0), np.float32(0.0))


def corner_paint_values(
    mesh,
    triangle_loop_indices,
    corner_uvs,
    *,
    loop_vertex_indices=None,
    offset_image=None,
    skew_image=None,
    offset_scale: float = 1.0,
    skew_amount: float = 0.0,
    offset_layer_mode: bool = False,
):
    """The per-triangle-corner (paint_offset, paint_skew) the exporter writes.

    One rule for every consumer (exporter, cage display, skew needles):
      offset: in layer mode the mesh attribute (0 where absent) and no image; otherwise the
              legacy image sampled at the corner UV, else 1.0; times Offset Scale.
      skew:   the legacy 1.0.x skew image sampled at the corner UV, else 1.0; times Skew
              Amount (the per-texel correction map travels separately).
    Returns two float32 arrays of ``len(triangle_loop_indices)``.
    """
    import numpy as np

    triangle_loop_indices = np.asarray(triangle_loop_indices, dtype=np.int64).reshape(-1)
    corner_count = int(triangle_loop_indices.shape[0])

    def _resolve(layer_mode, name, image, to_weights):
        if layer_mode:
            loop_values = read_loop_values(mesh, name, loop_vertex_indices)
            if loop_values is None or loop_values.shape[0] == 0:
                return to_weights(np.zeros(corner_count, dtype=np.float32))
            return to_weights(loop_values[triangle_loop_indices])
        sampled = sample_image_red_channel_numpy(image, corner_uvs) if image is not None else None
        if sampled is None:
            return np.ones(corner_count, dtype=np.float32)
        return np.asarray(sampled, dtype=np.float32)

    offsets = _resolve(offset_layer_mode, OFFSET_ATTRIBUTE, offset_image, offset_multipliers_from_values)
    skews = _resolve(False, "", skew_image, None)
    offsets = (offsets * np.float32(offset_scale)).astype(np.float32, copy=False)
    skews = (skews * np.float32(skew_amount)).astype(np.float32, copy=False)
    return offsets, skews


def paint_layer_digest(mesh) -> str:
    """Content identity of the mesh's paint layers ("" when it has none).

    Folded into export payload keys and the Rebuild Changed Maps state: an attribute
    write changes no vertex count, bound or modifier, so nothing else would notice a
    stroke. ~0.1 ms per 100k corners.
    """
    import hashlib

    import numpy as np

    parts = []
    for name in PAINT_ATTRIBUTES:
        layer = find_paint_layer(mesh, name)
        if layer is None:
            continue
        data = getattr(layer, "data", None)
        if data is None or not hasattr(data, "foreach_get"):
            continue
        values = np.empty(len(data), dtype=np.float32)
        if values.size:
            data.foreach_get("value", values)
        digest = hashlib.blake2b(values.tobytes(), digest_size=8).hexdigest()
        parts.append(f"o{str(getattr(layer, 'domain', ''))[:1]}{digest}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Skew correction maps: Paint Skew, per texel
# ---------------------------------------------------------------------------
#
# Painter / Marmoset style: the painted value c (0..1) bends the bake ray toward the low
# triangle's flat face normal, c = 1 straight off the face. It is read PER TEXEL from a
# UV-space map per UDIM tile of the group's bake UV layer (the backend resamples each map
# bilinearly, texel-centre convention, clamp to edge: map pixel (i, j) is centred at
# tile-local u = (i + 0.5) / w, v = (j + 0.5) / h, row 0 = v bottom).
#
# Maps are stored as float ID properties on the bake group itself, so every brush stroke
# is an ordinary memfile undo step and the data saves with the .blend (about 1 MB per
# 512 x 512 tile). Texels outside the UV islands carry the value of the nearest covered
# texel (the brush dilates on commit), so bilinear taps at island borders never pull in
# unpainted zeros.

SKEW_CORRECTION_PREFIX = "_fyr_skew_correction_"
SKEW_CORRECTION_SIZE_SUFFIX = "_size"
#: Default map size per tile. Marmoset uses a fixed 512; the backend resamples any size.
SKEW_CORRECTION_DEFAULT_SIZE = 512


def _correction_keys(group):
    keys = getattr(group, "keys", None)
    if keys is None:
        return []
    try:
        return [
            str(key)
            for key in keys()
            if str(key).startswith(SKEW_CORRECTION_PREFIX) and not str(key).endswith(SKEW_CORRECTION_SIZE_SUFFIX)
        ]
    except Exception:
        return []


def skew_correction_tiles(group, *, include_empty: bool = False) -> dict:
    """{udim_tile: (width, height, float32 [height, width] array, row 0 = v bottom)}.

    Empty when nothing is painted (a tile whose values are all 0 is left out unless
    *include_empty*). The arrays are copies, safe to keep.
    """
    import numpy as np

    tiles = {}
    for key in _correction_keys(group):
        try:
            tile = int(key[len(SKEW_CORRECTION_PREFIX):])
            size = group.get(key + SKEW_CORRECTION_SIZE_SUFFIX)
            width, height = int(size[0]), int(size[1])
            values = np.asarray(group.get(key), dtype=np.float32)
        except Exception:
            continue
        if width <= 0 or height <= 0 or values.size != width * height:
            continue
        values = np.clip(values.reshape(height, width), 0.0, 1.0).astype(np.float32)
        if not include_empty and not bool((values > 0.0).any()):
            continue
        tiles[tile] = (width, height, values)
    return tiles


def has_skew_correction(group) -> bool:
    """Cheap test for the sidebar: whether the group stores any correction map."""
    return bool(_correction_keys(group))


def store_skew_correction_tile(group, tile: int, values) -> None:
    """Write one tile's map ([height, width], row 0 = v bottom) onto the group."""
    import numpy as np

    values = np.ascontiguousarray(np.clip(values, 0.0, 1.0), dtype=np.float32)
    height, width = values.shape
    key = f"{SKEW_CORRECTION_PREFIX}{int(tile)}"
    group[key] = values.reshape(-1)
    group[key + SKEW_CORRECTION_SIZE_SUFFIX] = [int(width), int(height)]


def clear_skew_correction(group) -> int:
    """Remove every correction map from the group. Returns tiles removed."""
    removed = 0
    for key in _correction_keys(group):
        for name in (key, key + SKEW_CORRECTION_SIZE_SUFFIX):
            try:
                del group[name]
            except Exception:
                pass
        removed += 1
    return removed


def skew_correction_digest(group) -> str:
    """Content identity of the group's painted correction maps ("" when none)."""
    import hashlib

    parts = []
    for tile, (width, height, values) in sorted(skew_correction_tiles(group).items()):
        digest = hashlib.blake2b(values.tobytes(), digest_size=8).hexdigest()
        parts.append(f"{tile}x{width}x{height}:{digest}")
    return "|".join(parts)
