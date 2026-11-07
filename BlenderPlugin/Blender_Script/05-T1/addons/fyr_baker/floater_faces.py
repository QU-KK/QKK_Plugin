"""Floater faces: faces of a High mesh marked in Edit Mode that bake like a floater object.

A floater is detail that floats just above the surface (bolts, trims, decals). Baked as part
of the base it casts an AO ring onto the base that the finished asset should not have; the
per-object Casts AO toggle fixes that only when the floater is its own object. Marked faces
give a merged high (one ZBrush export) the same result:

- Mark / Clear Floater in Edit Mode stores a boolean FACE attribute, ``fyr_floater``.
- Export writes such a high twice: the body without the marked faces under the object's
  own name, and the marked faces as ``<object>__fyr_floater`` with Casts AO off. Casts AO
  is already per source on every route, so nothing new runs on the GPU. The backend treats
  that suffix as the same object wherever names are compared (Match By Isolation, the
  Object ID map): ``backend/src/backend_floater_faces.hpp``.
- The Automatic cage still fits them, as it fits a separate floater object: a floater
  above the surface only bakes into Normal if the cage reaches it (measured 2026-10-18:
  leaving them out of the fit dropped floating bolts from the Normal map).

A high with no marked faces exports, caches and bakes exactly as before.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager

#: The boolean FACE attribute marking floater faces.
ATTRIBUTE_NAME = "fyr_floater"
#: Mesh custom properties written by the operators: how many faces are marked, and a
#: counter bumped on every change. Their pair is the cache signature, so a mark change
#: re-exports the high without hashing the mask.
COUNT_PROP = "fyr_floater_count"
REVISION_PROP = "fyr_floater_revision"
#: Source-name suffix of the floater piece (backend kFloaterSourceSuffix).
FLOATER_NAME_SUFFIX = "__fyr_floater"

PART_BODY = "BODY"
PART_FLOATER = "FLOATER"
#: Every face, for consumers that need the whole object (Scene Blockers cast shadows with
#: their floater faces too).
PART_WHOLE = "WHOLE"

# The part an export is writing, keyed by the ORIGINAL object's pointer: writers receive
# either the object or its evaluated copy and resolve both to the original.
_EXPORT_PART: contextvars.ContextVar[tuple[int, str] | None] = contextvars.ContextVar(
    "fyr_floater_export_part", default=None
)


def _original_key(obj) -> int:
    original = getattr(obj, "original", None) or obj
    try:
        return int(original.as_pointer())
    except Exception:
        return id(original)


def _mesh_data(obj):
    data = getattr(obj, "data", None)
    return data if getattr(obj, "type", None) == "MESH" else None


def marked_face_count(obj) -> int:
    """How many faces of ``obj``'s mesh are marked (0 when none or not a mesh)."""
    data = _mesh_data(getattr(obj, "original", None) or obj)
    if data is None:
        return 0
    try:
        return max(0, int(data.get(COUNT_PROP, 0) or 0))
    except Exception:
        return 0


def has_floater_faces(obj) -> bool:
    return marked_face_count(obj) > 0


def signature(obj) -> tuple:
    """Cache-signature term: ``()`` without marked faces, so existing keys never change."""
    count = marked_face_count(obj)
    if count <= 0:
        return ()
    data = _mesh_data(getattr(obj, "original", None) or obj)
    try:
        revision = int(data.get(REVISION_PROP, 0) or 0)
    except Exception:
        revision = 0
    return ("floater-faces", count, revision)


def floater_object_name(name: str) -> str:
    return f"{name}{FLOATER_NAME_SUFFIX}"


def source_family(name: str) -> str:
    """``name`` without the floater suffix: the object a source belongs to."""
    text = str(name or "")
    if len(text) > len(FLOATER_NAME_SUFFIX) and text.endswith(FLOATER_NAME_SUFFIX):
        return text[: -len(FLOATER_NAME_SUFFIX)]
    return text


@contextmanager
def export_part(obj, part: str):
    """Within this block, exports of ``obj`` write only ``part`` (PART_BODY / PART_FLOATER)."""
    token = _EXPORT_PART.set((_original_key(obj), str(part)))
    try:
        yield
    finally:
        _EXPORT_PART.reset(token)


