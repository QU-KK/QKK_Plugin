from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import traceback

import bpy

from . import cage, constants, export, naming, properties, runtime
from .overlay_keys import effective_high_mesh_slots as _effective_high_mesh_slots
from .overlay_cache import DistanceAverageNormalsPreviewSlotBuildInput


@dataclass(slots=True)
class AutoCagePreviewCacheEntry:
    key: tuple
    fitted_triangles: list[cage.TriangleData]


@dataclass(slots=True)
class AutoCagePreviewBuildRequest:
    generation: int
    key: tuple
    group: object


@dataclass(slots=True)
class AutoCagePreviewBuildResult:
    generation: int
    key: tuple
    fitted_triangles: list[cage.TriangleData]


@dataclass(slots=True)
class DistanceAverageNormalsPreviewSlotBuildResult:
    # Subdivided CPU buffers (flat float32 arrays). They exist only until the static
    # overlay build first uploads them: the GPU batch is then cached below and the
    # buffers are dropped, so a dense cage is held once in VRAM instead of also
    # sitting in host RAM for the rest of the session.
    fill_buffers: cage.OffsetBatchBuffers | None
    line_buffers: cage.OffsetBatchBuffers | None = None
    fill_batch: object | None = None
    line_batch: object | None = None
    fill_batch_ready: bool = False
    line_batch_ready: bool = False
    #: The uploaded batch carries UVs and paint multipliers (a painted group's slot).
    fill_has_paint: bool = False
    line_has_paint: bool = False
    #: The worker raised for this slot. Kept as a tombstone so the build shows the
    #: unsubdivided cage instead of re-enqueueing the same failing work forever.
    failed: bool = False


@dataclass(slots=True)
class DistanceAverageNormalsPreviewCacheEntry:
    #: One per-slot preview key per entry of ``slots`` (same order).
    key: tuple
    slots: list[DistanceAverageNormalsPreviewSlotBuildResult]


@dataclass(slots=True)
class DistanceAverageNormalsPreviewBuildRequest:
    generation: int
    key: tuple
    slots: list[DistanceAverageNormalsPreviewSlotBuildInput]


@dataclass(slots=True)
class DistanceAverageNormalsPreviewBuildResult:
    generation: int
    key: tuple
    slots: list[DistanceAverageNormalsPreviewSlotBuildResult]
    #: Per-slot keys of ``slots`` (same order); ``key`` is the full wanted set.
    slot_keys: tuple = ()


@dataclass(slots=True)
class OverlayPreviewBuildRuntimeState:
    auto_cage_preview_cache: AutoCagePreviewCacheEntry | None = None
    auto_cage_preview_pending_request: AutoCagePreviewBuildRequest | None = None
    auto_cage_preview_build_result_queue: "queue.Queue[AutoCagePreviewBuildResult]" = field(default_factory=queue.Queue)
    auto_cage_preview_build_thread: threading.Thread | None = None
    auto_cage_preview_build_active_key: tuple | None = None
    auto_cage_preview_build_timer_registered: bool = False
    auto_cage_preview_build_generation: int = 0
    distance_average_normals_preview_cache: DistanceAverageNormalsPreviewCacheEntry | None = None
    distance_average_normals_preview_pending_request: DistanceAverageNormalsPreviewBuildRequest | None = None
    distance_average_normals_preview_build_result_queue: "queue.Queue[DistanceAverageNormalsPreviewBuildResult]" = field(default_factory=queue.Queue)
    distance_average_normals_preview_build_thread: threading.Thread | None = None
    distance_average_normals_preview_build_active_key: tuple | None = None
    distance_average_normals_preview_build_timer_registered: bool = False
    distance_average_normals_preview_build_generation: int = 0


@dataclass(slots=True)
class OverlayPreviewBuildDeps:
    iter_valid_meshes: Callable[[object], object]
    post_load_overlay_grace_active: Callable[[], bool]
    post_load_overlay_grace_delay: Callable[[], float]
    invalidate_overlay_cache: Callable[[], None]
    tag_redraw_all_view3d: Callable[[], None]


