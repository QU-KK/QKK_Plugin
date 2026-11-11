"""Paint Offset / Paint Skew brush: a Fyr tool in Object Mode.

Replaces the Texture Paint session (image canvas, joined proxy object, hidden originals).
Entering Paint Offset or Paint Skew activates a toolbar tool in Object Mode; every
left-button stroke runs ``master_baker.paint_brush_stroke``, a short modal operator that
edits the session's numpy buffers per dab and writes the result once, on release, so each
stroke is one ordinary undo step.

Paint Offset lives per face corner in ``paint_sampling.OFFSET_ATTRIBUTE`` on each low mesh.
Paint Skew is a per-texel correction map per UDIM tile of the group's bake UV layer
(``paint_sampling.skew_correction_tiles``), Painter / Marmoset style: painted = the ray
straightens toward the low's flat face normal. The exporter, the cage display and the
needles read both through paint_sampling / cage, so what is drawn here is what bakes. The live overlay (value tint, cage wire, skew needles) is
drawn by this module from the session buffers; the static cage / needle passes of the
painted group are held back while a session is live and rebuilt once when it ends.

The session keeps object and mesh NAMES only, never RNA references: an undo step frees
and reallocates every datablock (the RNA identity crash class), so ``reload_values``
re-reads the layers by name from ``undo_post``.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

import bpy
import gpu
import numpy as np
from mathutils import Matrix, Vector

from . import rna_buffers
from . import cage, constants, paint_brush_core as core, paint_sampling, properties

# bpy_extras / gpu_extras / mathutils.bvhtree are imported where used: the unit tests load
# this module (through operators) against a stub bpy that has none of them.
_persistent = getattr(getattr(getattr(bpy, "app", None), "handlers", None), "persistent", None) or (lambda fn: fn)
_WorkSpaceTool = getattr(getattr(bpy, "types", None), "WorkSpaceTool", object)


def batch_for_shader(*args, **kwargs):
    from gpu_extras.batch import batch_for_shader as _batch_for_shader

    return _batch_for_shader(*args, **kwargs)


KIND_OFFSET = "OFFSET"
KIND_SKEW = "SKEW"

TOOL_OFFSET_ID = "master_baker.paint_offset_tool"
TOOL_SKEW_ID = "master_baker.paint_skew_tool"
TOOL_IDS = {KIND_OFFSET: TOOL_OFFSET_ID, KIND_SKEW: TOOL_SKEW_ID}

#: Scene property: the tool that was active before the session, restored on exit.
PREVIOUS_TOOL_KEY = "_fyr_paint_previous_tool"

_BRUSH_PATH = "scene.fyr_baker_settings.paint_brush"

_SESSION: "PaintSession | None" = None
_DRAW_HANDLES: list = []
_SHADERS: dict = {}
#: Original mesh/object pointers whose last change was a paint-layer write by the brush,
#: with the time of the write; the overlay depsgraph handler skips them for a moment.
_PAINT_ONLY_POINTERS: dict[int, float] = {}
_PAINT_ONLY_WINDOW_SECONDS = 1.0


#: Texel rings the skew correction is padded past the UV islands on every commit, so the
#: backend's bilinear taps at island borders (and its bake padding) read painted values.
_SKEW_DILATION_TEXELS = 8


def _kind_bounds(kind: str) -> tuple[float, float]:
    if kind == KIND_OFFSET:
        return paint_sampling.OFFSET_VALUE_MIN, paint_sampling.OFFSET_VALUE_MAX
    return 0.0, 1.0


def brush_settings(context=None):
    context = context or bpy.context
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    return getattr(settings, "paint_brush", None)


# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------


@dataclass
class _ObjectEntry:
    name: str
    mesh_name: str
    loop_start: int
    loop_count: int
    matrix_world: Matrix
    matrix_inverse: Matrix
    bvh: object
    slot_offset_delta: float = 0.0
    group_name: str = ""


@dataclass
class _SkewTile:
    """One UDIM tile of the skew correction map while a session paints it."""

    tile: int
    width: int
    height: int
    grid: np.ndarray  # float32 [height * width], row 0 = v bottom
    covered: np.ndarray  # bool [height, width]
    pad_destinations: np.ndarray
    pad_sources: np.ndarray
    texture: object = None


@dataclass
class PaintSession:
    kind: str
    project_name: str
    group_name: str
    entries: list[_ObjectEntry]
    loop_values: np.ndarray  # per loop (all entries): offset layer values (0 for skew)
    loop_positions: np.ndarray  # world
    loop_normals: np.ndarray  # world, what the bake projects along (Smooth Cage off: bridged)
    loop_entry: np.ndarray
    loop_point: np.ndarray
    point_positions: np.ndarray
    point_normals: np.ndarray
    point_values: np.ndarray
    point_loop_indptr: np.ndarray
    point_loops: np.ndarray
    adjacency_indptr: np.ndarray
    adjacency_indices: np.ndarray
    labels: np.ndarray
    tri_loops: np.ndarray  # [T, 3] global loop indices
    poly_edge_loops: np.ndarray  # [E, 2] global loop pairs along real polygon edges
    bounds_diagonal: float
    cage_mode: str
    smooth_cage: bool
    base_distance_per_loop: np.ndarray  # Distance cage: world offset before paint
    cage_targets: np.ndarray | None  # caged modes: cage corner per tri corner [T*3, 3]
    # Paint Offset paints every low of the cage scope's groups at once (the anchor,
    # group_name, first); each group's triangles are one contiguous [t0, t1) range.
    group_names: tuple = ()
    group_tri_ranges: dict = field(default_factory=dict)
    loop_offset_scale: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    needle_tris: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int64))
    needle_weights: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float32))
    needle_lengths: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    needles_dirty: bool = False
    needle_starts: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float32))
    needle_loops: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.int64))
    needle_cage_points: np.ndarray | None = None
    tri_positions: np.ndarray = field(default_factory=lambda: np.empty((0, 3, 3), dtype=np.float32))
    tri_bounds: tuple | None = None
    tri_face_normals: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float32))
    dirty_entries: set = field(default_factory=set)
    display_dirty: bool = True
    tint_batch: object = None
    cage_batch: object = None
    cage_surface_batch: object = None
    # The live cage per group in the coverage depth-mask format; built only once the
    # coverage overlay asks for it (live_coverage_cage_batch).
    cage_depth_batches: dict = field(default_factory=dict)
    cage_depth_wanted: bool = False
    last_cage_depth_build: float = 0.0
    cage_depth_pending: bool = False
    needle_batch: object = None
    cursor: tuple | None = None  # (world centre, world normal, world radius, screen xy)
    stroke_active: bool = False
    last_needle_build: float = 0.0
    hud_value: str = ""
    hover_mode: str = ""  # mode the held modifiers select, for the cursor colour
    last_cage_lookup: float = 0.0
    notes: list = field(default_factory=list)
    # Paint Skew only
    loop_uvs: np.ndarray = field(default_factory=lambda: np.empty((0, 2), dtype=np.float32))  # global UV
    legacy_loop_skews: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    tiles: list = field(default_factory=list)  # [_SkewTile]
    texel_tile: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int64))  # index into tiles
    texel_flat: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int64))
    texel_tri: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int64))
    texel_positions: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float32))
    texel_values: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    dirty_tiles: set = field(default_factory=set)
    needle_uvs: np.ndarray = field(default_factory=lambda: np.empty((0, 2), dtype=np.float32))
    tile_batches: list = field(default_factory=list)  # [(tile index, batch)]

    def correction_tiles(self) -> dict:
        """The live map in the paint_sampling.skew_correction_tiles contract."""
        return {
            tile.tile: (tile.width, tile.height, tile.grid.reshape(tile.height, tile.width))
            for tile in self.tiles
        }


def active_session() -> PaintSession | None:
    return _SESSION


def _group_names_of(session: PaintSession) -> tuple:
    return session.group_names or (session.group_name,)


def session_group_names(kind: str | None = None) -> frozenset:
    """Names of every bake group the live session paints (empty when none)."""
    session = _SESSION
    if session is None or (kind is not None and session.kind != kind):
        return frozenset()
    return frozenset(_group_names_of(session))


def session_owns(group, kind: str | None = None) -> bool:
    """True while a live session paints *group* (optionally of *kind*)."""
    session = _SESSION
    if session is None or group is None:
        return False
    if kind is not None and session.kind != kind:
        return False
    return str(getattr(group, "name", "") or "") in _group_names_of(session)


def take_paint_only_update_pointers() -> set[int]:
    """Pointers of datablocks a brush stroke just wrote a layer to (last second only).

    Time-bounded rather than consumed by the first depsgraph update, which may belong to
    something else and arrive before the stroke's own.
    """
    now = time.monotonic()
    for pointer, stamp in list(_PAINT_ONLY_POINTERS.items()):
        if now - stamp > _PAINT_ONLY_WINDOW_SECONDS:
            del _PAINT_ONLY_POINTERS[pointer]
    return set(_PAINT_ONLY_POINTERS)


def _resolve_project_group(context):
    from . import cage_session

    _settings, project, group = cage_session.resolve_project_group(getattr(context, "scene", None))
    return project, group


def _session_group(context, session: PaintSession | None = None):
    session = session or _SESSION
    if session is None:
        return None
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    for project in getattr(settings, "projects", None) or ():
        if str(getattr(project, "name", "") or "") != session.project_name:
            continue
        for group in getattr(project, "groups", None) or ():
            if str(getattr(group, "name", "") or "") == session.group_name:
                return group
    return None


def _session_groups(context, session: PaintSession) -> list:
    """The live groups the session paints, in session order (missing ones skipped)."""
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    for project in getattr(settings, "projects", None) or ():
        if str(getattr(project, "name", "") or "") != session.project_name:
            continue
        by_name = {str(getattr(group, "name", "") or ""): group for group in getattr(project, "groups", None) or ()}
        return [by_name[name] for name in _group_names_of(session) if name in by_name]
    return []


def scope_paint_groups(context, project, group, kind: str) -> tuple[list, list[str]]:
    """The groups one session paints: *group*, plus for Paint Offset its cage-scope siblings.

    The cage panel's Apply-To scope (Texture Set / Global / Selected) already mirrors
    the cage settings across those groups; a sibling whose cage mode or Smooth Cage
    still differs is left out (one live cage cannot follow two projection rules).
    Paint Skew paints per-group UV maps and stays on *group* alone.
    """
    groups = [group]
    notes: list[str] = []
    if kind != KIND_OFFSET:
        return groups, notes
    settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
    try:
        ui_state = properties.scene_ui_state(settings) if settings is not None else None
    except Exception:
        ui_state = None
    scope = str(getattr(ui_state, "cage_settings_scope", "") or "")
    try:
        siblings = properties.cage_scope_target_groups(
            project, group, scope, selected_objects=list(getattr(context, "selected_objects", None) or ())
        )
    except Exception:
        siblings = []
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    smooth = bool(getattr(group, "average_normals", True))
    for sibling in siblings:
        if not _bakeable_lows(sibling):
            continue
        if str(getattr(sibling, "cage_mode", "") or "") != cage_mode or bool(getattr(sibling, "average_normals", True)) != smooth:
            notes.append(f"{sibling.name} has different cage settings and is not painted")
            continue
        groups.append(sibling)
    return groups, notes


def _bakeable_lows(group) -> list:
    from . import export

    return [
        slot.object_ref
        for slot in export._iter_bakeable_low_slots(getattr(group, "low_meshes", []) or [])
        if getattr(getattr(slot, "object_ref", None), "type", "") == "MESH"
    ]


def _slot_offset_delta(group, obj) -> float:
    from . import export

    for slot in export._iter_bakeable_low_slots(getattr(group, "low_meshes", []) or []):
        if getattr(slot, "object_ref", None) == obj:
            return float(export._slot_cage_offset_delta(group, slot))
    return 0.0


def _mesh_writable(mesh) -> bool:
    if mesh is None:
        return False
    if getattr(mesh, "library", None) is not None:
        return False
    if getattr(mesh, "override_library", None) is not None and not getattr(mesh, "is_editable", True):
        return False
    return True


def _read_rows(collection, key: str, count: int, width: int):
    values = np.empty(count * width, dtype=np.float32)
    if count:
        collection.foreach_get(key, values)
    return values.reshape(count, width) if width > 1 else values


def _loop_vertex_indices(mesh):
    count = len(mesh.loops)
    indices = rna_buffers.empty_u32_for_rna(count)
    corner_verts = getattr(mesh, "corner_verts", None)
    if corner_verts is not None and hasattr(corner_verts, "foreach_get"):
        corner_verts.foreach_get("vertex", indices)
    else:
        mesh.loops.foreach_get("vertex_index", indices)
    return rna_buffers.as_i32(indices)


def _corner_normals(mesh):
    count = len(mesh.loops)
    normals = np.empty(count * 3, dtype=np.float32)
    corner_normals = getattr(mesh, "corner_normals", None)
    if corner_normals is not None and hasattr(corner_normals, "foreach_get") and len(corner_normals) == count:
        corner_normals.foreach_get("vector", normals)
    else:
        mesh.loops.foreach_get("normal", normals)
    return normals.reshape(count, 3)


def _world_points(matrix, points):
    m = np.asarray(matrix, dtype=np.float64)
    return (np.asarray(points, dtype=np.float64) @ m[:3, :3].T + m[:3, 3]).astype(np.float32)


def _world_normals(matrix, normals):
    m = np.asarray(matrix, dtype=np.float64)
    return core.normalize_rows(np.asarray(normals, dtype=np.float64) @ m[:3, :3].T)


# ---------------------------------------------------------------------------
# Layers: create, migrate, write
# ---------------------------------------------------------------------------


def _loop_uvs(mesh, uv_layer_name: str | None, object_name: str):
    from . import export

    try:
        layer = export._resolve_uv_layer_data(mesh, uv_layer_name, object_name=object_name)
    except Exception:
        layer = None
    count = len(mesh.loops)
    uvs = np.zeros(count * 2, dtype=np.float32)
    if layer is not None and hasattr(layer, "foreach_get") and len(layer) == count:
        layer.foreach_get("uv", uvs)
    return uvs.reshape(count, 2)


def _write_layer(mesh, name: str, values) -> bool:
    """Write *values* (one per loop) into the CORNER layer *name*, creating it."""
    layer = paint_sampling.find_paint_layer(mesh, name)
    if layer is not None and str(getattr(layer, "domain", "")).upper() != "CORNER":
        try:
            mesh.attributes.remove(layer)
        except Exception:
            return False
        layer = None
    if layer is None:
        try:
            layer = mesh.attributes.new(name, "FLOAT", "CORNER")
        except Exception:
            return False
    values = np.ascontiguousarray(values, dtype=np.float32)
    if len(layer.data) != values.shape[0]:
        return False
    layer.data.foreach_set("value", values)
    return True


def _mark_paint_only(obj, mesh) -> None:
    now = time.monotonic()
    for datablock in (obj, mesh):
        try:
            _PAINT_ONLY_POINTERS[int(datablock.as_pointer())] = now
        except Exception:
            pass


def ensure_group_layer(context, group) -> list[str]:
    """Give every bakeable low of *group* the paint offset layer, converting a legacy image.

    Creating the layer never changes the bake: a legacy canvas is sampled at every
    corner UV exactly as the exporter samples it (r = v - 1, Offset Scale kept), a group
    without one gets 0. The image is unlinked from the group but kept in the file (it has
    a fake user). Returns notes for the status line.

    Paint Skew needs no preparation: its correction map starts empty (no change), and a
    1.0.x skew image keeps its own meaning next to it.
    """
    notes: list[str] = []
    name = paint_sampling.OFFSET_ATTRIBUTE
    lows = _bakeable_lows(group)
    paint_state = properties.group_paint_projection_settings_state(group)
    already = any(paint_sampling.has_paint_layer(getattr(obj, "data", None), name) for obj in lows)
    image_attr = "paint_offset_image"
    image = getattr(group, image_attr, None) if not already else None
    projection_state = properties.group_projection_settings_state(group)
    uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
    wrote_any = False
    for obj in lows:
        mesh = getattr(obj, "data", None)
        if paint_sampling.has_paint_layer(mesh, name):
            continue
        if not _mesh_writable(mesh):
            notes.append(f"{obj.name} is linked from a library and cannot be painted")
            continue
        loop_count = len(mesh.loops)
        if image is not None:
            sampled = paint_sampling.sample_image_red_channel_numpy(image, _loop_uvs(mesh, uv_layer_name, obj.name))
            values = (np.asarray(sampled, dtype=np.float32) - 1.0) if sampled is not None else np.zeros(loop_count, np.float32)
        else:
            values = np.zeros(loop_count, dtype=np.float32)
        lo, hi = _kind_bounds(KIND_OFFSET)
        if _write_layer(mesh, name, np.clip(values, lo, hi)):
            mesh.update_tag()
            wrote_any = True
    if image is not None and wrote_any:
        setattr(group, image_attr, None)
        try:
            setattr(paint_state, image_attr, None)
        except Exception:
            pass
        notes.append("Converted the painted offset image to mesh paint. The image is kept in the file")
    return notes


def clear_group_layer(group, kind: str) -> int:
    """Remove the painted *kind* values of *group* (offset layer / skew correction maps)."""
    if kind == KIND_SKEW:
        return paint_sampling.clear_skew_correction(group)
    name = paint_sampling.OFFSET_ATTRIBUTE
    changed = 0
    for obj in _bakeable_lows(group):
        mesh = getattr(obj, "data", None)
        layer = paint_sampling.find_paint_layer(mesh, name)
        if layer is None or not _mesh_writable(mesh):
            continue
        try:
            mesh.attributes.remove(layer)
            mesh.update_tag()
            changed += 1
        except Exception:
            pass
    return changed


# ---------------------------------------------------------------------------
# Session build
# ---------------------------------------------------------------------------


def _fitted_auto_cage_triangles(session_names: list[str], low_corner_positions):
    """The overlay's fitted Automatic cage for these lows, when it lines up with them.

    The fit is memoized per geometry (cage.get_or_build_auto_cage_fitted); take the newest
    entry covering exactly these meshes whose triangles sit on the session's own corners.
    """
    order = list(getattr(cage, "_AUTO_CAGE_FIT_ORDER", []) or [])
    fits = getattr(cage, "_AUTO_CAGE_FIT_CACHE", {}) or {}
    names = set(session_names)
    for key in reversed(order):
        triangles = fits.get(key)
        if not triangles or len(triangles) * 3 != len(low_corner_positions):
            continue
        if {triangle.object_name for triangle in triangles} != names:
            continue
        sources = np.asarray(
            [tuple(corner.source_position) for triangle in triangles for corner in triangle.corners], dtype=np.float32
        )
        scale = max(float(np.abs(low_corner_positions).max()), 1.0)
        if not np.allclose(sources, low_corner_positions, atol=1.0e-4 * scale):
            continue
        return triangles
    return None


def _caged_corner_targets(context, group, session: PaintSession, depsgraph):
    """World cage corner per session triangle corner for Custom/Automatic cages, or None.

    Only when the cage's triangles line up one-to-one with the session's, which is what
    the static needle overlay assumes too.
    """
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    tri_count = int(session.tri_loops.shape[0])
    triangles = None
    try:
        if cage_mode == constants.CAGE_MODE_CUSTOM and getattr(group, "custom_cage", None) is not None:
            triangles = cage.capture_object_triangles(group.custom_cage, depsgraph)
        elif cage_mode == constants.CAGE_MODE_AUTOMATIC:
            triangles = _fitted_auto_cage_triangles(
                [entry.name for entry in session.entries], session.loop_positions[session.tri_loops.reshape(-1)]
            )
    except Exception:
        triangles = None
    if not triangles or len(triangles) != tri_count:
        return None
    return np.asarray(
        [tuple(corner.position) for triangle in triangles for corner in triangle.corners], dtype=np.float32
    )


def _session_cage_targets(context, session: PaintSession, depsgraph):
    """Cage corner per session triangle corner across every painted group, or None."""
    from types import SimpleNamespace

    parts = []
    for group in _session_groups(context, session):
        name = str(getattr(group, "name", "") or "")
        t0, t1 = session.group_tri_ranges.get(name, (0, int(session.tri_loops.shape[0])))
        if t1 <= t0:
            continue
        view = SimpleNamespace(
            tri_loops=session.tri_loops[t0:t1],
            loop_positions=session.loop_positions,
            entries=[entry for entry in session.entries if entry.group_name in ("", name)],
        )
        targets = _caged_corner_targets(context, group, view, depsgraph)
        if targets is None:
            return None
        parts.append(targets)
    if not parts:
        return None
    targets = np.concatenate(parts)
    return targets if targets.shape[0] == session.tri_loops.shape[0] * 3 else None


def _refresh_cage_targets(context, session: PaintSession) -> None:
    """Pick up an Automatic cage fit that finished after the session opened."""
    if session.cage_targets is not None or session.cage_mode != constants.CAGE_MODE_AUTOMATIC:
        return
    now = time.monotonic()
    if now - session.last_cage_lookup < 0.5:
        return
    session.last_cage_lookup = now
    group = _session_group(context, session)
    if group is None:
        return
    targets = _session_cage_targets(context, session, None)
    if targets is not None:
        session.cage_targets = targets
        _prepare_needles(session)
        session.display_dirty = True


def build_session(context, project, group, kind: str, groups=None) -> PaintSession | None:
    """Gather the session's lows: every bakeable low of *groups* (default: *group* alone,
    the anchor). Each group keeps its own offset, Offset Scale and corner welding."""
    depsgraph = context.evaluated_depsgraph_get()
    groups = list(groups or [group])
    name = paint_sampling.OFFSET_ATTRIBUTE
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    smooth_cage = bool(getattr(group, "average_normals", True))

    entries: list[_ObjectEntry] = []
    loop_values = []
    loop_positions = []
    loop_normals = []
    tri_loops = []
    edge_loops = []
    loop_entry = []
    base_distance = []
    offset_scales = []
    loop_uvs = []
    legacy_skews = []
    group_names: list[str] = []
    group_tri_ranges: dict[str, tuple[int, int]] = {}
    group_loop_ranges: list[tuple[int, int]] = []
    seen_objects: set[str] = set()
    loop_start = 0
    tri_start = 0
    for paint_group in groups:
        group_name = str(getattr(paint_group, "name", "") or "")
        lows = [obj for obj in _bakeable_lows(paint_group) if obj.name not in seen_objects]
        paint_state = properties.group_paint_projection_settings_state(paint_group)
        offset_scale = float(getattr(paint_state, "paint_offset_scale", 1.0) or 0.0)
        group_offset = max(0.0, float(getattr(paint_group, "cage_offset", 0.0) or 0.0))
        projection_state = properties.group_projection_settings_state(paint_group)
        uv_layer_name = (getattr(projection_state, "uv_layer_name", "") or "").strip() or None
        legacy_skew_image = getattr(paint_state, "paint_skew_image", None)
        skew_amount = float(getattr(paint_state, "paint_skew", 0.0) or 0.0)
        group_loop_start = loop_start
        group_tri_start = tri_start
        for obj in lows:
            mesh = getattr(obj, "data", None)
            if mesh is None or not _mesh_writable(mesh):
                continue
            mesh.calc_loop_triangles()
            vertex_count = len(mesh.vertices)
            loop_count = len(mesh.loops)
            if loop_count == 0 or len(mesh.loop_triangles) == 0:
                continue
            loop_vertex = _loop_vertex_indices(mesh)
            positions = _read_rows(mesh.vertices, "co", vertex_count, 3)
            normals = _corner_normals(mesh)
            bridged = None
            obj_eval = obj.evaluated_get(depsgraph)
            eval_mesh = None
            try:
                eval_mesh = obj_eval.to_mesh()
            except Exception:
                eval_mesh = None
            try:
                # Deform-only stacks (Armature, Shrinkwrap, Weighted Normal...) keep the
                # topology, so the brush lands on the surface the artist sees; a generating
                # stack (Mirror, Subdivision) is painted on its base mesh and propagates.
                if eval_mesh is not None and len(eval_mesh.vertices) == vertex_count:
                    positions = _read_rows(eval_mesh.vertices, "co", vertex_count, 3)
                if eval_mesh is not None and len(eval_mesh.loops) == loop_count:
                    normals = _corner_normals(eval_mesh)
                    if not smooth_cage:
                        bridged = cage._try_build_convex_bridged_corner_normals_numpy(eval_mesh)
                elif not smooth_cage:
                    bridged = cage._try_build_convex_bridged_corner_normals_numpy(mesh)
            finally:
                if eval_mesh is not None:
                    try:
                        obj_eval.to_mesh_clear()
                    except Exception:
                        pass
            if bridged is not None and np.asarray(bridged).shape == (loop_count, 3):
                normals = np.asarray(bridged, dtype=np.float32)
            matrix = obj.matrix_world.copy()
            world_positions = _world_points(matrix, positions[loop_vertex])
            world_normals = _world_normals(matrix, normals)
            tris = _read_rows(mesh.loop_triangles, "loops", len(mesh.loop_triangles), 3).astype(np.int64)
            poly_starts = _read_rows(mesh.polygons, "loop_start", len(mesh.polygons), 1).astype(np.int64)
            poly_totals = _read_rows(mesh.polygons, "loop_total", len(mesh.polygons), 1).astype(np.int64)
            firsts = np.repeat(poly_starts, poly_totals)
            local = np.arange(loop_count, dtype=np.int64)
            nexts = np.where(local + 1 < firsts + np.repeat(poly_totals, poly_totals), local + 1, firsts)
            values = paint_sampling.read_loop_values(mesh, name, loop_vertex) if kind == KIND_OFFSET else None
            if values is None or values.shape[0] != loop_count:
                values = np.zeros(loop_count, dtype=np.float32)
            if kind == KIND_SKEW:
                uvs = _loop_uvs(mesh, uv_layer_name, obj.name)
                loop_uvs.append(uvs)
                # The 1.0.x per-vertex skew (legacy image x Skew Amount, else the amount alone)
                # still shapes the base ray the correction bends, exactly as exported.
                _offsets, corner_skews = paint_sampling.corner_paint_values(
                    mesh,
                    np.arange(loop_count, dtype=np.int64),
                    uvs,
                    skew_image=legacy_skew_image,
                    skew_amount=skew_amount,
                )
                legacy_skews.append(np.clip(corner_skews, 0.0, 1.0).astype(np.float32))
            try:
                from mathutils.bvhtree import BVHTree

                bvh = BVHTree.FromObject(obj, depsgraph)
            except Exception:
                bvh = None
            delta = _slot_offset_delta(paint_group, obj)
            seen_objects.add(obj.name)
            entries.append(
                _ObjectEntry(
                    name=obj.name,
                    mesh_name=mesh.name,
                    loop_start=loop_start,
                    loop_count=loop_count,
                    matrix_world=matrix,
                    matrix_inverse=matrix.inverted_safe(),
                    bvh=bvh,
                    slot_offset_delta=delta,
                    group_name=group_name,
                )
            )
            loop_values.append(np.asarray(values, dtype=np.float32))
            loop_positions.append(world_positions)
            loop_normals.append(world_normals)
            tri_loops.append(tris + loop_start)
            edge_loops.append(np.stack([local, nexts], axis=1) + loop_start)
            loop_entry.append(np.full(loop_count, len(entries) - 1, dtype=np.int32))
            base_distance.append(np.full(loop_count, max(0.0, group_offset + delta) * offset_scale, dtype=np.float32))
            offset_scales.append(np.full(loop_count, offset_scale, dtype=np.float32))
            loop_start += loop_count
            tri_start += int(tris.shape[0])
        if loop_start > group_loop_start:
            group_names.append(group_name)
            group_loop_ranges.append((group_loop_start, loop_start))
            group_tri_ranges[group_name] = (group_tri_start, tri_start)
    if not entries:
        return None

    loop_positions = np.concatenate(loop_positions)
    lo = loop_positions.min(axis=0)
    hi = loop_positions.max(axis=0)
    diagonal = float(np.linalg.norm(hi - lo))
    # Welded per group: two groups' lows that touch keep their own normals and paint,
    # as the bake treats them.
    weld_tolerance = max(diagonal * 1.0e-6, 1.0e-7)
    loop_point_parts = []
    point_position_parts = []
    point_base = 0
    for range_start, range_end in group_loop_ranges:
        group_points, group_positions = core.weld_corners(loop_positions[range_start:range_end], weld_tolerance)
        loop_point_parts.append(group_points.astype(np.int32) + np.int32(point_base))
        point_position_parts.append(group_positions)
        point_base += int(group_positions.shape[0])
    loop_point = np.concatenate(loop_point_parts).astype(np.int32)
    point_positions = np.concatenate(point_position_parts)
    point_count = int(point_positions.shape[0])
    loop_normals = np.concatenate(loop_normals)
    point_normals = np.zeros((point_count, 3), dtype=np.float64)
    for axis in range(3):
        point_normals[:, axis] = np.bincount(loop_point, weights=loop_normals[:, axis], minlength=point_count)
    point_normals = core.normalize_rows(point_normals)
    tri_loops = np.concatenate(tri_loops)
    indptr, indices = core.point_adjacency(loop_point[tri_loops], point_count)
    labels = core.connected_components(point_count, indptr, indices)
    order = np.argsort(loop_point, kind="stable")
    point_loop_indptr = np.zeros(point_count + 1, dtype=np.int64)
    np.cumsum(np.bincount(loop_point, minlength=point_count), out=point_loop_indptr[1:])
    all_values = np.concatenate(loop_values)

    session = PaintSession(
        kind=kind,
        project_name=str(getattr(project, "name", "") or ""),
        group_name=str(getattr(group, "name", "") or ""),
        entries=entries,
        loop_values=all_values,
        loop_positions=loop_positions,
        loop_normals=loop_normals,
        loop_entry=np.concatenate(loop_entry),
        loop_point=loop_point,
        point_positions=point_positions,
        point_normals=point_normals,
        point_values=core.point_values_from_corners(all_values, loop_point, point_count),
        point_loop_indptr=point_loop_indptr,
        point_loops=order.astype(np.int64),
        adjacency_indptr=indptr,
        adjacency_indices=indices,
        labels=labels,
        tri_loops=tri_loops,
        poly_edge_loops=np.concatenate(edge_loops),
        bounds_diagonal=diagonal,
        cage_mode=cage_mode,
        smooth_cage=smooth_cage,
        base_distance_per_loop=np.concatenate(base_distance),
        cage_targets=None,
        group_names=tuple(group_names),
        group_tri_ranges=group_tri_ranges,
        loop_offset_scale=np.concatenate(offset_scales),
    )
    if kind == KIND_SKEW:
        session.loop_uvs = np.concatenate(loop_uvs).astype(np.float32)
        session.legacy_loop_skews = np.concatenate(legacy_skews)
    if cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC):
        session.cage_targets = _session_cage_targets(context, session, depsgraph)
    _prepare_needles(session)
    if kind == KIND_SKEW:
        _build_skew_tiles(session, group)
    return session


def _build_skew_tiles(session: PaintSession, group) -> None:
    """Rasterize the lows into every UDIM tile their UVs touch: which texel sits where on
    the surface, the stored map (or an empty one), and the padding sources."""
    stored = paint_sampling.skew_correction_tiles(group, include_empty=True)
    tri_uvs = session.loop_uvs[session.tri_loops]  # [T, 3, 2] global
    centroids = tri_uvs.mean(axis=1)
    tri_tiles = 1001 + np.floor(centroids[:, 0]).astype(np.int64) + 10 * np.floor(centroids[:, 1]).astype(np.int64)
    tiles: list[_SkewTile] = []
    texel_tile, texel_flat, texel_tri, texel_pos, texel_values = [], [], [], [], []
    for tile_id in sorted(set(tri_tiles.tolist())):
        tris = np.flatnonzero(tri_tiles == tile_id)
        offset = np.array([(tile_id - 1001) % 10, (tile_id - 1001) // 10], dtype=np.float32)
        if tile_id in stored:
            width, height, values = stored[tile_id]
            grid = np.asarray(values, dtype=np.float32).reshape(-1).copy()
        else:
            width = height = paint_sampling.SKEW_CORRECTION_DEFAULT_SIZE
            grid = np.zeros(width * height, dtype=np.float32)
        flat, local_tri, bary = core.rasterize_uv_triangles(tri_uvs[tris] - offset, width, height)
        covered = np.zeros(width * height, dtype=bool)
        covered[flat] = True
        covered = covered.reshape(height, width)
        destinations, sources = core.dilation_sources(covered, _SKEW_DILATION_TEXELS)
        tri_index = tris[local_tri]
        positions = np.einsum("kj,kjc->kc", bary, session.tri_positions[tri_index]).astype(np.float32)
        tiles.append(
            _SkewTile(
                tile=int(tile_id),
                width=int(width),
                height=int(height),
                grid=grid,
                covered=covered,
                pad_destinations=destinations,
                pad_sources=sources,
            )
        )
        texel_tile.append(np.full(flat.size, len(tiles) - 1, dtype=np.int64))
        texel_flat.append(flat)
        texel_tri.append(tri_index)
        texel_pos.append(positions)
        texel_values.append(grid[flat])
    session.tiles = tiles
    if tiles:
        session.texel_tile = np.concatenate(texel_tile)
        session.texel_flat = np.concatenate(texel_flat)
        session.texel_tri = np.concatenate(texel_tri)
        session.texel_positions = np.concatenate(texel_pos)
        session.texel_values = np.concatenate(texel_values).astype(np.float32)


def _prepare_needles(session: PaintSession) -> None:
    corners = session.loop_positions[session.tri_loops]  # [T, 3, 3]
    session.tri_positions = np.ascontiguousarray(corners, dtype=np.float32)
    session.tri_bounds = core.triangle_bounds(session.tri_positions)
    edges = np.stack(
        [corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 1], corners[:, 0] - corners[:, 2]], axis=1
    )
    cross = np.cross(edges[:, 0], -edges[:, 2])
    areas = 0.5 * np.linalg.norm(cross, axis=1)
    session.tri_face_normals = core.normalize_rows(cross)
    if session.kind != KIND_SKEW:
        return
    resolutions = cage._skew_triangle_resolutions(
        areas.tolist(),
        constants.VIEWPORT_SKEW_SEGMENT_BUDGET,
        constants.VIEWPORT_SKEW_MAX_TRIANGLE_RESOLUTION,
    )
    session.needle_tris, session.needle_weights = core.triangle_needle_samples(resolutions, cage._skew_grid_samples)
    average_edge = np.linalg.norm(edges, axis=2).mean(axis=1)
    # Same floor as the static needles (cage._skew_needle_minimum_length at unit scale),
    # per low mesh.
    floors = np.zeros(len(session.entries), dtype=np.float32)
    for index, entry in enumerate(session.entries):
        positions = session.loop_positions[entry.loop_start : entry.loop_start + entry.loop_count]
        floors[index] = cage._SKEW_NEEDLE_BOUNDS_FLOOR * float(np.linalg.norm(positions.max(axis=0) - positions.min(axis=0)))
    tri_entry = session.loop_entry[session.tri_loops[:, 0]]
    lengths = np.maximum(average_edge, floors[tri_entry])
    session.needle_lengths = lengths[session.needle_tris].astype(np.float32)
    # Constant for the session: only the directions move while painting.
    session.needle_loops = session.tri_loops[session.needle_tris]
    session.needle_starts = _interpolate(session.loop_positions, session.needle_loops, session.needle_weights)
    session.needle_uvs = _interpolate(session.loop_uvs, session.needle_loops, session.needle_weights)
    if session.cage_targets is not None:
        corner_index = session.needle_tris[:, None] * 3 + np.arange(3)[None, :]
        session.needle_cage_points = _interpolate(session.cage_targets, corner_index, session.needle_weights)


def _interpolate(values, indices, weights):
    """Barycentric interpolation of per-corner *values* [N, C] at [K, 3] *indices*."""
    return np.einsum("kj,kjc->kc", weights, values[indices], dtype=np.float32, casting="unsafe").astype(np.float32)


def reload_values(context) -> bool:
    """Re-read the session's values (after undo/redo). False = the session ended."""
    session = _SESSION
    if session is None:
        return False
    if session.kind == KIND_SKEW:
        group = _session_group(context, session)
        if group is None:
            end_session(context, restore_tool=True, reason="the bake group is gone")
            return False
        stored = paint_sampling.skew_correction_tiles(group, include_empty=True)
        for tile in session.tiles:
            entry = stored.get(tile.tile)
            if entry is not None and entry[0] == tile.width and entry[1] == tile.height:
                tile.grid[:] = np.asarray(entry[2], dtype=np.float32).reshape(-1)
            else:
                tile.grid[:] = 0.0
        for index, tile in enumerate(session.tiles):
            mask = session.texel_tile == index
            session.texel_values[mask] = tile.grid[session.texel_flat[mask]]
        session.display_dirty = True
        _tag_redraw(context)
        return True
    for entry in session.entries:
        obj = bpy.data.objects.get(entry.name)
        mesh = getattr(obj, "data", None) if obj is not None else None
        if mesh is None or len(getattr(mesh, "loops", ())) != entry.loop_count:
            end_session(context, restore_tool=True, reason="the painted meshes changed")
            return False
        values = paint_sampling.read_loop_values(mesh, paint_sampling.OFFSET_ATTRIBUTE)
        if values is None or values.shape[0] != entry.loop_count:
            values = np.zeros(entry.loop_count, dtype=np.float32)
        session.loop_values[entry.loop_start : entry.loop_start + entry.loop_count] = values
    session.point_values = core.point_values_from_corners(
        session.loop_values, session.loop_point, session.point_positions.shape[0]
    )
    session.display_dirty = True
    _tag_redraw(context)
    return True


