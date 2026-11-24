from __future__ import annotations

from array import array
from dataclasses import dataclass, field
import queue

import bpy

from . import cage


@dataclass(slots=True)
class HighReferenceCacheEntry:
    source_signature: tuple
    color_key: tuple[float, float, float, float] | None
    positions: array | None
    normals: array | None
    overlay_pass: object | None


@dataclass(slots=True)
class HighReferenceBuildRequest:
    generation: int
    source_pointer: int
    source_signature: tuple
    source_object: object


@dataclass(slots=True)
class HighReferenceBuildResult:
    generation: int
    source_pointer: int
    source_signature: tuple
    positions: array
    normals: array


@dataclass(slots=True)
class OverlayHighReferenceRuntimeState:
    object_cache: dict[int, HighReferenceCacheEntry] = field(default_factory=dict)
    build_queue: dict[int, HighReferenceBuildRequest] = field(default_factory=dict)
    build_order: list[int] = field(default_factory=list)
    build_result_queue: "queue.Queue[HighReferenceBuildResult]" = field(default_factory=queue.Queue)
    build_thread: object | None = None
    build_active_pointer: int | None = None
    build_timer_registered: bool = False
    build_generation: int = 0


def clear_high_reference_object_cache(
    state: OverlayHighReferenceRuntimeState,
    *,
    keep_pointers: set[int] | None = None,
) -> None:
    keep = keep_pointers or set()
    for pointer in list(state.object_cache.keys()):
        if pointer in keep:
            continue
        state.object_cache.pop(pointer, None)


def clear_high_reference_build_queue(
    state: OverlayHighReferenceRuntimeState,
    *,
    keep_pointers: set[int] | None = None,
) -> None:
    keep = keep_pointers or set()
    for pointer in list(state.build_order):
        if pointer in keep:
            continue
        state.build_queue.pop(pointer, None)
    state.build_order[:] = [pointer for pointer in state.build_order if pointer in keep]
    if state.build_active_pointer is not None and state.build_active_pointer not in keep:
        state.build_active_pointer = None


def reset_high_reference_runtime(
    state: OverlayHighReferenceRuntimeState,
    *,
    timer_fn,
) -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and state.build_timer_registered and hasattr(timers, "unregister"):
        try:
            timers.unregister(timer_fn)
        except Exception:
            pass
    state.build_generation += 1
    state.build_thread = None
    state.build_active_pointer = None
    state.build_timer_registered = False
    clear_high_reference_object_cache(state)
    clear_high_reference_build_queue(state)


def high_reference_build_worker(
    generation: int,
    source_pointer: int,
    source_signature: tuple,
    source_data,
    *,
    result_queue: "queue.Queue[HighReferenceBuildResult]",
) -> None:
    try:
        vertex_positions, triangle_vertex_indices, matrix_world = source_data
        positions, normals = cage.build_high_mesh_display_buffers_from_data(
            vertex_positions,
            triangle_vertex_indices,
            matrix_world,
        )
        result_queue.put(
            HighReferenceBuildResult(
                generation=generation,
                source_pointer=source_pointer,
                source_signature=source_signature,
                positions=positions,
                normals=normals,
            )
        )
    except Exception:
        result_queue.put(
            HighReferenceBuildResult(
                generation=generation,
                source_pointer=source_pointer,
                source_signature=source_signature,
                positions=array("f"),
                normals=array("f"),
            )
        )


def ensure_high_reference_build_timer_registered(
    state: OverlayHighReferenceRuntimeState,
    *,
    first_interval: float = 0.01,
) -> bool:
    del first_interval
    clear_high_reference_object_cache(state)
    clear_high_reference_build_queue(state)
    return False


def enqueue_high_reference_build(state: OverlayHighReferenceRuntimeState, obj) -> None:
    del obj
    clear_high_reference_object_cache(state)
    clear_high_reference_build_queue(state)


def flush_high_reference_build_results(state: OverlayHighReferenceRuntimeState) -> bool:
    while True:
        try:
            state.build_result_queue.get_nowait()
        except queue.Empty:
            break
    state.build_active_pointer = None
    clear_high_reference_object_cache(state)
    return False


def high_reference_build_timer_tick(state: OverlayHighReferenceRuntimeState) -> None:
    flush_high_reference_build_results(state)
    state.build_thread = None
    state.build_active_pointer = None
    clear_high_reference_object_cache(state)
    clear_high_reference_build_queue(state)
    state.build_timer_registered = False
    return None


def high_reference_overlay_passes(state: OverlayHighReferenceRuntimeState, context, group, theme):
    del context, group, theme
    clear_high_reference_object_cache(state)
    clear_high_reference_build_queue(state)
    return []
