from __future__ import annotations

import collections
import ctypes
from dataclasses import dataclass
import mmap
import os
from pathlib import Path
import struct
import sys
import threading
import time
import uuid

from . import rna_buffers
from . import backend_install
from . import floater_faces
from . import mesh_read
from . import mesh_transport


MAGIC = b"FYRGEOM1"
VERSION = 1
# Version 2 files store the normals section at the domain Blender keeps them in (see
# FLAG_NORMALS_POINT / FLAG_NORMALS_TRIANGLE); a file whose normals are per corner stays
# version 1 byte for byte. The backend reads both.
VERSION_NORMALS_DOMAIN = 2
_SUPPORTED_VERSIONS = (VERSION, VERSION_NORMALS_DOMAIN)
SCHEMA = "FYRGEOM1"
FLAG_CORNER_COLORS = 1
# Set whenever corner colours were REQUESTED and resolved, including the case where
# the mesh carried no usable colour attribute and the section was therefore omitted.
# FLAG_CORNER_COLORS alone cannot express that: it means "a section is present", and
# the reuse checks in high_mesh_cache keyed off it, so a colourless mesh rebuilt its
# canonical file on every single export. Older files lack this bit and keep the old
# behaviour. The backend validates only FLAG_CORNER_COLORS and ignores unknown bits.
FLAG_CORNER_COLORS_RESOLVED = 2
# The normals section holds one normal per VERTEX (indexed by the corner's position index).
# Lossless for a mesh whose ``normals_domain`` is POINT: Blender's corner normals there ARE
# the vertex normals, bit for bit.
FLAG_NORMALS_POINT = 4
# One normal per TRIANGLE, shared by its three corners (a FACE-domain mesh: the corner
# normals are the face normals).
FLAG_NORMALS_TRIANGLE = 8
ALIGNMENT = 64
HEADER_SIZE = 192
_HEADER = struct.Struct("<8sIIQQQ" + "QQQ" * 4)
_BACKEND_COMPATIBLE = False
_CANONICAL_WRITE_LOCK = threading.Lock()
_CANONICAL_WRITE_TASKS: dict[str, tuple[threading.Thread, list[BaseException]]] = {}
_CANONICAL_WRITE_WORKSPACES: dict[str, set[str]] = {}
# The last exports' phase timings, newest last. One compact line per exported high is also
# printed to the Blender console ([MasterBaker] ...), the add-on's existing timing channel.
RECENT_EXPORT_TIMINGS: collections.deque = collections.deque(maxlen=64)


def format_export_timings(label: str, triangle_count: int, byte_size: int, phases: dict[str, float]) -> str:
    names = ("to_mesh", "section_create", "touch_test", "prefault", "positions_indices", "corner_normals", "corner_colors", "content_hash", "canonical_write")
    parts = [f"{name}={phases[name]:.0f}ms" for name in names if name in phases]
    return (
        f"export high {label}: {int(triangle_count)} tris, {int(byte_size) / 1048576.0:.0f} MiB, "
        + " ".join(parts)
    )


def log_export_timings(label: str, triangle_count: int, byte_size: int, phases: dict[str, float]) -> None:
    """Record and print one exported high's phase timings. No file access; never raises."""
    try:
        snapshot = dict(phases)
        RECENT_EXPORT_TIMINGS.append((label, int(triangle_count), int(byte_size), snapshot))
        print("[MasterBaker] " + format_export_timings(label, triangle_count, byte_size, snapshot))
    except Exception:
        pass


@dataclass(frozen=True, slots=True)
class IndexedGeometryTransport:
    mapping_name: str
    byte_size: int
    content_hash: str
    vertex_count: int
    triangle_count: int
    canonical_path: Path
    phase_timings_ms: dict[str, float]


@dataclass(frozen=True, slots=True)
class CanonicalPositionIndexView:
    positions: object
    indices: object
    vertex_count: int
    triangle_count: int


