from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading

import bpy

from . import constants, sidebar_icons
from . import persistent_settings
from . import update_policy
from .registration import safe_register_class, safe_unregister_class


def _mirror_setting_changed(self, _context):
    """Mirror a persisted preference to disk the moment it changes.

    Blender's own storage is not enough on its own: an extension update
    rewrites the add-on package while the preference block is live, so the
    file in the user's config directory is what survives it. Writing on every
    change is what keeps the file from ever being behind.
    """
    persistent_settings.save_from_preferences(self)


def _update_check_mode_changed(self, _context):
    update_policy.reschedule_update_check()
    persistent_settings.save_from_preferences(self)


def _idprop_get(owner, name: str, default=None):
    getter = getattr(owner, "get", None)
    if callable(getter):
        try:
            return getter(name, default)
        except Exception:
            return default
    return default


def normalize_bake_device_mode(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized == constants.BAKE_DEVICE_GPU:
        return constants.BAKE_DEVICE_GPU
    if normalized == constants.BAKE_DEVICE_BOTH:
        return constants.BAKE_DEVICE_BOTH
    # Legacy Embree-only preference: migrate to the hybrid GPU path. Cycles is the
    # recovery backend when GPU baking fails; users no longer force CPU_REFERENCE.
    if normalized in {constants.BAKE_DEVICE_CPU, "CPU_REFERENCE", "CPU"}:
        return constants.BAKE_DEVICE_BOTH
    if normalized in {"GPU", "GPU_PREFERRED", "GPU_D3D12", "GPU_D3D12_DXR"}:
        return constants.BAKE_DEVICE_GPU
    return constants.BAKE_DEVICE_BOTH


def normalize_render_backend_preference(value: str | None) -> str:
    from . import bake_backends

    return bake_backends.normalize_render_backend_preference(value)


def resolve_render_backend_preference(preferences_obj) -> str:
    from . import bake_backends

    return bake_backends.resolve_render_backend_preference(preferences_obj)


def normalize_cycles_device(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {constants.CYCLES_DEVICE_GPU, "GPU_COMPUTE", "OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"}:
        return constants.CYCLES_DEVICE_GPU
    return constants.CYCLES_DEVICE_CPU


_CYCLES_COMPUTE_TYPES = ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI")


def _first_idle_cycles_gpu(cycles_prefs) -> str:
    """Name a non-CPU Cycles device that exists but is not being used, if any."""
    getter = getattr(cycles_prefs, "get_devices_for_type", None)
    if not callable(getter):
        return ""
    for compute_type in _CYCLES_COMPUTE_TYPES:
        try:
            devices = list(getter(compute_type) or [])
        except Exception:
            continue
        for device in devices:
            if str(getattr(device, "type", "")).upper() == "CPU":
                continue
            name = str(getattr(device, "name", "") or "").strip()
            if name:
                return f"{compute_type}: {name}"
    return ""


def cycles_gpu_compute_available() -> tuple[bool, str]:
    """True when Blender has at least one non-CPU Cycles compute device enabled.

    Cycles silently falls back to CPU when ``scene.cycles.device = 'GPU'`` but no
    compute device is enabled in Preferences > System. Detect that here so the UI
    and bake log can say so instead of the user wondering why GPU mode is slow.
    """
    try:
        import bpy

        addon = bpy.context.preferences.addons.get("cycles")
        if addon is None:
            return False, "The Cycles add-on is not enabled"
        cycles_prefs = addon.preferences
        compute_type = str(getattr(cycles_prefs, "compute_device_type", "NONE") or "NONE")
        if compute_type in {"", "NONE"}:
            # A capable GPU is usually present and merely unselected. Naming it turns
            # a dead end into a one-click fix.
            candidate = _first_idle_cycles_gpu(cycles_prefs)
            if candidate:
                return False, (
                    "No Cycles compute device selected in Preferences > System "
                    f"({candidate} available)"
                )
            return False, "No Cycles compute device is selected in Preferences > System"
        # get_devices_for_type() is the supported way to enumerate without mutating state.
        getter = getattr(cycles_prefs, "get_devices_for_type", None)
        devices = list(getter(compute_type) or []) if callable(getter) else []
        if any(getattr(device, "use", False) for device in devices):
            return True, f"Cycles {compute_type} compute device enabled"
        return False, f"No {compute_type} device is enabled in Preferences > System"
    except Exception as exc:  # pragma: no cover - depends on live Blender prefs
        return False, f"Cycles compute device probe failed: {exc}"


def activate_cycles_gpu_compute() -> tuple[bool, str]:
    """Turn on a Cycles compute device when one exists but is not selected.

    Only called after the user explicitly asked for Cycles GPU Compute. Detecting the
    idle device and then baking on CPU anyway meant the slow recovery path got slower
    still, while the panel named the exact device that would have worked -- so do what
    the message was asking the user to do. Returns ``(enabled, note)``; ``note`` is empty
    when nothing had to change.
    """
    try:
        import bpy

        addon = bpy.context.preferences.addons.get("cycles")
        if addon is None:
            return False, ""
        cycles_prefs = addon.preferences
        getter = getattr(cycles_prefs, "get_devices_for_type", None)
        if not callable(getter):
            return False, ""

        compute_type = str(getattr(cycles_prefs, "compute_device_type", "NONE") or "NONE")
        candidate_types = (
            [compute_type] if compute_type not in {"", "NONE"} else list(_CYCLES_COMPUTE_TYPES)
        )
        for candidate_type in candidate_types:
            try:
                devices = list(getter(candidate_type) or [])
            except Exception:
                continue
            gpu_devices = [
                device for device in devices if str(getattr(device, "type", "")).upper() != "CPU"
            ]
            if not gpu_devices:
                continue
            if candidate_type != compute_type:
                try:
                    cycles_prefs.compute_device_type = candidate_type
                except Exception:
                    continue
                # Re-read: switching the backend re-populates the device list.
                try:
                    gpu_devices = [
                        device
                        for device in (getter(candidate_type) or [])
                        if str(getattr(device, "type", "")).upper() != "CPU"
                    ]
                except Exception:
                    gpu_devices = []
            enabled_names = []
            for device in gpu_devices:
                if not getattr(device, "use", False):
                    try:
                        device.use = True
                    except Exception:
                        continue
                name = str(getattr(device, "name", "") or "").strip()
                if name:
                    enabled_names.append(name)
            if any(getattr(device, "use", False) for device in gpu_devices):
                # Say what actually happened: this writes Blender's own System
                # preferences and nothing restores them, so it also applies to the
                # artist's unrelated Cycles renders from here on. It used to read
                # "for this bake", which is where a user who had deliberately
                # disabled a device would go looking and find nothing to undo.
                return True, (
                    f"Enabled Cycles {candidate_type} compute "
                    f"({', '.join(enabled_names) or candidate_type}) in Blender's System "
                    "preferences (Preferences > System > Cycles Render Devices)"
                )
        return False, ""
    except Exception as exc:  # pragma: no cover - depends on live Blender prefs
        return False, f"Could not enable a Cycles compute device: {exc}"


def resolve_cycles_device(preferences_obj=None) -> tuple[str, str]:
    """Resolve the Cycles device for Cycles-primary/recovery bakes.

    Returns ``(device, note)``. ``device`` is always a value Cycles accepts; when
    GPU was requested but is unusable it degrades to CPU and ``note`` explains why.
    """
    prefs = preferences_obj
    if prefs is None:
        try:
            prefs = get_preferences()
        except Exception:
            prefs = None
    requested = normalize_cycles_device(getattr(prefs, "cycles_device", None) if prefs is not None else None)
    if requested != constants.CYCLES_DEVICE_GPU:
        return constants.CYCLES_DEVICE_CPU, ""
    available, reason = cycles_gpu_compute_available()
    if available:
        return constants.CYCLES_DEVICE_GPU, ""
    # GPU was explicitly requested and a capable device may simply be unselected. Turn it
    # on rather than degrading to CPU while reporting the device that would have worked.
    activated, activation_note = activate_cycles_gpu_compute()
    if activated:
        available, reason = cycles_gpu_compute_available()
        if available:
            return constants.CYCLES_DEVICE_GPU, activation_note
    return (
        constants.CYCLES_DEVICE_CPU,
        f"Cycles GPU Compute requested but unavailable, baking on CPU ({reason})",
    )


def bake_device_mode_to_execution_backend(value: str | None) -> str:
    bake_device = normalize_bake_device_mode(value)
    if bake_device == constants.BAKE_DEVICE_GPU:
        return constants.EXECUTION_BACKEND_GPU_PREFERRED
    return constants.EXECUTION_BACKEND_AUTO


def resolve_bake_device_mode(preferences_obj) -> str:
    if preferences_obj is None:
        return constants.BAKE_DEVICE_BOTH

    for property_name in ("bake_device", "execution_backend"):
        raw_value = _idprop_get(preferences_obj, property_name, None)
        if raw_value not in (None, ""):
            return normalize_bake_device_mode(raw_value)

    for property_name in ("bake_device", "execution_backend"):
        attr_value = getattr(preferences_obj, property_name, None)
        if attr_value not in (None, ""):
            return normalize_bake_device_mode(attr_value)

    return constants.BAKE_DEVICE_BOTH


def resolve_execution_backend_preference(preferences_obj) -> str:
    return bake_device_mode_to_execution_backend(resolve_bake_device_mode(preferences_obj))


def migrate_legacy_backend_preference(preferences_obj) -> None:
    if preferences_obj is None:
        return

    bake_device = resolve_bake_device_mode(preferences_obj)
    canonical_backend = bake_device_mode_to_execution_backend(bake_device)

    try:
        if getattr(preferences_obj, "bake_device", None) != bake_device:
            preferences_obj.bake_device = bake_device
    except Exception:
        pass

    try:
        if getattr(preferences_obj, "execution_backend", None) != canonical_backend:
            preferences_obj.execution_backend = canonical_backend
    except Exception:
        pass


def default_persistent_cache_root() -> Path:
    local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "FyrBaker" / "backend_cache"
    xdg_cache_home = str(os.environ.get("XDG_CACHE_HOME", "") or "").strip()
    if xdg_cache_home:
        return Path(xdg_cache_home) / "fyr_baker" / "backend_cache"
    home = str(os.environ.get("HOME", "") or "").strip()
    if home:
        return Path(home) / ".cache" / "fyr_baker" / "backend_cache"
    return Path(tempfile.gettempdir()) / "fyr_baker_backend_cache"


def persistent_cache_root() -> Path:
    override_root = str(os.environ.get(constants.CACHE_ROOT_ENV_VAR, "") or "").strip()
    if override_root:
        return Path(override_root)
    legacy_override_root = str(os.environ.get("MASTER_BAKER_CACHE_ROOT", "") or "").strip()
    if legacy_override_root:
        return Path(legacy_override_root)
    return default_persistent_cache_root()


def resolve_persistent_cache_budget_gb(preferences_obj=None) -> int:
    if preferences_obj is None:
        preferences_obj = get_preferences()
    raw_value = getattr(preferences_obj, "persistent_cache_budget_gb", constants.PERSISTENT_CACHE_BUDGET_GB_DEFAULT)
    try:
        return max(1, int(raw_value))
    except Exception:
        return constants.PERSISTENT_CACHE_BUDGET_GB_DEFAULT


def developer_mode_enabled(preferences_obj=None) -> bool:
    if preferences_obj is None:
        preferences_obj = get_preferences()
    if preferences_obj is None:
        return False

    raw_value = _idprop_get(preferences_obj, "developer_mode", None)
    if raw_value is None:
        raw_value = getattr(preferences_obj, "developer_mode", False)
    try:
        return bool(raw_value)
    except Exception:
        return False


def _env_flag_enabled(name: str) -> bool:
    value = str(os.environ.get(name, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def normalize_backend_prewarm_mode(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {
        constants.BACKEND_PREWARM_OFF,
        constants.BACKEND_PREWARM_ON_PROJECT_DETECTED,
        constants.BACKEND_PREWARM_ON_ADDON_LOAD,
    }:
        return normalized
    return constants.BACKEND_PREWARM_ON_PROJECT_DETECTED


def resolve_backend_prewarm_mode(preferences_obj=None) -> str:
    """Return the effective prewarm mode, honoring the env-var kill switch."""
    if _env_flag_enabled(constants.DISABLE_BACKEND_PREWARM_ENV_VAR):
        return constants.BACKEND_PREWARM_OFF
    if preferences_obj is None:
        preferences_obj = get_preferences()
    if preferences_obj is None:
        return constants.BACKEND_PREWARM_ON_PROJECT_DETECTED
    raw_value = _idprop_get(preferences_obj, "backend_prewarm_mode", None)
    if raw_value is None:
        raw_value = getattr(preferences_obj, "backend_prewarm_mode", None)
    return normalize_backend_prewarm_mode(raw_value)


def backend_prewarm_prepare_meshes_enabled(preferences_obj=None) -> bool:
    if preferences_obj is None:
        preferences_obj = get_preferences()
    if preferences_obj is None:
        return True
    raw_value = _idprop_get(preferences_obj, "backend_prewarm_prepare_meshes", None)
    if raw_value is None:
        raw_value = getattr(preferences_obj, "backend_prewarm_prepare_meshes", True)
    try:
        return bool(raw_value)
    except Exception:
        return True


_CACHE_USAGE_LOCK = threading.Lock()
_CACHE_USAGE_CACHE: dict[str, float | bool] = {"timestamp": 0.0, "bytes": -1.0, "pending": False}
_CACHE_USAGE_TTL_SECONDS = 4.0


def _format_gb(byte_count: float) -> str:
    """Human size for the cache readout.

    Always-GB formatting printed "0.0 GB" for anything under ~50 MB, which read as
    "the cache is empty" while the folder held real data.
    """
    value = max(0.0, float(byte_count))
    gigabytes = value / float(1024 ** 3)
    if gigabytes >= 1.0:
        return f"{gigabytes:.1f} GB"
    megabytes = value / float(1024 ** 2)
    if megabytes >= 1.0:
        return f"{megabytes:.0f} MB"
    return f"{value / 1024.0:.0f} KB"


def _cache_usage_worker() -> None:
    usage = -1
    try:
        from . import storage_cleanup

        usage = int(storage_cleanup.cache_root_usage_bytes())
    except Exception:
        usage = -1
    import time as _time

    with _CACHE_USAGE_LOCK:
        if usage >= 0:
            _CACHE_USAGE_CACHE["timestamp"] = _time.time()
            _CACHE_USAGE_CACHE["bytes"] = float(usage)
        _CACHE_USAGE_CACHE["pending"] = False


def _schedule_cache_usage_prefs_redraw() -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return

    def _tick():
        try:
            window_manager = getattr(getattr(bpy, "context", None), "window_manager", None)
            for window in getattr(window_manager, "windows", None) or []:
                screen = getattr(window, "screen", None)
                for area in getattr(screen, "areas", None) or []:
                    if getattr(area, "type", "") == "PREFERENCES":
                        area.tag_redraw()
        except Exception:
            pass
        return None

    try:
        timers.register(_tick, first_interval=0.25)
    except Exception:
        pass


def cached_cache_usage_bytes(*, force: bool = False) -> int:
    """Last-known persistent-cache usage in bytes.

    Never walk the cache tree on the calling thread. Preferences draw() used to
    ``rglob`` multi-GB trees while Blender still had last-frame UI blocks; that
    stalls WM_main and is the window for leftover string-widget RNA crashes.
    """
    import time as _time

    now = _time.time()
    with _CACHE_USAGE_LOCK:
        bytes_value = float(_CACHE_USAGE_CACHE["bytes"])
        timestamp = float(_CACHE_USAGE_CACHE["timestamp"])
        pending = bool(_CACHE_USAGE_CACHE["pending"])
        fresh = (
            not force
            and bytes_value >= 0.0
            and (now - timestamp) < _CACHE_USAGE_TTL_SECONDS
        )
        if fresh:
            return int(bytes_value)
        start_worker = not pending
        if start_worker:
            _CACHE_USAGE_CACHE["pending"] = True

    if start_worker:
        try:
            thread = threading.Thread(
                target=_cache_usage_worker,
                name="fyr-baker-cache-usage",
                daemon=True,
            )
            thread.start()
        except Exception:
            _cache_usage_worker()
        _schedule_cache_usage_prefs_redraw()
    return int(bytes_value) if bytes_value >= 0.0 else -1


def invalidate_cache_usage() -> None:
    with _CACHE_USAGE_LOCK:
        _CACHE_USAGE_CACHE["timestamp"] = 0.0
        _CACHE_USAGE_CACHE["bytes"] = -1.0
        _CACHE_USAGE_CACHE["pending"] = False


class MASTER_BAKER_OT_clean_caches_now(bpy.types.Operator):
    bl_idname = "master_baker.clean_caches_now"
    bl_label = "Clean Now"
    bl_description = (
        "Reclaim disk now: sweep stale FyrBaker files from the system temp folder and "
        "evict the oldest bake caches down to the size limit. In-progress bake data and "
        "recent caches are kept"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        del context
        from . import runtime

        snapshot = runtime.active_bake_snapshot()
        if snapshot is not None and getattr(snapshot, "running", False):
            self.report({"ERROR"}, "Stop the active bake before cleaning caches")
            return {"CANCELLED"}
        if clean_caches_in_progress():
            self.report({"INFO"}, "Cache clean-up is already running")
            return {"CANCELLED"}
        if not _launch_clean_caches(resolve_persistent_cache_budget_gb()):
            self.report({"ERROR"}, "Could not start the cache clean-up")
            return {"CANCELLED"}
        self.report({"INFO"}, "Cleaning caches in the background")
        return {"FINISHED"}


_CLEAN_CACHES_LOCK = threading.Lock()
_CLEAN_CACHES_STATE: dict = {"running": False, "summary": ""}


def clean_caches_in_progress() -> bool:
    with _CLEAN_CACHES_LOCK:
        return bool(_CLEAN_CACHES_STATE["running"])


def last_clean_caches_summary() -> str:
    with _CLEAN_CACHES_LOCK:
        return str(_CLEAN_CACHES_STATE["summary"] or "")


def run_clean_caches(budget_gb) -> str:
    """The Clean Now work: temp sweep, alias prune, budget enforcement. Filesystem only."""
    from . import high_mesh_cache, storage_cleanup

    removed_count = 0
    reclaimed_bytes = 0
    try:
        removed_count, temp_bytes = storage_cleanup.sweep_stale_system_temp()
        reclaimed_bytes += int(temp_bytes)
    except Exception:
        pass
    try:
        high_mesh_cache._prune_persistent_cache()
    except Exception:
        pass
    try:
        reclaimed_bytes += int(storage_cleanup.enforce_persistent_cache_budget(budget_gb))
    except Exception:
        pass
    return f"Cleaned caches: reclaimed {_format_gb(reclaimed_bytes)}" + (
        f", removed {removed_count} stale temp item(s)" if removed_count else ""
    )


def launch_cache_task(work_fn, *, fallback_summary: str, thread_name: str = "fyr-baker-cache-task") -> bool:
    """Run a cache-changing job off the UI thread; ``work_fn`` returns the summary.

    Clean Now and Clear Cache both walk and delete multi-GB trees (1.25 s just to
    size a 27 GB cache; Clear Cache removes ~18 000 files). Done inline from the
    button they held WM_main for the whole time, the same stall the usage readout
    was moved off the draw path for. One task at a time: the readout shows
    "Cleaning caches" meanwhile and both buttons are disabled.
    """
    with _CLEAN_CACHES_LOCK:
        if _CLEAN_CACHES_STATE["running"]:
            return False
        _CLEAN_CACHES_STATE["running"] = True
        _CLEAN_CACHES_STATE["summary"] = ""

    # bpy.app.timers.register is main-thread only: the worker used to call
    # _schedule_cache_usage_prefs_redraw directly and mutate Blender's timer list
    # concurrently with the main loop. Arm the main-thread call drain here (main
    # thread) and let the worker only POST the redraw request.
    from . import runtime as _runtime

    _runtime._arm_main_thread_call_timer()  # noqa: SLF001

    def _work():
        summary = fallback_summary
        try:
            summary = str(work_fn() or fallback_summary)
        except Exception:
            pass
        with _CLEAN_CACHES_LOCK:
            _CLEAN_CACHES_STATE["running"] = False
            _CLEAN_CACHES_STATE["summary"] = summary
        invalidate_cache_usage()
        _runtime._post_main_thread_call(_schedule_cache_usage_prefs_redraw)  # noqa: SLF001

    try:
        threading.Thread(target=_work, name=thread_name, daemon=True).start()
    except Exception:
        with _CLEAN_CACHES_LOCK:
            _CLEAN_CACHES_STATE["running"] = False
        _runtime._post_main_thread_call(_runtime._noop_main_thread_call)  # noqa: SLF001
        return False
    return True


def _launch_clean_caches(budget_gb) -> bool:
    return launch_cache_task(
        lambda: run_clean_caches(budget_gb),
        fallback_summary="Cleaned caches",
        thread_name="fyr-baker-clean-caches",
    )


class MASTER_BAKER_OT_open_cache_folder(bpy.types.Operator):
    bl_idname = "master_baker.open_cache_folder"
    bl_label = "Open Cache Folder"
    bl_description = "Open the folder where Fyr Baker stores reusable bake caches"
    bl_options = {"REGISTER"}

    def execute(self, context):
        del context
        import subprocess
        import sys

        root = persistent_cache_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.report({"ERROR"}, f"Could not create cache folder: {exc}")
            return {"CANCELLED"}
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(root))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_detect_external_applications(bpy.types.Operator):
    bl_idname = "master_baker.detect_external_applications"
    bl_label = "Auto-Detect"
    bl_description = (
        "Search this computer for installed external applications and fill in the path of the "
        "newest version found. Looks in the registry, the Program Files folders, Steam libraries "
        "and the common install folders on every fixed drive"
    )
    bl_options = {"REGISTER"}

    application: bpy.props.EnumProperty(
        name="Application",
        description="Which external application to search for",
        items=(
            ("ALL", "All", "Search for every supported application"),
            ("PAINTER", "Substance 3D Painter", "Search for Adobe Substance 3D Painter"),
            ("TOOLBAG", "Marmoset Toolbag", "Search for Marmoset Toolbag"),
            ("PHOTOSHOP", "Photoshop", "Search for Adobe Photoshop"),
            ("DESIGNER", "Substance 3D Designer", "Search for Substance 3D Designer"),
            ("COAT", "3DCoat", "Search for 3DCoat"),
            ("MARI", "Mari", "Search for Foundry Mari"),
        ),
        default="ALL",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        from . import external_handoff

        prefs = get_preferences()
        if prefs is None:
            self.report({"ERROR"}, "Fyr Baker preferences are unavailable")
            return {"CANCELLED"}

        targets = external_handoff.INTEGRATION_APPLICATIONS
        if self.application != "ALL":
            targets = tuple(item for item in targets if item[2] == self.application)

        found: list[str] = []
        missing: list[str] = []
        for key, prop_name, _detect_id in targets:
            label = external_handoff.APPLICATION_LABELS.get(key, key)
            try:
                # deep=True: the button is an explicit request, so pay for the wider sweep.
                candidates = external_handoff.discover_application_candidates(key, deep=True)
            except Exception as exc:
                self.report({"ERROR"}, f"{label} search failed: {exc}")
                return {"CANCELLED"}
            if not candidates:
                missing.append(label)
                continue
            newest = str(candidates[0])
            if str(getattr(prefs, prop_name, "") or "").strip() != newest:
                try:
                    setattr(prefs, prop_name, newest)
                except Exception as exc:
                    self.report({"ERROR"}, f"Could not store the {label} path: {exc}")
                    return {"CANCELLED"}
            found.append(f"{label}: {newest}")

        if found:
            # Written from script, so Blender does not mark the preferences dirty for us.
            try:
                context.preferences.is_dirty = True
            except Exception:
                pass
            self.report({"INFO"}, "Found " + "  |  ".join(found))
            return {"FINISHED"}
        self.report({"WARNING"}, f"Could not find {' or '.join(missing)}. Set the path manually")
        return {"CANCELLED"}


def _probed_gpu_adapters() -> list:
    """(name, VRAM MB, DXR tier) of the adapters the last capabilities check saw, one per
    name (a GPU behind a virtual display driver enumerates twice). Never probes."""
    try:
        from . import runtime

        verdict = runtime.last_backend_probe_verdict()
    except Exception:
        return []
    seen = {}
    for name, vram, tier in getattr(verdict, "adapters", ()) or ():
        if name not in seen or (seen[name][2] in ("", "UNKNOWN") and tier not in ("", "UNKNOWN")):
            seen[name] = (name, vram, tier)
    return list(seen.values())


class MASTER_BAKER_OT_set_gpu_adapter(bpy.types.Operator):
    bl_idname = "master_baker.set_gpu_adapter"
    bl_label = "Use This GPU"
    bl_description = "Bake on this GPU. Automatic picks the GPU with ray tracing and the most memory"
    bl_options = {"INTERNAL"}

    adapter_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        prefs = get_preferences()
        if prefs is None:
            return {"CANCELLED"}
        prefs.gpu_adapter = str(self.adapter_name or "")
        return {"FINISHED"}


class MASTER_BAKER_MT_gpu_adapter(bpy.types.Menu):
    bl_idname = "MASTER_BAKER_MT_gpu_adapter"
    bl_label = "Bake GPU"

    def draw(self, context):
        layout = self.layout
        layout.operator(MASTER_BAKER_OT_set_gpu_adapter.bl_idname, text="Automatic").adapter_name = ""
        for name, vram, tier in _probed_gpu_adapters():
            ray_tracing = tier not in ("", "UNKNOWN", "NOT_SUPPORTED")
            label = f"{name} ({vram / 1024:.0f} GB)" if vram >= 1024 else f"{name} ({vram} MB)"
            if tier == "NOT_SUPPORTED":
                label += ", no ray tracing"
            row = layout.row()
            row.enabled = ray_tracing or tier in ("", "UNKNOWN")
            row.operator(MASTER_BAKER_OT_set_gpu_adapter.bl_idname, text=label).adapter_name = name


class MasterBakerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    pref_tabs: bpy.props.EnumProperty(
        name="Settings",
        description="Choose a preference category",
        items=(
            ("GENERAL", "General", "Baking behavior, live bake, and viewport display", "SETTINGS", 0),
            ("PERFORMANCE", "Performance", "CPU use, first-bake preparation, and cache management", "MEMORY", 1),
            ("INTEGRATIONS", "Integrations", "External editors and which Send To entries are shown", "EXPORT", 2),
            ("EXPORT_TEMPLATES", "Output Templates", "Author the channel-packing templates used by Export Textures", "PRESET", 3),
            ("ADVANCED", "Advanced", "Developer and backend diagnostic options", "TOOL_SETTINGS", 4),
        ),
        default="GENERAL",
        options={"SKIP_SAVE"},
    )

    backend_executable: bpy.props.StringProperty(
        name="Backend Executable",
        subtype="FILE_PATH",
        default="",
        description="Choose a custom Fyr Baker backend executable, or leave blank to use the bundled version",
        # Mirrored: losing a custom backend path on update strands anyone who
        # keeps the backend somewhere non-standard, and the add-on then reports
        # "no backend" and drops to Cycles with no explanation.
        update=_mirror_setting_changed,
    )
    painter_executable: bpy.props.StringProperty(
        name="Substance 3D Painter",
        subtype="FILE_PATH",
        default="",
        description="Choose the Adobe Substance 3D Painter application used by Send to Painter",
    )
    toolbag_executable: bpy.props.StringProperty(
        name="Marmoset Toolbag",
        subtype="FILE_PATH",
        default="",
        description="Choose the Marmoset Toolbag application used by Send to Marmoset",
    )
    photoshop_executable: bpy.props.StringProperty(
        name="Photoshop",
        subtype="FILE_PATH",
        default="",
        description="Choose the Adobe Photoshop application used by Send to Photoshop",
    )
    designer_executable: bpy.props.StringProperty(
        name="Substance 3D Designer",
        subtype="FILE_PATH",
        default="",
        description="Choose the Substance 3D Designer application used by Send to Designer",
    )
    coat_executable: bpy.props.StringProperty(
        name="3DCoat",
        subtype="FILE_PATH",
        default="",
        description="Choose the 3DCoat application used by Send to 3DCoat",
    )
    mari_executable: bpy.props.StringProperty(
        name="Mari",
        subtype="FILE_PATH",
        default="",
        description="Choose the Foundry Mari application used by Send to Mari",
    )
    show_send_to_painter: bpy.props.BoolProperty(
        name="Painter",
        default=True,
        description="Show Send to Painter in the Send To menu",
    )
    show_send_to_toolbag: bpy.props.BoolProperty(
        name="Marmoset",
        default=True,
        description="Show Send to Marmoset in the Send To menu",
    )
    show_send_to_photoshop: bpy.props.BoolProperty(
        name="Photoshop",
        default=True,
        description="Show Send to Photoshop in the Send To menu",
    )
    show_send_to_designer: bpy.props.BoolProperty(
        name="Designer",
        default=True,
        description="Show Send to Substance Designer in the Send To menu",
    )
    show_send_to_coat: bpy.props.BoolProperty(
        name="3DCoat",
        default=True,
        description="Show Send to 3DCoat in the Send To menu",
    )
    show_send_to_mari: bpy.props.BoolProperty(
        name="Mari",
        default=True,
        description="Show Send to Mari in the Send To menu",
    )
    developer_mode: bpy.props.BoolProperty(
        name="Developer Mode",
        default=False,
        description="Prefer repo-local development backends, including build_profiling when present, over the bundled executable",
    )
    open_backend_log_window: bpy.props.BoolProperty(
        name="Live Backend Log Window",
        default=False,
        description="Open a separate, copyable log window whenever the bake worker starts",
    )
    #: Name of the GPU to bake on (FYR_BAKER_ADAPTER); empty = Automatic, the GPU with
    #: ray tracing and the most dedicated memory. A name, not the adapter's LUID: the LUID
    #: changes on every reboot.
    gpu_adapter: bpy.props.StringProperty(
        name="Bake GPU",
        default="",
        description="GPU Fyr bakes on. Empty picks the GPU with ray tracing and the most memory",
        update=_mirror_setting_changed,
    )
    render_backend: bpy.props.EnumProperty(
        name="Bake Renderer",
        items=constants.RENDER_BACKEND_ITEMS,
        default=constants.RENDER_BACKEND_AUTO,
        description=(
            "Choose the bake renderer. Auto uses FYR when the native GPU baker is available, "
            "otherwise Blender/Cycles. Force Cycles for A/B triage or when FYR cannot run"
        ),
    )
    bake_device: bpy.props.EnumProperty(
        name="Bake Device",
        items=constants.BAKE_DEVICE_ITEMS,
        default=constants.BAKE_DEVICE_BOTH,
        description=(
            "Choose the hardware used for FYR baking. "
            "Both uses the recommended hybrid CPU and GPU path; GPU prefers the fastest available GPU path. "
            "If GPU baking fails, supported maps hand off to Blender/Cycles"
        ),
    )
    cycles_device: bpy.props.EnumProperty(
        name="Cycles Device",
        items=constants.CYCLES_DEVICE_ITEMS,
        # GPU by default: resolve_cycles_device degrades to CPU (with a note the bake
        # report surfaces) whenever no Cycles compute device is enabled, so the only
        # thing a CPU default bought was a silently slow fallback on GPU machines.
        default=constants.CYCLES_DEVICE_GPU,
        description=(
            "Choose the hardware Cycles uses when it is the active bake renderer. "
            "GPU Compute uses the device configured in Blender Preferences > System"
        ),
    )
    execution_backend: bpy.props.EnumProperty(
        name="Execution Backend",
        items=constants.EXECUTION_BACKEND_PREFERENCE_ITEMS,
        default=constants.EXECUTION_BACKEND_AUTO,
        options={"HIDDEN"},
        description=(
            "Choose the processing path used for baking. Auto uses the GPU when available and "
            "hands off to Blender/Cycles when it is not. During hybrid bakes, GPU projection and "
            "CPU ray-traced maps can run together"
        ),
    )
    default_collection_mode: bpy.props.EnumProperty(
        name="New Project Collections",
        items=constants.COLLECTION_MODE_ITEMS,
        default=constants.COLLECTION_MODE_FYR,
        description="Choose how new bake projects organize their objects in the Outliner",
        # Mirrored: someone who bakes from their own collections would otherwise find
        # every new project building Fyr's collections again after an update.
        update=_mirror_setting_changed,
    )
    cage_lit_shading: bpy.props.BoolProperty(
        name="Cage Lit Shading",
        default=True,
        description=(
            "Shade Automatic cages with a light gradient when Average Normals is enabled. "
            "The gradient helps reveal surface curvature but is not physically accurate"
        ),
    )
    dirty_rebake_debounce: bpy.props.FloatProperty(
        name="Live Bake Debounce (s)",
        default=0.3,
        min=0.05,
        max=5.0,
        step=5,
        precision=2,
        description=(
            "Set how long Live Bake waits after the last scene change before starting "
            "an automatic incremental rebake"
        ),
    )
    cpu_threads: bpy.props.IntProperty(
        name="CPU Threads",
        default=0,
        min=0,
        max=64,
        description=(
            "Set the CPU threads used by ray-traced maps such as AO, Thickness, and Curvature. "
            "0 automatically uses most available cores"
        ),
    )
    persistent_cache_budget_gb: bpy.props.IntProperty(
        name="Cache Size Limit (GB)",
        default=constants.PERSISTENT_CACHE_BUDGET_GB_DEFAULT,
        min=1,
        max=1024,
        description=(
            "Set the approximate disk-space limit for reusable bake caches. "
            "When the limit is exceeded, Fyr Baker removes the oldest caches first and keeps any active bake data"
        ),
    )
    backend_prewarm_mode: bpy.props.EnumProperty(
        name="Bake Worker Startup",
        items=constants.BACKEND_PREWARM_MODE_ITEMS,
        default=constants.BACKEND_PREWARM_ON_PROJECT_DETECTED,
        description=(
            "Choose when to start the bake worker. Starting it early makes the first bake of a session begin faster"
        ),
        update=_mirror_setting_changed,
    )
    backend_prewarm_prepare_meshes: bpy.props.BoolProperty(
        name="Prepare Meshes Early",
        default=True,
        description=(
            "Prepare high-poly mesh data in advance so the first bake starts faster. "
            "Disable this if a problematic mesh prevents preparation from completing"
        ),
        update=_mirror_setting_changed,
    )
    backend_prewarm_first_run_acknowledged: bpy.props.BoolProperty(
        name="Prewarm First Run Acknowledged",
        default=False,
        options={"HIDDEN"},
        description="Internal flag; set after the user dismisses the prewarm explainer dialog",
        # The one that users notice: without it the first-run dialog returns
        # after every update and asks a question they already answered.
        update=_mirror_setting_changed,
    )
    backend_shaders_ready_signature: bpy.props.StringProperty(
        name="Backend Shaders Ready Signature",
        default="",
        options={"HIDDEN"},
        description="Internal: backend executable signature of the last successful bake (its GPU shaders are compiled)",
    )
    backend_prewarm_pso_priming_signature: bpy.props.StringProperty(
        name="Prewarm PSO Priming Signature",
        default="",
        options={"HIDDEN"},
        description="Internal: backend executable signature for which the on-disk pipeline cache has been primed",
    )
    warn_low_sample_count: bpy.props.BoolProperty(
        name="Warn About Low Sample Counts",
        default=True,
        description="Show a confirmation when a ray-traced map is reduced below 32 samples",
    )
    show_statusbar_progress: bpy.props.BoolProperty(
        name="Show Bake Progress in Status Bar",
        default=True,
        description=(
            "Show a live bake progress bar in Blender's bottom status bar, next to the "
            "scene statistics, while a bake is running"
        ),
    )
    bake_low_impact_viewport: bpy.props.BoolProperty(
        name="Quiet Viewport During Bake",
        default=True,
        description=(
            "Pause 3D viewport rendering and cage or coverage overlays during baking to reduce GPU use "
            "and finish faster. Bake progress remains visible, and the viewport resumes afterward"
        ),
    )
    bake_keep_viewport_live: bpy.props.BoolProperty(
        name="Keep Viewport Live During Bake",
        default=False,
        description=(
            "Keep the 3D viewport and overlays updating while a bake runs. "
            "This lets you watch the bake, but uses more GPU time and may make baking slower"
        ),
    )
    use_fast_aa_path: bpy.props.BoolProperty(
        name="Accelerated AA (RTX)",
        default=True,
        description=(
            "Use RTX hardware acceleration for faster anti-aliasing at high sample counts. "
            "Unsupported hardware or bake settings use the standard path automatically. "
            "Disable this to always use the standard path"
        ),
    )
    paint_offset_raise_color: bpy.props.FloatVectorProperty(
        name="Raised Offset",
        subtype="COLOR",
        size=3,
        default=(0.16, 0.50, 1.00),
        min=0.0,
        max=1.0,
        description="Default tint for Paint Offset where the cage is pushed further out. Each scene can change it in the Paint Offset brush options",
    )
    paint_offset_lower_color: bpy.props.FloatVectorProperty(
        name="Lowered Offset",
        subtype="COLOR",
        size=3,
        default=(1.00, 0.24, 0.20),
        min=0.0,
        max=1.0,
        description="Default tint for Paint Offset where the cage is pulled in. Each scene can change it in the Paint Offset brush options",
    )
    uv_preview_color: bpy.props.FloatVectorProperty(
        name="Preview Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 0.05, 0.75, 1.0),
        min=0.0,
        max=1.0,
        description="Set the color of the UV selection highlight in 3D Viewports",
    )
    uv_preview_face_opacity: bpy.props.FloatProperty(
        name="Face Opacity",
        default=0.20,
        min=0.0,
        max=1.0,
        description="Set the opacity of highlighted UV faces",
    )
    uv_preview_edge_width: bpy.props.FloatProperty(
        name="Edge Width",
        default=3.0,
        min=0.5,
        max=10.0,
        description="Set the width of highlighted UV edges and face outlines in pixels",
    )
    uv_preview_vertex_size: bpy.props.FloatProperty(
        name="Vertex Size",
        default=6.0,
        min=1.0,
        max=20.0,
        description="Set the size of highlighted UV vertices in pixels",
    )
    uv_preview_use_xray: bpy.props.BoolProperty(
        name="X-Ray",
        default=False,
        description="Show the UV selection highlight through occluding geometry",
    )
    uv_preview_show_face_fill: bpy.props.BoolProperty(
        name="Face Fill",
        default=True,
        description="Show a translucent fill on selected UV faces",
    )
    uv_preview_show_face_outline: bpy.props.BoolProperty(
        name="Face Outline",
        default=True,
        description="Show a bright outline around selected UV faces",
    )
    uv_preview_show_when_overlays_hidden: bpy.props.BoolProperty(
        name="Show When Overlays Are Hidden",
        default=False,
        description="Keep the UV selection highlight visible when viewport overlays are disabled",
    )
    update_check_mode: bpy.props.EnumProperty(
        name="Check for Updates",
        # A build packaged without the updater (the Superhive channel) offers
        # "Never" alone; the preference still exists so the rest of the add-on
        # has one place to read the mode from.
        items=update_policy.update_mode_items(),
        # Blender keeps online access off unless the user turns it on, so Fyr Baker
        # never contacts the network until the user picks an automatic mode here or
        # in the first-run dialog.
        default=update_policy.UPDATE_MODE_DEFAULT,
        description=(
            "Choose how often Fyr Baker checks for updates automatically. "
            "Update checks connect to the internet to look for new versions. "
            "You can also check at any time from the add-on preferences"
        ),
        update=_update_check_mode_changed,
    )
    viewport_controls_placement: bpy.props.EnumProperty(
        name="Overlay Controls",
        items=(
            ("HEADER", "Header", "Show the cage, low/high visibility, and map preview controls in the 3D viewport header"),
            ("OVERLAYS", "Overlays Menu", "Show the overlay controls inside the Viewport Overlays popover"),
            ("BOTH", "Header + Overlays", "Show the overlay controls in both the header and the Overlays popover"),
            ("NPANEL", "N-Panel Only", "Keep the overlay controls only in the Fyr Baker N-panel"),
        ),
        default="HEADER",
        description=(
            "Choose where the overlay-style viewport controls appear (cage overlay, "
            "low/high visibility, map preview). Bake and Send always stay in the header"
        ),
    )

    @staticmethod
    def _section(box, text, icon):
        """Left-aligned section header plus a split-form column for its props."""
        box.label(text=text, icon=icon)
        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False
        return col

    @staticmethod
    def _hint(container, lines, icon="NONE"):
        """Dimmed explanatory lines, for information the first-run dialog also shows."""
        hint = container.column(align=True)
        hint.enabled = False
        for index, line in enumerate(lines):
            hint.label(text=line, icon=icon if index == 0 else "NONE")
        return hint

    def _last_probed_gpu_name(self) -> str:
        """Adapter the backend's last capabilities check reported. Draw-safe: never probes."""
        if (
            normalize_render_backend_preference(getattr(self, "render_backend", None))
            == constants.RENDER_BACKEND_CYCLES
        ):
            return ""
        try:
            from . import runtime

            verdict = runtime.last_backend_probe_verdict()
        except Exception:
            return ""
        return str(getattr(verdict, "adapter_name", "") or "").strip() if verdict is not None else ""

    def _draw_general(self, box):
        from . import bake_backends

        col = self._section(box, "Baking", "RENDER_STILL")
        col.prop(self, "render_backend")
        gpu_name = self._last_probed_gpu_name()
        chosen = str(getattr(self, "gpu_adapter", "") or "").strip()
        if gpu_name or chosen or _probed_gpu_adapters():
            gpu_row = col.row(align=True)
            gpu_row.label(text="Bake GPU")
            gpu_row.menu(MASTER_BAKER_MT_gpu_adapter.bl_idname, text=chosen or "Automatic")
            if gpu_name:
                in_use = col.row()
                in_use.enabled = False
                in_use.label(text=f"In use: {gpu_name}")
        active_is_cycles = False
        try:
            active_is_cycles = (
                bake_backends.resolve_active_render_backend(self).backend_id == "cycles"
            )
        except Exception:
            active_is_cycles = (
                normalize_render_backend_preference(getattr(self, "render_backend", None))
                == constants.RENDER_BACKEND_CYCLES
            )
        if active_is_cycles:
            try:
                fallback_reason = bake_backends.auto_fallback_reason(self)
            except Exception:
                fallback_reason = ""
            if fallback_reason:
                info = col.row()
                info.enabled = False
                info.label(text=fallback_reason, icon="INFO")
            # FYR's CPU/GPU/DXR routing is meaningless under Cycles — offer the
            # renderer's own device instead of a dead control.
            col.prop(self, "cycles_device")
            if normalize_cycles_device(getattr(self, "cycles_device", None)) == constants.CYCLES_DEVICE_GPU:
                available, reason = cycles_gpu_compute_available()
                if not available:
                    warn = col.column()
                    warn.alert = True
                    warn.label(text=reason, icon="ERROR")
        else:
            col.prop(self, "bake_device")
        col.prop(self, "warn_low_sample_count")
        col.prop(self, "default_collection_mode")

        box.separator()
        col = self._section(box, "Live Bake", "TIME")
        col.prop(self, "dirty_rebake_debounce")

        box.separator()
        col = self._section(box, "Display", "RESTRICT_VIEW_OFF")
        col.prop(self, "viewport_controls_placement")
        col.prop(self, "show_statusbar_progress")
        col.prop(self, "cage_lit_shading")
        col.prop(self, "bake_low_impact_viewport")
        sub = col.column()
        sub.enabled = bool(getattr(self, "bake_low_impact_viewport", True))
        sub.prop(self, "bake_keep_viewport_live")

        box.separator()
        col = self._section(box, "Paint Offset", "BRUSH_DATA")
        col.prop(self, "paint_offset_raise_color")
        col.prop(self, "paint_offset_lower_color")

        box.separator()
        col = self._section(box, "UV Selection Preview", "UV_VERTEXSEL")
        col.prop(self, "uv_preview_color")
        col.prop(self, "uv_preview_face_opacity")
        col.prop(self, "uv_preview_edge_width")
        col.prop(self, "uv_preview_vertex_size")
        col.prop(self, "uv_preview_use_xray")
        col.prop(self, "uv_preview_show_face_fill")
        col.prop(self, "uv_preview_show_face_outline")
        col.prop(self, "uv_preview_show_when_overlays_hidden")

    def _draw_performance(self, box):
        from . import bake_backends

        active_is_cycles = False
        try:
            active_is_cycles = (
                bake_backends.resolve_active_render_backend(self).backend_id == "cycles"
            )
        except Exception:
            active_is_cycles = (
                normalize_render_backend_preference(getattr(self, "render_backend", None))
                == constants.RENDER_BACKEND_CYCLES
            )

        col = self._section(box, "Processing", "MEMORY")
        col.prop(self, "cpu_threads")
        if int(getattr(self, "cpu_threads", 0) or 0) == 0:
            hint = col.column()
            hint.enabled = False
            hint.label(text="0: automatic, uses most available cores")

        if not active_is_cycles:
            box.separator()
            col = self._section(box, "Anti-Aliasing", "MOD_SMOOTH")
            col.prop(self, "use_fast_aa_path")

            box.separator()
            col = self._section(box, "Bake Worker Startup", "PLAY")
            col.prop(self, "backend_prewarm_mode")
            sub = col.column()
            sub.enabled = self.backend_prewarm_mode != constants.BACKEND_PREWARM_OFF
            sub.prop(self, "backend_prewarm_prepare_meshes")
            # Same explanation the first-run dialog gives, for users who dismissed it
            # or never saw it (it can open behind the Preferences window).
            self._hint(
                box,
                (
                    "Fyr Baker can spawn its backend bake worker before you press Bake.",
                    "The first bake of a session is otherwise much slower because the backend",
                    "must start, initialize the GPU, compile pipelines, and load mesh caches.",
                ),
                icon="INFO",
            )

        box.separator()
        col = self._section(box, "Disk Cache", "DISK_DRIVE")
        col.prop(self, "persistent_cache_budget_gb")
        usage_row = col.row()
        usage_row.enabled = False
        try:
            usage_bytes = cached_cache_usage_bytes()
            usage_text = (
                f"Currently using {_format_gb(usage_bytes)}"
                if usage_bytes >= 0
                else "Measuring cache size…"
            )
        except Exception:
            usage_text = "Currently using unknown"
        if clean_caches_in_progress():
            usage_text = "Cleaning caches…"
        elif last_clean_caches_summary():
            usage_text = f"{usage_text}. {last_clean_caches_summary()}"
        usage_row.label(text=usage_text, icon="INFO")
        path_row = box.row()
        path_row.enabled = False
        path_row.label(text=str(persistent_cache_root()), icon="FILE_FOLDER")
        row = box.row(align=True)
        row.operator("master_baker.open_cache_folder", text="Open Cache Folder", icon_value=sidebar_icons.get_icon_value("open_folder"))
        clean_row = row.row(align=True)
        clean_row.enabled = not clean_caches_in_progress()
        clean_row.operator("master_baker.clean_caches_now", text="Clean Now", icon="BRUSH_DATA")
        clear_row = row.row(align=True)
        clear_row.enabled = not clean_caches_in_progress()
        clear_row.operator("master_baker.clear_all_caches", text="Clear Cache", icon="TRASH")

    def _draw_advanced(self, box):
        col = self._section(box, "Backend & Diagnostics", "CONSOLE")
        col.prop(self, "developer_mode")
        col.prop(self, "backend_executable")
        col.prop(self, "open_backend_log_window")

        box.separator()
        box.operator("master_baker.clear_logs", text="Clear Logs", icon="TRASH")


        # No updater in this build (Superhive channel): drawing a mode that can
        # only say "Never" next to a Check Now button that does not exist would
        # be worse than saying nothing.
        if update_policy.updater_available():
            box.separator()
            col = self._section(box, "Updates", "FILE_REFRESH")
            col.prop(self, "update_check_mode")
            self._hint(
                box,
                ("Update checks connect to the internet to look for new versions.",),
                icon="INFO",
            )
            row = box.row()
            row.operator("fyr_baker.check_updates", text="Check Now", icon="FILE_REFRESH")

            # Direct-channel builds download updates on behalf of the buyer's
            # Fyr account; this block is where that connection is made.
            box.separator()
            update_policy.draw_account_section(box)

    def _draw_integrations(self, box):
        # Same shape as _section(), plus a right-aligned "find them all" button on the header.
        header = box.row(align=True)
        header.label(text="External Applications", icon="EXPORT")
        detect_all = header.row(align=True)
        detect_all.alignment = "RIGHT"
        detect_all.operator("master_baker.detect_external_applications", text="Auto-Detect", icon="VIEWZOOM").application = "ALL"
        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False
        from . import external_handoff

        for _app_key, prop_name, detect_id in external_handoff.INTEGRATION_APPLICATIONS:
            row = col.row(align=True)
            row.prop(self, prop_name)
            row.operator("master_baker.detect_external_applications", text="", icon="VIEWZOOM").application = detect_id
        box.separator()
        shown = box.column(align=True)
        shown.label(text="Send To", icon="FORWARD")
        flow = shown.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for app_key, _prop_name, _detect_id in external_handoff.INTEGRATION_APPLICATIONS:
            flow.prop(self, external_handoff.send_to_visibility_property(app_key), toggle=True)

    def _draw_export_templates(self, box, context):
        # The whole editor lives in export_template_editor.py (staging state,
        # operators and drawing); this tab is only its mount point.
        from . import export_template_editor

        export_template_editor.draw_export_templates(box, context)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.35
        row.prop(self, "pref_tabs", expand=True)
        box = layout.box()
        if self.pref_tabs == "GENERAL":
            self._draw_general(box)
        elif self.pref_tabs == "PERFORMANCE":
            self._draw_performance(box)
        elif self.pref_tabs == "INTEGRATIONS":
            self._draw_integrations(box)
        elif self.pref_tabs == "EXPORT_TEMPLATES":
            self._draw_export_templates(box, context)
        else:
            self._draw_advanced(box)


CLASSES = (
    MASTER_BAKER_OT_set_gpu_adapter,
    MASTER_BAKER_MT_gpu_adapter,
    MASTER_BAKER_OT_clean_caches_now,
    MASTER_BAKER_OT_open_cache_folder,
    MASTER_BAKER_OT_detect_external_applications,
    MasterBakerPreferences,
)

_saved_prefs: dict = {}

_SKIP_PROP_NAMES = frozenset({
    "rna_type", "bl_idname", "bl_label", "bl_description",
    "bl_options", "bl_property", "bl_region_type", "bl_space_type",
})


def _save_prefs_to_dict(prefs) -> dict:
    if prefs is None:
        return {}
    result = {}
    try:
        prop_keys = prefs.bl_rna.properties.keys()
    except Exception:
        return result
    for key in prop_keys:
        if key in _SKIP_PROP_NAMES:
            continue
        try:
            value = getattr(prefs, key)
            # RNA array values are live proxy objects tied to the registered
            # AddonPreferences struct. Keeping the proxy across unregister made
            # re-enable iterate freed IDProperty memory and could crash Blender.
            if isinstance(value, (str, bytes, bool, int, float)) or value is None:
                result[key] = value
            elif isinstance(value, set):
                result[key] = set(value)
            else:
                try:
                    result[key] = tuple(value)
                except TypeError:
                    # Pointer/collection properties are not expected here and
                    # cannot be safely restored across RNA re-registration.
                    continue
        except Exception:
            pass
    return result


# Blender's File Paths > Applications panel. Appending here mirrors our
# Integrations paths into the native location artists expect, without moving
# storage off our AddonPreferences. The panel id has been stable since 4.x but
# is internal, so every hook is guarded and the append is best-effort.
_NATIVE_FILE_PATHS_PANEL = "USERPREF_PT_file_paths_applications"


def _draw_masterbaker_native_paths(self, context):
    prefs = get_preferences(migrate=False)
    if prefs is None:
        return
    from . import sidebar_icons

    layout = self.layout
    header = layout.row()
    icon_value = sidebar_icons.get_icon_value("fyr_baker")
    if icon_value:
        header.label(text="Fyr Baker", icon_value=icon_value)
    else:
        header.label(text="Fyr Baker", icon="EXPORT")
    col = layout.column(align=True)
    from . import external_handoff

    for _app_key, prop_name, detect_id in external_handoff.INTEGRATION_APPLICATIONS:
        row = col.row(align=True)
        row.prop(prefs, prop_name)
        row.operator("master_baker.detect_external_applications", text="", icon="VIEWZOOM").application = detect_id


def _register_native_file_paths():
    panel = getattr(bpy.types, _NATIVE_FILE_PATHS_PANEL, None)
    if panel is None:
        return
    try:
        panel.append(_draw_masterbaker_native_paths)
    except Exception:
        pass


def _unregister_native_file_paths():
    panel = getattr(bpy.types, _NATIVE_FILE_PATHS_PANEL, None)
    if panel is None:
        return
    try:
        panel.remove(_draw_masterbaker_native_paths)
    except Exception:
        pass


#: The legacy backend-preference migration writes RNA, so it must run once per
#: session from a non-draw path, never on every lookup (the File Paths panel hook
#: calls get_preferences() from inside Blender's draw).
_LEGACY_BACKEND_MIGRATED = False


def get_preferences(*, migrate: bool = True):
    global _LEGACY_BACKEND_MIGRATED
    context = getattr(bpy, "context", None)
    if context is None:
        return None
    context_preferences = getattr(context, "preferences", None)
    addons = getattr(context_preferences, "addons", None)
    if addons is None or not hasattr(addons, "get"):
        return None
    addon_entry = addons.get(__package__)
    if addon_entry is None:
        return None
    prefs = addon_entry.preferences
    if migrate and not _LEGACY_BACKEND_MIGRATED:
        _LEGACY_BACKEND_MIGRATED = True
        migrate_legacy_backend_preference(prefs)
    return prefs


def _default_resident_ram_cache_budget_gb() -> int:
    """A sane host-RAM cache budget so the resident worker bounds its resident
    high-scene/SDF/AO caches instead of growing unbounded.

    The backend's resident-RAM cache prune is DISABLED by default
    (FYR_BAKER_RAM_CACHE_BUDGET_GB unset → budget 0 → no eviction), which is why
    the worker ratchets host RAM up across bakes until OOM. We derive a budget
    from physical RAM (leaving headroom for Blender + the per-bake transient
    working set + the OS/other apps): ~25% of RAM, floored at 6 GB, capped at
    24 GB. On this 64 GB box that is 16 GB — enough to keep the active groups'
    geometry resident (no warm-bake thrash) while evicting stale LRU fields."""
    try:
        from . import storage_cleanup

        measured = storage_cleanup.available_system_memory()
        total_gb = (measured[1] / (1024 ** 3)) if measured else 0.0
    except Exception:
        total_gb = 0.0
    if total_gb <= 0.0:
        return 8
    budget = int(round(0.25 * total_gb))
    return max(6, min(budget, 24))


def build_backend_env() -> dict[str, str] | None:
    """Return an env dict with backend overrides, or None for the default environment."""
    prefs = get_preferences()
    if prefs is None:
        return None
    cpu_threads = int(getattr(prefs, "cpu_threads", 0) or 0)
    cache_budget_gb = resolve_persistent_cache_budget_gb(prefs)
    # Always set the resident-RAM cache budget unless the user pinned one via env,
    # so the backend's LRU prune is enabled (it is off by default → unbounded host
    # RAM growth → OOM). This keeps the worker warm and bounded without a restart.
    ram_budget_override = str(os.environ.get("FYR_BAKER_RAM_CACHE_BUDGET_GB", "") or "").strip()
    env = os.environ.copy()
    if cpu_threads > 0:
        env["FYR_BAKER_CPU_THREADS"] = str(cpu_threads)
    gpu_adapter = str(getattr(prefs, "gpu_adapter", "") or "").strip()
    if gpu_adapter:
        # A changed choice changes the env signature, so the resident worker restarts.
        env["FYR_BAKER_ADAPTER"] = gpu_adapter
    # Always publish the resolved disk-cache budget so the preference is authoritative.
    # (The backend's own built-in default differs, so omitting this at the addon default
    # value silently handed the worker a different budget than the UI showed.) An explicit
    # environment override still wins because os.environ.copy() already carries it and
    # setdefault below would not clobber it — but here the pref is the source of truth for
    # the addon-driven path, so we set it unconditionally.
    env.setdefault(constants.PERSISTENT_CACHE_BUDGET_ENV_VAR, str(cache_budget_gb))
    if not ram_budget_override:
        env["FYR_BAKER_RAM_CACHE_BUDGET_GB"] = str(_default_resident_ram_cache_budget_gb())
    # prepared_group_cache byte budget: the backend defaults to 12 GiB, which on
    # smaller machines lets the prepared entries alone crowd out the per-bake
    # working set (the memory watchdog then recycles the whole worker after most
    # heavy bakes — a ~20s background re-prewarm each time). ~10% of RAM keeps a
    # couple of full configurations resident while letting the cache evict itself
    # instead of escalating to a worker recycle.
    prepared_budget_override = str(
        os.environ.get("FYR_BAKER_PREPARED_GROUP_CACHE_BUDGET_GB", "") or ""
    ).strip()
    if not prepared_budget_override:
        try:
            from . import storage_cleanup

            measured = storage_cleanup.available_system_memory()
            total_gb = (measured[1] / (1024 ** 3)) if measured else 0.0
        except Exception:
            total_gb = 0.0
        prepared_budget_gb = max(3, min(int(round(0.10 * total_gb)), 12)) if total_gb > 0.0 else 6
        env["FYR_BAKER_PREPARED_GROUP_CACHE_BUDGET_GB"] = str(prepared_budget_gb)
    # Accelerated AA path: enable the DXR ray-gen hit generation + one-batch/sparse/
    # gpugen accumulation stack (a large speedup at high AA sample counts). setdefault
    # so an explicit environment override still wins; the backend gates each flag
    # per-bake and falls back to the raster path where unsupported, so the raster path
    # stays intact for older GPUs / unsupported configurations.
    if bool(getattr(prefs, "use_fast_aa_path", True)):
        for _key, _val in (
            ("FYR_BAKER_AA_DXR_HITGEN", "1"),
            ("FYR_BAKER_AA_ONEBATCH", "1"),
            ("FYR_BAKER_AA_SPARSE", "1"),
            ("FYR_BAKER_AA_GPUGEN", "1"),
            ("FYR_BAKER_MORTON_DISPATCH", "2"),
        ):
            env.setdefault(_key, _val)
    # The DISTANCE-cage closest-point rescue (FYR_BAKER_DISTANCE_NEAREST_FILL) is OFF.
    # It was signed off 2026-07-19 for white cavity splotches in concave folds; bounded
    # reach, the concave-cell rule, the low-occlusion rule and the v15/v16 convex bridge
    # now cover those. With a small Distance (customer shears, 1.149 mm) the cage sits
    # under a wrap lip's overhang and the rescue swapped correct hits for whichever high
    # point was nearest: a ragged splotch in every map that Automatic and a larger
    # Distance never show. Set the variable to 1 in the environment for an A/B.
    return env


def register():
    for cls in CLASSES:
        safe_register_class(cls)
    prefs = get_preferences()
    # Before anything reads them: an update rewrote the add-on package, and the
    # preference block that came back may be a fresh one holding defaults. The
    # config-directory mirror is outside the package and survives that, so it
    # wins here. See persistent_settings for why this cannot live in Blender's
    # own storage alone.
    persistent_settings.restore_into_preferences(prefs)
    # Blender keeps AddonPreferences values in its own IDProperty storage across
    # disable/enable. Reassigning a Python snapshot here is unnecessary and, in
    # Blender 5.1, can dereference an RNA array proxy whose owning struct was
    # destroyed during unregister. Never replay values into a freshly registered
    # AddonPreferences instance.
    _saved_prefs.clear()
    migrate_legacy_backend_preference(prefs)
    _register_native_file_paths()


def unregister():
    global _saved_prefs
    # Preference persistence belongs to Blender. Holding RNA-derived values
    # across class unregistration is unsafe even when most values appear scalar.
    _saved_prefs = {}
    _unregister_native_file_paths()
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
