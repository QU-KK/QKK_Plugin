"""Update-checker state that has to outlive both the session and a reinstall.

Two facts must survive a Blender restart or the update popup becomes a loop the
user cannot break:

* "I do not want this version" - without it, ``_last_notified_version`` resets on
  every launch and the same popup returns forever.
* "the automatic install of version X did not take" - without it the add-on
  re-offers the identical auto-install that already failed, instead of pointing
  at the manual route.

Add-on preferences look like the natural home, but the install path rewrites the
extension package while the preference block is live, and a failed install is
exactly the moment we least want to trust that block. A small JSON file in the
user's config directory is written before any of that happens and is read back
by whichever build loads next.

Every accessor is failure-tolerant on purpose: an unreadable or corrupt state
file must degrade to "no skip recorded", never to an exception inside a timer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Config subdirectory shared with the user's export templates.
STATE_DIR_NAME = "fyr_baker"
STATE_FILENAME = "update_state.json"

KEY_SKIPPED_VERSION = "skipped_version"
KEY_FAILED_VERSION = "failed_install_version"
KEY_FAILED_REASON = "failed_install_reason"
KEY_FAILED_ARCHIVE = "failed_install_archive"


def state_path(create: bool = False) -> Path | None:
    """Absolute path of the state file, or None when Blender has no config dir."""
    try:
        import bpy

        base = bpy.utils.user_resource("CONFIG", path=STATE_DIR_NAME, create=create)
    except Exception:
        return None
    if not base:
        return None
    return Path(base) / STATE_FILENAME


def read_state(path: Path | None = None) -> dict:
    if path is None:
        path = state_path(create=False)
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_state(state: dict, path: Path | None = None) -> bool:
    if path is None:
        path = state_path(create=True)
    if path is None:
        return False
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Staged then replaced, never truncated in place. This file is written at
        # the moment the add-on is least stable -- right before an install rewrites
        # the extension package -- and a torn write reads back as "{}", losing the
        # "I do not want this version" record and bringing back forever the popup
        # the user just dismissed. The temp carries the pid so a second Blender
        # writing its own state cannot land in the middle of ours.
        temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            temp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(temp, path)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
        return True
    except Exception:
        return False


def _update_state(path: Path | None, **changes) -> bool:
    state = read_state(path)
    for key, value in changes.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    return write_state(state, path)


def skipped_version(path: Path | None = None) -> str:
    return str(read_state(path).get(KEY_SKIPPED_VERSION) or "")


def set_skipped_version(version: str, path: Path | None = None) -> bool:
    return _update_state(path, **{KEY_SKIPPED_VERSION: str(version or "") or None})


def clear_skipped_version(path: Path | None = None) -> bool:
    return _update_state(path, **{KEY_SKIPPED_VERSION: None})


def is_version_skipped(version: str, path: Path | None = None) -> bool:
    version = str(version or "")
    return bool(version) and skipped_version(path) == version


def record_install_failure(
    version: str,
    reason: str,
    archive_path: str = "",
    path: Path | None = None,
) -> bool:
    return _update_state(
        path,
        **{
            KEY_FAILED_VERSION: str(version or "") or None,
            KEY_FAILED_REASON: str(reason or "") or None,
            KEY_FAILED_ARCHIVE: str(archive_path or "") or None,
        },
    )


def clear_install_failure(path: Path | None = None) -> bool:
    return _update_state(
        path,
        **{KEY_FAILED_VERSION: None, KEY_FAILED_REASON: None, KEY_FAILED_ARCHIVE: None},
    )


def install_failure(path: Path | None = None) -> dict:
    """The recorded failure as ``{version, reason, archive}``; empty when clean."""
    state = read_state(path)
    version = str(state.get(KEY_FAILED_VERSION) or "")
    if not version:
        return {}
    return {
        "version": version,
        "reason": str(state.get(KEY_FAILED_REASON) or ""),
        "archive": str(state.get(KEY_FAILED_ARCHIVE) or ""),
    }


def install_failed_for(version: str, path: Path | None = None) -> bool:
    version = str(version or "")
    return bool(version) and install_failure(path).get("version") == version
