"""On-disk record of the Live Reproject reference.

The reference (the output textures plus the UV layout they were made for) used
to live only in process memory: the pixel stores were written to disk, but
nothing could read them back, so Restore Textures died with the Blender session
and the next toggle-on overwrote the stores with already-reprojected pixels.
This module is the pure, bpy-free part of the persistent version: a small JSON
manifest beside the stores that names every file and records the signature of
each output file the reference corresponds to.

Signature semantics: an output's signature is the (mtime_ns, size) of the file
on disk the last time the reference and the file agreed, that is at capture and
after each commit or restore we wrote ourselves. While the file still carries
that signature, its content is either the original or our own transfer of it,
so the stored reference remains the true source and must not be recaptured.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MANIFEST_VERSION = 1
MANIFEST_NAME = "reference.json"


def file_signature(path: str | os.PathLike[str]) -> tuple[int, int] | None:
    """(mtime_ns, size) of a file, or None when it cannot be read."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return int(info.st_mtime_ns), int(info.st_size)


def manifest_path(folder: str | os.PathLike[str]) -> Path:
    return Path(folder) / MANIFEST_NAME


def write_manifest(folder: str | os.PathLike[str], payload: dict) -> Path:
    """Atomic: a crash mid-write leaves the previous manifest, never a torn one."""
    target = manifest_path(folder)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique per writer. A fixed "reference.json.tmp" is a shared name: two
    # Blender sessions (or a second one opened on the same project) pointed at
    # this folder interleave their writes into the one file and then race on the
    # replace, so one manifest ends up describing the other's stores -- and the
    # loser's os.replace raises because its temp is already gone. The same shared
    # name is what made progress.json fail with "Failed to replace".
    temp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    data = dict(payload)
    data["version"] = MANIFEST_VERSION
    try:
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
        os.replace(temp, target)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return target


def read_manifest(folder: str | os.PathLike[str]) -> dict | None:
    """The manifest as a dict, or None when absent, unreadable or of another version."""
    try:
        with open(manifest_path(folder), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return None
    if not isinstance(data.get("outputs"), list) or not isinstance(data.get("layouts"), dict):
        return None
    return data


def _normalize(path: str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def missing_files(payload: dict) -> list[str]:
    """Store and layout files the manifest names that are no longer on disk."""
    missing: list[str] = []
    for output in payload.get("outputs", ()):
        store = str(output.get("store_path", "") or "")
        if not store or not os.path.isfile(store):
            missing.append(store or "<store>")
    for name, layout in payload.get("layouts", {}).items():
        for key in ("uvs", "triangles"):
            file_path = str(layout.get(key, "") or "")
            if not file_path or not os.path.isfile(file_path):
                missing.append(file_path or f"<{name} {key}>")
    return missing


def reuse_verdict(payload: dict, tracked_paths, *, signature_fn=file_signature, require_files: bool = True) -> tuple[bool, str]:
    """Whether the stored reference still describes the files on disk.

    ``tracked_paths`` are the project's current output files. Every one must be
    in the manifest with its recorded signature still matching the file, and
    every store/layout file must exist (``require_files=False`` skips that for a
    reference still held in memory). A tracked output the manifest never saw
    (a new map baked since) or a rewritten file (a rebake, paint, or import)
    means the disk holds newer truth and the caller should capture afresh.
    """
    if not isinstance(payload, dict):
        return False, "no stored reference"
    by_path = {}
    for output in payload.get("outputs", ()):
        path = str(output.get("path", "") or "")
        if path:
            by_path[_normalize(path)] = output
    if not by_path:
        return False, "stored reference names no textures"
    tracked = [str(p) for p in tracked_paths if p]
    if not tracked:
        return False, "no tracked outputs"
    for path in tracked:
        output = by_path.get(_normalize(path))
        if output is None:
            return False, f"{Path(path).name} was not in the stored reference"
        recorded = output.get("signature")
        current = signature_fn(path)
        if current is None:
            return False, f"{Path(path).name} is missing on disk"
        if recorded is None or tuple(recorded) != tuple(current):
            return False, f"{Path(path).name} changed on disk since the reference was recorded"
    missing = missing_files(payload) if require_files else []
    if missing:
        return False, f"stored reference is incomplete ({len(missing)} files missing)"
    return True, ""
