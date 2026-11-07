"""Blender-engine bake helpers for material map outputs.

Called by the export pipeline when the image-texture fast path is unavailable
(procedural materials, multi-texture setups, etc.).

Material channels are baked through Cycles via ``bpy.ops.object.bake``. EEVEE Next
(Blender 4.2+) has no bake operator, so there is no alternate engine path.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Callable

from . import rna_buffers
from . import constants, handler_thread_guard, image_cleanup, material_channel_graph


class MaterialChannelUnresolved(RuntimeError):
    """This material exposes no socket for the channel, so Cycles cannot bake it.

    Raised instead of letting an EMIT pass run over a surface that emits nothing,
    which is how a non-Principled closure used to bake as a silent black map.
    """


# Map material channel → bake strategy:
#   "diffuse_color"  — use DIFFUSE bake type with only the Color pass enabled
#   "emit"           — route socket through a temporary Emission node, bake EMIT
#   "emit_normal"    — EMIT of a tangent-space material normal (authored Normal Bake
#                      socket, or a temporary encode of Principled Normal / Bump)
#   "normal"         — Cycles NORMAL pass (fallback / high-to-low detail)
_CHANNEL_BAKE_STRATEGY: dict[str, str] = {
    constants.MATERIAL_CHANNEL_ALBEDO: "diffuse_color",
    constants.MATERIAL_CHANNEL_ROUGHNESS: "emit",
    constants.MATERIAL_CHANNEL_METALNESS: "emit",
    constants.MATERIAL_CHANNEL_EMISSION: "emit",
    constants.MATERIAL_CHANNEL_OPACITY: "emit",
    constants.MATERIAL_CHANNEL_SPECULAR: "emit",
    constants.MATERIAL_CHANNEL_TRANSMISSION: "emit",
    # Prefer emit_normal via _resolve_strategy when the graph can supply a tangent
    # map that matches live Bump / Normal Map shading. Cycles NORMAL alone
    # under-reproduces strong bump when reapplied through a Normal Map node.
    "NORMAL": "normal",
    "__DETAIL_AO__": "ao_image",
    "__DETAIL_NORMAL__": "normal",
}

#: Shared node-group name for the tangent-space encoder used when a material has
#: no authored Normal Bake output. Renamed with the bitangent fix: a .blend saved
#: since keeps the old, green-flipped group under the old name.
_TANGENT_NORMAL_ENCODE_GROUP = "__FyrTangentNormalEncodeGL"

# Map channel → Principled BSDF input socket name
_CHANNEL_SOCKET: dict[str, str] = {
    constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
    constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    constants.MATERIAL_CHANNEL_METALNESS: "Metallic",
    constants.MATERIAL_CHANNEL_EMISSION: "Emission Color",
    constants.MATERIAL_CHANNEL_OPACITY: "Alpha",
    constants.MATERIAL_CHANNEL_SPECULAR: "Specular IOR Level",
    constants.MATERIAL_CHANNEL_TRANSMISSION: "Transmission Weight",
}

#: Authored helper sockets on asset-library groups (Sanctus Library, etc.). Prefer
#: these over Principled inputs when present — they are the artist's bake path and
#: often already encode tangent normals / flattened albedo.
_CHANNEL_AUTHORED_BAKE_OUTPUTS: dict[str, tuple[str, ...]] = {
    constants.MATERIAL_CHANNEL_ALBEDO: (
        "Color Bake",
        "Albedo Bake",
        "Base Color Bake",
    ),
    constants.MATERIAL_CHANNEL_ROUGHNESS: ("Roughness Bake",),
    constants.MATERIAL_CHANNEL_METALNESS: ("Metallic Bake", "Metalness Bake"),
}

#: Polls to wait for an invoked OBJECT_BAKE job to appear before giving up on it.
#: The queue polls at 0.1s, so this is ~2s -- far longer than registration takes, and
#: bounded so a bake that truly never starts still finishes the session instead of
#: hanging the queue.
_JOB_START_GRACE_POLLS = 20

_DEFERRED_PURGE_IDS: list[tuple[str, str, int]] = []
_DEFERRED_PURGE_TIMER_REGISTERED = False

#: Name prefixes the deferred purge is allowed to delete. Every scratch datablock the
#: material bake queues MUST carry one of these, or the purge silently skips it and the
#: datablock survives into the user's saved .blend. Keep the whitelist: it is what stops
#: a name collision after a reload from deleting a user's own material or image.
_DEFERRED_PURGE_NAME_PREFIXES = (
    "__mb_material_bake_",
    "__mb_bake_target_",
    "__fyr_matbake_",
)

#: 0.5s ticks the deferred scene restore waits for the machine to go quiet before
#: giving up and leaving the scene on CYCLES (recoverable by hand; a deadlocked
#: main thread is not).
_DEFERRED_RESTORE_MAX_TICKS = 240
#: Consecutive quiet ticks required before the restore is attempted. One is not
#: enough: `is_job_running` goes false while Cycles is still tearing its render
#: engine down, and the engine assignment blocks on exactly that teardown.
_DEFERRED_RESTORE_SETTLE_TICKS = 2
#: One pending restore per scene. Sessions in a queue all want the same original
#: engine back, so the first request wins and later ones are folded into it —
#: that is what makes the restore land once, after the queue, instead of racing
#: the next session's setup.
_PENDING_SCENE_RESTORES: dict[str, dict] = {}
_DEFERRED_PURGE_QUIET_TICKS = 0


def _material_queue_is_idle() -> bool:
    """True when no addon material-bake queue is still running."""
    try:
        from . import export

        return export.active_material_bake_status() is None
    except Exception:
        return True


def _defer_scene_bake_restore(
    *,
    scene_name: str,
    engine: str,
    margin_type,
    cycles_device,
    cycles_samples,
) -> None:
    """Restore engine/device/samples once the machine is quiet.

    A direct ``scene.render.engine = ...`` blocks the calling thread while a bake
    is in flight or a render engine is still tearing down — and the caller is the
    main thread, which is what the bake needs to finish. This waits for the whole
    material queue to go idle plus a settle margin, so the assignment lands with
    Blender at rest.
    """
    import bpy

    key = str(scene_name or "")
    pending = _PENDING_SCENE_RESTORES.get(key)
    if pending is not None:
        # A queue's later sessions saved the SAME original engine, so the first request
        # covers them -- except for the fields it could not capture. margin_type is only
        # saved on an artist-facing session, so a detail layer registering first parked
        # None and the artist-facing EXTEND was never undone. Fill those gaps instead of
        # dropping the later request whole.
        for field, value in (
            ("margin_type", margin_type),
            ("cycles_device", cycles_device),
            ("cycles_samples", cycles_samples),
        ):
            if pending.get(field) is None and value is not None:
                pending[field] = value
        return
    _PENDING_SCENE_RESTORES[key] = {
        "engine": engine,
        "margin_type": margin_type,
        "cycles_device": cycles_device,
        "cycles_samples": cycles_samples,
        "ticks": 0,
        "quiet": 0,
    }

    def _restore_timer():
        state = _PENDING_SCENE_RESTORES.get(key)
        if state is None:
            return None
        state["ticks"] += 1
        busy = True
        try:
            busy = bool(bpy.app.is_job_running("OBJECT_BAKE"))
        except (AttributeError, TypeError):
            busy = False
        if busy or not _material_queue_is_idle():
            state["quiet"] = 0
        else:
            state["quiet"] += 1
        if state["quiet"] < _DEFERRED_RESTORE_SETTLE_TICKS:
            if state["ticks"] < _DEFERRED_RESTORE_MAX_TICKS:
                return 0.5
            # Past the cap we restore anyway rather than walking away. The cap used to
            # abandon the restore, and because `quiet` resets on every busy tick the
            # whole queue had to finish within 120 s of the first channel ending -- an
            # ordinary multi-channel 4K queue does not, so the artist was left on
            # CYCLES with our device, samples and margin type, and only a print() to
            # show for it. Assigning while a bake is in flight can stall the main
            # thread briefly; a wrong render engine left behind is worse.
            print(
                "[MasterBaker] bake queue still busy after "
                f"{state['ticks'] * 0.5:.0f}s; restoring the scene's render settings now"
            )
        _PENDING_SCENE_RESTORES.pop(key, None)
        scene = bpy.data.scenes.get(key) if key else None
        if scene is None:
            return None
        try:
            if scene.render.engine != state["engine"]:
                scene.render.engine = state["engine"]
        except Exception:
            pass
        cycles = getattr(scene, "cycles", None)
        if state["margin_type"] is not None:
            try:
                scene.render.bake.margin_type = state["margin_type"]
            except (AttributeError, TypeError, ValueError):
                pass
        if cycles is not None and state["cycles_device"] is not None:
            try:
                cycles.device = state["cycles_device"]
            except Exception:
                pass
        if cycles is not None and state["cycles_samples"] is not None:
            try:
                cycles.samples = state["cycles_samples"]
            except Exception:
                pass
        return None

    try:
        bpy.app.timers.register(_restore_timer, first_interval=0.5)
    except Exception:
        _PENDING_SCENE_RESTORES.pop(key, None)


def _queue_deferred_id_purge(kind: str, name: str, *, attempts: int = 8) -> None:
    """Remove addon-owned temporary Blender IDs after UI/depsgraph references settle."""
    global _DEFERRED_PURGE_TIMER_REGISTERED
    kind = str(kind or "").strip()
    name = str(name or "").strip()
    if kind not in {"IMAGE", "MATERIAL"} or not name:
        return
    _DEFERRED_PURGE_IDS.append((kind, name, max(1, int(attempts))))
    if _DEFERRED_PURGE_TIMER_REGISTERED:
        return
    try:
        import bpy
        bpy.app.timers.register(_deferred_id_purge_timer, first_interval=1.0)
        _DEFERRED_PURGE_TIMER_REGISTERED = True
    except Exception:
        _DEFERRED_PURGE_TIMER_REGISTERED = False


def _deferred_id_purge_timer():
    """Timer callback for `_queue_deferred_id_purge`."""
    global _DEFERRED_PURGE_TIMER_REGISTERED
    try:
        import bpy
    except Exception:
        _DEFERRED_PURGE_TIMER_REGISTERED = False
        return None

    # Removing an ID tags the depsgraph's relations. Fired while the queue's next session
    # was baking, that wrote through the depsgraph the bake had in hand and crashed Blender
    # (access violation in graph_id_tag_update, 2026-11-04). Wait for rest, as the scene
    # restore does: no attempt is spent here.
    global _DEFERRED_PURGE_QUIET_TICKS
    try:
        busy = bool(bpy.app.is_job_running("OBJECT_BAKE"))
    except (AttributeError, TypeError):
        busy = False
    if busy or not _material_queue_is_idle():
        _DEFERRED_PURGE_QUIET_TICKS = 0
        return 0.5
    _DEFERRED_PURGE_QUIET_TICKS += 1
    if _DEFERRED_PURGE_QUIET_TICKS < _DEFERRED_RESTORE_SETTLE_TICKS:
        return 0.5
    _DEFERRED_PURGE_QUIET_TICKS = 0

    remaining: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    while _DEFERRED_PURGE_IDS:
        kind, name, attempts = _DEFERRED_PURGE_IDS.pop(0)
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        collection = bpy.data.images if kind == "IMAGE" else bpy.data.materials
        datablock = collection.get(name)
        if datablock is None:
            continue
        # Only purge scratch data the addon created. This avoids deleting a user
        # material/image if a name collision somehow occurs after a reload.
        if not name.startswith(_DEFERRED_PURGE_NAME_PREFIXES):
            continue
        try:
            if int(getattr(datablock, "users", 0)) <= 0:
                collection.remove(datablock)
                continue
        except ReferenceError:
            continue
        except Exception:
            pass
        attempts -= 1
        if attempts > 0:
            remaining.append((kind, name, attempts))
    _DEFERRED_PURGE_IDS.extend(remaining)
    if _DEFERRED_PURGE_IDS:
        return 1.0
    _DEFERRED_PURGE_TIMER_REGISTERED = False
    return None


def _material_can_emit_tangent_normal(material) -> bool:
    """True when *material* can supply a tangent-space normal via EMIT."""
    if material_channel_graph.find_height_bake_output(material) is not None:
        return True
    if material_channel_graph.find_normal_bake_output(material) is not None:
        return True
    return material_channel_graph.can_resolve(material, "Normal")


def _resolve_strategy(channel: str, shading_materials) -> str:
    """Bake strategy for *channel*, upgrading albedo / material normals when possible.

    Blender's DIFFUSE/COLOR pass returns black for a fully metallic surface, so a
    metal's albedo baked as pure black. Routing Base Color through Emission reads the
    authored value directly and is identical for dielectrics, so it is preferred
    whenever every contributing material exposes a resolvable Base Color. The DIFFUSE
    pass stays the fallback for graphs with no traceable Principled (mixed closures),
    where it is still the only way to get a meaningful flatten.

    Material-space Normal prefers EMIT of an authored ``Normal Bake`` output (or a
    temporary tangent encode of Principled Normal / Bump), then neutral-fills atlas
    voids and downsamples in normal space (see ``_EMIT_NORMAL_SUPERSAMPLE``). Raw
    EMIT of Distance=1 Bump is crunchier than the live EEVEE footprint; Cycles'
    NORMAL pass alone is softer than the same live view. ``__DETAIL_NORMAL__`` stays
    on Cycles NORMAL (high-to-low transfer).
    """
    key = str(channel or "").strip().upper()
    strategy = _CHANNEL_BAKE_STRATEGY.get(key, "emit")
    materials = list(shading_materials or [])
    if strategy == "normal" and key == "NORMAL" and materials:
        if all(_material_can_emit_tangent_normal(material) for material in materials):
            return "emit_normal"
        return strategy
    if strategy != "diffuse_color":
        return strategy
    socket_name = _CHANNEL_SOCKET.get(key)
    if not socket_name or not materials:
        return strategy
    if all(material_channel_graph.can_resolve(material, socket_name) for material in materials):
        return "emit"
    return strategy


def _layer_collection_chain(view_layer, collection):
    """Every layer collection from ``collection`` up to the root, or [] if absent.

    An excluded or hidden ancestor hides its children, so a fix has to walk the
    whole chain rather than the one node that owns the object.
    """
    chain: list = []

    def walk(node, ancestors):
        if getattr(node, "collection", None) == collection:
            chain.extend(ancestors + [node])
            return True
        for child in getattr(node, "children", []) or []:
            if walk(child, ancestors + [node]):
                return True
        return False

    walk(getattr(view_layer, "layer_collection", None), [])
    return chain


def _space_key(space):
    try:
        return space.as_pointer()
    except Exception:
        return id(space)


def _local_view_spaces() -> dict:
    """Every 3D View currently in Local View, keyed by its pointer.

    Only screens shown in a window: ``Object.local_view_set`` resolves the view
    layer through the window that displays the space's screen, so a space on a
    screen no window shows has nothing to resolve against.
    """
    import bpy

    spaces: dict = {}
    window_manager = getattr(bpy.context, "window_manager", None)
    for window in getattr(window_manager, "windows", None) or []:
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", None) or []:
            if getattr(area, "type", "") != "VIEW_3D":
                continue
            for space in getattr(area, "spaces", None) or []:
                if getattr(space, "type", "") != "VIEW_3D":
                    continue
                if getattr(space, "local_view", None) is None:
                    continue
                spaces.setdefault(_space_key(space), space)
    return spaces


#: Relative tolerance on M^T M for treating a low's transform as uniform scale (plus
#: rotation / mirror). Anything looser needs a generated cage; see WorldDistanceCages.
_UNIFORM_SCALE_TOLERANCE = 1e-5
_WORLD_CAGE_NAME_PREFIX = "__fyr_world_cage_"


class WorldDistanceCages:
    """Blender bake kwargs that put a Distance cage ``cage_offset`` WORLD units out.

    Fyr and the addon's cage preview treat ``cage_offset`` as world units, but
    Blender adds ``cage_extrusion`` to the low's LOCAL coordinates before its object
    matrix (``calc_point_from_barycentric_extrusion`` in render/intern/bake.cc). On
    a scale-0.01 FBX import an 11 mm cage became 0.11 mm, the high poly sat outside
    it, and every selected-to-active Cycles map baked garbage.

    Uniform scale (with any rotation or mirror) divides the offset by the scale,
    which reproduces the extrusion exactly. Non-uniform scale or shear cannot be
    expressed as one local distance, so a temporary cage object is built instead:
    each face corner moves ``cage_offset`` along the WORLD normal of the normal
    Blender's extrusion would have used (the vertex normal on smooth faces, the face
    normal on flat ones). Corners are split per face so flat faces keep their own
    normal, exactly as the extrusion does. Cages are cached per target and removed
    by :meth:`close`.
    """

    def __init__(self):
        self._cages: dict[tuple[str, float], str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
        return False

    def kwargs(self, target, cage_offset: float) -> dict:
        offset = max(0.0, float(cage_offset))
        if offset <= 0.0:
            return {"cage_extrusion": 0.0}
        scale = _uniform_world_scale(target)
        if scale is not None:
            return {"cage_extrusion": offset / scale}
        key = (str(getattr(target, "name", "") or ""), offset)
        cage_name = self._cages.get(key)
        if cage_name is None:
            cage_name = _build_world_distance_cage(target, offset)
            self._cages[key] = cage_name
        return {"cage_extrusion": 0.0, "use_cage": True, "cage_object": cage_name}

    def fitted_kwargs(self, target, corner_positions) -> dict | None:
        """Bake kwargs tracing from a fitted cage: one LOCAL position per face corner.

        ``corner_positions`` is ``(len(mesh.loops), 3)`` in the low's local space,
        indexed like the evaluated low's corners (an Automatic cage the export fitted).
        None when the evaluated low no longer has that many corners, so the caller
        falls back to a uniform distance.
        """
        key = (str(getattr(target, "name", "") or ""), "fitted")
        cage_name = self._cages.get(key)
        if cage_name is None:
            cage_name = _build_fitted_cage(target, corner_positions)
            if cage_name is None:
                return None
            self._cages[key] = cage_name
        return {"cage_extrusion": 0.0, "use_cage": True, "cage_object": cage_name}

    def close(self) -> None:
        import bpy

        cages, self._cages = self._cages, {}
        for cage_name in cages.values():
            cage = bpy.data.objects.get(cage_name)
            if cage is None:
                continue
            mesh = cage.data
            try:
                bpy.data.objects.remove(cage, do_unlink=True)
            except Exception:
                continue
            try:
                if mesh is not None and int(getattr(mesh, "users", 0)) == 0:
                    bpy.data.meshes.remove(mesh)
            except Exception:
                pass


def _uniform_world_scale(target) -> float | None:
    """The target's uniform world scale, or None when its matrix is not s * orthogonal."""
    import numpy as np

    matrix = getattr(target, "matrix_world", None)
    if matrix is None:
        return 1.0
    linear = np.array(matrix.to_3x3(), dtype=np.float64)
    gram = linear.T @ linear
    scale_sq = float(np.trace(gram)) / 3.0
    if not np.isfinite(scale_sq) or scale_sq <= 1e-24:
        # Degenerate: nothing meaningful to divide by, keep Blender's own units.
        return 1.0
    if float(np.max(np.abs(gram - scale_sq * np.eye(3)))) > _UNIFORM_SCALE_TOLERANCE * scale_sq:
        return None
    return float(np.sqrt(scale_sq))


