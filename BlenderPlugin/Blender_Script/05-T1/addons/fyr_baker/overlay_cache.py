from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import time

from array import array

import bpy
import gpu

from . import auto_cage_fit_queue, cage, cage_fit_store, cage_session, constants, preferences, properties, runtime
from .overlay_keys import (
    effective_high_mesh_slots as _effective_high_mesh_slots,
    group_bake_uv_layer_name as _group_bake_uv_layer_name,
    group_role_assignments_state as _group_role_assignments_state,
    iter_unique_role_slots as _iter_unique_role_slots,
    overlay_settings_state as _overlay_settings_state,
)


_DEFAULT_LOW_DEPTH_EPSILON = 1.0e-5


def _group_paint_projection_settings_state(group):
    paint_state_fn = getattr(properties, "group_paint_projection_settings_state", None)
    if callable(paint_state_fn):
        return paint_state_fn(group)
    nested_state = getattr(group, "paint_projection_settings", None) if group is not None else None
    if nested_state is not None:
        return nested_state
    return group


def _iter_valid_role_slots(group, attr_name: str):
    for slot in _iter_unique_role_slots(group, attr_name):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield slot


@dataclass(slots=True)
class OverlayPass:
    fill_batch: object | None
    line_batch: object | None
    fill_color: tuple[float, float, float, float]
    line_color: tuple[float, float, float, float]
    line_width: float
    shader: object | None = None
    offset: float = 0.0
    uses_group_offset: bool = False
    depth_test_mode: str | None = None
    depth_write: bool = False
    color_write: bool = True
    face_culling_mode: str | None = None
    shader_mode: str = ""
    blend_mode: str | None = None
    kind: str = ""
    paint_texture: object | None = None
    paint_offset_scale: float = 1.0
    show_paint_mask: bool = False
    # Group NAME, never the group itself. Adding a project/group reallocates
    # the CollectionProperty storage, and a cached PropertyGroup pointer then
    # dangles -- dereferencing it in the draw callback crashes Blender inside
    # RNA lookup, which getattr() with a default cannot catch.
    offset_group_name: str = ""
    # Bake group whose cage this cage_fill / cage_line pass draws ("" = the active
    # group's fallback cage), so a paint session can hide only its own static cage.
    cage_group_name: str = ""


@dataclass(slots=True)
class OverlayCacheEntry:
    key: tuple | None = None
    passes: list[OverlayPass] = field(default_factory=list)
    low_depth_batches: list[object] = field(default_factory=list)
    cage_depth_batches: list[tuple[object, float]] = field(default_factory=list)
    coverage_cage_passes: dict[str, list[OverlayPass]] = field(default_factory=dict)
    low_depth_epsilon: float = _DEFAULT_LOW_DEPTH_EPSILON
    miss_batch: object | None = None


def _with_pass_kind(overlay_pass: OverlayPass, kind: str, *, depth_write: bool | None = None) -> OverlayPass:
    overlay_pass.kind = kind
    if depth_write is not None:
        overlay_pass.depth_write = bool(depth_write)
    return overlay_pass


def _tag_cage_group(passes: list[OverlayPass], start: int, group_name: str) -> None:
    for overlay_pass in passes[start:]:
        if not overlay_pass.cage_group_name:
            overlay_pass.cage_group_name = group_name


def _fitted_cage_fill_pass(deps, fill_batch, fill_color, *, depth_write: bool) -> OverlayPass:
    """Build a cage-fill pass for an already-fitted (Automatic/Custom) cage.

    The batch carries final positions + normals, so it is drawn through the same
    offset / offset-lit shaders as the Distance cage at a zero displacement.  Whether it
    is lit is governed solely by the ``cage_lit_shading`` preference — identical to the
    Distance cage — so switching cage mode no longer changes the shader used to draw it.
    """
    lit = bool(getattr(preferences.get_preferences(), "cage_lit_shading", False))
    if lit:
        overlay_pass = deps.make_lit_offset_overlay_pass(fill_batch, fill_color, 0.0)
    else:
        overlay_pass = deps.make_offset_overlay_pass(fill_batch, fill_color, 0.0)
    # The cage is already displaced; never re-apply a group offset at draw time.
    overlay_pass.offset = 0.0
    overlay_pass.uses_group_offset = False
    overlay_pass.offset_group_name = ""
    return _with_pass_kind(overlay_pass, "cage_fill", depth_write=depth_write)


def _group_cage_hidden(group) -> bool:
    """True when nothing of this group's cage should show: its cage eye is off, or every
    one of its low meshes is hidden in the viewport (H)."""
    if bool(getattr(group, "cage_overlay_hidden", False)):
        return True
    try:
        lows = [
            getattr(slot, "object_ref", None)
            for slot in getattr(_group_role_assignments_state(group), "low_meshes", []) or []
        ]
        lows = [obj for obj in lows if obj is not None]
        return bool(lows) and not any(obj.visible_get() for obj in lows)
    except Exception:
        return False


_STATIC_REBUILD_PENDING = False


def _request_static_rebuild() -> None:
    """Invalidate the static cage cache from outside the draw callback, once."""
    global _STATIC_REBUILD_PENDING
    if _STATIC_REBUILD_PENDING:
        return
    _STATIC_REBUILD_PENDING = True

    def _rebuild():
        global _STATIC_REBUILD_PENDING
        _STATIC_REBUILD_PENDING = False
        try:
            from . import overlays

            overlays.invalidate_overlay_cache(clear_static=True)
            overlays.tag_redraw_all_view3d()
        except Exception:
            pass
        return None

    try:
        bpy.app.timers.register(_rebuild, first_interval=0.05)
    except Exception:
        _STATIC_REBUILD_PENDING = False


#: refined fit key -> (content key, (plain offsets, diagnostics)): the first stage's fit,
#: kept for the refinement stage so it only adds the ray check.
_PLAIN_PREVIEW_FITS: dict = {}
#: refined fit keys whose plain stage loaded the final (refined) fit from cage_fit_store.
_STORED_FINAL: dict = {}
#: refined fit key -> the plain offsets the first stage drew, to tell when the ray check
#: changed nothing.
_PLAIN_OFFSETS_SEEN: dict = {}
#: object geometry signature -> its real-edge keys (cage.mesh_edge_keys), read once.
_EDGE_KEYS: dict = {}


def _mesh_edge_keys_cached(obj, depsgraph) -> set:
    try:
        from .overlay_keys import object_cache_signature

        signature = object_cache_signature(obj)
    except Exception:
        signature = None
    if signature is not None:
        cached = _EDGE_KEYS.get(signature)
        if cached is not None:
            return cached
    keys = cage.mesh_edge_keys(obj, depsgraph)
    if signature is not None:
        _EDGE_KEYS[signature] = keys
        while len(_EDGE_KEYS) > 512:
            _EDGE_KEYS.pop(next(iter(_EDGE_KEYS)))
    return keys
#: preview fit key -> cage_fit_store content key, so the geometry is hashed once.
_CONTENT_KEYS: dict = {}


@dataclass(slots=True)
class PreviewTargetCageCacheEntry:
    # Group NAME, never the group itself -- the same rule as OverlayPass.offset_group_name
    # above, for a second reason: the static overlay key is deliberately undo-stable and
    # undo handling only invalidates the DISPLAY cache, so these entries outlive a memfile
    # undo (toggle a per-group cage eye, Ctrl+Z) that has already freed the PropertyGroup
    # storage behind them. The next draw then dereferences freed RNA and takes Blender down
    # with an access violation inside the draw callback, which getattr() cannot catch.
    # build_overlay_cache re-resolves this name against the live project on every draw.
    group_name: str
    # The index the group had when the entry was built. A hint for that lookup only: it is
    # an O(1) hit while nothing was added or removed, but it is always validated against
    # group_name, because a reorder would otherwise silently draw another group's cage.
    group_index: int
    cage_mode: str
    slot_indices: tuple[int, ...] = ()
    #: An Automatic cage left unfitted because its group was hidden at build time; the
    #: draw asks for a rebuild once the group shows again (see _group_cage_hidden).
    deferred_hidden: bool = False
    fill_batches: list[object | None] = field(default_factory=list)
    lit_fill_batches: list[object | None] = field(default_factory=list)
    paint_fill_batches: list[object | None] = field(default_factory=list)
    line_batches: list[object | None] = field(default_factory=list)
    line_paint_batches: list[object | None] = field(default_factory=list)


def resolve_preview_target_group(project, group_name: str, group_index: int):
    """Re-resolve a cached preview target against the live project.

    Returns None when the name no longer resolves (the group was deleted, renamed, or
    its collection was rebuilt by an undo), so the caller skips the entry instead of
    drawing from a pointer that may already be freed.
    """
    if not group_name:
        return None
    groups = getattr(project, "groups", None)
    if groups is None:
        return None
    try:
        group_count = len(groups)
    except TypeError:
        group_count = 0
    index = int(group_index)
    if 0 <= index < group_count:
        candidate = groups[index]
        if str(getattr(candidate, "name", "") or "") == group_name:
            return candidate
    getter = getattr(groups, "get", None)
    if callable(getter):
        return getter(group_name)
    for candidate in groups:
        if str(getattr(candidate, "name", "") or "") == group_name:
            return candidate
    return None


@dataclass(slots=True)
class StaticOverlayCacheEntry:
    key: tuple | None = None
    high_hit_triangles: list[cage.TriangleData] = field(default_factory=list)
    high_hit_bvh: object | None = None
    high_passes: list[OverlayPass] = field(default_factory=list)
    low_passes: list[tuple[object, OverlayPass]] = field(default_factory=list)
    low_depth_batches: list[object] = field(default_factory=list)
    low_depth_epsilon: float = _DEFAULT_LOW_DEPTH_EPSILON
    low_triangle_sets: list[list[cage.TriangleData]] = field(default_factory=list)
    auto_cage_source_sets: list[list[cage.TriangleData]] = field(default_factory=list)
    auto_projection_source_sets: list[list[cage.TriangleData]] = field(default_factory=list)
    # Low triangles carrying the exporter's corner normals, one list per low slot, in
    # the same loop-triangle order as the cage captures. Only the skew needles read
    # these; see cage.capture_projection_ray_triangles for why they are separate.
    skew_ray_triangle_sets: list[list[cage.TriangleData]] = field(default_factory=list)
    #: True once the ray sets were captured, even when the capture found nothing (a
    #: group with no valid low slots), so the slot walk is not redone on every call.
    skew_rays_captured: bool = False
    auto_cage_fill_batches: list[object] = field(default_factory=list)
    auto_cage_lit_fill_batches: list[object | None] = field(default_factory=list)
    auto_cage_fill_paint_batches: list[object | None] = field(default_factory=list)
    auto_cage_line_batches: list[object | None] = field(default_factory=list)
    auto_cage_line_paint_batches: list[object | None] = field(default_factory=list)
    auto_cage_skew_batches: list[object | None] = field(default_factory=list)
    custom_cage_triangles: list[cage.TriangleData] | None = None
    custom_cage_skew_batch: object | None = None
    custom_cage_fill_batch: object | None = None
    custom_cage_line_batch: object | None = None
    paint_control_batches: list[object | None] = field(default_factory=list)
    preview_cage_targets: list[PreviewTargetCageCacheEntry] = field(default_factory=list)
    # True once the skew/ray debug source geometry (low_triangle_sets / distance
    # source sets) has been captured for this entry — either during the build
    # (debug toggle already on) or lazily via ensure_static_debug_geometry.
    debug_geometry_ready: bool = False
    # (signature, passes): skew field generation is ~1s on a dense group, so the
    # built passes are cached here and reused across display rebuilds while the
    # inputs (ray length, paint image + version) are unchanged.
    skew_pass_cache: tuple | None = None