def _auto_cage_preview_build_worker(
    generation: int,
    key: tuple,
    low_mesh_refs,
    high_mesh_refs,
    backend_exe,
    temp_dir: str,
    average_normals: bool,
    result_queue: "queue.Queue[AutoCagePreviewBuildResult]",
) -> None:
    try:
        fitted_triangles = cage.backend_build_automatic_cage_triangles(
            list(low_mesh_refs),
            list(high_mesh_refs),
            backend_exe,
            average_normals=average_normals,
        )
        result_queue.put(
            AutoCagePreviewBuildResult(
                generation=generation,
                key=key,
                fitted_triangles=fitted_triangles,
            )
        )
    except Exception:
        traceback.print_exc()
        result_queue.put(
            AutoCagePreviewBuildResult(
                generation=generation,
                key=key,
                fitted_triangles=[],
            )
        )
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


def distance_average_normals_preview_slot_keys(
    key: tuple,
    slots: list[DistanceAverageNormalsPreviewSlotBuildInput],
) -> tuple:
    """Per-slot keys for a request; a slot built without one falls back to its position."""
    return tuple(
        slot.key if getattr(slot, "key", None) is not None else (key, "slot", index)
        for index, slot in enumerate(slots)
    )


def _distance_average_normals_preview_build_worker(
    generation: int,
    key: tuple,
    slots: list[DistanceAverageNormalsPreviewSlotBuildInput],
    result_queue: "queue.Queue[DistanceAverageNormalsPreviewBuildResult]",
) -> None:
    slot_keys = distance_average_normals_preview_slot_keys(key, slots)
    try:
        slot_results: list[DistanceAverageNormalsPreviewSlotBuildResult] = []
        for slot in slots:
            fill_buffers = cage.subdivide_offset_buffers_where_curved(slot.fill_buffers, iterations=2)
            line_buffers = (
                cage.subdivide_line_buffers_where_curved(slot.line_buffers, iterations=2)
                if slot.line_buffers is not None
                else None
            )
            slot_results.append(
                DistanceAverageNormalsPreviewSlotBuildResult(
                    fill_buffers=fill_buffers,
                    line_buffers=line_buffers,
                )
            )
        result_queue.put(
            DistanceAverageNormalsPreviewBuildResult(
                generation=generation,
                key=key,
                slots=slot_results,
                slot_keys=slot_keys,
            )
        )
    except Exception:
        traceback.print_exc()
        result_queue.put(
            DistanceAverageNormalsPreviewBuildResult(
                generation=generation,
                key=key,
                slots=[],
                slot_keys=slot_keys,
            )
        )


def reset_auto_cage_preview_runtime(
    state: OverlayPreviewBuildRuntimeState,
    *,
    timer_fn: Callable[[], float | None],
) -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and state.auto_cage_preview_build_timer_registered and hasattr(timers, "unregister"):
        try:
            timers.unregister(timer_fn)
        except Exception:
            pass
    state.auto_cage_preview_cache = None
    state.auto_cage_preview_pending_request = None
    state.auto_cage_preview_build_generation += 1
    state.auto_cage_preview_build_thread = None
    state.auto_cage_preview_build_active_key = None
    state.auto_cage_preview_build_timer_registered = False


def reset_distance_average_normals_preview_runtime(
    state: OverlayPreviewBuildRuntimeState,
    *,
    timer_fn: Callable[[], float | None],
) -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if (
        timers is not None
        and state.distance_average_normals_preview_build_timer_registered
        and hasattr(timers, "unregister")
    ):
        try:
            timers.unregister(timer_fn)
        except Exception:
            pass
    state.distance_average_normals_preview_cache = None
    state.distance_average_normals_preview_pending_request = None
    state.distance_average_normals_preview_build_generation += 1
    state.distance_average_normals_preview_build_thread = None
    state.distance_average_normals_preview_build_active_key = None
    state.distance_average_normals_preview_build_timer_registered = False