# ---------------------------------------------------------------------------
# Enter / exit
# ---------------------------------------------------------------------------


def _active_tool_id(context) -> str:
    workspace = getattr(context, "workspace", None)
    if workspace is None:
        # Timers run without a window in context; use the one holding a 3D Viewport.
        window, _area, _region = _view3d_override(context)
        workspace = getattr(window, "workspace", None)
    tools = getattr(workspace, "tools", None)
    if tools is None:
        return ""
    try:
        tool = tools.from_space_view3d_mode("OBJECT", create=False)
    except Exception:
        return ""
    return str(getattr(tool, "idname", "") or "")


def _view3d_override(context):
    """(window, area, region) of a 3D Viewport, preferring the current one."""
    area = getattr(context, "area", None)
    window = getattr(context, "window", None)
    if area is not None and area.type == "VIEW_3D" and window is not None:
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is not None:
            return window, area, region
    windows = list(getattr(getattr(context, "window_manager", None), "windows", None) or ())
    if window is not None:
        windows.insert(0, window)
    for candidate in windows:
        for candidate_area in getattr(getattr(candidate, "screen", None), "areas", None) or ():
            if candidate_area.type != "VIEW_3D":
                continue
            region = next((r for r in candidate_area.regions if r.type == "WINDOW"), None)
            if region is not None:
                return candidate, candidate_area, region
    return None, None, None