@dataclass(slots=True)
class DistanceAverageNormalsPreviewSlotBuildInput:
    fill_buffers: cage.OffsetBatchBuffers
    line_buffers: cage.OffsetBatchBuffers | None = None
    #: Per-slot preview key (see overlay_keys.distance_average_normals_preview_slot_key):
    #: exactly the inputs the subdivided geometry depends on. The finished slot is
    #: filed under it, so unrelated static-key churn (high meshes, colours, other
    #: groups) no longer throws away a multi-GB subdivision.
    key: tuple | None = None


#: Returned by _preview_slot_line_batch when the slot carries no subdivided lines.
_NO_PREVIEW_LINE = object()


def _distance_preview_slot_key(
    context,
    obj,
    static_key,
    *,
    cage_mode: str,
    smooth_normals: bool,
    uv_layer_name: str | None,
    lines_enabled: bool,
) -> tuple:
    try:
        from .overlay_keys import distance_average_normals_preview_slot_key

        return distance_average_normals_preview_slot_key(
            context,
            obj,
            cage_mode=cage_mode,
            smooth_normals=smooth_normals,
            uv_layer_name=uv_layer_name,
            lines_enabled=lines_enabled,
        )
    except Exception:
        # A host that cannot sign the object (test doubles): tie the slot to the
        # whole static key, which is never narrower than the pre-slot-key behaviour.
        try:
            identity = int(obj.as_pointer())
        except Exception:
            identity = id(obj)
        return (
            "distance_average_normals_preview_static_fallback",
            static_key,
            identity,
            str(cage_mode or ""),
            bool(smooth_normals),
            str(uv_layer_name or ""),
            bool(lines_enabled),
        )


def _distance_preview_slot_lookup(cache_entry) -> dict:
    if cache_entry is None:
        return {}
    keys = tuple(getattr(cache_entry, "key", None) or ())
    slots = list(getattr(cache_entry, "slots", None) or ())
    if len(keys) != len(slots):
        return {}
    return dict(zip(keys, slots))


def _buffers_carry_paint(buffers) -> bool:
    count = len(getattr(buffers, "positions", ()) or ()) // 3
    return (
        bool(count)
        and len(getattr(buffers, "paints", ()) or ()) == count
        and len(getattr(buffers, "uvs", ()) or ()) == count * 2
    )


def _preview_slot_fill_batch(deps, preview_slot):
    """The slot's fill batch, uploaded once; the CPU buffers are released after.

    A painted group's slot carries UVs and paint multipliers too: its one batch then
    feeds the paint shader, and the plain offset/depth shaders ignore the extra
    attributes."""
    if not preview_slot.fill_batch_ready:
        fill_buffers = preview_slot.fill_buffers
        painted = fill_buffers is not None and _buffers_carry_paint(fill_buffers)
        if fill_buffers is None:
            preview_slot.fill_batch = None
        elif painted:
            preview_slot.fill_batch = deps.build_paint_offset_batch(fill_buffers)
        else:
            preview_slot.fill_batch = deps.build_offset_batch(fill_buffers)
        preview_slot.fill_has_paint = painted and preview_slot.fill_batch is not None
        preview_slot.fill_buffers = None
        preview_slot.fill_batch_ready = True
    return preview_slot.fill_batch


def _preview_slot_line_batch(deps, preview_slot):
    """The slot's LINES batch, uploaded once, or _NO_PREVIEW_LINE when it has none."""
    if not preview_slot.line_batch_ready:
        line_buffers = preview_slot.line_buffers
        if line_buffers is None:
            return _NO_PREVIEW_LINE
        painted = _buffers_carry_paint(line_buffers)
        if painted:
            preview_slot.line_batch = deps.build_paint_offset_batch(line_buffers, primitive_type="LINES")
        else:
            preview_slot.line_batch = deps.build_offset_batch(line_buffers, primitive_type="LINES")
        preview_slot.line_has_paint = painted and preview_slot.line_batch is not None
        preview_slot.line_buffers = None
        preview_slot.line_batch_ready = True
    return preview_slot.line_batch


def _slot_buffers(buffers, painted: bool):
    """Positions + normals for the subdivision worker, plus UVs and paint multipliers
    only for a painted group (an unpainted slot never draws through the paint shader)."""
    if buffers is None or painted:
        return buffers
    return cage.OffsetBatchBuffers(positions=buffers.positions, normals=buffers.normals)


class _DistancePreviewSlotTracker:
    """Resolves Distance + Average Normals preview slots by their own narrow key.

    Every slot the build wants is recorded in order; slots missing from the cache are
    requested once (the active group and a preview target that share a low mesh share
    one slot). ``finish`` enqueues the missing ones under the full wanted key, or, when
    nothing is missing, prunes cached slots the build no longer draws.
    """

    __slots__ = ("cache_entry", "lookup", "wanted", "requests")

    def __init__(self, cache_entry):
        self.cache_entry = cache_entry
        self.lookup = _distance_preview_slot_lookup(cache_entry)
        self.wanted: dict[tuple, None] = {}
        self.requests: dict[tuple, DistanceAverageNormalsPreviewSlotBuildInput] = {}

    def slot(self, slot_key):
        if slot_key is None:
            return None
        self.wanted[slot_key] = None
        preview_slot = self.lookup.get(slot_key)
        if preview_slot is None or getattr(preview_slot, "failed", False):
            return None
        return preview_slot

    def request(self, slot_key, fill_buffers, line_buffers) -> None:
        if slot_key is None or slot_key in self.lookup or slot_key in self.requests:
            return
        self.requests[slot_key] = DistanceAverageNormalsPreviewSlotBuildInput(
            fill_buffers=fill_buffers,
            line_buffers=line_buffers,
            key=slot_key,
        )

    def finish(self, deps) -> None:
        wanted_key = tuple(self.wanted)
        if self.requests:
            deps.enqueue_distance_average_normals_preview_build(wanted_key, list(self.requests.values()))
            return
        cache_entry = self.cache_entry
        if cache_entry is None or tuple(getattr(cache_entry, "key", None) or ()) == wanted_key:
            return
        # Nothing missing, but the cache still holds slots (GPU batches or not-yet-
        # uploaded buffers) that no build draws any more: release them.
        try:
            cache_entry.key = wanted_key
            cache_entry.slots = [self.lookup[slot_key] for slot_key in wanted_key]
        except Exception:
            pass


@dataclass(slots=True)
class OverlayCacheBuilderDeps:
    overlay_theme_for_settings: Callable[[object], object]
    effective_static_debug_flags: Callable[[object], dict[str, bool]]
    line_render_enabled: Callable[[object, float], bool]
    build_batch: Callable[[str, object], object]
    build_offset_batch: Callable[..., object]
    build_lit_offset_batch: Callable[[cage.OffsetBatchBuffers], object | None]
    build_paint_offset_batch: Callable[..., object | None]
    estimate_low_depth_epsilon: Callable[[list[list[cage.TriangleData]]], float]
    iter_valid_meshes: Callable[[object], object]
    make_overlay_pass: Callable[..., OverlayPass]
    make_line_overlay_pass: Callable[..., OverlayPass]
    make_offset_overlay_pass: Callable[..., OverlayPass]
    make_lit_offset_overlay_pass: Callable[..., OverlayPass]
    make_paint_offset_overlay_pass: Callable[..., OverlayPass]
    make_offset_line_overlay_pass: Callable[..., OverlayPass]
    heatmap_overlay_passes_from_debug_result: Callable[..., list[OverlayPass]]
    use_screen_heatmap_overlay: Callable[..., bool]
    backend_debug_result_is_stale: Callable[..., bool]
    skew_overlay_pass_from_batch: Callable[..., OverlayPass | None]
    enqueue_auto_cage_preview_build: Callable[[object, tuple], None]
    enqueue_distance_average_normals_preview_build: Callable[[tuple, list[DistanceAverageNormalsPreviewSlotBuildInput]], None]


@dataclass(slots=True)
class OverlayCacheState:
    cache_dirty: bool = True
    overlay_cache: OverlayCacheEntry | None = None
    static_overlay_cache: StaticOverlayCacheEntry | None = None


def invalidate_overlay_cache_state(cache_state: OverlayCacheState, *, clear_static: bool = True) -> None:
    cache_state.cache_dirty = True
    cache_state.overlay_cache = None
    if clear_static:
        cache_state.static_overlay_cache = None


def get_static_overlay_cache(
    cache_state: OverlayCacheState,
    *,
    context,
    settings,
    project,
    group,
    static_key_fn: Callable[..., tuple],
    build_static_cache_fn: Callable[..., StaticOverlayCacheEntry],
    static_key: tuple | None = None,
) -> StaticOverlayCacheEntry:
    # The caller usually just computed this key; recomputing it costs a full walk of
    # every tracked group's role collections, which is not free on the draw path.
    key = static_key_fn(context, settings, project, group) if static_key is None else static_key
    if cache_state.static_overlay_cache is not None and cache_state.static_overlay_cache.key == key:
        return cache_state.static_overlay_cache
    cache_state.static_overlay_cache = build_static_cache_fn(context, settings, group, key)
    return cache_state.static_overlay_cache


