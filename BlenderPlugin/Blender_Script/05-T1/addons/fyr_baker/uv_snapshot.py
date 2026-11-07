from __future__ import annotations

"""Durable Blender-native UV snapshot ownership and exact restore planning."""

from dataclasses import dataclass
import hashlib
import math
import struct
import uuid

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - pure tests run without Blender
    bpy = None


SCHEMA_VERSION = 1
OBJECT_UUID_KEY = "_fyr_baker_uv_snapshot_object_uuid"
PAYLOAD_PREFIX = ".FyrBaker_UVSnapshot_"


@dataclass(frozen=True)
class ExactRestorePlan:
    topology_fingerprint: str
    source_layer_name: str
    values: tuple[tuple[float, float], ...]


def topology_fingerprint_from_data(
    vertex_count: int,
    edge_count: int,
    polygon_loop_ranges,
    loop_vertex_indices,
    edge_vertex_indices=(),
) -> str:
    """Hash full face-corner connectivity while deliberately excluding positions."""
    digest = hashlib.sha256()
    ranges = tuple((int(start), int(total)) for start, total in polygon_loop_ranges)
    loop_vertices = tuple(int(index) for index in loop_vertex_indices)
    edges = tuple((int(a), int(b)) for a, b in edge_vertex_indices)
    digest.update(struct.pack("<QQQQ", int(vertex_count), int(edge_count), len(ranges), len(loop_vertices)))
    for start, total in ranges:
        digest.update(struct.pack("<QQ", start, total))
    for vertex_index in loop_vertices:
        digest.update(struct.pack("<Q", vertex_index))
    for a, b in edges:
        digest.update(struct.pack("<QQ", a, b))
    return digest.hexdigest()


def topology_fingerprint(mesh) -> str:
    return topology_fingerprint_from_data(
        len(mesh.vertices),
        len(mesh.edges),
        ((polygon.loop_start, polygon.loop_total) for polygon in mesh.polygons),
        (loop.vertex_index for loop in mesh.loops),
        (edge.vertices for edge in mesh.edges),
    )


def uv_values(layer) -> tuple[tuple[float, float], ...]:
    values = tuple((float(item.uv[0]), float(item.uv[1])) for item in layer.data)
    if not all(math.isfinite(value) for uv in values for value in uv):
        raise ValueError("UV layer contains non-finite coordinates")
    return values