def _build_world_distance_cage(target, offset: float) -> str:
    """Link a temporary cage for ``target`` offset ``offset`` world units; return its name."""
    import bpy
    import numpy as np

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    # The cage must match the EVALUATED low face for face and corner for corner
    # (Blender rejects it otherwise), so it is built from exactly that mesh.
    source = evaluated.to_mesh()
    try:
        vert_count = len(source.vertices)
        face_count = len(source.polygons)
        corner_count = len(source.loops)
        positions = np.empty(vert_count * 3, dtype=np.float32)
        source.vertices.foreach_get("co", positions)
        vert_normals = np.empty(vert_count * 3, dtype=np.float32)
        source.vertex_normals.foreach_get("vector", vert_normals)
        face_normals = np.empty(face_count * 3, dtype=np.float32)
        # MeshPolygon.normal is the geometric face normal; mesh.polygon_normals is not on
        # meshes with custom normals (Blender 5.2), which would bend flat cage faces.
        source.polygons.foreach_get("normal", face_normals)
        smooth = np.empty(face_count, dtype=bool)
        source.polygons.foreach_get("use_smooth", smooth)
        loop_start = rna_buffers.empty_u32_for_rna(face_count)
        source.polygons.foreach_get("loop_start", loop_start)
        loop_start = rna_buffers.as_i32(loop_start)
        loop_total = rna_buffers.empty_u32_for_rna(face_count)
        source.polygons.foreach_get("loop_total", loop_total)
        loop_total = rna_buffers.as_i32(loop_total)
        corner_verts = rna_buffers.empty_u32_for_rna(corner_count)
        source.loops.foreach_get("vertex_index", corner_verts)
        corner_verts = rna_buffers.as_i32(corner_verts)
    finally:
        evaluated.to_mesh_clear()

    positions = positions.reshape(-1, 3).astype(np.float64)
    vert_normals = vert_normals.reshape(-1, 3).astype(np.float64)
    face_normals = face_normals.reshape(-1, 3).astype(np.float64)
    corner_faces = np.repeat(np.arange(face_count), loop_total)
    local_normals = np.where(
        smooth[corner_faces][:, None], vert_normals[corner_verts], face_normals[corner_faces]
    )

    linear = np.array(target.matrix_world.to_3x3(), dtype=np.float64)
    inverse = np.linalg.inv(linear)
    # Normals transform by M^-T; as row vectors that is n @ M^-1.
    world_normals = local_normals @ inverse
    lengths = np.linalg.norm(world_normals, axis=1, keepdims=True)
    world_normals = world_normals / np.maximum(lengths, 1e-20)
    # Back to the low's local space, where the cage mesh lives (it shares the matrix).
    cage_positions = positions[corner_verts] + (world_normals * offset) @ inverse.T
    return _link_corner_cage(target, cage_positions, loop_start)


def _build_fitted_cage(target, corner_positions) -> str | None:
    """Link a cage for ``target`` from per-corner LOCAL positions; None on a topology change."""
    import bpy
    import numpy as np

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    source = evaluated.to_mesh()
    try:
        face_count = len(source.polygons)
        loop_start = rna_buffers.empty_u32_for_rna(face_count)
        source.polygons.foreach_get("loop_start", loop_start)
        loop_start = rna_buffers.as_i32(loop_start)
        corner_count = len(source.loops)
    finally:
        evaluated.to_mesh_clear()
    positions = np.asarray(corner_positions, dtype=np.float64).reshape(-1, 3)
    if len(positions) != corner_count:
        return None
    return _link_corner_cage(target, positions, loop_start)


def _link_corner_cage(target, cage_positions, loop_start) -> str:
    """Link a corner-split cage mesh (one vertex per face corner) sharing ``target``'s matrix.

    Blender pairs cage and low face for face and corner for corner, so the faces are
    the evaluated low's own (``loop_start``) with every corner a vertex of its own.
    """
    import bpy
    import numpy as np

    cage_positions = np.asarray(cage_positions, dtype=np.float64).reshape(-1, 3)
    corner_count = len(cage_positions)
    face_count = len(loop_start)
    name = f"{_WORLD_CAGE_NAME_PREFIX}{getattr(target, 'name', '')}"[:63]
    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(corner_count)
    mesh.vertices.foreach_set("co", cage_positions.astype(np.float32).ravel())
    mesh.loops.add(corner_count)
    mesh.loops.foreach_set("vertex_index", np.arange(corner_count, dtype=np.uintc))
    mesh.polygons.add(face_count)
    mesh.polygons.foreach_set("loop_start", np.ascontiguousarray(loop_start, dtype=np.uintc))
    mesh.update(calc_edges=True)
    cage = bpy.data.objects.new(name, mesh)
    cage.matrix_world = target.matrix_world.copy()
    # Blender's bake resolves the cage from a RENDER depsgraph, so it must stay
    # render-visible; the bake itself hides it from the traced scene.
    bpy.context.scene.collection.objects.link(cage)
    return cage.name


@contextmanager
def ensured_bake_visibility(objects):
    """Make every object a bake touches visible and selectable, then restore it.

    ``bpy.ops.object.bake`` only sees objects in ``selected_editable_objects``, so
    a hidden high-poly fails the bake outright with "not visible and selectable".
    Hiding the high after assigning it is ordinary workflow and Fyr's native path
    does not care — it exports meshes itself — so every Cycles bake (projection
    recovery and material channels alike) lifts the restrictions for the duration
    of the bake instead of making the artist do it.

    Local View counts too: with a 3D View in Local View, Blender drops every
    object outside it from the bake context. A tester (2026-09-26) had Cycles
    refuse the highs until they added them to the local view by hand; eye-icon
    hiding was not the cause. Each object is added to the local view of every
    3D View that has one, never removed from it, and the view is not exited.

    Collections are fixed before objects and restored after them: re-including a
    layer collection resets its objects' per-view-layer hide state, so the object
    flags have to be applied on top of the final collection state. Local View is
    applied last and restored first, because its membership lives on the object's
    view-layer base, which only exists while its collection is included.
    """
    import bpy

    view_layer = getattr(bpy.context, "view_layer", None)
    participants = [obj for obj in (objects or []) if obj is not None]
    collection_state: list = []
    object_state: list = []
    local_view_state: list = []
    seen_collections = set()
    changed = False

    def settle():
        try:
            view_layer.update()
        except Exception:
            pass

    try:
        for obj in participants:
            for collection in getattr(obj, "users_collection", []) or []:
                for node in _layer_collection_chain(view_layer, collection):
                    key = node.name
                    if key in seen_collections:
                        continue
                    seen_collections.add(key)
                    collection_state.append(
                        (node, bool(node.exclude), bool(node.hide_viewport),
                         bool(getattr(node.collection, "hide_viewport", False)))
                    )
                    try:
                        if node.exclude:
                            node.exclude = False
                            changed = True
                        if node.hide_viewport:
                            node.hide_viewport = False
                            changed = True
                        if getattr(node.collection, "hide_viewport", False):
                            node.collection.hide_viewport = False
                            changed = True
                    except Exception:
                        pass

        for obj in participants:
            try:
                hidden = bool(obj.hide_get(view_layer=view_layer))
            except Exception:
                hidden = None
            hide_viewport = bool(getattr(obj, "hide_viewport", False))
            hide_select = bool(getattr(obj, "hide_select", False))
            object_state.append((obj, hidden, hide_viewport, hide_select))
            try:
                if hidden:
                    obj.hide_set(False, view_layer=view_layer)
                    changed = True
                if hide_viewport:
                    obj.hide_viewport = False
                    changed = True
                if hide_select:
                    obj.hide_select = False
                    changed = True
            except Exception:
                pass

        # local_view_get reads the base flags the depsgraph copies onto the object,
        # so a base a re-included collection just created has to be synced first.
        if changed:
            settle()

        for space_key, space in _local_view_spaces().items():
            for obj in participants:
                try:
                    if obj.local_view_get(space):
                        continue
                    obj.local_view_set(space, True)
                except Exception:
                    continue
                local_view_state.append((space_key, obj))
        if local_view_state:
            changed = True
            settle()
        yield
    finally:
        if local_view_state:
            # Re-resolved rather than reusing the wrappers: a space is not an ID, and
            # an area closed (or a local view exited) during an async bake leaves a
            # dangling pointer behind that is not safe to call into.
            live_spaces = _local_view_spaces()
            for space_key, obj in reversed(local_view_state):
                space = live_spaces.get(space_key)
                if space is None:
                    continue
                try:
                    obj.local_view_set(space, False)
                except Exception:
                    pass
        for obj, hidden, hide_viewport, hide_select in reversed(object_state):
            try:
                obj.hide_select = hide_select
                obj.hide_viewport = hide_viewport
                if hidden is not None:
                    obj.hide_set(hidden, view_layer=view_layer)
            except Exception:
                pass
        for node, exclude, hide_viewport, collection_hidden in reversed(collection_state):
            try:
                node.collection.hide_viewport = collection_hidden
                node.hide_viewport = hide_viewport
                node.exclude = exclude
            except Exception:
                pass
        if changed:
            settle()


def _verify_bake_selection(source_objects, target):
    """Fail with the actual cause instead of Blender's generic bake error."""
    import bpy

    try:
        selectable = {obj.as_pointer() for obj in bpy.context.selected_editable_objects}
    except Exception:
        selectable = None
    required = [("high", obj) for obj in source_objects]
    required.append(("low", target))
    if selectable is not None:
        unusable = [
            f"{role} '{obj.name}'"
            for role, obj in required
            if obj is not None and obj.as_pointer() not in selectable
        ]
        if unusable:
            raise RuntimeError(
                "Blender cannot bake "
                + ", ".join(unusable)
                + ": the object is not visible and selectable in the active view layer "
                "even with its hiding, collection exclusion and local view lifted "
                "(is it linked into this scene's view layer?)"
            )
    try:
        active = getattr(getattr(bpy.context, "view_layer", None), "objects", None).active
    except Exception:
        active = None
    if active is not target:
        raise RuntimeError(
            f"Blender cannot bake low '{getattr(target, 'name', '<unknown>')}': "
            "it could not be made the active object"
        )
    try:
        if not bpy.ops.object.bake.poll():
            selected_names = [
                getattr(obj, "name", "<unnamed>")
                for obj in getattr(bpy.context, "selected_editable_objects", [])
            ]
            raise RuntimeError(
                "Blender bake operator is unavailable for the prepared context "
                f"(selected editable objects: {selected_names})"
            )
    except RuntimeError:
        raise
    except Exception:
        pass


@contextmanager
def _saved_render_engine(scene):
    original = scene.render.engine
    try:
        yield
    finally:
        if scene.render.engine != original:
            scene.render.engine = original


#: Scene bake settings pinned for the duration of one of our bakes. Blender fills every
#: operator property we do NOT pass from scene.render.bake, so the artist's Bake panel
#: leaked straight into a material channel: Target left on "Active Color Attribute"
#: baked into their colour attribute and saved whatever the fresh image buffer held,
#: and a DirectX swizzle green-flipped the MATERIAL Normal channel relative to every
#: natively baked map in the same texture set. cycles_projection pins the same keys,
#: minus normal_space, which every one of its passes supplies explicitly.
_PINNED_BAKE_SETTINGS = {
    "target": "IMAGE_TEXTURES",
    # The Bake panel's Space dropdown sits right beside the swizzle this pin already
    # neutralises, and neither NORMAL invocation passes normal_space -- so an artist
    # who left it on Object baked an OBJECT-space map into a tangent-space slot: a
    # rainbow Normal channel composited next to natively baked tangent-space maps in
    # the same texture set. Every channel that bakes a normal here wants TANGENT.
    "normal_space": "TANGENT",
    "normal_r": "POS_X",
    "normal_g": "POS_Y",
    "normal_b": "POS_Z",
    "use_cage": False,
    # Output = External Files makes the operator write scene.render.bake.filepath and
    # leave the target datablock untouched, so our image.save() would write out a
    # blank buffer. We always want the result in the datablock we injected.
    "save_mode": "INTERNAL",
}


@contextmanager
def _pinned_scene_bake_settings(scene):
    """Pin the scene's bake target / swizzle / cage flags for one bake, then restore."""
    bake = getattr(getattr(scene, "render", None), "bake", None)
    saved = {}
    if bake is not None:
        for name, value in _PINNED_BAKE_SETTINGS.items():
            if not hasattr(bake, name):
                continue
            saved[name] = getattr(bake, name)
            try:
                setattr(bake, name, value)
            except Exception:
                saved.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            try:
                setattr(bake, name, value)
            except Exception:
                pass


@contextmanager
def _bake_margin_type(scene, margin_type: str):
    """Force the scene's bake margin algorithm for the duration of one bake.

    Blender's default is ADJACENT_FACES, which only bleeds where a neighbouring
    face exists in 3D. Measured on the Pottery low at 1024 with margin 16:
    ADJACENT_FACES fills 83.85% of the sheet, EXTEND 88.07%, no margin 69.85%,
    and the backend's own dilation -- the semantics every natively baked map in
    the same texture set has -- fills 90.16%. EXTEND is the closer match, so a
    channel that falls back to Cycles no longer ships with a visibly harder
    island edge than its neighbours.

    Goes through the scene property rather than the operator's ``margin_type``
    keyword because that is what the measurement above was taken with.
    """
    bake_settings = getattr(getattr(scene, "render", None), "bake", None)
    previous = getattr(bake_settings, "margin_type", None) if bake_settings is not None else None
    if bake_settings is not None and previous is not None:
        try:
            bake_settings.margin_type = margin_type
        except (TypeError, ValueError):
            previous = None
    try:
        yield
    finally:
        if bake_settings is not None and previous is not None:
            try:
                bake_settings.margin_type = previous
            except (TypeError, ValueError):
                pass