def get_overlay_cache(
    cache_state: OverlayCacheState,
    *,
    context,
    settings,
    project,
    group,
    static_key_fn: Callable[..., tuple],
    display_key_fn: Callable[..., tuple],
    build_static_cache_fn: Callable[..., StaticOverlayCacheEntry],
    build_overlay_cache_fn: Callable[..., OverlayCacheEntry],
    post_load_overlay_grace_active_fn: Callable[[], bool],
    schedule_interaction_redraw_fn: Callable[[float], None],
    post_load_overlay_grace_until: float,
) -> OverlayCacheEntry:
    static_key = static_key_fn(context, settings, project, group)
    display_key = display_key_fn(context, settings, project, group, static_key)
    if not cache_state.cache_dirty and cache_state.overlay_cache is not None and cache_state.overlay_cache.key == display_key:
        return cache_state.overlay_cache
    if post_load_overlay_grace_active_fn():
        schedule_interaction_redraw_fn(max(0.05, post_load_overlay_grace_until - time.monotonic()))
        return OverlayCacheEntry(key=display_key)
    static_cache = get_static_overlay_cache(
        cache_state,
        context=context,
        settings=settings,
        project=project,
        group=group,
        static_key_fn=static_key_fn,
        build_static_cache_fn=build_static_cache_fn,
        static_key=static_key,
    )
    # Recomputed rather than reusing display_key above: the static build can move state
    # the display key reads (interaction window, paint session version).
    key = display_key_fn(context, settings, project, group, static_cache.key)
    cache_state.overlay_cache = build_overlay_cache_fn(context, settings, project, group, static_cache, key)
    cache_state.cache_dirty = False
    return cache_state.overlay_cache


#: Finished GPU batches of each Automatic-cage preview target, keyed by its fit key. The
#: static overlay key changes with the ACTIVE group, so every group switch rebuilt every
#: target's cage; and with more targets than cage._AUTO_CAGE_FIT_MAX the fit memo evicted
#: in a loop and each switch refit them all (30 groups: ~0.4 s per switch, 2026-10-27).
#: Replaced wholesale by each build, so it never holds more than the current target set.
_AUTO_PREVIEW_TARGET_BATCHES: dict = {}


#: Flat (pre-subdivision) capture of each Distance preview slot, by its narrow slot key:
#: the source buffers plus whichever fallback batches a build made from them. The slot
#: key already ignores the active group, but every rebuild re-captured every slot's
#: triangles and edges anyway (30 groups: ~65 ms per group switch). Replaced wholesale
#: by each build, like _AUTO_PREVIEW_TARGET_BATCHES.
_DISTANCE_FLAT_SLOTS: dict = {}


def clear_preview_target_batches() -> None:
    _AUTO_PREVIEW_TARGET_BATCHES.clear()
    _DISTANCE_FLAT_SLOTS.clear()


def _field_solve_scope(function):
    """cage.field_solve_scope (one Smooth Cage solve per rebuild); a plain pass-through when the cage
    module is a stand-in without it."""
    scope = getattr(cage, "field_solve_scope", None)
    return scope(function) if scope is not None else function


def _memo(entry: dict, name: str, build):
    if name not in entry:
        entry[name] = build()
    return entry[name]


