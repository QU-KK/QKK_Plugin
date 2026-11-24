"""Reading big meshes without leaving copies behind in Blender.

Blender's RNA reads of mesh geometry are not free after they return. A read of positions or
corner vertices takes write access, which un-shares a full copy of that array on the mesh it
reads, and corner tris and vertex/face/corner normals are cached on the mesh. On the
evaluated or original mesh all of that lives as long as the mesh does, which in the UI is the
session. Measured on SvAT (87.4M high triangles): a bake's PREPARE took Blender's commit from
5.8 to 13.2 GB and held it through the bake.

Reading a ``to_mesh`` copy instead keeps everything on the copy. The copy is cheap (every
layer implicitly shared, no modifier re-evaluation) and ``to_mesh_clear`` frees it. The caches
need one more step, see :func:`detach_mesh_runtime_caches`.
"""

from __future__ import annotations

from contextlib import contextmanager


def detach_mesh_runtime_caches(mesh) -> None:
    """Give a ``to_mesh`` copy runtime caches of its own, so ``to_mesh_clear`` frees them.

    A copy shares its corner-tri and normal caches with the mesh it was copied from, so
    caches computed while reading the copy outlive it (1.68 GB of the 2.24 GB SvAT's 41.4M
    triangle PM3D_Cylinder3D8 left behind). Writing one position back to itself is Blender's
    positions-changed tag: it gives the copy fresh caches it alone owns. No value changes, so
    everything read from the copy is identical.
    """
    vertices = getattr(mesh, "vertices", None)
    if vertices is None or len(vertices) == 0:
        return
    vertex = vertices[0]
    vertex.co = tuple(vertex.co)


def ensure_object_ready(obj) -> None:
    """A high that high_poly_park is still bringing back (timer slices after a bake)
    comes back now, before the caller reads its mesh. A no-op while a bake runs (the
    park is what keeps the memory free) and for everything that was never parked."""
    try:
        from . import high_poly_park

        if high_poly_park.is_parked():
            high_poly_park.ensure_restored([obj], only_when_idle=True)
    except Exception:  # noqa: BLE001 - never break a capture over the park bookkeeping
        pass


@contextmanager
def evaluated_mesh_copy(obj, depsgraph):
    """Yield ``(obj_eval, mesh)``: a cache-detached ``to_mesh`` copy of the evaluated object.

    ``mesh`` is None when the object has no mesh geometry. The copy is cleared on exit.
    """
    ensure_object_ready(obj)
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    try:
        if mesh is not None:
            detach_mesh_runtime_caches(mesh)
        yield obj_eval, mesh
    finally:
        obj_eval.to_mesh_clear()


def element_count(owner, name: str) -> int:
    """``len(owner.<name>)`` for a mesh element collection, 0 when there is none.

    Never truth-test a bpy mesh collection (``mesh.vertices or ()``, ``if mesh.polygons:``):
    ``bool()`` begins an iteration, and beginning one over vertices, edges, polygons or loops
    takes write access, which un-shares that whole array on the mesh for as long as the mesh
    lives. ``len()`` reads the stored count. Measured on SvAT's PM3D_Cylinder3D8 (20.7M quads):
    ``bool()`` kept +240 MB (vertices), +321 MB (edges), +80 MB (polygons), +321 MB (loops);
    ``len()`` kept nothing.
    """
    collection = getattr(owner, name, None)
    return 0 if collection is None else len(collection)


# ---- Fast array reads --------------------------------------------------------------------
#
# Blender's ``foreach_get`` takes its memcpy path only when the buffer's format character is
# the property's exactly (see rna_buffers); a numpy array built with an explicit dtype such as
# "<u4" or "<f4" reports 'L' / '<f' and drops to a per-element loop (about 40 ns per value).
# Reading the generic ``position`` and ``.corner_vert`` attributes and the ``corner_normals``
# vectors into native-format arrays is 20 to 45 times faster than ``vertices.co`` /
# ``loop_triangles.vertices`` / ``loop_triangles.split_normals`` and returns the same values.

def is_all_triangles(mesh) -> bool:
    """True when every face of ``mesh`` is a triangle (``len`` only, nothing un-shared).

    Then triangle i is loops 3i..3i+2, in that order, so corner-ordered attributes ARE the
    triangle-corner order of ``loop_triangles``."""
    polygons = getattr(mesh, "polygons", None)
    loops = getattr(mesh, "loops", None)
    if polygons is None or loops is None:
        return False
    face_count = len(polygons)
    return face_count > 0 and len(loops) == 3 * face_count


def _flat_attribute_read(mesh, name: str, data_type: str, domain: str, length: int, prop: str, out) -> bool:
    attributes = getattr(mesh, "attributes", None)
    getter = getattr(attributes, "get", None) if attributes is not None else None
    if getter is None:
        return False
    try:
        layer = getter(name)
        if (
            layer is None
            or str(getattr(layer, "data_type", "")) != data_type
            or str(getattr(layer, "domain", "")) != domain
        ):
            return False
        data = layer.data
        if len(data) != length:
            return False
        data.foreach_get(prop, out)
        return True
    except Exception:
        return False


def read_positions_flat(mesh, out) -> bool:
    """Fill the float32 (native format) ``out`` of 3*vertex_count with the vertex
    coordinates; False when the attribute read does not apply (use ``vertices.co``)."""
    return _flat_attribute_read(mesh, "position", "FLOAT_VECTOR", "POINT", len(mesh.vertices), "vector", out)


def read_corner_verts_flat(mesh, out) -> bool:
    """Fill the intc ``out`` of loop_count with each corner's vertex index (``.corner_vert``)."""
    return _flat_attribute_read(mesh, ".corner_vert", "INT", "CORNER", len(mesh.loops), "value", out)


def read_corner_normals_flat(mesh, out) -> bool:
    """Fill the float32 (native format) ``out`` of 3*loop_count with the corner normals."""
    corner_normals = getattr(mesh, "corner_normals", None)
    if corner_normals is None or not hasattr(corner_normals, "foreach_get"):
        return False
    try:
        if len(corner_normals) * 3 != len(out):
            return False
        corner_normals.foreach_get("vector", out)
        return True
    except Exception:
        return False