def _set_tool(context, idname: str) -> bool:
    window, area, region = _view3d_override(context)
    if area is None:
        return False
    try:
        with context.temp_override(window=window, area=area, region=region):
            bpy.ops.wm.tool_set_by_id(name=idname, space_type="VIEW_3D")
        return True
    except Exception:
        traceback.print_exc()
        return False


def _ensure_object_mode(context) -> bool:
    active = getattr(getattr(context, "view_layer", None), "objects", None)
    active = getattr(active, "active", None)
    if active is None or getattr(active, "mode", "OBJECT") == "OBJECT":
        return True
    window, area, region = _view3d_override(context)
    try:
        if area is not None:
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.object.mode_set(mode="OBJECT")
        else:
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        return False
    return getattr(active, "mode", "OBJECT") == "OBJECT"


def start_session(context, project, group, kind: str) -> tuple[bool, str]:
    """Open a paint session on *group*. Returns (ok, message)."""
    global _SESSION
    if _SESSION is not None:
        end_session(context, restore_tool=False, reason="")
    if not _ensure_object_mode(context):
        return False, "Leave the current mode first"
    if not _bakeable_lows(group):
        return False, "This bake group needs a low mesh with a UV map"
    _seed_offset_colors(context)
    groups, notes = scope_paint_groups(context, project, group, kind)
    try:
        if kind == KIND_OFFSET:
            for paint_group in groups:
                notes.extend(ensure_group_layer(context, paint_group))
    except Exception as exc:
        traceback.print_exc()
        return False, f"Could not prepare the paint layer: {exc}"
    try:
        session = build_session(context, project, group, kind, groups=groups)
    except Exception as exc:
        traceback.print_exc()
        return False, f"Could not start painting: {exc}"
    if session is None:
        return False, "No low mesh in this bake group can be painted"
    session.notes = notes
    scene = context.scene
    previous = _active_tool_id(context)
    if previous not in TOOL_IDS.values() and not scene.get(PREVIOUS_TOOL_KEY):
        scene[PREVIOUS_TOOL_KEY] = previous or "builtin.select_box"
    _SESSION = session
    _ensure_draw_handlers()
    if not _set_tool(context, TOOL_IDS[kind]):
        _SESSION = None
        return False, "Could not activate the paint tool. Open a 3D Viewport"
    _invalidate_static_overlay()
    _tag_redraw(context)
    what = "offset" if kind == KIND_OFFSET else "skew"
    names = ", ".join(entry.name for entry in session.entries)
    message = f"Painting {what} on {names}"
    if notes:
        message = f"{message}. {notes[-1]}"
    return True, message


