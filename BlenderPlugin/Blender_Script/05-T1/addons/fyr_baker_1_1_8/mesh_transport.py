from __future__ import annotations

from dataclasses import dataclass
import mmap
import os
from pathlib import Path
import struct
import sys
from typing import Iterable, Sequence
import uuid


MBMESH_MAGIC_V1 = b"MBMESHv1"
MBMESH_MAGIC_V2 = b"MBMESHv2"
MBMESH_MAGIC_V3 = b"MBMESHv3"
# V4: position + normal only (6 floats/corner). For high-poly ray-cast meshes where UV and
# color are never read by the backend GPU path. 45% smaller than V2.
MBMESH_MAGIC_V4 = b"MBMESHv4"
MBMESH_VERSION_RESERVED = 0
MBMESH_EXTENSION = ".fymesh"
SHARED_MEMORY_MESH_PREFIX = "__mbshm__."

_HEADER = struct.Struct("<8sII")


def map_v4_positions(path):
    """Memory-map local-space triangle-corner positions from a compact V4 mesh."""
    import numpy as np

    source = Path(path)
    with source.open("rb") as stream:
        raw = stream.read(_HEADER.size)
    if len(raw) != _HEADER.size:
        raise ValueError("Binary mesh header is incomplete")
    magic, triangle_count, _reserved = _HEADER.unpack(raw)
    if magic != MBMESH_MAGIC_V4:
        raise ValueError("Binary mesh is not compact V4 geometry")
    corner_count = int(triangle_count) * 3
    expected_size = _HEADER.size + corner_count * 6 * 4
    if source.stat().st_size != expected_size:
        raise ValueError("Binary V4 mesh size does not match its header")
    payload = np.memmap(
        source,
        dtype="<f4",
        mode="r",
        offset=_HEADER.size,
        shape=(corner_count, 6),
    )
    return payload[:, :3], int(triangle_count)
_VERTEX_V1 = struct.Struct("<8f")
_VERTEX_V2 = struct.Struct("<11f")
# V3 adds paint_offset (float) and paint_skew (float) per corner
_VERTEX_V3 = struct.Struct("<13f")
_PAINT_OFFSET_DEFAULT = 1.0
_PAINT_SKEW_DEFAULT = 0.0

_SHARED_MEMORY_WORKSPACES: dict[str, dict[str, mmap.mmap]] = {}
_SHARED_MEMORY_MIN_BYTES = 1024 * 1024


@dataclass(slots=True)
class MeshTransportCorner:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    paint_offset: float = 1.0
    paint_skew: float = 0.0


@dataclass(slots=True)
class MeshTransportTriangle:
    corners: tuple[MeshTransportCorner, MeshTransportCorner, MeshTransportCorner]


@dataclass(slots=True)
class MeshTransportData:
    triangle_count: int
    triangles: list[MeshTransportTriangle]


def ensure_dir(path) -> None:
    """``Path(path).mkdir(parents=True, exist_ok=True)``, with one stat when the directory is there
    (the job build asks for the same few directories several times per group)."""
    text = os.fspath(path)
    try:
        if os.path.isdir(text):
            return
    except OSError:
        pass
    Path(text).mkdir(parents=True, exist_ok=True)


def binary_mesh_path(path: str | Path) -> Path:
    destination = Path(path)
    if destination.suffix.lower() == MBMESH_EXTENSION:
        return destination
    if destination.suffix:
        return destination.with_suffix(MBMESH_EXTENSION)
    return destination.with_name(destination.name + MBMESH_EXTENSION)


def _coerce_float_sequence(value, expected_length: int, label: str) -> tuple[float, ...]:
    if hasattr(value, "x") and hasattr(value, "y"):
        raw = (
            float(getattr(value, "x")),
            float(getattr(value, "y")),
            float(getattr(value, "z", 0.0)),
        )
        if expected_length == 2:
            return raw[:2]
        if expected_length == 3:
            return raw
    if isinstance(value, Sequence):
        raw = tuple(float(component) for component in value[:expected_length])
        if len(raw) == expected_length:
            return raw
    try:
        raw = tuple(float(component) for component in value)
    except TypeError as exc:
        raise TypeError(f"Expected {label} to be a sequence") from exc
    if len(raw) != expected_length:
        raise ValueError(f"Expected {label} to have {expected_length} components")
    return raw


