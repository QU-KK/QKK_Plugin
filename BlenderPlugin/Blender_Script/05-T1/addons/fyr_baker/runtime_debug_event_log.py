from __future__ import annotations

import json
from pathlib import Path


def format_debug_log_value(value) -> str:
    if isinstance(value, Path):
        value = str(value)
    elif isinstance(value, bool):
        value = bool(value)
    elif isinstance(value, (list, tuple)):
        value = list(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def debug_overlay_scope_label(project=None, group=None) -> str:
    project_name = str(getattr(project, "name", "") or "").strip()
    group_name = str(getattr(group, "name", "") or "").strip()
    if project_name and group_name:
        return f"{project_name} / {group_name}"
    return group_name or project_name


def format_duration_ms(value) -> str:
    try:
        return f"{int(round(float(value)))} ms"
    except Exception:
        return str(value)


def format_debug_overlay_event_block(
    event: str,
    *,
    project=None,
    group=None,
    fields: dict[str, object],
    live_log_time_text_fn,
    short_log_path_fn,
) -> str:
    title = event.replace("-", " ").title()
    details: list[str] = []
    scope_label = debug_overlay_scope_label(project, group)
    if event == "worker-start":
        title = "Debug worker ready"
        backend_name = str(fields.get("backend_name", "") or "").strip()
        backend_version = str(fields.get("backend_version", "") or "").strip()
        if backend_name:
            detail = f"Backend: {backend_name}"
            if backend_version:
                detail += f" ({backend_version})"
            details.append(detail)
    elif event == "launch":
        title = "Overlay refresh started"
        if scope_label:
            details.append(f"Target: {scope_label}")
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        low_mesh_count = fields.get("low_mesh_count", None)
        high_mesh_count = fields.get("high_mesh_count", None)
        cage_mode = str(fields.get("cage_mode", "") or "").strip()
        cage_offset = fields.get("cage_offset", None)
        input_parts = []
        if low_mesh_count is not None:
            input_parts.append(f"low {int(low_mesh_count)}")
        if high_mesh_count is not None:
            input_parts.append(f"high {int(high_mesh_count)}")
        if cage_mode:
            input_parts.append(f"cage {cage_mode}")
        if cage_offset is not None:
            input_parts.append(f"offset {float(cage_offset):.3f}")
        if input_parts:
            details.append("Inputs: " + ", ".join(input_parts))
        job_path = short_log_path_fn(fields.get("job_path"), parts=3)
        if job_path:
            details.append(f"Job: {job_path}")
    elif event == "run":
        title = "Running backend overlay job"
        group_name = str(fields.get("group_name", "") or "").strip()
        if group_name:
            details.append(f"Group: {group_name}")
        job_path = short_log_path_fn(fields.get("job_path"), parts=3)
        if job_path:
            details.append(f"Job: {job_path}")
    elif event == "ok":
        title = "Backend overlay job finished"
        elapsed_ms = fields.get("elapsed_ms", None)
        if elapsed_ms is not None:
            details.append(f"Backend time: {format_duration_ms(elapsed_ms)}")
        output_path = short_log_path_fn(fields.get("output_path"), parts=3)
        if output_path:
            details.append(f"Output: {output_path}")
    elif event == "result":
        title = "Overlay ready"
        if scope_label:
            details.append(f"Target: {scope_label}")
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        time_parts = []
        if fields.get("backend_elapsed_ms", None) is not None:
            time_parts.append(f"backend {format_duration_ms(fields['backend_elapsed_ms'])}")
        if fields.get("total_ms", None) is not None:
            time_parts.append(f"total {format_duration_ms(fields['total_ms'])}")
        if fields.get("queue_ms", None) is not None:
            time_parts.append(f"queue {format_duration_ms(fields['queue_ms'])}")
        if time_parts:
            details.append("Time: " + ", ".join(time_parts))
        details.append(
            "Heatmap: "
            f"low {int(fields.get('low_tris', 0) or 0)}, "
            f"medium {int(fields.get('medium_tris', 0) or 0)}, "
            f"high {int(fields.get('high_tris', 0) or 0)}, "
            f"misses {int(fields.get('miss_segments', 0) or 0)}"
        )
        heatmap_image = str(fields.get("heatmap_image", "") or "").strip()
        if heatmap_image:
            details.append(f"Image: {heatmap_image}")
    elif event == "request":
        title = "Overlay refresh queued"
        if scope_label:
            details.append(f"Target: {scope_label}")
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        delay_seconds = fields.get("delay_seconds", None)
        if delay_seconds is not None:
            details.append(f"Delay: {float(delay_seconds):.2f}s")
    elif event == "request-skip":
        title = "Overlay refresh skipped"
        if scope_label:
            details.append(f"Target: {scope_label}")
        requested_reason = str(fields.get("requested_reason", "") or "").strip()
        skip_reason = str(fields.get("skip_reason", "") or "").strip()
        if requested_reason:
            details.append(f"Reason: {requested_reason}")
        if skip_reason:
            details.append(f"Skipped because: {skip_reason}")
    elif event == "invalidate-export":
        title = "Overlay export cache cleared"
        if scope_label:
            details.append(f"Target: {scope_label}")
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
    elif event == "invalidate-results":
        title = "Overlay result cache cleared"
        if scope_label:
            details.append(f"Target: {scope_label}")
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
    elif event == "cancel":
        title = "Overlay refresh cancelled"
        reason = str(fields.get("reason", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
    elif event == "launch-error":
        title = "Overlay refresh launch failed"
        reason = str(fields.get("reason", "") or "").strip()
        error = str(fields.get("error", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        if error:
            details.append(f"Error: {error}")
    elif event == "worker-error":
        title = "Debug worker failed"
        reason = str(fields.get("reason", "") or "").strip()
        error = str(fields.get("error", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        if error:
            details.append(f"Error: {error}")
    elif event == "result-error":
        title = "Overlay result handling failed"
        reason = str(fields.get("reason", "") or "").strip()
        error = str(fields.get("error", "") or "").strip()
        if reason:
            details.append(f"Reason: {reason}")
        if error:
            details.append(f"Error: {error}")
    elif event == "result-mismatch":
        title = "Ignored mismatched overlay result"
        expected_path = short_log_path_fn(fields.get("expected_path"), parts=3)
        output_path = short_log_path_fn(fields.get("output_path"), parts=3)
        if output_path:
            details.append(f"Output: {output_path}")
        if expected_path:
            details.append(f"Expected: {expected_path}")
    elif event == "worker-exit":
        title = "Debug worker exited early"
        returncode = fields.get("returncode", None)
        note = str(fields.get("note", "") or "").strip()
        if returncode is not None:
            details.append(f"Return code: {returncode}")
        if note:
            details.append(f"Note: {note}")
    else:
        if scope_label:
            details.append(f"Target: {scope_label}")
        for key, value in fields.items():
            if value is None:
                continue
            details.append(f"{key.replace('_', ' ').title()}: {format_debug_log_value(value)}")

    return "\n".join([f"[{live_log_time_text_fn()}] {title}", *[f"  {detail}" for detail in details if detail]]) + "\n\n"