def end_session(context, *, restore_tool: bool = True, keep_previous_tool: bool = False, reason: str = "") -> None:
    """Close the session (strokes already committed on release) and restore the tool.

    *keep_previous_tool* leaves the recorded pre-session tool in place for a session the
    paint tool will reopen (it stayed active in Object Mode).
    """
    global _SESSION
    session = _SESSION
    _SESSION = None
    if session is None:
        return
    scene = getattr(context, "scene", None)
    if restore_tool and scene is not None:
        previous = str(scene.get(PREVIOUS_TOOL_KEY) or "")
        if _active_tool_id(context) in TOOL_IDS.values():
            _set_tool(context, previous or "builtin.select_box")
    if scene is not None and PREVIOUS_TOOL_KEY in scene and not keep_previous_tool:
        try:
            del scene[PREVIOUS_TOOL_KEY]
        except Exception:
            pass
    _stamp_painted_meshes(session)
    _invalidate_static_overlay()
    _tag_redraw(context)


def _stamp_painted_meshes(session: PaintSession) -> None:
    """Give the painted meshes the overlay revision their stroke updates skipped
    (overlay_events.paint_only_update), so the static rebuild sees the new values."""
    try:
        from .overlay_keys import bump_id_revision
    except Exception:
        return
    for entry in session.entries:
        obj = bpy.data.objects.get(entry.name)
        if obj is None:
            continue
        bump_id_revision(obj)
        bump_id_revision(getattr(obj, "data", None))


def _invalidate_static_overlay() -> None:
    try:
        from . import overlays

        overlays.invalidate_overlay_cache(clear_static=True)
    except Exception:
        pass


def _tag_redraw(context=None) -> None:
    context = context or bpy.context
    for window in getattr(getattr(context, "window_manager", None), "windows", None) or ():
        for area in getattr(getattr(window, "screen", None), "areas", None) or ():
            if area.type == "VIEW_3D":
                area.tag_redraw()


def session_exit_reason(context) -> str | None:
    """Why the live session should end ('tool', 'mode', 'group'), or None to keep it."""
    session = _SESSION
    if session is None:
        return None
    if _active_tool_id(context) != TOOL_IDS.get(session.kind):
        return "tool"
    active = getattr(getattr(context, "view_layer", None), "objects", None)
    active = getattr(active, "active", None)
    if active is not None and getattr(active, "mode", "OBJECT") != "OBJECT":
        return "mode"
    _project, group = _resolve_project_group(context)
    if group is None or str(getattr(group, "name", "") or "") not in _group_names_of(session):
        return "group"
    return None


_EXIT_CHECK_PENDING = False


def _deferred_exit_check():
    """Timer: end a session the artist left another way (never from a draw callback)."""
    global _EXIT_CHECK_PENDING
    _EXIT_CHECK_PENDING = False
    context = bpy.context
    reason = session_exit_reason(context)
    if reason is not None:
        new_kind = _paint_tool_kind(_active_tool_id(context)) if reason == "tool" else None
        # Picking another tool is the artist's choice. Leaving Object Mode leaves the
        # toolbars alone too (tool_set_by_id would act on the new mode's toolbar); the
        # paint tool stays in Object Mode and its next stroke reopens the session.
        # Switching the bake group puts the previous tool back.
        end_session(
            context,
            restore_tool=reason == "group",
            keep_previous_tool=reason == "mode" or new_kind is not None,
        )
        if new_kind is not None:
            # Offset -> Skew (or back) from the toolbar: open the other session now. Waiting
            # for the first stroke left the sidebar on the pre-session panel in between.
            _open_session_for_tool(context, new_kind)
    return None


def _paint_tool_kind(tool_id: str):
    return next((kind for kind, idname in TOOL_IDS.items() if idname == tool_id), None)


#: (tool id, project, group) a tool-driven session last failed to open for, so a group that
#: cannot be painted is not retried on every header redraw.
_TOOL_SYNC_FAILED: tuple = ()
_TOOL_SYNC_PENDING = False


def _open_session_for_tool(context, kind: str) -> bool:
    global _TOOL_SYNC_FAILED
    project, group = _resolve_project_group(context)
    key = (TOOL_IDS.get(kind), getattr(project, "name", None), getattr(group, "name", None))
    if project is None or group is None or key == _TOOL_SYNC_FAILED:
        return False
    ok, message = start_session(context, project, group, kind)
    _TOOL_SYNC_FAILED = () if ok else key
    if not ok and message:
        print(f"[Fyr Baker] {message}")
    return ok


def _deferred_tool_sync():
    """Timer: the paint tool is active without its session (picked from the toolbar):
    open it, so the brush panel and live display are there before the first stroke."""
    global _TOOL_SYNC_PENDING
    _TOOL_SYNC_PENDING = False
    context = bpy.context
    kind = _paint_tool_kind(_active_tool_id(context))
    if kind is None or (_SESSION is not None and _SESSION.kind == kind):
        return None
    if _SESSION is not None:
        end_session(context, restore_tool=False, keep_previous_tool=True)
    _open_session_for_tool(context, kind)
    return None


def _schedule_tool_sync() -> None:
    global _TOOL_SYNC_PENDING
    if _TOOL_SYNC_PENDING:
        return
    _TOOL_SYNC_PENDING = True
    try:
        bpy.app.timers.register(_deferred_tool_sync, first_interval=0.0)
    except Exception:
        _TOOL_SYNC_PENDING = False


def _schedule_exit_check() -> None:
    global _EXIT_CHECK_PENDING
    if _EXIT_CHECK_PENDING:
        return
    _EXIT_CHECK_PENDING = True
    try:
        bpy.app.timers.register(_deferred_exit_check, first_interval=0.0)
    except Exception:
        _EXIT_CHECK_PENDING = False


# ---------------------------------------------------------------------------
# Brush
# ---------------------------------------------------------------------------


def _mouse_ray(region, rv3d, coord):
    from bpy_extras import view3d_utils

    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    return origin, direction


def _raycast(session: PaintSession, origin: Vector, direction: Vector):
    """Nearest hit over every painted mesh: (location, normal) in world space, or None."""
    best = None
    best_distance = float("inf")
    for entry in session.entries:
        if entry.bvh is None:
            continue
        local_origin = entry.matrix_inverse @ origin
        local_target = entry.matrix_inverse @ (origin + direction)
        local_direction = (local_target - local_origin).normalized()
        location, normal, _index, _distance = entry.bvh.ray_cast(local_origin, local_direction)
        if location is None:
            continue
        world_location = entry.matrix_world @ location
        distance = (world_location - origin).length
        if distance < best_distance:
            best_distance = distance
            world_normal = (entry.matrix_world.to_3x3() @ normal).normalized()
            best = (world_location, world_normal)
    return best


def _world_radius(region, rv3d, coord, location: Vector, radius_px: float) -> float:
    from bpy_extras import view3d_utils

    shifted = view3d_utils.region_2d_to_location_3d(region, rv3d, (coord[0] + radius_px, coord[1]), location)
    return float((shifted - location).length)


def _visible_points(session: PaintSession, points, eye: Vector, is_perspective: bool, view_direction: Vector):
    """Keep the points no painted surface hides from the viewer."""
    if points.size == 0:
        return points
    keep = np.ones(points.size, dtype=bool)
    positions = session.point_positions[points]
    normals = session.point_normals[points]
    epsilon = max(session.bounds_diagonal * 1.0e-4, 1.0e-6)
    for index in range(points.size):
        start = Vector(positions[index]) + Vector(normals[index]) * epsilon
        if is_perspective:
            to_eye = eye - start
            distance = to_eye.length
            if distance <= 1.0e-9:
                continue
            direction = to_eye / distance
        else:
            direction = -view_direction
            distance = session.bounds_diagonal * 4.0 + 1.0
        for entry in session.entries:
            if entry.bvh is None:
                continue
            local_start = entry.matrix_inverse @ start
            local_end = entry.matrix_inverse @ (start + direction * distance)
            local_vector = local_end - local_start
            local_distance = local_vector.length
            if local_distance <= 1.0e-12:
                continue
            hit, _n, _i, _d = entry.bvh.ray_cast(local_start, local_vector / local_distance, local_distance)
            if hit is not None:
                keep[index] = False
                break
    return points[keep]


def _set_value_from_settings(kind: str, brush) -> float:
    if kind == KIND_OFFSET:
        return float(getattr(brush, "offset_target", 0.0)) / 100.0
    return float(getattr(brush, "skew_target", 1.0))


def apply_dab(context, region, rv3d, coord, mode: str, pressure: float = 1.0) -> bool:
    """One dab at screen *coord*. Returns True when values changed."""
    session = _SESSION
    brush = brush_settings(context)
    if session is None or brush is None:
        return False
    origin, direction = _mouse_ray(region, rv3d, coord)
    hit = _raycast(session, origin, direction)
    if hit is None:
        session.cursor = None
        return False
    location, normal = hit
    radius_px = float(brush.radius) * (pressure if brush.use_pressure_radius else 1.0)
    radius = _world_radius(region, rv3d, coord, location, max(radius_px, 1.0))
    session.cursor = (location, normal, radius, tuple(coord))
    tri_index, bary = core.containing_triangle(
        session.tri_positions, location, max(session.bounds_diagonal * 1.0e-3, 1.0e-6), bounds=session.tri_bounds
    )
    view_matrix = rv3d.view_matrix
    view_inverse = view_matrix.inverted_safe()
    eye = view_inverse.translation.copy()
    view_direction = (view_inverse.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    is_perspective = bool(rv3d.is_perspective)
    strength = float(brush.strength) * (pressure if brush.use_pressure_strength else 1.0)
    if session.kind == KIND_SKEW:
        return _apply_skew_dab(
            session, brush, mode, strength, location, radius, tri_index, eye, is_perspective, view_direction
        )
    points, distances = core.points_in_sphere(session.point_positions, location, radius)
    keep = np.ones(points.size, dtype=bool)
    if brush.use_front_faces_only:
        keep &= core.facing_mask(
            session.point_positions[points], session.point_normals[points], tuple(eye), is_perspective, tuple(view_direction)
        )
    if brush.use_connected_only and points.size:
        if tri_index >= 0:
            anchor = int(session.loop_point[session.tri_loops[tri_index, 0]])
        else:
            anchor = int(points[int(np.argmin(distances))])
        keep &= session.labels[points] == session.labels[anchor]
    points = points[keep]
    distances = distances[keep]
    if points.size and brush.use_visible_only:
        visible = _visible_points(session, points, eye, is_perspective, view_direction)
        mask = np.isin(points, visible)
        points = points[mask]
        distances = distances[mask]
    weights = core.falloff_weights(distances, brush.falloff, brush.hardness)
    # Values live at the corners. On a low whose faces are larger than the brush no
    # corner may be inside it, so the corners of the face under the cursor always take
    # part, weighted by where on the face the cursor is.
    if tri_index >= 0:
        points, weights = core.merge_face_corners(
            points, weights, session.loop_point[session.tri_loops[tri_index]], bary
        )
    if points.size == 0:
        return False
    lo, hi = _kind_bounds(session.kind)
    # Dabs are laid this far apart (MASTER_BAKER_OT_paint_brush_stroke.modal); scaling each
    # by it makes one full-strength pass add +100% of the cage offset at any Spacing.
    spacing_px = max(1.0, float(brush.radius) * float(brush.spacing) / 100.0)
    updated = core.apply_dab(
        session.point_values,
        points,
        weights,
        mode,
        strength,
        lower=lo,
        upper=hi,
        target=_set_value_from_settings(session.kind, brush),
        indptr=session.adjacency_indptr,
        indices=session.adjacency_indices,
        rate=core.pass_normalized_rate(spacing_px, max(radius_px, 1.0)),
    )
    changed = np.abs(updated - session.point_values[points]) > 0.0
    if not changed.any():
        return False
    points = points[changed]
    updated = updated[changed]
    session.point_values[points] = updated
    starts = session.point_loop_indptr[points]
    counts = session.point_loop_indptr[points + 1] - starts
    flat = np.repeat(starts, counts) + (np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts))
    loops = session.point_loops[flat]
    session.loop_values[loops] = np.repeat(updated, counts)
    session.dirty_entries.update(np.unique(session.loop_entry[loops]).tolist())
    session.display_dirty = True
    return True


