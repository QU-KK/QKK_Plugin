"""Client for ``fyr_cage_gpu.exe``: batched closest-hit rays against high-poly scenes on the GPU.

The automatic cage fit's ray check (``cage.raise_offsets_to_ray_reach``) needs, for millions of
rays, "how far to the nearest high surface, and does it face the ray". Answering that with
mathutils BVH trees costs one BVH build per high (GIL-bound) plus a Python call per ray. The tool
keeps a high scene as a DXR acceleration structure (built from the same ``.fymesh`` files the bake
reads) and answers whole arrays of rays, the way Toolbag's cageEstimate pass does.

This module only talks to the process. The fit itself lives in :mod:`cage_gpu_fit`.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

_MAGIC = 0x31474346  # 'FCG1'
_CMD_HELLO, _CMD_LOAD, _CMD_TRACE, _CMD_FREE, _CMD_QUIT, _CMD_FITBATCH, _CMD_PRELOAD, _CMD_STATS, _CMD_COVERBATCH = range(9)
_FREE_ALL = 0xFFFFFFFF
_REQUEST = struct.Struct("<IIIIQ")
_RESPONSE = struct.Struct("<IiIIQ")

ENV_ENABLE = "FYR_GPU_CAGE"
ENV_EXE = "FYR_CAGE_GPU_EXE"

#: Seconds without a request after which the tool drops its resident scenes and buffers (VRAM goes
#: back to the bake worker), and after which the process itself exits. Both restart lazily.
IDLE_RELEASE_SECONDS = 30.0
IDLE_EXIT_SECONDS = 120.0


class CageGpuError(RuntimeError):
    """The tool is missing, could not start, or answered with an error."""


def gpu_cage_enabled() -> bool:
    """The GPU cage fit is the default; ``FYR_GPU_CAGE=0`` (or off/false/no) is the kill switch.

    Whether it can actually run (tool installed, DXR adapter, no earlier failure) is decided by
    :func:`cage_gpu_fit.available`, and every failure falls back to the Python fit."""
    value = str(os.environ.get(ENV_ENABLE, "") or "").strip().upper()
    return value not in {"0", "OFF", "FALSE", "NO", "DISABLED"}


#: Found tool paths by override value: the lookup (resolve + stat) ran ~1500 times in a
#: 300-group bake's prepare (0.8 s). Only a path that exists is remembered, so a tool
#: installed or removed later is still noticed (a vanished file fails at launch, which
#: every caller already handles).
_EXE_FOUND: dict = {}


def executable_path() -> Path | None:
    override = os.environ.get(ENV_EXE) or ""
    cached = _EXE_FOUND.get(override)
    if cached is not None:
        return cached
    if override:
        path = Path(override)
    elif sys.platform != "win32":
        return None
    else:
        path = Path(__file__).resolve().parent / "bin" / "windows-x64" / "fyr_cage_gpu.exe"
    if path.is_file():
        _EXE_FOUND[override] = path
        return path
    return None


class CageGpuWorker:
    """One resident ``fyr_cage_gpu.exe``. Calls are serialized; the process is restarted lazily."""

    def __init__(self, exe: Path | None = None):
        self._exe = Path(exe) if exe is not None else executable_path()
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._next_scene = 1
        self.info: dict = {}
        #: Bumped on every (re)start and every release-all: scene ids from before are gone.
        self.generation = 0
        self._last_used = time.monotonic()
        self._holding = False  # scenes or buffers may be resident in the tool
        self._idle_thread: threading.Thread | None = None

    def start(self) -> dict:
        """Start the tool if it is not running (raises :class:`CageGpuError`); returns its HELLO info."""
        with self._lock:
            self._ensure_started()
            return dict(self.info)

    # -- process ----------------------------------------------------------------------------
    def _ensure_started(self) -> subprocess.Popen:
        process = self._process
        if process is not None and process.poll() is None:
            return process
        if self._exe is None or not self._exe.is_file():
            raise CageGpuError("fyr_cage_gpu.exe not found")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            [str(self._exe)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            bufsize=0,
        )
        self.info = {}
        self.generation += 1
        self._holding = False
        try:
            self.info = json.loads(self._call(_CMD_HELLO, 0, b"").decode("utf-8"))
        except Exception:
            self.close()
            raise
        self._ensure_idle_thread()
        return self._process

    # -- idle management --------------------------------------------------------------------
    def _ensure_idle_thread(self) -> None:
        thread = self._idle_thread
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(target=self._idle_loop, name="fyr-cage-gpu-idle", daemon=True)
        self._idle_thread = thread
        thread.start()

    def _idle_loop(self) -> None:
        while True:
            time.sleep(2.0)
            if not self._lock.acquire(blocking=False):
                continue  # a request is running
            try:
                process = self._process
                if process is None or process.poll() is not None:
                    self._idle_thread = None
                    return
                idle = time.monotonic() - self._last_used
                if idle >= IDLE_EXIT_SECONDS:
                    self.close()
                    self._idle_thread = None
                    return
                if idle >= IDLE_RELEASE_SECONDS and self._holding:
                    self._release_locked()
            finally:
                self._lock.release()

    def _release_locked(self) -> None:
        try:
            self._call(_CMD_FREE, _FREE_ALL, b"")
        except CageGpuError:
            return
        self._holding = False
        self.generation += 1  # scene ids handed out before are gone

    def release(self, *, wait: bool = False, timeout: float | None = None) -> bool:
        """Drop every resident scene and the tool's buffers (VRAM and host commit back to the bake
        worker).

        Skipped, and False returned, when a request is running and ``wait`` is false: the idle timer
        releases then. ``timeout`` (seconds) waits that long for a running request instead."""
        if timeout is not None:
            if not self._lock.acquire(timeout=max(0.0, float(timeout))):
                return False
        elif not self._lock.acquire(blocking=bool(wait)):
            return False
        try:
            process = self._process
            if process is None or process.poll() is not None or not self._holding:
                return True
            self._release_locked()
            return not self._holding
        finally:
            self._lock.release()

    def stats(self) -> dict:
        """The tool's own VRAM / RAM numbers (current and peak), cache size and limit, in MB."""
        with self._lock:
            self._ensure_started()
            return json.loads(self._call(_CMD_STATS, 0, b"").decode("utf-8"))

    def _read(self, size: int) -> bytes:
        chunks = []
        remaining = size
        stream = self._process.stdout
        while remaining > 0:
            chunk = stream.read(min(remaining, 1 << 24))
            if not chunk:
                raise CageGpuError("fyr_cage_gpu.exe closed its output")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _call(self, command: int, arg: int, payload) -> bytes:
        process = self._process
        self._last_used = time.monotonic()
        if command in (_CMD_LOAD, _CMD_TRACE, _CMD_FITBATCH, _CMD_PRELOAD):
            self._holding = True
        view = memoryview(payload)
        try:
            process.stdin.write(_REQUEST.pack(_MAGIC, command, arg, 0, view.nbytes))
            if view.nbytes:
                process.stdin.write(view)
            process.stdin.flush()
            magic, status, _r0, _r1, size = _RESPONSE.unpack(self._read(_RESPONSE.size))
            body = self._read(size) if size else b""
        except (OSError, ValueError) as error:
            self.close()
            raise CageGpuError(f"fyr_cage_gpu.exe is not responding: {error}") from error
        if magic != _MAGIC:
            self.close()
            raise CageGpuError("fyr_cage_gpu.exe sent a bad frame")
        self._last_used = time.monotonic()
        if status != 0:
            raise CageGpuError(body.decode("utf-8", "replace") or f"status {status}")
        return body

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=2.0)
        except Exception:
            try:
                process.kill()  # this process only, by handle
            except Exception:
                pass
        try:
            process.stdout.close()
        except Exception:
            pass

    # -- scenes -----------------------------------------------------------------------------
    def load_scene(self, meshes) -> tuple[int, dict]:
        """``meshes``: iterable of ``(fymesh path, 16 floats object-to-world, row-major)``.

        Returns ``(scene_id, report)``; the report carries triangles, read_ms, build_ms."""
        parts = [struct.pack("<I", 0)]
        count = 0
        for path, matrix in meshes:
            encoded = os.fspath(path).encode("utf-8")
            values = [float(v) for v in matrix]
            if len(values) != 16:
                raise ValueError("matrix must have 16 values")
            parts.append(struct.pack("<I", len(encoded)))
            parts.append(encoded)
            parts.append(struct.pack("<16f", *values))
            count += 1
        parts[0] = struct.pack("<I", count)
        payload = b"".join(parts)
        with self._lock:
            self._ensure_started()
            scene_id = self._next_scene
            self._next_scene += 1
            report = json.loads(self._call(_CMD_LOAD, scene_id, payload).decode("utf-8"))
        return scene_id, report

    def free_scene(self, scene_id: int) -> None:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                return
            try:
                self._call(_CMD_FREE, scene_id, b"")
            except CageGpuError:
                pass

    def trace(self, scene_id: int, rays):
        """Closest hit per ray. ``rays``: (N, 8) float32 ``ox oy oz tmin dx dy dz tmax``.

        Returns ``(distance, facing)`` float32 arrays; distance is -1 on a miss, facing is the
        dot of the hit surface's winding normal and the ray direction (negative = the ray meets
        the surface from its front, positive = from behind)."""
        import numpy as np

        rays = np.ascontiguousarray(rays, dtype="<f4")
        if rays.ndim != 2 or rays.shape[1] != 8:
            raise ValueError("rays must be (N, 8)")
        count = int(rays.shape[0])
        if count == 0:
            empty = np.zeros(0, dtype=np.float32)
            return empty, empty.copy()
        header = struct.pack("<I", count)
        with self._lock:
            self._ensure_started()
            body = self._call(_CMD_TRACE, scene_id, header + rays.tobytes())
        result = np.frombuffer(body, dtype="<f4").reshape(count, 2)
        return result[:, 0].copy(), result[:, 1].copy()

    def preload(self, scenes) -> None:
        """Ask the tool to build these high scenes in the background (returns at once).

        ``scenes``: iterable of mesh lists, each ``(fymesh path, 16 floats)`` entries as in
        :meth:`load_scene`. The scene builds then overlap the caller's own work, and a later
        :meth:`fit_batch` for the same meshes finds them resident."""
        parts = []
        count = 0
        for meshes in scenes:
            meshes = list(meshes)
            parts.append(struct.pack("<I", len(meshes)))
            for path, matrix in meshes:
                encoded = os.fspath(path).encode("utf-8")
                parts.append(struct.pack("<I", len(encoded)))
                parts.append(encoded)
                parts.append(struct.pack("<16f", *[float(v) for v in matrix]))
            count += 1
        if not count:
            return
        with self._lock:
            self._ensure_started()
            self._call(_CMD_PRELOAD, 0, struct.pack("<I", count) + b"".join(parts))

    def fit_batch(self, jobs):
        """Run the whole ray check natively for several groups in ONE request.

        ``jobs``: iterable of dicts with ``meshes`` (``(fymesh path, 16 floats)`` list), ``key_index``
        (T, 3) int32, ``positions`` / ``normals`` (T, 3, 3) float32, ``original`` (K,) float32 and
        ``params`` (window, wide_window, margin, ceiling, slope, edge_factor, slope_iterations, passes).
        Scenes stay resident in the tool (LRU by VRAM budget), so a high shared by several fits, or a
        second fit of the same group, loads once. Returns one dict per job: ``offsets`` (K,) float32
        plus ``stats`` (raised, reverted, short, samples, after_dense, after_slope, after_revert,
        rays, trace_calls) and ``load_ms`` / ``fit_ms``."""
        import numpy as np

        jobs = list(jobs)
        parts = [struct.pack("<I", len(jobs))]
        for job in jobs:
            meshes = list(job["meshes"])
            parts.append(struct.pack("<I", len(meshes)))
            for path, matrix in meshes:
                encoded = os.fspath(path).encode("utf-8")
                values = [float(v) for v in matrix]
                if len(values) != 16:
                    raise ValueError("matrix must have 16 values")
                parts.append(struct.pack("<I", len(encoded)))
                parts.append(encoded)
                parts.append(struct.pack("<16f", *values))
            key_index = np.ascontiguousarray(job["key_index"], dtype="<i4")
            positions = np.ascontiguousarray(job["positions"], dtype="<f4")
            normals = np.ascontiguousarray(job["normals"], dtype="<f4")
            original = np.ascontiguousarray(job["original"], dtype="<f4")
            window, wide, margin, ceiling, slope, edge_factor, slope_iterations, passes = job["params"]
            parts.append(struct.pack("<II", int(key_index.shape[0]), int(original.shape[0])))
            parts.append(
                struct.pack(
                    "<6f2i", window, wide, margin, ceiling, slope, edge_factor, int(slope_iterations), int(passes)
                )
            )
            parts.append(key_index.tobytes())
            parts.append(positions.tobytes())
            parts.append(normals.tobytes())
            parts.append(original.tobytes())
        payload = b"".join(parts)
        with self._lock:
            self._ensure_started()
            body = self._call(_CMD_FITBATCH, 0, payload)
        (count,) = struct.unpack_from("<I", body, 0)
        cursor = 4
        results = []
        for _ in range(count):
            (key_count,) = struct.unpack_from("<I", body, cursor)
            cursor += 4
            stats = struct.unpack_from("<9I", body, cursor)
            cursor += 36
            load_ms, fit_ms = struct.unpack_from("<2f", body, cursor)
            cursor += 8
            offsets = np.frombuffer(body, dtype="<f4", count=key_count, offset=cursor).copy()
            cursor += key_count * 4
            results.append({"offsets": offsets, "stats": stats, "load_ms": load_ms, "fit_ms": fit_ms})
        return results

    def coverage_batch(self, items):
        """The plain coverage fit's nearest-face binding, natively, for several partitions at once.

        ``items``: iterable of dicts with ``meshes`` (``(fymesh path, 16 floats)`` list: the highs the
        partition fits against), ``key_index`` (T, 3) int32 (global fit key per triangle corner),
        ``positions`` (T, 3, 3) float32 and ``normals`` (T, 3, 3) float32 (the normal of each corner's
        KEY, as ``cage.build_coverage_offsets`` binds it), ``key_count`` (K). Every high vertex is
        bound to its nearest low triangle and its reach along the blended normal is scattered (max)
        onto that triangle's three keys. Returns one dict per item: ``reach`` (K,) float32 (0 where
        nothing bound), ``vertices`` bound, ``gather_ms`` and ``gpu_ms``."""
        import numpy as np

        items = list(items)
        parts = [struct.pack("<I", len(items))]
        for item in items:
            meshes = list(item["meshes"])
            parts.append(struct.pack("<I", len(meshes)))
            for path, matrix in meshes:
                encoded = os.fspath(path).encode("utf-8")
                values = [float(v) for v in matrix]
                if len(values) != 16:
                    raise ValueError("matrix must have 16 values")
                parts.append(struct.pack("<I", len(encoded)))
                parts.append(encoded)
                parts.append(struct.pack("<16f", *values))
            key_index = np.ascontiguousarray(item["key_index"], dtype="<i4")
            positions = np.ascontiguousarray(item["positions"], dtype="<f4")
            normals = np.ascontiguousarray(item["normals"], dtype="<f4")
            parts.append(struct.pack("<II", int(key_index.shape[0]), int(item["key_count"])))
            parts.append(key_index.tobytes())
            parts.append(positions.tobytes())
            parts.append(normals.tobytes())
        payload = b"".join(parts)
        with self._lock:
            self._ensure_started()
            body = self._call(_CMD_COVERBATCH, 0, payload)
        (count,) = struct.unpack_from("<I", body, 0)
        cursor = 4
        results = []
        for _ in range(count):
            key_count, vertices, gather_ms, gpu_ms = struct.unpack_from("<IIff", body, cursor)
            cursor += 16
            reach = np.frombuffer(body, dtype="<f4", count=key_count, offset=cursor).copy()
            cursor += key_count * 4
            results.append({"reach": reach, "vertices": vertices, "gather_ms": gather_ms, "gpu_ms": gpu_ms})
        return results


_WORKER: CageGpuWorker | None = None
_WORKER_LOCK = threading.Lock()


def shared_worker() -> CageGpuWorker | None:
    """The process-wide worker, or None when the tool is not installed."""
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            if executable_path() is None:
                return None
            _WORKER = CageGpuWorker()
        return _WORKER


def release_gpu_memory(wait_seconds: float | None = None) -> bool:
    """Hand the tool's VRAM and host commit back (the bake is about to start). Never raises.

    The scenes it keeps resident after a cage fit or a prewarm preload weigh ~4 GB of commit on
    a 72 M-triangle gun, and the backend's host-build admission counts that against the bake until
    the tool lets go (the idle timer needs 30 s of quiet, which a bake pressed right after the
    fits does not give it: the Uzi's first bake was refused with GPU_GROUP_TOO_LARGE, its second
    passed). ``wait_seconds`` waits that long for a request still running; None never blocks.
    Returns True when nothing is held any more."""
    worker = _WORKER
    if worker is None:
        return True
    try:
        return bool(worker.release(timeout=wait_seconds))
    except Exception:
        return False


def shutdown() -> None:
    global _WORKER
    with _WORKER_LOCK:
        worker, _WORKER = _WORKER, None
    if worker is not None:
        worker.close()
