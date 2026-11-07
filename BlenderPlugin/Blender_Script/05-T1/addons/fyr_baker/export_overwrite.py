"""Transient consent for replacing the existing files in one export plan."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat


def replacement_snapshot(paths, *, scope: str) -> str:
    """Describe existing destinations without reading image data or writing files.

    Approval covers the plan and the files as shown, not future replacements at
    those names. Stat metadata makes edits, file replacement and new destinations
    invalidate an open confirmation. Missing destinations need no consent;
    inspection errors and non-file destinations must fail before export starts.
    """
    by_destination = {os.path.normcase(path): path for path in map(os.path.abspath, paths)}
    destinations = [by_destination[key] for key in sorted(by_destination)]
    files = []
    for path in destinations:
        try:
            info = os.stat(path)
        except FileNotFoundError:
            if os.path.lexists(path):
                raise OSError(f"Export destination is a broken link: {path}")
            continue
        if not stat.S_ISREG(info.st_mode):
            raise OSError(f"Export destination is not a file: {path}")
        files.append({
            "path": path,
            "target": os.path.normcase(os.path.realpath(path)),
            "identity": [info.st_dev, info.st_ino],
            "size": info.st_size,
            "modified": info.st_mtime_ns,
            "changed": info.st_ctime_ns,
        })
    if not files:
        return ""
    return json.dumps({"scope": scope, "destinations": destinations, "files": files}, sort_keys=True)


def replacement_paths(snapshot: str) -> list[Path]:
    return [Path(entry["path"]) for entry in json.loads(snapshot)["files"]] if snapshot else []
