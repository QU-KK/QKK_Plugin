"""One bake group per material of a low mesh: Painter's texture set per material.

``group.low_material`` restricts a bake group to the faces of its low meshes that use that
material, so one low object with four materials can sit in four groups and bake into four
texture sets. A group with no material set bakes whole objects, exactly as before.

What a restricted group changes, and what it deliberately does not:

- The exported low keeps only the material's faces, but its corner normals are read from
  the WHOLE mesh first and written back as custom normals. Shading along a border between
  two materials therefore matches on both sides, which separating the mesh does not do.
- The Automatic cage is captured from the whole mesh and then cut down, for the same reason.
- High meshes are untouched: every material bakes from the same source.

Export code runs inside :func:`group_scope`, keyed by the original objects (writers receive
either the object or its evaluated copy), the same pattern as ``floater_faces.export_part``.
"""

from __future__ import annotations

import contextvars
import hashlib
from contextlib import contextmanager

# (original object pointers, material name) of the scope being exported.
_SCOPE: contextvars.ContextVar[tuple[frozenset, str] | None] = contextvars.ContextVar(
    "fyr_low_material_scope", default=None
)

#: Bake target of the materials a restricted Cycles pass must not write into the output.
DISCARD_IMAGE_NAME = "__mb_bake_discard__"


def _original_key(obj) -> int:
    original = getattr(obj, "original", None) or obj
    try:
        return int(original.as_pointer())
    except Exception:
        return id(original)


def group_material_name(group) -> str:
    """The material ``group`` is restricted to, "" when it bakes whole objects."""
    material = getattr(group, "low_material", None)
    return str(getattr(material, "name", "") or "") if material is not None else ""


@contextmanager
def object_scope(objects, material_name: str):
    """Within this block, ``objects`` read as only the faces of ``material_name``."""
    name = str(material_name or "")
    if not name:
        yield
        return
    token = _SCOPE.set((frozenset(_original_key(obj) for obj in objects if obj is not None), name))
    try:
        yield
    finally:
        _SCOPE.reset(token)


@contextmanager
def group_scope(group):
    """Within this block, ``group``'s low meshes read as its material's faces only."""
    name = group_material_name(group)
    if not name:
        yield
        return
    # Flat slots first, as the exporter does; the role-state slots are the UI's copy.
    role_state = getattr(group, "role_assignments", None)
    slots = list(getattr(group, "low_meshes", []) or []) + list(getattr(role_state, "low_meshes", []) or [])
    with object_scope([getattr(slot, "object_ref", None) for slot in slots], name):
        yield


def current_material_name(obj) -> str:
    """The material ``obj`` is being read as, "" outside a scope that names it."""
    active = _SCOPE.get()
    if active is None or obj is None:
        return ""
    keys, name = active
    return name if _original_key(obj) in keys else ""


def _original_slot_materials(obj) -> list:
    # Lazy: this module is imported by code the unit tests load without bpy.
    from . import preview_materials

    return preview_materials.original_slot_materials(obj)


def _slot_material_names(obj) -> list[str]:
    original = getattr(obj, "original", None) or obj
    return [
        str(getattr(material, "name", "") or "") if material is not None else ""
        for material in _original_slot_materials(original)
    ]


def _face_material_indices(mesh):
    import numpy as np

    polygons = getattr(mesh, "polygons", None)
    count = len(polygons) if polygons is not None else 0
    indices = np.zeros(count, dtype=np.int32)
    if count:
        polygons.foreach_get("material_index", indices)
    return indices


def used_materials(obj) -> list:
    """The materials faces of ``obj`` actually use, in slot order, each once.

    An unused slot is not a texturing decision, so it gets no texture set.
    """
    import numpy as np

    mesh = getattr(obj, "data", None)
    if getattr(obj, "type", None) != "MESH" or mesh is None:
        return []
    materials = _original_slot_materials(obj)
    used = {int(index) for index in np.unique(_face_material_indices(mesh))}
    result = []
    seen = set()
    for index, material in enumerate(materials):
        if index not in used or material is None:
            continue
        if material.name in seen:
            continue
        seen.add(material.name)
        result.append(material)
    return result


def face_mask(obj, mesh, material_name: str):
    """Per face of ``mesh``: True where it belongs to ``material_name``.

    Faces on an empty slot go with the object's first used material, so no face of a mesh
    is ever left out of every set.
    """
    import numpy as np

    indices = _face_material_indices(mesh)
    names = _slot_material_names(obj)
    used = [int(index) for index in np.unique(indices)]

    def _is_named(index: int) -> bool:
        return 0 <= index < len(names) and bool(names[index])

    named = [index for index in used if _is_named(index)]
    if not named:
        return np.ones(len(indices), dtype=bool)
    wanted = {index for index in named if names[index] == material_name}
    if named and names[named[0]] == material_name:
        wanted.update(index for index in used if not _is_named(index))
    return np.isin(indices, sorted(wanted))


def has_faces(obj, material_name: str) -> bool:
    mesh = getattr(obj, "data", None)
    if mesh is None or not len(getattr(mesh, "polygons", ()) or ()):
        return False
    return bool(face_mask(obj, mesh, material_name).any())


