"""The high mesh's corner colour stream, and which mesh data fills it.

The backend bakes exactly one per-corner RGB stream per high mesh: the VERTEX_COLOR
map projects it, and an ID map with the Vertex Color source reads it. Historically
that stream was always the mesh's active colour attribute. An ATTRIBUTE row bakes any
named attribute instead (a Geometry Nodes mask, a sculpt mask, a float or vector field)
by filling the same stream from that attribute, remapped into 0..1. The backend never
learns the difference: the job carries ATTRIBUTE rows as VERTEX_COLOR on the wire
(:func:`backend_wire_map_type`).

One stream per high mesh means one SOURCE per bake job. Rows that need different
sources bake as separate stages (operators splits them, see :func:`partition_rows`).
Cycles reads attributes straight from Blender per row, so it never needs that split.

bpy-free apart from the duck-typed mesh access, so the conversions are unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import rna_buffers
from . import constants

SOURCE_ACTIVE = "ACTIVE"
SOURCE_ATTRIBUTE = "ATTRIBUTE"

#: Attribute data types an ATTRIBUTE row can bake: foreach_get property, component
#: count, numpy dtype name. Matrices and strings have no colour meaning and are refused.
_ATTRIBUTE_LAYOUTS: dict[str, tuple[str, int, str]] = {
    "FLOAT": ("value", 1, "float32"),
    "INT": ("value", 1, "intc"),
    "INT8": ("value", 1, "int8"),
    "BOOLEAN": ("value", 1, "bool"),
    "FLOAT2": ("vector", 2, "float32"),
    "INT32_2D": ("value", 2, "int32"),
    "INT16_2D": ("value", 2, "int16"),
    "FLOAT_VECTOR": ("vector", 3, "float32"),
    "FLOAT_COLOR": ("color", 4, "float32"),
    "BYTE_COLOR": ("color", 4, "float32"),
    "QUATERNION": ("value", 4, "float32"),
}

_BAKEABLE_DOMAINS = frozenset({"POINT", "EDGE", "FACE", "CORNER"})


@dataclass(frozen=True, slots=True)
class ColorStreamSource:
    """What fills the corner colour stream of every high mesh in one bake job."""

    kind: str = SOURCE_ACTIVE
    attribute_name: str = ""
    range_min: float = 0.0
    range_max: float = 1.0

    @property
    def is_active_color(self) -> bool:
        return self.kind == SOURCE_ACTIVE

    @property
    def cache_key(self) -> str:
        """Identity of the stream CONTENT, for reusing a cached high mesh export.

        The active-colour key is the empty string so every cache entry written before
        ATTRIBUTE rows existed (which only ever held active colours) still matches.
        """
        if self.is_active_color:
            return ""
        return f"attr:{self.attribute_name}:{self.range_min!r}:{self.range_max!r}"


ACTIVE_COLOR_SOURCE = ColorStreamSource()


def backend_wire_map_type(map_type: str) -> str:
    """The map type the backend receives for ``map_type`` (see wire_types).

    An ATTRIBUTE row IS the backend's VERTEX_COLOR map over a different stream, so it
    travels as VERTEX_COLOR; the addon keeps ATTRIBUTE for naming and output tracking.
    """
    from .wire_types import backend_wire_map_type as _wire

    return _wire(map_type)


def row_attribute_source(map_setting) -> ColorStreamSource:
    """The stream an ATTRIBUTE row bakes (its name and range, as configured)."""
    return ColorStreamSource(
        kind=SOURCE_ATTRIBUTE,
        attribute_name=str(getattr(map_setting, "attribute_name", "") or "").strip(),
        range_min=float(getattr(map_setting, "attribute_range_min", 0.0) or 0.0),
        range_max=float(getattr(map_setting, "attribute_range_max", 1.0)),
    )


def row_color_source(map_setting) -> ColorStreamSource | None:
    """The corner colour stream a map row reads, or None when it reads none."""
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if map_type == constants.MAP_VERTEX_COLOR:
        return ACTIVE_COLOR_SOURCE
    if map_type == constants.MAP_ATTRIBUTE:
        return row_attribute_source(map_setting)
    if map_type == constants.MAP_ID:
        id_source = str(getattr(map_setting, "id_source", constants.MAP_ID_SOURCE_OBJECT) or "")
        if id_source == constants.MAP_ID_SOURCE_VERTEX_COLOR:
            return ACTIVE_COLOR_SOURCE
    return None


def partition_rows(map_settings) -> list[tuple[ColorStreamSource | None, list]]:
    """Split rows into bakeable stages: one per distinct colour stream source.

    The first stage holds every row that reads no stream plus the rows of the FIRST
    source in stack order, so a job with a single source is never split. Each further
    source is its own stage, in stack order.
    """
    order: list[ColorStreamSource] = []
    by_source: dict[ColorStreamSource, list] = {}
    streamless: list = []
    for map_setting in map_settings:
        source = row_color_source(map_setting)
        if source is None:
            streamless.append(map_setting)
            continue
        if source not in by_source:
            order.append(source)
            by_source[source] = []
        by_source[source].append(map_setting)
    if not order:
        return [(None, streamless)] if streamless else []
    stages: list[tuple[ColorStreamSource | None, list]] = [(order[0], streamless + by_source[order[0]])]
    stages.extend((source, by_source[source]) for source in order[1:])
    return stages


def job_color_source(map_settings) -> ColorStreamSource | None:
    """The single stream source a job's rows need; None when no row reads colours.

    Raises ValueError when the rows need more than one source: the bake operator
    splits those into stages before a job is built, so reaching this is a bug.
    """
    sources = {source for source in (row_color_source(item) for item in map_settings) if source is not None}
    if not sources:
        return None
    if len(sources) > 1:
        raise ValueError(
            "One bake job can only carry one vertex color / attribute stream; "
            "these rows need: " + ", ".join(sorted(describe(source) for source in sources))
        )
    return next(iter(sources))


def describe(source: ColorStreamSource) -> str:
    if source.is_active_color:
        return "active color attribute"
    return f"attribute '{source.attribute_name}'"


def attribute_is_bakeable(attribute) -> bool:
    data_type = str(getattr(attribute, "data_type", "") or "").upper()
    domain = str(getattr(attribute, "domain", "") or "").upper()
    return data_type in _ATTRIBUTE_LAYOUTS and domain in _BAKEABLE_DOMAINS


def bakeable_attribute_names(mesh) -> list[str]:
    """Attribute names on ``mesh`` an ATTRIBUTE row can bake (internal '.' names excluded)."""
    names: list[str] = []
    for attribute in getattr(mesh, "attributes", None) or ():
        name = str(getattr(attribute, "name", "") or "")
        if not name or name.startswith(".") or not attribute_is_bakeable(attribute):
            continue
        names.append(name)
    return names


def _find_attribute(mesh, name: str):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None or not name:
        return None
    getter = getattr(attributes, "get", None)
    if callable(getter):
        return getter(name)
    for attribute in attributes:
        if str(getattr(attribute, "name", "") or "") == name:
            return attribute
    return None


def attribute_raw_components(attribute):
    """(domain, float32 array (n, k)) of an attribute's raw values, or None if unbakeable."""
    import numpy as np

    data_type = str(getattr(attribute, "data_type", "") or "").upper()
    domain = str(getattr(attribute, "domain", "") or "").upper()
    layout = _ATTRIBUTE_LAYOUTS.get(data_type)
    if layout is None or domain not in _BAKEABLE_DOMAINS:
        return None
    prop, width, dtype = layout
    data = getattr(attribute, "data", None)
    if data is None or not hasattr(data, "foreach_get"):
        return None
    count = len(data)
    flat = np.empty(count * width, dtype=np.dtype(dtype))
    if count:
        data.foreach_get(prop, flat)
    return domain, flat.reshape(count, width).astype(np.float32, copy=False)