@_field_solve_scope
def build_static_overlay_cache(
    *,
    context,
    settings,
    group,
    key,
    auto_cage_preview_cache,
    distance_average_normals_preview_cache,
    deps: OverlayCacheBuilderDeps,
) -> StaticOverlayCacheEntry:
    depsgraph = context.evaluated_depsgraph_get()
    theme = deps.overlay_theme_for_settings(settings)
    group_uv_layer_name = _group_bake_uv_layer_name(group)
    role_state = _group_role_assignments_state(group)
    static_debug_flags = deps.effective_static_debug_flags(settings)
    heatmap_enabled = False
    heatmap_geometry_enabled = heatmap_enabled
    overlay_state = _overlay_settings_state(settings)
    cage_check_shell_enabled = False
    need_low_reference = static_debug_flags["show_low_reference"]
    need_high_reference = static_debug_flags["show_high_reference"]
    need_skew_debug = static_debug_flags["show_skew_debug"]
    need_ray_miss_debug = False
    high_hit_triangles: list[cage.TriangleData] = []
    high_hit_bvh = None
    high_passes: list[OverlayPass] = []
    low_passes: list[tuple[object, OverlayPass]] = []
    low_depth_batches: list[object] = []
    low_triangle_sets: list[list[cage.TriangleData]] = []
    auto_cage_source_sets: list[list[cage.TriangleData]] = []
    auto_projection_source_sets: list[list[cage.TriangleData]] = []
    auto_cage_fill_batches: list[object] = []
    auto_cage_lit_fill_batches: list[object | None] = []
    auto_cage_fill_paint_batches: list[object | None] = []
    auto_cage_line_batches: list[object | None] = []
    auto_cage_line_paint_batches: list[object | None] = []
    auto_cage_skew_batches: list[object | None] = []
    custom_cage_triangles = None
    custom_cage_skew_batch = None
    custom_cage_fill_batch = None
    custom_cage_line_batch = None
    preview_cage_targets: list[PreviewTargetCageCacheEntry] = []
    # Every preview scope (active texture set / selected lows / all) resolves the
    # groups whose cages should be drawn, always including the active group, so the
    # overlay renders from these targets rather than the active group alone.
    resolved_preview_targets = cage_session.resolve_preview_targets(
        getattr(context, "scene", None), context=context, include_hidden=True
    )[3]
    active_distance_cache_needed = (
        group.cage_mode == constants.CAGE_MODE_DISTANCE
        and (not resolved_preview_targets or need_skew_debug)
    )

    if need_ray_miss_debug and high_hit_triangles:
        high_hit_bvh = cage.build_triangle_bvh(high_hit_triangles)

    if group.cage_mode == constants.CAGE_MODE_CUSTOM and group.custom_cage is not None:
        custom_cage_triangles = cage.capture_object_triangles(group.custom_cage, depsgraph)
        custom_cage_fill_batch = deps.build_offset_batch(
            cage.fitted_offset_batch_buffers_from_triangles(custom_cage_triangles)
        )
        if deps.line_render_enabled(theme.cage_line, theme.cage_line_width):
            custom_cage_line_batch = deps.build_batch(
                "LINES",
                cage.capture_object_edge_lines(
                    group.custom_cage,
                    depsgraph,
                    smooth_normals=bool(getattr(group, "average_normals", True)),
                ).positions,
            )
    elif group.cage_mode == constants.CAGE_MODE_AUTOMATIC:
        if auto_cage_preview_cache is not None and auto_cage_preview_cache.key == key and auto_cage_preview_cache.fitted_triangles:
            custom_cage_triangles = auto_cage_preview_cache.fitted_triangles
            custom_cage_fill_batch = deps.build_offset_batch(
                cage.fitted_offset_batch_buffers_from_triangles(custom_cage_triangles)
            )
            if deps.line_render_enabled(theme.cage_line, theme.cage_line_width):
                custom_cage_line_batch = deps.build_batch(
                    "LINES",
                    cage.draw_buffers_from_triangles(custom_cage_triangles, include_lines=True).line_positions,
                )
        # No worker enqueue here: the backend automatic-cage solver that worker
        # called (cage.backend_build_automatic_cage_triangles) no longer exists, so
        # every key change exported all low and high meshes to a temp dir only to
        # cache an empty result. The coverage fit below is the live path.

    distance_preview_slots = _DistancePreviewSlotTracker(distance_average_normals_preview_cache)

    for slot in _iter_valid_role_slots(group, "low_meshes"):
        obj = slot.object_ref
        low_triangles = None
        need_low_triangles = (
            need_low_reference
            or heatmap_geometry_enabled
            or cage_check_shell_enabled
            or (
                group.cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC)
                and need_skew_debug
            )
        )
        if need_low_triangles:
            low_triangles = cage.capture_cage_source_triangles(
                obj,
                depsgraph,
                smooth_normals=bool(getattr(group, "average_normals", True)),
                uv_layer_name=group_uv_layer_name,
                uv_layer_required=False,
            )
        if low_triangles is not None:
            low_triangle_sets.append(low_triangles)
            if heatmap_geometry_enabled or cage_check_shell_enabled:
                low_depth_batches.append(
                    deps.build_batch(
                        "TRIS",
                        cage.draw_buffers_from_triangles(
                            low_triangles,
                            include_lines=False,
                        ).fill_positions,
                    )
                )
            if need_low_reference:
                low_buffers = cage.draw_buffers_from_triangles(
                    low_triangles,
                    include_lines=deps.line_render_enabled(theme.low_line, theme.low_line_width),
                )
                low_passes.append((obj, deps.make_overlay_pass(low_buffers, theme.low_fill, theme.low_line, theme.low_line_width)))
        else:
            low_triangle_sets.append([])

        if active_distance_cache_needed:
            auto_cage_average_normals = cage.auto_cage_uses_average_normals(group)
            cage_lines_enabled = deps.line_render_enabled(theme.cage_line, theme.cage_line_width)
            # Keyed before the captures below, from the same inputs they read.
            preview_slot_key = (
                _distance_preview_slot_key(
                    context,
                    obj,
                    key,
                    cage_mode=group.cage_mode,
                    smooth_normals=auto_cage_average_normals,
                    uv_layer_name=group_uv_layer_name,
                    lines_enabled=cage_lines_enabled,
                )
                if auto_cage_average_normals
                else None
            )
            cage_source_triangles = cage.capture_cage_source_triangles(
                obj,
                depsgraph,
                smooth_normals=auto_cage_average_normals,
                uv_layer_name=group_uv_layer_name,
                uv_layer_required=False,
            )
            projection_source_triangles = cage_source_triangles
            average_normals = bool(getattr(group, "average_normals", True))
            if average_normals != auto_cage_average_normals:
                projection_source_triangles = cage.capture_cage_source_triangles(
                    obj,
                    depsgraph,
                    smooth_normals=average_normals,
                    uv_layer_name=group_uv_layer_name,
                    uv_layer_required=False,
                )
            auto_cage_source_sets.append(cage_source_triangles)
            auto_projection_source_sets.append(projection_source_triangles)
            cage_offset_buffers = cage.offset_batch_buffers_from_triangles(cage_source_triangles)
            preview_slot = distance_preview_slots.slot(preview_slot_key)
            fill_batch = (
                _preview_slot_fill_batch(deps, preview_slot)
                if preview_slot is not None
                else deps.build_offset_batch(cage_offset_buffers)
            )
            auto_cage_fill_batches.append(fill_batch)
            auto_cage_lit_fill_batches.append(fill_batch)
            auto_cage_fill_paint_batches.append(deps.build_paint_offset_batch(cage_offset_buffers))
            if cage_lines_enabled:
                edge_buffers = cage.capture_object_edge_lines(
                    obj,
                    depsgraph,
                    smooth_normals=auto_cage_average_normals,
                    with_uvs=True,
                    uv_layer_name=group_uv_layer_name,
                )
                line_batch = (
                    _preview_slot_line_batch(deps, preview_slot)
                    if preview_slot is not None
                    else _NO_PREVIEW_LINE
                )
                if line_batch is _NO_PREVIEW_LINE:
                    line_batch = deps.build_offset_batch(edge_buffers, primitive_type="LINES")
                auto_cage_line_batches.append(line_batch)
                auto_cage_line_paint_batches.append(deps.build_paint_offset_batch(edge_buffers, primitive_type="LINES"))
            else:
                edge_buffers = None
                auto_cage_line_batches.append(None)
                auto_cage_line_paint_batches.append(None)
            auto_cage_skew_batches.append(None)
            distance_preview_slots.request(preview_slot_key, cage_offset_buffers, edge_buffers)

    low_depth_epsilon = deps.estimate_low_depth_epsilon(low_triangle_sets)

    if need_high_reference:
        for slot in _iter_valid_role_slots(group, "high_meshes"):
            obj = slot.object_ref
            high_triangles = cage.capture_object_triangles(obj, depsgraph)
            if high_triangles:
                high_buffers = cage.draw_buffers_from_triangles(
                    high_triangles,
                    include_lines=deps.line_render_enabled(theme.high_line, theme.high_line_width),
                )
                high_passes.append(
                    deps.make_overlay_pass(high_buffers, theme.high_fill, theme.high_line, theme.high_line_width)
                )

    built_preview_batches: dict = {}
    built_distance_flat_slots: dict = {}
    if resolved_preview_targets:
        for preview_target in resolved_preview_targets:
            preview_group = preview_target.group
            preview_role_state = _group_role_assignments_state(preview_group)
            preview_uv_layer_name = _group_bake_uv_layer_name(preview_group)
            preview_mode = str(getattr(preview_group, "cage_mode", "") or "")
            preview_entry = PreviewTargetCageCacheEntry(
                group_name=str(getattr(preview_group, "name", "") or ""),
                group_index=int(preview_target.group_index),
                cage_mode=preview_mode,
                slot_indices=tuple(int(slot_index) for slot_index in preview_target.slot_indices),
            )
            if preview_mode == constants.CAGE_MODE_CUSTOM and getattr(preview_group, "custom_cage", None) is not None:
                preview_triangles = cage.capture_object_triangles(preview_group.custom_cage, depsgraph)
                preview_entry.fill_batches.append(
                    deps.build_offset_batch(cage.fitted_offset_batch_buffers_from_triangles(preview_triangles))
                )
                preview_low_triangles: list[cage.TriangleData] = []
                for slot_index in preview_entry.slot_indices:
                    if 0 <= slot_index < len(getattr(preview_role_state, "low_meshes", [])):
                        preview_obj = getattr(preview_role_state.low_meshes[slot_index], "object_ref", None)
                        if preview_obj is not None and getattr(preview_obj, "type", None) == "MESH":
                            captured_low_triangles = cage.capture_cage_source_triangles(
                                    preview_obj,
                                    depsgraph,
                                    smooth_normals=bool(getattr(preview_group, "average_normals", True)),
                                    uv_layer_name=preview_uv_layer_name,
                                    uv_layer_required=False,
                                )
                            if captured_low_triangles:
                                preview_low_triangles.extend(captured_low_triangles)
                preview_entry.paint_fill_batches.append(
                    deps.build_paint_offset_batch(
                        cage.paint_offset_batch_buffers_between_triangle_sets(
                            preview_low_triangles,
                            preview_triangles,
                        )
                    )
                )
                if deps.line_render_enabled(theme.cage_line, theme.cage_line_width):
                    preview_entry.line_batches.append(
                        deps.build_batch(
                            "LINES",
                            cage.capture_object_edge_lines(
                                preview_group.custom_cage,
                                depsgraph,
                                smooth_normals=bool(getattr(preview_group, "average_normals", True)),
                            ).positions,
                        )
                    )
                else:
                    preview_entry.line_batches.append(None)
            elif preview_mode == constants.CAGE_MODE_AUTOMATIC:
                smooth_normals = cage.auto_cage_uses_average_normals(preview_group)
                preview_match_by_isolation = bool(getattr(preview_group, "match_by_isolation", False))
                preview_low_objs = list(deps.iter_valid_meshes(preview_role_state.low_meshes))
                preview_high_objs = list(deps.iter_valid_meshes(_effective_high_mesh_slots(preview_group)))
                # Fitting (per-vertex nearest-surface query over the low mesh) and the high-mesh
                # BVH build are the whole automatic-cage cost (~1s+ for a dense group). Both are
                # pure waste on a cage-visibility toggle — the geometry is unchanged — so memoize
                # the fitted triangles by a geometry+transform signature. A toggle then only redoes
                # the cheap GPU batch upload below, keeping it instant.
                try:
                    from .overlay_keys import object_cache_signature as _object_cache_signature

                    preview_high_bvh_key = tuple(_object_cache_signature(obj) for obj in preview_high_objs)
                    preview_fit_key = (
                        tuple(_object_cache_signature(obj) for obj in preview_low_objs),
                        preview_high_bvh_key,
                        bool(smooth_normals),
                        int(cage._AUTO_CAGE_DILATION_ITERATIONS),
                        bool(preview_match_by_isolation),
                    )
                except Exception:
                    preview_high_bvh_key = None
                    preview_fit_key = None

                if preview_fit_key is not None:
                    # v6: cross-part reach clamp + Match By Isolation partitioning change the fit.
                    # The UV layer rides along: the fitted corners carry the paint batch's UVs.
                    preview_fit_key = preview_fit_key + ("coverage_v10", preview_uv_layer_name)

                def _build_preview_fitted(
                    fit_depsgraph=None,
                    low_objs=tuple(preview_low_objs),
                    high_objs=tuple(preview_high_objs),
                    smooth=smooth_normals,
                    isolate=preview_match_by_isolation,
                    draw_depsgraph=depsgraph,
                    refined_key=preview_fit_key,
                    refine=False,
                    uv_layer=preview_uv_layer_name,
                    plain_key=(preview_fit_key + ("plain",)) if preview_fit_key is not None else None,
                ):
                    # Runs a tick or more after this draw (auto_cage_fit_queue), so it takes the
                    # depsgraph current at fit time.
                    depsgraph = fit_depsgraph or draw_depsgraph
                    # Fit all of the group's low meshes together so no single low mesh balloons out to
                    # reach another mesh's high detail (e.g. lower teeth inflating up to the upper teeth).
                    low_tri_groups = []
                    for low_obj in low_objs:
                        source_triangles = cage.capture_cage_source_triangles(
                            low_obj, depsgraph, smooth_normals=smooth, uv_layer_name=uv_layer, uv_layer_required=False
                        )
                        if source_triangles:
                            low_tri_groups.append(source_triangles)
                    if not low_tri_groups:
                        return []
                    # The fit key already signs these objects' geometry, so one content hash
                    # (a full read of every high's positions) per key serves both stages.
                    content_key = _CONTENT_KEYS.get(refined_key)
                    if content_key is None:
                        content_key = cage_fit_store.content_key(
                            low_objs, high_objs, depsgraph, smooth_normals=smooth, match_by_isolation=isolate
                        )
                        if refined_key is not None and content_key is not None:
                            _CONTENT_KEYS[refined_key] = content_key
                            if len(_CONTENT_KEYS) > 1024:
                                _CONTENT_KEYS.pop(next(iter(_CONTENT_KEYS)))

                    def _plain():
                        # Reverse-mapped coverage fit: each low vertex reaches the farthest high
                        # detail bound to it. Cheap; shown first while the ray check runs.
                        high_source_data = []
                        high_object_names = []
                        for obj in high_objs:
                            captured = cage.capture_high_mesh_fit_source_data(obj, depsgraph)
                            if captured is not None:
                                high_source_data.append(captured)
                                high_object_names.append(str(getattr(obj, "name", "")))
                        if not high_source_data:
                            return None
                        diagnostics: dict = {}
                        offsets = cage.build_group_coverage_offsets(
                            low_tri_groups,
                            high_source_data,
                            high_object_names=high_object_names,
                            match_by_isolation=isolate,
                            diagnostics=diagnostics,
                        )
                        return offsets, diagnostics

                    stored = cage_fit_store.cached(content_key)
                    if stored is not None:
                        offsets = stored[0]
                    elif not refine:
                        plain = _plain()
                        if plain is None:
                            return []
                        _PLAIN_PREVIEW_FITS[refined_key] = (content_key, plain)
                        _PLAIN_OFFSETS_SEEN[refined_key] = plain[0]
                        while len(_PLAIN_OFFSETS_SEEN) > 512:
                            _PLAIN_OFFSETS_SEEN.pop(next(iter(_PLAIN_OFFSETS_SEEN)))
                        offsets = plain[0]
                    else:
                        # The ray reach check is most of a group's fit and touches no Blender
                        # data: only the plain fit and the high's BVHs are made here, the rays
                        # run on a worker thread (auto_cage_fit_queue.Deferred), and the
                        # viewport stays live. On a customer's 73-group gun the refinement froze
                        # Blender 60 times, 85 s in all, after every cage was on screen.
                        memo = _PLAIN_PREVIEW_FITS.pop(refined_key, None)
                        plain = memo[1] if memo is not None and memo[0] == content_key else _plain()
                        if plain is None:
                            return []
                        index = (
                            cage.get_or_build_fit_high_index(high_objs, depsgraph)
                            if cage.RAY_REACH_CHECK
                            else None
                        )

                        def _work(plain=plain, index=index):
                            offsets, diagnostics = dict(plain[0]), dict(plain[1])
                            if index:
                                triangles = [triangle for group in low_tri_groups for triangle in group]
                                raised = cage.raise_offsets_to_ray_reach(triangles, offsets, index, diagnostics=diagnostics)
                                if raised:
                                    diagnostics["ray_raised_vertices"] = (
                                        int(diagnostics.get("ray_raised_vertices", 0)) + raised
                                    )
                            return offsets, diagnostics

                        def _finish(fit):
                            cage_fit_store.put(content_key, fit)
                            offsets = fit[0]
                            plain_cage = cage.peek_auto_cage_fitted(plain_key)
                            seen = _PLAIN_OFFSETS_SEEN.get(refined_key)
                            if plain_cage is not None and seen is not None and seen == offsets:
                                # The ray check changed nothing (most groups): the plain cage IS
                                # the refined one, and handing back the same object lets the draw
                                # keep its batches instead of rebuilding them.
                                return plain_cage
                            fitted: list[cage.TriangleData] = []
                            for source_triangles in low_tri_groups:
                                fitted.extend(cage.offset_triangles_with_proximity_fit(source_triangles, offsets))
                            return fitted

                        if auto_cage_fit_queue.background():
                            return _finish(_work())
                        return auto_cage_fit_queue.Deferred(_work, _finish)
                    fitted: list[cage.TriangleData] = []
                    for source_triangles in low_tri_groups:
                        fitted.extend(cage.offset_triangles_with_proximity_fit(source_triangles, offsets))
                    if stored is not None and not refine and refined_key is not None:
                        # The stored fit IS the refined one: hand it to the refined slot too, and
                        # drop the refinement the first draw queued (the fitted-cage memo holds 12
                        # groups, so on a reopened 73-group gun the refined slot was evicted
                        # before its tick and every group was built a second time).
                        cage.get_or_build_auto_cage_fitted(refined_key, lambda: fitted)
                        _STORED_FINAL[refined_key] = True
                        while len(_STORED_FINAL) > 1024:
                            _STORED_FINAL.pop(next(iter(_STORED_FINAL)))
                        auto_cage_fit_queue.cancel(refined_key, auto_cage_fit_queue.STAGE_REFINE)
                    return fitted

                preview_lines_wanted = bool(deps.line_render_enabled(theme.cage_line, theme.cage_line_width))
                # Two stages (auto_cage_fit_queue): the refined cage once it is fitted, the
                # plain fit until then, so every group shows within seconds.
                plain_fit_key = preview_fit_key + ("plain",) if preview_fit_key is not None else None
                preview_batch_key = (
                    (preview_fit_key, preview_uv_layer_name, preview_lines_wanted)
                    if preview_fit_key is not None
                    else None
                )
                reused_batches = (
                    _AUTO_PREVIEW_TARGET_BATCHES.get(preview_batch_key) if preview_batch_key is not None else None
                )
                refined_triangles = None
                fit_request_key = preview_fit_key
                if (
                    reused_batches is None
                    and preview_fit_key is not None
                    and not _group_cage_hidden(preview_group)
                ):
                    refined_triangles = cage.peek_auto_cage_fitted(preview_fit_key)
                    if refined_triangles is None and preview_fit_key in _STORED_FINAL:
                        # The plain stage drew the stored, already refined fit: nothing to refine.
                        fit_request_key = plain_fit_key
                        preview_batch_key = (plain_fit_key, preview_uv_layer_name, preview_lines_wanted)
                        reused_batches = _AUTO_PREVIEW_TARGET_BATCHES.get(preview_batch_key)
                    elif refined_triangles is None and not auto_cage_fit_queue.has_failed(preview_fit_key):
                        # Queue the refinement (behind every plain fit) and show the plain fit.
                        auto_cage_fit_queue.fitted_or_request(
                            preview_fit_key,
                            lambda fit_depsgraph=None, _build=_build_preview_fitted: _build(fit_depsgraph, refine=True),
                            stage=auto_cage_fit_queue.STAGE_REFINE,
                        )
                        fit_request_key = plain_fit_key
                        preview_batch_key = (plain_fit_key, preview_uv_layer_name, preview_lines_wanted)
                        reused_batches = _AUTO_PREVIEW_TARGET_BATCHES.get(preview_batch_key)
                if refined_triangles is not None and refined_triangles is cage.peek_auto_cage_fitted(plain_fit_key):
                    # Refined to the very same cage: keep drawing the plain batches.
                    plain_batches = _AUTO_PREVIEW_TARGET_BATCHES.get((plain_fit_key, preview_uv_layer_name, preview_lines_wanted))
                    if plain_batches is not None:
                        reused_batches = plain_batches
                        refined_triangles = None
                if refined_triangles is not None:
                    preview_fitted_triangles = refined_triangles
                elif reused_batches is not None:
                    preview_entry.fill_batches = list(reused_batches[0])
                    preview_entry.paint_fill_batches = list(reused_batches[1])
                    preview_entry.line_batches = list(reused_batches[2])
                    preview_fitted_triangles = None
                elif _group_cage_hidden(preview_group):
                    # Nothing to show, so nothing to fit: a hidden group (cage eye off, or its
                    # lows hidden with H) used to be fitted anyway, which on a customer's
                    # 73-group gun meant ~3 minutes of fitting cages nobody could see.
                    preview_entry.deferred_hidden = True
                    preview_fitted_triangles = []
                else:
                    # None while the fit is queued: this group's cage appears when it lands.
                    # The active group goes first, so the cage being looked at shows soonest.
                    preview_fitted_triangles = (
                        auto_cage_fit_queue.fitted_or_request(
                            fit_request_key,
                            _build_preview_fitted,
                            front=preview_group == group,
                        )
                        or []
                    )
                if preview_fitted_triangles:
                    # Draw the surface the bake traces (cage.bake_surface_triangles), not the
                    # flat fitted mesh the high detail pokes through on convex patches.
                    # numpy builders (same buffers to float32 rounding): the per-corner
                    # Python loops were most of every cage reload on a 73-group gun.
                    preview_entry.fill_batches.append(
                        deps.build_offset_batch(cage.bake_surface_fill_buffers(preview_fitted_triangles))
                    )
                    # The fitted corners keep their low source, UVs and paint values, so the
                    # low mesh is not captured a second time for the paint batch.
                    preview_entry.paint_fill_batches.append(
                        deps.build_paint_offset_batch(cage.paint_offset_batch_buffers_from_cage(preview_fitted_triangles))
                    )
                    if deps.line_render_enabled(theme.cage_line, theme.cage_line_width):
                        # Offset-shader line batch (zero displacement): same colour handling
                        # and cage depth bias as the Distance wireframe. The builtin
                        # UNIFORM_COLOR path drew these lines brighter and let them lose the
                        # depth test against the high they hug.
                        real_edges: set = set()
                        for preview_obj in preview_low_objs:
                            real_edges |= _mesh_edge_keys_cached(preview_obj, depsgraph)
                        edge_positions = cage.bake_surface_edge_lines_numpy(
                            preview_fitted_triangles, allowed_edges=real_edges or None
                        )
                        preview_entry.line_batches.append(
                            deps.build_offset_batch(
                                cage.OffsetBatchBuffers(
                                    positions=edge_positions,
                                    normals=array("f", bytes(len(edge_positions) * 4)),
                                ),
                                primitive_type="LINES",
                            )
                        )
                    else:
                        preview_entry.line_batches.append(None)
                if preview_batch_key is not None and preview_entry.fill_batches:
                    built_preview_batches[preview_batch_key] = (
                        tuple(preview_entry.fill_batches),
                        tuple(preview_entry.paint_fill_batches),
                        tuple(preview_entry.line_batches),
                    )
            elif preview_mode == constants.CAGE_MODE_DISTANCE:
                for slot_index in preview_target.slot_indices:
                    if slot_index < 0 or slot_index >= len(getattr(preview_role_state, "low_meshes", [])):
                        continue
                    preview_slot = getattr(preview_role_state, "low_meshes", [])[slot_index]
                    preview_obj = getattr(preview_slot, "object_ref", None)
                    if preview_obj is None or getattr(preview_obj, "type", None) != "MESH":
                        continue
                    auto_cage_average_normals = cage.auto_cage_uses_average_normals(preview_group)
                    preview_lines_enabled = deps.line_render_enabled(theme.cage_line, theme.cage_line_width)
                    # A painted group's dense cage carries its UVs and paint multipliers,
                    # so the painted cage and its coverage match the bake exactly like the
                    # unpainted one; an unpainted slot stays positions + normals only.
                    preview_slot_painted = bool(
                        _group_offset_layer_mode(preview_group)
                        or getattr(_group_paint_projection_settings_state(preview_group), "paint_offset_image", None) is not None
                    )
                    preview_slot_key = (
                        _distance_preview_slot_key(
                            context,
                            preview_obj,
                            key,
                            cage_mode=preview_mode,
                            smooth_normals=auto_cage_average_normals,
                            uv_layer_name=preview_uv_layer_name,
                            lines_enabled=preview_lines_enabled,
                        )
                    )
                    # Smooth Cage on or off, the drawn cage is the bake's: subdivided
                    # where the corner normals differ (the split, bridged normals with
                    # Smooth Cage off), exact flat triangles elsewhere.
                    if preview_slot_key is not None and preview_slot_painted:
                        preview_slot_key = (preview_slot_key, "painted")
                    # The flat capture depends only on what the slot key signs (object
                    # revision, smooth flag, UV layer, lines), so a key seen by the last
                    # build reuses its buffers and fallback batches.
                    if preview_slot_key is not None:
                        flat = _DISTANCE_FLAT_SLOTS.get(preview_slot_key)
                        if flat is None:
                            flat = built_distance_flat_slots.get(preview_slot_key, {})
                        built_distance_flat_slots[preview_slot_key] = flat
                    else:
                        flat = {}
                    preview_cage_offset_buffers = _memo(
                        flat,
                        "fill_buffers",
                        lambda: cage.capture_cage_offset_buffers(
                            preview_obj,
                            depsgraph,
                            smooth_normals=auto_cage_average_normals,
                            uv_layer_name=preview_uv_layer_name,
                            uv_layer_required=False,
                        ),
                    )
                    preview_slot_cache = distance_preview_slots.slot(preview_slot_key)
                    preview_fill_batch = (
                        _preview_slot_fill_batch(deps, preview_slot_cache)
                        if preview_slot_cache is not None
                        else _memo(flat, "fill_batch", lambda: deps.build_offset_batch(preview_cage_offset_buffers))
                    )
                    preview_entry.fill_batches.append(preview_fill_batch)
                    preview_entry.lit_fill_batches.append(preview_fill_batch)
                    if preview_slot_cache is not None and getattr(preview_slot_cache, "fill_has_paint", False):
                        preview_entry.paint_fill_batches.append(preview_fill_batch)
                    else:
                        # Until the dense slot lands (or without Smooth Cage), the flat cage.
                        preview_entry.paint_fill_batches.append(
                            _memo(flat, "paint_fill_batch", lambda: deps.build_paint_offset_batch(preview_cage_offset_buffers))
                        )
                    if preview_lines_enabled:
                        preview_edge_buffers = _memo(
                            flat,
                            "edge_buffers",
                            lambda: cage.capture_object_edge_lines(
                                preview_obj,
                                depsgraph,
                                smooth_normals=auto_cage_average_normals,
                                with_uvs=True,
                                uv_layer_name=preview_uv_layer_name,
                            ),
                        )
                        preview_line_batch = (
                            _preview_slot_line_batch(deps, preview_slot_cache)
                            if preview_slot_cache is not None
                            else _NO_PREVIEW_LINE
                        )
                        if preview_line_batch is _NO_PREVIEW_LINE:
                            preview_line_batch = _memo(
                                flat,
                                "line_batch",
                                lambda: deps.build_offset_batch(preview_edge_buffers, primitive_type="LINES"),
                            )
                        preview_entry.line_batches.append(preview_line_batch)
                        if preview_slot_cache is not None and getattr(preview_slot_cache, "line_has_paint", False):
                            preview_entry.line_paint_batches.append(preview_line_batch)
                        else:
                            preview_entry.line_paint_batches.append(
                                _memo(
                                    flat,
                                    "line_paint_batch",
                                    lambda: deps.build_paint_offset_batch(preview_edge_buffers, primitive_type="LINES"),
                                )
                            )
                    else:
                        preview_edge_buffers = None
                        preview_entry.line_batches.append(None)
                        preview_entry.line_paint_batches.append(None)
                    distance_preview_slots.request(
                        preview_slot_key,
                        _slot_buffers(preview_cage_offset_buffers, preview_slot_painted),
                        _slot_buffers(preview_edge_buffers, preview_slot_painted),
                    )
            if (
                preview_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC)
                and not preview_entry.lit_fill_batches
            ):
                preview_entry.lit_fill_batches = [None] * len(preview_entry.fill_batches)
                if not preview_entry.paint_fill_batches:
                    preview_entry.paint_fill_batches = [None] * len(preview_entry.fill_batches)
                if not preview_entry.line_paint_batches:
                    preview_entry.line_paint_batches = [None] * len(preview_entry.fill_batches)
            preview_cage_targets.append(preview_entry)

    distance_preview_slots.finish(deps)
    _AUTO_PREVIEW_TARGET_BATCHES.clear()
    _AUTO_PREVIEW_TARGET_BATCHES.update(built_preview_batches)
    _DISTANCE_FLAT_SLOTS.clear()
    _DISTANCE_FLAT_SLOTS.update(built_distance_flat_slots)

    return StaticOverlayCacheEntry(
        key=key,
        high_hit_triangles=high_hit_triangles,
        high_hit_bvh=high_hit_bvh,
        high_passes=high_passes,
        low_passes=low_passes,
        low_depth_batches=low_depth_batches,
        low_depth_epsilon=low_depth_epsilon,
        low_triangle_sets=low_triangle_sets,
        auto_cage_source_sets=auto_cage_source_sets,
        auto_projection_source_sets=auto_projection_source_sets,
        auto_cage_fill_batches=auto_cage_fill_batches,
        auto_cage_lit_fill_batches=auto_cage_lit_fill_batches,
        auto_cage_fill_paint_batches=auto_cage_fill_paint_batches,
        auto_cage_line_batches=auto_cage_line_batches,
        auto_cage_line_paint_batches=auto_cage_line_paint_batches,
        auto_cage_skew_batches=auto_cage_skew_batches,
        custom_cage_triangles=custom_cage_triangles,
        custom_cage_skew_batch=custom_cage_skew_batch,
        custom_cage_fill_batch=custom_cage_fill_batch,
        custom_cage_line_batch=custom_cage_line_batch,
        preview_cage_targets=preview_cage_targets,
        debug_geometry_ready=bool(need_skew_debug),
    )