def ensure_auto_cage_preview_build_timer_registered(
    state: OverlayPreviewBuildRuntimeState,
    *,
    timer_fn: Callable[[], float | None],
    first_interval: float = 0.01,
) -> bool:
    if state.auto_cage_preview_build_timer_registered:
        return True
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False
    try:
        timers.register(timer_fn, first_interval=max(0.01, float(first_interval)))
        state.auto_cage_preview_build_timer_registered = True
        return True
    except Exception:
        return False


def ensure_distance_average_normals_preview_build_timer_registered(
    state: OverlayPreviewBuildRuntimeState,
    *,
    timer_fn: Callable[[], float | None],
    first_interval: float = 0.01,
) -> bool:
    if state.distance_average_normals_preview_build_timer_registered:
        return True
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False
    try:
        timers.register(timer_fn, first_interval=max(0.01, float(first_interval)))
        state.distance_average_normals_preview_build_timer_registered = True
        return True
    except Exception:
        return False


def enqueue_auto_cage_preview_build(
    state: OverlayPreviewBuildRuntimeState,
    *,
    group,
    key: tuple,
    ensure_timer_registered_fn: Callable[[float], bool],
) -> None:
    if group is None:
        return
    cache_entry = state.auto_cage_preview_cache
    if cache_entry is not None and cache_entry.key == key:
        return
    pending_request = state.auto_cage_preview_pending_request
    if pending_request is not None and pending_request.key == key:
        return
    if state.auto_cage_preview_build_active_key == key:
        return
    state.auto_cage_preview_pending_request = AutoCagePreviewBuildRequest(
        generation=state.auto_cage_preview_build_generation,
        key=key,
        group=group,
    )
    ensure_timer_registered_fn(0.01)


def enqueue_distance_average_normals_preview_build(
    state: OverlayPreviewBuildRuntimeState,
    *,
    key: tuple,
    slots: list[DistanceAverageNormalsPreviewSlotBuildInput],
    ensure_timer_registered_fn: Callable[[float], bool],
) -> None:
    if not slots:
        return
    cache_entry = state.distance_average_normals_preview_cache
    if cache_entry is not None and cache_entry.key == key:
        return
    if cache_entry is not None:
        # The cache is stale for this request. Release every slot the new key no
        # longer wants NOW, before the worker allocates the replacement: a dense
        # cage's slot is GBs, and holding the old one through the rebuild doubled
        # the peak. Slots the new key still wants are kept and merged at flush.
        state.distance_average_normals_preview_cache = prune_distance_average_normals_preview_cache(
            cache_entry,
            key,
        )
    pending_request = state.distance_average_normals_preview_pending_request
    if pending_request is not None and pending_request.key == key:
        return
    if state.distance_average_normals_preview_build_active_key == key:
        return
    state.distance_average_normals_preview_pending_request = DistanceAverageNormalsPreviewBuildRequest(
        generation=state.distance_average_normals_preview_build_generation,
        key=key,
        slots=slots,
    )
    ensure_timer_registered_fn(0.01)


def flush_auto_cage_preview_build_results(state: OverlayPreviewBuildRuntimeState) -> bool:
    updated = False
    while True:
        try:
            result = state.auto_cage_preview_build_result_queue.get_nowait()
        except queue.Empty:
            break
        if result.generation != state.auto_cage_preview_build_generation:
            continue
        if state.auto_cage_preview_build_active_key == result.key:
            state.auto_cage_preview_build_active_key = None
        state.auto_cage_preview_cache = AutoCagePreviewCacheEntry(
            key=result.key,
            fitted_triangles=result.fitted_triangles,
        )
        updated = True
    return updated


def distance_average_normals_preview_slot_lookup(
    cache_entry: DistanceAverageNormalsPreviewCacheEntry | None,
) -> dict[tuple, DistanceAverageNormalsPreviewSlotBuildResult]:
    """Per-slot-key view of a cache entry (empty when keys and slots disagree)."""
    if cache_entry is None:
        return {}
    keys = tuple(cache_entry.key or ())
    slots = list(cache_entry.slots or ())
    if len(keys) != len(slots):
        return {}
    return dict(zip(keys, slots))


