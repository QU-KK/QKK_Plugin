"""Park high-poly mesh data out of Blender while the backend bakes it (2026-09-30).

A heavy high-poly costs RAM twice during a bake: Blender holds the mesh (and its
viewport caches) while the backend worker holds its own copy. SvAT's 87.4M-triangle
single group measured Blender 22.8 GB + worker 22.9 GB at once, past this PC's commit
limit. After the job's geometry has been exported, Blender does not need the high-poly
meshes until the bake is over, so they are written to a .blend next to the bake jobs
(bpy.data.libraries.write: lossless, every attribute), swapped for empty placeholder
meshes, and removed. SvAT: 20.5 -> 9.7 GB in Blender, 3.6 GB of VRAM back, 16 s to
write and 28 s to load back on an NVMe SSD.

Parking only happens when the bake would not fit otherwise (should_park), so ordinary
bakes are unchanged. Every exit restores: the restore timer fires once no bake is
active, save_pre restores before a save, and load_post restores a file that was saved
or autosaved while parked (each parked object carries the park file path).

Neither direction freezes the UI for long (Uzi, 73 groups, 71 highs: write 1.8-5.5 s,
restore 6-9 s of a frozen Blender):

* The restore after a bake runs in timer slices (restore_async): visible highs first,
  smaller before larger, a bounded main-thread budget per tick. Anything that is about
  to read a parked mesh calls ensure_restored (one object) or restore (everything)
  first: save_pre, load_post, the next bake, the exporters and captures, Cycles retries.
  The bake state recorded at the end of a bake describes the real meshes: park takes
  a snapshot of their state terms before the swap (parked_mesh_state_fields).
* With FYR_BAKER_PARK_KEEP_FILE=1 (off by default: storage) the park file is kept after
  the restore and reused by the next park when none of its
  meshes had a geometry edit in between (high_mesh_cache.geometry_edit_token), so a repeat
  bake of unchanged highs skips the write. One file is retained per session; a stale one
  is replaced, pruned by age, and removed on unregister.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path

import bpy

try:
    from bpy.app.handlers import persistent
except Exception:  # noqa: BLE001 - unit tests run against a stub bpy
    def persistent(fn):
        return fn

PLACEHOLDER_SUFFIX = "__fyr_parked"
OBJECT_MESH_PROP = "fyr_parked_mesh"
OBJECT_FILE_PROP = "fyr_parked_file"
PARK_ENV_VAR = "FYR_BAKER_PARK_HIGH_POLY"  # "1" always park, "0" never
GIB = 1024 ** 3
# Measured backend model (PLAN_v2 item 1.6; peak commit fit R2 0.98 on the memory probe):
# ~4 GiB fixed + ~0.6 GiB per million triangles of the LARGEST planned pass, and a pass
# is bounded by the per-pass triangle cap. Uzi: 73M high triangles, measured 14.2 GiB
# peak commit, model 4 + 0.6 * 17.9 = 14.7 GiB. (The old flat 280 B/triangle asked
# 25 GiB for it and parked every bake.)
PASS_TRIANGLE_CAP = 17_900_000
BACKEND_BASE_BYTES = 4 * GIB
BACKEND_BYTES_PER_TRIANGLE = int(0.6 * GIB / 1_000_000)
# A single group above the cap is not known to split into passes; keep the flat figure
# measured on SvAT (22.9 GB for 87.4M triangles, 262 B, rounded up) for it.
UNSPLIT_GROUP_BYTES_PER_TRIANGLE = 280
# The worker's need is multiplied by this, whichever source gave it.
SAFETY_FACTOR = 1.3
# True: a measured peak of an earlier bake of this scene replaces the model (the Uzi
# measures 8.6 GiB against the model's 14.7), floored at HISTORY_MODEL_FLOOR x model
# because the key does not include bake settings (resolution, maps). The mid-bake commit
# guard parks late if a bake outgrows it. False: the larger of the two.
HISTORY_REPLACES_MODEL = True
HISTORY_MODEL_FLOOR = 0.5
# Blender's own growth while the bake runs (result images, viewport updates, caches).
BLENDER_GROWTH_BASE_BYTES = GIB // 2
BLENDER_GROWTH_BYTES_PER_TRIANGLE = 8
# Kept free for the OS (a PC reset on 10-21 came from commit exhaustion).
RESERVE_BYTES = 4 * GIB
# Mid-bake floor: below this much available commit an unparked bake parks late.
COMMIT_FLOOR_BYTES = 4 * GIB
FAKE_AVAILABLE_ENV_VAR = "FYR_BAKER_PARK_FAKE_AVAILABLE_GB"  # test hook: pretend this much commit is free
HISTORY_FILE_NAME = "high_poly_park_history.json"
HISTORY_MAX_ENTRIES = 64

# Keeps the park file after the restore and reuses it for an unchanged repeat park (a
# rebake of unchanged highs then skips the write: 10.5 s for the 4 GB Uzi file). "0" turns
# it off, "1" forces it on, unset = on while the park drive has KEEP_FREE_BYTES free beyond
# the file and the retained file is younger than KEEP_MAX_AGE_SECONDS. One file at most.
KEEP_ENV_VAR = "FYR_BAKER_PARK_KEEP_FILE"
KEEP_FREE_BYTES = 40 * 1024**3
KEEP_MAX_AGE_SECONDS = 30 * 60

# Park file written ahead of the Bake press (the 71 highs of the Uzi take 13 to 14 s to write
# and the Bake used to wait for it). While the user is idle, after the high-mesh prewarm has
# drained and only when a Bake would park, the highs are written in small slices (a few
# million triangles, well under a second each). Bake then finds every mesh in a written file
# with an unchanged edit token and only swaps (0.2 s). "0" turns it off.
PREWRITE_ENV_VAR = "FYR_BAKER_PARK_PREWRITE"
#: A slice is a few hundred ms of main-thread time: small meshes are batched up to this many
#: triangles per slice, a larger one is a slice of its own (measured 0.1 to 1.5 s for 3 to 9M
#: triangles on a warm disk), and a mesh above PREWRITE_MAX_MESH_TRIANGLES is never written
#: ahead (one write cannot be split); the Bake writes those few at the press, next to the swap.
PREWRITE_SLICE_TRIANGLES = 1_200_000
PREWRITE_MAX_MESH_TRIANGLES = 4_500_000
PREWRITE_BYTES_PER_TRIANGLE = 70
PREWRITE_TICK_SECONDS = 0.25
#: Nothing is written (and no slice continues) unless the machine has had no keyboard or mouse
#: input for this long; FYR_BAKER_PARK_PREWRITE_IDLE_SECONDS overrides (tests).
PREWRITE_IDLE_SECONDS = 60.0
PREWRITE_IDLE_ENV_VAR = "FYR_BAKER_PARK_PREWRITE_IDLE_SECONDS"
PREWRITE_BUSY_RECHECK_SECONDS = 3.0

#: Main-thread time a restore slice may spend before it yields to the UI (a single mesh
#: load cannot be split, so a slice always restores at least one).
RESTORE_SLICE_SECONDS = 0.04
RESTORE_SLICE_INTERVAL = 0.02
#: A retained park file nobody references is pruned after this long.
STALE_PARK_FILE_SECONDS = 24 * 3600

_STATE: dict = {
    "park_file": None,
    "entries": [],
    "timer": False,
    # Restore in timer slices: (park_file, mesh_name) units still to bring back, in order.
    "queue": [],
    "slice_timer": False,
    # {object name: mesh state terms} and {object name: overlay key term} taken before a swap.
    "fields": {},
    "signatures": {},
    # The park file kept for reuse: {"file": path, "tokens": {mesh name: edit token}}.
    "retained": None,
    # {park file: {mesh name: edit token}} for the files parked from this session.
    "file_tokens": {},
    # Park files written ahead of the Bake press, in slices while the user is idle:
    # {mesh name: {"file": path, "token": edit token}}. park() swaps those meshes without
    # a write while every token still matches.
    "prewritten": {},
    "prewrite_timer": False,
    "expiry_timer": False,
    # The park decision of the running bake (for the peak record) and the mid-bake guard.
    "decision": None,
    "guard": False,
}


def _log(message: str) -> None:
    print(f"[Fyr Baker] high-poly park: {message}")


class _quiet:
    """The swap changes no content: keep the dirty tracker, the high-mesh export cache
    and the speculative PREPARE from reacting to it. Depsgraph handlers run after the
    change, so the block forces the evaluation while the suppression is still held."""

    def __enter__(self):
        from . import dirty_tracker, high_mesh_cache

        try:
            from . import operators

            operators._suppress_bg_prepare(10.0)
        except Exception:  # noqa: BLE001
            pass
        self._dirty = dirty_tracker.suppress()
        self._dirty.__enter__()
        self._cache = high_mesh_cache.suspend_tracking()
        self._cache.__enter__()
        self._overlay = None
        try:
            from . import overlay_keys

            self._overlay = overlay_keys.freeze_revisions()
            self._overlay.__enter__()
        except Exception:  # noqa: BLE001
            self._overlay = None
        return self

    def __exit__(self, *exc):
        from . import dirty_tracker

        try:
            bpy.context.view_layer.update()
        except Exception:  # noqa: BLE001
            pass
        if self._overlay is not None:
            self._overlay.__exit__(*exc)
        self._cache.__exit__(*exc)
        self._dirty.__exit__(*exc)
        try:
            dirty_tracker.set_post_bake_cooldown(2.0)
        except Exception:  # noqa: BLE001
            pass
        return False


def _empty_material_slots(mesh) -> None:
    """Empty every material slot of ``mesh`` so a write carries geometry only. Not
    materials.clear(): that also wipes every polygon's material index and the objects'
    object-linked slots, for good."""
    for index in range(len(mesh.materials)):
        mesh.materials[index] = None


def _fill_material_slots(mesh, materials) -> None:
    """Put ``materials`` back into the (still existing) slots of ``mesh`` by index."""
    for index, material in enumerate(materials):
        if index < len(mesh.materials):
            mesh.materials[index] = material
        else:
            mesh.materials.append(material)


def _clear_high_geometry_caches() -> None:
    """Retained high BVHs and cage-check batches (~140 B/triangle) point at the parked
    meshes; drop them (they rebuild on demand)."""
    for module_name, fn_name in (("cage", "clear_geometry_caches"),
                                 ("overlay_cage_check_gpu", "clear_cage_check_gpu_cache")):
        try:
            module = __import__(f"{__package__}.{module_name}", fromlist=[fn_name])
            getattr(module, fn_name)()
        except Exception:  # noqa: BLE001
            pass


def is_parked() -> bool:
    return bool(_STATE["entries"])


def triangle_count(objects) -> int:
    total = 0
    for obj in objects:
        mesh = getattr(obj, "data", None)
        if mesh is None or getattr(obj, "type", "") != "MESH":
            continue
        # Sum over faces of (corners - 2), without walking 40M+ faces in Python.
        total += max(0, len(mesh.loops) - 2 * len(mesh.polygons))
    return total


def _available_commit_now(honor_fake: bool = False) -> int | None:
    """Commit still available at the page file's CURRENT size. Deliberately not the
    growth-inclusive figure cycles_memory uses: growing the page file eats the system
    drive, and a nearly full C: under commit pressure is what reset the PC (09-28)."""
    # The test hook only fakes the START decision; the mid-bake guard and the restore
    # check always read the real commit, so a faked "plenty" cannot hide a real shortage.
    fake = str(os.environ.get(FAKE_AVAILABLE_ENV_VAR, "") or "").strip() if honor_fake else ""
    if fake:
        try:
            return int(float(fake) * GIB)
        except ValueError:
            pass
    if os.name == "nt":
        try:
            import ctypes

            class _Status(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _Status()
            status.dwLength = ctypes.sizeof(_Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPageFile)
        except Exception:  # noqa: BLE001
            return None
        return None
    try:
        from . import cycles_memory

        memory = cycles_memory.system_memory()
    except Exception:  # noqa: BLE001
        return None
    if memory is None:
        return None
    return int(memory.available_commit if memory.available_commit is not None else memory.available_physical)


def estimate_worker_bytes(total_triangles: int, largest_group_triangles: int | None = None) -> int:
    """Backend peak commit for the bake from the measured model (no history)."""
    if largest_group_triangles is not None and largest_group_triangles > PASS_TRIANGLE_CAP:
        return int(largest_group_triangles) * UNSPLIT_GROUP_BYTES_PER_TRIANGLE
    pass_triangles = min(int(total_triangles), PASS_TRIANGLE_CAP)
    return BACKEND_BASE_BYTES + pass_triangles * BACKEND_BYTES_PER_TRIANGLE


def decide_park(
    total_triangles: int,
    available_commit: int,
    *,
    largest_group_triangles: int | None = None,
    history_peak_bytes: int | None = None,
) -> tuple[bool, str]:
    """Park only when the bake would not fit: (worker need, the larger of the model and
    the measured peak of earlier bakes of this scene) x safety factor, plus Blender's
    growth, plus the OS reserve, against the commit still available."""
    model = estimate_worker_bytes(total_triangles, largest_group_triangles)
    history = int(history_peak_bytes or 0)
    if HISTORY_REPLACES_MODEL and history > 0:
        worker = max(history, int(model * HISTORY_MODEL_FLOOR))
    else:
        worker = max(model, history)
    growth = BLENDER_GROWTH_BASE_BYTES + int(total_triangles) * BLENDER_GROWTH_BYTES_PER_TRIANGLE
    needed = int(worker * SAFETY_FACTOR) + growth + RESERVE_BYTES
    reason = (
        f"needed={needed / GIB:.1f}GiB available={int(available_commit) / GIB:.1f}GiB "
        f"(worker={worker / GIB:.1f}GiB model={model / GIB:.1f}GiB "
        f"history={(history_peak_bytes or 0) / GIB:.1f}GiB x{SAFETY_FACTOR} "
        f"+ blender={growth / GIB:.1f}GiB + reserve={RESERVE_BYTES / GIB:.0f}GiB, "
        f"tris={int(total_triangles) / 1e6:.1f}M"
        + (f", largest_group={int(largest_group_triangles) / 1e6:.1f}M" if largest_group_triangles else "")
        + ")"
    )
    return needed > int(available_commit), reason


def scene_key(objects) -> str:
    """Content key of the high-poly set: object count, triangle total and mesh names."""
    import zlib

    names = sorted(str(getattr(getattr(o, "data", None), "name", "") or getattr(o, "name", "")) for o in objects)
    digest = zlib.crc32("\n".join(names).encode("utf-8", "replace")) & 0xFFFFFFFF
    return f"{len(names)}:{triangle_count(objects)}:{digest:08x}"


def _history_path() -> Path | None:
    try:
        from . import preferences

        return preferences.persistent_cache_root() / HISTORY_FILE_NAME
    except Exception:  # noqa: BLE001
        return None


def _read_history() -> dict:
    path = _history_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def history_peak_bytes(history_key: str) -> int | None:
    entry = _read_history().get(history_key)
    try:
        value = int(entry["peak_commit"])
    except Exception:  # noqa: BLE001
        return None
    return value if value > 0 else None


def process_peak_commit(pid: int) -> int | None:
    """Peak commit (PeakPagefileUsage) of a process, Windows only."""
    if os.name != "nt" or not pid:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None
        try:
            counters = _Counters()
            counters.cb = ctypes.sizeof(_Counters)
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.PeakPagefileUsage)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return None
    return None


def record_bake_peak() -> None:
    """After a finished bake: store the worker's peak commit under this bake's key. A
    resident worker's peak spans its lifetime, so it is an upper bound (safe side); a
    new worker pid replaces the stored value, the same pid only raises it."""
    decision = _STATE.get("decision")
    if not decision:
        return
    _STATE["decision"] = None
    try:
        from . import runtime

        worker = getattr(runtime, "_BAKE_WORKER", None)
        process = getattr(worker, "process", None) if worker is not None else None
        pid = int(getattr(process, "pid", 0) or 0)
        peak = process_peak_commit(pid)
        path = _history_path()
        if not peak or path is None:
            return
        history = _read_history()
        old = history.get(decision["key"]) or {}
        if old.get("pid") == pid:
            peak = max(peak, int(old.get("peak_commit", 0) or 0))
        history[decision["key"]] = {"peak_commit": int(peak), "pid": pid, "time": int(time.time()),
                                    "tris": decision.get("tris", 0), "parked": bool(decision.get("park"))}
        if len(history) > HISTORY_MAX_ENTRIES:
            for stale in sorted(history, key=lambda k: history[k].get("time", 0))[: len(history) - HISTORY_MAX_ENTRIES]:
                del history[stale]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(history), encoding="utf-8")
        os.replace(tmp, path)
        _log(f"recorded worker peak commit {peak / GIB:.1f}GiB for {decision['key']}")
    except Exception as exc:  # noqa: BLE001
        _log(f"peak record failed: {exc}")


def should_park(objects, *, largest_group_triangles: int | None = None, project_name: str = "",
                record: bool = True) -> tuple[bool, str]:
    forced = str(os.environ.get(PARK_ENV_VAR, "") or "").strip().lower()
    if forced in {"0", "off", "false", "no"}:
        return False, "disabled"
    if forced in {"1", "on", "true", "yes"}:
        return True, "forced"
    available = _available_commit_now(honor_fake=True)
    if available is None:
        return False, "memory-unknown"
    total = triangle_count(objects)
    key = f"{project_name}|{scene_key(objects)}"
    park_it, reason = decide_park(
        total, int(available),
        largest_group_triangles=largest_group_triangles,
        history_peak_bytes=history_peak_bytes(key),
    )
    if record:
        _STATE["decision"] = {"key": key, "tris": total, "park": park_it}
    return park_it, reason


def _meshes_to_park(objects) -> list:
    """Unique meshes whose every user is one of `objects` (parking a mesh shared with
    another object would empty that object too)."""
    targets = [o for o in objects if getattr(o, "type", "") == "MESH" and o.data is not None]
    ids = {o.as_pointer() for o in targets}
    meshes = []
    seen = set()
    for obj in targets:
        mesh = obj.data
        key = mesh.as_pointer()
        if key in seen or mesh.library is not None or mesh.name.endswith(PLACEHOLDER_SUFFIX):
            continue
        seen.add(key)
        users = [o for o in bpy.data.objects if o.data is not None and o.data.as_pointer() == key]
        if all(u.as_pointer() in ids for u in users):
            meshes.append((mesh, users))
    return meshes


def _combined_token(users):
    """Edit token of every object sharing a mesh, None when any is untracked."""
    from . import high_mesh_cache

    tokens = []
    for obj in users:
        token = high_mesh_cache.geometry_edit_token(obj)
        if token is None:
            return None
        tokens.append(token)
    return tuple(tokens)


def keep_file_enabled() -> bool:
    value = str(os.environ.get(KEEP_ENV_VAR, "") or "").strip().lower()
    return value not in {"0", "off", "false", "no"}


LOW_DISK_NOTICE = "Low disk space: rebakes will be slower."


def take_low_disk_notice() -> str | None:
    """The one-time low-disk message when the last park could not keep its file, else None."""
    if _STATE.pop("low_disk_notice", False):
        return LOW_DISK_NOTICE
    return None


def _should_retain(park_dir, park_size: int, reuse: bool, forced: bool, all_tracked: bool) -> bool:
    """Whether the park file stays after the restore. When the disk is too low the park
    runs as it always did (write, restore, delete) and a one-time notice is queued."""
    if not keep_file_enabled() or not all_tracked:
        return False
    if reuse or _keep_fits_disk(park_dir, park_size, forced):
        return True
    if not _STATE.get("low_disk_told"):
        _STATE["low_disk_told"] = True
        _STATE["low_disk_notice"] = True
    return False


def _keep_fits_disk(park_dir, size: int, forced: bool) -> bool:
    if forced:
        return True
    try:
        import shutil

        return shutil.disk_usage(str(park_dir)).free >= KEEP_FREE_BYTES + size
    except OSError:
        return False


def _reusable_park_file(tokens: dict) -> str | None:
    """The retained park file when every mesh about to be parked is in it unedited."""
    if not keep_file_enabled():
        return None
    retained = _STATE.get("retained")
    if not retained or not tokens:
        return None
    path = str(retained.get("file") or "")
    if not path or not os.path.exists(path):
        return None
    forced = str(os.environ.get(KEEP_ENV_VAR, "") or "").strip().lower() in {"1", "on", "true", "yes"}
    try:
        if not forced and time.time() - os.path.getmtime(path) > KEEP_MAX_AGE_SECONDS:
            return None
    except OSError:
        return None
    known = retained.get("tokens") or {}
    for name, token in tokens.items():
        if token is None or known.get(name) != token:
            return None
    return path


def _snapshot_before_swap(users) -> None:
    """What the rest of the addon reads off a high while its mesh is a placeholder: the
    state terms a bake records, and the overlay key term (so a lossless swap does not
    rebuild every group's cage overlay)."""
    try:
        from . import map_rebuild

        fields = map_rebuild.mesh_state_fields
    except Exception:  # noqa: BLE001
        fields = None
    try:
        from . import overlay_keys

        signature = overlay_keys.object_revision_signature
    except Exception:  # noqa: BLE001
        signature = None
    for obj in users:
        if fields is not None:
            try:
                _STATE["fields"][obj.name] = fields(obj)
            except Exception:  # noqa: BLE001
                pass
        if signature is not None:
            try:
                _STATE["signatures"][obj.name] = signature(obj)
            except Exception:  # noqa: BLE001
                pass


def _pin_signature(obj) -> None:
    signature = _STATE["signatures"].get(obj.name)
    if signature is None:
        return
    try:
        from . import overlay_keys

        overlay_keys.pin_object_signature(obj, signature)
    except Exception:  # noqa: BLE001
        pass


def parked_mesh_state_fields(obj) -> dict | None:
    """The mesh terms of ``obj``'s bake state as they were before it was parked, while its
    mesh is still a placeholder; None for any object that is not parked."""
    if not _STATE["entries"]:
        return None
    try:
        if not obj.get(OBJECT_MESH_PROP):
            return None
        fields = _STATE["fields"].get(obj.name)
    except Exception:  # noqa: BLE001
        return None
    return dict(fields) if fields is not None else None


def is_object_parked(obj) -> bool:
    """True while ``obj`` carries an empty placeholder instead of its mesh."""
    if not _STATE["entries"]:
        return False
    try:
        return bool(obj.get(OBJECT_FILE_PROP))
    except Exception:  # noqa: BLE001
        return False


def _prune_park_dir(park_dir: Path, keep: Path) -> None:
    """Remove park files nothing references any more and nobody has touched for a day."""
    referenced = {str(entry.get("file")) for entry in _STATE["prewritten"].values()}
    try:
        referenced |= {str(o.get(OBJECT_FILE_PROP)) for o in bpy.data.objects if o.get(OBJECT_FILE_PROP)}
    except Exception:  # noqa: BLE001
        pass
    now = time.time()
    try:
        candidates = list(park_dir.glob("high_poly_*.blend"))
    except OSError:
        return
    for path in candidates:
        if path == keep or str(path) in referenced:
            continue
        # Age only: another Blender on the same output folder may be mid-bake on its own file.
        try:
            if now - path.stat().st_mtime > STALE_PARK_FILE_SECONDS:
                path.unlink()
                path.with_suffix(".json").unlink(missing_ok=True)
        except OSError:
            pass


def park(objects, park_dir: str | Path) -> bool:
    """Write the high-poly meshes to `park_dir` (or reuse the file of the last park when
    none of them changed), swap in placeholders, free them."""
    if is_parked():
        return True
    pairs = _meshes_to_park(objects)
    if not pairs:
        return False
    park_dir = Path(park_dir)
    park_dir.mkdir(parents=True, exist_ok=True)
    tokens = {mesh.name: _combined_token(users) for mesh, users in pairs}
    reuse = _reusable_park_file(tokens)
    covered, missing = ({}, list(pairs)) if reuse else _prewritten_split(pairs, tokens)
    # Meshes already in a file written ahead of the press are swapped without a write; any
    # others (an edited mesh, or one too large to write in an idle slice) are written now.
    prewritten = covered if covered else None
    if reuse:
        park_file = Path(reuse)
        write_pairs = []
    elif prewritten and not missing:
        park_file = Path(next(iter(prewritten.values())))
        write_pairs = []
    else:
        park_file = park_dir / f"high_poly_{int(time.time())}_{os.getpid()}.blend"
        write_pairs = missing if prewritten else list(pairs)
    write_names = [mesh.name for mesh, _users in write_pairs]
    write_needed = bool(write_pairs)
    file_of = dict(covered)
    t0 = time.monotonic()
    entries = []
    _STATE["fields"] = {}
    _STATE["signatures"] = {}
    with _quiet():
        for _mesh, users in pairs:
            _snapshot_before_swap(users)
        # Materials stay in this file: detach them before the write so the park file
        # holds geometry only (a write carries dependencies, and loading them back
        # would append duplicate materials and images). The placeholder keeps them. Empty the
        # slots instead of materials.clear(): clear() also wipes every polygon's material
        # index and the objects' object-linked slots, for good.
        stashed = {}
        for mesh, _users in pairs:
            stashed[mesh.name] = list(mesh.materials)
            if mesh.name in write_names:
                _empty_material_slots(mesh)
        if write_needed:
            try:
                bpy.data.libraries.write(str(park_file), {mesh for mesh, _users in write_pairs}, compress=False)
            except Exception as exc:  # noqa: BLE001 - a failed write parks nothing
                _log(f"write failed, not parking: {exc}")
                for mesh, _users in write_pairs:
                    _fill_material_slots(mesh, stashed.get(mesh.name, []))
                try:
                    park_file.unlink()
                except OSError:
                    pass
                _STATE["fields"] = {}
                _STATE["signatures"] = {}
                return False
        t1 = time.monotonic()
        for mesh, users in pairs:
            name = mesh.name
            tris = max(0, len(mesh.loops) - 2 * len(mesh.polygons))
            placeholder = bpy.data.meshes.new(name + PLACEHOLDER_SUFFIX)
            for material in stashed.get(name, []):
                placeholder.materials.append(material)
            for obj in users:
                obj.data = placeholder
                obj[OBJECT_MESH_PROP] = name
                obj[OBJECT_FILE_PROP] = str(file_of.get(name, park_file))
            bpy.data.meshes.remove(mesh)
            for obj in users:
                _pin_signature(obj)
            entries.append({"mesh": name, "objects": [o.name for o in users], "tris": tris})
    _clear_high_geometry_caches()
    _STATE["park_file"] = str(park_file)
    _STATE["entries"] = entries
    _STATE["queue"] = []
    known = {name: token for name, token in tokens.items() if token is not None}
    forced_keep = str(os.environ.get(KEEP_ENV_VAR, "") or "").strip().lower() in {"1", "on", "true", "yes"}
    try:
        park_size = park_file.stat().st_size
    except OSError:
        park_size = 0
    if prewritten is not None:
        # Written ahead of the press: these files stay (their tokens are in "prewritten")
        # until a geometry edit replaces them; what the press had to write joins them, so
        # the next park of unchanged highs only swaps.
        for name in write_names:
            file_of[name] = str(park_file)
            if tokens.get(name) is not None and prewrite_enabled():
                _STATE["prewritten"][name] = {"file": str(park_file), "token": tokens[name], "at": time.time()}
    elif _should_retain(park_dir, park_size, reuse, forced_keep, len(known) == len(tokens)):
        previous = _STATE.get("retained")
        _STATE["retained"] = {"file": str(park_file), "tokens": known}
        _STATE["file_tokens"][str(park_file)] = known
        if previous and str(previous.get("file")) != str(park_file):
            _remove_park_files(str(previous.get("file")))
    else:
        stale = _STATE.get("retained")
        _STATE["retained"] = None
        if stale and str(stale.get("file")) != str(park_file):
            _remove_park_files(str(stale.get("file")))
    try:
        if prewritten is not None:
            by_file: dict = {}
            for entry in entries:
                by_file.setdefault(str(file_of.get(entry["mesh"], park_file)), []).append(entry)
            for file_name, file_entries in by_file.items():
                Path(file_name).with_suffix(".json").write_text(
                    json.dumps({"file": bpy.data.filepath, "entries": file_entries}), encoding="utf-8")
        else:
            (park_file.with_suffix(".json")).write_text(
                json.dumps({"file": bpy.data.filepath, "entries": entries}), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001 - a full disk must not fail the bake
        _log(f"park sidecar not written: {exc}")
    _prune_park_dir(park_dir, park_file)
    if reuse:
        verb = "reused"
    elif prewritten is not None:
        verb = f"prewritten + {len(write_names)} written {t1 - t0:.1f}s" if write_names else "prewritten"
    else:
        verb = f"write {t1 - t0:.1f}s"
    _log(f"parked {len(entries)} meshes in {park_file} ({verb}, swap {time.monotonic() - t1:.2f}s)")
    return True


def _prewritten_split(pairs, tokens: dict):
    """(covered, missing): {mesh name: park file} for the meshes that sit in a file written
    ahead of the press with an unchanged edit token, and the (mesh, users) pairs that do not."""
    covered: dict = {}
    missing = []
    if not prewrite_enabled():
        return covered, list(pairs)
    forced = str(os.environ.get(KEEP_ENV_VAR, "") or "").strip().lower() in {"1", "on", "true", "yes"}
    now = time.time()
    for mesh, users in pairs:
        entry = _STATE["prewritten"].get(mesh.name)
        token = tokens.get(mesh.name)
        if (entry and token is not None and entry.get("token") == token and os.path.exists(str(entry.get("file")))
                and (forced or now - float(entry.get("at", 0.0)) <= KEEP_MAX_AGE_SECONDS)):
            covered[mesh.name] = str(entry["file"])
        else:
            missing.append((mesh, users))
    return covered, missing


def expire_prewritten(force_all: bool = False) -> int:
    """Forget (and delete the files of) written-ahead entries older than the kept park file's
    limit, KEEP_MAX_AGE_SECONDS. Returns how many entries went."""
    now = time.time()
    gone = []
    for name, entry in list(_STATE["prewritten"].items()):
        if force_all or now - float(entry.get("at", 0.0)) > KEEP_MAX_AGE_SECONDS:
            gone.append(str(entry.get("file")))
            del _STATE["prewritten"][name]
    _remove_unreferenced_prewrite_files(set(gone))
    return len(gone)


def _expiry_timer():
    """One shot: when the written-ahead files are old enough to be of no more use, remove
    them (not while a bake has the highs parked). Nothing is written again by this."""
    _STATE["expiry_timer"] = False
    try:
        if not _STATE["prewritten"]:
            return None
        if is_parked():
            _STATE["expiry_timer"] = True
            return 60.0
        expire_prewritten()
        if _STATE["prewritten"]:
            oldest = min(float(e.get("at", 0.0)) for e in _STATE["prewritten"].values())
            _STATE["expiry_timer"] = True
            return max(30.0, oldest + KEEP_MAX_AGE_SECONDS + 5.0 - time.time())
    except Exception:  # noqa: BLE001
        pass
    return None


def _schedule_expiry() -> None:
    if _STATE.get("expiry_timer"):
        return
    try:
        bpy.app.timers.register(_expiry_timer, first_interval=KEEP_MAX_AGE_SECONDS + 5.0)
        _STATE["expiry_timer"] = True
    except Exception:  # noqa: BLE001
        pass


def _prewritten_files_for(pairs, tokens: dict) -> dict | None:
    """{mesh name: park file} when EVERY mesh sits in a file written ahead of the press."""
    covered, missing = _prewritten_split(pairs, tokens)
    return covered if covered and not missing else None


def system_idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input anywhere on the machine (Windows
    GetLastInputInfo); 0.0 where it cannot be read, so nothing is written ahead there."""
    override = str(os.environ.get(PREWRITE_IDLE_ENV_VAR, "") or "").strip()
    if override and override.lower().startswith("fake:"):
        try:
            return float(override[5:])
        except ValueError:
            return 0.0
    if os.name != "nt":
        return 0.0
    try:
        import ctypes

        class _LastInput(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = _LastInput()
        info.cbSize = ctypes.sizeof(_LastInput)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        ticks = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return ((ticks - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:  # noqa: BLE001
        return 0.0


def prewrite_idle_required() -> float:
    override = str(os.environ.get(PREWRITE_IDLE_ENV_VAR, "") or "").strip()
    if override and not override.lower().startswith("fake:"):
        try:
            return float(override)
        except ValueError:
            pass
    return PREWRITE_IDLE_SECONDS


def prewrite_enabled() -> bool:
    value = str(os.environ.get(PREWRITE_ENV_VAR, "") or "").strip().lower()
    return keep_file_enabled() and value not in {"0", "off", "false", "no"}


def prewrite_step(objects, park_dir, max_triangles: int = PREWRITE_SLICE_TRIANGLES) -> bool:
    """Write the next slice of the highs that are not in a park file yet (or were edited
    since), one `libraries.write` of a few million triangles. Returns True while more
    remain. Drops entries of meshes that changed and removes files nothing references."""
    if is_parked():
        return False
    pairs = _meshes_to_park(objects)
    if not pairs:
        return False
    park_dir = Path(park_dir)
    expire_prewritten()
    tokens = {mesh.name: _combined_token(users) for mesh, users in pairs}
    names = set(tokens)
    dropped_files = set()
    for name in list(_STATE["prewritten"]):
        entry = _STATE["prewritten"][name]
        if name not in names or tokens.get(name) is None or entry.get("token") != tokens.get(name):
            dropped_files.add(str(entry.get("file")))
            del _STATE["prewritten"][name]
    todo = [(mesh, users) for mesh, users in pairs
            if tokens[mesh.name] is not None and mesh.name not in _STATE["prewritten"]
            and max(0, len(mesh.loops) - 2 * len(mesh.polygons)) <= PREWRITE_MAX_MESH_TRIANGLES]
    batch = []
    batch_triangles = 0
    for mesh, users in todo:
        triangles = max(0, len(mesh.loops) - 2 * len(mesh.polygons))
        if batch and batch_triangles + triangles > max_triangles:
            break
        batch.append((mesh, users))
        batch_triangles += triangles
    if batch and not _STATE["prewritten"]:
        # A crash or a killed Blender leaves high_poly_pre_* files behind: the prune removes
        # the ones nothing references that are older than STALE_PARK_FILE_SECONDS.
        _prune_park_dir(park_dir, park_dir / "high_poly_none.blend")
        # First slice: the whole set must fit the drive, same rule as the kept park file.
        total = sum(max(0, len(m.loops) - 2 * len(m.polygons)) for m, _u in todo)
        try:
            park_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        if not _keep_fits_disk(park_dir, total * PREWRITE_BYTES_PER_TRIANGLE, False):
            return False
    if batch:
        park_dir.mkdir(parents=True, exist_ok=True)
        path = park_dir / f"high_poly_pre_{os.getpid()}_{int(time.time() * 1000)}.blend"
        t0 = time.monotonic()
        with _quiet():
            stashed = {}
            for mesh, _users in batch:
                stashed[mesh.name] = list(mesh.materials)
                _empty_material_slots(mesh)
            try:
                bpy.data.libraries.write(str(path), {mesh for mesh, _users in batch}, compress=False)
                written = True
            except Exception as exc:  # noqa: BLE001 - a failed write just means no prewrite
                _log(f"prewrite failed: {exc}")
                written = False
            for mesh, _users in batch:
                _fill_material_slots(mesh, stashed.get(mesh.name, []))
        if not written:
            try:
                path.unlink()
            except OSError:
                pass
            return False
        for mesh, _users in batch:
            _STATE["prewritten"][mesh.name] = {"file": str(path), "token": tokens[mesh.name], "at": time.time()}
        _log(f"prewrote {len(batch)} meshes ({batch_triangles / 1e6:.1f}M tris) in {time.monotonic() - t0:.2f}s")
        _schedule_expiry()
    _remove_unreferenced_prewrite_files(dropped_files)
    return len(todo) > len(batch)


def _prewrite_targets():
    """(objects, park_dir, largest_group_triangles) of the first project that has highs,
    or None. park_dir is where a Bake of that project would park."""
    from . import export, properties

    scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return None
    for project in getattr(settings, "projects", []):
        objects = []
        largest = 0
        for group in getattr(project, "groups", []):
            if getattr(group, "use_low_as_high", False):
                return None
            group_objects = []
            for slot in properties.effective_high_mesh_slots(group):
                obj = getattr(slot, "object_ref", None)
                if obj is not None and getattr(obj, "type", "") == "MESH":
                    group_objects.append(obj)
                    if obj not in objects:
                        objects.append(obj)
            largest = max(largest, triangle_count(group_objects))
        if not objects:
            continue
        output_root, _is_default = export.resolve_output_root(project)
        return objects, Path(output_root) / ".fyr_baker" / "parked", largest, str(getattr(project, "name", "") or "")
    return None


def schedule_prewrite(delay: float = 1.0) -> None:
    """Start writing the park file ahead of the press once the scene is idle (called when the
    high-mesh prewarm has drained). No-op when a Bake would not park, when it is off, or
    when a timer is already running."""
    if _STATE["prewrite_timer"] or not prewrite_enabled():
        return
    try:
        bpy.app.timers.register(_prewrite_timer, first_interval=delay)
        _STATE["prewrite_timer"] = True
    except Exception:  # noqa: BLE001
        pass


def _prewrite_timer():
    def stop():
        _STATE["prewrite_timer"] = False
        return None

    try:
        from . import high_mesh_cache, operators, runtime

        if is_parked() or runtime.active_bake_snapshot() is not None:
            return stop()
        if getattr(operators, "_DEFERRED_BAKE_STATE", None) is not None:
            return stop()
        if high_mesh_cache._PENDING_PREWARM_KEYS or high_mesh_cache.prewarm_writes_in_flight():  # noqa: SLF001
            return 1.0  # exports first: the park file is written from the same main thread
        if getattr(bpy.context, "mode", "OBJECT") != "OBJECT":
            return 2.0
        try:
            if runtime._viewport_cage_fits_pending():  # noqa: SLF001
                return 1.0
        except Exception:  # noqa: BLE001
            pass
        if system_idle_seconds() < prewrite_idle_required():
            return PREWRITE_BUSY_RECHECK_SECONDS  # someone is working: no slice starts or continues
        targets = _prewrite_targets()
        if targets is None:
            return stop()
        objects, park_dir, largest, project_name = targets
        if not _STATE["prewritten"]:
            wanted, reason = should_park(
                objects, largest_group_triangles=largest, project_name=project_name, record=False)
            if not wanted:
                return stop()
            _log(f"prewriting the park file while idle ({reason})")
        more = prewrite_step(objects, park_dir)
        return PREWRITE_TICK_SECONDS if more else stop()
    except Exception as exc:  # noqa: BLE001 - never let an idle optimisation raise into Blender
        _log(f"prewrite stopped: {exc}")
        return stop()


def _remove_unreferenced_prewrite_files(candidates) -> None:
    if not candidates:
        return
    referenced = {str(entry.get("file")) for entry in _STATE["prewritten"].values()}
    try:
        referenced |= {str(o.get(OBJECT_FILE_PROP)) for o in bpy.data.objects if o.get(OBJECT_FILE_PROP)}
    except Exception:  # noqa: BLE001
        pass
    for file_name in candidates:
        if file_name and file_name not in referenced:
            _remove_park_files(file_name)


def _remove_park_files(park_file: str) -> None:
    for path in (Path(park_file), Path(park_file).with_suffix(".json")):
        try:
            path.unlink()
        except OSError:
            pass


def _is_retained(park_file: str) -> bool:
    retained = _STATE.get("retained")
    if bool(retained) and str(retained.get("file")) == str(park_file):
        return True
    return any(str(entry.get("file")) == str(park_file) for entry in _STATE["prewritten"].values())


def _park_units() -> dict:
    """{(park_file, mesh_name): [objects]} for every parked object in the file."""
    units: dict = {}
    for obj in bpy.data.objects:
        try:
            park_file = obj.get(OBJECT_FILE_PROP)
            name = obj.get(OBJECT_MESH_PROP)
        except Exception:  # noqa: BLE001
            continue
        if park_file and name:
            units.setdefault((str(park_file), str(name)), []).append(obj)
    return units


def _restore_units(keys, units: dict | None = None, *, quiet: bool = True) -> int:
    """Bring the given (park_file, mesh_name) units back; returns the objects restored.
    ``quiet=False`` when the caller already holds a _quiet block (a slice restores several
    units under one, so the depsgraph is evaluated once per slice, not once per mesh)."""
    units = units if units is not None else _park_units()
    by_file: dict[str, list[str]] = {}
    for key in keys:
        if key in units:
            by_file.setdefault(key[0], []).append(key[1])
    restored = 0
    done_names: set[str] = set()
    with (_quiet() if quiet else contextlib.nullcontext()):
        for park_file, names in by_file.items():
            if not os.path.exists(park_file):
                _log(f"park file missing, cannot restore {len(names)} meshes: {park_file}")
                continue
            t0 = time.monotonic()
            wanted = sorted(set(names))
            with bpy.data.libraries.load(park_file, link=False) as (_src, dst):
                dst.meshes = list(wanted)
            loaded = {name: mesh for name, mesh in zip(wanted, dst.meshes) if mesh is not None}
            swapped = []
            for name in wanted:
                mesh = loaded.get(name)
                if mesh is None:
                    continue
                for obj in units[(park_file, name)]:
                    placeholder = obj.data
                    if placeholder is not None:
                        # The park file holds the slots empty (no slots at all before 1.1.3).
                        for index, material in enumerate(placeholder.materials):
                            if index >= len(mesh.materials):
                                mesh.materials.append(material)
                            elif mesh.materials[index] is None:
                                mesh.materials[index] = material
                    obj.data = mesh
                    del obj[OBJECT_MESH_PROP]
                    if OBJECT_FILE_PROP in obj:
                        del obj[OBJECT_FILE_PROP]
                    if placeholder is not None and placeholder.name.endswith(PLACEHOLDER_SUFFIX) and placeholder.users == 0:
                        bpy.data.meshes.remove(placeholder)
                    swapped.append(obj)
                    _pin_signature(obj)
                    _STATE["fields"].pop(obj.name, None)
                    _STATE["signatures"].pop(obj.name, None)
                    restored += 1
                done_names.add(name)
            try:
                from . import high_mesh_cache

                high_mesh_cache.rebind_data_keys(swapped)
            except Exception:  # noqa: BLE001
                pass
            _log(f"restored {len(loaded)} meshes from {park_file} in {time.monotonic() - t0:.2f}s")
            still_parked = [o for o in bpy.data.objects if o.get(OBJECT_FILE_PROP) == park_file]
            if not still_parked:
                path = Path(park_file)
                if _is_retained(park_file):
                    path.with_suffix(".json").unlink(missing_ok=True)
                else:
                    _remove_park_files(park_file)
    _STATE["entries"] = [e for e in _STATE["entries"] if e.get("mesh") not in done_names]
    if not _STATE["entries"]:
        _STATE["park_file"] = None
        _STATE["fields"] = {}
        _STATE["signatures"] = {}
    return restored


def restore() -> int:
    """Put every parked mesh back NOW (this session's and any found in the file). The
    synchronous path: save_pre, load_post, the next bake, anything about to read them."""
    _STATE["queue"] = []
    units = _park_units()
    restored = 0
    if units:
        _release_worker_if_restore_does_not_fit()
        restored = _restore_units(list(units), units)
    _STATE["park_file"] = None
    _STATE["entries"] = []
    _STATE["fields"] = {}
    _STATE["signatures"] = {}
    return restored


def _release_worker_if_restore_does_not_fit() -> None:
    fits, reason = restore_fits_memory()
    if fits:
        return
    # The resident worker's caches (a warm rebake) are worth less than getting
    # the artist's meshes back without pushing the system out of memory.
    _log(f"releasing the bake worker before restore ({reason})")
    try:
        from . import runtime

        runtime.release_bake_worker_for_memory("high-poly restore")
    except Exception as exc:  # noqa: BLE001
        _log(f"worker release failed: {exc}")


def ensure_restored(objects=None, *, only_when_idle: bool = False) -> int:
    """Restore now what a reader is about to use: the given objects' meshes, or everything
    when ``objects`` is None. ``only_when_idle`` leaves everything parked while a bake runs
    (the park is what keeps the memory free then)."""
    if not _STATE["entries"] and objects is None:
        return 0
    if only_when_idle and _bake_active():
        return 0
    if objects is None:
        return restore()
    wanted: set = set()
    for obj in objects:
        try:
            park_file = obj.get(OBJECT_FILE_PROP)
            name = obj.get(OBJECT_MESH_PROP)
        except Exception:  # noqa: BLE001
            continue
        if park_file and name:
            wanted.add((str(park_file), str(name)))
    if not wanted:
        return 0
    queue = _STATE["queue"]
    if queue:
        _STATE["queue"] = [key for key in queue if key not in wanted]
    return _restore_units(list(wanted))


def _visible(objects) -> bool:
    for obj in objects:
        try:
            if obj.visible_get():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def restore_async() -> None:
    """Start bringing the parked meshes back in timer slices: visible highs first, small
    before large. Returns at once; ensure_restored/restore finish whatever a reader needs
    sooner."""
    units = _park_units()
    if not units:
        _STATE["entries"] = []
        return
    tris = {e.get("mesh"): int(e.get("tris", 0) or 0) for e in _STATE["entries"]}
    ordered = sorted(
        units.items(),
        key=lambda item: (0 if _visible(item[1]) else 1, tris.get(item[0][1], 0), item[0][1]),
    )
    _release_worker_if_restore_does_not_fit()
    _STATE["queue"] = [key for key, _objects in ordered]
    if not _STATE["slice_timer"]:
        _STATE["slice_timer"] = True
        bpy.app.timers.register(_restore_slice, first_interval=0.0, persistent=True)


def _restore_slice():
    queue = _STATE["queue"]
    if not queue:
        _STATE["slice_timer"] = False
        return None
    deadline = time.monotonic() + RESTORE_SLICE_SECONDS
    try:
        units = _park_units()
        with _quiet():
            while queue:
                key = queue.pop(0)
                if key in units:
                    _restore_units([key], units, quiet=False)
                if time.monotonic() >= deadline:
                    break
    except Exception as exc:  # noqa: BLE001 - keep trying rather than lose the meshes
        _log(f"restore slice failed, retrying: {exc}")
        return 2.0
    if queue:
        return RESTORE_SLICE_INTERVAL
    _STATE["slice_timer"] = False
    _STATE["park_file"] = None
    _STATE["entries"] = []
    return None


def pending_restore_count() -> int:
    return len(_STATE["queue"])


# Blender's growth when the parked meshes come back, per byte of park file: SvAT's
# 5.73 GB file restored as +13.1 GB (mesh data + runtime/viewport caches).
RESTORE_GROWTH_PER_FILE_BYTE = 2.3
RESTORE_RESERVE_BYTES = 4 * 1024 ** 3


def restore_fits_memory() -> tuple[bool, str]:
    """Whether loading the parked meshes back fits next to what is resident now (the
    worker keeps its high-scene caches after a bake: SvAT 16.2 GB)."""
    files = {str(o.get(OBJECT_FILE_PROP)) for o in bpy.data.objects if o.get(OBJECT_FILE_PROP)}
    size = 0
    for path in files:
        try:
            size += os.path.getsize(path)
        except OSError:
            pass
    available = _available_commit_now()
    if available is None or size <= 0:
        return True, "unmeasured"
    needed = int(size * RESTORE_GROWTH_PER_FILE_BYTE) + RESTORE_RESERVE_BYTES
    return needed <= available, f"needed={needed // 1024 ** 2}MB available={available // 1024 ** 2}MB"


def _bake_active() -> bool:
    try:
        from . import runtime

        return runtime.active_bake_snapshot() is not None
    except Exception:  # noqa: BLE001 - unknown means "still busy"
        return True


def _restore_when_idle():
    if not is_parked():
        _STATE["timer"] = False
        return None
    if _bake_active():
        return 1.0
    try:
        restore_async()
    except Exception as exc:  # noqa: BLE001 - keep trying rather than lose the meshes
        _log(f"restore failed, retrying: {exc}")
        return 5.0
    _STATE["timer"] = False
    return None


def commit_floor_bytes() -> int:
    raw = str(os.environ.get("FYR_BAKER_PARK_COMMIT_FLOOR_GB", "") or "").strip()
    if raw:
        try:
            return int(float(raw) * GIB)
        except ValueError:
            pass
    return COMMIT_FLOOR_BYTES


def guard_tick(object_names: list[str], park_dir: str | Path, state: dict) -> float | None:
    """One mid-bake check of an UNPARKED bake: when the available commit falls under the
    floor, park late (the job's geometry is already exported, so Blender's copy is free
    to go) and hand the restore to the usual timer, which releases the worker first if
    the meshes would not fit next to it. Returns the next interval, None to stop."""
    if is_parked():
        return None
    if not _bake_active():
        state["idle"] = state.get("idle", 0) + 1
        return None if state["idle"] >= 3 else 1.0
    state["idle"] = 0
    available = _available_commit_now()
    floor = commit_floor_bytes()
    if available is None:
        return 1.0
    state["min_available"] = min(state.get("min_available", available), available)
    if available >= floor:
        return 1.0
    objects = [bpy.data.objects.get(name) for name in object_names]
    objects = [o for o in objects if o is not None]
    _log(f"commit fell to {available / GIB:.1f}GiB (floor {floor / GIB:.1f}GiB) mid-bake: parking late")
    try:
        if park(objects, park_dir):
            arm_restore_timer()
    except Exception as exc:  # noqa: BLE001 - never break the bake over the guard
        _log(f"late park failed: {exc}")
    return None


def arm_commit_guard(objects, park_dir: str | Path) -> None:
    """Watch the commit during an unparked bake (see guard_tick)."""
    if _STATE["guard"]:
        return
    names = [o.name for o in objects]
    state: dict = {}
    _STATE["guard"] = True

    def _tick():
        try:
            nxt = guard_tick(names, park_dir, state)
        except Exception:  # noqa: BLE001
            nxt = None
        if nxt is None:
            _STATE["guard"] = False
            if "min_available" in state:
                _log(f"guard ended, minimum available commit seen {state['min_available'] / GIB:.1f}GiB")
        return nxt

    bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)


def arm_restore_timer() -> None:
    if not _STATE["timer"]:
        _STATE["timer"] = True
        bpy.app.timers.register(_restore_when_idle, first_interval=1.0, persistent=True)


@persistent
def _on_save_pre(*_args):
    if is_parked() or any(o.get(OBJECT_FILE_PROP) for o in bpy.data.objects):
        _log("restoring parked meshes before save")
        restore()


@persistent
def _on_load_post(*_args):
    _STATE["park_file"] = None
    _STATE["entries"] = []
    _STATE["queue"] = []
    _STATE["fields"] = {}
    _STATE["signatures"] = {}
    _STATE["retained"] = None
    # The meshes the written-ahead files hold belong to the scene that was just closed.
    stale = {str(entry.get("file")) for entry in _STATE["prewritten"].values()}
    _STATE["prewritten"] = {}
    if any(o.get(OBJECT_FILE_PROP) for o in bpy.data.objects):
        _log("file was saved while parked; restoring")
        restore()
    _remove_unreferenced_prewrite_files(stale)


def register() -> None:
    if _on_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_on_save_pre)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister() -> None:
    if is_parked() or any(o.get(OBJECT_FILE_PROP) for o in bpy.data.objects):
        try:
            restore()
        except Exception:  # noqa: BLE001
            pass
    retained = _STATE.get("retained")
    _STATE["retained"] = None
    if retained and not any(o.get(OBJECT_FILE_PROP) for o in bpy.data.objects):
        _remove_park_files(str(retained.get("file") or ""))
    stale = {str(entry.get("file")) for entry in _STATE["prewritten"].values()}
    _STATE["prewritten"] = {}
    _remove_unreferenced_prewrite_files(stale)
    for handlers, fn in ((bpy.app.handlers.save_pre, _on_save_pre), (bpy.app.handlers.load_post, _on_load_post)):
        if fn in handlers:
            handlers.remove(fn)