def _to_rgb(components):
    """(n, k) components -> (n, 3): a scalar is grey, a 2D vector fills R/G, a
    colour or quaternion keeps its first three channels."""
    import numpy as np

    count, width = components.shape
    if width == 1:
        return np.repeat(components, 3, axis=1)
    if width == 2:
        return np.concatenate((components, np.zeros((count, 1), dtype=np.float32)), axis=1)
    return np.ascontiguousarray(components[:, :3])


def _expand_to_point_or_corner(mesh, domain: str, rows):
    """Bring FACE / EDGE rows onto a domain the stream writers index (POINT / CORNER)."""
    import numpy as np

    if domain in {"POINT", "CORNER"}:
        return domain, rows
    if domain == "FACE":
        polygons = mesh.polygons
        loop_totals = rna_buffers.empty_u32_for_rna(len(polygons))
        polygons.foreach_get("loop_total", loop_totals)
        loop_totals = rna_buffers.as_i32(loop_totals)
        loop_starts = rna_buffers.empty_u32_for_rna(len(polygons))
        polygons.foreach_get("loop_start", loop_starts)
        loop_starts = rna_buffers.as_i32(loop_starts)
        # Each polygon owns the contiguous loop run [loop_start, loop_start + loop_total);
        # walking polygons in loop_start order lays those runs end to end.
        order = np.argsort(loop_starts, kind="stable")
        loop_to_face = np.repeat(order, loop_totals[order])
        return "CORNER", rows[loop_to_face]
    # EDGE: average every edge touching a vertex.
    edges = mesh.edges
    edge_vertices = rna_buffers.empty_u32_for_rna(len(edges) * 2)
    edges.foreach_get("vertices", edge_vertices)
    edge_vertices = edge_vertices.astype(np.int64).reshape(-1, 2)
    vertex_count = len(mesh.vertices)
    sums = np.zeros((vertex_count, rows.shape[1]), dtype=np.float64)
    counts = np.zeros(vertex_count, dtype=np.int64)
    for column in (0, 1):
        np.add.at(sums, edge_vertices[:, column], rows)
        np.add.at(counts, edge_vertices[:, column], 1)
    averaged = (sums / np.maximum(counts, 1)[:, None]).astype(np.float32)
    return "POINT", averaged