def ensure_static_debug_geometry(static_cache, *, context, group) -> None:
    """Lazily capture the skew debug source geometry into an existing static
    cache entry. Debug toggles are display-only (they no longer key the static
    cache), so turning one ON for the first time fills the source triangles here
    instead of rebuilding every cage batch; turning it OFF keeps them resident so
    the next ON is instant."""
    # The static build captures the cage-side sources itself when the needles were
    # already on (debug_geometry_ready=True at construction), but never the ray sets,
    # so those are checked on their own.
    need_sources = not static_cache.debug_geometry_ready
    need_rays = not static_cache.skew_rays_captured
    if not need_sources and not need_rays:
        return
    try:
        depsgraph = context.evaluated_depsgraph_get()
    except Exception:
        return
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    group_uv_layer_name = _group_bake_uv_layer_name(group)
    if need_sources and cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC):
        smooth_normals = bool(getattr(group, "average_normals", True))
        triangle_sets: list[list[cage.TriangleData]] = []
        for slot in _iter_valid_role_slots(group, "low_meshes"):
            triangle_sets.append(
                cage.capture_cage_source_triangles(
                    slot.object_ref,
                    depsgraph,
                    smooth_normals=smooth_normals,
                    uv_layer_name=group_uv_layer_name,
                    uv_layer_required=False,
                )
                or []
            )
        static_cache.low_triangle_sets = triangle_sets
    elif need_sources and cage_mode == constants.CAGE_MODE_DISTANCE and not static_cache.auto_cage_source_sets:
        auto_cage_average_normals = cage.auto_cage_uses_average_normals(group)
        average_normals = bool(getattr(group, "average_normals", True))
        for slot in _iter_valid_role_slots(group, "low_meshes"):
            source_triangles = cage.capture_cage_source_triangles(
                slot.object_ref,
                depsgraph,
                smooth_normals=auto_cage_average_normals,
                uv_layer_name=group_uv_layer_name,
                uv_layer_required=False,
            )
            projection_triangles = source_triangles
            if average_normals != auto_cage_average_normals:
                projection_triangles = cage.capture_cage_source_triangles(
                    slot.object_ref,
                    depsgraph,
                    smooth_normals=average_normals,
                    uv_layer_name=group_uv_layer_name,
                    uv_layer_required=False,
                )
            static_cache.auto_cage_source_sets.append(source_triangles)
            static_cache.auto_projection_source_sets.append(projection_triangles)
            # Draw batches for these slots stay None: with preview targets active
            # (always, now that hidden groups are included) the cage itself draws
            # from preview_cage_targets; these sets only feed the skew/ray loops.
            static_cache.auto_cage_fill_batches.append(None)
            static_cache.auto_cage_lit_fill_batches.append(None)
            static_cache.auto_cage_fill_paint_batches.append(None)
            static_cache.auto_cage_line_batches.append(None)
            static_cache.auto_cage_line_paint_batches.append(None)
            static_cache.auto_cage_skew_batches.append(None)
    if need_rays:
        ray_sets: list[list[cage.TriangleData]] = []
        for slot in _iter_valid_role_slots(group, "low_meshes"):
            try:
                ray_sets.append(
                    cage.capture_projection_ray_triangles(
                        slot.object_ref,
                        depsgraph,
                        uv_layer_name=group_uv_layer_name,
                        uv_layer_required=False,
                        smooth_normals=bool(getattr(group, "average_normals", True)),
                    )
                    or []
                )
            except Exception:
                ray_sets.append([])
        static_cache.skew_ray_triangle_sets = ray_sets
        static_cache.skew_rays_captured = True
    static_cache.debug_geometry_ready = True