def _visible_triangles(session: PaintSession, tris, eye: Vector, is_perspective: bool, view_direction: Vector):
    """The triangles (by centroid) no painted surface hides from the viewer."""
    tris = np.asarray(tris, dtype=np.int64)
    if tris.size == 0:
        return tris
    centroids = session.tri_positions[tris].mean(axis=1)
    normals = session.tri_face_normals[tris]
    epsilon = max(session.bounds_diagonal * 1.0e-4, 1.0e-6)
    keep = np.ones(tris.size, dtype=bool)
    for index in range(tris.size):
        start = Vector(centroids[index]) + Vector(normals[index]) * epsilon
        if is_perspective:
            to_eye = eye - start
            distance = to_eye.length
            if distance <= 1.0e-9:
                continue
            direction = to_eye / distance
        else:
            direction = -view_direction
            distance = session.bounds_diagonal * 4.0 + 1.0
        for entry in session.entries:
            if entry.bvh is None:
                continue
            local_start = entry.matrix_inverse @ start
            local_end = entry.matrix_inverse @ (start + direction * distance)
            local_vector = local_end - local_start
            local_distance = local_vector.length
            if local_distance <= 1.0e-12:
                continue
            hit, _n, _i, _d = entry.bvh.ray_cast(local_start, local_vector / local_distance, local_distance)
            if hit is not None:
                keep[index] = False
                break
    return tris[keep]


def _apply_skew_dab(session, brush, mode, strength, location, radius, tri_index, eye, is_perspective, view_direction) -> bool:
    """One dab on the skew correction map: every covered texel whose surface point is
    inside the brush sphere."""
    if session.texel_positions.shape[0] == 0:
        return False
    texels, distances = core.points_in_sphere(session.texel_positions, location, radius)
    if texels.size == 0:
        return False
    tris = session.texel_tri[texels]
    keep = np.ones(texels.size, dtype=bool)
    if brush.use_front_faces_only:
        keep &= core.facing_mask(
            session.texel_positions[texels], session.tri_face_normals[tris], tuple(eye), is_perspective, tuple(view_direction)
        )
    if brush.use_connected_only:
        anchor_tri = tri_index if tri_index >= 0 else int(tris[int(np.argmin(distances))])
        tri_labels = session.labels[session.loop_point[session.tri_loops[:, 0]]]
        keep &= tri_labels[tris] == tri_labels[anchor_tri]
    texels = texels[keep]
    distances = distances[keep]
    tris = tris[keep]
    if texels.size and brush.use_visible_only:
        unique_tris = np.unique(tris)
        visible = _visible_triangles(session, unique_tris, eye, is_perspective, view_direction)
        mask = np.isin(tris, visible)
        texels = texels[mask]
        distances = distances[mask]
    if texels.size == 0:
        return False
    weights = core.falloff_weights(distances, brush.falloff, brush.hardness)
    current = session.texel_values[texels]
    if mode == core.MODE_SMOOTH:
        updated = current.copy()
        w = np.clip(weights * np.float32(strength), 0.0, 1.0)
        for tile_index in np.unique(session.texel_tile[texels]).tolist():
            sel = session.texel_tile[texels] == tile_index
            tile = session.tiles[tile_index]
            means = core.masked_neighbour_means(
                tile.grid.reshape(tile.height, tile.width), tile.covered, session.texel_flat[texels[sel]]
            )
            updated[sel] = current[sel] + w[sel] * (means - current[sel])
        updated = np.clip(updated, 0.0, 1.0).astype(np.float32)
    else:
        updated = core.apply_dab(
            session.texel_values,
            texels,
            weights,
            mode,
            strength,
            lower=0.0,
            upper=1.0,
            target=_set_value_from_settings(KIND_SKEW, brush),
        )
    changed = np.abs(updated - current) > 0.0
    if not changed.any():
        return False
    texels = texels[changed]
    updated = updated[changed]
    session.texel_values[texels] = updated
    for tile_index in np.unique(session.texel_tile[texels]).tolist():
        sel = session.texel_tile[texels] == tile_index
        session.tiles[tile_index].grid[session.texel_flat[texels[sel]]] = updated[sel]
        session.dirty_tiles.add(int(tile_index))
    session.display_dirty = True
    return True


def _commit_skew(context, session: PaintSession) -> int:
    if not session.dirty_tiles:
        return 0
    group = _session_group(context, session)
    if group is None:
        return 0
    written = 0
    for tile_index in sorted(session.dirty_tiles):
        tile = session.tiles[tile_index]
        if tile.pad_destinations.size:
            tile.grid[tile.pad_destinations] = tile.grid[tile.pad_sources]
        paint_sampling.store_skew_correction_tile(group, tile.tile, tile.grid.reshape(tile.height, tile.width))
        written += 1
    session.dirty_tiles.clear()
    return written


def commit(context) -> int:
    """Write what the strokes changed (mesh layers or correction maps). Returns items written."""
    session = _SESSION
    if session is None:
        return 0
    if session.kind == KIND_SKEW:
        return _commit_skew(context, session)
    if not session.dirty_entries:
        return 0
    written = 0
    for index in sorted(session.dirty_entries):
        entry = session.entries[index]
        obj = bpy.data.objects.get(entry.name)
        mesh = getattr(obj, "data", None) if obj is not None else None
        if mesh is None or len(mesh.loops) != entry.loop_count:
            continue
        values = session.loop_values[entry.loop_start : entry.loop_start + entry.loop_count]
        if _write_layer(mesh, paint_sampling.OFFSET_ATTRIBUTE, values):
            _mark_paint_only(obj, mesh)
            mesh.update_tag()
            written += 1
    session.dirty_entries.clear()
    return written


def sample_value(context, region, rv3d, coord) -> float | None:
    """The painted value at the surface under *coord* (nearest welded point or texel)."""
    session = _SESSION
    if session is None:
        return None
    origin, direction = _mouse_ray(region, rv3d, coord)
    hit = _raycast(session, origin, direction)
    if hit is None:
        return None
    if session.kind == KIND_SKEW:
        if session.texel_positions.shape[0] == 0:
            return None
        delta = session.texel_positions - np.asarray(hit[0], dtype=np.float32)
        return float(session.texel_values[int(np.argmin(np.einsum("ij,ij->i", delta, delta)))])
    delta = session.point_positions - np.asarray(hit[0], dtype=np.float32)
    nearest = int(np.argmin(np.einsum("ij,ij->i", delta, delta)))
    return float(session.point_values[nearest])


def describe_value(session: PaintSession, value: float, context=None) -> str:
    if session.kind == KIND_OFFSET:
        percent = value * 100.0
        text = f"{percent:+.0f}%"
        if session.cage_mode == constants.CAGE_MODE_DISTANCE and session.cursor is not None:
            base = float(np.median(session.base_distance_per_loop)) if session.base_distance_per_loop.size else 0.0
            if base > 0.0:
                unit = getattr(getattr(getattr(context, "scene", None), "unit_settings", None), "system", "METRIC")
                try:
                    distance = bpy.utils.units.to_string(unit, "LENGTH", base * max(0.0, 1.0 + value), precision=3)
                except Exception:
                    distance = f"{base * max(0.0, 1.0 + value):.4f}"
                text = f"{text} ({distance})"
        return text
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

_SRGB_GLSL = """
vec3 srgb_to_linear(vec3 c)
{
  vec3 low = c / 12.92;
  vec3 high = pow((c + vec3(0.055)) / 1.055, vec3(2.4));
  return mix(low, high, step(vec3(0.04045), c));
}
"""


def _tint_shader():
    shader = _SHADERS.get("tint")
    if shader is not None:
        return shader
    from . import overlay_gpu

    info = gpu.types.GPUShaderCreateInfo()
    iface = gpu.types.GPUStageInterfaceInfo("fyr_paint_tint_iface")
    iface.smooth("VEC4", "tintColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("FLOAT", "signedMode")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.push_constant("VEC4", "raiseColor")
    info.push_constant("VEC4", "lowerColor")
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "FLOAT", "value")
    info.vertex_out(iface)
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        _SRGB_GLSL
        + """
void main()
{
  vec3 rgb;
  float amount;
  if (signedMode > 0.5) {
    float v = clamp(value, -1.0, 1.0);
    rgb = v >= 0.0 ? raiseColor.rgb : lowerColor.rgb;
    amount = abs(v);
  } else {
    amount = clamp(value, 0.0, 1.0);
    rgb = vec3(0.72, 0.36, 1.00);
  }
  float alpha = amount > 1.0e-4 ? 0.10 + 0.45 * amount : 0.0;
  tintColor = vec4(srgb_to_linear(rgb), alpha);
  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
"""
        + overlay_gpu._CAGE_DEPTH_BIAS_GLSL
        + """}
"""
    )
    info.fragment_source(
        """
void main()
{
  if (tintColor.a <= 0.0) {
    discard;
  }
  FragColor = tintColor;
}
"""
    )
    shader = gpu.shader.create_from_info(info)
    _SHADERS["tint"] = shader
    return shader


def _map_tint_shader():
    """Surface tint read from the skew correction map through the bake UVs."""
    shader = _SHADERS.get("map_tint")
    if shader is not None:
        return shader
    from . import overlay_gpu

    info = gpu.types.GPUShaderCreateInfo()
    iface = gpu.types.GPUStageInterfaceInfo("fyr_paint_map_tint_iface")
    iface.smooth("VEC2", "mapUV")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC2", "uv")
    info.sampler(0, "FLOAT_2D", "correctionMap")
    info.vertex_out(iface)
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        """
void main()
{
  mapUV = uv;
  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
"""
        + overlay_gpu._CAGE_DEPTH_BIAS_GLSL
        + """}
"""
    )
    info.fragment_source(
        _SRGB_GLSL
        + """
void main()
{
  float amount = clamp(texture(correctionMap, mapUV).r, 0.0, 1.0);
  if (amount <= 1.0e-4) {
    discard;
  }
  FragColor = vec4(srgb_to_linear(vec3(0.72, 0.36, 1.00)), 0.10 + 0.45 * amount);
}
"""
    )
    shader = gpu.shader.create_from_info(info)
    _SHADERS["map_tint"] = shader
    return shader


def _correction_texture(tile, buffer):
    """R32F texture of one tile, sampled like the backend: bilinear between texel centres,
    clamped at the map edge (nearest filtering drew every texel as a flat square)."""
    texture = gpu.types.GPUTexture((tile.width, tile.height), format="R32F", data=buffer)
    texture.filter_mode(True)
    texture.extend_mode("EXTEND")
    return texture


