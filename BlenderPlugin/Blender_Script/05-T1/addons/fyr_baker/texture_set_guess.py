"""Spot sculpt-app placeholder materials before they split a project into texture sets.

ZBrush's GoZ / GoB bridge gives every mesh it sends to Blender its own material,
named after the mesh. Per Material texture sets then make one set per mesh, which
artists rarely notice until they open the bake in Painter and find six texture sets
for six rocks. A material named after its own mesh says nothing about how the asset
is meant to be textured, so the auto-build treats it like no material, but only
when those meshes can actually share one texture: their UVs must not overlap each
other. When they do overlap (every rock fills the whole 0-1 square), separate sets
are the only bake that works, and the placeholder sets are kept.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np

from . import matching
from .paint_brush_core import rasterize_uv_triangles

#: Occupancy grid per UV tile for the overlap test. Coarse on purpose: it only has to
#: tell "laid out side by side" from "stacked on top of each other".
OVERLAP_GRID = 256

#: Share of the smaller mesh's covered texels that may also be covered by another mesh.
#: Islands packed edge to edge share a few boundary texels; stacked layouts share most.
OVERLAP_TOLERANCE = 0.02

_DUPLICATE_SUFFIX = re.compile(r"\.\d{3,}$")
_BRIDGE_PREFIXES = ("gob_", "goz_")


def _name_key(name: str) -> str:
    text = _DUPLICATE_SUFFIX.sub("", str(name or "").strip()).casefold()
    for prefix in _BRIDGE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return "".join(c for c in text if c.isalnum())


def _name_keys(name: str) -> set[str]:
    keys = {_name_key(name)}
    stripped = matching.strip_role_suffix(_DUPLICATE_SUFFIX.sub("", str(name or "").strip()))
    keys.add(_name_key(stripped))
    keys.discard("")
    return keys


def is_placeholder_material(material_name: str, mesh_names: Iterable[str]) -> bool:
    """True when a material is just named after the mesh (object or mesh data) it is on."""
    material_keys = _name_keys(material_name)
    if not material_keys:
        return False
    for mesh_name in mesh_names:
        if material_keys & _name_keys(mesh_name):
            return True
    return False


def _occupancy(tri_uvs: np.ndarray, grid: int) -> np.ndarray:
    """Flat occupied-texel keys of one mesh, each UDIM tile in its own key range."""
    uvs = np.asarray(tri_uvs, dtype=np.float64).reshape(-1, 3, 2)
    if uvs.shape[0] == 0:
        return np.empty(0, dtype=np.int64)
    centroid = uvs.mean(axis=1)
    tile_u = np.floor(centroid[:, 0]).astype(np.int64)
    tile_v = np.floor(centroid[:, 1]).astype(np.int64)
    keys = []
    for tu, tv in set(zip(tile_u.tolist(), tile_v.tolist())):
        members = (tile_u == tu) & (tile_v == tv)
        local = uvs[members] - np.array([tu, tv], dtype=np.float64)
        texels, _tri, _bary = rasterize_uv_triangles(local, grid, grid)
        tile_id = (tv + 1024) * 2048 + (tu + 1024)
        keys.append(texels + tile_id * grid * grid)
    return np.unique(np.concatenate(keys)) if keys else np.empty(0, dtype=np.int64)


def uv_layouts_overlap(
    meshes_tri_uvs: Sequence[np.ndarray],
    *,
    grid: int = OVERLAP_GRID,
    tolerance: float = OVERLAP_TOLERANCE,
) -> bool:
    """True when any two meshes' UVs cover the same texels beyond edge contact.

    Overlap inside one mesh (mirrored or stacked islands) is the artist's choice
    and is ignored; only overlap between meshes stops them sharing a texture set.
    """
    occupied = [texels for texels in (_occupancy(tri_uvs, grid) for tri_uvs in meshes_tri_uvs) if texels.size]
    for index, first in enumerate(occupied):
        for second in occupied[index + 1:]:
            shared = np.intersect1d(first, second, assume_unique=True).size
            # Measured against the smaller mesh, so a small rock stacked inside a big
            # rock's island still counts as overlap.
            if shared > max(4, int(tolerance * min(first.size, second.size))):
                return True
    return False
