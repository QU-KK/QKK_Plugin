from __future__ import annotations

from pathlib import Path


def backend_run_log_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "logs" / "backend_run.log"


def gpu_diagnostics_log_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "logs" / "gpu_diagnostics.log"


#: Appended to a bake failure report so the artist knows where the detail lives.
#: The panel already has Log and GPU Log buttons that open both files, so the
#: report points at those instead of printing two absolute paths nobody can click.
FAILURE_LOG_HINT = "Open Log or GPU Log in the Bake panel for the full details"


def backend_failure_messages(progress, *, progress_path: str | Path | None = None) -> list[str]:
    """User-facing lines for a failed bake, one per reported toast.

    ``progress_path`` is accepted for call-site compatibility and is no longer
    part of the message text; use ``backend_run_log_path`` /
    ``gpu_diagnostics_log_path`` directly when a caller needs the files (the
    support bundle and the Log buttons do).
    """
    messages: list[str] = []
    primary_message = getattr(progress, "message", "") or ""
    if primary_message:
        messages.append(primary_message)
    for message in list(getattr(progress, "errors", []))[:3]:
        if message and message not in messages:
            messages.append(message)
    messages.append(FAILURE_LOG_HINT)
    return messages


# Substrings the backend surfaces when a host/GPU allocation fails. `std::bad_alloc`
# stringifies to "bad allocation" on MSVC; the others cover CUDA/DX and generic OOM
# wording so the recovery path fires regardless of which allocator gave up.
_OUT_OF_MEMORY_MARKERS = (
    "bad allocation",
    "bad_alloc",
    "out of memory",
    "outofmemory",
    "cannot allocate",
    "allocation failed",
    "failed to allocate",
    "cuda_error_out_of_memory",
)


def failure_is_out_of_memory(progress) -> bool:
    """True when a backend failure looks like memory exhaustion (std::bad_alloc / OOM).

    The resident worker's host footprint grows across a long session; a large
    allocation (e.g. the Opacity postprocess of the biggest group) can then fail
    with a raw ``bad allocation``. Detecting that lets us restart the worker to
    reclaim memory and give the user an actionable message instead of C++ noise.
    """
    parts = [str(getattr(progress, "message", "") or "")]
    parts.extend(str(message or "") for message in getattr(progress, "errors", []) or [])
    haystack = " ".join(parts).lower()
    return any(marker in haystack for marker in _OUT_OF_MEMORY_MARKERS)


def out_of_memory_summary(raw_detail: str, *, restarted: bool) -> str:
    """A user-facing summary for an out-of-memory bake failure.

    Keeps the backend's group/map/stage context (which is genuinely useful) but
    leads with the cause and the recovery, so the panel no longer just says
    "bad allocation".
    """
    detail = str(raw_detail or "").strip()
    if restarted:
        recovery = (
            "The bake backend was restarted to reclaim memory. Press Bake to retry. "
            "If it recurs, lower the resolution or close other GPU/RAM-heavy apps."
        )
    else:
        recovery = (
            "Restart the backend (or Blender) and retry. Lowering the resolution "
            "or closing other GPU/RAM-heavy apps helps."
        )
    if detail:
        return f"Out of memory during the bake ({detail}). {recovery}"
    return f"Out of memory during the bake. {recovery}"