@contextmanager
def _saved_cycles_device(scene, device: str = "CPU"):
    """Run a Cycles bake on ``device``, restoring the scene's device afterwards.

    Defaults to CPU: material-channel bakes run *concurrently* with FYR GPU
    projection, so they must not contend for the baking GPU. Cycles-primary and
    Cycles-recovery bakes own the GPU and pass the user's Cycles Device instead
    (see :func:`resolve_material_bake_device`).
    """
    cycles = getattr(scene, "cycles", None)
    if cycles is None or not hasattr(cycles, "device"):
        yield
        return
    original = cycles.device
    try:
        cycles.device = str(device or "CPU").strip().upper() or "CPU"
        yield
    finally:
        cycles.device = original


def resolve_material_bake_device_with_note(*, owns_machine: bool) -> tuple[str, str]:
    """Cycles device for one material-channel bake, plus why it is not what was asked.

    ``owns_machine`` is the whole distinction. A material bake queued alongside a
    healthy FYR projection must stay on CPU or it fights the baking GPU for VRAM
    and clocks. A Cycles-*primary* bake (Route = Cycles, or a GPU recovery) has no
    such neighbour, and pinning it to CPU anyway is what made a 4K Metallic sit for
    minutes and read as a hang -- the docstring above claimed the user's device was
    honoured there, but nothing passed it.

    The note is non-empty only when the user asked for GPU Compute and Cycles has no
    usable device; callers surface it so the CPU fall-back is never silent.
    """
    if not owns_machine:
        return "CPU", ""
    try:
        from . import cycles_projection

        device, note = cycles_projection.resolve_cycles_bake_device()
        return str(device or "CPU").strip().upper() or "CPU", str(note or "")
    except Exception:
        return "CPU", ""


def resolve_material_bake_device(*, owns_machine: bool) -> str:
    """Device-only form of :func:`resolve_material_bake_device_with_note`."""
    device, _note = resolve_material_bake_device_with_note(owns_machine=owns_machine)
    return device


#: Sample bounds for a material-channel Cycles bake. Blender's scene default is
#: 4096 samples, and nothing in this module used to override it: six channels at
#: 4096x4096 inherited it and ran for minutes with no progress and no way to stop.
#: A material channel is a surface evaluation (EMIT/DIFFUSE-COLOR of an already
#: shaded graph), not a light transport integration, so it converges far below the
#: render default. Mirrors cycles_projection's clamp for the same reason.
_MATERIAL_MIN_SAMPLES = 1
_MATERIAL_MAX_SAMPLES = 64


