"""Settings that must outlive an update, a reinstall, or a disable/enable cycle.

Add-on preferences are the natural home for these and they are NOT a reliable
one. The values live in Blender's own storage keyed by the add-on package, and
an extension update rewrites that package while the preference block is live.
``updater_state`` already exists for exactly this reason; this module is the same
idea for the settings a returning user notices immediately when they are lost:

* ``backend_prewarm_first_run_acknowledged`` - lose it and the first-run dialog
  returns after every update, asking a question the user already answered.
* the prewarm mode and update-check mode they chose in that dialog.
* ``backend_executable`` - the manual backend path. Losing it strands anyone who
  keeps their backend somewhere non-standard, and the add-on then reports "no
  backend" and quietly falls back to Cycles.

The file lives in the user's CONFIG directory, NOT inside the add-on package, so
nothing that replaces the package can touch it.

Deliberately independent of ``updater_state``: the Superhive build ships without
that module, and these settings matter there too. Every function here is
failure-tolerant. A missing, unreadable or corrupt file means "nothing saved",
never an exception during registration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Config subdirectory shared with updater_state and the user's export templates.
STATE_DIR_NAME = "fyr_baker"
STATE_FILENAME = "persistent_settings.json"

#: Preference names mirrored to disk. Keep this SMALL and deliberate: every key
#: here is one the add-on will happily overwrite from the file at registration,
#: so a key that Blender manages better than we do does not belong.
MIRRORED_KEYS = (
    "backend_prewarm_first_run_acknowledged",
    "backend_prewarm_mode",
    "backend_prewarm_prepare_meshes",
    "update_check_mode",
    "backend_executable",
    "default_collection_mode",
    # The Bake GPU choice: an update that resets it would quietly move bakes to another card.
    "gpu_adapter",
)

#: True while restore_into_preferences is assigning, so the property update
#: callbacks it triggers do not write the file back mid-restore.
_restoring = False


def state_path(create: bool = False) -> Path | None:
    """Absolute path of the settings file, or None when there is no config dir."""
    try:
        import bpy

        base = bpy.utils.user_resource("CONFIG", path=STATE_DIR_NAME, create=create)
    except Exception:
        return None
    if not base:
        return None
    return Path(base) / STATE_FILENAME


def read_settings(path: Path | None = None) -> dict:
    if path is None:
        path = state_path(create=False)
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_settings(values: dict, path: Path | None = None) -> bool:
    """Replace the settings file. False when it could not be written."""
    if path is None:
        path = state_path(create=True)
    if path is None:
        return False
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written whole through a temporary file: a half-written settings file
        # read back by the next launch would look like corrupt JSON and silently
        # discard every mirrored setting.
        #
        # The temp name carries this process's pid. The config directory is shared by
        # every Blender session on the machine and a mirrored preference is written on
        # EVERY change, so a fixed ".tmp" name let two sessions truncate each other's
        # in-flight file and made replace() fail with a sharing violation on Windows --
        # the same class as the progress.json tmp race. write_settings swallows that
        # and returns False, so the loss was silent: the next launch lost the manual
        # backend path and re-asked the first-run question.
        temporary = target.with_suffix(f"{target.suffix}.{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(values, indent=2, sort_keys=True), encoding="utf-8")
            temporary.replace(target)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        return True
    except Exception:
        return False


def snapshot_preferences(prefs) -> dict:
    """Read the mirrored keys off a preferences block."""
    values: dict = {}
    if prefs is None:
        return values
    for key in MIRRORED_KEYS:
        try:
            value = getattr(prefs, key)
        except Exception:
            continue
        if isinstance(value, (bool, int, float, str)):
            values[key] = value
    return values


def save_from_preferences(prefs) -> bool:
    """Mirror the current preference values to disk.

    Called from the property update callbacks and after the first-run dialog, so
    the file is never staler than the preferences it shadows.
    """
    if _restoring or prefs is None:
        return False
    values = snapshot_preferences(prefs)
    if not values:
        return False
    return write_settings(values)


def restore_into_preferences(prefs) -> list[str]:
    """Apply saved values onto a freshly registered preferences block.

    Returns the keys actually restored. The file wins over whatever the block
    holds: it is written on every change, so it is never behind, and after an
    update the block is exactly what we cannot trust.

    Each assignment is guarded individually. A value can be legitimately
    unsettable on the build now running - a Superhive archive ships no updater,
    so its ``update_check_mode`` enum offers only NEVER and a stored MANUAL will
    not assign - and that must skip the key rather than abandon the rest.
    """
    global _restoring
    if prefs is None:
        return []
    values = read_settings()
    if not values:
        return []

    restored: list[str] = []
    _restoring = True
    try:
        for key in MIRRORED_KEYS:
            if key not in values:
                continue
            saved = values[key]
            try:
                current = getattr(prefs, key)
            except Exception:
                continue
            if current == saved:
                continue
            try:
                setattr(prefs, key, saved)
            except Exception:
                continue
            restored.append(key)
    finally:
        _restoring = False
    return restored