def _coerce_corner(corner) -> MeshTransportCorner:
    position = getattr(corner, "position", corner)
    normal = getattr(corner, "normal", None)
    uv = getattr(corner, "uv", None)
    color = getattr(corner, "color", None)
    if normal is None or uv is None:
        if isinstance(corner, Sequence) and len(corner) >= 3:
            position, normal, uv = corner[:3]
            if len(corner) >= 4:
                color = corner[3]
        else:
            raise ValueError("Triangle corners must expose position, normal, and uv values")
    if color is None:
        color = (1.0, 1.0, 1.0)
    paint_offset = _PAINT_OFFSET_DEFAULT
    paint_skew = _PAINT_SKEW_DEFAULT
    if isinstance(corner, Sequence) and len(corner) >= 5:
        paint_offset = float(corner[4])
    if isinstance(corner, Sequence) and len(corner) >= 6:
        paint_skew = float(corner[5])
    return MeshTransportCorner(
        position=_coerce_float_sequence(position, 3, "position"),
        normal=_coerce_float_sequence(normal, 3, "normal"),
        uv=_coerce_float_sequence(uv, 2, "uv"),
        color=_coerce_float_sequence(color, 3, "color"),
        paint_offset=paint_offset,
        paint_skew=paint_skew,
    )


def _coerce_triangle(triangle) -> MeshTransportTriangle:
    corners = getattr(triangle, "corners", triangle)
    if len(corners) != 3:
        raise ValueError("Binary mesh transport only supports triangle soup")
    return MeshTransportTriangle(corners=tuple(_coerce_corner(corner) for corner in corners))


def build_triangle_soup_mesh_payload(triangles: Iterable, *, triangle_count: int | None = None) -> bytes:
    triangle_records = [_coerce_triangle(triangle) for triangle in triangles]
    resolved_triangle_count = len(triangle_records) if triangle_count is None else int(triangle_count)
    if resolved_triangle_count != len(triangle_records):
        raise ValueError("Triangle count does not match the provided triangle records")

    use_v3 = any(
        abs(corner.paint_offset - _PAINT_OFFSET_DEFAULT) > 1e-7 or abs(corner.paint_skew - _PAINT_SKEW_DEFAULT) > 1e-7
        for triangle in triangle_records
        for corner in triangle.corners
    )

    magic = MBMESH_MAGIC_V3 if use_v3 else MBMESH_MAGIC_V2
    vertex_struct = _VERTEX_V3 if use_v3 else _VERTEX_V2

    payload = bytearray()
    payload.extend(_HEADER.pack(magic, resolved_triangle_count, MBMESH_VERSION_RESERVED))
    for triangle in triangle_records:
        for corner in triangle.corners:
            if use_v3:
                payload.extend(
                    vertex_struct.pack(
                        float(corner.position[0]),
                        float(corner.position[1]),
                        float(corner.position[2]),
                        float(corner.normal[0]),
                        float(corner.normal[1]),
                        float(corner.normal[2]),
                        float(corner.uv[0]),
                        float(corner.uv[1]),
                        float(corner.color[0]),
                        float(corner.color[1]),
                        float(corner.color[2]),
                        float(corner.paint_offset),
                        float(corner.paint_skew),
                    )
                )
            else:
                payload.extend(
                    vertex_struct.pack(
                        float(corner.position[0]),
                        float(corner.position[1]),
                        float(corner.position[2]),
                        float(corner.normal[0]),
                        float(corner.normal[1]),
                        float(corner.normal[2]),
                        float(corner.uv[0]),
                        float(corner.uv[1]),
                        float(corner.color[0]),
                        float(corner.color[1]),
                        float(corner.color[2]),
                    )
                )

    return bytes(payload)