def object_uuid(obj) -> str:
    try:
        return str(obj.get(OBJECT_UUID_KEY, "") or "").strip()
    except Exception:
        return ""


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _same_blender_id(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if a is b or a == b:
        return True
    try:
        return a.as_pointer() == b.as_pointer()
    except Exception:
        return False


def ensure_object_uuid(obj, settings) -> str:
    current = object_uuid(obj)
    conflicting_owner = False
    if current:
        for snapshot in getattr(settings, "uv_snapshots", []):
            if str(getattr(snapshot, "source_object_uuid", "") or "") != current:
                continue
            owner = getattr(snapshot, "source_object_ref", None)
            if owner is not None and not _same_blender_id(owner, obj):
                conflicting_owner = True
                break
    if not current or conflicting_owner:
        current = _new_uuid()
        obj[OBJECT_UUID_KEY] = current
    return current


def _uuid_owner_count(identity: str, objects=None) -> int:
    """How many objects in the file carry this snapshot UUID (stops at 2)."""
    if objects is None:
        if bpy is None:
            return 1
        try:
            objects = bpy.data.objects
        except Exception:
            return 1
    count = 0
    for candidate in objects:
        try:
            if object_uuid(candidate) == identity:
                count += 1
        except Exception:
            continue
        if count > 1:
            break
    return count


def find_snapshot(settings, obj, *, objects=None):
    for snapshot in getattr(settings, "uv_snapshots", []):
        if _same_blender_id(getattr(snapshot, "source_object_ref", None), obj):
            return snapshot
    identity = object_uuid(obj)
    if not identity:
        return None
    # Re-adopting an orphaned snapshot (its object was deleted) by UUID is only
    # safe when exactly one object carries that UUID: Shift+D duplicates inherit
    # the custom property, so after deleting the original every duplicate would
    # otherwise claim the snapshot and Restore would write the original's UVs
    # onto each of them without a warning.
    if _uuid_owner_count(identity, objects) > 1:
        return None
    for snapshot in getattr(settings, "uv_snapshots", []):
        if (
            getattr(snapshot, "source_object_ref", None) is None
            and str(getattr(snapshot, "source_object_uuid", "") or "") == identity
        ):
            return snapshot
    return None


def snapshot_index(settings, target) -> int:
    target_pointer = getattr(target, "as_pointer", lambda: None)()
    for index, snapshot in enumerate(getattr(settings, "uv_snapshots", [])):
        if snapshot is target:
            return index
        if target_pointer is not None and getattr(snapshot, "as_pointer", lambda: None)() == target_pointer:
            return index
    return -1


def _build_payload(source_mesh, source_layer, snapshot_uuid: str):
    if bpy is None:
        raise RuntimeError("Blender is required to create a UV snapshot")
    payload = bpy.data.meshes.new(f"{PAYLOAD_PREFIX}{snapshot_uuid}")
    try:
        vertices = [tuple(float(value) for value in vertex.co) for vertex in source_mesh.vertices]
        edges = [tuple(int(value) for value in edge.vertices) for edge in source_mesh.edges]
        faces = [tuple(int(value) for value in polygon.vertices) for polygon in source_mesh.polygons]
        payload.from_pydata(vertices, edges, faces)
        payload.update()
        if topology_fingerprint(payload) != topology_fingerprint(source_mesh):
            raise RuntimeError("Snapshot payload did not preserve source loop topology")
        payload_layer = payload.uv_layers.new(name=str(source_layer.name))
        values = uv_values(source_layer)
        if len(payload_layer.data) != len(values):
            raise RuntimeError("Snapshot UV loop count is incomplete")
        for item, value in zip(payload_layer.data, values):
            item.uv = value
        payload_layer.active_render = bool(getattr(source_layer, "active_render", False))
        payload.use_fake_user = True
        return payload
    except Exception:
        bpy.data.meshes.remove(payload)
        raise


def default_snapshot_name(obj, captured_at: str) -> str:
    """Name a freshly captured snapshot "<object> <YYYY-MM-DD HH:MM>".

    ``captured_at`` is the ISO-8601 stamp the operator passes; anything unparseable
    degrades to the object name alone rather than producing a blank row.
    """
    object_name = str(getattr(obj, "name", "") or "").strip()
    stamp = str(captured_at or "").strip().replace("T", " ")
    for terminator in ("+", "Z"):
        stamp = stamp.split(terminator, 1)[0]
    stamp = stamp.strip()[:16]
    return f"{object_name} {stamp}".strip() or "UV Snapshot"


def capture_snapshot(settings, obj, *, captured_at: str, blender_version: str, addon_version: str):
    if bpy is None:
        raise RuntimeError("Blender is required to capture a UV snapshot")
    if getattr(obj, "type", None) != "MESH" or getattr(obj, "data", None) is None:
        raise ValueError("The active object is not a mesh")
    if getattr(obj, "library", None) is not None or getattr(obj.data, "library", None) is not None:
        raise ValueError("Linked or read-only mesh data cannot own a UV snapshot")
    source_mesh = obj.data
    source_layer = getattr(source_mesh.uv_layers, "active", None)
    if source_layer is None or len(source_layer.data) != len(source_mesh.loops) or not source_layer.data:
        raise ValueError("The active mesh needs a complete active UV layer")
    uv_values(source_layer)

    identity = ensure_object_uuid(obj, settings)
    existing = find_snapshot(settings, obj)
    snapshot_uuid = _new_uuid()
    payload = _build_payload(source_mesh, source_layer, snapshot_uuid)
    old_payload = getattr(existing, "payload_mesh", None) if existing is not None else None
    # Read before the record is rewritten below: an Update Snapshot must keep a name the
    # artist set through Rename Snapshot instead of resetting it. A name equal to the
    # source layer's name is the legacy auto value (pre-default-name captures stamped
    # `source_layer.name`, "UVMap" on nearly every mesh), not an artist rename — let it
    # upgrade to the descriptive default.
    existing_name = str(getattr(existing, "snapshot_name", "") or "").strip() if existing is not None else ""
    if existing_name == str(source_layer.name).strip():
        existing_name = ""
    record = existing if existing is not None else settings.uv_snapshots.add()
    try:
        record.schema_version = SCHEMA_VERSION
        record.snapshot_uuid = snapshot_uuid
        record.source_object_uuid = identity
        record.source_object_name = str(obj.name)
        record.source_object_ref = obj
        record.snapshot_name = existing_name or default_snapshot_name(obj, captured_at)
        record.captured_at = str(captured_at)
        record.blender_version = str(blender_version)
        record.addon_version = str(addon_version)
        record.topology_fingerprint = topology_fingerprint(source_mesh)
        record.uv_layer_name = str(source_layer.name)
        record.face_count = len(source_mesh.polygons)
        record.loop_count = len(source_mesh.loops)
        record.active_render = bool(getattr(source_layer, "active_render", False))
        record.source_matrix = tuple(float(value) for row in obj.matrix_world for value in row)
        record.payload_mesh = payload
    except Exception:
        if existing is None:
            index = snapshot_index(settings, record)
            if index >= 0:
                settings.uv_snapshots.remove(index)
        payload.use_fake_user = False
        bpy.data.meshes.remove(payload)
        raise
    if old_payload is not None and old_payload is not payload:
        old_payload.use_fake_user = False
        if old_payload.users == 0:
            bpy.data.meshes.remove(old_payload)
    return record, existing is not None


def validate_snapshot(snapshot, obj) -> None:
    if int(getattr(snapshot, "schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("The UV snapshot schema is unsupported")
    payload = getattr(snapshot, "payload_mesh", None)
    if payload is None:
        raise ValueError("The UV snapshot payload is missing")
    owner = getattr(snapshot, "source_object_ref", None)
    if owner is not None and not _same_blender_id(owner, obj):
        raise ValueError("This UV snapshot belongs to another object")
    if str(getattr(snapshot, "source_object_uuid", "") or "") != object_uuid(obj):
        raise ValueError("The active object no longer owns this UV snapshot")
    layer = payload.uv_layers.get(str(getattr(snapshot, "uv_layer_name", "") or ""))
    if layer is None or len(layer.data) != len(payload.loops):
        raise ValueError("The UV snapshot layer is incomplete")
    uv_values(layer)


def exact_restore_plan(snapshot, obj) -> ExactRestorePlan:
    validate_snapshot(snapshot, obj)
    current_fingerprint = topology_fingerprint(obj.data)
    stored_fingerprint = str(getattr(snapshot, "topology_fingerprint", "") or "")
    if current_fingerprint != stored_fingerprint:
        raise ValueError("The mesh topology has changed")
    payload = snapshot.payload_mesh
    layer_name = str(snapshot.uv_layer_name)
    values = uv_values(payload.uv_layers[layer_name])
    if len(values) != len(obj.data.loops):
        raise ValueError("The UV snapshot loop count does not match the mesh")
    return ExactRestorePlan(current_fingerprint, layer_name, values)


def topology_matches(snapshot, obj) -> bool:
    try:
        validate_snapshot(snapshot, obj)
        return topology_fingerprint(obj.data) == str(snapshot.topology_fingerprint)
    except (ValueError, ReferenceError, RuntimeError):
        return False


def delete_snapshot(settings, snapshot) -> None:
    if bpy is None:
        raise RuntimeError("Blender is required to delete a UV snapshot")
    index = snapshot_index(settings, snapshot)
    if index < 0:
        raise ValueError("UV snapshot is no longer registered")
    payload = getattr(snapshot, "payload_mesh", None)
    settings.uv_snapshots.remove(index)
    if payload is not None:
        payload.use_fake_user = False
        if payload.users == 0:
            bpy.data.meshes.remove(payload)


def unique_restore_layer_name(mesh, source_name: str) -> str:
    base = f"{source_name or 'UVMap'}_Restored"
    if mesh.uv_layers.get(base) is None:
        return base
    ordinal = 1
    while mesh.uv_layers.get(f"{base}.{ordinal:03d}") is not None:
        ordinal += 1
    return f"{base}.{ordinal:03d}"