def _rebuild_skew_tint(session: PaintSession) -> None:
    """One batch and one R32F texture per UDIM tile the lows' UVs touch. The batches are
    built once per session; later calls only upload the maps."""
    if session.tile_batches:
        for tile in session.tiles:
            buffer = gpu.types.Buffer("FLOAT", tile.width * tile.height, tile.grid)
            tile.texture = _correction_texture(tile, buffer)
        return
    if not session.tiles:
        return
    tri_uvs = session.loop_uvs[session.tri_loops]
    centroids = tri_uvs.mean(axis=1)
    tri_tiles = 1001 + np.floor(centroids[:, 0]).astype(np.int64) + 10 * np.floor(centroids[:, 1]).astype(np.int64)
    for index, tile in enumerate(session.tiles):
        tris = np.flatnonzero(tri_tiles == tile.tile)
        if tris.size == 0:
            continue
        offset = np.array([(tile.tile - 1001) % 10, (tile.tile - 1001) // 10], dtype=np.float32)
        corners = session.tri_loops[tris].reshape(-1)
        batch = batch_for_shader(
            _map_tint_shader(),
            "TRIS",
            {"pos": session.loop_positions[corners], "uv": (session.loop_uvs[corners] - offset).astype(np.float32)},
        )
        buffer = gpu.types.Buffer("FLOAT", tile.width * tile.height, tile.grid)
        tile.texture = _correction_texture(tile, buffer)
        session.tile_batches.append((index, batch))


#: Paint Offset cage: the wire and a see-through surface in the same colour.
_CAGE_COLOR = (0.55, 0.85, 1.0)
_CAGE_SURFACE_OPACITY = 0.08
_DEFAULT_RAISE_COLOR = (0.16, 0.50, 1.00)
_DEFAULT_LOWER_COLOR = (1.00, 0.24, 0.20)


def _seed_offset_colors(context) -> None:
    """Copy the addon preferences' offset tint colours into this scene's brush once."""
    brush = brush_settings(context)
    if brush is None or bool(getattr(brush, "offset_colors_seeded", True)):
        return
    try:
        from . import preferences

        prefs = preferences.get_preferences(migrate=False)
        if prefs is not None:
            brush.offset_raise_color = tuple(prefs.paint_offset_raise_color)
            brush.offset_lower_color = tuple(prefs.paint_offset_lower_color)
        brush.offset_colors_seeded = True
    except Exception:
        pass


def _offset_tint_colors(brush):
    raise_rgb = tuple(getattr(brush, "offset_raise_color", _DEFAULT_RAISE_COLOR)) if brush is not None else _DEFAULT_RAISE_COLOR
    lower_rgb = tuple(getattr(brush, "offset_lower_color", _DEFAULT_LOWER_COLOR)) if brush is not None else _DEFAULT_LOWER_COLOR
    return raise_rgb[:3], lower_rgb[:3]


def _cage_surface_shader():
    shader = _SHADERS.get("cage_surface")
    if shader is not None:
        return shader
    from . import overlay_gpu

    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.push_constant("VEC4", "surfaceColor")
    info.vertex_in(0, "VEC3", "pos")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        "void main()\n{\n  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        + overlay_gpu._CAGE_DEPTH_BIAS_GLSL
        + "}\n"
    )
    info.fragment_source(
        _SRGB_GLSL + "void main()\n{\n  FragColor = vec4(srgb_to_linear(surfaceColor.rgb), surfaceColor.a);\n}\n"
    )
    shader = gpu.shader.create_from_info(info)
    _SHADERS["cage_surface"] = shader
    return shader


def _line_shader():
    shader = _SHADERS.get("line")
    if shader is None:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        _SHADERS["line"] = shader
    return shader


def _needle_directions(session: PaintSession):
    """Needle (start, direction) arrays mirroring the bake ray (cage.py needles).

    The base ray is the projection normal (Smooth Cage on: welded; off: bridged split
    normal); a Custom/Automatic cage bends it toward the cage point by the 1.0.x per-vertex
    skew. The painted correction, sampled at the needle UV, then straightens it toward the
    low's flat face normal (cage.apply_skew_correction, the backend's rule).
    """
    if session.needle_tris.size == 0:
        return None
    tris = session.needle_loops
    w = session.needle_weights
    starts = session.needle_starts
    welded = session.point_normals[session.loop_point]
    base_normals = welded if session.smooth_cage else session.loop_normals
    projection = core.normalize_rows(_interpolate(base_normals, tris, w))
    base = projection
    if session.cage_mode != constants.CAGE_MODE_DISTANCE and session.needle_cage_points is not None:
        to_cage = session.needle_cage_points - starts
        degenerate = np.einsum("ij,ij->i", to_cage, to_cage) <= 1.0e-12
        to_cage[degenerate] = projection[degenerate]
        legacy = np.einsum("kj,kj->k", session.legacy_loop_skews[tris], w)
        base = core.skew_blend(projection, to_cage, legacy)
    corrections = cage.sample_skew_correction(session.correction_tiles(), session.needle_uvs)
    directions = cage.apply_skew_correction(
        base, session.tri_face_normals[session.needle_tris], corrections, projection
    )
    return starts, np.asarray(directions, dtype=np.float32)


#: While a stroke runs, the needle field (up to ~220k needles, ~45 ms) is rebuilt at most
#: this often; the tint and cage follow every redraw, and release rebuilds everything.
_NEEDLE_REBUILD_INTERVAL = 0.08


def _rebuild_batches(context, session: PaintSession, *, needles: bool = True) -> None:
    group = _session_group(context, session)
    paint_state = properties.group_paint_projection_settings_state(group) if group is not None else None
    corners = session.tri_loops.reshape(-1)
    if session.kind == KIND_SKEW:
        session.tint_batch = None
        _rebuild_skew_tint(session)
    else:
        session.tint_batch = batch_for_shader(
            _tint_shader(),
            "TRIS",
            {"pos": session.loop_positions[corners], "value": session.loop_values[corners].astype(np.float32)},
        )
    session.cage_batch = None
    session.cage_surface_batch = None
    if session.kind == KIND_OFFSET:
        multiplier = np.maximum(1.0 + session.loop_values, 0.0)
        if session.cage_mode == constants.CAGE_MODE_DISTANCE:
            directions = session.point_normals[session.loop_point] if session.smooth_cage else session.loop_normals
            cage_positions = session.loop_positions + directions * (session.base_distance_per_loop * multiplier)[:, None]
            segments = cage_positions[session.poly_edge_loops.reshape(-1)]
            surface = cage_positions[corners]
        elif session.cage_targets is not None:
            if session.loop_offset_scale.shape[0] == session.loop_values.shape[0]:
                scale = session.loop_offset_scale[corners]
            else:
                scale = float(getattr(paint_state, "paint_offset_scale", 1.0) or 0.0) if paint_state is not None else 1.0
            low = session.loop_positions[corners]
            cage_corners = low + (session.cage_targets - low) * (multiplier[corners] * scale)[:, None]
            tri_edges = np.stack(
                [cage_corners[0::3], cage_corners[1::3], cage_corners[1::3], cage_corners[2::3], cage_corners[2::3], cage_corners[0::3]],
                axis=1,
            )
            segments = tri_edges.reshape(-1, 3)
            surface = cage_corners
        else:
            segments = None
            surface = None
        if segments is not None and len(segments):
            session.cage_batch = batch_for_shader(_line_shader(), "LINES", {"pos": segments.astype(np.float32)})
        if surface is not None and len(surface):
            session.cage_surface_batch = batch_for_shader(
                _cage_surface_shader(), "TRIS", {"pos": np.asarray(surface, dtype=np.float32)}
            )
            if session.cage_depth_wanted:
                _rebuild_cage_depth_batches(context, session, surface, multiplier, corners)
    session.display_dirty = False
    if needles or session.needle_batch is None:
        _rebuild_needles(session, paint_state)
        session.needles_dirty = False
    else:
        session.needles_dirty = True


#: While a stroke runs, the dense coverage cage is rebuilt at most this often (release
#: rebuilds it at once); the drawn cage and tint still follow every dab.
_CAGE_DEPTH_REBUILD_INTERVAL = 0.08


def _exact_distance_surface(session: PaintSession, multiplier, corners):
    """The Distance cage exactly as the bake fires from it, 16 triangles per low
    triangle: lerp(position) + normalize(lerp(normal)) * lerp(offset * paint)
    (cage.subdivide_offset_arrays), the same cage the static coverage judges against.
    Smooth Cage off traces the split (bridged) corner normals instead of the welded ones."""
    directions = session.point_normals[session.loop_point] if session.smooth_cage else session.loop_normals
    distances = (session.base_distance_per_loop * multiplier).astype(np.float32)
    positions, normals, (lerped,) = cage.subdivide_offset_arrays(
        session.loop_positions[corners].astype(np.float32),
        directions[corners].astype(np.float32),
        2,
        extras=[distances[corners]],
    )
    positions = np.frombuffer(positions, dtype=np.float32).reshape(-1, 3)
    normals = np.frombuffer(normals, dtype=np.float32).reshape(-1, 3)
    lerped = np.frombuffer(lerped, dtype=np.float32)
    return positions + normals * lerped[:, None], 16


def _rebuild_cage_depth_batches(context, session: PaintSession, surface, multiplier, corners) -> None:
    now = time.monotonic()
    if session.stroke_active and session.cage_depth_batches and now - session.last_cage_depth_build < _CAGE_DEPTH_REBUILD_INTERVAL:
        # Come back for it once the interval has passed.
        session.cage_depth_pending = True
        _tag_redraw(context)
        return
    per_triangle = 1
    if session.cage_mode == constants.CAGE_MODE_DISTANCE:
        surface, per_triangle = _exact_distance_surface(session, multiplier, corners)
    batches = {}
    ranges = session.group_tri_ranges or {session.group_name: (0, int(session.tri_loops.shape[0]))}
    rows = 3 * per_triangle
    for range_group, (t0, t1) in ranges.items():
        if t1 > t0:
            batches[range_group] = _cage_depth_batch(surface[t0 * rows : t1 * rows])
    session.cage_depth_batches = batches
    session.last_cage_depth_build = now
    session.cage_depth_pending = False


def _cage_depth_batch(surface):
    """The live cage triangles for the coverage depth mask (zero normals: no offset)."""
    from . import overlay_gpu, overlays

    positions = np.asarray(surface, dtype=np.float32)
    shader = overlay_gpu.get_shell_cage_depth_mask_shader(overlays._OVERLAY_GPU_STATE)
    return batch_for_shader(shader, "TRIS", {"position": positions, "normal": np.zeros_like(positions)})


def live_coverage_cage_batch(context, group):
    """The cage the offset brush is painting on *group*, for Cage Coverage, or None.

    While a session paints, the static coverage passes still carry the pre-session
    offsets; the coverage mask draws this batch instead so red turns blue as the
    painted cage clears the high poly. None when no live cage can be built (an
    Automatic fit still pending): the static passes are then still current.
    """
    session = _SESSION
    if session is None or session.kind != KIND_OFFSET or not session_owns(group, KIND_OFFSET):
        return None
    if not session.cage_depth_wanted:
        session.cage_depth_wanted = True
        session.display_dirty = True
    if session.display_dirty or session.cage_depth_pending:
        _refresh_cage_targets(context, session)
        _rebuild_batches(context, session)
    return session.cage_depth_batches.get(str(getattr(group, "name", "") or ""))


def _rebuild_needles(session: PaintSession, paint_state) -> None:
    session.needle_batch = None
    if session.kind != KIND_SKEW:
        return
    result = _needle_directions(session)
    if result is None:
        return
    starts, directions = result
    colors = core.skew_deviation_colors(session.tri_face_normals[session.needle_tris], directions)
    count = starts.shape[0]
    pos = np.repeat(starts, 2, axis=0)
    needle = np.zeros((count * 2, 3), dtype=np.float32)
    needle[1::2] = directions * session.needle_lengths[:, None]
    from . import overlays

    shader = overlays._get_skew_shader()
    session.needle_batch = batch_for_shader(
        shader,
        "LINES",
        {
            "pos": pos,
            "needle": needle,
            "color": np.repeat(colors, 2, axis=0),
            "dir": np.repeat(directions, 2, axis=0),
        },
    )
    session.last_needle_build = time.monotonic()


def _draw_view() -> None:
    session = _SESSION
    context = bpy.context
    if session is None:
        return
    try:
        if session_exit_reason(context) is not None:
            _schedule_exit_check()
            return
        brush = brush_settings(context)
        _refresh_cage_targets(context, session)
        throttled = (
            session.stroke_active
            and session.kind == KIND_SKEW
            and time.monotonic() - session.last_needle_build < _NEEDLE_REBUILD_INTERVAL
        )
        if session.display_dirty or (session.needles_dirty and not throttled):
            _rebuild_batches(context, session, needles=not throttled)
        if session.needles_dirty:
            # Come back for the needles once the interval has passed.
            _tag_redraw(context)
        projection = gpu.matrix.get_projection_matrix()
        model_view = gpu.matrix.get_model_view_matrix()
        mvp = projection @ model_view
        group = _session_group(context, session)
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)
        from . import overlay_renderer

        bias_cap = overlay_renderer.cage_depth_bias_clip_cap(context, group) if group is not None else 0.0
        if session.tint_batch is not None and (brush is None or brush.show_values):
            shader = _tint_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("signedMode", 1.0 if session.kind == KIND_OFFSET else 0.0)
            shader.uniform_float("depthBiasClipCap", float(bias_cap))
            raise_rgb, lower_rgb = _offset_tint_colors(brush)
            shader.uniform_float("raiseColor", (*raise_rgb, 1.0))
            shader.uniform_float("lowerColor", (*lower_rgb, 1.0))
            session.tint_batch.draw(shader)
        if session.tile_batches and (brush is None or brush.show_values):
            shader = _map_tint_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("depthBiasClipCap", float(bias_cap))
            for tile_index, batch in session.tile_batches:
                texture = session.tiles[tile_index].texture
                if texture is None:
                    continue
                shader.uniform_sampler("correctionMap", texture)
                batch.draw(shader)
        if session.cage_surface_batch is not None:
            # The pushed-out cage as a see-through shell, so how far it sits off the surface
            # reads while painting (the wire alone showed only its edges).
            shader = _cage_surface_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("depthBiasClipCap", float(bias_cap))
            shader.uniform_float("surfaceColor", (*_CAGE_COLOR, _CAGE_SURFACE_OPACITY))
            session.cage_surface_batch.draw(shader)
        if session.cage_batch is not None:
            shader = _line_shader()
            shader.bind()
            gpu.state.line_width_set(1.0)
            shader.uniform_float("color", (*_CAGE_COLOR, 0.55))
            session.cage_batch.draw(shader)
        if session.needle_batch is not None:
            from . import overlays

            settings = getattr(context.scene, "fyr_baker_settings", None)
            overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
            shader = overlays._get_skew_shader()
            shader.bind()
            viewport = gpu.state.viewport_get()
            constant, pixel_to_world, is_persp = overlay_renderer.skew_screen_size_uniforms(
                projection,
                (float(viewport[2]), float(viewport[3])),
                bool(getattr(overlay_state, "skew_debug_constant_screen_size", False)),
            )
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("ModelViewMatrix", model_view)
            shader.uniform_float("needleScale", float(getattr(overlay_state, "skew_debug_length", 1.0) or 0.0))
            shader.uniform_float("constantScreenSize", 1.0 if constant else 0.0)
            shader.uniform_float("pixelToWorld", float(pixel_to_world) if constant else 0.0)
            shader.uniform_float("isPersp", 1.0 if is_persp else 0.0)
            session.needle_batch.draw(shader)
        if session.cursor is not None and brush is not None:
            _draw_cursor(session, brush)
    except Exception:
        traceback.print_exc()
    finally:
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
        gpu.state.line_width_set(1.0)


