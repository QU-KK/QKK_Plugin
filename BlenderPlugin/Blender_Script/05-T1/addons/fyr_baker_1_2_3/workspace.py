from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from . import naming


def slugify_name(value: str) -> str:
    return naming.sanitize_token(value)


def build_job_id(project_name: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{slugify_name(project_name)}_{timestamp}_{suffix}"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_job_workspace(output_root: str | Path, job_id: str) -> Path:
    return Path(output_root) / ".fyr_baker" / "jobs" / job_id


def build_project_output_dir(output_root: str | Path, project_name: str, blend_file_name: str | None = None) -> Path:
    if blend_file_name:
        return Path(output_root) / f"{slugify_name(blend_file_name)}_{slugify_name(project_name)}"
    return Path(output_root) / slugify_name(project_name)