def _group_offset_layer_mode(group) -> bool:
    """Whether a low of *group* carries the brush's paint offset layer."""
    try:
        from .paint_sampling import OFFSET_ATTRIBUTE, has_paint_layer
    except ImportError:
        return False
    for slot in getattr(group, "low_meshes", []) or []:
        mesh = getattr(getattr(slot, "object_ref", None), "data", None)
        if mesh is not None and has_paint_layer(mesh, OFFSET_ATTRIBUTE):
            return True
    return False


def _group_skew_correction_tiles(group) -> dict:
    """The group's painted skew correction maps (paint_sampling.skew_correction_tiles), {} when none."""
    try:
        from .paint_sampling import skew_correction_tiles
    except ImportError:
        return {}
    try:
        return skew_correction_tiles(group) or {}
    except Exception:
        return {}


def _group_skew_correction_digest(group) -> str:
    """The painted skew correction maps' content, so an undo or a finished session that
    changes them regenerates the needles."""
    try:
        from .paint_sampling import skew_correction_digest
    except ImportError:
        return ""
    try:
        return skew_correction_digest(group)
    except Exception:
        return ""


def _group_offset_paint_texture(group, paint_state):
    """Canvas the paint-offset shader samples: white for a brush-painted group (the
    per-vertex layer multiplier carries the paint), the legacy image otherwise, or None
    when the group has no offset paint at all."""
    if _group_offset_layer_mode(group):
        from . import overlay_gpu, overlays

        try:
            return overlay_gpu.white_paint_texture(overlays._OVERLAY_GPU_STATE)
        except Exception:
            return None
    image = getattr(paint_state, "paint_offset_image", None)
    if image is None:
        return None
    try:
        return gpu.texture.from_image(image)
    except Exception:
        return None


def _paint_session_owns(group, kind: str) -> bool:
    try:
        from . import paint_brush

        return paint_brush.session_owns(group, kind)
    except Exception:
        return False


def _cached_skew_passes(
    static_cache,
    *,
    group,
    theme,
    deps,
    paint_state,
    skew_paint_version: int,
    allow_generate: bool = True,
) -> list[OverlayPass]:
    """Skew debug passes for the current static geometry, cached on the entry.

    Generating the skew direction field is CPU-heavy (~1s on a dense group), and
    build_overlay_cache re-runs on every display-key change (opacity drags, eye
    toggles, colors). Regenerate only when an actual skew input changes: ray
    length, the paint-skew image, or a paint stroke on it (skew_paint_version)."""
    paint_image = getattr(paint_state, "paint_skew_image", None)
    paint_pointer = 0
    if paint_image is not None:
        try:
            paint_pointer = int(paint_image.as_pointer())
        except Exception:
            paint_pointer = id(paint_image)
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    smooth_normals = bool(getattr(group, "average_normals", True))
    # Needles are generated at unit length; the live slider scales them on the GPU
    # (overlay_renderer skew_color branch), so length is not part of the signature.
    signature = (
        paint_pointer,
        int(skew_paint_version),
        cage_mode,
        smooth_normals,
        round(float(getattr(paint_state, "paint_skew", 0.0)), 4),
        _group_skew_correction_digest(group),
    )
    cached = static_cache.skew_pass_cache
    if cached is not None and cached[0] == signature:
        return cached[1]
    if not allow_generate:
        # Mid-interaction (a slider drag, a paint stroke): regenerating is ~1s on a
        # dense group, so keep showing whatever was last built rather than nothing.
        return cached[1] if cached is not None else []

    # Mirrors the backend ray setup (projection_ray_span): custom and automatic cages blend
    # from the projection normal toward the cage point by a legacy 1.0.x skew image; a
    # distance cage traces along the projection normal. Every mode then bends toward the
    # low face normal by the per-pixel Paint Skew correction (backend v18).
    skew_passes: list[OverlayPass] = []
    caged = cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC)
    cage_triangles = static_cache.custom_cage_triangles if caged else None
    correction_tiles = _group_skew_correction_tiles(group)
    for ray_triangles in static_cache.skew_ray_triangle_sets:
        if not ray_triangles:
            continue
        if cage_triangles is not None and len(ray_triangles) == len(cage_triangles):
            skew_buffers = cage.skew_direction_field_buffers_between_triangle_sets(
                ray_triangles,
                cage_triangles,
                max_segments=constants.VIEWPORT_SKEW_SEGMENT_BUDGET,
                max_triangle_resolution=constants.VIEWPORT_SKEW_MAX_TRIANGLE_RESOLUTION,
                line_length_scale=1.0,
                correction_strength=float(getattr(paint_state, "paint_skew", 0.0)),
                paint_image=paint_image,
                smooth_normals=smooth_normals,
                skew_correction_tiles=correction_tiles,
            )
        else:
            skew_buffers = cage.skew_direction_field_buffers_from_triangles(
                ray_triangles,
                max_segments=constants.VIEWPORT_SKEW_SEGMENT_BUDGET,
                max_triangle_resolution=constants.VIEWPORT_SKEW_MAX_TRIANGLE_RESOLUTION,
                line_length_scale=1.0,
                smooth_normals=smooth_normals,
                skew_correction_tiles=correction_tiles,
            )
        skew_pass = deps.skew_overlay_pass_from_batch(skew_buffers, theme)
        if skew_pass is not None:
            skew_passes.append(skew_pass)
    static_cache.skew_pass_cache = (signature, skew_passes)
    return skew_passes


