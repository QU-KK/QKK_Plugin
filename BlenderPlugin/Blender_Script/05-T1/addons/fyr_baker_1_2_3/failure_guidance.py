"""Turn raw bake failure text into guidance the artist can act on.

Testers could not tell whether a failed bake came from their scene setup or from
the renderer. The backend, Blender's bake operator and the Cycles recovery route
all fail with precise but technical text; this module recognises the known ones
and says which side the problem is on (SETUP, GPU or RENDERER), what it means,
and what to do next. The raw text is never replaced, only explained: callers show
it alongside the guidance.

Every pattern below is a lowercase substring of a real failure string, quoted in
the comment above its rule with the file that produces it. Keep them in sync when
those strings change; ``tests/test_failure_guidance.py`` feeds each source string
through the classifier.

Pure Python on purpose (no bpy): the classifier is unit-tested outside Blender.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

CATEGORY_SETUP = "SETUP"
CATEGORY_GPU = "GPU"
CATEGORY_RENDERER = "RENDERER"

CATEGORY_LABELS = {
    CATEGORY_SETUP: "Setup issue",
    CATEGORY_GPU: "GPU issue",
    CATEGORY_RENDERER: "Renderer issue",
}


@dataclass(frozen=True)
class FailureGuidance:
    """What a failure means for the artist: whose problem it is and the next step."""

    category: str
    title: str
    fix: str


@dataclass(frozen=True)
class _Rule:
    patterns: tuple[str, ...]
    guidance: FailureGuidance


_GPU_RETRY_FIX = (
    "Update the GPU driver, close other GPU-heavy apps and bake again; "
    "Fyr re-checks the GPU on the next bake."
)

# Order is priority. When several failure lines are available (a GPU error plus the
# Cycles retry's own errors), the earliest matching rule wins, so setup problems the
# artist can fix come first, then specific GPU causes, then the generic fallbacks.
_RULES: tuple[_Rule, ...] = (
    # backend/src/master_baker_backend_gpu_d3d12.cpp:
    #   "GPU_GROUP_TOO_LARGE: bake group '<g>' has <n> high-poly triangles, more than ..."
    #   "GPU_GROUP_TOO_LARGE: bake group '<g>' needs about <n> MB of VRAM for hardware ray
    #    tracing (...), but only <n> MB of the <n> MB budget is free. ..."
    _Rule(
        ("gpu_group_too_large",),
        FailureGuidance(
            CATEGORY_SETUP,
            "A bake group is too large for the GPU",
            "Split the group into smaller bake groups, one per part, or reduce the high-poly meshes.",
        ),
    ),
    # addon/blender_bake.py: "Blender cannot bake high 'X': the object is not visible and
    #   selectable in the active view layer (check collection exclusion, ...)"
    # Blender object_bake_api.cc: 'Object "X" is not in view layer',
    #   'Object "X" is not enabled for rendering',
    #   'Object "X" not found in evaluated scene, it may be hidden',
    #   'Failed to access mesh from object "X", ensure it\'s visible while rendering',
    #   "No valid selected objects"
    _Rule(
        (
            "not visible and selectable",
            "is not in view layer",
            "is not enabled for rendering",
            "not found in evaluated scene, it may be hidden",
            "ensure it's visible while rendering",
            "no valid selected objects",
        ),
        FailureGuidance(
            CATEGORY_SETUP,
            "An object in the bake is hidden or not selectable",
            "Make the named object visible, selectable and renderable in this view layer, "
            "and leave local view before baking again.",
        ),
    ),
    # Blender object_bake_api.cc: 'No active UV layer found in the object "X"',
    #   'No UV layer named "U" found in the object "X"',
    #   'No UV map found in the evaluated object "X"'
    # addon/udim.py: "X: no UV layer to read tiles from"
    _Rule(
        (
            "no active uv layer found",
            "no uv layer named",
            "no uv map found in the evaluated object",
            "no uv layer to read tiles from",
        ),
        FailureGuidance(
            CATEGORY_SETUP,
            "A low-poly mesh has no UV map",
            "Add or unwrap a UV map on the named low-poly mesh and bake again.",
        ),
    ),
    # backend/src/master_baker_backend.cpp: "Bake group 'G' has no high meshes"
    # addon/cycles_projection.py: "Cycles fallback skipped NORMAL for group 'G': no high objects"
    _Rule(
        ("has no high meshes", "no high objects"),
        FailureGuidance(
            CATEGORY_SETUP,
            "A bake group has no high-poly mesh",
            "Assign at least one high-poly mesh to the group, or turn off the maps that need one.",
        ),
    ),
    # backend/src/master_baker_backend.cpp: "Bake group 'G' has no low meshes"
    # addon/cycles_projection.py: "Cycles fallback skipped for group 'G': no low objects"
    _Rule(
        ("has no low meshes", "no low objects"),
        FailureGuidance(
            CATEGORY_SETUP,
            "A bake group has no low-poly mesh",
            "Assign the low-poly mesh the maps should be baked onto to the group and bake again.",
        ),
    ),
    # addon/cycles_projection.py:
    #   "Cycles fallback skipped for group 'G': missing low object(s): A, B"
    #   "Cycles fallback skipped NORMAL for group 'G': missing high object(s): A"
    _Rule(
        ("missing low object(s)", "missing high object(s)"),
        FailureGuidance(
            CATEGORY_SETUP,
            "A mesh assigned to a bake group is no longer in the scene",
            "Restore or reassign the named mesh in the bake group, then bake again.",
        ),
    ),
    # Blender object_bake_api.cc: 'No faces found in the object "X"'
    _Rule(
        ("no faces found in the object",),
        FailureGuidance(
            CATEGORY_SETUP,
            "A mesh in the bake has no faces",
            "Remove the empty mesh from the bake group or give it geometry, then bake again.",
        ),
    ),
    # Blender object_bake_api.cc: "Invalid cage object, the cage mesh must have the same
    #   number of faces as the active object", "No valid cage object"
    _Rule(
        ("the cage mesh must have the same number of faces", "no valid cage object"),
        FailureGuidance(
            CATEGORY_SETUP,
            "The custom cage does not match the low-poly mesh",
            "Rebuild the cage from the current low-poly mesh so both have the same faces, "
            "or switch the group to an automatic cage.",
        ),
    ),
    # backend/src/backend_file_io.cpp: "Failed to write file: <path>"
    # Blender object_bake_api.cc: 'Problem saving baked map in "<path>"'
    _Rule(
        ("failed to write file:", "problem saving baked map in"),
        FailureGuidance(
            CATEGORY_SETUP,
            "The baked map could not be saved",
            "Check that the output folder exists, is writable and has free disk space, then bake again.",
        ),
    ),
    # backend/src/master_baker_backend_gpu_d3d12.cpp:
    #   "No D3D12-capable hardware adapter was found" (before 2026-10-17),
    #   "No usable D3D12 GPU: <every adapter with its device-creation result>"
    # addon/runtime.py: "No DirectX 12 device (<detail>)"
    _Rule(
        ("no d3d12-capable hardware adapter", "no usable d3d12 gpu", "no directx 12 device"),
        FailureGuidance(
            CATEGORY_GPU,
            "No DirectX 12 GPU was found",
            _GPU_RETRY_FIX,
        ),
    ),
    # backend/src/master_baker_backend_gpu_d3d12.cpp: "D3D12CreateDevice failed (<hresult>)",
    #   "CreateDXGIFactory1 failed (<hresult>)"
    _Rule(
        ("d3d12createdevice failed", "createdxgifactory1 failed"),
        FailureGuidance(
            CATEGORY_GPU,
            "The GPU could not be started for baking",
            _GPU_RETRY_FIX,
        ),
    ),
    # backend/src/master_baker_backend_gpu_d3d12.cpp: "DXR projection device removed (",
    #   "D3D12 projection shading device removed (", "D3D12 device removed during fence wait",
    #   hresult names DXGI_ERROR_DEVICE_REMOVED / _HUNG / _RESET / DXGI_ERROR_DRIVER_INTERNAL_ERROR
    # addon/runtime_bake_worker.py device-loss tokens: "device lost", "device hung"
    _Rule(
        (
            "device removed",
            "dxgi_error_device_removed",
            "dxgi_error_device_hung",
            "dxgi_error_device_reset",
            "dxgi_error_driver_internal_error",
            "device_hung",
            "device hung",
            "device lost",
        ),
        FailureGuidance(
            CATEGORY_GPU,
            "The GPU stopped responding during the bake",
            _GPU_RETRY_FIX,
        ),
    ),
    # addon/runtime.py: "No DirectX Raytracing on <adapter>"
    # backend/src/backend_bake_pipeline.cpp: "DXR is not supported by the active adapter",
    #   "DXR hardware support could not be confirmed on the active adapter",
    #   "DXR runtime prerequisites are unavailable"
    _Rule(
        (
            "no directx raytracing",
            "dxr is not supported by the active adapter",
            "dxr hardware support could not be confirmed",
            "dxr runtime prerequisites are unavailable",
        ),
        FailureGuidance(
            CATEGORY_GPU,
            "This GPU has no hardware ray tracing",
            "Fyr needs a ray tracing GPU, so this machine bakes through Blender Cycles; "
            "update the GPU driver if the card should support ray tracing.",
        ),
    ),
    # backend/src/backend_bake_pipeline.cpp / master_baker_backend.cpp:
    #   "GPU_UNAVAILABLE_USE_CYCLES: <reason>. Addon should retry via Blender/Cycles."
    _Rule(
        ("gpu_unavailable_use_cycles",),
        FailureGuidance(
            CATEGORY_GPU,
            "No usable GPU was available for the bake",
            _GPU_RETRY_FIX,
        ),
    ),
    # addon/cycles_projection.py: "Cycles fallback does not support map 'X' for group 'G': ..."
    _Rule(
        ("cycles fallback does not support map",),
        FailureGuidance(
            CATEGORY_RENDERER,
            "Blender Cycles cannot bake this map type",
            "Turn off the named map for this bake, or bake it on a ray tracing GPU with Fyr.",
        ),
    ),
    # backend/src/master_baker_backend.cpp:
    #   "GPU_FAILED_USE_CYCLES: GPU projection failed (<detail>). Addon should retry via ..."
    #   "GPU_FAILED_USE_CYCLES: GPU shading failed (<detail>). Addon should retry via ..."
    _Rule(
        ("gpu_failed_use_cycles",),
        FailureGuidance(
            CATEGORY_RENDERER,
            "The GPU bake failed inside Fyr",
            "Bake again, and if it fails the same way, create a Support Bundle from the Bake panel and send it in.",
        ),
    ),
    # addon/cycles_projection.py: "Cycles bake failed for G/MAP: <Blender error>"
    _Rule(
        ("cycles bake failed for",),
        FailureGuidance(
            CATEGORY_RENDERER,
            "Blender Cycles could not bake a map",
            "Read the Blender error in the details, fix the object it names and bake again.",
        ),
    ),
)


def _match_rule_index(text: str) -> int | None:
    lowered = str(text or "").lower()
    if not lowered.strip():
        return None
    for index, rule in enumerate(_RULES):
        if any(pattern in lowered for pattern in rule.patterns):
            return index
    return None


def explain_failure(text: str) -> FailureGuidance | None:
    """Guidance for one raw failure line, or None when the text is not recognised."""
    index = _match_rule_index(text)
    return None if index is None else _RULES[index].guidance


def explain_failures(texts: Iterable[str]) -> tuple[FailureGuidance, str] | None:
    """Best guidance across several failure lines, plus the raw line it explains.

    Rule order decides, not line order: a setup problem in the Cycles retry's errors
    outranks the generic GPU error that triggered the retry, because it is the one
    the artist can fix.
    """
    best: tuple[int, str] | None = None
    for text in texts or ():
        index = _match_rule_index(text)
        if index is None:
            continue
        if best is None or index < best[0]:
            best = (index, str(text))
    if best is None:
        return None
    return _RULES[best[0]].guidance, best[1]


def format_guided_message(guidance: FailureGuidance, raw: str) -> str:
    """"Setup issue: <title>. <fix> (details: <raw>)" with the raw text kept verbatim."""
    label = CATEGORY_LABELS.get(guidance.category, "Bake issue")
    message = f"{label}: {guidance.title}. {guidance.fix}"
    raw_text = str(raw or "").strip()
    if raw_text:
        message = f"{message} (details: {raw_text})"
    return message


def guided_message(raw: str) -> str:
    """The guided form of one failure line, or the raw line unchanged when unknown."""
    guidance = explain_failure(raw)
    return raw if guidance is None else format_guided_message(guidance, raw)


def all_guidance() -> tuple[FailureGuidance, ...]:
    """Every guidance entry, in priority order (for tests and docs)."""
    return tuple(rule.guidance for rule in _RULES)