def current_part(obj) -> str | None:
    active = _EXPORT_PART.get()
    if active is None or obj is None:
        return None
    key, part = active
    return part if key == _original_key(obj) else None


def cache_token(obj) -> tuple:
    """Cache-key term for exports: the mark signature plus the part being written."""
    sig = signature(obj)
    if not sig:
        return ()
    return sig + (current_part(obj) or "WHOLE",)


def filter_export_mesh(obj, mesh) -> None:
    """Drop the faces outside the active export part from ``mesh``, a ``to_mesh`` copy.

    No-op unless an :func:`export_part` block names ``obj``. The body keeps every unmarked
    face, the floater piece every marked one; vertices and edges only the dropped faces used
    go with them. bmesh carries every layer (normals, UVs, colours, attributes) across.
    """
    part = current_part(obj)
    if part in (None, PART_WHOLE) or mesh is None:
        return
    attribute = mesh.attributes.get(ATTRIBUTE_NAME)
    if attribute is None or attribute.domain != "FACE":
        if part == PART_FLOATER:
            raise ValueError(f"'{getattr(obj, 'name', '')}' has no floater faces to export")
        return
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = bm.faces.layers.bool.get(ATTRIBUTE_NAME)
        if layer is None:
            return
        drop_marked = part == PART_BODY
        doomed = [face for face in bm.faces if bool(face[layer]) == drop_marked]
        if not doomed:
            return
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(mesh)
    finally:
        bm.free()


def triangle_marked_mask(mesh):
    """Per loop triangle of ``mesh``: True where its face is marked. None without marks.

    Reads ``mesh.loop_triangles`` as they are (callers have computed them).
    """
    import numpy as np

    attribute = mesh.attributes.get(ATTRIBUTE_NAME) if mesh is not None else None
    if attribute is None or attribute.domain != "FACE":
        return None
    face_count = len(mesh.polygons)
    triangles = mesh.loop_triangles
    triangle_count = len(triangles)
    if face_count <= 0 or triangle_count <= 0:
        return None
    marked = np.zeros(face_count, dtype=bool)
    attribute.data.foreach_get("value", marked)
    if not marked.any():
        return None
    # uintc: the buffer format Blender's foreach_get fast path matches for this property.
    polygon_index = np.empty(triangle_count, dtype=np.uintc)
    triangles.foreach_get("polygon_index", polygon_index)
    polygon_index = polygon_index.view(np.int32)
    return marked[polygon_index]


def reorder_export_triangles(mesh, per_triangle):
    """``per_triangle`` (first axis = ``mesh``'s loop triangles) in split-export order.

    A high with marked faces exports its body, then its floater piece; each keeps its faces'
    triangles in their original order (bmesh deletion and re-triangulation keep the face
    order). So the per-triangle sidecars of such a high are its body rows, then its floater
    rows. Unchanged without marks.
    """
    import numpy as np

    mask = triangle_marked_mask(mesh)
    if mask is None or len(mask) != len(per_triangle):
        return per_triangle
    return np.concatenate([np.asarray(per_triangle)[~mask], np.asarray(per_triangle)[mask]])


def set_marked(obj, bm, value: bool, *, selected_only: bool = True) -> tuple[int, int]:
    """Mark (or clear) the selected faces of an edit-mode bmesh. Returns (changed, total)."""
    layer = bm.faces.layers.bool.get(ATTRIBUTE_NAME)
    if layer is None:
        if not value:
            return 0, 0
        layer = bm.faces.layers.bool.new(ATTRIBUTE_NAME)
    changed = 0
    total = 0
    for face in bm.faces:
        if (face.select or not selected_only) and bool(face[layer]) != value:
            face[layer] = value
            changed += 1
        if face[layer]:
            total += 1
    if total == 0:
        bm.faces.layers.bool.remove(layer)
    data = obj.data
    data[COUNT_PROP] = int(total)
    if changed:
        data[REVISION_PROP] = int(data.get(REVISION_PROP, 0) or 0) + 1
    if total == 0:
        for prop in (COUNT_PROP, REVISION_PROP):
            if prop in data:
                del data[prop]
    return changed, total