_MODE_COLORS = {
    core.MODE_ADD: (1.00, 0.55, 0.15, 0.9),
    core.MODE_SUBTRACT: (0.25, 0.60, 1.00, 0.9),
    core.MODE_SMOOTH: (0.35, 0.95, 0.55, 0.9),
    core.MODE_SET: (0.95, 0.95, 0.95, 0.9),
    core.MODE_ERASE: (0.85, 0.35, 0.35, 0.9),
}


def _circle(center: Vector, normal: Vector, radius: float, segments: int = 48):
    tangent = normal.orthogonal().normalized()
    bitangent = normal.cross(tangent).normalized()
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    points = [center + (tangent * float(np.cos(a)) + bitangent * float(np.sin(a))) * radius for a in angles]
    lines = []
    for index, point in enumerate(points):
        lines.append(tuple(point))
        lines.append(tuple(points[(index + 1) % segments]))
    return lines


def _draw_cursor(session: PaintSession, brush) -> None:
    location, normal, radius, _coord = session.cursor
    mode = _CURRENT_STROKE_MODE or session.hover_mode or brush.mode
    color = _MODE_COLORS.get(mode, (1.0, 1.0, 1.0, 0.9))
    lift = normal * (radius * 0.01)
    lines = _circle(location + lift, normal, radius)
    hardness = float(brush.hardness)
    if hardness > 0.01:
        lines += _circle(location + lift, normal, radius * hardness, 32)
    shader = _line_shader()
    shader.bind()
    gpu.state.depth_test_set("NONE")
    gpu.state.line_width_set(2.0)
    shader.uniform_float("color", color)
    batch_for_shader(shader, "LINES", {"pos": lines}).draw(shader)


def _draw_pixel() -> None:
    session = _SESSION
    if session is None or session.cursor is None:
        return
    try:
        import blf

        context = bpy.context
        value = session.hud_value
        if not value:
            return
        x, y = session.cursor[3]
        scale = float(getattr(getattr(context.preferences, "system", None), "ui_scale", 1.0) or 1.0)
        font_id = 0
        blf.size(font_id, 14.0 * scale)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        blf.enable(font_id, blf.SHADOW)
        blf.shadow(font_id, 5, 0.0, 0.0, 0.0, 1.0)
        blf.position(font_id, x + 16 * scale, y + 16 * scale, 0)
        blf.draw(font_id, value)
        blf.disable(font_id, blf.SHADOW)
    except Exception:
        traceback.print_exc()


def _ensure_draw_handlers() -> None:
    if _DRAW_HANDLES:
        return
    _DRAW_HANDLES.append(bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), "WINDOW", "POST_VIEW"))
    _DRAW_HANDLES.append(bpy.types.SpaceView3D.draw_handler_add(_draw_pixel, (), "WINDOW", "POST_PIXEL"))


def _remove_draw_handlers() -> None:
    while _DRAW_HANDLES:
        handle = _DRAW_HANDLES.pop()
        try:
            bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
        except Exception:
            pass


def _event_mode(brush, event) -> str:
    return core.modifier_mode(
        brush.mode,
        shift=bool(getattr(event, "shift", False)),
        ctrl=bool(getattr(event, "ctrl", False)),
    )


def _update_hover(context, region, rv3d, coord) -> None:
    session = _SESSION
    brush = brush_settings(context)
    if session is None or brush is None:
        return
    origin, direction = _mouse_ray(region, rv3d, coord)
    hit = _raycast(session, origin, direction)
    if hit is None:
        session.cursor = None
        session.hud_value = ""
        return
    radius = _world_radius(region, rv3d, coord, hit[0], float(brush.radius))
    session.cursor = (hit[0], hit[1], radius, tuple(coord))
    value = sample_value(context, region, rv3d, coord)
    session.hud_value = describe_value(session, value, context) if value is not None else ""


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

_CURRENT_STROKE_MODE: str = ""
_MODIFIER_KEYS = {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL"}


def _poll_session_or_tool(context) -> bool:
    if getattr(getattr(context, "area", None), "type", "") != "VIEW_3D":
        return False
    return _SESSION is not None or _active_tool_id(context) in TOOL_IDS.values()


def _ensure_session_for_tool(context) -> bool:
    """A tool picked from the toolbar with no session opens one on the active group."""
    tool_id = _active_tool_id(context)
    kind = next((k for k, v in TOOL_IDS.items() if v == tool_id), None)
    if kind is None:
        return _SESSION is not None
    if _SESSION is not None and _SESSION.kind == kind:
        return True
    project, group = _resolve_project_group(context)
    if project is None or group is None:
        return False
    ok, _message = start_session(context, project, group, kind)
    return ok


class MASTER_BAKER_OT_paint_brush_stroke(bpy.types.Operator):
    bl_idname = "master_baker.paint_brush_stroke"
    bl_label = "Paint Stroke"
    bl_description = "Paint the cage offset or the ray skew on the bake group's low meshes"
    # One undo step per stroke; no REGISTER, so no redo panel for a brush stroke.
    bl_options = {"UNDO", "BLOCKING"}

    @classmethod
    def poll(cls, context):
        return _poll_session_or_tool(context)

    def invoke(self, context, event):
        global _CURRENT_STROKE_MODE
        if not _ensure_session_for_tool(context):
            self.report({"ERROR"}, "Select a bake group with a low mesh to paint")
            return {"CANCELLED"}
        brush = brush_settings(context)
        region = context.region
        rv3d = context.region_data
        if brush is None or region is None or rv3d is None:
            return {"CANCELLED"}
        self._mode = _event_mode(brush, event)
        _CURRENT_STROKE_MODE = self._mode
        self._region = region
        self._rv3d = rv3d
        self._snapshot = _SESSION.loop_values.copy()
        self._point_snapshot = _SESSION.point_values.copy()
        self._texel_snapshot = _SESSION.texel_values.copy()
        self._grid_snapshots = [tile.grid.copy() for tile in _SESSION.tiles]
        self._changed = False
        self._last = (float(event.mouse_region_x), float(event.mouse_region_y))
        self._leftover = 0.0
        _SESSION.stroke_active = True
        self._dab(context, self._last, event)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _dab(self, context, coord, event) -> None:
        pressure = float(getattr(event, "pressure", 1.0) or 1.0)
        if pressure <= 0.0:
            pressure = 1.0
        if apply_dab(context, self._region, self._rv3d, coord, self._mode, pressure):
            self._changed = True
        session = _SESSION
        if session is not None:
            value = sample_value(context, self._region, self._rv3d, coord)
            session.hud_value = describe_value(session, value, context) if value is not None else ""
        self._region.tag_redraw()

    def modal(self, context, event):
        global _CURRENT_STROKE_MODE
        if _SESSION is None:
            _CURRENT_STROKE_MODE = ""
            return {"CANCELLED"}
        if event.type in _MODIFIER_KEYS:
            # Held modifiers pick the mode live: Shift in the middle of a stroke smooths
            # until it is released.
            self._mode = _event_mode(brush_settings(context), event)
            _CURRENT_STROKE_MODE = self._mode
            self._region.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            brush = brush_settings(context)
            self._mode = _event_mode(brush, event)
            _CURRENT_STROKE_MODE = self._mode
            current = (float(event.mouse_region_x), float(event.mouse_region_y))
            spacing = max(1.0, float(brush.radius) * float(brush.spacing) / 100.0)
            for position in core.dab_spacing_positions(self._last, current, spacing):
                self._dab(context, (float(position[0]), float(position[1])), event)
                self._last = (float(position[0]), float(position[1]))
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            _SESSION.stroke_active = False
            _SESSION.display_dirty = True
            _CURRENT_STROKE_MODE = ""
            if not self._changed:
                return {"CANCELLED"}
            commit(context)
            self._region.tag_redraw()
            return {"FINISHED"}
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            _SESSION.loop_values[:] = self._snapshot
            _SESSION.point_values[:] = self._point_snapshot
            _SESSION.texel_values[:] = self._texel_snapshot
            for tile, grid in zip(_SESSION.tiles, self._grid_snapshots):
                tile.grid[:] = grid
            _SESSION.dirty_tiles.clear()
            _SESSION.dirty_entries.clear()
            _SESSION.display_dirty = True
            _SESSION.stroke_active = False
            _CURRENT_STROKE_MODE = ""
            self._region.tag_redraw()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


class MASTER_BAKER_OT_paint_brush_hover(bpy.types.Operator):
    """Track the brush cursor over the surface (bound to mouse move in the tool)."""

    bl_idname = "master_baker.paint_brush_hover"
    bl_label = "Paint Brush Cursor"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return _SESSION is not None and getattr(getattr(context, "area", None), "type", "") == "VIEW_3D"

    def invoke(self, context, event):
        brush = brush_settings(context)
        if _SESSION is not None and brush is not None:
            _SESSION.hover_mode = _event_mode(brush, event)
        if context.region is not None and context.region_data is not None:
            if event.type in _MODIFIER_KEYS:
                context.region.tag_redraw()
                return {"PASS_THROUGH"}
            _update_hover(context, context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y))
            context.region.tag_redraw()
        return {"PASS_THROUGH"}


class MASTER_BAKER_OT_paint_brush_sample(bpy.types.Operator):
    bl_idname = "master_baker.paint_brush_sample"
    bl_label = "Sample Paint Value"
    bl_description = "Use the painted value under the cursor as the Set target"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _poll_session_or_tool(context)

    def invoke(self, context, event):
        if _SESSION is None and not _ensure_session_for_tool(context):
            return {"CANCELLED"}
        value = sample_value(context, context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y))
        brush = brush_settings(context)
        if value is None or brush is None:
            return {"CANCELLED"}
        if _SESSION.kind == KIND_OFFSET:
            brush.offset_target = value * 100.0
        else:
            brush.skew_target = value
        brush.mode = core.MODE_SET
        _tag_redraw(context)
        self.report({"INFO"}, f"Set target {describe_value(_SESSION, value, context)}")
        return {"FINISHED"}


class MASTER_BAKER_OT_paint_brush_exit(bpy.types.Operator):
    bl_idname = "master_baker.paint_brush_exit"
    bl_label = "Stop Painting"
    bl_description = "Leave Paint Offset or Paint Skew"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _SESSION is not None

    def execute(self, context):
        end_session(context)
        return {"FINISHED"}


class MASTER_BAKER_OT_paint_brush_fill(bpy.types.Operator):
    bl_idname = "master_baker.paint_brush_fill"
    bl_label = "Fill"
    bl_description = "Fill every low mesh of the bake group with the Set Value shown above"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _SESSION is not None

    def execute(self, context):
        session = _SESSION
        brush = brush_settings(context)
        value = _set_value_from_settings(session.kind, brush)
        lo, hi = _kind_bounds(session.kind)
        value = float(min(max(value, lo), hi))
        if session.kind == KIND_SKEW:
            session.texel_values[:] = value
            for index, tile in enumerate(session.tiles):
                tile.grid[session.texel_flat[session.texel_tile == index]] = value
            session.dirty_tiles.update(range(len(session.tiles)))
        else:
            session.loop_values[:] = value
            session.point_values[:] = value
            session.dirty_entries.update(range(len(session.entries)))
        session.display_dirty = True
        commit(context)
        _tag_redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


