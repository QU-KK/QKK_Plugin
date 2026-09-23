# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Jarand Folkestad Wicklund (JFW)
"""Detect whether a newer Keymapper is available from its extension repo.

Blender caches each remote repository's listing at
``<repo.directory>/.blender_ext/index.json`` after a sync. We locate the repo
this add-on was installed from, look up our own id in that index, and compare
its version against ours.

Deliberately defensive: the index format is Blender's internal business and can
change between versions, so anything unexpected simply means "no banner". The
result is cached and only re-read when the file's mtime changes (and at most
once every few seconds), because this is consulted from panel draw code.

Blender only refreshes that file when the repository is synced — with "Check
for Updates on Startup" off, the banner can lag until the user checks manually.
"""

import json
import os
import time

import bpy

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CHECK_INTERVAL = 5.0        # seconds between filesystem stats
_state = {
    "checked_at": 0.0,
    "mtime": None,
    "path": None,
    "available": False,
    "latest": "",
    "current": "",
}


def _version_tuple(value) -> tuple:
    """"1.10.2" / (1, 10, 2) -> (1, 10, 2). Junk -> ()."""
    if isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        parts = str(value or "").strip().lstrip("v").split(".")
    out = []
    for p in parts:
        s = str(p).strip()
        num = ""
        for ch in s:
            if ch.isdigit():
                num += ch
            else:
                break
        if num == "":
            break
        out.append(int(num))
    return tuple(out)


def _own_ids() -> tuple:
    """(repo_module, extension_id) for this add-on, or ("", "")."""
    pkg = __package__ or ""
    parts = pkg.split(".")
    if len(parts) >= 3 and parts[0] == "bl_ext":
        return parts[1], parts[-1]
    # Legacy add-on install (not an extension): no repo to check.
    return "", parts[-1] if parts else ""


def _current_version() -> str:
    """Our installed version, preferring blender_manifest.toml.

    The manifest is what the extension system publishes and compares against,
    so reading it directly means the banner can't be thrown off by the
    hand-maintained KEYMAPPER_VERSION drifting out of sync. Falls back to that
    constant for legacy (non-extension) installs with no manifest.
    """
    path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            import tomllib
            data = tomllib.loads(raw.decode("utf-8"))
            ver = str(data.get("version", "") or "")
            if ver:
                return ver.lstrip("v")
        except Exception:
            pass
        # Manifest present but tomllib unavailable/unhappy: pull the top-level
        # `version = "..."` line without a parser.
        import re
        for line in raw.decode("utf-8", "ignore").splitlines():
            m = re.match(r'\s*version\s*=\s*"([^"]+)"', line)
            if m and not line.strip().startswith("schema_version"):
                return m.group(1).lstrip("v")
    except Exception:
        pass
    try:
        from .preferences import KEYMAPPER_VERSION
        return str(KEYMAPPER_VERSION).lstrip("v")
    except Exception:
        return ""


def _index_path(repo_module: str) -> str:
    try:
        for repo in bpy.context.preferences.extensions.repos:
            if repo.module != repo_module:
                continue
            directory = repo.directory
            if not directory:
                return ""
            return os.path.join(directory, ".blender_ext", "index.json")
    except Exception:
        pass
    return ""


def _find_entry(data, ext_id: str):
    """Locate our extension's record anywhere in the index structure."""
    if isinstance(data, dict):
        if data.get("id") == ext_id and "version" in data:
            return data
        for value in data.values():
            found = _find_entry(value, ext_id)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_entry(value, ext_id)
            if found is not None:
                return found
    return None


def _refresh(force: bool = False) -> None:
    now = time.time()
    if not force and (now - _state["checked_at"]) < _CHECK_INTERVAL:
        return
    _state["checked_at"] = now

    repo_module, ext_id = _own_ids()
    current = _current_version()
    _state["current"] = current
    if not repo_module or not ext_id or not current:
        _state.update(available=False, latest="")
        return

    path = _index_path(repo_module)
    if not path or not os.path.isfile(path):
        _state.update(available=False, latest="", path="", mtime=None)
        return

    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    if (not force and path == _state["path"] and mtime == _state["mtime"]):
        return  # unchanged since the last read
    _state["path"] = path
    _state["mtime"] = mtime

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        _state.update(available=False, latest="")
        return

    entry = _find_entry(data, ext_id)
    latest = str((entry or {}).get("version", "") or "")
    cur_t = _version_tuple(current)
    new_t = _version_tuple(latest)
    _state["latest"] = latest
    _state["available"] = bool(cur_t and new_t and new_t > cur_t)


def get_update_status(force: bool = False) -> dict:
    """{"available": bool, "latest": str, "current": str} — never raises."""
    try:
        _refresh(force=force)
    except Exception:
        pass
    return {
        "available": bool(_state["available"]),
        "latest": _state["latest"],
        "current": _state["current"],
    }


def update_available() -> bool:
    return get_update_status()["available"]