def map_canonical_positions_indices(path: str | Path) -> CanonicalPositionIndexView:
    """Memory-map the compact position/index sections of a verified FYRGEOM1 file."""
    import numpy as np

    source = Path(path)
    with source.open("rb") as stream:
        raw = stream.read(_HEADER.size)
    if len(raw) != _HEADER.size:
        raise ValueError("FYRGEOM1 header is truncated")
    values = _HEADER.unpack(raw)
    if values[0] != MAGIC or values[1] not in _SUPPORTED_VERSIONS or values[2] != HEADER_SIZE:
        raise ValueError("FYRGEOM1 header is incompatible")
    total_size = int(values[4])
    positions_offset, positions_bytes, vertex_count = map(int, values[6:9])
    indices_offset, indices_bytes, corner_count = map(int, values[9:12])
    if total_size != source.stat().st_size:
        raise ValueError("FYRGEOM1 file size does not match its header")
    if positions_bytes != vertex_count * 12 or indices_bytes != corner_count * 4 or corner_count % 3:
        raise ValueError("FYRGEOM1 position/index sections are invalid")
    return CanonicalPositionIndexView(
        positions=np.memmap(
            source, dtype="<f4", mode="r", offset=positions_offset,
            shape=(vertex_count, 3),
        ),
        indices=np.memmap(
            source, dtype="<u4", mode="r", offset=indices_offset,
            shape=(corner_count // 3, 3),
        ),
        vertex_count=vertex_count,
        triangle_count=corner_count // 3,
    )


_KILL_SWITCH_VALUES = {"0", "OFF", "FALSE", "NO", "DISABLED"}


def enabled() -> bool:
    """FYRGEOM1 indexed transport is the default for DXR bakes on Windows.

    ``FYR_BAKER_INDEXED_GEOMETRY=0`` (or OFF/FALSE/NO/DISABLED) is the kill switch that sends
    every high mesh back through the FYMESH triangle soup. Groups that need high UVs
    (masked highs, material bakes) keep FYMESH regardless; see ``export._export_high_mesh_refs``.
    ``_BACKEND_COMPATIBLE`` is only set when the probed backend speaks FYRGEOM1 AND the adapter
    can bake on the GPU, so a machine without DXR never takes this path.
    """
    if sys.platform != "win32":
        return False
    value = str(os.environ.get("FYR_BAKER_INDEXED_GEOMETRY", "") or "").strip().upper()
    return _BACKEND_COMPATIBLE and value not in _KILL_SWITCH_VALUES


def set_backend_compatible(value: bool) -> None:
    global _BACKEND_COMPATIBLE
    _BACKEND_COMPATIBLE = bool(value)


def _canonical_task_key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def wait_for_canonical_path(path: str | Path) -> None:
    key = _canonical_task_key(path)
    with _CANONICAL_WRITE_LOCK:
        task = _CANONICAL_WRITE_TASKS.get(key)
    if task is None:
        return
    thread, errors = task
    thread.join()
    with _CANONICAL_WRITE_LOCK:
        _CANONICAL_WRITE_TASKS.pop(key, None)
    if errors:
        raise RuntimeError(f"FYRGEOM1 canonical write failed: {errors[0]}")


def throttle_canonical_writes(limit: int = 2) -> None:
    """Main thread: wait until fewer than ``limit`` canonical writes are still running.

    Each running write holds its whole section (up to several GB of commit) until the file
    is on disk, so an export loop that does not retain its sections bounds them here."""
    while True:
        with _CANONICAL_WRITE_LOCK:
            alive = [(key, task[0]) for key, task in _CANONICAL_WRITE_TASKS.items() if task[0].is_alive()]
        if len(alive) < max(1, int(limit)):
            return
        alive[0][1].join()


def wait_for_workspace_canonical_writes(workspace_key: str | Path) -> None:
    workspace = _canonical_task_key(workspace_key)
    with _CANONICAL_WRITE_LOCK:
        paths = tuple(_CANONICAL_WRITE_WORKSPACES.pop(workspace, set()))
    for path in paths:
        wait_for_canonical_path(path)


def _align(value: int) -> int:
    return (int(value) + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def _file_backed_sections_enabled() -> bool:
    if sys.platform != "win32":
        return False
    raw = str(os.environ.get("FYR_BAKER_FILE_BACKED_SECTIONS", "1") or "1").strip().upper()
    return raw not in {"0", "OFF", "FALSE", "NO"}


_PREFAULT_MIN_BYTES = 8 * 1024 * 1024
_PREFAULT_THREADS = 3
_PREFAULT_MIN_STRIPE = 8 * 1024 * 1024


def _section_prefault_enabled() -> bool:
    raw = str(os.environ.get("FYR_BAKER_SECTION_PREFAULT", "1") or "1").strip().upper()
    return raw not in {"0", "OFF", "FALSE", "NO"}


def _start_section_prefault(np, handle, total_size: int):
    """Start helper threads that write a zero into every page of ``handle``.

    The strided numpy store runs without the GIL, so the threads keep going while the
    caller is inside a long Blender call. The caller must not write the section before
    :func:`_join_section_prefault` returns."""
    view = np.ndarray((total_size,), dtype=np.uint8, buffer=handle)
    stripe = max(_PREFAULT_MIN_STRIPE, -(-total_size // _PREFAULT_THREADS))
    stripe = -(-stripe // 4096) * 4096
    threads = []
    for begin in range(0, total_size, stripe):
        part = view[begin : min(begin + stripe, total_size) : 4096]
        thread = threading.Thread(
            target=part.fill, args=(0,), name="fyr-prefault", daemon=True
        )
        thread.start()
        threads.append(thread)
        del part
    del view
    return threads


def _join_section_prefault(threads) -> None:
    for thread in threads:
        thread.join()


def _build_normal_cache(mesh, normals_domain: str) -> None:
    """Make Blender compute the normals this section stores now, so the later read is a copy.

    Reading one element evaluates the whole cache; a bare ``len`` does not."""
    try:
        name = {"POINT": "vertex_normals", "FACE": "polygon_normals"}.get(normals_domain, "corner_normals")
        normals = getattr(mesh, name)
        if len(normals):
            normals[0].vector  # noqa: B018 - the access is the point
    except Exception:  # noqa: BLE001 - the later read computes it the old way
        pass


def _create_file_backed_section(directory: Path, total_size: int, mapping_name: str):
    """Windows: a named section backed by a new file in the canonical cache directory.

    A page-file-backed section charges its whole size to system commit for as long as
    any process maps it: Blender until the bake finishes, the worker until its idle
    release. On a 72M-triangle scene that was 3.7 GB of commit held through the bake,
    on top of a second full copy written to the canonical file. Backed by the file
    itself, the same bytes cost no commit, the OS writes them out lazily, and the
    canonical file needs no separate write. The file is opened with FILE_SHARE_DELETE
    so it can be renamed to its content-hash name (known only after the fill) while
    Blender and the worker still map it.

    Returns (mmap, temporary_path), or None when the file cannot be created."""
    from ctypes import wintypes
    import msvcrt

    directory.mkdir(parents=True, exist_ok=True)
    temporary_path = directory / f"{mapping_name}.section.tmp"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    set_pointer = kernel32.SetFilePointerEx
    set_pointer.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
    set_pointer.restype = wintypes.BOOL
    set_end = kernel32.SetEndOfFile
    set_end.argtypes = [wintypes.HANDLE]
    set_end.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    generic_read_write = 0x80000000 | 0x40000000
    share_all = 0x1 | 0x2 | 0x4  # READ | WRITE | DELETE
    create_new = 1
    file_attribute_normal = 0x80
    raw = create_file(str(temporary_path), generic_read_write, share_all, None, create_new, file_attribute_normal, None)
    if raw is None or raw == wintypes.HANDLE(-1).value:
        return None
    # Size the file without writing it: SetEndOfFile leaves the valid data length at 0,
    # so untouched pages read as zeros with no disk I/O (os.ftruncate on Windows would
    # write the zeros out).
    if not set_pointer(raw, int(total_size), None, 0) or not set_end(raw):
        close_handle(raw)
        try:
            temporary_path.unlink()
        except OSError:
            pass
        return None
    fd = msvcrt.open_osfhandle(raw, os.O_RDWR | getattr(os, "O_BINARY", 0))
    try:
        handle = mmap.mmap(fd, total_size, tagname=mapping_name, access=mmap.ACCESS_WRITE)
    except BaseException:
        os.close(fd)
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    # mmap duplicated the file handle; the section keeps the file open until it closes.
    os.close(fd)
    return handle, temporary_path


def inspect_canonical_file(path: str | Path) -> tuple[int, str]:
    source = Path(path)
    with source.open("rb") as stream:
        raw = stream.read(_HEADER.size)
    if len(raw) != _HEADER.size:
        raise ValueError("FYRGEOM1 header is truncated")
    values = _HEADER.unpack(raw)
    if values[0] != MAGIC or values[1] not in _SUPPORTED_VERSIONS or values[2] != HEADER_SIZE:
        raise ValueError("FYRGEOM1 header is incompatible")
    total_size = int(values[4])
    if total_size != source.stat().st_size:
        raise ValueError("FYRGEOM1 file size does not match its header")
    return total_size, f"xxh3:{int(values[5]):016x}"


def _stored_normals_domain(mesh) -> str:
    """POINT / FACE / CORNER: the domain the section stores this mesh's normals at.

    Blender reports ``normals_domain`` POINT when every corner normal is its vertex's normal
    (smooth, no sharp edges, no custom normals) and FACE when every corner normal is its
    face's normal (all flat); the corner normals are then those arrays gathered, bit for bit
    (checked on every POINT/FACE mesh of Uzi_002 and the regression scenes), so storing the
    vertex or face array is lossless and 3x or 2x smaller than three normals per triangle.
    FYR_BAKER_FYRGEOM_NORMALS_DOMAIN=0 writes per-corner normals always.
    """
    if str(os.environ.get("FYR_BAKER_FYRGEOM_NORMALS_DOMAIN", "") or "").strip().upper() in {
        "0", "OFF", "FALSE", "NO", "DISABLED",
    }:
        return "CORNER"
    domain = str(getattr(mesh, "normals_domain", "CORNER") or "CORNER").upper()
    if domain == "POINT" and hasattr(mesh, "vertex_normals"):
        return "POINT"
    if domain == "FACE" and hasattr(mesh, "polygon_normals"):
        return "FACE"
    return "CORNER"


def _usable_color_attribute(mesh):
    """The colour attribute write_canonical would actually read, or None.

    Must stay byte-identical in its accept/reject decision to the fill branch below:
    anything this rejects is a mesh whose colours would have been written as solid
    white, and the whole point is to not write those.
    """
    color_attributes = getattr(mesh, "color_attributes", None)
    if color_attributes is None:
        return None
    active_color = getattr(color_attributes, "active_color", None)
    if active_color is None:
        active_color = getattr(color_attributes, "active", None)
    color_data = getattr(active_color, "data", None)
    color_type = str(getattr(active_color, "data_type", "") or "").upper()
    if (
        color_data is None
        or color_type not in {"FLOAT_COLOR", "BYTE_COLOR"}
        or not hasattr(color_data, "foreach_get")
    ):
        return None
    return active_color


def canonical_colors_resolved(path: str | Path) -> bool:
    """Were corner colours resolved for this file (present, or absent-because-none)?"""
    source = Path(path)
    try:
        with source.open("rb") as stream:
            raw = stream.read(_HEADER.size)
    except OSError:
        return False
    if len(raw) != _HEADER.size:
        return False
    values = _HEADER.unpack(raw)
    if values[0] != MAGIC or values[1] not in _SUPPORTED_VERSIONS:
        return False
    return bool(int(values[3]) & (FLAG_CORNER_COLORS | FLAG_CORNER_COLORS_RESOLVED))


#: Byte offset of the 64-bit flags field, derived from the header layout rather than
#: hardcoded so it follows _HEADER if the leading fields ever change.
_FLAGS_OFFSET = struct.calcsize("<8sII")


def mark_canonical_colors_resolved(path: str | Path) -> bool:
    """Set FLAG_CORNER_COLORS_RESOLVED on a canonical file that already exists.

    A mesh with no usable colour attribute hashes to the SAME content whether or
    not colours were requested, because the section is omitted either way. So an
    export that asks for colours reuses the file an earlier colourless export
    wrote, the canonical write is skipped, and the freshly computed flags never
    reach disk. high_mesh_cache then fails ``canonical_colors_resolved`` forever
    and rebuilds that canonical file on every single export.

    Only this metadata bit changes. The section bytes are identical by
    construction (same content hash), and the backend validates only
    FLAG_CORNER_COLORS and ignores unknown bits, so a concurrent reader sees
    either the old or the new flags and both are valid.
    """
    target = Path(path)
    try:
        with target.open("r+b") as stream:
            raw = stream.read(_HEADER.size)
            if len(raw) != _HEADER.size:
                return False
            values = _HEADER.unpack(raw)
            if values[0] != MAGIC or values[1] not in _SUPPORTED_VERSIONS:
                return False
            flags = int(values[3])
            if flags & FLAG_CORNER_COLORS_RESOLVED:
                return True
            stream.seek(_FLAGS_OFFSET)
            stream.write(struct.pack("<Q", flags | FLAG_CORNER_COLORS_RESOLVED))
            stream.flush()
        return True
    except OSError:
        return False


def canonical_has_corner_colors(path: str | Path) -> bool:
    source = Path(path)
    with source.open("rb") as stream:
        raw = stream.read(_HEADER.size)
    if len(raw) != _HEADER.size:
        return False
    values = _HEADER.unpack(raw)
    return (
        values[0] == MAGIC
        and values[1] in _SUPPORTED_VERSIONS
        and bool(int(values[3]) & FLAG_CORNER_COLORS)
    )


def write_temporary_fymesh(
    canonical_path: str | Path,
    destination: str | Path,
    *,
    cancel_check=None,
    chunk_corners: int = 262_144,
) -> Path:
    """Stream a canonical FYRGEOM1 blob into a bounded-memory FYMESH fallback.

    This is intentionally used only after a named-section mapping error. It
    never constructs a full triangle-soup payload and writes atomically so a
    cancelled/failed conversion cannot be mistaken for a valid retry file.
    """
    import numpy as np

    source = Path(canonical_path)
    target = mesh_transport.binary_mesh_path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + f".{uuid.uuid4().hex}.tmp")
    with source.open("rb") as stream:
        raw_header = stream.read(_HEADER.size)
    if len(raw_header) != _HEADER.size:
        raise ValueError("FYRGEOM1 fallback source header is truncated")
    values = _HEADER.unpack(raw_header)
    (
        magic,
        version,
        header_size,
        flags,
        total_size,
        _content_hash,
        positions_offset,
        positions_bytes,
        vertex_count,
        indices_offset,
        indices_bytes,
        corner_count,
        normals_offset,
        normals_bytes,
        normal_count,
        colors_offset,
        colors_bytes,
        color_count,
    ) = values
    if magic != MAGIC or version not in _SUPPORTED_VERSIONS or header_size != HEADER_SIZE:
        raise ValueError("FYRGEOM1 fallback source is incompatible")
    if int(total_size) != source.stat().st_size:
        raise ValueError("FYRGEOM1 fallback source size mismatch")
    if int(corner_count) % 3:
        raise ValueError("FYRGEOM1 fallback source has a non-triangular index count")
    normals_point = bool(int(flags) & FLAG_NORMALS_POINT)
    normals_triangle = bool(int(flags) & FLAG_NORMALS_TRIANGLE)
    expected_normal_count = (
        int(vertex_count) if normals_point else int(corner_count) // 3 if normals_triangle else int(corner_count)
    )
    if int(normal_count) != expected_normal_count:
        raise ValueError("FYRGEOM1 fallback source normal count mismatch")
    if int(positions_bytes) != int(vertex_count) * 12:
        raise ValueError("FYRGEOM1 fallback source position section mismatch")
    if int(indices_bytes) != int(corner_count) * 4:
        raise ValueError("FYRGEOM1 fallback source index section mismatch")
    if int(normals_bytes) != expected_normal_count * 12:
        raise ValueError("FYRGEOM1 fallback source normal section mismatch")
    has_colors = bool(int(flags) & FLAG_CORNER_COLORS)
    if has_colors and (
        int(color_count) != int(corner_count)
        or int(colors_bytes) != int(corner_count) * 12
    ):
        raise ValueError("FYRGEOM1 fallback source color section mismatch")

    positions = np.memmap(
        source, dtype="<f4", mode="r", offset=int(positions_offset),
        shape=(int(vertex_count), 3),
    )
    indices = np.memmap(
        source, dtype="<u4", mode="r", offset=int(indices_offset),
        shape=(int(corner_count),),
    )
    normals = np.memmap(
        source, dtype="<f4", mode="r", offset=int(normals_offset),
        shape=(expected_normal_count, 3),
    )
    colors = (
        np.memmap(
            source, dtype="<f4", mode="r", offset=int(colors_offset),
            shape=(int(corner_count), 3),
        )
        if has_colors
        else None
    )
    try:
        magic_out = (
            mesh_transport.MBMESH_MAGIC_V2
            if has_colors
            else mesh_transport.MBMESH_MAGIC_V4
        )
        floats_per_corner = 11 if has_colors else 6
        scratch_count = max(1, int(chunk_corners))
        scratch = np.empty((scratch_count, floats_per_corner), dtype="<f4")
        with temporary.open("wb") as stream:
            stream.write(
                struct.pack(
                    "<8sII",
                    magic_out,
                    int(corner_count) // 3,
                    mesh_transport.MBMESH_VERSION_RESERVED,
                )
            )
            for begin in range(0, int(corner_count), scratch_count):
                if cancel_check is not None and cancel_check():
                    raise InterruptedError("FYRGEOM1 fallback conversion cancelled")
                end = min(begin + scratch_count, int(corner_count))
                count = end - begin
                chunk = scratch[:count]
                chunk[:, 0:3] = positions[indices[begin:end]]
                if normals_point:
                    chunk[:, 3:6] = normals[indices[begin:end]]
                elif normals_triangle:
                    chunk[:, 3:6] = normals[np.arange(begin, end) // 3]
                else:
                    chunk[:, 3:6] = normals[begin:end]
                if has_colors:
                    chunk[:, 6:8] = 0.0
                    chunk[:, 8:11] = colors[begin:end]
                stream.write(memoryview(chunk).cast("B"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        return target
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        del positions, indices, normals
        if colors is not None:
            del colors


#: Native XXH3. Not interchangeable with a Python hash: the content hash it
#: produces is written into the FYRGEOM1 header and the backend RECOMPUTES and
#: compares it (backend_indexed_high_mesh.cpp), so substituting another
#: algorithm would make every transported mesh fail validation.
HASH_LIBRARY_FILENAME = "fyr_geometry_hash.dll"


_PACKAGED_HASH_LIBRARY: Path | None = None
_HASH_LIBRARY = None
_HASH_LIBRARY_LOCK = threading.Lock()


def _hash_library_path() -> Path:
    # The packaged path is looked up once per process (Path.resolve costs a syscall chain
    # and this ran once per transported mesh); a DLL that is missing is looked up again.
    global _PACKAGED_HASH_LIBRARY
    packaged = _PACKAGED_HASH_LIBRARY
    if packaged is not None:
        return packaged
    packaged = Path(__file__).resolve().parent / "bin" / "windows-x64" / HASH_LIBRARY_FILENAME
    if packaged.exists():
        _PACKAGED_HASH_LIBRARY = packaged
        return packaged
    # No native payload in the archive: this is the Superhive build, where the
    # hash library arrives with the backend installer. Only reached when a
    # backend is in play at all, since the Cycles path never transports indexed
    # geometry.
    installed = backend_install.find_payload_file(HASH_LIBRARY_FILENAME)
    if installed is not None:
        return installed
    development = Path(__file__).resolve().parents[1] / "backend" / "build" / "Release" / HASH_LIBRARY_FILENAME
    return development


def _load_hash_library():
    global _HASH_LIBRARY
    library = _HASH_LIBRARY
    if library is not None:
        return library
    with _HASH_LIBRARY_LOCK:
        if _HASH_LIBRARY is None:
            _HASH_LIBRARY = _load_hash_library_uncached()
        return _HASH_LIBRARY


def _load_hash_library_uncached():
    library = ctypes.CDLL(str(_hash_library_path()))
    library.fyr_xxh3_64bits.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    library.fyr_xxh3_64bits.restype = ctypes.c_uint64
    library.fyr_xxh3_create.restype = ctypes.c_void_p
    library.fyr_xxh3_update.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t)
    library.fyr_xxh3_update.restype = ctypes.c_int
    library.fyr_xxh3_digest.argtypes = (ctypes.c_void_p,)
    library.fyr_xxh3_digest.restype = ctypes.c_uint64
    library.fyr_xxh3_free.argtypes = (ctypes.c_void_p,)
    return library


def xxh3_text_hex(value: str) -> str:
    raw = str(value).encode("utf-8")
    library = _load_hash_library()
    buffer = ctypes.create_string_buffer(raw)
    return f"{int(library.fyr_xxh3_64bits(buffer, len(raw))):016x}"


def _hash_mapped_ranges(
    handle: mmap.mmap,
    ranges: tuple[tuple[int, int], ...],
    *,
    cancel_check=None,
) -> int:
    library = _load_hash_library()
    state = library.fyr_xxh3_create()
    if not state:
        raise MemoryError("Unable to allocate XXH3 state")
    try:
        for offset, byte_size in ranges:
            if not byte_size:
                continue
            for begin in range(0, byte_size, 16 * 1024 * 1024):
                if cancel_check is not None and cancel_check():
                    raise InterruptedError("FYRGEOM1 section fill cancelled")
                chunk_size = min(16 * 1024 * 1024, byte_size - begin)
                buffer = (ctypes.c_ubyte * chunk_size).from_buffer(
                    handle, offset + begin
                )
                try:
                    if library.fyr_xxh3_update(
                        state, ctypes.addressof(buffer), chunk_size
                    ) != 0:
                        raise RuntimeError("XXH3 update failed")
                finally:
                    del buffer
        return int(library.fyr_xxh3_digest(state))
    finally:
        library.fyr_xxh3_free(state)


def _acquire_evaluated_mesh(obj, depsgraph):
    # Always a copy with its own caches, so reading it leaves nothing behind (see mesh_read).
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    if mesh is not None:
        mesh_read.detach_mesh_runtime_caches(mesh)
        floater_faces.filter_export_mesh(obj, mesh)
    return obj_eval, mesh, True


def create_evaluated_high_section(
    obj,
    depsgraph,
    workspace_key: str | Path,
    *,
    include_corner_colors: bool = False,
    # What fills the colour section (None = the active colour attribute). An
    # ATTRIBUTE source always writes the section: its "absent" value is black, not
    # the white every reader substitutes for a missing section.
    color_source=None,
    canonical_root: str | Path | None = None,
    evaluated_mesh=None,
    mesh_is_triangulated: bool = False,
    cancel_check=None,
    # False: the section is not registered under ``workspace_key``. Its only user is the
    # canonical writer thread, which holds it until the file is written (an export whose
    # only consumer is the canonical file, such as the cage fit's high scene).
    retain_section: bool = True,
) -> IndexedGeometryTransport:
    """Fill FYRGEOM1 directly in a pagefile-backed named section.

    Positions and triangle indices are written into their final mapped arrays.
    Blender's corner-normal collection API requires one loop-sized scratch array;
    conversion to triangle-corner order is then bounded to small chunks.
    """
    import numpy as np

    acquire_ms = 0.0
    if evaluated_mesh is None:
        acquire_started = time.perf_counter()
        obj_eval, mesh, temporary_mesh = _acquire_evaluated_mesh(obj, depsgraph)
        acquire_ms = (time.perf_counter() - acquire_started) * 1000.0
    else:
        obj_eval, mesh, temporary_mesh = evaluated_mesh
    if mesh is None:
        raise ValueError(f"Unable to evaluate mesh for {getattr(obj, 'name', '<unknown>')}")
    try:
        if cancel_check is not None and cancel_check():
            raise InterruptedError("FYRGEOM1 section fill cancelled")
        calc_started = time.perf_counter()
        calc_normals_split = getattr(mesh, "calc_normals_split", None)
        if callable(calc_normals_split):
            calc_normals_split()
        acquire_ms += (time.perf_counter() - calc_started) * 1000.0
        vertices = mesh.vertices
        loops = mesh.loops
        # An all-triangle mesh (every FBX/OBJ high) needs no loop-triangle table: triangle i
        # is corners 3i..3i+2, so the corner attributes are read as they are (mesh_read).
        all_triangles = mesh_read.is_all_triangles(mesh)
        triangles = None
        if all_triangles:
            triangle_count = len(mesh.polygons)
        else:
            if not mesh_is_triangulated:
                mesh.calc_loop_triangles()
            triangles = mesh.loop_triangles
            triangle_count = len(triangles)

        def _loop_triangles():
            nonlocal triangles
            if triangles is None:
                mesh.calc_loop_triangles()
                triangles = mesh.loop_triangles
            return triangles

        vertex_count = len(vertices)
        corner_count = triangle_count * 3
        if triangle_count <= 0 or vertex_count <= 0:
            raise ValueError("Evaluated high mesh has no triangles")

        # Decide colours from the MESH, not only from the project setting. The old code
        # sized a full corner_count*12 section off include_corner_colors alone and then
        # filled it with solid white when the mesh had no colour attribute -- 40% of every
        # canonical file, and the same bytes again in the D3D12 upload heap. Every consumer
        # already substitutes white for an empty section (backend_geometry's c[3] init,
        # backend_mesh_io's else branch, the GPU path's fallback_color), so dropping it is
        # bit-identical rather than merely close.
        # FYR_BAKER_FYRGEOM_CONSTANT_COLORS=1 restores the old behaviour (always write the
        # section, filled with white) so the two can be measured against each other.
        _keep_constant_colors = str(
            os.environ.get("FYR_BAKER_FYRGEOM_CONSTANT_COLORS", "") or ""
        ).strip() in {"1", "ON", "TRUE", "YES"}
        attribute_source = (
            color_source
            if color_source is not None and not color_source.is_active_color
            else None
        )
        store_corner_colors = bool(include_corner_colors) and (
            attribute_source is not None
            or _keep_constant_colors
            or _usable_color_attribute(mesh) is not None
        )

        positions_offset = HEADER_SIZE
        positions_bytes = vertex_count * 12
        indices_offset = _align(positions_offset + positions_bytes)
        indices_bytes = corner_count * 4
        normals_offset = _align(indices_offset + indices_bytes)
        normals_domain = _stored_normals_domain(mesh)
        normal_count = (
            vertex_count if normals_domain == "POINT"
            else triangle_count if normals_domain == "FACE"
            else corner_count
        )
        normals_bytes = normal_count * 12
        colors_offset = _align(normals_offset + normals_bytes)
        colors_bytes = corner_count * 12 if store_corner_colors else 0
        total_size = _align(colors_offset + colors_bytes)

        section_started = time.perf_counter()
        mapping_name = f"FyrGeom_{uuid.uuid4().hex}"
        section_temporary_path: Path | None = None
        file_backed = None
        if canonical_root is not None and _file_backed_sections_enabled():
            try:
                file_backed = _create_file_backed_section(Path(canonical_root), total_size, mapping_name)
            except Exception as exc:
                print(f"[MasterBaker] file-backed FYRGEOM1 section unavailable, using the page file: {exc!r}")
                file_backed = None
        if file_backed is not None:
            handle, section_temporary_path = file_backed
        else:
            handle = mmap.mmap(-1, total_size, tagname=mapping_name, access=mmap.ACCESS_WRITE)
        try:
            phase_timings: dict[str, float] = {
                "to_mesh": acquire_ms,
                "section_create": (time.perf_counter() - section_started) * 1000.0,
            }
            if os.environ.get("OV_TOUCH_TEST"):
                _t0 = time.perf_counter()
                _a = np.ndarray((total_size,), dtype=np.uint8, buffer=handle)
                _a[::4096] = 0
                del _a
                phase_timings["touch_test"] = (time.perf_counter() - _t0) * 1000.0
            elif _section_prefault_enabled() and total_size >= _PREFAULT_MIN_BYTES:
                # First touch of a fresh section costs about as much as the copy into it
                # (a page fault per 4 KiB). Touch every page from helper threads while this
                # thread has Blender build the corner-normal cache, which does not write
                # the section. Nothing is written to the section by this thread until the
                # helpers are joined, so the zeros they store cannot overwrite data.
                _t0 = time.perf_counter()
                _touch_threads = _start_section_prefault(np, handle, total_size)
                try:
                    _build_normal_cache(mesh, normals_domain)
                finally:
                    _join_section_prefault(_touch_threads)
                phase_timings["prefault"] = (time.perf_counter() - _t0) * 1000.0
            export_label = str(getattr(obj, "name", "") or "")
            canonical_thread = None
            # Native-format dtypes (float32 / intc / uintc), not "<f4" / "<u4": foreach_get's
            # memcpy path needs the buffer format to equal the property's (see mesh_read).
            positions = np.ndarray((vertex_count, 3), dtype=np.float32, buffer=handle, offset=positions_offset)
            indices = np.ndarray((corner_count,), dtype=np.intc, buffer=handle, offset=indices_offset)
            normals = np.ndarray((normal_count, 3), dtype=np.float32, buffer=handle, offset=normals_offset)

            if cancel_check is not None and cancel_check():
                raise InterruptedError("FYRGEOM1 section fill cancelled")
            phase_started = time.perf_counter()
            if not mesh_read.read_positions_flat(mesh, positions.reshape(-1)):
                vertices.foreach_get("co", positions.reshape(-1))
            if not (all_triangles and mesh_read.read_corner_verts_flat(mesh, indices)):
                _loop_triangles().foreach_get(
                    "vertices",
                    np.ndarray((corner_count,), dtype=np.uintc, buffer=handle, offset=indices_offset),
                )
            phase_timings["positions_indices"] = (
                time.perf_counter() - phase_started
            ) * 1000.0

            chunk_size = 1_048_576
            # MeshLoopTriangle exposes the evaluated custom split normals in
            # triangle-corner order. Writing that property directly into the
            # final section avoids both the loop-sized normal scratch and the
            # corner gather, and preserves Blender's float32 values exactly.
            phase_started = time.perf_counter()
            if normals_domain == "POINT":
                mesh.vertex_normals.foreach_get("vector", normals.reshape(-1))
            elif normals_domain == "FACE":
                if all_triangles:
                    mesh.polygon_normals.foreach_get("vector", normals.reshape(-1))
                else:
                    face_normals = np.empty((len(mesh.polygons), 3), dtype=np.float32)
                    mesh.polygon_normals.foreach_get("vector", face_normals.reshape(-1))
                    triangle_faces = np.empty((triangle_count,), dtype=np.intc)
                    _loop_triangles().foreach_get("polygon_index", triangle_faces)
                    for begin in range(0, triangle_count, chunk_size):
                        if cancel_check is not None and cancel_check():
                            raise InterruptedError("FYRGEOM1 section fill cancelled")
                        end = min(begin + chunk_size, triangle_count)
                        normals[begin:end] = face_normals[triangle_faces[begin:end]]
            try:
                if normals_domain == "CORNER" and not (
                    all_triangles and mesh_read.read_corner_normals_flat(mesh, normals.reshape(-1))
                ):
                    _loop_triangles().foreach_get("split_normals", normals.reshape(-1))
            except (AttributeError, TypeError, ValueError):
                triangle_loops = rna_buffers.empty_u32_for_rna(corner_count)
                _loop_triangles().foreach_get("loops", triangle_loops)
                triangle_loops = rna_buffers.as_i32(triangle_loops)
                loop_normals = np.empty((len(loops), 3), dtype=np.float32)
                corner_normals = getattr(mesh, "corner_normals", None)
                if corner_normals is not None and hasattr(corner_normals, "foreach_get"):
                    corner_normals.foreach_get("vector", loop_normals.reshape(-1))
                else:
                    loops.foreach_get("normal", loop_normals.reshape(-1))
                for begin in range(0, corner_count, chunk_size):
                    if cancel_check is not None and cancel_check():
                        raise InterruptedError("FYRGEOM1 section fill cancelled")
                    end = min(begin + chunk_size, corner_count)
                    normals[begin:end] = loop_normals[
                        triangle_loops[begin:end]
                    ]
            phase_timings["corner_normals"] = (
                time.perf_counter() - phase_started
            ) * 1000.0

            flags = 0
            if normals_domain == "POINT":
                flags |= FLAG_NORMALS_POINT
            elif normals_domain == "FACE":
                flags |= FLAG_NORMALS_TRIANGLE
            if include_corner_colors:
                flags |= FLAG_CORNER_COLORS_RESOLVED
            if store_corner_colors:
                phase_started = time.perf_counter()
                flags |= FLAG_CORNER_COLORS
                colors = np.ndarray((corner_count, 3), dtype="<f4", buffer=handle, offset=colors_offset)
                active_color = _usable_color_attribute(mesh) if attribute_source is None else None
                color_data = getattr(active_color, "data", None)
                if attribute_source is not None:
                    from . import color_stream

                    stream_domain, stream_rows = color_stream.attribute_stream_rows(mesh, attribute_source)
                    if stream_domain == "POINT":
                        source_indices = indices
                    else:
                        source_indices = rna_buffers.empty_u32_for_rna(corner_count)
                        _loop_triangles().foreach_get("loops", source_indices)
                        source_indices = rna_buffers.as_i32(source_indices)
                    for begin in range(0, corner_count, chunk_size):
                        if cancel_check is not None and cancel_check():
                            raise InterruptedError("FYRGEOM1 section fill cancelled")
                        end = min(begin + chunk_size, corner_count)
                        colors[begin:end] = stream_rows[source_indices[begin:end]]
                elif color_data is None:
                    # Only reachable under FYR_BAKER_FYRGEOM_CONSTANT_COLORS=1, which forces
                    # the section on for A/B comparison against the old behaviour.
                    colors.fill(1.0)
                else:
                    triangle_loops = rna_buffers.empty_u32_for_rna(corner_count)
                    _loop_triangles().foreach_get("loops", triangle_loops)
                    triangle_loops = rna_buffers.as_i32(triangle_loops)
                    source_colors = np.empty((len(color_data), 4), dtype=np.float32)
                    color_data.foreach_get("color", source_colors.reshape(-1))
                    color_domain = str(
                        getattr(active_color, "domain", "CORNER") or "CORNER"
                    ).upper()
                    source_indices = indices if color_domain == "POINT" else triangle_loops
                    for begin in range(0, corner_count, chunk_size):
                        if cancel_check is not None and cancel_check():
                            raise InterruptedError(
                                "FYRGEOM1 section fill cancelled"
                            )
                        end = min(begin + chunk_size, corner_count)
                        colors[begin:end] = np.clip(
                            source_colors[source_indices[begin:end], :3],
                            0.0,
                            1.0,
                        )
                phase_timings["corner_colors"] = (
                    time.perf_counter() - phase_started
                ) * 1000.0

            ranges = (
                (positions_offset, positions_bytes),
                (indices_offset, indices_bytes),
                (normals_offset, normals_bytes),
                (colors_offset, colors_bytes),
            )
            phase_started = time.perf_counter()
            content_hash_u64 = _hash_mapped_ranges(
                handle, ranges, cancel_check=cancel_check
            )
            phase_timings["content_hash"] = (
                time.perf_counter() - phase_started
            ) * 1000.0
            header = _HEADER.pack(
                MAGIC,
                VERSION if normals_domain == "CORNER" else VERSION_NORMALS_DOMAIN,
                HEADER_SIZE,
                flags,
                total_size,
                content_hash_u64,
                positions_offset,
                positions_bytes,
                vertex_count,
                indices_offset,
                indices_bytes,
                corner_count,
                normals_offset,
                normals_bytes,
                normal_count,
                colors_offset if colors_bytes else 0,
                colors_bytes,
                corner_count if colors_bytes else 0,
            )
            handle[: len(header)] = header
            if len(header) < HEADER_SIZE:
                handle[len(header) : HEADER_SIZE] = b"\0" * (HEADER_SIZE - len(header))
            if section_temporary_path is None:
                # A file-backed section must not flush here: FlushViewOfFile writes the
                # whole file synchronously. The OS writes it out lazily instead.
                handle.flush()
            canonical_base = Path(canonical_root) if canonical_root is not None else Path()
            canonical_path = (
                canonical_base / content_hash_u64.to_bytes(8, "big").hex()[:2] / f"{content_hash_u64:016x}.fyrgeom"
                if canonical_root is not None
                else Path()
            )
            if canonical_root is not None and canonical_path.exists() and include_corner_colors:
                # Reusing a file an earlier colourless export wrote: the write below is
                # skipped, so carry the resolved bit over or the reuse check fails forever.
                mark_canonical_colors_resolved(canonical_path)
            if section_temporary_path is not None:
                # The section IS the file: publish it under its content-hash name (a rename,
                # no copy), or drop it when an identical canonical file already exists. Both
                # work while mapped (FILE_SHARE_DELETE); a deleted file goes away when the
                # last view of the section closes.
                phase_started = time.perf_counter()
                published = False
                if not canonical_path.exists():
                    try:
                        canonical_path.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(section_temporary_path, canonical_path)
                        published = True
                    except OSError as exc:
                        print(f"[MasterBaker] could not publish canonical FYRGEOM1 {canonical_path.name}: {exc!r}")
                if not published:
                    try:
                        os.remove(section_temporary_path)
                    except OSError:
                        pass
                phase_timings["canonical_write"] = (time.perf_counter() - phase_started) * 1000.0
            elif canonical_root is not None and not canonical_path.exists():
                canonical_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = canonical_path.with_name(canonical_path.name + f".{uuid.uuid4().hex}.tmp")
                write_errors: list[BaseException] = []
                phase_started = time.perf_counter()

                def _write_canonical() -> None:
                    try:
                        with temporary_path.open("wb") as stream:
                            view = memoryview(handle)
                            try:
                                for begin in range(0, total_size, 16 * 1024 * 1024):
                                    if cancel_check is not None and cancel_check():
                                        raise InterruptedError(
                                            "FYRGEOM1 canonical write cancelled"
                                        )
                                    stream.write(view[begin : min(begin + 16 * 1024 * 1024, total_size)])
                                stream.flush()
                            finally:
                                view.release()
                        try:
                            temporary_path.replace(canonical_path)
                        except FileExistsError:
                            temporary_path.unlink(missing_ok=True)
                    except BaseException as exc:
                        temporary_path.unlink(missing_ok=True)
                        write_errors.append(exc)
                    finally:
                        phase_timings["canonical_write"] = (
                            time.perf_counter() - phase_started
                        ) * 1000.0
                        # The write finishes after create_evaluated_high_section returned, so
                        # the line with every phase is printed here, not at the return.
                        log_export_timings(export_label, triangle_count, total_size, phase_timings)

                canonical_thread = threading.Thread(
                    target=_write_canonical,
                    name=f"fyr-canonical-{content_hash_u64:016x}",
                    daemon=True,
                )
                canonical_key = _canonical_task_key(canonical_path)
                workspace_task_key = _canonical_task_key(workspace_key)
                with _CANONICAL_WRITE_LOCK:
                    _CANONICAL_WRITE_TASKS[canonical_key] = (
                        canonical_thread,
                        write_errors,
                    )
                    _CANONICAL_WRITE_WORKSPACES.setdefault(
                        workspace_task_key, set()
                    ).add(canonical_key)
                canonical_thread.start()
            del positions, indices, normals
            if canonical_thread is None:
                log_export_timings(export_label, triangle_count, total_size, phase_timings)
            if retain_section:
                mesh_transport.retain_workspace_shared_memory(workspace_key, mapping_name, handle)
            return IndexedGeometryTransport(
                mapping_name=mapping_name,
                byte_size=total_size,
                content_hash=f"xxh3:{content_hash_u64:016x}",
                vertex_count=vertex_count,
                triangle_count=triangle_count,
                canonical_path=canonical_path,
                phase_timings_ms=phase_timings,
            )
        except Exception:
            handle.close()
            if section_temporary_path is not None:
                try:
                    os.remove(section_temporary_path)
                except OSError:
                    pass
            raise
    finally:
        if temporary_mesh:
            obj_eval.to_mesh_clear()