def prune_distance_average_normals_preview_cache(
    cache_entry: DistanceAverageNormalsPreviewCacheEntry | None,
    wanted_keys: tuple,
) -> DistanceAverageNormalsPreviewCacheEntry | None:
    """Keep only the slots ``wanted_keys`` still names; None when none survive."""
    if cache_entry is None:
        return None
    wanted = set(wanted_keys or ())
    lookup = distance_average_normals_preview_slot_lookup(cache_entry)
    kept_keys = tuple(slot_key for slot_key in lookup if slot_key in wanted)
    if not kept_keys:
        return None
    return DistanceAverageNormalsPreviewCacheEntry(
        key=kept_keys,
        slots=[lookup[slot_key] for slot_key in kept_keys],
    )


def flush_distance_average_normals_preview_build_results(state: OverlayPreviewBuildRuntimeState) -> bool:
    updated = False
    while True:
        try:
            result = state.distance_average_normals_preview_build_result_queue.get_nowait()
        except queue.Empty:
            break
        if result.generation != state.distance_average_normals_preview_build_generation:
            continue
        if state.distance_average_normals_preview_build_active_key == result.key:
            state.distance_average_normals_preview_build_active_key = None
        pending_request = state.distance_average_normals_preview_pending_request
        if pending_request is not None and pending_request.key != result.key:
            # Superseded while it ran: the pending request recomputes every slot the
            # current key is missing, and a result whose key has moved on was never
            # displayable anyway. Drop it rather than hold GBs until the next flush.
            continue
        merged = distance_average_normals_preview_slot_lookup(state.distance_average_normals_preview_cache)
        slot_keys = tuple(result.slot_keys or ())
        if not slot_keys and len(result.key or ()) == len(result.slots):
            slot_keys = tuple(result.key)
        if result.slots and len(result.slots) == len(slot_keys):
            merged.update(zip(slot_keys, result.slots))
        else:
            for slot_key in slot_keys:
                merged[slot_key] = DistanceAverageNormalsPreviewSlotBuildResult(fill_buffers=None, failed=True)
        entry_keys = tuple(slot_key for slot_key in dict.fromkeys(result.key or ()) if slot_key in merged)
        state.distance_average_normals_preview_cache = DistanceAverageNormalsPreviewCacheEntry(
            key=entry_keys,
            slots=[merged[slot_key] for slot_key in entry_keys],
        )
        updated = True
    return updated


def capture_auto_cage_preview_build_data(
    group,
    depsgraph,
    *,
    iter_valid_meshes_fn: Callable[[object], object],
):
    smooth_normals = cage.auto_cage_uses_average_normals(group)
    tmp_path = Path(tempfile.mkdtemp(prefix="mb_auto_cage_preview_"))
    try:
        uv_layer_name = (getattr(group, "uv_layer_name", "") or "").strip() or None
        low_mesh_refs = []
        for index, obj in enumerate(iter_valid_meshes_fn(group.low_meshes)):
            ref = export.write_evaluated_obj(
                obj,
                depsgraph,
                tmp_path / f"low_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
                uv_layer_name=uv_layer_name,
            )
            ref.role = constants.OBJECT_ROLE_LOW
            low_mesh_refs.append(ref)

        high_mesh_refs = []
        for index, obj in enumerate(iter_valid_meshes_fn(_effective_high_mesh_slots(group))):
            ref = export.write_evaluated_obj(
                obj,
                depsgraph,
                tmp_path / f"high_{index:02d}_{naming.sanitize_token(obj.name)}.fymesh",
            )
            ref.role = constants.OBJECT_ROLE_HIGH
            high_mesh_refs.append(ref)
        return low_mesh_refs, high_mesh_refs, str(runtime.resolve_backend_executable()), str(tmp_path), smooth_normals
    except Exception:
        shutil.rmtree(tmp_path, ignore_errors=True)
        raise