def material_bake_sample_count(scene, strategy: str = "") -> int:
    """Clamp the scene's Cycles samples into a sane budget for a material channel.

    ``emit_normal`` forces 1 sample. Encoded tangent normals are stored as RGB; with
    multiple samples Cycles averages those colours inside the pixel filter, which
    dilutes XY slopes and makes strong Bump look washed out when reapplied through a
    Normal Map node. A single center sample keeps the authored Normal Bake sharp.
    """
    if str(strategy or "").strip().lower() == "emit_normal":
        return 1
    cycles = getattr(scene, "cycles", None)
    try:
        value = int(getattr(cycles, "samples", 0) or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        value = _MATERIAL_MAX_SAMPLES
    return max(_MATERIAL_MIN_SAMPLES, min(value, _MATERIAL_MAX_SAMPLES))


@contextmanager
def _clamped_cycles_samples(scene, strategy: str = ""):
    """Cap Cycles samples for one material bake, restoring the scene's value after."""
    cycles = getattr(scene, "cycles", None)
    if cycles is None or not hasattr(cycles, "samples"):
        yield
        return
    original = cycles.samples
    try:
        cycles.samples = material_bake_sample_count(scene, strategy)
        yield
    finally:
        try:
            cycles.samples = original
        except (AttributeError, TypeError, ValueError):
            pass


def _flattened_channel_constant(mat, channel: str):
    """Constant value for *channel* on a non-Principled surface, or None.

    Uses the shared closure model in `material_graph`, which reads the same table
    the native Material IR compiles from, so the Cycles and Fyr routes cannot
    disagree about what a Glossy or Metallic BSDF means. Returns None whenever the
    channel resolves to something varying (a linked socket) rather than a constant,
    leaving the caller to refuse as before rather than flattening real detail away.
    """
    from . import material_graph

    tree = getattr(mat, "node_tree", None)
    if tree is None or not getattr(mat, "use_nodes", False):
        return None
    output = material_channel_graph.active_material_output(tree)
    surface = output.inputs.get("Surface") if output is not None else None
    if surface is None or not surface.links:
        return None
    expression = material_graph._extract_from_shader(  # noqa: SLF001
        surface.links[0].from_node, str(channel or "").strip().upper()
    )
    if expression is None or expression.invalid or expression.linked:
        return None
    return expression.constant


@contextmanager
def _freeze_view_dependent_factors(material, factor: float | None = None):
    """Replace Layer Weight / Fresnel outputs with constants for the duration of a bake.

    UV EMIT baking evaluates Facing along the shading normal, so view-dependent mixes
    (Sanctus car-paint Color1/Color2 blend, etc.) collapse to a single hue that does
    not match the live material. Freezing Facing / Fresnel to the node's Blend value
    (or *factor*) keeps the authored dual-tone mix stable under bake rays.
    """
    import bpy

    edits: list[tuple] = []

    def walk(tree, depth=0):
        if tree is None or depth > material_channel_graph._MAX_GROUP_DEPTH:  # noqa: SLF001
            return
        for node in list(getattr(tree, "nodes", []) or []):
            ntype = str(getattr(node, "type", "") or "")
            if ntype in material_channel_graph._VIEW_DEPENDENT_NODE_TYPES:  # noqa: SLF001
                blend = factor
                if blend is None:
                    # Layer Weight's Blend input is falloff *softness*, not Facing.
                    # Sanctus car paint wires it to a group "Blend" (e.g. 0.8); using
                    # that as the frozen Facing collapses Color1/Color2 to one hue.
                    # Only trust an *unlinked* Blend default on the node itself.
                    blend_in = node.inputs.get("Blend") if hasattr(node.inputs, "get") else None
                    if blend_in is not None and not getattr(blend_in, "is_linked", False):
                        try:
                            blend = float(blend_in.default_value)
                        except Exception:
                            blend = 0.35
                    else:
                        # Mid-low Facing keeps dual-tone paints (Sanctus Color1/Color2)
                        # from collapsing to the rim color under UV EMIT. 0.5 reads too
                        # cool on car paint; ~0.35 matches typical hero-angle warmth.
                        blend = 0.35
                for out in list(getattr(node, "outputs", []) or []):
                    if out.name not in {"Facing", "Fresnel"}:
                        continue
                    for link in list(getattr(out, "links", []) or []):
                        to_socket = link.to_socket
                        tree.links.remove(link)
                        value_node = tree.nodes.new("ShaderNodeValue")
                        value_node.label = "__fyr_freeze_view__"
                        value_node.outputs[0].default_value = float(blend)
                        new_link = tree.links.new(value_node.outputs[0], to_socket)
                        edits.append((tree, value_node, out, to_socket, new_link))
            if ntype == "GROUP" and getattr(node, "node_tree", None) is not None:
                walk(node.node_tree, depth + 1)

    walk(getattr(material, "node_tree", None))
    try:
        yield
    finally:
        for tree, value_node, from_socket, to_socket, new_link in reversed(edits):
            try:
                tree.links.remove(new_link)
            except Exception:
                pass
            try:
                tree.nodes.remove(value_node)
            except Exception:
                pass
            try:
                tree.links.new(from_socket, to_socket)
            except Exception:
                pass


@contextmanager
def _emit_reroute(mat, channel: str, *, source_socket=None, default_color=None):
    """Temporarily wire the target channel through an Emission node for EMIT bake.

    Inserts: [channel source] → Emission → Material Output (Surface)
    Restores original wiring on exit.
    """
    import bpy

    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    socket_name = _CHANNEL_SOCKET.get(str(channel or "").strip().upper())
    mat_output = material_channel_graph.active_material_output(tree)

    if source_socket is None and default_color is None and socket_name is None:
        yield
        return
    if mat_output is None:
        # Yielding here ran an EMIT pass over an unrouted graph: a surface that
        # emits nothing bakes pure black with no error, the exact silence the
        # unresolved-channel guard below exists to prevent.
        raise MaterialChannelUnresolved(
            f"'{mat.name}' has no active Material Output node, so nothing can be routed "
            "to the bake. Add a Material Output and connect the surface shader."
        )

    with ExitStack() as stack:
        # Collapse Facing/Fresnel so dual-tone / coat-style mixes stay stable.
        stack.enter_context(_freeze_view_dependent_factors(mat))
        channel_socket = source_socket
        if channel_socket is None and default_color is None:
            # Prefer authored bake helper sockets (Sanctus Color Bake / Roughness Bake /
            # Metallic Bake) before promoting Principled inputs through group nesting.
            # View-dependent Facing/Fresnel drivers are frozen above so Color Bake stays
            # dual-tone under UV EMIT (car paint, etc.).
            authored = _CHANNEL_AUTHORED_BAKE_OUTPUTS.get(
                str(channel or "").strip().upper()
            )
            if authored:
                channel_socket = material_channel_graph.find_named_surface_output(
                    mat, authored
                )
            if channel_socket is None and socket_name:
                # Resolve through any node-group nesting. A bare top-level Principled is
                # the easy case; asset-library and procedural materials wrap it in
                # groups, and reading the group node's own input default would flatten
                # away the procedural variation the user actually authored.
                channel_socket = stack.enter_context(
                    material_channel_graph.exposed_channel_socket(mat, socket_name)
                )
            if channel_socket is None:
                # No Principled to read. Before refusing, ask the same closure model
                # the native Fyr route uses: a Metallic/Glossy BSDF *is* metalness 1.0,
                # Glass/Refraction *are* transmission 1.0, and a Mix Shader of constant
                # branches blends to a constant. Cycles used to fail the whole bake on
                # those materials while Fyr baked them correctly, so a metal shader that
                # was not a Principled had no Cycles path at all -- which is the only
                # path on macOS/Linux.
                default_color = _flattened_channel_constant(mat, channel)
            if channel_socket is None and default_color is None:
                # Falling through to `yield` here left the ORIGINAL surface wired to
                # the output while the caller ran an EMIT pass over it. A surface
                # that emits nothing then baked pure black, with no error and no
                # warning -- every channel of every Metallic/Glass/Toon/... material.
                # `exposed_channel_socket` documents that it returns None precisely
                # so callers do not do that, so refuse instead of inventing a map.
                raise MaterialChannelUnresolved(
                    f"'{mat.name}' has no {socket_name} to bake: its surface shader is not a "
                    "Principled BSDF and could not be flattened. Baking it would produce a "
                    "black map."
                )

        # Build temporary emit subgraph. Sanctus and similar libraries often ship a
        # Material Output with target=CYCLES. Cycles prefers any CYCLES-targeted
        # output over target=ALL — even when ALL is the active output — so a
        # temporary emit Output that kept the default ALL target was silently
        # ignored and EMIT baked pure black (asphalt, brick, carbon fiber, …).
        saved_output_state: list[tuple] = []
        for node in nodes:
            if getattr(node, "type", "") != "OUTPUT_MATERIAL":
                continue
            saved_output_state.append(
                (node, bool(node.is_active_output), getattr(node, "target", None))
            )
            node.is_active_output = False

        emit_node = nodes.new("ShaderNodeEmission")
        emit_node.location = (mat_output.location[0] - 250, mat_output.location[1] - 150)

        out_node = nodes.new("ShaderNodeOutputMaterial")
        out_node.location = (mat_output.location[0], mat_output.location[1] - 150)
        try:
            out_node.target = "CYCLES"
        except Exception:
            pass
        out_node.is_active_output = True

        if channel_socket is not None:
            links.new(channel_socket, emit_node.inputs["Color"])
        elif default_color is not None:
            # The Emission "Color" socket is RGBA. Scalar channels (Roughness, Metallic, …)
            # have a plain float default, and assigning that to a color socket raised a
            # TypeError that was swallowed here — leaving Emission at its white default, so a
            # constant scalar channel baked as 1.0 instead of its value. Broadcast scalars to
            # grey and normalise colour/vector defaults to RGBA.
            try:
                if hasattr(default_color, "__len__"):
                    comps = list(default_color)
                    if len(comps) >= 3:
                        emit_node.inputs["Color"].default_value = (
                            comps[0], comps[1], comps[2], comps[3] if len(comps) > 3 else 1.0,
                        )
                else:
                    value = float(default_color)
                    emit_node.inputs["Color"].default_value = (value, value, value, 1.0)
            except Exception:
                pass

        if str(channel or "").strip().upper() == constants.MATERIAL_CHANNEL_EMISSION:
            # Fyr's native route bakes Emission Colour x Emission Strength. Leaving the
            # temporary Emission node at its default strength of 1 made this route
            # disagree with it on every material whose strength is not 1 -- most
            # visibly the Blender default (white colour, strength 0), where the native
            # bake is black and this one was white.
            strength_socket = stack.enter_context(
                material_channel_graph.exposed_channel_socket(mat, "Emission Strength")
            )
            # exposed_channel_socket always yields an OUTPUT socket -- the linked
            # source, or a constant node holding the unlinked default -- so this one
            # link covers both the "strength is a slider" and "strength is driven"
            # cases. None means the graph could not be resolved; leave strength at 1
            # rather than bake black.
            if strength_socket is not None:
                links.new(strength_socket, emit_node.inputs["Strength"])

        links.new(emit_node.outputs["Emission"], out_node.inputs["Surface"])

        try:
            yield
        finally:
            # Remove temporary nodes
            nodes.remove(emit_node)
            nodes.remove(out_node)
            for node, was_active, target in saved_output_state:
                try:
                    if target is not None:
                        node.target = target
                    node.is_active_output = was_active
                except Exception:
                    pass


def _ensure_tangent_normal_encode_group():
    """Node group: shading normal (Color) → tangent-space RGB for Normal Map nodes.

    TBN dots, OpenGL +Y, so materials without an authored Normal Bake output still
    flatten Bump / Normal Map inputs into a map that matches live shading when
    reapplied through a Normal Map node.
    """
    import bpy

    existing = bpy.data.node_groups.get(_TANGENT_NORMAL_ENCODE_GROUP)
    if existing is not None:
        return existing

    group = bpy.data.node_groups.new(_TANGENT_NORMAL_ENCODE_GROUP, "ShaderNodeTree")
    interface = group.interface
    interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
    interface.new_socket(name="Vector", in_out="OUTPUT", socket_type="NodeSocketVector")

    nodes, links = group.nodes, group.links
    group_in = nodes.new("NodeGroupInput")
    group_out = nodes.new("NodeGroupOutput")
    geometry = nodes.new("ShaderNodeNewGeometry")
    tangent = nodes.new("ShaderNodeTangent")
    try:
        tangent.direction_type = "UV_MAP"
    except Exception:
        pass

    # bitangent = cross(normal, tangent), the Normal Map node's own order. The
    # reverse order wrote DirectX green into OpenGL maps: measured against Blender's
    # native NORMAL bake, green correlated -0.99 where red read +0.99.
    cross = nodes.new("ShaderNodeVectorMath")
    cross.operation = "CROSS_PRODUCT"
    links.new(geometry.outputs["Normal"], cross.inputs[0])
    links.new(tangent.outputs["Tangent"], cross.inputs[1])

    dot_t = nodes.new("ShaderNodeVectorMath")
    dot_t.operation = "DOT_PRODUCT"
    links.new(group_in.outputs["Color"], dot_t.inputs[0])
    links.new(tangent.outputs["Tangent"], dot_t.inputs[1])

    dot_b = nodes.new("ShaderNodeVectorMath")
    dot_b.operation = "DOT_PRODUCT"
    links.new(group_in.outputs["Color"], dot_b.inputs[0])
    links.new(cross.outputs["Vector"], dot_b.inputs[1])

    dot_n = nodes.new("ShaderNodeVectorMath")
    dot_n.operation = "DOT_PRODUCT"
    links.new(group_in.outputs["Color"], dot_n.inputs[0])
    links.new(geometry.outputs["Normal"], dot_n.inputs[1])

    combine = nodes.new("ShaderNodeCombineXYZ")
    links.new(dot_t.outputs["Value"], combine.inputs["X"])
    links.new(dot_b.outputs["Value"], combine.inputs["Y"])
    links.new(dot_n.outputs["Value"], combine.inputs["Z"])

    scale = nodes.new("ShaderNodeVectorMath")
    scale.operation = "SCALE"
    scale.inputs["Scale"].default_value = 0.5
    links.new(combine.outputs["Vector"], scale.inputs[0])

    offset = nodes.new("ShaderNodeVectorMath")
    offset.operation = "ADD"
    offset.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(scale.outputs["Vector"], offset.inputs[0])
    links.new(offset.outputs["Vector"], group_out.inputs["Vector"])
    return group


@contextmanager
def _height_to_tangent_normal_emit(mat, height_socket, *, distance: float = 1.0):
    """EMIT a tangent normal derived from a scalar height / displacement bake socket.

    Do not stack Principled Normal / Bump on top of this height bump: Sanctus
    materials already combine tile bevels, Musgrave grain, and glaze cracks in
    the height signal. Stacking the same bump graph again roughly doubles
    high-frequency normal energy and reads as glittery speckle in the PNG.
    """
    tree = getattr(mat, "node_tree", None)
    if tree is None or height_socket is None:
        yield
        return
    bump = tree.nodes.new("ShaderNodeBump")
    bump.name = "__fyr_height_bump__"
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = float(distance)
    tree.links.new(height_socket, bump.inputs["Height"])
    encode_group = _ensure_tangent_normal_encode_group()
    encode_node = tree.nodes.new("ShaderNodeGroup")
    encode_node.node_tree = encode_group
    encode_node.name = "__fyr_tangent_normal_encode__"
    tree.links.new(bump.outputs["Normal"], encode_node.inputs["Color"])
    try:
        with _emit_reroute(mat, "NORMAL", source_socket=encode_node.outputs["Vector"]):
            yield
    finally:
        for node in (encode_node, bump):
            try:
                tree.nodes.remove(node)
            except Exception:
                pass


@contextmanager
def _material_normal_emit_reroute(mat):
    """Route a tangent-space material normal into Emission for EMIT baking.

    Order:
    1. Authored ``Normal Bake`` when its graph contains Bump / Normal Map. Sanctus
       ships a ``normal_bake`` encoder tuned for the live bump stack; EMIT of that
       socket is much less speckled than re-deriving from scalar height (finite-
       difference Bump on Musgrave/Voronoi at bake resolution).
    2. Fed scalar height / ``Displacement`` VALUE → Bump → tangent encode when no
       usable Normal Bake exists (true displacement without a bake helper).
    3. Any remaining fed ``Normal Bake``.
    4. Temporary encode of Principled Normal / Bump.

    Callers bake ``EMIT`` so the PNG matches a Normal Map node on re-import.
    """
    bake_socket = material_channel_graph.find_normal_bake_output(mat)
    normal_bake_has_relief = bake_socket is not None and (
        material_channel_graph.named_output_graph_has_types(
            mat,
            material_channel_graph.NORMAL_BAKE_OUTPUT_NAMES,
            {"BUMP", "NORMAL_MAP"},
        )
    )
    if normal_bake_has_relief:
        with _emit_reroute(mat, "NORMAL", source_socket=bake_socket):
            yield
        return

    height_socket = material_channel_graph.find_height_bake_output(mat)
    if height_socket is not None:
        with _height_to_tangent_normal_emit(mat, height_socket, distance=1.0):
            yield
        return

    if bake_socket is not None:
        with _emit_reroute(mat, "NORMAL", source_socket=bake_socket):
            yield
        return

    tree = getattr(mat, "node_tree", None)
    if tree is None:
        yield
        return
    encode_group = _ensure_tangent_normal_encode_group()
    encode_node = tree.nodes.new("ShaderNodeGroup")
    encode_node.node_tree = encode_group
    encode_node.name = "__fyr_tangent_normal_encode__"
    try:
        with material_channel_graph.exposed_channel_socket(mat, "Normal") as normal_socket:
            if normal_socket is None:
                yield
                return
            tree.links.new(normal_socket, encode_node.inputs["Color"])
            with _emit_reroute(mat, "NORMAL", source_socket=encode_node.outputs["Vector"]):
                yield
    finally:
        try:
            tree.nodes.remove(encode_node)
        except Exception:
            pass


def _semantic_ao_image_node(mat, explicit_image=None):
    nodes = getattr(getattr(mat, "node_tree", None), "nodes", []) or []
    if explicit_image is not None:
        for node in nodes:
            if getattr(node, "type", "") == "TEX_IMAGE" and getattr(node, "image", None) == explicit_image:
                return node
        return None

    best = None
    best_score = 0
    for node in nodes:
        if getattr(node, "type", "") != "TEX_IMAGE" or getattr(node, "image", None) is None:
            continue
        image = node.image
        haystack = " ".join(
            str(value or "")
            for value in (
                getattr(node, "name", ""),
                getattr(node, "label", ""),
                getattr(image, "name", ""),
                getattr(image, "filepath", ""),
            )
        ).lower().replace("-", "_").replace(" ", "_")
        score = 0
        if "ambientocclusion" in haystack or "ambient_occlusion" in haystack:
            score = 3
        elif "_ao." in haystack or "_ao_" in haystack or haystack.endswith("_ao"):
            score = 2
        if score > best_score:
            best = node
            best_score = score
    return best


@contextmanager
def _ao_image_reroute(mat, explicit_image=None):
    """Route a detected/manual AO image through Emission for transfer baking."""
    tree = getattr(mat, "node_tree", None)
    if tree is None:
        yield
        return
    node = _semantic_ao_image_node(mat, explicit_image)
    temporary_node = None
    if node is None and explicit_image is not None:
        temporary_node = tree.nodes.new("ShaderNodeTexImage")
        temporary_node.image = explicit_image
        node = temporary_node
    try:
        source_socket = node.outputs.get("Color") if node is not None else None
        # Materials without AO contribute neutral white to the combined result.
        with _emit_reroute(
            mat,
            "__DETAIL_AO__",
            source_socket=source_socket,
            default_color=(1.0, 1.0, 1.0, 1.0),
        ):
            yield
    finally:
        if temporary_node is not None:
            try:
                tree.nodes.remove(temporary_node)
            except Exception:
                pass


#: Tangent-space flat normal. EMIT bakes clear uncovered texels to black; sampling
#: those at UV island edges reads as dark seams. Cycles' NORMAL pass fills neutral
#: instead — match that for emit_normal / material Normal maps.
_TANGENT_NORMAL_NEUTRAL = (0.5, 0.5, 1.0, 1.0)

#: A hidden detail layer is neutral too, but material_detail.py reads its alpha as the
#: coverage mask: an opaque fill replaces the whole final map, wiping the other groups
#: that share the texture set with this group's flat background.
_DETAIL_NORMAL_NEUTRAL = (0.5, 0.5, 1.0, 0.0)

#: Bake emit_normal at this multiple of the request size, then downsample in
#: normal space. Kept at 1: 2×+Toksvig washed Sanctus concrete chip relief.
#: Glitter from Musgrave/Voronoi bump is handled by the post-bake attenuator.
_EMIT_NORMAL_SUPERSAMPLE = 1

#: Exponent on ``|mean(n)|`` when blending averaged normals toward flat.
#: Used by supersample downsample *and* the post-bake glitter pass.
#: 0 = ``normalize(mean)`` only; higher → stronger wash of disagreeing neighbours.
_EMIT_NORMAL_TOKSVIG_POWER = 1.25

#: Kernel width for the post-bake glitter attenuator (odd).
_EMIT_NORMAL_GLITTER_KERNEL = 3

#: Skip glitter wash when most neighbourhoods already agree (calm maps / subway).
_EMIT_NORMAL_GLITTER_DISAGREE_MIN = 0.28


def _image_rgba_array(image, height: int, width: int):
    """*image*'s pixels as a writable (height, width, 4) float32 array.

    ``image.pixels[:]`` builds a Python list of every float first: at 2048 that cost
    about a second per read, and the tangent-normal finalize reads six times.
    """
    import numpy as np

    if isinstance(image, _PixelImage):
        return image._rgba  # already the buffer: edits land in place
    pixels = np.empty(int(height) * int(width) * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(int(height), int(width), 4)


def _channel_is_tangent_normal(channel: str) -> bool:
    key = str(channel or "").strip().upper()
    return key in {
        constants.MATERIAL_CHANNEL_NORMAL,
        "__DETAIL_NORMAL__",
    }


def _sum3(values):
    """Sum over a last axis of three: ``values.sum(axis=-1)`` bit for bit, without
    numpy's slow short-axis reduction (it was a quarter of the Relief post-passes)."""
    return values[..., 0] + values[..., 1] + values[..., 2]


def _tangent_normal_fill(channel: str, planned_strategy) -> tuple | None:
    """The colour a tangent normal bake target starts from, ``None`` for other maps."""
    if str(channel or "").strip().upper() == "__DETAIL_NORMAL__":
        return _DETAIL_NORMAL_NEUTRAL
    if planned_strategy == "emit_normal" or _channel_is_tangent_normal(channel):
        return _TANGENT_NORMAL_NEUTRAL
    return None


def _fill_unbaked_tangent_normals(image, fill=_TANGENT_NORMAL_NEUTRAL) -> None:
    """Replace near-black / empty texels with a flat tangent normal."""
    import numpy as np

    if image is None:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    void = _sum3(pixels[..., :3]) < 0.05
    if not bool(void.any()):
        return
    pixels[void, 0] = fill[0]
    pixels[void, 1] = fill[1]
    pixels[void, 2] = fill[2]
    pixels[void, 3] = fill[3]
    image.pixels.foreach_set(pixels.ravel())
    image.update()


def _average_tangent_normals(block_normals):
    """Mean high-res tangent normals into one output normal per texel block.

    Naive ``normalize(mean(n))`` is wrong for the case the artist expects: when
    neighbours disagree (high-frequency detail), ``|mean|`` drops and renormalising
    *amplifies* the residual XY — the map stays crunchy or gets worse. Live EEVEE /
    footprint-filtered bump instead washes that variance toward flat.

    Toksvig-style reconstruct: blend the averaged direction toward ``(0,0,1)`` by
    ``|mean|^power``. Agreement (length≈1) keeps detail; disagreement pulls smooth.
    """
    import numpy as np

    avg = block_normals.mean(axis=(1, 3))
    length = np.sqrt(_sum3(avg * avg)[..., None])
    length = np.clip(length, 1e-8, 1.0)
    direction = avg / length
    power = float(_EMIT_NORMAL_TOKSVIG_POWER)
    if power <= 0.0:
        return direction
    flat = np.zeros_like(direction)
    flat[..., 2] = 1.0
    weight = np.power(length, power)
    blended = direction * weight + flat * (1.0 - weight)
    blended_len = np.sqrt(_sum3(blended * blended)[..., None])
    return blended / np.clip(blended_len, 1e-8, None)


def _downsample_tangent_normal_image(image, width: int, height: int):
    """Box-filter *image* down to ``width``×``height`` in decoded normal space.

    Returns a new image (caller owns it). Source may be larger by an integer factor.
    """
    import bpy
    import numpy as np

    src_w, src_h = int(image.size[0]), int(image.size[1])
    width, height = int(width), int(height)
    if src_w == width and src_h == height:
        return image
    if src_w % width != 0 or src_h % height != 0:
        raise ValueError(
            f"Normal supersample size {src_w}x{src_h} is not an integer multiple "
            f"of {width}x{height}"
        )
    fx, fy = src_w // width, src_h // height
    pixels = _image_rgba_array(image, src_h, src_w)
    # Fill voids before averaging so black padding does not pull normals down.
    void = _sum3(pixels[..., :3]) < 0.05
    pixels[void, 0] = _TANGENT_NORMAL_NEUTRAL[0]
    pixels[void, 1] = _TANGENT_NORMAL_NEUTRAL[1]
    pixels[void, 2] = _TANGENT_NORMAL_NEUTRAL[2]
    pixels[void, 3] = 1.0
    normals = pixels[..., :3] * 2.0 - 1.0
    normals = _average_tangent_normals(normals.reshape(height, fy, width, fx, 3))
    out = np.zeros((height, width, 4), dtype=np.float32)
    out[..., :3] = normals * 0.5 + 0.5
    out[..., 3] = 1.0
    name = f"{getattr(image, 'name', 'normal')}_ss"
    while name in bpy.data.images:
        name = f"{name}_"
    dst = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=True)
    dst.colorspace_settings.name = "Non-Color"
    dst.pixels.foreach_set(out.ravel())
    dst.update()
    return dst


#: Peak |n.xy| below this ⇒ treat the map as intentionally flat (skip amplify).
_WEAK_NORMAL_MIN_PEAK = 0.015
#: Stretch remaining mid-frequency slopes (crack lips) toward this after glitter wash.
#: Baseline at Relief=0.5; remapped by :func:`_emit_normal_relief_params`.
_WEAK_NORMAL_TARGET_PEAK = 0.32
#: Cap gain so a nearly-flat map cannot explode into speckled noise.
_WEAK_NORMAL_MAX_GAIN = 4.0
#: Only amplify texels at/above this fraction of the measured peak — micro-grain
#: left after Toksvig stays put; coherent crack lips get the lift.
_WEAK_NORMAL_AMPLIFY_SLOPE_FRAC = 0.35


def _emit_normal_relief_params(relief: float | None) -> tuple[float, float, str]:
    """Map Relief 0–1 → (Toksvig power, amplify target peak, grain mode).

    Grain mode is ``force`` (always smooth), ``auto`` (smooth when slope-dense),
    or ``off``. Module defaults match Relief=0.5.
    """
    if relief is None:
        return (
            float(_EMIT_NORMAL_TOKSVIG_POWER),
            float(_WEAK_NORMAL_TARGET_PEAK),
            "auto",
        )
    r = min(max(float(relief), 0.0), 1.0)
    if r <= 0.5:
        t = r / 0.5
        toksvig = 2.0 + (1.25 - 2.0) * t
        amplify = 0.18 + (0.32 - 0.18) * t
    else:
        t = (r - 0.5) / 0.5
        toksvig = 1.25 + (0.0 - 1.25) * t
        amplify = 0.32 + (0.45 - 0.32) * t
    if r <= 1e-6:
        grain = "force"
    elif r >= 1.0 - 1e-6:
        grain = "off"
    else:
        grain = "auto"
    return float(toksvig), float(amplify), grain


def _amplify_weak_tangent_normals(image, *, target_peak: float | None = None) -> None:
    """Restore mid-frequency crack lips after glitter attenuation.

    Toksvig wash lowers overall slope. Uniform gain would also re-boost leftover
    grain, so only texels near the current peak (coherent lips) are scaled toward
    ``target_peak`` (defaults to ``_WEAK_NORMAL_TARGET_PEAK``).
    """
    import numpy as np

    if image is None:
        return
    peak_target = float(_WEAK_NORMAL_TARGET_PEAK if target_peak is None else target_peak)
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    normals = pixels[..., :3] * 2.0 - 1.0
    slope = np.sqrt(normals[..., 0] ** 2 + normals[..., 1] ** 2)
    active = slope > (_WEAK_NORMAL_MIN_PEAK * 0.25)
    if not bool(active.any()):
        return
    peak = float(np.percentile(slope[active], 99.5))
    if peak < _WEAK_NORMAL_MIN_PEAK or peak >= peak_target:
        return
    gain = min(peak_target / max(peak, 1e-6), _WEAK_NORMAL_MAX_GAIN)
    mask = slope >= (peak * _WEAK_NORMAL_AMPLIFY_SLOPE_FRAC)
    if not bool(mask.any()):
        return
    normals[mask, 0] *= gain
    normals[mask, 1] *= gain
    length = np.sqrt(_sum3(normals * normals)[..., None])
    normals = normals / np.clip(length, 1e-8, None)
    pixels[..., :3] = normals * 0.5 + 0.5
    image.pixels.foreach_set(pixels.ravel())
    image.update()


def _renormalize_tangent_normals(image) -> None:
    """Unit-length decode for every non-void texel (EMIT can leave |n|≠1)."""
    import numpy as np

    if image is None:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    void = _sum3(pixels[..., :3]) < 0.05
    normals = pixels[..., :3] * 2.0 - 1.0
    length = np.sqrt(_sum3(normals * normals)[..., None])
    valid = (~void) & (length[..., 0] > 1e-6)
    if not bool(valid.any()):
        return
    np.divide(normals, length, out=normals, where=valid[..., None])
    pixels[..., :3] = normals * 0.5 + 0.5
    image.pixels.foreach_set(pixels.ravel())
    image.update()


def _attenuate_glitter_tangent_normals(image, *, toksvig_power: float | None = None) -> None:
    """Toksvig-style neighbourhood wash for point-sampled EMIT bump glitter.

    Sanctus asphalt (and similar) push high-scale Musgrave/Voronoi into Bump.
    Live EEVEE footprint-filters that; 1spp UV EMIT does not, so the PNG reads as
    salt-and-pepper. A small kernel mean with ``|mean|^power`` blend toward flat
    removes disagreeing micro-slopes while coherent crack / chip lips survive.

    Skips when neighbourhood agreement is already high (subway, calm Normal Bakes)
    so we do not soften intentional mid-frequency relief for free.
    """
    import numpy as np

    if image is None:
        return
    kernel = int(_EMIT_NORMAL_GLITTER_KERNEL)
    power = float(_EMIT_NORMAL_TOKSVIG_POWER if toksvig_power is None else toksvig_power)
    if kernel < 3 or kernel % 2 == 0 or power <= 0.0:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    void = _sum3(pixels[..., :3]) < 0.05
    normals = pixels[..., :3] * 2.0 - 1.0
    pad = kernel // 2
    padded = np.pad(normals, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    flat_n = np.zeros_like(normals)
    flat_n[..., 2] = 1.0
    padded_void = np.pad(void, ((pad, pad), (pad, pad)), mode="edge")
    padded[padded_void] = flat_n[0, 0]
    acc = np.zeros_like(normals)
    for dy in range(kernel):
        for dx in range(kernel):
            acc += padded[dy : dy + height, dx : dx + width]
    avg = acc / float(kernel * kernel)
    length = np.clip(np.sqrt(_sum3(avg * avg)[..., None]), 1e-8, 1.0)
    valid = ~void
    if not bool(valid.any()):
        return
    disagree = float((length[..., 0][valid] < 0.85).mean())
    if disagree < float(_EMIT_NORMAL_GLITTER_DISAGREE_MIN):
        return
    direction = avg / length
    weight = np.power(length, power)
    blended = direction * weight + flat_n * (1.0 - weight)
    blended_len = np.clip(np.sqrt(_sum3(blended * blended)[..., None]), 1e-8, None)
    blended = blended / blended_len
    normals = np.where(void[..., None], flat_n, blended)
    pixels[..., :3] = normals * 0.5 + 0.5
    image.pixels.foreach_set(pixels.ravel())
    image.update()


#: Hard cap on |n.xy| after glitter wash. UV-apron / island-edge garbage often
#: encodes near-horizontal normals (magenta/cyan speckles) that dominate the look.
_EMIT_NORMAL_MAX_SLOPE = 0.72


def _clamp_extreme_tangent_slopes(image) -> None:
    """Pull near-horizontal normals back toward flat (kills seam glitter spikes)."""
    import numpy as np

    if image is None:
        return
    max_slope = float(_EMIT_NORMAL_MAX_SLOPE)
    if max_slope <= 0.0:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    normals = pixels[..., :3] * 2.0 - 1.0
    slope = np.sqrt(normals[..., 0] ** 2 + normals[..., 1] ** 2)
    hot = slope > max_slope
    if not bool(hot.any()):
        return
    scale = max_slope / np.clip(slope[hot], 1e-6, None)
    normals[hot, 0] *= scale
    normals[hot, 1] *= scale
    length = np.sqrt(_sum3(normals * normals)[..., None])
    normals = normals / np.clip(length, 1e-8, None)
    pixels[..., :3] = normals * 0.5 + 0.5
    image.pixels.foreach_set(pixels.ravel())
    image.update()


#: After Toksvig, asphalt still has coherent aggregate grain (neighbours agree, so
#: Toksvig leaves it). A plain 3×3 mean softens that sparkle without the flat bias.
_EMIT_NORMAL_GRAIN_SMOOTH_KERNEL = 3
#: Only run grain smooth when mean |n.xy| exceeds this (skip flat subway maps).
_EMIT_NORMAL_GRAIN_SMOOTH_MIN_SLOPE = 0.04


def _smooth_coherent_tangent_grain(image, *, grain_mode: str = "auto") -> None:
    """Box-filter tangent normals when the map still has dense mid-frequency grain."""
    import numpy as np

    if image is None:
        return
    mode = str(grain_mode or "auto").strip().lower()
    if mode == "off":
        return
    kernel = int(_EMIT_NORMAL_GRAIN_SMOOTH_KERNEL)
    if kernel < 3 or kernel % 2 == 0:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    void = _sum3(pixels[..., :3]) < 0.05
    normals = pixels[..., :3] * 2.0 - 1.0
    slope = np.sqrt(normals[..., 0] ** 2 + normals[..., 1] ** 2)
    valid = ~void
    if not bool(valid.any()):
        return
    if mode != "force" and float(slope[valid].mean()) < float(_EMIT_NORMAL_GRAIN_SMOOTH_MIN_SLOPE):
        return
    pad = kernel // 2
    flat_n = np.zeros_like(normals)
    flat_n[..., 2] = 1.0
    padded = np.pad(normals, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    padded_void = np.pad(void, ((pad, pad), (pad, pad)), mode="edge")
    padded[padded_void] = flat_n[0, 0]
    acc = np.zeros_like(normals)
    for dy in range(kernel):
        for dx in range(kernel):
            acc += padded[dy : dy + height, dx : dx + width]
    avg = acc / float(kernel * kernel)
    length = np.clip(np.sqrt(_sum3(avg * avg)[..., None]), 1e-8, None)
    smoothed = avg / length
    normals = np.where(void[..., None], flat_n, smoothed)
    pixels[..., :3] = normals * 0.5 + 0.5
    image.pixels.foreach_set(pixels.ravel())
    image.update()


def _finalize_tangent_normal_bake_image(
    image,
    *,
    width: int | None = None,
    height: int | None = None,
    relief: float | None = None,
    void_fill=_TANGENT_NORMAL_NEUTRAL,
):
    """Neutral-fill voids, downsample, renormalize, wash glitter, lift weak slopes.

    ``relief`` (0–1) remaps Toksvig wash / grain smooth / crack amplify for
    emit_normal. ``None`` keeps the Relief=0.5 module baselines. Absolute caps
    (max slope, disagree skip) stay fixed so Relief=1 cannot reintroduce
    magenta UV-apron spikes.
    """
    if image is None:
        return image
    toksvig_power, amplify_target, grain_mode = _emit_normal_relief_params(relief)
    src_w, src_h = int(image.size[0]), int(image.size[1])
    dst_w = int(width) if width is not None else src_w
    dst_h = int(height) if height is not None else src_h
    if (src_w, src_h) != (dst_w, dst_h):
        image = _downsample_tangent_normal_image(image, dst_w, dst_h)
    else:
        _fill_unbaked_tangent_normals(image, void_fill)
    _renormalize_tangent_normals(image)
    _attenuate_glitter_tangent_normals(image, toksvig_power=toksvig_power)
    _smooth_coherent_tangent_grain(image, grain_mode=grain_mode)
    _clamp_extreme_tangent_slopes(image)
    _amplify_weak_tangent_normals(image, target_peak=amplify_target)
    return image


class _PixelImage:
    """The slice of ``bpy.types.Image`` the tangent-normal passes use, over a numpy buffer."""

    def __init__(self, rgba):
        self._rgba = rgba
        self.size = (int(rgba.shape[1]), int(rgba.shape[0]))
        self.pixels = self

    def foreach_get(self, out) -> None:
        out[:] = self._rgba.reshape(-1)

    def foreach_set(self, values) -> None:
        import numpy as np

        if np.shares_memory(values, self._rgba):
            return  # the pass edited this buffer in place
        self._rgba[...] = values.reshape(self._rgba.shape)

    def update(self) -> None:
        pass


def finalize_tangent_normal_pixels(rgba, *, relief: float | None):
    """Run the Cycles route's Relief post-passes on an already-baked tangent map.

    *rgba* is a float32 (height, width, 4) array in Blender's bottom-up row order,
    modified in place and returned. The GPU route bakes the raw normal; this gives
    its material-workflow Normal the same Relief look the Cycles route always had.
    """
    image = _PixelImage(rgba)
    _finalize_tangent_normal_bake_image(image, relief=relief)
    return rgba


def _flip_tangent_normal_green(image) -> None:
    """DirectX convention: invert the encoded green of a finished OpenGL tangent map."""
    if image is None:
        return
    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        return
    pixels = _image_rgba_array(image, height, width)
    pixels[..., 1] = 1.0 - pixels[..., 1]
    image.pixels.foreach_set(pixels.ravel())
    image.update()


def _make_bake_target_image(
    name: str, width: int, height: int, channel: str,
    *, offset_u: float = 0.0, offset_v: float = 0.0,
    fill_rgba: tuple[float, float, float, float] | None = None,
):
    """Allocate only the destination tile, leaving the mesh's shading UVs intact."""
    import bpy
    import numpy as np

    u, v = int(offset_u), int(offset_v)
    tile = constants.UDIM_TILE_MIN + u + 10 * v
    if (u != offset_u or v != offset_v or not 0 <= u <= 9
            or v < 0 or tile > constants.UDIM_TILE_MAX):
        raise ValueError(f"Invalid UDIM tile offset: ({offset_u}, {offset_v})")
    tiled = tile != constants.UDIM_TILE_MIN
    img = bpy.data.images.new(name, width=width, height=height, alpha=True,
                             float_buffer=True, tiled=tiled)
    if tiled:
        try:
            img.tiles[0].number = tile
            # Initialize the requested tile's pixel buffer explicitly. The image
            # operator allocates it without needing an Image Editor area, including
            # in background Blender and a bake session invoked from the 3D View.
            clear = fill_rgba if fill_rgba is not None else (0.0, 0.0, 0.0, 0.0)
            with bpy.context.temp_override(edit_image=img):
                result = bpy.ops.image.tile_fill(width=width, height=height,
                    float=True, alpha=True, color=clear)
            if "FINISHED" not in result:
                raise RuntimeError(f"Could not allocate bake tile {tile}: {sorted(result)}")
        except Exception:
            bpy.data.images.remove(img)
            raise
    elif fill_rgba is not None:
        pixels = np.empty((height, width, 4), dtype=np.float32)
        pixels[..., 0] = fill_rgba[0]
        pixels[..., 1] = fill_rgba[1]
        pixels[..., 2] = fill_rgba[2]
        pixels[..., 3] = fill_rgba[3]
        img.pixels.foreach_set(pixels.ravel())
        img.update()
    img.colorspace_settings.name = (
        "sRGB"
        if channel in {constants.MATERIAL_CHANNEL_ALBEDO, constants.MATERIAL_CHANNEL_EMISSION}
        else "Non-Color"
    )
    return img


def _save_bake_target_image(image, output_path: Path):
    """Save a single bake tile under the exact filename requested by the exporter."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.file_format = {
        ".tga": "TARGA_RAW", ".png": "PNG", ".exr": "OPEN_EXR",
        ".tif": "TIFF", ".tiff": "TIFF", ".jpg": "JPEG", ".jpeg": "JPEG",
    }.get(output_path.suffix.lower(), "OPEN_EXR")
    if image.source != "TILED":
        image.filepath_raw = str(output_path)
        image.save()
        return
    # Blender requires a <UDIM> token for tiled images. Stage in the destination
    # directory so atomic replacement works on the same volume, with bounded
    # temporary storage and cleanup on both successful and failed saves.
    with tempfile.TemporaryDirectory(prefix=".fyr_bake_tile_", dir=output_path.parent) as scratch:
        tile = image.tiles[0].number
        template = Path(scratch) / ("bake.<UDIM>" + output_path.suffix)
        image.filepath_raw = str(template)
        image.save()
        os.replace(str(template).replace("<UDIM>", str(tile)), output_path)


def _make_strip_image(name: str, width: int, strip_rows: int, channel: str):
    """The reusable bake image of a striped material bake.

    Never tiled, even for a UDIM tile: the strip UVs already carry the tile offset.
    Same buffer and colour space as :func:`_make_bake_target_image`, so Blender saves
    each strip exactly as it would have saved the whole map.
    """
    import bpy

    img = bpy.data.images.new(name, width=int(width), height=int(strip_rows), alpha=True,
                              float_buffer=True, tiled=False)
    img.colorspace_settings.name = (
        "sRGB"
        if channel in {constants.MATERIAL_CHANNEL_ALBEDO, constants.MATERIAL_CHANNEL_EMISSION}
        else "Non-Color"
    )
    return img


def _resolve_material_output_path(output_path, scratch_dir, image_name: str, channel: str) -> Path:
    if output_path is None and scratch_dir is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".exr", delete=False)
        tmp.close()
        output_path = tmp.name
    elif output_path is None:
        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        output_path = scratch_path / f"{image_name}_{channel.lower()}.exr"
    return Path(output_path)


def _material_channel_label(channel: str) -> str:
    special = {
        "__DETAIL_AO__": "material detail AO",
        "__DETAIL_NORMAL__": "material detail normal",
        "NORMAL": "Normal",
    }
    key = str(channel or "").strip().upper()
    if key in special:
        return special[key]
    return key.replace("_", " ").strip().title() or "material"


def _shading_materials_of(objects) -> list:
    materials = []
    seen = set()
    for source in objects or []:
        for slot in getattr(source, "material_slots", None) or []:
            material = slot.material if slot else None
            if material is None or not getattr(material, "use_nodes", False):
                continue
            key = material.as_pointer()
            if key in seen:
                continue
            seen.add(key)
            materials.append(material)
    return materials


def _material_bake_participants(target_objects, source_objects, source_groups) -> tuple[list, list]:
    """(targets, every high any target bakes from), duplicates removed."""
    sources = list(source_objects or [])
    for group in source_groups or []:
        sources.extend(group or [])
    unique = []
    seen = set()
    for obj in sources:
        if obj is None:
            continue
        key = obj.as_pointer() if hasattr(obj, "as_pointer") else id(obj)
        if key in seen:
            continue
        seen.add(key)
        unique.append(obj)
    return list(target_objects or []), unique


def _material_render_scope_enabled(strategy: str, shading_materials) -> bool:
    try:
        from . import cycles_projection

        return cycles_projection.material_pass_is_scene_independent(strategy, shading_materials)
    except Exception:
        return False


def _render_scope_outsiders(participants) -> list:
    try:
        import bpy
        from . import cycles_projection

        view_layer_objects = list(getattr(bpy.context.view_layer, "objects", []) or [])
        return cycles_projection._render_scope_outsiders(view_layer_objects, participants)  # noqa: SLF001
    except Exception:
        return []


def _plan_material_strips(
    target_objects,
    source_objects,
    source_groups,
    channel: str,
    width: int,
    height: int,
    margin: int,
    strategy: str,
    shading_materials,
):
    """Memory plan for one material channel; raises CyclesMemoryError when it cannot fit."""
    from . import cycles_memory

    targets, sources = _material_bake_participants(target_objects, source_objects, source_groups)
    participants = targets + sources
    others = []
    if not _material_render_scope_enabled(strategy, shading_materials):
        # Without render-scope isolation Cycles syncs every render-visible object.
        others = _render_scope_outsiders(participants)
    scene_bytes = cycles_memory.estimate_scene_bytes(sources, targets, others=others)
    per_texel = cycles_memory.bytes_per_texel(selected_to_active=bool(sources), float_target=True)
    group = ", ".join(str(getattr(obj, "name", "") or "") for obj in targets[:3] if obj is not None)
    return cycles_memory.plan_strips(
        width,
        height,
        apron=cycles_memory.apron_rows(margin),
        bytes_per_texel=per_texel,
        scene_bytes=scene_bytes,
        what=_material_channel_label(channel),
        group=group,
    )


def _material_uv_layers(
    target_objects, source_objects, source_groups, plan, offset_u, offset_v, uv_layer_name=""
):
    """StripUVLayers for a striped material bake (in place only when every target has highs).

    ``uv_layer_name`` is the group's bake UV set; the strip UVs derive from it.
    """
    from . import cycles_memory

    every_target_projects = all(
        bool(_sources_for_target(source_objects, source_groups, index))
        for index in range(len(target_objects or []))
    )
    return cycles_memory.StripUVLayers(
        objects=list(target_objects or []),
        tile_u=float(offset_u),
        tile_v=float(offset_v),
        height=int(plan.height),
        allow_in_place=every_target_projects,
        source_layer_name=str(uv_layer_name or ""),
    )


def _fitted_cages_by_low(fitted_cages) -> dict:
    """FittedCage per low name (cycles_projection.FittedCage)."""
    return {str(cage.low_name): cage for cage in fitted_cages or ()}


def _material_cage_kwargs(world_cages, target, cage_extrusion: float, fitted_by_low, extrusion_by_low=None) -> dict:
    """Selected-to-active cage kwargs for ``target``: its fitted cage, else a distance.

    Lows of different groups can share one bake (a combined texture set), each with its
    group's own distance in ``extrusion_by_low``.

    Under an Automatic cage ``cage_extrusion`` alone was the hidden Distance control
    (0.02 by default), so a floating detail further out than that never reached the
    material bake while the GPU, tracing the fitted cage, picked it up.
    """
    fitted = fitted_by_low.get(str(getattr(target, "name", "") or ""))
    if fitted is not None:
        kwargs = world_cages.fitted_kwargs(target, fitted.corner_positions)
        if kwargs is not None:
            return kwargs
        print(
            f"[FyrBaker] Cycles: Automatic cage of '{fitted.low_name}' no longer matches its mesh; "
            "using a uniform distance"
        )
    return world_cages.kwargs(
        target, (extrusion_by_low or {}).get(str(getattr(target, "name", "") or ""), cage_extrusion)
    )


def _require_bake_uv_layer(target_objects, uv_layer_name: str) -> None:
    """Refuse a named bake UV set that a target mesh does not have.

    Blender's own error for a missing ``uv_layer`` names neither the object nor the
    layer, and it only surfaces after the scene has been staged for the bake.
    """
    if not uv_layer_name:
        return
    for target in target_objects or ():
        mesh = getattr(target, "data", None)
        layers = getattr(mesh, "uv_layers", None)
        if layers is None or layers.get(uv_layer_name) is None:
            raise RuntimeError(
                f"'{getattr(target, 'name', '?')}' has no UV map named '{uv_layer_name}' to bake into"
            )


def _inject_bake_target_node(mat, image):
    """Add an active (selected) Image Texture node pointing at image in this material."""
    import bpy
    tree = mat.node_tree
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.location = (-400, 200)
    # Deselect everything, then select and activate this node
    for n in tree.nodes:
        n.select = False
    node.select = True
    tree.nodes.active = node
    return node


def _remove_bake_target_node(mat, node):
    mat.node_tree.nodes.remove(node)


#: Depth of active material isolations. While one is open the objects' slots hold
#: the __fyr_matbake_ copies, and material_capture_sync must not read them.
_MATERIAL_ISOLATION_DEPTH = 0


def material_isolation_active() -> bool:
    return _MATERIAL_ISOLATION_DEPTH > 0


@contextmanager
def _isolated_object_materials(objects):
    """Swap object material slots to temporary copies; restore and purge on exit."""
    import bpy

    global _MATERIAL_ISOLATION_DEPTH
    originals = []
    copies = []
    copy_by_source = {}
    copy_pointers: set[int] = set()
    _MATERIAL_ISOLATION_DEPTH += 1
    try:
        for obj in objects:
            for index, slot in enumerate(getattr(obj, "material_slots", []) or []):
                material = getattr(slot, "material", None)
                if material is None:
                    continue
                key = material.as_pointer()
                if key in copy_pointers:
                    # Two objects sharing one mesh (Alt+D linked duplicates: repeated
                    # bolts, teeth, rivets). MaterialSlot.link defaults to DATA, so the
                    # first object's swap already wrote our copy into the SHARED mesh
                    # and this slot is now reading that copy back. Copying it again
                    # would record OUR scratch material as this slot's "original", and
                    # the restore -- writing that same shared mesh -- would then leave
                    # the scratch material on the artist's mesh for good: the deferred
                    # purge sees users > 0, retries, gives up, and their real material
                    # is left orphaned and disappears on the next save. Same
                    # linked-duplicate hazard _temporary_uv_tile_offset documents.
                    continue
                working = copy_by_source.get(key)
                if working is None:
                    working = material.copy()
                    working.name = f"__fyr_matbake_{material.name}"[:60]
                    copies.append(working)
                    copy_by_source[key] = working
                    copy_pointers.add(working.as_pointer())
                originals.append((obj, index, material))
                slot.material = working
        yield copy_by_source
    finally:
        _MATERIAL_ISOLATION_DEPTH = max(0, _MATERIAL_ISOLATION_DEPTH - 1)
        for obj, index, material in originals:
            try:
                if index < len(obj.material_slots):
                    obj.material_slots[index].material = material
            except Exception:
                pass
        for working in copies:
            try:
                name = str(getattr(working, "name", "") or "")
                if name:
                    _queue_deferred_id_purge("MATERIAL", name)
            except Exception:
                pass


@contextmanager
def bake_uv_layer_active(objects, layer_name: str):
    """Make ``layer_name`` each mesh's ACTIVE UV layer for a bake, then restore it.

    Blender rasterizes into the bake's ``uv_layer`` but builds a Tangent normal's
    tangent space from the mesh's active UV layer (measured on 5.2). With the UV Set
    not active, every tangent normal came back rotated by the active layer's layout,
    while Fyr takes its tangents from the UV Set. active_render, the layer the
    materials sample, is left alone. "" changes nothing.
    """
    restored = []
    try:
        seen = set()
        for obj in (objects or ()) if layer_name else ():
            mesh = getattr(obj, "data", None)
            layers = getattr(mesh, "uv_layers", None)
            if layers is None:
                continue
            try:
                key = int(mesh.as_pointer())
            except Exception:
                key = id(mesh)
            if key in seen:
                continue
            seen.add(key)
            target = layers.get(layer_name)
            previous = layers.active
            if target is None or previous is None or str(previous.name) == layer_name:
                continue
            restored.append((mesh, str(previous.name)))
            layers.active = target
        yield
    finally:
        for mesh, name in reversed(restored):
            try:
                previous = mesh.uv_layers.get(name)
                if previous is not None:
                    mesh.uv_layers.active = previous
            except Exception:  # noqa: BLE001 - restore every other mesh regardless
                continue


@contextmanager
def _temporary_uv_tile_offset(objects, offset_u: float, offset_v: float, layer_name: str = ""):
    """Shift each mesh's bake UV layer back into tile 1001 for the bake, then restore it.

    ``layer_name`` is the bake's explicit ``uv_layer``; "" shifts active_render.
    """
    if abs(offset_u) < 1e-12 and abs(offset_v) < 1e-12:
        yield
        return
    restored = []
    # One shift per UV LAYER, not per object. Two objects sharing a mesh (Alt+D linked
    # duplicates) reached the same layer twice: the second pass backed up the already
    # shifted UVs and subtracted again, and the restore replayed the backups in forward
    # order, so the last write won and the artist's mesh was left permanently at
    # original-minus-offset - with no undo push, and the bake sampling a double-shifted
    # tile in the meantime.
    seen_layers: set[int] = set()
    try:
        for obj in objects:
            mesh = getattr(obj, "data", None)
            if mesh is None or not hasattr(mesh, "uv_layers"):
                continue
            if layer_name:
                # An explicit bake uv_layer: shift exactly the layer the bake rasterizes.
                uv_layer = mesh.uv_layers.get(layer_name)
                if uv_layer is None:
                    raise RuntimeError(
                        f"'{getattr(obj, 'name', '?')}' has no UV map named '{layer_name}' to bake into"
                    )
            else:
                # The bake reads active_render, not active; where they differ, shifting the
                # active layer moved UVs the bake never looks at and left the baked ones alone.
                uv_layer = None
                for candidate in getattr(mesh, "uv_layers", []) or []:
                    if bool(getattr(candidate, "active_render", False)):
                        uv_layer = candidate
                        break
                if uv_layer is None:
                    uv_layer = mesh.uv_layers.active
            if uv_layer is None:
                continue
            try:
                layer_key = int(uv_layer.as_pointer())
            except Exception:
                layer_key = id(uv_layer)
            if layer_key in seen_layers:
                continue
            seen_layers.add(layer_key)
            backup = [tuple(loop.uv) for loop in uv_layer.data]
            restored.append((uv_layer, backup))
            for loop in uv_layer.data:
                loop.uv[0] -= float(offset_u)
                loop.uv[1] -= float(offset_v)
        yield
    finally:
        for uv_layer, backup in restored:
            for loop, uv in zip(uv_layer.data, backup):
                loop.uv[0] = uv[0]
                loop.uv[1] = uv[1]


@contextmanager
def _custom_output_reroute(mat, output_name: str):
    from . import material_capture_nodes

    tree = getattr(mat, "node_tree", None)
    if tree is None:
        yield
        return
    target = None
    normalized = str(output_name or "").strip().casefold()
    for node in material_capture_nodes.iter_custom_outputs(mat):
        name = str(getattr(node, "output_name", "") or "").strip()
        if name.casefold() == normalized:
            target = node
            break
    if target is not None and target.inputs and target.inputs[0].links:
        source_socket = target.inputs[0].links[0].from_socket
        with _emit_reroute(mat, "__CUSTOM__", source_socket=source_socket):
            yield
        return
    default_color = (0.0, 0.0, 0.0, 1.0)
    if target is not None and target.inputs:
        try:
            value = target.inputs[0].default_value
            if hasattr(value, "__len__"):
                comps = list(value)
                if len(comps) >= 3:
                    default_color = (
                        comps[0],
                        comps[1],
                        comps[2],
                        comps[3] if len(comps) > 3 else 1.0,
                    )
                else:
                    v = float(comps[0])
                    default_color = (v, v, v, 1.0)
            else:
                v = float(value)
                default_color = (v, v, v, 1.0)
        except Exception:
            pass
    with _emit_reroute(mat, "__CUSTOM__", source_socket=None, default_color=default_color):
        yield


def _sources_for_target(source_objects, source_groups, target_index):
    """Sources for one target: its own group's, or the shared list.

    `source_groups` is parallel to the target list. Anything ragged or short falls
    back to the shared list rather than silently baking a target against nothing.
    """
    if not source_groups:
        return list(source_objects or [])
    try:
        group = source_groups[target_index]
    except (IndexError, TypeError):
        return list(source_objects or [])
    if group is None:
        return list(source_objects or [])
    return list(group)


def bake_material_channel(
    target_objects,
    channel: str,
    width: int,
    height: int,
    source_objects=None,
    on_progress: Callable[[str], None] | None = None,
    scratch_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    margin: int = 4,
    cage_extrusion: float = 0.0,
    source_image=None,
    uv_offset_u: float = 0.0,
    uv_offset_v: float = 0.0,
    custom_output_name: str = "",
    artist_facing: bool = True,
    device: str = "CPU",
    source_groups=None,
    normal_relief: float | None = None,
    uv_layer_name: str = "",
    fitted_cages=(),
    normal_flip_green: bool = False,
    cage_extrusions=(),
) -> str:
    """Bake a material channel from source objects onto target-object UVs.

    ``artist_facing`` marks an output the user receives, as opposed to a hidden
    material-detail transfer layer. Only the former gets the wider EXTEND margin
    (see :func:`_bake_margin_type`); a detail layer keeps whatever the scene is set
    to, because ``material_detail.py`` reads its alpha as the coverage mask and
    widening that would composite detail into the gutter.

    ``device`` is the Cycles device. It stays CPU by default because the usual
    caller runs this queue *beside* a live FYR GPU bake; a Cycles-primary caller
    passes :func:`resolve_material_bake_device` so the user's GPU is actually used.

    ``source_groups`` gives each target its OWN sources, parallel to
    ``target_objects``; ``None`` uses ``source_objects`` for all of them. Groups
    sharing a texture set bake into ONE image here, and each low has to keep
    projecting from its own group's highs -- a merged source list would let a
    neighbouring high win the cage ray wherever two objects touch in 3D.

    ``uv_layer_name`` is the group's UV Set override: the bake rasterizes into that
    layer (Blender's ``uv_layer``) while the materials keep sampling active_render,
    so a self-bake still reads its textures through the material UVs. "" bakes into
    active_render as before.

    ``fitted_cages`` are the Automatic cages the export fitted
    (cycles_projection.FittedCage): a target with one traces from it, as the GPU
    does, and ``cage_extrusion`` is only the fallback for a target without one.
    """
    import bpy

    target_objects = list(target_objects) if isinstance(target_objects, (list, tuple)) else [target_objects]
    if source_objects is None:
        source_objects = []
    else:
        source_objects = list(source_objects) if isinstance(source_objects, (list, tuple)) else [source_objects]
    if not target_objects:
        raise RuntimeError("Material bake has no target objects")
    uv_layer_name = str(uv_layer_name or "")
    _require_bake_uv_layer(target_objects, uv_layer_name)

    channel = str(channel or "").strip().upper()
    scene = bpy.context.scene
    image_name = f"__mb_material_bake_{channel.lower()}__"
    # Memory preflight. A plan with one strip runs the unchanged whole-image path below;
    # more strips bake the same channel window by window (see cycles_memory).
    shading_objects = source_objects or target_objects
    planned_strategy = "emit" if custom_output_name else _resolve_strategy(
        channel, _shading_materials_of(shading_objects)
    )
    normal_supersample = (
        _EMIT_NORMAL_SUPERSAMPLE
        if planned_strategy == "emit_normal" and _EMIT_NORMAL_SUPERSAMPLE > 1
        else 1
    )
    bake_width = int(width) * normal_supersample
    bake_height = int(height) * normal_supersample
    bake_margin = int(margin) * normal_supersample
    strip_plan = _plan_material_strips(
        target_objects, source_objects, source_groups, channel,
        bake_width, bake_height, bake_margin,
        planned_strategy, _shading_materials_of(shading_objects),
    )
    striped = not strip_plan.single
    # Strip path already windows the atlas; skip supersample there (finalize still
    # neutral-fills voids so EMIT does not leave black seam padding).
    if striped:
        normal_supersample = 1
        bake_width, bake_height, bake_margin = int(width), int(height), int(margin)
        strip_plan = _plan_material_strips(
            target_objects, source_objects, source_groups, channel,
            bake_width, bake_height, bake_margin,
            planned_strategy, _shading_materials_of(shading_objects),
        )
    normal_fill = _tangent_normal_fill(channel, planned_strategy)
    if striped:
        image = _make_strip_image(image_name, bake_width, strip_plan.strip_rows, channel)
    else:
        image = _make_bake_target_image(
            image_name, bake_width, bake_height, channel,
            offset_u=uv_offset_u, offset_v=uv_offset_v,
            fill_rgba=normal_fill,
        )
    uv_layers = None
    assembler = None
    injected_nodes: list[tuple] = []
    temporary_materials: list[tuple] = []
    view_layer_objects = getattr(getattr(bpy.context, "view_layer", None), "objects", None)
    original_selected = [
        item for item in (view_layer_objects or [])
        if bool(getattr(item, "select_get", lambda: False)())
    ]
    original_active = getattr(view_layer_objects, "active", None) if view_layer_objects is not None else None
    # Opened before anything else is staged and closed at the old restore point in
    # `finally`: re-including a collection resets hide state, see
    # ensured_bake_visibility.
    visibility = ExitStack()

    try:
        try:
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        visibility.enter_context(
            ensured_bake_visibility(list(target_objects) + list(source_objects))
        )
        # Entered after the visibility lift so its temporary cages leave first.
        world_cages = visibility.enter_context(WorldDistanceCages())
        fitted_by_low = _fitted_cages_by_low(fitted_cages)
        # Outside the strip UVs, so the strips derive from (and restore to) this state.
        visibility.enter_context(bake_uv_layer_active(target_objects, uv_layer_name))
        if striped:
            from . import cycles_memory

            uv_layers = _material_uv_layers(
                target_objects, source_objects, source_groups, strip_plan, uv_offset_u, uv_offset_v,
                uv_layer_name,
            )
            uv_layers.open()
            output_path = _resolve_material_output_path(output_path, scratch_dir, image_name, channel)
            assembler = cycles_memory.StripAssembler(output_path, width, height)
        # Target image nodes belong to the LOW objects. A material-less low gets a
        # temporary host material so users do not have to prepare one manually.
        seen_target_materials = set()
        for target in target_objects:
            materials = [
                slot.material for slot in getattr(target, "material_slots", [])
                if slot and slot.material is not None
            ]
            if not materials:
                material = bpy.data.materials.new(f"__mb_bake_target_{target.name}__")
                material.use_nodes = True
                target.data.materials.append(material)
                temporary_materials.append((target, material))
                materials = [material]
            for material in materials:
                key = material.as_pointer()
                if key in seen_target_materials:
                    continue
                seen_target_materials.add(key)
                injected_nodes.append((material, _inject_bake_target_node(material, image)))

        shading_objects = source_objects or target_objects
        with _isolated_object_materials(shading_objects):
            shading_materials = []
            seen_shading_materials = set()
            for source in shading_objects:
                for slot in getattr(source, "material_slots", []):
                    material = slot.material if slot else None
                    if material is None or not getattr(material, "use_nodes", False):
                        continue
                    key = material.as_pointer()
                    if key not in seen_shading_materials:
                        seen_shading_materials.add(key)
                        shading_materials.append(material)

            strategy = _resolve_strategy(channel, shading_materials)
            if custom_output_name:
                strategy = "emit"
            # A striped detail layer bakes EXTEND too: ADJACENT_FACES reaches across the
            # whole UV sheet, so a strip could not reproduce it, and only a bake that would
            # otherwise exhaust memory is ever striped.
            # Tangent EMIT normals must not EXTEND across UV islands: that copies
            # conflicting TBN bases into the apron and reads as magenta/cyan seam glitter.
            if strategy == "emit_normal" or _channel_is_tangent_normal(channel):
                margin_type = "ADJACENT_FACES"
                bake_margin = min(int(bake_margin), 8)
            else:
                margin_type = "EXTEND" if (artist_facing or striped) else scene.render.bake.margin_type
            with _saved_render_engine(scene), _saved_cycles_device(
                scene, device
            ), _clamped_cycles_samples(scene, strategy), _bake_margin_type(
                scene, margin_type
            ), _pinned_scene_bake_settings(scene):
                if scene.render.engine != "CYCLES":
                    scene.render.engine = "CYCLES"
                with ExitStack() as reroutes:
                    if strategy == "ao_image":
                        for material in shading_materials:
                            reroutes.enter_context(_ao_image_reroute(material, source_image))
                    elif strategy == "emit_normal":
                        for material in shading_materials:
                            reroutes.enter_context(_material_normal_emit_reroute(material))
                    elif strategy not in {"diffuse_color", "normal"}:
                        for material in shading_materials:
                            if custom_output_name:
                                reroutes.enter_context(_custom_output_reroute(material, custom_output_name))
                            else:
                                reroutes.enter_context(_emit_reroute(material, channel))
                    # Hide render-visible objects that cannot affect this channel's
                    # pixels, like the projection route does (cycles_projection
                    # ._isolated_render_scope). Listed after the visibility lift.
                    from . import cycles_projection

                    scope_targets, scope_sources = _material_bake_participants(
                        target_objects, source_objects, source_groups
                    )
                    reroutes.enter_context(
                        cycles_projection._isolated_render_scope(  # noqa: SLF001
                            list(view_layer_objects or []),
                            scope_targets + scope_sources,
                            enabled=_material_render_scope_enabled(strategy, shading_materials),
                        )
                    )
                    strips = strip_plan.top_down() if striped else [None]
                    for strip_order, strip in enumerate(strips):
                        if strip is not None:
                            if strip_order:
                                cycles_memory.check_strip_fits(
                                    strip_plan, credit_bytes=strip_plan.strip_bytes()
                                )
                            uv_layers.set_window(strip.window_start, strip_plan.strip_rows)
                        for target_index, target in enumerate(target_objects):
                            target_sources = _sources_for_target(
                                source_objects, source_groups, target_index
                            )
                            if view_layer_objects is not None:
                                for other in view_layer_objects:
                                    try:
                                        other.select_set(False)
                                    except Exception:
                                        pass
                            for source in target_sources:
                                source.select_set(True)
                            target.select_set(True)
                            bpy.context.view_layer.objects.active = target
                            _verify_bake_selection(target_sources, target)

                            bake_kwargs = {
                                "use_selected_to_active": bool(target_sources),
                                # Only the FIRST target clears. Every later one
                                # composites into the same image, which is what makes
                                # a shared texture-set file keep all its members. A
                                # detail layer never clears: that paints it opaque.
                                "use_clear": target_index == 0 and channel != "__DETAIL_NORMAL__",
                                "margin": max(0, int(bake_margin)),
                            }
                            if target_sources:
                                bake_kwargs.update(
                                    _material_cage_kwargs(
                                        world_cages, target, cage_extrusion, fitted_by_low, dict(cage_extrusions)
                                    )
                                )
                                bake_kwargs["max_ray_distance"] = 0.0
                            # The UDIM tile needs no UV shift here: the target image is
                            # tiled, and Blender picks the tile from this layer's UVs.
                            if uv_layer_name:
                                bake_kwargs["uv_layer"] = uv_layer_name
                            if strip is not None and uv_layers.layer_name:
                                bake_kwargs["uv_layer"] = uv_layers.layer_name
                            # Synchronous and main-thread by design; see the note in
                            # cycles_projection - without this the hang watchdog fired
                            # once per map on a healthy but slow bake.
                            from . import hang_watchdog

                            with hang_watchdog.suspended(f"Cycles material bake {channel}"):
                                if strategy == "diffuse_color":
                                    result = bpy.ops.object.bake(
                                        type="DIFFUSE",
                                        pass_filter={"COLOR"},
                                        **bake_kwargs,
                                    )
                                elif strategy == "normal":
                                    result = bpy.ops.object.bake(type="NORMAL", **bake_kwargs)
                                else:
                                    result = bpy.ops.object.bake(type="EMIT", **bake_kwargs)
                            if "FINISHED" not in result:
                                raise RuntimeError(f"Blender bake returned {sorted(result)}")
                        if strip is not None:
                            assembler.add_strip(image, strip, strip_plan.strip_rows)

        if on_progress:
            on_progress(f"Baked {channel} via Cycles")

        if striped:
            return assembler.commit()
        # Write the requested format. The old path wrote EXR and renamed its bytes
        # to .tga, producing a 256 MiB file that only looked like a TGA by filename.
        output_path = _resolve_material_output_path(output_path, scratch_dir, image_name, channel)
        if planned_strategy == "emit_normal" or _channel_is_tangent_normal(channel):
            # use_clear leaves uncovered atlas texels black; EMIT does not fill them
            # the way Cycles NORMAL does. Neutral-fill (+ optional 2× downsample)
            # stops UV filtering from reading black at island edges as dark seams.
            # Relief remaps glitter/amplify only for emit_normal; other tangent
            # paths keep the Relief=0.5 module baselines.
            finalize_relief = (
                normal_relief if planned_strategy == "emit_normal" else None
            )
            finalized = _finalize_tangent_normal_bake_image(
                image,
                width=int(width),
                height=int(height),
                relief=finalize_relief,
                void_fill=normal_fill or _TANGENT_NORMAL_NEUTRAL,
            )
            if finalized is not image:
                try:
                    bpy.data.images.remove(image)
                except Exception:
                    pass
                image = finalized
            if normal_flip_green:
                _flip_tangent_normal_green(image)
        _save_bake_target_image(image, output_path)
        return str(output_path)

    finally:
        if uv_layers is not None:
            uv_layers.close()
        if assembler is not None:
            assembler.abort()
        for material, node in injected_nodes:
            try:
                _remove_bake_target_node(material, node)
            except Exception:
                pass
        for target, material in reversed(temporary_materials):
            try:
                name = str(getattr(material, "name", "") or "")
                for index in range(len(target.data.materials) - 1, -1, -1):
                    if target.data.materials[index] == material:
                        target.data.materials.pop(index=index)
                if name:
                    _queue_deferred_id_purge("MATERIAL", name)
            except Exception:
                pass
        try:
            name = str(getattr(image, "name", "") or "")
            if name:
                _queue_deferred_id_purge("IMAGE", name)
        except Exception:
            pass
        try:
            visibility.close()
        except Exception:
            pass
        if view_layer_objects is not None:
            for item in view_layer_objects:
                try:
                    item.select_set(False)
                except Exception:
                    pass
            for item in original_selected:
                try:
                    item.select_set(True)
                except Exception:
                    pass
            try:
                view_layer_objects.active = original_active
            except Exception:
                pass


class MaterialBakeSession:
    """One non-blocking Blender bake, advanced from a bpy timer.

    Blender's OBJECT_BAKE job is asynchronous only when invoked. The session
    deliberately owns every temporary datablock and node reroute until that job
    finishes; restoring them immediately is the common cause of blank modal bakes.
    """

    # Striped-bake state (cycles_memory), as class defaults so a session built without
    # __init__ (tests, or a subclass) still reads as an unstriped one.
    _strip_plan = None
    _strips: tuple = ()
    _strip_order = 0
    _uv_layers = None
    _assembler = None
    _render_scope = None
    _active_uv = None
    _done = False
    _handler_guard_held = False
    uv_layer_name = ""

    def __init__(
        self,
        target_objects,
        channel: str,
        width: int,
        height: int,
        *,
        source_objects=None,
        output_path: str | Path,
        margin: int = 4,
        cage_extrusion: float = 0.0,
        source_image=None,
        uv_offset_u: float = 0.0,
        uv_offset_v: float = 0.0,
        custom_output_name: str = "",
        artist_facing: bool = True,
        device: str = "CPU",
        source_groups=None,
        normal_relief: float | None = None,
        uv_layer_name: str = "",
        fitted_cages=(),
        normal_flip_green: bool = False,
        cage_extrusions=(),
    ):
        self.target_objects = list(target_objects)
        # Per-target sources; see _sources_for_target and bake_material_channel.
        self.source_groups = list(source_groups) if source_groups else []
        self.source_objects = list(source_objects or [])
        self.channel = str(channel or "").strip().upper()
        self.width = int(width)
        self.height = int(height)
        self.output_path = Path(output_path)
        self.margin = max(0, int(margin))
        self.cage_extrusion = max(0.0, float(cage_extrusion))
        self.source_image = source_image
        self.uv_offset_u = float(uv_offset_u)
        self.uv_offset_v = float(uv_offset_v)
        self.custom_output_name = str(custom_output_name or "").strip()
        # See bake_material_channel.
        self.artist_facing = bool(artist_facing)
        self.device = str(device or "CPU").strip().upper() or "CPU"
        self.normal_relief = (
            None if normal_relief is None else min(max(float(normal_relief), 0.0), 1.0)
        )
        # The group's bake UV set; see bake_material_channel.
        self.uv_layer_name = str(uv_layer_name or "")
        self.normal_flip_green = bool(normal_flip_green)
        # Automatic cages per low; see bake_material_channel.
        self._fitted_by_low = _fitted_cages_by_low(fitted_cages)
        self._extrusion_by_low = dict(cage_extrusions)
        self.error = ""
        self.finished = False
        self._target_index = 0
        self._waiting_for_job = False
        # `bpy.app.is_job_running("OBJECT_BAKE")` reports False in the gap between
        # invoking a modal bake and Blender registering the job. Treating that gap as
        # completion tears the session down mid-bake, so a job has to be SEEN running
        # before "not running" is allowed to mean "done".
        self._job_observed = False
        self._job_start_polls = 0
        self._setup_complete = False
        self._image = None
        self._injected_nodes = []
        self._temporary_materials = []
        self._reroutes = ExitStack()
        self._material_isolation = None
        self._view_layer_objects = None
        self._original_selected = []
        self._original_active = None
        self._scene = None
        self._original_engine = None
        self._original_cycles_device = None
        self._original_margin_type = None
        self._original_samples = None
        self._visibility = None
        self._strategy = ""
        # ``_strip_plan`` is None until _setup; a single-strip plan leaves the striped
        # fields unused and the session runs the whole-image path unchanged.
        self._render_scope = ExitStack()
        # Temporary cages for non-uniformly scaled lows; see WorldDistanceCages.
        self._world_cages = WorldDistanceCages()

    def _enter_active_uv_layer(self) -> None:
        """The UV Set becomes the active layer until _cleanup; see bake_uv_layer_active."""
        if self._active_uv is None:
            self._active_uv = ExitStack()
            self._active_uv.enter_context(bake_uv_layer_active(self.target_objects, self.uv_layer_name))

    @staticmethod
    def _job_running() -> bool:
        import bpy
        try:
            return bool(bpy.app.is_job_running("OBJECT_BAKE"))
        except (AttributeError, TypeError):
            return False

    def _setup(self):
        import bpy

        if not self.target_objects:
            raise RuntimeError("Material bake has no target objects")
        _require_bake_uv_layer(self.target_objects, self.uv_layer_name)
        # The invoked bake builds its render depsgraph on the job thread, which calls
        # every add-on's depsgraph handlers off the main thread against the context
        # the viewport is drawing with (see handler_thread_guard). Held until _cleanup.
        handler_thread_guard.acquire()
        self._handler_guard_held = True
        self._scene = bpy.context.scene
        self._original_engine = self._scene.render.engine
        cycles = getattr(self._scene, "cycles", None)
        if cycles is not None and hasattr(cycles, "device"):
            self._original_cycles_device = cycles.device
            cycles.device = self.device
        if self.artist_facing:
            bake_settings = getattr(getattr(self._scene, "render", None), "bake", None)
            if bake_settings is not None:
                try:
                    self._original_margin_type = bake_settings.margin_type
                    bake_settings.margin_type = "EXTEND"
                except (AttributeError, TypeError, ValueError):
                    self._original_margin_type = None

        # Even an identical assignment tears down the render engine. Between UDIM
        # sessions Cycles can still be finishing the preceding job; reassigning
        # CYCLES here then deadlocks Blender's main thread against that teardown.
        if self._scene.render.engine != "CYCLES":
            self._scene.render.engine = "CYCLES"
        # bpy.ops.object.bake only sees visible, selectable bases: a hidden low or
        # high mesh is dropped from selected_editable_objects and Blender reports the
        # opaque "No valid selected objects". Reveal every participant (local view
        # included) for the whole async job and restore the user's exact state in
        # _cleanup.
        self._visibility = ExitStack()
        self._visibility.enter_context(
            ensured_bake_visibility(list(self.target_objects) + list(self.source_objects))
        )
        self._view_layer_objects = getattr(getattr(bpy.context, "view_layer", None), "objects", None)
        if self._view_layer_objects is not None:
            self._original_selected = [
                item for item in self._view_layer_objects
                if bool(getattr(item, "select_get", lambda: False)())
            ]
            self._original_active = getattr(self._view_layer_objects, "active", None)

        # Memory preflight before the target image exists. One strip = the whole-image
        # path; more strips bake the channel window by window (cycles_memory).
        shading_candidates = list(self.source_objects or self.target_objects)
        planned_strategy = "emit" if self.custom_output_name else _resolve_strategy(
            self.channel, _shading_materials_of(shading_candidates)
        )
        self._planned_strategy = planned_strategy
        self._normal_supersample = (
            _EMIT_NORMAL_SUPERSAMPLE
            if planned_strategy == "emit_normal" and _EMIT_NORMAL_SUPERSAMPLE > 1
            else 1
        )
        bake_width = self.width * self._normal_supersample
        bake_height = self.height * self._normal_supersample
        bake_margin = self.margin * self._normal_supersample
        if cycles is not None and hasattr(cycles, "samples"):
            # Uncapped, a material channel inherits the scene's render samples --
            # 4096 by default. With adaptive sampling on that costs nothing, but with
            # it off (a common artist setting) a 4K channel runs for tens of minutes.
            # Measured 2026-08-19 at 512, adaptive off: 4096spp 23.7s -> 64spp 6.5s,
            # with not one 8-bit texel changed (mean |d| 5.2e-5, max 2.1e-3).
            # emit_normal forces 1 sample so RGB AA does not dilute encoded slopes;
            # footprint filtering comes from 2× normal-space downsample instead.
            self._original_samples = cycles.samples
            cycles.samples = material_bake_sample_count(self._scene, planned_strategy)
        self._strip_plan = _plan_material_strips(
            self.target_objects, self.source_objects, self.source_groups, self.channel,
            bake_width, bake_height, bake_margin, planned_strategy,
            _shading_materials_of(shading_candidates),
        )
        # Before any strip UVs exist, so they derive from (and restore to) this state.
        self._enter_active_uv_layer()
        if self._striped:
            from . import cycles_memory

            # Strip path windows the atlas; keep request resolution (finalize still
            # neutral-fills EMIT voids).
            self._normal_supersample = 1
            bake_width, bake_height, bake_margin = self.width, self.height, self.margin
            self._strip_plan = _plan_material_strips(
                self.target_objects, self.source_objects, self.source_groups, self.channel,
                bake_width, bake_height, bake_margin, planned_strategy,
                _shading_materials_of(shading_candidates),
            )
            if not self.artist_facing:
                # See bake_material_channel: a striped detail layer bakes EXTEND too.
                bake_settings = getattr(getattr(self._scene, "render", None), "bake", None)
                if bake_settings is not None:
                    try:
                        self._original_margin_type = bake_settings.margin_type
                        bake_settings.margin_type = "EXTEND"
                    except (AttributeError, TypeError, ValueError):
                        self._original_margin_type = None
            self._strips = self._strip_plan.top_down()
            self._image = _make_strip_image(
                f"__mb_material_bake_{self.channel.lower()}__",
                bake_width,
                self._strip_plan.strip_rows,
                self.channel,
            )
            self._uv_layers = _material_uv_layers(
                self.target_objects, self.source_objects, self.source_groups,
                self._strip_plan, self.uv_offset_u, self.uv_offset_v,
                self.uv_layer_name,
            )
            self._uv_layers.open()
            self._assembler = cycles_memory.StripAssembler(self.output_path, self.width, self.height)
        else:
            normal_fill = _tangent_normal_fill(self.channel, planned_strategy)
            self._image = _make_bake_target_image(
                f"__mb_material_bake_{self.channel.lower()}__",
                bake_width,
                bake_height,
                self.channel,
                offset_u=self.uv_offset_u, offset_v=self.uv_offset_v,
                fill_rgba=normal_fill,
            )
        self._bake_margin = bake_margin
        seen_target_materials = set()
        for target in self.target_objects:
            materials = [
                slot.material for slot in getattr(target, "material_slots", [])
                if slot and slot.material is not None
            ]
            if not materials:
                material = bpy.data.materials.new(f"__mb_bake_target_{target.name}__")
                material.use_nodes = True
                target.data.materials.append(material)
                self._temporary_materials.append((target, material))
                materials = [material]
            for material in materials:
                key = material.as_pointer()
                if key in seen_target_materials:
                    continue
                seen_target_materials.add(key)
                self._injected_nodes.append((material, _inject_bake_target_node(material, self._image)))

        shading_objects = list(self.source_objects or self.target_objects)
        # Keep Emission/AO reroutes on temporary material copies so linked library
        # materials and the user's authored graphs stay untouched for the whole
        # async bake job (same contract as bake_material_channel).
        self._material_isolation = ExitStack()
        self._material_isolation.enter_context(_isolated_object_materials(shading_objects))
        # Held for the whole async job, like the material isolation: every property we
        # do not pass to bpy.ops.object.bake comes from the artist's Bake panel.
        self._material_isolation.enter_context(
            _pinned_scene_bake_settings(getattr(bpy.context, "scene", None))
        )
        shading_materials = []
        seen = set()
        for source in shading_objects:
            for slot in getattr(source, "material_slots", []):
                material = slot.material if slot else None
                if material is None or not getattr(material, "use_nodes", False):
                    continue
                key = material.as_pointer()
                if key in seen:
                    continue
                seen.add(key)
                shading_materials.append(material)
        strategy = _resolve_strategy(self.channel, shading_materials)
        if self.custom_output_name:
            strategy = "emit"
        self._strategy = strategy
        if strategy == "ao_image":
            for material in shading_materials:
                self._reroutes.enter_context(_ao_image_reroute(material, self.source_image))
        elif strategy == "emit_normal":
            for material in shading_materials:
                self._reroutes.enter_context(_material_normal_emit_reroute(material))
        elif strategy not in {"diffuse_color", "normal"}:
            for material in shading_materials:
                if self.custom_output_name:
                    self._reroutes.enter_context(_custom_output_reroute(material, self.custom_output_name))
                else:
                    self._reroutes.enter_context(_emit_reroute(material, self.channel))
        # Held for the whole async job like the reroutes; see bake_material_channel.
        from . import cycles_projection

        scope_targets, scope_sources = _material_bake_participants(
            self.target_objects, self.source_objects, self.source_groups
        )
        if self._render_scope is None:
            self._render_scope = ExitStack()
        self._render_scope.enter_context(
            cycles_projection._isolated_render_scope(  # noqa: SLF001
                list(self._view_layer_objects or []),
                scope_targets + scope_sources,
                enabled=_material_render_scope_enabled(strategy, shading_materials),
            )
        )
        if self._striped:
            self._begin_strip()
        self._setup_complete = True

    @property
    def _striped(self) -> bool:
        return self._strip_plan is not None and not self._strip_plan.single

    def _begin_strip(self) -> None:
        """Point the strip UVs at the next window, re-checking memory first."""
        from . import cycles_memory

        if self._strip_order:
            cycles_memory.check_strip_fits(
                self._strip_plan, credit_bytes=self._strip_plan.strip_bytes()
            )
        strip = self._strips[self._strip_order]
        self._uv_layers.set_window(strip.window_start, self._strip_plan.strip_rows)

    def _finish_strip(self) -> None:
        strip = self._strips[self._strip_order]
        self._assembler.add_strip(self._image, strip, self._strip_plan.strip_rows)

    def _invoke_target(self):
        import bpy

        target = self.target_objects[self._target_index]
        target_sources = _sources_for_target(
            self.source_objects, self.source_groups, self._target_index
        )
        if self._view_layer_objects is not None:
            for other in self._view_layer_objects:
                try:
                    other.select_set(False)
                except Exception:
                    pass
        for source in target_sources:
            source.select_set(True)
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        _verify_bake_selection(target_sources, target)
        kwargs = {
            "use_selected_to_active": bool(target_sources),
            # Only the first target clears; the rest composite into the same image so
            # a shared texture-set file keeps every member's islands. A detail layer
            # never clears: that paints it opaque.
            "use_clear": self._target_index == 0 and self.channel != "__DETAIL_NORMAL__",
            "margin": getattr(self, "_bake_margin", self.margin),
        }
        if target_sources:
            kwargs.update(
                _material_cage_kwargs(
                    self._world_cages, target, self.cage_extrusion, self._fitted_by_low, self._extrusion_by_low
                )
            )
            kwargs["max_ray_distance"] = 0.0
        if self.uv_layer_name:
            kwargs["uv_layer"] = self.uv_layer_name
        if self._striped and self._uv_layers.layer_name:
            kwargs["uv_layer"] = self._uv_layers.layer_name
        strategy = self._strategy or _resolve_strategy(self.channel, [])
        if strategy == "diffuse_color":
            result = bpy.ops.object.bake(
                "INVOKE_DEFAULT", type="DIFFUSE", pass_filter={"COLOR"}, **kwargs
            )
        elif strategy == "normal":
            result = bpy.ops.object.bake("INVOKE_DEFAULT", type="NORMAL", **kwargs)
        else:
            result = bpy.ops.object.bake("INVOKE_DEFAULT", type="EMIT", **kwargs)
        if not ({"RUNNING_MODAL", "FINISHED"} & set(result)):
            raise RuntimeError(f"Blender bake returned {sorted(result)}")
        self._waiting_for_job = "RUNNING_MODAL" in result

    def _save(self):
        if self._striped:
            self._finish_strip()
            self._assembler.commit()
            return
        strategy = getattr(self, "_planned_strategy", None) or self._strategy
        if strategy == "emit_normal" or _channel_is_tangent_normal(self.channel):
            finalize_relief = (
                getattr(self, "normal_relief", None)
                if strategy == "emit_normal"
                else None
            )
            finalized = _finalize_tangent_normal_bake_image(
                self._image,
                width=self.width,
                height=self.height,
                relief=finalize_relief,
                void_fill=_tangent_normal_fill(self.channel, strategy) or _TANGENT_NORMAL_NEUTRAL,
            )
            if finalized is not self._image:
                try:
                    import bpy
                    bpy.data.images.remove(self._image)
                except Exception:
                    pass
                self._image = finalized
            if getattr(self, "normal_flip_green", False):
                _flip_tangent_normal_green(self._image)
        _save_bake_target_image(self._image, self.output_path)

    def _cleanup(self):
        import bpy

        if self._handler_guard_held:
            # _cleanup runs only once no OBJECT_BAKE job is left running (poll waits
            # the job out first), so the job thread can no longer call handlers.
            self._handler_guard_held = False
            handler_thread_guard.release()
        try:
            self._reroutes.close()
        except Exception:
            pass
        try:
            self._world_cages.close()
        except Exception:
            pass
        render_scope, self._render_scope = self._render_scope, None
        if render_scope is not None:
            try:
                render_scope.close()
            except Exception:
                pass
        uv_layers, self._uv_layers = self._uv_layers, None
        if uv_layers is not None:
            uv_layers.close()
        active_uv, self._active_uv = self._active_uv, None
        if active_uv is not None:
            try:
                active_uv.close()
            except Exception:
                pass
        assembler, self._assembler = self._assembler, None
        if assembler is not None:
            assembler.abort()
        try:
            isolation = getattr(self, "_material_isolation", None)
            if isolation is not None:
                isolation.close()
                self._material_isolation = None
        except Exception:
            pass
        for material, node in self._injected_nodes:
            try:
                _remove_bake_target_node(material, node)
            except Exception:
                pass
        for target, material in reversed(self._temporary_materials):
            try:
                for index in range(len(target.data.materials) - 1, -1, -1):
                    if target.data.materials[index] == material:
                        target.data.materials.pop(index=index)
                # Deferred like the synchronous path: removing the datablock on the
                # tick the job ends, while the depsgraph/preview still holds it, is
                # the temp-datablock crash class.
                _queue_deferred_id_purge("MATERIAL", str(getattr(material, "name", "") or ""))
            except Exception:
                pass
        if self._image is not None:
            try:
                image_cleanup.remove_image_when_safe(self._image, reason="material bake target")
            except Exception:
                pass
        visibility = getattr(self, "_visibility", None)
        self._visibility = None
        if visibility is not None:
            try:
                visibility.close()
            except Exception:
                pass
        if self._scene is not None and self._original_engine is not None:
            # NEVER assign scene.render.engine from here. The assignment tears down
            # render engines and blocks the calling thread until a bake in flight
            # finishes — and this runs ON the main thread, which is what that bake
            # needs to make progress: a hard deadlock (0% CPU, kill required,
            # reproduced twice on 2026-08-23). `is_job_running` is not a sufficient
            # guard either: the second hang took the "no job" branch while Cycles was
            # still tearing down. The restore is handed to a timer that waits for the
            # whole material queue to go idle, so it lands with Blender at rest and
            # once per queue rather than once per session.
            _defer_scene_bake_restore(
                scene_name=str(getattr(self._scene, "name", "") or ""),
                engine=self._original_engine,
                margin_type=self._original_margin_type,
                cycles_device=self._original_cycles_device,
                cycles_samples=self._original_samples,
            )
            self._original_margin_type = None
            self._original_samples = None
        if self._view_layer_objects is not None:
            for item in self._view_layer_objects:
                try:
                    item.select_set(False)
                except Exception:
                    pass
            for item in self._original_selected:
                try:
                    item.select_set(True)
                except Exception:
                    pass
            try:
                self._view_layer_objects.active = self._original_active
            except Exception:
                pass

    def poll(self) -> bool:
        """Advance the session. Return True once it is complete."""
        if self.finished:
            return True
        try:
            if not self._setup_complete:
                self._setup()
                self._invoke_target()
                return False
            if self._handler_guard_held:
                handler_thread_guard.refresh()
            if self._waiting_for_job:
                if self._job_running():
                    self._job_observed = True
                    return False
                if not self._job_observed:
                    # Invoked, not yet registered. Falling through here would run
                    # _save() and _cleanup() while the bake is still about to write
                    # into the target image -- and _cleanup restores
                    # scene.render.engine, which BLOCKS against a live bake job. That
                    # is the freeze: one target hid the race because the gap sat at
                    # the end of the only bake; merging a texture set's groups into
                    # one session made the path run once per member.
                    self._job_start_polls += 1
                    if self._job_start_polls < _JOB_START_GRACE_POLLS:
                        return False
            if self._job_running():
                # The grace can expire on a job that registered late (a slow device
                # init) — never overlap it with the next invoke or run _save/_cleanup
                # against it; wait it out like an observed job.
                self._job_observed = True
                return False
            self._waiting_for_job = False
            self._job_observed = False
            self._job_start_polls = 0
            self._target_index += 1
            if self._target_index < len(self.target_objects):
                self._invoke_target()
                return False
            if self._striped and self._strip_order + 1 < len(self._strips):
                # (strip, target) order: every target composites into this strip
                # before the next window starts, and only the first target clears.
                self._finish_strip()
                self._strip_order += 1
                self._target_index = 0
                self._begin_strip()
                self._invoke_target()
                return False
            self._save()
            self._done = True
        except Exception as exc:
            self.error = str(exc)
        finally:
            if self.error or self._done:
                self._cleanup()
                self.finished = True
        return self.finished


# ---------------------------------------------------------------- registration

def _clear_deferred_state() -> None:
    """Drop every pending deferred purge/restore and the flags that gate them.

    Blender frees all app timers when a file is loaded and when the addon is
    disabled. The module-level bookkeeping does not go with them, so a stale
    ``_DEFERRED_PURGE_TIMER_REGISTERED`` made every later purge request think a
    timer was already running, and a stale ``_PENDING_SCENE_RESTORES`` entry made
    every later restore for that scene fold into a request that no longer exists.
    Both were then silently skipped for the rest of the session.
    """
    global _DEFERRED_PURGE_TIMER_REGISTERED
    _DEFERRED_PURGE_TIMER_REGISTERED = False
    _DEFERRED_PURGE_IDS.clear()
    # The scene-restore timers are per-scene closures; clearing the dict makes each
    # orphan return None on its next tick, which unregisters it.
    _PENDING_SCENE_RESTORES.clear()


def _unregister_deferred_purge_timer() -> None:
    try:
        import bpy

        timers = bpy.app.timers
        if timers.is_registered(_deferred_id_purge_timer):
            timers.unregister(_deferred_id_purge_timer)
    except Exception:
        pass


def _load_post(_filepath=None) -> None:
    _clear_deferred_state()
    # A file load kills the bake job and frees the timer driving its session, so the
    # session's _cleanup never runs to release the handler guard.
    handler_thread_guard.reset(after_file_load=True)


#: The load_post callback actually appended to the handler list. `@persistent` is
#: applied at register time because `bpy` is not importable when this module is.
_LOAD_POST_HANDLER = None


def register() -> None:
    global _LOAD_POST_HANDLER
    _clear_deferred_state()
    try:
        import bpy

        handlers = bpy.app.handlers
        persistent = getattr(handlers, "persistent", None)
        _LOAD_POST_HANDLER = persistent(_load_post) if callable(persistent) else _load_post
        load_post = getattr(handlers, "load_post", None)
        if load_post is not None and _LOAD_POST_HANDLER not in load_post:
            load_post.append(_LOAD_POST_HANDLER)
    except Exception:
        _LOAD_POST_HANDLER = None
    try:
        handler_thread_guard.register()
    except Exception:
        pass


def unregister() -> None:
    global _LOAD_POST_HANDLER
    try:
        import bpy

        load_post = getattr(getattr(getattr(bpy, "app", None), "handlers", None), "load_post", None)
        if load_post is not None and _LOAD_POST_HANDLER is not None and _LOAD_POST_HANDLER in load_post:
            load_post.remove(_LOAD_POST_HANDLER)
    except Exception:
        pass
    _LOAD_POST_HANDLER = None
    _unregister_deferred_purge_timer()
    _clear_deferred_state()
    handler_thread_guard.unregister()