@_field_solve_scope
def build_overlay_cache(
    *,
    context,
    settings,
    project,
    group,
    static_cache,
    key,
    interaction_active: bool,
    deps: OverlayCacheBuilderDeps,
    skew_paint_version: int = 0,
) -> OverlayCacheEntry:
    overlay_state = _overlay_settings_state(settings)
    theme = deps.overlay_theme_for_settings(settings)
    # The cage fill is a translucent overlay; letting it write depth makes a concave cage's
    # near surface occlude its own wireframe (and far fill) from most angles. Keeping it out
    # of the depth buffer lets the whole cage wireframe read through the fill, while real
    # scene geometry (via the solid pass depth) still occludes the cage as expected.
    cage_fill_depth_write = False
    heatmap_enabled = False
    mesh_enabled = False
    show_cage_surface = bool(getattr(overlay_state, "show_cage_surface", True))
    show_cage_wireframe = bool(getattr(overlay_state, "show_cage_wireframe", True))
    scene = getattr(bpy.context, "scene", None)
    _scene_settings, active_project, active_group = cage_session.resolve_project_group(scene) if scene is not None else (None, None, None)
    debug_result = (
        runtime.peek_debug_overlay_result(scene, active_project, active_group)
        if scene is not None and active_project is not None and active_group is not None
        else None
    )
    screen_heatmap_active = bool(heatmap_enabled and deps.use_screen_heatmap_overlay(context, debug_result))
    geometry_heatmap_active = bool(heatmap_enabled and debug_result is not None and not screen_heatmap_active)
    split_heatmap_active = bool(heatmap_enabled and mesh_enabled and debug_result is not None and not screen_heatmap_active)
    passes = []
    cage_fill_passes = []
    cage_line_passes = []
    paint_mask_passes = []
    miss_positions: list[tuple[float, float, float]] = []
    cage_depth_batches: list[tuple[object, float]] = []
    coverage_cage_passes: dict[str, list[OverlayPass]] = {}
    valid_low_slots = list(_iter_valid_role_slots(group, "low_meshes"))
    paint_state = _group_paint_projection_settings_state(group)
    active_object = getattr(context, "active_object", None)
    image_paint = getattr(getattr(getattr(context, "scene", None), "tool_settings", None), "image_paint", None)
    paint_canvas = getattr(image_paint, "canvas", None)
    active_paint_image = None
    if active_object is not None and getattr(active_object, "mode", "") == "TEXTURE_PAINT":
        for image_attr in ("paint_offset_image", "paint_skew_image"):
            candidate = getattr(paint_state, image_attr, None)
            if candidate is not None and paint_canvas is candidate:
                active_paint_image = candidate
                break
    if active_paint_image is not None:
        ensure_static_debug_geometry(static_cache, context=context, group=group)
        if not static_cache.paint_control_batches:
            source_sets = (
                static_cache.low_triangle_sets
                if str(getattr(group, "cage_mode", "") or "")
                in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC)
                else static_cache.auto_cage_source_sets
            )
            static_cache.paint_control_batches = [
                deps.build_paint_offset_batch(cage.offset_batch_buffers_from_triangles(triangles))
                for triangles in source_sets
                if triangles
            ]
        try:
            active_paint_texture = gpu.texture.from_image(active_paint_image)
        except Exception:
            active_paint_texture = None
        if active_paint_texture is not None:
            for paint_control_batch in static_cache.paint_control_batches:
                if paint_control_batch is None:
                    continue
                paint_mask_passes.append(
                    deps.make_paint_offset_overlay_pass(
                        paint_control_batch,
                        (1.0, 1.0, 1.0, 0.88),
                        0.0,
                        paint_texture=active_paint_texture,
                        uses_group_offset=False,
                        show_paint_mask=True,
                    )
                )
    if not interaction_active and bool(getattr(overlay_state, "show_skew_debug", False)):
        ensure_static_debug_geometry(static_cache, context=context, group=group)
    # When preview targets were resolved (every scope resolves at least the active
    # group), draw the cages from those targets and suppress the active group's own
    # cage pass below so it is not drawn twice. The static cache includes hidden
    # groups' batches on purpose; the eye toggles are applied here, at draw
    # assembly, so they never trigger a static rebuild.
    preview_targets_active = bool(static_cache.preview_cage_targets)
    # When the active group's cage overlay is hidden via the cage menu eye and it is
    # the only target, preview_cage_targets is empty; suppress the fallback below so
    # the hidden group's cage is not drawn anyway.
    draw_active_group_fallback = not preview_targets_active and not bool(getattr(group, "cage_overlay_hidden", False))

    # The static cache is undo-stable on purpose (an undo must not pay for a full cage
    # rebuild), so a cached target can outlive the group it was built from. Re-resolve
    # every entry by name against the live project here instead of caching the
    # PropertyGroup: a freed group dereferenced below would crash the draw callback.
    preview_project = project if project is not None else active_project
    if preview_targets_active:
        tag_fill_start = tag_line_start = 0
        tag_group_name = ""
        for preview_target in static_cache.preview_cage_targets:
            # Name the passes the previous target added (its body has several `continue`s).
            _tag_cage_group(cage_fill_passes, tag_fill_start, tag_group_name)
            _tag_cage_group(cage_line_passes, tag_line_start, tag_group_name)
            tag_fill_start, tag_line_start = len(cage_fill_passes), len(cage_line_passes)
            tag_group_name = str(preview_target.group_name or "")
            preview_group = resolve_preview_target_group(
                preview_project,
                preview_target.group_name,
                preview_target.group_index,
            )
            if preview_group is None:
                continue
            if _group_cage_hidden(preview_group):
                # Cage eye off, or every low hidden in the viewport (H): its cage goes too.
                continue
            if preview_target.deferred_hidden:
                # Shown again after a build that skipped it: fit it now.
                _request_static_rebuild()
                continue
            preview_paint_state = _group_paint_projection_settings_state(preview_group)
            preview_paint_texture = _group_offset_paint_texture(preview_group, preview_paint_state)
            if preview_target.cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC):
                painted_fitted_cage = bool(
                    preview_paint_texture is not None
                    and any(batch is not None for batch in preview_target.paint_fill_batches)
                )
                for batch_index, fill_batch in enumerate(preview_target.fill_batches):
                    if fill_batch is None:
                        continue
                    paint_batch = (
                        preview_target.paint_fill_batches[batch_index]
                        if batch_index < len(preview_target.paint_fill_batches)
                        else None
                    )
                    if preview_paint_texture is not None and paint_batch is not None:
                        cage_pass = _with_pass_kind(
                            deps.make_paint_offset_overlay_pass(
                                paint_batch,
                                theme.cage_fill,
                                1.0,
                                paint_texture=preview_paint_texture,
                                offset_group=preview_group,
                                uses_group_offset=False,
                                paint_offset_scale=float(
                                    getattr(preview_paint_state, "paint_offset_scale", 1.0)
                                ),
                            ),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    else:
                        cage_pass = _fitted_cage_fill_pass(
                            deps,
                            fill_batch,
                            theme.cage_fill,
                            depth_write=cage_fill_depth_write,
                        )
                    coverage_cage_passes.setdefault(preview_target.group_name, []).append(cage_pass)
                    if show_cage_surface:
                        cage_fill_passes.append(cage_pass)
                # The fitted-cage wire batch has no low-mesh UV/displacement
                # attributes.  Do not draw the original, unpainted wire over a
                # paint-deformed surface.
                if show_cage_wireframe and not painted_fitted_cage:
                    for line_batch in preview_target.line_batches:
                        if line_batch is None:
                            continue
                        line_pass = (
                            deps.make_offset_line_overlay_pass(
                                line_batch,
                                theme.cage_line,
                                theme.cage_line_width,
                                0.0,
                                uses_group_offset=False,
                                offset_group=preview_group,
                            )
                            if preview_target.cage_mode == constants.CAGE_MODE_AUTOMATIC
                            else deps.make_line_overlay_pass(
                                line_batch,
                                theme.cage_line,
                                theme.cage_line_width,
                            )
                        )
                        cage_line_passes.append(_with_pass_kind(line_pass, "cage_line"))
                continue

            preview_role_state = getattr(_group_role_assignments_state(preview_group), "low_meshes", [])
            for preview_slot_position, slot_index in enumerate(preview_target.slot_indices):
                slot_offset_delta = 0.0
                if 0 <= slot_index < len(preview_role_state):
                    slot_offset_delta = float(getattr(preview_role_state[slot_index], "cage_offset_delta", 0.0))
                fill_batch = (
                    preview_target.fill_batches[preview_slot_position]
                    if preview_slot_position < len(preview_target.fill_batches)
                    else None
                )
                # The degenerate-offset check (overlay_renderer) reads cage_depth_batches,
                # and a Distance cage draws from preview targets now, so the static
                # auto_cage_fill_batches entries for DISTANCE are all None by design. Without
                # this the batch list stayed empty, distance_degenerate_offset was never
                # computed, and the solid red warning for a ~zero cage offset could not draw
                # at all. Active group only: overlay_renderer pairs these deltas with the
                # ACTIVE group's cage_offset, so another group's slot would be measured
                # against the wrong base. `==` not `is`: RNA rebuilds the wrapper per access.
                if (
                    bool(getattr(overlay_state, "show_error_heatmap", False))
                    and fill_batch is not None
                    and group is not None
                    and preview_group == group
                ):
                    cage_depth_batches.append((fill_batch, slot_offset_delta))
                lit_fill_batch = (
                    preview_target.lit_fill_batches[preview_slot_position]
                    if preview_slot_position < len(preview_target.lit_fill_batches)
                    else None
                )
                paint_batch = (
                    preview_target.paint_fill_batches[preview_slot_position]
                    if preview_slot_position < len(preview_target.paint_fill_batches)
                    else None
                )
                line_batch = (
                    preview_target.line_batches[preview_slot_position]
                    if preview_slot_position < len(preview_target.line_batches)
                    else None
                )
                line_paint_batch = (
                    preview_target.line_paint_batches[preview_slot_position]
                    if preview_slot_position < len(preview_target.line_paint_batches)
                    else None
                )
                cage_pass = None
                if fill_batch is not None:
                    if preview_paint_texture is not None and paint_batch is not None:
                        cage_pass = _with_pass_kind(
                            deps.make_paint_offset_overlay_pass(
                                paint_batch,
                                theme.cage_fill,
                                slot_offset_delta,
                                paint_texture=preview_paint_texture,
                                offset_group=preview_group,
                                paint_offset_scale=float(
                                    getattr(preview_paint_state, "paint_offset_scale", 1.0)
                                ),
                            ),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    elif lit_fill_batch is not None and bool(getattr(preferences.get_preferences(), "cage_lit_shading", False)):
                        cage_pass = _with_pass_kind(
                            deps.make_lit_offset_overlay_pass(
                                lit_fill_batch,
                                theme.cage_fill,
                                slot_offset_delta,
                                offset_group=preview_group,
                            ),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    else:
                        cage_pass = _with_pass_kind(
                            deps.make_offset_overlay_pass(
                                fill_batch,
                                theme.cage_fill,
                                slot_offset_delta,
                                offset_group=preview_group,
                            ),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                if cage_pass is not None:
                    coverage_cage_passes.setdefault(preview_target.group_name, []).append(cage_pass)
                    if show_cage_surface:
                        cage_fill_passes.append(cage_pass)
                if show_cage_wireframe and line_batch is not None and preview_paint_texture is None:
                    cage_line_passes.append(
                        _with_pass_kind(
                            deps.make_offset_line_overlay_pass(
                                line_batch,
                                theme.cage_line,
                                theme.cage_line_width,
                                slot_offset_delta,
                                uses_group_offset=True,
                                offset_group=preview_group,
                            ),
                            "cage_line",
                        )
                    )
                elif show_cage_wireframe and line_paint_batch is not None and preview_paint_texture is not None:
                    # A painted cage's wire is its own cage_line pass, like the unpainted
                    # one: drawn inside the fill pass it sat under Cage Coverage (which
                    # draws between the fills and the wires) and vanished.
                    cage_line_passes.append(
                        _with_pass_kind(
                            deps.make_paint_offset_overlay_pass(
                                None,
                                theme.cage_fill,
                                slot_offset_delta,
                                paint_texture=preview_paint_texture,
                                line_batch=line_paint_batch,
                                line_color=theme.cage_line,
                                line_width=theme.cage_line_width,
                                offset_group=preview_group,
                                paint_offset_scale=float(
                                    getattr(preview_paint_state, "paint_offset_scale", 1.0)
                                ),
                            ),
                            "cage_line",
                        )
                    )
        _tag_cage_group(cage_fill_passes, tag_fill_start, tag_group_name)
        _tag_cage_group(cage_line_passes, tag_line_start, tag_group_name)

    if group.cage_mode in (constants.CAGE_MODE_CUSTOM, constants.CAGE_MODE_AUTOMATIC):
        if draw_active_group_fallback and show_cage_surface and static_cache.custom_cage_fill_batch is not None:
            cage_fill_passes.append(
                _fitted_cage_fill_pass(
                    deps,
                    static_cache.custom_cage_fill_batch,
                    theme.cage_fill,
                    depth_write=cage_fill_depth_write,
                )
            )
        if draw_active_group_fallback and show_cage_wireframe and static_cache.custom_cage_line_batch is not None:
            cage_line_passes.append(
                _with_pass_kind(
                    deps.make_line_overlay_pass(
                        static_cache.custom_cage_line_batch,
                        theme.cage_line,
                        theme.cage_line_width,
                    ),
                    "cage_line",
                )
            )
        # The editable grayscale control surface is geometrically beneath the cage.
        # Draw it first so the translucent cage and its wireframe remain readable
        # instead of the near-opaque white mask painting over both.
        passes.extend(paint_mask_passes)
        passes.extend(cage_fill_passes)
        if geometry_heatmap_active:
            passes.extend(
                deps.heatmap_overlay_passes_from_debug_result(
                    debug_result,
                    theme,
                    include_inside=split_heatmap_active,
                )
            )
        passes.extend(cage_line_passes)
        if bool(getattr(overlay_state, "show_skew_debug", False)) and not _paint_session_owns(group, "SKEW"):
            passes.extend(
                _cached_skew_passes(
                    static_cache,
                    group=group,
                    theme=theme,
                    deps=deps,
                    paint_state=_group_paint_projection_settings_state(group),
                    skew_paint_version=skew_paint_version,
                    allow_generate=not interaction_active,
                )
            )
        if bool(getattr(overlay_state, "show_ray_miss_debug", False)) and debug_result is not None:
            miss_positions.extend(tuple(item) for item in getattr(debug_result, "ray_miss_line_positions", []))
        return OverlayCacheEntry(
            key=key,
            passes=passes,
            low_depth_batches=static_cache.low_depth_batches if geometry_heatmap_active else [],
            coverage_cage_passes=coverage_cage_passes,
            low_depth_epsilon=static_cache.low_depth_epsilon,
            miss_batch=deps.build_batch("LINES", miss_positions),
        )

    for low_slot_index, (
        _source_triangles,
        projection_triangles,
        fill_batch,
        lit_fill_batch,
        paint_batch,
        line_batch,
        line_paint_batch,
        _skew_batch,
    ) in enumerate(
        zip(
            static_cache.auto_cage_source_sets,
            static_cache.auto_projection_source_sets,
            static_cache.auto_cage_fill_batches,
            static_cache.auto_cage_lit_fill_batches,
            static_cache.auto_cage_fill_paint_batches,
            static_cache.auto_cage_line_batches,
            static_cache.auto_cage_line_paint_batches,
            static_cache.auto_cage_skew_batches,
        )
    ):
        paint_state = _group_paint_projection_settings_state(group)
        slot_offset_delta = 0.0
        if low_slot_index < len(valid_low_slots):
            slot_offset_delta = float(getattr(valid_low_slots[low_slot_index], "cage_offset_delta", 0.0))
        total_offset = max(0.0, float(group.cage_offset) + slot_offset_delta)
        if (
            bool(getattr(overlay_state, "show_error_heatmap", False))
            and getattr(group, "cage_mode", "") == constants.CAGE_MODE_DISTANCE
            and fill_batch is not None
        ):
            cage_depth_batches.append((fill_batch, slot_offset_delta))
        paint_texture = _group_offset_paint_texture(group, paint_state) if paint_batch is not None else None
        if draw_active_group_fallback:
            if show_cage_surface:
                if paint_texture is not None:
                    cage_fill_passes.append(
                        _with_pass_kind(
                            deps.make_paint_offset_overlay_pass(
                                paint_batch,
                                theme.cage_fill,
                                slot_offset_delta,
                                paint_texture=paint_texture,
                                line_batch=line_paint_batch if show_cage_wireframe else None,
                                line_color=theme.cage_line,
                                line_width=theme.cage_line_width,
                                offset_group=group,
                                paint_offset_scale=float(getattr(paint_state, "paint_offset_scale", 1.0)),
                            ),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    )
                elif lit_fill_batch is not None and bool(getattr(preferences.get_preferences(), "cage_lit_shading", False)):
                    cage_fill_passes.append(
                        _with_pass_kind(
                            deps.make_lit_offset_overlay_pass(lit_fill_batch, theme.cage_fill, slot_offset_delta),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    )
                else:
                    cage_fill_passes.append(
                        _with_pass_kind(
                            deps.make_offset_overlay_pass(fill_batch, theme.cage_fill, slot_offset_delta),
                            "cage_fill",
                            depth_write=cage_fill_depth_write,
                        )
                    )
            if show_cage_wireframe and line_batch is not None and paint_texture is None:
                cage_line_passes.append(
                    _with_pass_kind(
                        deps.make_offset_line_overlay_pass(
                            line_batch,
                            theme.cage_line,
                            theme.cage_line_width,
                            slot_offset_delta,
                            uses_group_offset=True,
                        ),
                        "cage_line",
                    )
                )
    if bool(getattr(overlay_state, "show_skew_debug", False)) and not _paint_session_owns(group, "SKEW"):
        passes.extend(
            _cached_skew_passes(
                static_cache,
                group=group,
                theme=theme,
                deps=deps,
                paint_state=_group_paint_projection_settings_state(group),
                skew_paint_version=skew_paint_version,
                allow_generate=not interaction_active,
            )
        )
    # Keep Paint Offset feedback beneath the actual cage. Drawing the white/black
    # control mask last obscures the shell precisely where the artist needs to
    # judge the painted displacement.
    passes.extend(paint_mask_passes)
    passes.extend(cage_fill_passes)
    if geometry_heatmap_active:
        passes.extend(
            deps.heatmap_overlay_passes_from_debug_result(
                debug_result,
                theme,
                include_inside=split_heatmap_active,
            )
        )
    passes.extend(cage_line_passes)
    if bool(getattr(overlay_state, "show_ray_miss_debug", False)) and debug_result is not None:
        miss_positions.extend(tuple(item) for item in getattr(debug_result, "ray_miss_line_positions", []))

    return OverlayCacheEntry(
        key=key,
        passes=passes,
        low_depth_batches=static_cache.low_depth_batches if (geometry_heatmap_active or cage_depth_batches) else [],
        cage_depth_batches=cage_depth_batches,
        coverage_cage_passes=coverage_cage_passes,
        low_depth_epsilon=static_cache.low_depth_epsilon,
        miss_batch=deps.build_batch("LINES", miss_positions),
    )