def signature_term(obj) -> tuple:
    """Cache-signature term: ``()`` outside a scope, so existing keys never change.

    Hashes which faces are in, because reassigning faces between materials changes no
    count or position that the rest of the signature sees.
    """
    name = current_material_name(obj)
    if not name:
        return ()
    original = getattr(obj, "original", None) or obj
    mesh = getattr(original, "data", None)
    digest = hashlib.blake2b(face_mask(original, mesh, name).tobytes(), digest_size=8).hexdigest() if mesh else ""
    return (("low-material", name, digest),)


def scope_signature(objects) -> tuple:
    """:func:`signature_term` of every object: the fit of a material's faces is its own."""
    return tuple(signature_term(obj) for obj in objects or ())


def filter_export_mesh(obj, mesh) -> None:
    """Drop the faces of other materials from ``mesh``, a ``to_mesh`` copy.

    Corner normals are read before the delete and written back after it: recomputing them
    would change shading wherever a border between two materials is not a hard edge.
    """
    name = current_material_name(obj)
    if not name or mesh is None:
        return
    import bmesh
    import numpy as np

    mask = face_mask(obj, mesh, name)
    if mask.all():
        return
    polygons = mesh.polygons
    loop_count = len(mesh.loops)
    totals = np.zeros(len(polygons), dtype=np.int32)
    polygons.foreach_get("loop_total", totals)
    normals = np.zeros(loop_count * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", normals)
    # Corners are stored face after face.
    corner_kept = np.repeat(mask, totals)
    kept_normals = normals.reshape(-1, 3)[corner_kept]

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        doomed = [face for face, keep in zip(bm.faces, mask.tolist()) if not keep]
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if len(mesh.loops) == len(kept_normals):
        mesh.normals_split_custom_set(kept_normals.tolist())


def triangle_mask(obj, mesh, material_name: str | None = None):
    """Per loop triangle of ``mesh``: True where its face is in, or None to keep them all.

    ``mesh.loop_triangles`` must be calculated. Outside a scope, pass ``material_name``.
    """
    import numpy as np

    name = material_name or current_material_name(obj)
    if not name:
        return None
    triangles = mesh.loop_triangles
    faces = face_mask(obj, mesh, name)
    # uintc: the buffer format Blender's foreach_get fast path matches for this property.
    polygon_index = np.empty(len(triangles), dtype=np.uintc)
    triangles.foreach_get("polygon_index", polygon_index)
    return faces[polygon_index.view(np.int32)]


def subset_cage_triangles(obj, depsgraph, triangles):
    """Cut a whole-mesh cage capture down to the scope's faces (no-op outside a scope)."""
    name = current_material_name(obj)
    if not name or not triangles:
        return triangles
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        mask = triangle_mask(obj, mesh, name)
    finally:
        evaluated.to_mesh_clear()
    if mask is None or len(mask) != len(triangles):
        return triangles
    subset = getattr(triangles, "subset", None)
    if callable(subset):
        return subset(mask)
    return [triangle for triangle, keep in zip(triangles, mask.tolist()) if keep]


def expand_cage_corners(low, world_corners, material_name: str):
    """A whole-low corner array from a restricted group's cage corners, or None.

    Blender's cage has to match the whole object. Corners of other materials stay on the
    low: those faces bake into the discard image, so their reach does not matter.
    """
    import bpy
    import numpy as np

    from . import rna_buffers

    evaluated = low.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        mask = triangle_mask(low, mesh, material_name)
        triangle_count = len(mesh.loop_triangles)
        loops = rna_buffers.empty_u32_for_rna(triangle_count * 3)
        mesh.loop_triangles.foreach_get("loops", loops)
        loops = rna_buffers.as_i32(loops)
        corner_verts = rna_buffers.empty_u32_for_rna(len(mesh.loops))
        mesh.loops.foreach_get("vertex_index", corner_verts)
        corner_verts = rna_buffers.as_i32(corner_verts)
        positions = np.zeros(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", positions)
        positions = positions.reshape(-1, 3)
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
    finally:
        evaluated.to_mesh_clear()
    corners = np.asarray(world_corners, dtype=np.float32).reshape(-1, 3)
    corner_kept = np.repeat(mask, 3)
    if int(corner_kept.sum()) != len(corners):
        return None
    local = positions[corner_verts[loops]]
    whole = (matrix[:3, :3] @ local.T).T + matrix[:3, 3]
    whole = whole.astype(np.float32)
    whole[corner_kept] = corners
    return whole


def discard_image():
    """A tiny image for the slots a restricted Cycles pass must not write to the output.

    Blender needs an active image in every material of a baked object. Node removal leaves
    this at zero users, so Blender drops it on save.
    """
    import bpy

    image = bpy.data.images.get(DISCARD_IMAGE_NAME)
    if image is None:
        image = bpy.data.images.new(DISCARD_IMAGE_NAME, 16, 16, alpha=True)
    return image


# The material the running Cycles projection step writes. Steps run one at a time, and the
# value reaches the pass that injects bake targets through several layers of job objects.
_CYCLES_ONLY_MATERIAL = ""


def set_cycles_only_material(material_name: str) -> None:
    global _CYCLES_ONLY_MATERIAL
    _CYCLES_ONLY_MATERIAL = str(material_name or "")


def cycles_only_material() -> str:
    return _CYCLES_ONLY_MATERIAL


def bake_image_for_material(material, image, only_material: str):
    """The image a Cycles pass writes this material's faces into."""
    if not only_material or str(getattr(material, "name", "") or "") == only_material:
        return image
    return discard_image()
