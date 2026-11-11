"""Native writer for the compact V4 (.fymesh) high-poly mesh file.

``export.write_high_corner_arrays`` gathers every triangle corner (position, loop normal),
normalises the normal in float32 and streams the rows to disk with numpy. On a 71-object,
~100 M triangle customer scene that was 13 s of Python-driven gathering. The same bytes are
produced here by ``fyr_write_fymesh_v4_arrays`` in ``fyr_geometry_hash.dll``, which reads the
numpy arrays the capture already made (no Blender pointer is kept, so nothing depends on the
mesh being alive), runs the gather on several threads and writes in order.

Everything is opt-out and fail-safe: any unsupported dtype/layout, a missing DLL or symbol, or
a non-zero native result returns ``None`` and the caller uses the numpy writer, which remains
the reference. ``FYR_BAKER_NATIVE_MESH_WRITE=0`` forces the numpy writer.
"""

from __future__ import annotations

import ctypes
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()
_LIBRARY = None
_LIBRARY_FAILED = False

_SYMBOL = "fyr_write_fymesh_v4_arrays"


def native_mesh_write_enabled() -> bool:
    value = str(os.environ.get("FYR_BAKER_NATIVE_MESH_WRITE", "") or "").strip().upper()
    return value not in {"0", "OFF", "FALSE", "NO", "DISABLED"}


def _load_library():
    global _LIBRARY, _LIBRARY_FAILED
    with _LOCK:
        if _LIBRARY is not None or _LIBRARY_FAILED:
            return _LIBRARY
        try:
            from . import indexed_geometry

            library = ctypes.CDLL(str(indexed_geometry._hash_library_path()))
            function = getattr(library, _SYMBOL)  # AttributeError on a DLL from before this writer
            function.argtypes = (
                ctypes.c_char_p,
                ctypes.c_void_p,
                ctypes.c_uint64,
                ctypes.c_void_p,
                ctypes.c_uint64,
                ctypes.c_void_p,
                ctypes.c_uint64,
                ctypes.c_void_p,
                ctypes.c_uint32,
            )
            function.restype = ctypes.c_int
            _LIBRARY = library
        except Exception:
            _LIBRARY_FAILED = True
            _LIBRARY = None
        return _LIBRARY


def _array_ok(array, dtype, size) -> bool:
    return (
        array is not None
        and getattr(array, "dtype", None) == dtype
        and bool(array.flags.c_contiguous)
        and int(array.size) == int(size)
    )


def write_fymesh_v4_arrays(destination, captured, *, threads: int = 0):
    """Write ``captured`` (the tuple ``capture_high_obj_corner_arrays`` returns) to
    ``destination`` as a V4 mesh, or return None when the numpy writer must do it.

    On None nothing is left at ``destination`` by this call."""
    if not native_mesh_write_enabled():
        return None
    try:
        import numpy as np
        from . import mesh_transport

        triangle_count, triangle_loop_indices, loop_vertex_indices, vertex_positions, loop_normals = captured
        triangle_count = int(triangle_count)
        loop_count = int(loop_vertex_indices.shape[0])
        vertex_count = int(vertex_positions.shape[0])
        if triangle_count <= 0 or loop_count <= 0 or vertex_count <= 0 or triangle_count > 0xFFFFFFFF:
            return None
        if vertex_positions.ndim != 2 or vertex_positions.shape[1] != 3:
            return None
        if loop_normals.ndim != 2 or loop_normals.shape != (loop_count, 3):
            return None
        if not _array_ok(vertex_positions, np.float32, vertex_count * 3):
            return None
        if not _array_ok(loop_normals, np.float32, loop_count * 3):
            return None
        if not _array_ok(loop_vertex_indices, np.int32, loop_count):
            return None
        if triangle_loop_indices is None:
            if loop_count < triangle_count * 3:
                return None
            loops_pointer = None
        else:
            if not _array_ok(triangle_loop_indices, np.int32, triangle_count * 3):
                return None
            loops_pointer = triangle_loop_indices.ctypes.data

        library = _load_library()
        if library is None:
            return None
        resolved = mesh_transport.binary_mesh_path(destination)
        mesh_transport.ensure_dir(resolved.parent)
        status = getattr(library, _SYMBOL)(
            os.fsencode(str(resolved)) if os.name != "nt" else str(resolved).encode("utf-8"),
            vertex_positions.ctypes.data,
            vertex_count,
            loop_vertex_indices.ctypes.data,
            loop_count,
            loops_pointer,
            triangle_count,
            loop_normals.ctypes.data,
            int(threads),
        )
        if status != 0:
            try:
                Path(resolved).unlink()
            except OSError:
                pass
            return None
        return resolved
    except Exception:
        return None