def auto_cage_preview_build_timer_tick(
    state: OverlayPreviewBuildRuntimeState,
    *,
    deps: OverlayPreviewBuildDeps,
) -> float | None:
    updated = flush_auto_cage_preview_build_results(state)
    if updated:
        deps.invalidate_overlay_cache()
        deps.tag_redraw_all_view3d()

    if deps.post_load_overlay_grace_active():
        return deps.post_load_overlay_grace_delay()

    if state.auto_cage_preview_build_thread is not None and state.auto_cage_preview_build_thread.is_alive():
        return 0.05
    state.auto_cage_preview_build_thread = None

    pending_request = state.auto_cage_preview_pending_request
    if pending_request is None:
        state.auto_cage_preview_build_timer_registered = False
        return None

    state.auto_cage_preview_pending_request = None
    try:
        context = getattr(bpy, "context", None)
        if context is None or not hasattr(context, "evaluated_depsgraph_get"):
            state.auto_cage_preview_build_timer_registered = False
            return None
        depsgraph = context.evaluated_depsgraph_get()
        low_mesh_refs, high_mesh_refs, backend_exe, temp_dir, average_normals = capture_auto_cage_preview_build_data(
            pending_request.group,
            depsgraph,
            iter_valid_meshes_fn=deps.iter_valid_meshes,
        )
        if not high_mesh_refs:
            shutil.rmtree(temp_dir, ignore_errors=True)
            state.auto_cage_preview_cache = AutoCagePreviewCacheEntry(
                key=pending_request.key,
                fitted_triangles=[],
            )
            deps.invalidate_overlay_cache()
            deps.tag_redraw_all_view3d()
            state.auto_cage_preview_build_timer_registered = False
            return None
        worker = threading.Thread(
            target=_auto_cage_preview_build_worker,
            args=(
                pending_request.generation,
                pending_request.key,
                low_mesh_refs,
                high_mesh_refs,
                backend_exe,
                temp_dir,
                average_normals,
                state.auto_cage_preview_build_result_queue,
            ),
            daemon=True,
            name="master_baker_auto_cage_preview",
        )
        state.auto_cage_preview_build_thread = worker
        state.auto_cage_preview_build_active_key = pending_request.key
        worker.start()
        return 0.05
    except Exception:
        traceback.print_exc()
        state.auto_cage_preview_build_timer_registered = False
        return None


def distance_average_normals_preview_build_timer_tick(
    state: OverlayPreviewBuildRuntimeState,
    *,
    deps: OverlayPreviewBuildDeps,
) -> float | None:
    updated = flush_distance_average_normals_preview_build_results(state)
    if updated:
        deps.invalidate_overlay_cache()
        deps.tag_redraw_all_view3d()

    if deps.post_load_overlay_grace_active():
        return deps.post_load_overlay_grace_delay()

    if (
        state.distance_average_normals_preview_build_thread is not None
        and state.distance_average_normals_preview_build_thread.is_alive()
    ):
        return 0.05
    state.distance_average_normals_preview_build_thread = None

    pending_request = state.distance_average_normals_preview_pending_request
    if pending_request is None:
        state.distance_average_normals_preview_build_timer_registered = False
        return None

    state.distance_average_normals_preview_pending_request = None
    try:
        worker = threading.Thread(
            target=_distance_average_normals_preview_build_worker,
            args=(
                pending_request.generation,
                pending_request.key,
                pending_request.slots,
                state.distance_average_normals_preview_build_result_queue,
            ),
            daemon=True,
            name="master_baker_distance_average_normals_preview",
        )
        state.distance_average_normals_preview_build_thread = worker
        state.distance_average_normals_preview_build_active_key = pending_request.key
        worker.start()
        return 0.05
    except Exception:
        traceback.print_exc()
        state.distance_average_normals_preview_build_timer_registered = False
        return None