def build_triangle_soup_mesh_payload_from_corner_objects(triangles) -> bytes:
    """Byte-identical to build_triangle_soup_mesh_payload for corner objects that expose
    position / normal (3 components) and uv (2) and carry no colour or paint values
    (cage.TriangleData): a V2 payload with white colour, built by one numpy array
    instead of ~25 Python objects per corner."""
    import numpy as np

    corners = [corner for triangle in triangles for corner in triangle.corners]
    count = len(corners)
    if count == 0 or count % 3:
        raise ValueError("Binary mesh transport only supports triangle soup")
    data = np.empty((count, 11), dtype="<f4")
    data[:, 0:3] = [(c.position[0], c.position[1], c.position[2]) for c in corners]
    data[:, 3:6] = [(c.normal[0], c.normal[1], c.normal[2]) for c in corners]
    data[:, 6:8] = [(c.uv[0], c.uv[1]) for c in corners]
    data[:, 8:11] = 1.0
    return _HEADER.pack(MBMESH_MAGIC_V2, count // 3, MBMESH_VERSION_RESERVED) + data.tobytes()


def build_triangle_soup_mesh_payload_from_soup(soup) -> bytes:
    """Byte-identical to build_triangle_soup_mesh_payload_from_corner_objects for the corners of a
    cage_soup.CageSoup (the same float32 values, held as arrays)."""
    return soup.payload(_HEADER, MBMESH_MAGIC_V2, MBMESH_VERSION_RESERVED)


def build_triangle_soup_mesh_payload_from_corner_arrays(
    positions,
    normals,
    uvs,
    *,
    colors=None,
    paint_offsets=None,
    paint_skews=None,
) -> bytes:
    import numpy as np

    corner_positions = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
    corner_normals = np.asarray(normals, dtype=np.float32).reshape(-1, 3)
    corner_uvs = np.asarray(uvs, dtype=np.float32).reshape(-1, 2)
    corner_count = int(corner_positions.shape[0])
    if corner_count <= 0 or (corner_count % 3) != 0:
        raise ValueError("Corner arrays must contain a positive multiple of 3 elements")
    if corner_normals.shape[0] != corner_count or corner_uvs.shape[0] != corner_count:
        raise ValueError("Corner array lengths must match")

    if colors is None:
        corner_colors = np.ones((corner_count, 3), dtype=np.float32)
    else:
        corner_colors = np.asarray(colors, dtype=np.float32).reshape(-1, 3)
        if corner_colors.shape[0] != corner_count:
            raise ValueError("Color array length must match the corner count")

    use_v3 = paint_offsets is not None or paint_skews is not None
    if use_v3:
        if paint_offsets is None:
            corner_paint_offsets = np.full(corner_count, _PAINT_OFFSET_DEFAULT, dtype=np.float32)
        else:
            corner_paint_offsets = np.asarray(paint_offsets, dtype=np.float32).reshape(-1)
            if corner_paint_offsets.shape[0] != corner_count:
                raise ValueError("Paint offset array length must match the corner count")
        if paint_skews is None:
            corner_paint_skews = np.full(corner_count, _PAINT_SKEW_DEFAULT, dtype=np.float32)
        else:
            corner_paint_skews = np.asarray(paint_skews, dtype=np.float32).reshape(-1)
            if corner_paint_skews.shape[0] != corner_count:
                raise ValueError("Paint skew array length must match the corner count")
        if not np.any(np.abs(corner_paint_offsets - _PAINT_OFFSET_DEFAULT) > 1.0e-7) and not np.any(
            np.abs(corner_paint_skews - _PAINT_SKEW_DEFAULT) > 1.0e-7
        ):
            use_v3 = False

    if use_v3:
        magic = MBMESH_MAGIC_V3
        corner_payload = np.column_stack(
            (
                corner_positions,
                corner_normals,
                corner_uvs,
                corner_colors,
                corner_paint_offsets.reshape(-1, 1),
                corner_paint_skews.reshape(-1, 1),
            )
        )
    else:
        magic = MBMESH_MAGIC_V2
        corner_payload = np.column_stack(
            (
                corner_positions,
                corner_normals,
                corner_uvs,
                corner_colors,
            )
        )

    header = _HEADER.pack(magic, corner_count // 3, MBMESH_VERSION_RESERVED)
    return header + np.ascontiguousarray(corner_payload, dtype=np.float32).tobytes()


def triangle_soup_paint_columns_needed(paint_offsets, paint_skews) -> bool:
    """Whether corner paint values force the V3 layout (same rule as the whole-array builder)."""
    import numpy as np

    if paint_offsets is None and paint_skews is None:
        return False
    offsets_differ = paint_offsets is not None and bool(
        np.any(np.abs(np.asarray(paint_offsets, dtype=np.float32).reshape(-1) - _PAINT_OFFSET_DEFAULT) > 1.0e-7)
    )
    skews_differ = paint_skews is not None and bool(
        np.any(np.abs(np.asarray(paint_skews, dtype=np.float32).reshape(-1) - _PAINT_SKEW_DEFAULT) > 1.0e-7)
    )
    return offsets_differ or skews_differ


@dataclass(slots=True)
class StreamedTriangleSoupPayload:
    """A V2/V3 triangle-soup payload produced chunk by chunk instead of as one bytes object.

    ``chunk_factory()`` returns a fresh iterable of float32 row blocks of shape
    (corners, 11) for V2 or (corners, 13) for V3, in corner order. The bytes written are
    the header followed by those rows: identical to
    build_triangle_soup_mesh_payload_from_corner_arrays for the same corner arrays, but
    the full payload (and its column_stack / tobytes / header-concat copies, ~4x the file
    size at once) never exists in memory.
    """

    triangle_count: int
    use_v3: bool
    chunk_factory: object

    @property
    def magic(self) -> bytes:
        return MBMESH_MAGIC_V3 if self.use_v3 else MBMESH_MAGIC_V2

    @property
    def floats_per_corner(self) -> int:
        return 13 if self.use_v3 else 11

    @property
    def byte_size(self) -> int:
        return _HEADER.size + int(self.triangle_count) * 3 * self.floats_per_corner * 4

    def header(self) -> bytes:
        return _HEADER.pack(self.magic, int(self.triangle_count), MBMESH_VERSION_RESERVED)

    def iter_row_blocks(self):
        """Yield validated contiguous float32 row blocks; raise if the corner total is off."""
        import numpy as np

        width = self.floats_per_corner
        expected = int(self.triangle_count) * 3
        written = 0
        for rows in self.chunk_factory():
            rows = np.ascontiguousarray(rows, dtype=np.float32)
            if rows.ndim != 2 or rows.shape[1] != width:
                raise ValueError(f"Triangle-soup rows must have shape (corners, {width})")
            written += int(rows.shape[0])
            if written > expected:
                raise ValueError("Triangle-soup stream produced more corners than its header")
            yield rows
        if written != expected:
            raise ValueError(
                f"Triangle-soup stream wrote {written} corners, header says {expected}"
            )


def _write_streamed_triangle_soup_file(path: str | Path, payload: StreamedTriangleSoupPayload, mapping=None) -> Path:
    destination = binary_mesh_path(path)
    ensure_dir(destination.parent)
    header = payload.header()
    try:
        with destination.open("wb") as stream:
            stream.write(header)
            if mapping is not None:
                mapping.write(header)
            for rows in payload.iter_row_blocks():
                view = rows.data
                stream.write(view)
                if mapping is not None:
                    mapping.write(view)
    except BaseException:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    return destination


def build_high_poly_mesh_payload_from_corner_arrays(positions, normals) -> bytes:
    """V4 format: position + normal only (6 floats/corner).

    UV and color are always discarded for high-poly ray-cast meshes by the backend GPU path,
    so exporting them is pure waste. V4 is 45% smaller than V2 and the backend reads it
    using the same parser with UV/color filled in as neutral defaults.
    """
    import numpy as np

    corner_positions = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
    corner_normals = np.asarray(normals, dtype=np.float32).reshape(-1, 3)
    corner_count = int(corner_positions.shape[0])
    if corner_count <= 0 or (corner_count % 3) != 0:
        raise ValueError("Corner arrays must contain a positive multiple of 3 elements")
    if corner_normals.shape[0] != corner_count:
        raise ValueError("Corner normal array length must match position array")
    corner_payload = np.ascontiguousarray(
        np.column_stack((corner_positions, corner_normals)), dtype=np.float32
    )
    header = _HEADER.pack(MBMESH_MAGIC_V4, corner_count // 3, MBMESH_VERSION_RESERVED)
    return header + corner_payload.tobytes()


def write_high_poly_mesh_payload_chunks(path: str | Path, triangle_count: int, chunks: Iterable) -> Path:
    """Stream a V4 mesh to disk: the header, then each chunk of (corners, 6) float32 rows.

    Same bytes as write_triangle_soup_payload(path, build_high_poly_mesh_payload_from_corner_arrays(...)),
    but the full payload never exists in memory. Building it whole held the corner arrays plus three
    payload-sized copies (column_stack, tobytes, header concat) at once: ~410 B per triangle at the
    peak, 17 GB of Blender RAM for one 41M-triangle high (SvAT Body_Main, 2026-09-29).
    A failed write removes the partial file.
    """
    import numpy as np

    destination = binary_mesh_path(path)
    ensure_dir(destination.parent)
    expected_corners = int(triangle_count) * 3
    written_corners = 0
    try:
        with destination.open("wb") as stream:
            stream.write(_HEADER.pack(MBMESH_MAGIC_V4, int(triangle_count), MBMESH_VERSION_RESERVED))
            for rows in chunks:
                rows = np.ascontiguousarray(rows, dtype=np.float32)
                if rows.ndim != 2 or rows.shape[1] != 6:
                    raise ValueError("V4 corner rows must have shape (corners, 6)")
                stream.write(rows.data)
                written_corners += int(rows.shape[0])
        if written_corners != expected_corners:
            raise ValueError(
                f"V4 mesh stream wrote {written_corners} corners, header says {expected_corners}"
            )
    except BaseException:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    return destination


def shared_memory_transport_available() -> bool:
    return sys.platform == "win32"


def shared_memory_transport_enabled() -> bool:
    if not shared_memory_transport_available():
        return False
    value = str(os.environ.get("FYR_BAKER_MESH_TRANSPORT", "") or "").strip().upper()
    if value in {"OFF", "DISABLED", "NONE", "FILE", "DISK", "0", "FALSE", "NO"}:
        return False
    if value in {"", "AUTO", "SHARED_MEMORY", "MMAP", "MEMORY_MAP", "ON", "1", "TRUE", "YES"}:
        # Default to shared memory on Windows; write_triangle_soup_mesh_ref falls back to files.
        return True
    return False


def shared_memory_mesh_path(mapping_name: str, byte_count: int, fallback_path: str | Path | None = None) -> str:
    path = f"{SHARED_MEMORY_MESH_PREFIX}{int(byte_count)}.{mapping_name}{MBMESH_EXTENSION}"
    if fallback_path is not None:
        path += f"|fallback={Path(fallback_path)}"
    return path


def release_workspace_shared_memory(workspace_key: str | Path | None) -> int:
    key = str(Path(workspace_key).resolve(strict=False)) if workspace_key else ""
    handles = _SHARED_MEMORY_WORKSPACES.pop(key, {}) if key else {}
    released_count = 0
    retained: dict[str, mmap.mmap] = {}
    for name, handle in handles.items():
        try:
            handle.close()
            released_count += 1
        except BufferError:
            # A canonical-writer thread still holds a memoryview over this section.
            # Dropping it from the registry anyway (and reporting 0 released) left a
            # multi-GB mapping committed with nothing left that could ever close it.
            # Keep it registered so the next release - or unregister - can try again.
            retained[name] = handle
            print(
                f"[MasterBaker] shared-memory section '{name}' is still in use; "
                "keeping it registered to release later"
            )
        except Exception:
            pass
    if retained and key:
        _SHARED_MEMORY_WORKSPACES.setdefault(key, {}).update(retained)
    return released_count


def retain_workspace_shared_memory(
    workspace_key: str | Path,
    mapping_name: str,
    handle: mmap.mmap,
) -> None:
    key = str(Path(workspace_key).resolve(strict=False))
    _SHARED_MEMORY_WORKSPACES.setdefault(key, {})[str(mapping_name)] = handle


def release_all_shared_memory() -> int:
    total = 0
    for workspace_key in tuple(_SHARED_MEMORY_WORKSPACES.keys()):
        total += release_workspace_shared_memory(workspace_key)
    return total


def write_triangle_soup_mesh(path: str | Path, triangles: Iterable, *, triangle_count: int | None = None) -> Path:
    destination = binary_mesh_path(path)
    ensure_dir(destination.parent)
    payload = build_triangle_soup_mesh_payload(triangles, triangle_count=triangle_count)
    destination.write_bytes(payload)
    return destination


def write_triangle_soup_payload(path: str | Path, payload: bytes | bytearray | memoryview) -> Path:
    destination = binary_mesh_path(path)
    ensure_dir(destination.parent)
    destination.write_bytes(bytes(payload))
    return destination


def write_triangle_soup_mesh_ref(
    path: str | Path,
    triangles: Iterable,
    *,
    triangle_count: int | None = None,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> str:
    if use_shared_memory and shared_memory_transport_enabled() and workspace_key:
        try:
            payload = build_triangle_soup_mesh_payload(triangles, triangle_count=triangle_count)
            fallback_path = write_triangle_soup_payload(path, payload)
            if len(payload) < _SHARED_MEMORY_MIN_BYTES:
                return str(fallback_path)
            mapping_name = f"MasterBakerMesh_{uuid.uuid4().hex}"
            handle = mmap.mmap(-1, len(payload), tagname=mapping_name, access=mmap.ACCESS_WRITE)
            handle.write(payload)
            handle.seek(0)
            workspace_registry = _SHARED_MEMORY_WORKSPACES.setdefault(
                str(Path(workspace_key).resolve(strict=False)),
                {},
            )
            workspace_registry[mapping_name] = handle
            return shared_memory_mesh_path(mapping_name, len(payload), fallback_path)
        except Exception:
            pass

    return str(write_triangle_soup_mesh(path, triangles, triangle_count=triangle_count))


def write_triangle_soup_payload_ref(
    path: str | Path,
    payload: bytes | bytearray | memoryview,
    *,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> str:
    if isinstance(payload, StreamedTriangleSoupPayload):
        return _write_streamed_triangle_soup_payload_ref(
            path, payload, workspace_key=workspace_key, use_shared_memory=use_shared_memory
        )
    payload_bytes = bytes(payload)
    if use_shared_memory and shared_memory_transport_enabled() and workspace_key:
        try:
            fallback_path = write_triangle_soup_payload(path, payload_bytes)
            if len(payload_bytes) < _SHARED_MEMORY_MIN_BYTES:
                return str(fallback_path)
            mapping_name = f"MasterBakerMesh_{uuid.uuid4().hex}"
            handle = mmap.mmap(-1, len(payload_bytes), tagname=mapping_name, access=mmap.ACCESS_WRITE)
            handle.write(payload_bytes)
            handle.seek(0)
            workspace_registry = _SHARED_MEMORY_WORKSPACES.setdefault(
                str(Path(workspace_key).resolve(strict=False)),
                {},
            )
            workspace_registry[mapping_name] = handle
            return shared_memory_mesh_path(mapping_name, len(payload_bytes), fallback_path)
        except Exception:
            pass

    return str(write_triangle_soup_payload(path, payload_bytes))


def _write_streamed_triangle_soup_payload_ref(
    path: str | Path,
    payload: StreamedTriangleSoupPayload,
    *,
    workspace_key: str | Path | None = None,
    use_shared_memory: bool = False,
) -> str:
    """write_triangle_soup_payload_ref for a streamed payload: same file, same mapping.

    The shared-memory section is sized from the header up front and filled chunk by chunk
    alongside the file, so the result matches the whole-bytes path exactly. A MemoryError
    is never swallowed here: retrying the plain file write would only need the same memory.
    """
    byte_size = payload.byte_size
    if (
        use_shared_memory
        and shared_memory_transport_enabled()
        and workspace_key
        and byte_size >= _SHARED_MEMORY_MIN_BYTES
    ):
        handle = None
        try:
            mapping_name = f"MasterBakerMesh_{uuid.uuid4().hex}"
            handle = mmap.mmap(-1, byte_size, tagname=mapping_name, access=mmap.ACCESS_WRITE)
            fallback_path = _write_streamed_triangle_soup_file(path, payload, mapping=handle)
            handle.seek(0)
            workspace_registry = _SHARED_MEMORY_WORKSPACES.setdefault(
                str(Path(workspace_key).resolve(strict=False)),
                {},
            )
            workspace_registry[mapping_name] = handle
            return shared_memory_mesh_path(mapping_name, byte_size, fallback_path)
        except MemoryError:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            raise
        except Exception:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

    return str(_write_streamed_triangle_soup_file(path, payload))


def read_triangle_soup_mesh(path: str | Path) -> MeshTransportData:
    source = Path(path)
    raw = source.read_bytes()
    if len(raw) < _HEADER.size:
        raise ValueError(f"Binary mesh header is incomplete: {source}")
    magic, triangle_count, reserved = _HEADER.unpack_from(raw, 0)
    is_v1 = magic == MBMESH_MAGIC_V1
    is_v2 = magic == MBMESH_MAGIC_V2
    is_v3 = magic == MBMESH_MAGIC_V3
    if not is_v1 and not is_v2 and not is_v3:
        raise ValueError(f"Binary mesh magic mismatch: {source}")
    if reserved != MBMESH_VERSION_RESERVED:
        raise ValueError(f"Binary mesh reserved field mismatch: {source}")

    cursor = _HEADER.size
    triangles: list[MeshTransportTriangle] = []
    for _triangle_index in range(int(triangle_count)):
        corners: list[MeshTransportCorner] = []
        for _corner_index in range(3):
            if is_v1:
                vertex_struct = _VERTEX_V1
            elif is_v3:
                vertex_struct = _VERTEX_V3
            else:
                vertex_struct = _VERTEX_V2
            end = cursor + vertex_struct.size
            if end > len(raw):
                raise ValueError(f"Binary mesh payload is truncated: {source}")
            if is_v1:
                position_x, position_y, position_z, normal_x, normal_y, normal_z, uv_u, uv_v = vertex_struct.unpack_from(raw, cursor)
                color_r, color_g, color_b = (1.0, 1.0, 1.0)
                paint_offset, paint_skew = _PAINT_OFFSET_DEFAULT, _PAINT_SKEW_DEFAULT
            elif is_v3:
                position_x, position_y, position_z, normal_x, normal_y, normal_z, uv_u, uv_v, color_r, color_g, color_b, paint_offset, paint_skew = vertex_struct.unpack_from(raw, cursor)
            else:
                position_x, position_y, position_z, normal_x, normal_y, normal_z, uv_u, uv_v, color_r, color_g, color_b = vertex_struct.unpack_from(raw, cursor)
                paint_offset, paint_skew = _PAINT_OFFSET_DEFAULT, _PAINT_SKEW_DEFAULT
            corners.append(
                MeshTransportCorner(
                    position=(position_x, position_y, position_z),
                    normal=(normal_x, normal_y, normal_z),
                    uv=(uv_u, uv_v),
                    color=(color_r, color_g, color_b),
                    paint_offset=paint_offset,
                    paint_skew=paint_skew,
                )
            )
            cursor = end
        triangles.append(MeshTransportTriangle(corners=tuple(corners)))

    if cursor != len(raw):
        raise ValueError(f"Binary mesh payload has unexpected trailing bytes: {source}")

    return MeshTransportData(triangle_count=int(triangle_count), triangles=triangles)
