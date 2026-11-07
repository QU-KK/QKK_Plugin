from __future__ import annotations

from array import array

from gpu_extras.batch import batch_for_shader

from . import cage


def _vertex_rows(values, components: int):
    """Row view of a flat ``array('f')`` for the ``batch_for_shader`` fallbacks.

    Subdivided cage buffers arrive as flat float32 arrays (3 floats per vertex) so the
    GPUVertBuf fast path can fill them directly. ``batch_for_shader`` sizes the vertex
    buffer from ``len()`` of an attribute, so a flat array must be presented as an
    (N, components) buffer; row sequences pass through unchanged.
    """
    if isinstance(values, array):
        # batch_for_shader indexes row 0 to size the attribute; a multi-dimensional
        # memoryview cannot be indexed ("sub-views are not implemented"), a numpy
        # view can (and shares the array's memory).
        import numpy as np

        return np.frombuffer(values, dtype=np.float32).reshape(-1, components)
    return values


def build_batch(primitive_type, positions, *, get_shader_fn):
    if not positions:
        return None
    return batch_for_shader(get_shader_fn(), primitive_type, {"pos": positions})


def build_offset_batch(
    buffers: cage.OffsetBatchBuffers,
    *,
    primitive_type: str = "TRIS",
    build_offset_gpu_batch_fn,
    get_offset_shader_fn,
):
    if not buffers.positions:
        return None
    gpu_batch = build_offset_gpu_batch_fn(
        primitive_type,
        buffers.positions,
        buffers.normals,
    )
    if gpu_batch is not None:
        return gpu_batch
    return batch_for_shader(
        get_offset_shader_fn(),
        primitive_type,
        {
            "position": _vertex_rows(buffers.positions, 3),
            "normal": _vertex_rows(buffers.normals, 3),
        },
    )


def build_lit_offset_batch(
    buffers: cage.OffsetBatchBuffers,
    *,
    build_offset_gpu_batch_fn,
    get_lit_offset_shader_fn,
):
    if not buffers.positions:
        return None
    gpu_batch = build_offset_gpu_batch_fn(
        "TRIS",
        buffers.positions,
        buffers.normals,
    )
    if gpu_batch is not None:
        return gpu_batch
    return batch_for_shader(
        get_lit_offset_shader_fn(),
        "TRIS",
        {"position": _vertex_rows(buffers.positions, 3), "normal": _vertex_rows(buffers.normals, 3)},
    )


def build_paint_offset_batch(
    buffers: cage.OffsetBatchBuffers,
    *,
    primitive_type: str = "TRIS",
    build_offset_gpu_batch_fn,
    get_paint_offset_shader_fn,
):
    if not buffers.positions or not buffers.uvs:
        return None
    paints = getattr(buffers, "paints", None) or None
    gpu_batch = build_offset_gpu_batch_fn(
        primitive_type,
        buffers.positions,
        buffers.normals,
        uvs=buffers.uvs,
        paints=paints,
    )
    if gpu_batch is not None:
        return gpu_batch
    vertex_count = len(buffers.positions)
    paint_values = (
        [float(value) for value in paints]
        if paints is not None and len(paints) == vertex_count
        else [1.0] * vertex_count
    )
    try:
        return batch_for_shader(
            get_paint_offset_shader_fn(),
            primitive_type,
            {
                "position": _vertex_rows(buffers.positions, 3),
                "normal": _vertex_rows(buffers.normals, 3),
                "uv": _vertex_rows(buffers.uvs, 2),
                "paint_value": paint_values,
            },
        )
    except Exception:
        return None