def _tool_keymap():
    stroke = "master_baker.paint_brush_stroke"
    hover = "master_baker.paint_brush_hover"
    # Blender's Sculpt / paint combinations; the stroke reads Shift (smooth) and Ctrl
    # (invert) from each event, dab by dab. Alt+LMB is left to Blender (3-button emulation).
    return (
        (stroke, {"type": "LEFTMOUSE", "value": "PRESS"}, None),
        (stroke, {"type": "LEFTMOUSE", "value": "PRESS", "ctrl": True}, None),
        (stroke, {"type": "LEFTMOUSE", "value": "PRESS", "shift": True}, None),
        (stroke, {"type": "LEFTMOUSE", "value": "PRESS", "ctrl": True, "shift": True}, None),
        (hover, {"type": "MOUSEMOVE", "value": "ANY", "any": True}, None),
    ) + tuple(
        (hover, {"type": key, "value": "ANY", "any": True}, None) for key in sorted(_MODIFIER_KEYS)
    ) + (
        (
            "wm.radial_control",
            {"type": "F", "value": "PRESS"},
            {"properties": [("data_path_primary", f"{_BRUSH_PATH}.radius")]},
        ),
        (
            "wm.radial_control",
            {"type": "F", "value": "PRESS", "shift": True},
            {"properties": [("data_path_primary", f"{_BRUSH_PATH}.strength")]},
        ),
        ("master_baker.paint_brush_sample", {"type": "S", "value": "PRESS"}, None),
        ("master_baker.paint_brush_exit", {"type": "ESC", "value": "PRESS"}, None),
    )


def draw_brush_header(layout, context, kind: str) -> None:
    """Compact brush settings for the tool header."""
    brush = brush_settings(context)
    if brush is None:
        return
    layout.prop(brush, "mode", text="", icon_only=False)
    layout.prop(brush, "radius")
    layout.prop(brush, "use_pressure_radius", text="", icon="STYLUS_PRESSURE")
    layout.prop(brush, "strength")
    layout.prop(brush, "use_pressure_strength", text="", icon="STYLUS_PRESSURE")
    if brush.mode == core.MODE_SET:
        layout.prop(brush, "offset_target" if kind == KIND_OFFSET else "skew_target")
    layout.popover("MASTER_BAKER_PT_paint_brush_options", text="Brush")


def _section(layout, title: str, icon: str):
    """A boxed section with an icon header and a rule under it."""
    box = layout.box()
    header = box.row()
    header.label(text=title, icon=icon)
    box.separator(type="LINE")
    return box


def _labelled_value(layout, brush, prop: str, label: str, icon: str, *, pressure: str = "") -> None:
    row = layout.row(align=True)
    label_row = row.row()
    label_row.label(text=label, icon=icon)
    value = row.row(align=True)
    value.prop(brush, prop, text="", slider=prop != "radius")
    if pressure:
        value.prop(brush, pressure, text="", icon="STYLUS_PRESSURE")
    else:
        # Same width as the rows with a pressure toggle, so the sliders line up.
        value.label(text="", icon="BLANK1")


def draw_brush_sections(layout, context, kind: str, group) -> None:
    """Sidebar brush settings while a session is live, laid out as separate boxed sections:
    Brush Settings (modes and falloff on the left, the value sliders on the right),
    Options, and Actions."""
    brush = brush_settings(context)
    if brush is None:
        return
    layout = layout.column()
    layout.use_property_split = False

    box = _section(layout, "Brush Settings", "BRUSH_DATA")
    split = box.split(factor=0.46)
    left = split.column()
    left.label(text="Mode")
    grid = left.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
    for mode in core.MODES:
        grid.prop_enum(brush, "mode", mode)
    left.separator()
    left.label(text="Brush Falloff")
    left.prop(brush, "falloff", text="")
    right = split.column(align=False)
    # One empty row so Radius starts level with the first mode buttons, under "Mode".
    right.label(text="")
    _labelled_value(right, brush, "radius", "Radius", "MESH_CIRCLE", pressure="use_pressure_radius")
    _labelled_value(right, brush, "strength", "Strength", "FORCE_FORCE", pressure="use_pressure_strength")
    _labelled_value(right, brush, "hardness", "Hardness", "SPHERECURVE")
    _labelled_value(right, brush, "spacing", "Spacing", "THREE_DOTS")
    if brush.mode == core.MODE_SET:
        target = "offset_target" if kind == KIND_OFFSET else "skew_target"
        _labelled_value(right, brush, target, "Set Value", "IPO_CONSTANT")

    box = _section(layout, "Options", "PREFERENCES")
    grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True)
    for prop, label, icon in (
        ("use_visible_only", "Visible Only", "HIDE_OFF"),
        ("use_front_faces_only", "Front Faces Only", "NORMALS_FACE"),
        ("use_connected_only", "Connected Only", "LINKED"),
        ("show_values", "Show Values", "COLOR"),
    ):
        cell = grid.row(align=True)
        cell.prop(brush, prop, text="")
        cell.label(text=label, icon=icon)
    if kind == KIND_OFFSET:
        colors = box.row(align=True)
        colors.prop(brush, "offset_raise_color", text="Raised")
        colors.prop(brush, "offset_lower_color", text="Lowered")
        box.prop(group, "paint_offset_scale", text="Offset Scale", slider=True)
    elif getattr(group, "paint_skew_image", None) is not None:
        # Skew Amount scales the 1.0.x skew image only; the correction map is used as painted.
        box.prop(group, "paint_skew", text="Skew Amount", slider=True)

    box = _section(layout, "Actions", "TOOL_SETTINGS")
    # The value Fill (and the Set mode) paints, always visible where Fill is: it used to
    # show only in Set mode, so Fill painted a value nobody could see.
    box.prop(brush, "offset_target" if kind == KIND_OFFSET else "skew_target", text="Set Value", slider=True)
    row = box.row()
    row.scale_y = 1.2
    row.operator("master_baker.paint_brush_fill", text="Fill", icon="MATFLUID")
    clear = row.operator(
        "master_baker.clear_paint_image",
        text="Clear Offset" if kind == KIND_OFFSET else "Clear Skew",
        icon="TRASH",
    )
    clear.target = "OFFSET" if kind == KIND_OFFSET else "SKEW"


def _draw_brush_options(layout, brush) -> None:
    col = layout.column(align=True)
    row = col.row(align=True)
    row.prop(brush, "falloff", text="")
    row.prop(brush, "hardness")
    col.prop(brush, "spacing")
    col = layout.column(align=True)
    col.prop(brush, "use_visible_only")
    col.prop(brush, "use_front_faces_only")
    col.prop(brush, "use_connected_only")
    col.prop(brush, "show_values")


class MASTER_BAKER_PT_paint_brush_options(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_label = "Brush Options"

    def draw(self, context):
        brush = brush_settings(context)
        if brush is not None:
            _draw_brush_options(self.layout, brush)


class _FyrPaintToolBase(_WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_cursor = "CROSSHAIR"
    bl_keymap = _tool_keymap()
    _kind = KIND_OFFSET

    @classmethod
    def draw_settings(cls, context, layout, tool):
        if _SESSION is None or _SESSION.kind != cls._kind:
            _schedule_tool_sync()
        draw_brush_header(layout, context, cls._kind)


class FYR_TOOL_paint_offset(_FyrPaintToolBase):
    bl_idname = TOOL_OFFSET_ID
    bl_label = "Paint Offset"
    bl_description = (
        "Paint where the cage sits. Add pushes the cage out, Ctrl pulls it in, Shift smooths. "
        "Paint is stored on the low mesh and needs no UVs"
    )
    bl_icon = "brush.particle.length"
    _kind = KIND_OFFSET


class FYR_TOOL_paint_skew(_FyrPaintToolBase):
    bl_idname = TOOL_SKEW_ID
    bl_label = "Paint Skew"
    bl_description = (
        "Paint where bake rays straighten out: painted areas fire rays straight off the "
        "low-poly faces. Needles show the ray direction; Ctrl lowers, Shift smooths"
    )
    bl_icon = "brush.particle.comb"
    _kind = KIND_SKEW


# ---------------------------------------------------------------------------
# Handlers and registration
# ---------------------------------------------------------------------------


@_persistent
def _on_undo_redo(_scene, *_args) -> None:
    if _SESSION is None:
        return
    try:
        reload_values(bpy.context)
    except Exception:
        traceback.print_exc()


@_persistent
def _on_load_pre(*_args) -> None:
    global _SESSION
    _SESSION = None


CLASSES = (
    MASTER_BAKER_OT_paint_brush_stroke,
    MASTER_BAKER_OT_paint_brush_hover,
    MASTER_BAKER_OT_paint_brush_sample,
    MASTER_BAKER_OT_paint_brush_exit,
    MASTER_BAKER_OT_paint_brush_fill,
    MASTER_BAKER_PT_paint_brush_options,
)

_TOOLS = (FYR_TOOL_paint_offset, FYR_TOOL_paint_skew)

#: Whether the two paint tools are in the toolbar. They only are while the scene has a bake
#: project: without one there is nothing to paint, and they would only clutter the toolbar.
_TOOLS_REGISTERED = False
_TOOLS_SYNC_PENDING = False


def _scene_has_bake_project(scene) -> bool:
    settings = getattr(scene, "fyr_baker_settings", None)
    try:
        return settings is not None and len(settings.projects) > 0
    except Exception:
        return False


def _register_tools() -> None:
    """One toolbar slot: Paint Offset with Paint Skew in its hold-to-expand group."""
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return
    offset_tool, skew_tool = _TOOLS
    try:
        bpy.utils.register_tool(offset_tool, separator=True, group=True)
        bpy.utils.register_tool(skew_tool, after={offset_tool.bl_idname})
        _TOOLS_REGISTERED = True
    except Exception:
        traceback.print_exc()
        _unregister_tools(force=True)


def _unregister_tools(*, force: bool = False) -> None:
    global _TOOLS_REGISTERED
    if not _TOOLS_REGISTERED and not force:
        return
    for tool in reversed(_TOOLS):
        try:
            bpy.utils.unregister_tool(tool)
        except Exception:
            pass
    _TOOLS_REGISTERED = False


def _sync_tools() -> None:
    context = bpy.context
    want = _scene_has_bake_project(getattr(context, "scene", None))
    if want == _TOOLS_REGISTERED:
        return
    if want:
        _register_tools()
    else:
        # The last bake project went away: close a live session and leave the tool first,
        # or the toolbar would keep an active tool that no longer exists.
        if _SESSION is not None:
            end_session(context, restore_tool=True)
        elif _active_tool_id(context) in TOOL_IDS.values():
            _set_tool(context, "builtin.select_box")
        _unregister_tools()
    _tag_redraw(context)
    for window in getattr(getattr(context, "window_manager", None), "windows", None) or ():
        for area in getattr(getattr(window, "screen", None), "areas", None) or ():
            area.tag_redraw()


def _deferred_tools_sync():
    global _TOOLS_SYNC_PENDING
    _TOOLS_SYNC_PENDING = False
    try:
        _sync_tools()
    except Exception:
        traceback.print_exc()
    return None


def _schedule_tools_sync() -> None:
    global _TOOLS_SYNC_PENDING
    if _TOOLS_SYNC_PENDING:
        return
    _TOOLS_SYNC_PENDING = True
    try:
        bpy.app.timers.register(_deferred_tools_sync, first_interval=0.0)
    except Exception:
        _TOOLS_SYNC_PENDING = False


#: Seconds between the cheap "does the scene have a bake project" checks. Removing the last
#: project (or clearing them from a script) does not always fire a scene-update handler.
_TOOLS_POLL_INTERVAL = 0.5


def _poll_tools_state():
    try:
        if _scene_has_bake_project(getattr(bpy.context, "scene", None)) != _TOOLS_REGISTERED:
            _sync_tools()
    except Exception:
        pass
    return _TOOLS_POLL_INTERVAL


@_persistent
def _on_tools_state_changed(*_args) -> None:
    """Project added or removed (or a file / undo step changed it): add or drop the tools,
    deferred to a timer so tools never register from inside a handler."""
    try:
        if _scene_has_bake_project(getattr(bpy.context, "scene", None)) != _TOOLS_REGISTERED:
            _schedule_tools_sync()
    except Exception:
        pass


def register() -> None:
    from .registration import safe_register_class

    for cls in CLASSES:
        safe_register_class(cls)
    handlers = bpy.app.handlers
    for handler_list in (handlers.undo_post, handlers.redo_post):
        if _on_undo_redo not in handler_list:
            handler_list.append(_on_undo_redo)
        if _on_tools_state_changed not in handler_list:
            handler_list.append(_on_tools_state_changed)
    if _on_load_pre not in handlers.load_pre:
        handlers.load_pre.append(_on_load_pre)
    for handler_list in (handlers.load_post, handlers.depsgraph_update_post):
        if _on_tools_state_changed not in handler_list:
            handler_list.append(_on_tools_state_changed)
    _schedule_tools_sync()
    try:
        if not bpy.app.timers.is_registered(_poll_tools_state):
            bpy.app.timers.register(_poll_tools_state, first_interval=_TOOLS_POLL_INTERVAL, persistent=True)
    except Exception:
        pass


def unregister() -> None:
    global _SESSION
    from .registration import safe_unregister_class

    _SESSION = None
    _remove_draw_handlers()
    handlers = bpy.app.handlers
    for handler_list in (
        handlers.undo_post, handlers.redo_post, handlers.load_pre, handlers.load_post, handlers.depsgraph_update_post
    ):
        for fn in (_on_undo_redo, _on_load_pre, _on_tools_state_changed):
            while fn in handler_list:
                handler_list.remove(fn)
    try:
        if bpy.app.timers.is_registered(_poll_tools_state):
            bpy.app.timers.unregister(_poll_tools_state)
    except Exception:
        pass
    _unregister_tools()
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
    _SHADERS.clear()