def attribute_stream_rows(mesh, source: ColorStreamSource):
    """(domain "POINT"/"CORNER", float32 (n, 3) in 0..1) for an ATTRIBUTE source.

    A mesh without the attribute (or with an unbakeable one) bakes black: for a mask
    "not there" means 0, and the stream's neutral white would read as fully masked.
    """
    import numpy as np

    attribute = _find_attribute(mesh, source.attribute_name)
    raw = attribute_raw_components(attribute) if attribute is not None else None
    if raw is None:
        return "POINT", np.zeros((len(mesh.vertices), 3), dtype=np.float32)
    domain, components = raw
    rows = _to_rgb(components)
    span = float(source.range_max) - float(source.range_min)
    if span != 0.0:
        rows = (rows - np.float32(source.range_min)) / np.float32(span)
    rows = np.clip(rows, 0.0, 1.0).astype(np.float32, copy=False)
    return _expand_to_point_or_corner(mesh, domain, rows)


def attribute_value_range(meshes, attribute_name: str) -> tuple[float, float] | None:
    """Min and max over every component of ``attribute_name`` across ``meshes``."""
    import numpy as np

    low = None
    high = None
    for mesh in meshes:
        attribute = _find_attribute(mesh, attribute_name)
        raw = attribute_raw_components(attribute) if attribute is not None else None
        if raw is None or raw[1].size == 0:
            continue
        components = raw[1]
        if components.shape[1] == 4 and str(getattr(attribute, "data_type", "")).upper() in {"FLOAT_COLOR", "BYTE_COLOR"}:
            components = components[:, :3]
        finite = components[np.isfinite(components)]
        if finite.size == 0:
            continue
        mesh_low = float(finite.min())
        mesh_high = float(finite.max())
        low = mesh_low if low is None else min(low, mesh_low)
        high = mesh_high if high is None else max(high, mesh_high)
    if low is None or high is None:
        return None
    return low, high
