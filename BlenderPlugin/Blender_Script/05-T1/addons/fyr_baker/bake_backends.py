"""Renderer-backend capability surface (FYR vs Cycles).

This is the Phase-0/1 seam from ``docs/CROSS_PLATFORM_BAKE_FALLBACK_PLAN.md``:
UI and bake dispatch branch on capabilities / resolved backend id, not
``sys.platform``.

Production default remains FYR on Windows when the native exe is available.
``render_backend=CYCLES`` (or AUTO when FYR is unavailable) routes supported
projection maps through ``cycles_projection`` without launching the FYR worker.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Literal

from . import constants, cycles_projection

MapFidelity = Literal["native", "approx", "unsupported"]
RenderBackendId = Literal["fyr", "cycles"]

CONTROL_SCOPE_PROJECT = "project"
CONTROL_SCOPE_GROUP = "group"
CONTROL_SCOPE_MAP = "map"

# These values are persisted even when their controls are hidden.  Switching back
# to Fyr therefore restores the artist's exact configuration instead of resetting
# it merely because Cycles was selected for one bake.
_CYCLES_UNSUPPORTED_PROJECT_CONTROLS = frozenset(
    {
        "aa_samples",
        "ignore_backface",
        "denoise_quality",
        "denoise_strength",
        "live_reproject",
    }
)
_CYCLES_UNSUPPORTED_GROUP_CONTROLS = frozenset(
    {
        "paint_offset_image",
        "paint_offset_scale",
        "paint_skew_image",
        "paint_skew",
        "show_skew_debug",
        "skew_debug_length",
        "skew_debug_constant_screen_size",
        "show_ray_miss_debug",
    }
)
_CYCLES_PROJECTION_MAP_CONTROLS = frozenset(
    {
        "samples",
        "output_suffix",
        # These selectors change the effective map type before Cycles planning.
        "curvature_output_mode",
        "lighting_output",
        # Material-detail compositing runs after either renderer completes.
        "material_detail_mode",
        "material_detail_image",
    }
)

_FYR_AVAILABILITY_CACHE: dict[str, object] = {
    "checked_at": 0.0,
    "available": False,
    "reason": "not probed yet",
}
_FYR_AVAILABILITY_TTL_S = 30.0


@dataclass(frozen=True)
class BackendCapabilities:
    """What a bake renderer can produce and which controls still apply."""

    backend_id: str
    label: str
    supported_maps: frozenset[str]
    map_fidelity: dict[str, MapFidelity]
    supports_aa_samples: bool
    supports_ao_diffusion_solver: bool
    supports_paint_skew_offset: bool
    supports_live_reproject: bool
    supports_debug_overlays: bool
    supports_cage_fit_accel: bool
    supports_denoise: bool
    exposes_execution_device: bool


@dataclass(frozen=True)
class ResolvedRenderBackend:
    """Concrete baker chosen for this session / bake."""

    backend_id: RenderBackendId
    label: str
    preference: str
    reason: str
    capabilities: BackendCapabilities


def _cycles_map_fidelity() -> dict[str, MapFidelity]:
    fidelity: dict[str, MapFidelity] = {}
    for map_type in constants.MAP_VALID_JOB_TYPES:
        strategy = cycles_projection.cycles_map_strategy(map_type)
        if strategy is None:
            if map_type in constants.CYCLES_UNSUPPORTED_MAP_TYPES:
                fidelity[map_type] = "unsupported"
            continue
        fidelity[map_type] = "approx" if strategy.approximate else "native"
    for map_type in constants.CYCLES_UNSUPPORTED_MAP_TYPES:
        fidelity[map_type] = "unsupported"
    return fidelity


def cycles_capabilities() -> BackendCapabilities:
    """Capabilities for Blender/Cycles recovery and Cycles-primary mode."""
    fidelity = _cycles_map_fidelity()
    supported = frozenset(
        map_type for map_type, level in fidelity.items() if level != "unsupported"
    )
    return BackendCapabilities(
        backend_id="cycles",
        label="Cycles (CPU/GPU)",
        supported_maps=supported,
        map_fidelity=fidelity,
        supports_aa_samples=False,
        supports_ao_diffusion_solver=False,
        supports_paint_skew_offset=False,
        supports_live_reproject=False,
        supports_debug_overlays=False,
        supports_cage_fit_accel=False,
        # The Cycles projection runner writes bpy bake results directly and does
        # not currently consume Fyr's denoise quality/strength settings.
        supports_denoise=False,
        exposes_execution_device=True,
    )


def fyr_capabilities() -> BackendCapabilities:
    """Capabilities for the native FYR GPU baker (production Windows path)."""
    supported = frozenset(constants.MAP_VALID_JOB_TYPES)
    fidelity = {map_type: "native" for map_type in supported}
    return BackendCapabilities(
        backend_id="fyr",
        label="FYR (GPU)",
        supported_maps=supported,
        map_fidelity=fidelity,
        supports_aa_samples=True,
        supports_ao_diffusion_solver=True,
        supports_paint_skew_offset=True,
        supports_live_reproject=True,
        supports_debug_overlays=True,
        supports_cage_fit_accel=True,
        supports_denoise=True,
        exposes_execution_device=True,
    )


def cycles_recovery_unsupported(map_type: str) -> bool:
    """True when FYR can bake this map but Cycles recovery cannot."""
    normalized = str(map_type or "").strip().upper()
    return cycles_capabilities().map_fidelity.get(normalized) == "unsupported"


def cycles_recovery_fidelity(map_type: str) -> MapFidelity | None:
    """Fidelity of Cycles recovery for ``map_type``, or None if unknown."""
    normalized = str(map_type or "").strip().upper()
    return cycles_capabilities().map_fidelity.get(normalized)


def normalize_render_backend_preference(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {
        constants.RENDER_BACKEND_AUTO,
        constants.RENDER_BACKEND_FYR,
        constants.RENDER_BACKEND_CYCLES,
    }:
        return normalized
    return constants.RENDER_BACKEND_AUTO


def resolve_render_backend_preference(preferences_obj=None) -> str:
    """Return the user-facing Bake Renderer preference (AUTO/FYR/CYCLES)."""
    prefs = preferences_obj
    if prefs is None:
        try:
            from . import preferences as preferences_module

            prefs = preferences_module.get_preferences()
        except Exception:
            prefs = None
    raw = getattr(prefs, "render_backend", None) if prefs is not None else None
    if raw is None and prefs is not None:
        getter = getattr(prefs, "get", None)
        if callable(getter):
            try:
                raw = getter("render_backend", constants.RENDER_BACKEND_AUTO)
            except Exception:
                raw = constants.RENDER_BACKEND_AUTO
    return normalize_render_backend_preference(raw)


_FYR_PROBE_THREAD = None


def _run_fyr_probe_now() -> tuple[bool, str]:
    available, reason = _probe_fyr_backend_blocking()
    _FYR_AVAILABILITY_CACHE["checked_at"] = time.monotonic()
    _FYR_AVAILABILITY_CACHE["available"] = available
    _FYR_AVAILABILITY_CACHE["reason"] = reason
    return available, reason


def _start_background_fyr_probe() -> None:
    """Probe off the main thread and redraw when done; never inside a draw."""
    global _FYR_PROBE_THREAD
    if _FYR_PROBE_THREAD is not None and _FYR_PROBE_THREAD.is_alive():
        return
    import threading

    def _work():
        global _FYR_PROBE_THREAD
        try:
            _run_fyr_probe_now()
        except BaseException as error:  # noqa: BLE001 - never let a worker thread print its own traceback
            print(f"[Fyr Baker] backend probe failed: {error!r}")
        finally:
            _FYR_PROBE_THREAD = None
            try:
                from . import runtime

                runtime._post_main_thread_call(_redraw_after_probe)  # noqa: SLF001
            except Exception:
                pass

    try:
        from . import runtime

        runtime._arm_main_thread_call_timer()  # noqa: SLF001
    except Exception:
        pass
    _FYR_PROBE_THREAD = threading.Thread(target=_work, name="fyr-baker-backend-probe", daemon=True)
    try:
        _FYR_PROBE_THREAD.start()
    except Exception:
        _FYR_PROBE_THREAD = None


def _redraw_after_probe() -> None:
    try:
        from . import overlays

        overlays.tag_redraw_all_view3d(sync_preview=False)
    except Exception:
        pass


def probe_fyr_backend_available(*, force_refresh: bool = False) -> tuple[bool, str]:
    """Whether the native FYR executable exists and reports a compatible version.

    Cached for a while. On a cache miss WITHOUT force_refresh the probe runs on a
    background thread and the call answers optimistically (FYR available) so a
    panel draw never spawns the backend (that blocked the first sidebar draw of a
    session for ~1.8 s, and up to 60 s per draw against a wedged exe). Bake
    launches pass force_refresh=True and get the real, blocking answer.
    """
    now = time.monotonic()
    checked_at = float(_FYR_AVAILABILITY_CACHE.get("checked_at", 0.0) or 0.0)
    if (
        not force_refresh
        and checked_at > 0.0
        and (now - checked_at) < _FYR_AVAILABILITY_TTL_S
    ):
        return (
            bool(_FYR_AVAILABILITY_CACHE.get("available")),
            str(_FYR_AVAILABILITY_CACHE.get("reason") or ""),
        )
    if not force_refresh:
        _start_background_fyr_probe()
        if checked_at > 0.0:
            # Stale but known: keep answering with it until the refresh lands.
            return (
                bool(_FYR_AVAILABILITY_CACHE.get("available")),
                str(_FYR_AVAILABILITY_CACHE.get("reason") or ""),
            )
        return True, "Checking the FYR backend"
    # Bake launch: a negative GPU verdict may have been a transient (driver not
    # ready, device reset, discrete GPU briefly failing so the iGPU was picked).
    # Let a stale one be re-probed here, and only here, so draws never pay for it.
    _expire_stale_negative_gpu_verdicts()
    return _run_fyr_probe_now()


def _expire_stale_negative_gpu_verdicts() -> None:
    # A runtime that was never imported holds no verdicts to expire, and importing it
    # here would bind it to whatever bpy the caller has (a test's fake, at worst).
    runtime = sys.modules.get(f"{__package__}.runtime")
    if runtime is None:
        return
    try:
        expire = getattr(runtime, "expire_stale_negative_backend_verdicts", None)
        if callable(expire):
            expire()
    except Exception:
        pass


def _probe_fyr_backend_blocking() -> tuple[bool, str]:
    available = False
    reason = "FYR backend executable was not found"
    try:
        from . import runtime

        backend_path = runtime.resolve_backend_executable()
        runtime.ensure_backend_compatible(backend_path)
        available = True
        reason = f"FYR backend available ({backend_path.name})"
    except FileNotFoundError as exc:
        reason = str(exc) or reason
    except Exception as exc:
        reason = str(exc) or "FYR backend probe failed"
    return available, reason


def resolve_active_render_backend(
    preferences_obj=None,
    *,
    force_refresh: bool = False,
) -> ResolvedRenderBackend:
    """Resolve AUTO/FYR/CYCLES preference into the concrete baker for this bake/UI."""
    preference = resolve_render_backend_preference(preferences_obj)
    if preference == constants.RENDER_BACKEND_CYCLES:
        caps = cycles_capabilities()
        return ResolvedRenderBackend(
            backend_id="cycles",
            label=caps.label,
            preference=preference,
            reason="Bake Renderer preference is Cycles",
            capabilities=caps,
        )

    available, reason = probe_fyr_backend_available(force_refresh=force_refresh)
    if preference == constants.RENDER_BACKEND_FYR:
        if available:
            caps = fyr_capabilities()
            return ResolvedRenderBackend(
                backend_id="fyr",
                label=caps.label,
                preference=preference,
                reason=reason,
                capabilities=caps,
            )
        raise RuntimeError(
            "FYR bake renderer is unavailable: "
            f"{reason}. Choose Auto or Cycles in Add-on Preferences."
        )

    # AUTO
    if available:
        caps = fyr_capabilities()
        return ResolvedRenderBackend(
            backend_id="fyr",
            label=caps.label,
            preference=preference,
            reason=reason,
            capabilities=caps,
        )
    caps = cycles_capabilities()
    return ResolvedRenderBackend(
        backend_id="cycles",
        label=caps.label,
        preference=preference,
        reason=f"AUTO selected Cycles because FYR is unavailable ({reason})",
        capabilities=caps,
    )


def auto_fallback_reason(preferences_obj=None) -> str:
    """Short UI text for why AUTO landed on Cycles, or "" when it did not.

    Prefers the backend's own GPU verdict ("No DirectX Raytracing on <adapter>")
    over the generic probe message, so the panel says what is actually wrong with
    this machine rather than "FYR is unavailable". Draw-safe: never probes.
    """
    try:
        resolved = resolve_active_render_backend(preferences_obj)
    except RuntimeError:
        return ""
    if resolved.backend_id != "cycles" or resolved.preference != constants.RENDER_BACKEND_AUTO:
        return ""
    try:
        from . import runtime

        verdict = runtime.last_backend_probe_verdict()
    except Exception:
        verdict = None
    if verdict is not None and not verdict.gpu_projection_available and verdict.gpu_unavailable_reason:
        return str(verdict.gpu_unavailable_reason)
    _available, reason = probe_fyr_backend_available()
    return str(reason or "")


def fyr_native_lifecycle_enabled(preferences_obj=None) -> bool:
    """Whether the FYR worker, prewarm, and FYR-only preference blocks should run.

    Cycles-primary (forced, or AUTO with no native exe) must not spawn
    ``fyr_baker_backend`` or show Bake Worker Startup. Stored FYR values stay
    untouched so switching back to Fyr restores the artist's setup.
    """
    try:
        return resolve_active_render_backend(preferences_obj).backend_id == "fyr"
    except RuntimeError:
        return False


def active_capabilities(preferences_obj=None) -> BackendCapabilities:
    """Capabilities for the currently resolved baker (safe for UI draw)."""
    try:
        return resolve_active_render_backend(preferences_obj).capabilities
    except RuntimeError:
        # Forced FYR with a missing exe — UI still needs a capability set.
        return fyr_capabilities()


def control_supported(
    scope: str,
    property_name: str,
    *,
    map_type: str | None = None,
    capabilities: BackendCapabilities | None = None,
) -> bool:
    """Return whether the active renderer consumes one artist-facing control.

    This is deliberately a UI capability query, not a dispatch rule.  It keeps
    renderer-specific property visibility in one place while leaving stored RNA
    values and bake routing untouched.
    """
    caps = capabilities or active_capabilities()
    if caps.backend_id != "cycles":
        return True

    normalized_scope = str(scope or "").strip().lower()
    normalized_property = str(property_name or "").strip()
    if normalized_scope == CONTROL_SCOPE_PROJECT:
        return normalized_property not in _CYCLES_UNSUPPORTED_PROJECT_CONTROLS
    if normalized_scope == CONTROL_SCOPE_GROUP:
        return normalized_property not in _CYCLES_UNSUPPORTED_GROUP_CONTROLS
    if normalized_scope == CONTROL_SCOPE_MAP:
        normalized_map_type = str(map_type or "").strip().upper()
        # Material rows are produced by the material-capture pipeline, whose
        # controls remain meaningful when Cycles is the selected renderer.
        if normalized_map_type == constants.MAP_MATERIAL:
            return True
        return normalized_property in _CYCLES_PROJECTION_MAP_CONTROLS
    return True
