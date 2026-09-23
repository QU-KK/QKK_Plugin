"""
persistence.py
Handles saving and loading of Keymapper entries.

Storage:
  Addon Preferences StringProperty (keymapper_json_store).
  Blender saves this automatically to userpref.blend when preferences
  are marked dirty — we mark them dirty via context.preferences.is_dirty.
  Entries survive all file open/close/new/restart scenarios.
"""

import bpy
import json
import uuid

_entries: list[dict] = []
_folders: list[dict] = []


# ---------------------------------------------------------------------------
# Folder API
# ---------------------------------------------------------------------------

def get_folders() -> list[dict]:
    return _folders


def get_folder_by_id(folder_id: str) -> dict | None:
    for f in _folders:
        if f.get("folder_id") == folder_id:
            return f
    return None


def add_folder(label: str) -> dict:
    folder = {
        "folder_id":  str(uuid.uuid4()),
        "label":      label,
        "collapsed":  False,
        "sort_index": len(_folders),
    }
    _folders.append(folder)
    _rebuild_folder_sort_indices()
    _write_to_prefs()
    return folder


def update_folder(folder_id: str, data: dict):
    for f in _folders:
        if f.get("folder_id") == folder_id:
            f.update(data)
            _write_to_prefs()
            return


def delete_folder(folder_id: str, delete_entries: bool = False):
    global _folders, _entries
    _folders = [f for f in _folders if f.get("folder_id") != folder_id]
    if delete_entries:
        _entries = [e for e in _entries if e.get("folder_id", "") != folder_id]
    else:
        for e in _entries:
            if e.get("folder_id", "") == folder_id:
                e["folder_id"] = ""
    _rebuild_folder_sort_indices()
    _rebuild_sort_indices()
    _write_to_prefs()


def move_folder(folder_id: str, direction: int):
    idx = next((i for i, f in enumerate(_folders) if f.get("folder_id") == folder_id), -1)
    if idx < 0:
        return
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(_folders):
        return
    _folders[idx], _folders[new_idx] = _folders[new_idx], _folders[idx]
    _rebuild_folder_sort_indices()
    _write_to_prefs()


def set_entry_folder(entry_id: str, folder_id: str):
    for e in _entries:
        if e.get("entry_id") == entry_id:
            e["folder_id"] = folder_id
            _write_to_prefs()
            return


def _rebuild_folder_sort_indices():
    for i, f in enumerate(_folders):
        f["sort_index"] = i


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_entries() -> list[dict]:
    return _entries


def add_entry(entry_dict: dict) -> dict:
    if not entry_dict.get("entry_id"):
        entry_dict["entry_id"] = str(uuid.uuid4())
    entry_dict.setdefault("sort_index", len(_entries))
    _entries.append(entry_dict)
    _rebuild_sort_indices()
    _write_to_prefs()
    return entry_dict


def insert_entry_at(entry_dict: dict, index: int) -> dict:
    """Insert an entry at a specific position in the list."""
    if not entry_dict.get("entry_id"):
        entry_dict["entry_id"] = str(uuid.uuid4())
    insert_pos = max(0, min(index, len(_entries)))
    _entries.insert(insert_pos, entry_dict)
    _rebuild_sort_indices()
    _write_to_prefs()
    return entry_dict


def remove_entry(entry_id: str) -> bool:
    global _entries
    before = len(_entries)
    _entries = [e for e in _entries if e.get("entry_id") != entry_id]
    if len(_entries) < before:
        _rebuild_sort_indices()
        _write_to_prefs()
        return True
    return False


def update_entry(entry_id: str, data: dict):
    for e in _entries:
        if e.get("entry_id") == entry_id:
            e.update(data)
            _write_to_prefs()
            return


def move_entry(entry_id: str, direction: int):
    idx = _find_index(entry_id)
    if idx < 0:
        return
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(_entries):
        return
    _entries[idx], _entries[new_idx] = _entries[new_idx], _entries[idx]
    _rebuild_sort_indices()
    _write_to_prefs()


def get_entry_by_id(entry_id: str) -> dict | None:
    for e in _entries:
        if e.get("entry_id") == entry_id:
            return e
    return None


def get_entry_at_index(index: int) -> dict | None:
    if 0 <= index < len(_entries):
        return _entries[index]
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_index(entry_id: str) -> int:
    for i, e in enumerate(_entries):
        if e.get("entry_id") == entry_id:
            return i
    return -1


def _rebuild_sort_indices():
    for i, e in enumerate(_entries):
        e["sort_index"] = i


def _entries_to_json() -> str:
    return json.dumps(_entries, indent=2, ensure_ascii=False)


def _folders_to_json() -> str:
    return json.dumps(_folders, indent=2, ensure_ascii=False)


def _entries_from_json(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[Keymapper] JSON parse error: {e}")
    return []


# ---------------------------------------------------------------------------
# Core save / load — uses addon preferences as the store
# ---------------------------------------------------------------------------

def _get_prefs():
    """Safely retrieve addon preferences object."""
    try:
        addon = bpy.context.preferences.addons.get(__package__)
        if addon and hasattr(addon, "preferences"):
            return addon.preferences
    except Exception:
        pass
    return None


def _write_to_prefs():
    """
    Write current in-memory data to working StringProperty.
    Does NOT mark preferences dirty — these are just the in-session working copies.
    """
    prefs = _get_prefs()
    if prefs is None:
        return
    prefs.keymapper_json_store    = _entries_to_json()
    prefs.keymapper_folders_store = _folders_to_json()


def save():
    """
    Explicitly save: write to the SAVED stores and mark dirty.
    Only called when user presses Save.
    """
    prefs = _get_prefs()
    if prefs is None:
        print("[Keymapper] save(): prefs not ready.")
        return

    entries_json = _entries_to_json()
    folders_json = _folders_to_json()

    # Write to both working and saved stores
    prefs.keymapper_json_store         = entries_json
    prefs.keymapper_folders_store      = folders_json
    prefs.keymapper_saved_json_store    = entries_json
    prefs.keymapper_saved_folders_store = folders_json

    # Persist which KMIs we created, so the next launch can distinguish our own
    # bindings from the user's identical ones (adoption self-exclusion).
    try:
        from . import keymap_manager
        keymap_manager.save_owned_kmi_registry()
    except Exception as e:
        print(f"[Keymapper] owned-KMI registry save skipped: {e}")

    try:
        bpy.context.preferences.is_dirty = True
    except Exception:
        pass

    print(f"[Keymapper] Saved {len(_entries)} entries to addon preferences.")

    print(f"[Keymapper] Saved {len(_entries)} entries to addon preferences.")


def _migrate_entry(entry: dict) -> dict:
    """
    Migrate older entry formats to current schema.
    """
    # Add custom_label if missing
    if "custom_label" not in entry:
        entry["custom_label"] = ""
    # Remove is_friendly — replaced by global toggle
    entry.pop("is_friendly", None)

    # Migrate renamed bundled operator ids (v0.9.103). The bundled operators
    # were briefly registered under built-in prefixes before being moved into
    # the keymapper.op_* namespace. Rewrite any saved references so existing
    # entries/JSON keep working.
    _BUNDLED_OP_RENAMES = {
        "wm.window_new_assetbrowser": "keymapper.op_open_assetbrowser_window",
        "view3d.pivot_transform":     "keymapper.op_pivot_transform",
    }
    for _old, _new in _BUNDLED_OP_RENAMES.items():
        oids = entry.get("operator_ids", "")
        if _old in oids:
            entry["operator_ids"] = oids.replace(_old, _new)
        if entry.get("display_name", "") == _old:
            entry["display_name"] = _new

    # Migrate keymap context names Blender has renamed. Saved entries keep the
    # spelling that was current when they were made; if the name no longer
    # resolves to a real keymap the entry silently stops registering. Mirrors
    # Blender's own rename table in bl_keymap_utils/versioning.py.
    _KEYMAP_CONTEXT_RENAMES = {
        "Grease Pencil Paint Mode": "Grease Pencil Draw Mode",   # 5.1
        "SequencerCommon":          "Video Sequence Editor",     # 4.5
        "SequencerPreview":         "Preview",                   # 4.5
        "Sequencer Preview":        "Preview",                   # never a real name
        "NLA Channels":             "NLA Tracks",                # 4.1
    }
    for _fld in ("operator_ids", "keymap_contexts"):
        _val = entry.get(_fld, "")
        if isinstance(_val, str) and _val:
            for _old, _new in _KEYMAP_CONTEXT_RENAMES.items():
                if f'"{_old}"' in _val:
                    _val = _val.replace(f'"{_old}"', f'"{_new}"')
            entry[_fld] = _val
    for _fld in ("context",):
        if entry.get(_fld) in _KEYMAP_CONTEXT_RENAMES:
            entry[_fld] = _KEYMAP_CONTEXT_RENAMES[entry[_fld]]
    _ctxs = entry.get("contexts")
    if isinstance(_ctxs, list):
        entry["contexts"] = [_KEYMAP_CONTEXT_RENAMES.get(c, c) for c in _ctxs]

    # Migrate old shortcut_conflicts → shortcut_conflicts_internal
    if "shortcut_conflicts" in entry and "shortcut_conflicts_internal" not in entry:
        entry["shortcut_conflicts_internal"] = entry.pop("shortcut_conflicts")
    if "keybind_conflicts" in entry and "keybind_conflicts_internal" not in entry:
        entry["keybind_conflicts_internal"] = entry.pop("keybind_conflicts")

    # Add new external conflict fields if missing
    entry.setdefault("shortcut_conflicts_internal", [])
    entry.setdefault("keybind_conflicts_internal",  [])
    entry.setdefault("shortcut_conflicts_external", [])
    entry.setdefault("keybind_conflicts_external",  [])
    entry.setdefault("extra_keybinds", [])
    entry.setdefault("any", False)
    # Ops referenced by the entry that were not registered at the last
    # re-scan/import (addon disabled, or op removed in this Blender version).
    entry.setdefault("unregistered_ops", [])
    # Entry Buttons (see buttons.py). use_keybind False = button-only entry:
    # no KMIs are created and conflict scans are gated by
    # button_conflict_detection (shortcut conflicts only, informational).
    entry.setdefault("use_keybind", True)
    entry.setdefault("use_button", False)
    entry.setdefault("button_locations", [])
    entry.setdefault("button_show_label", True)
    entry.setdefault("button_show_icon", True)
    entry.setdefault("button_visible", True)
    entry.setdefault("button_conflict_detection", False)
    entry.setdefault("button_label", "")

    # Preset provenance — empty for user-created entries; populated by
    # KEYMAPPER_OT_ApplyPreset when the entry came from a built-in preset.
    entry.setdefault("source_preset_id",       "")
    entry.setdefault("source_preset_category", "")

    # Conflict-cache signatures — empty for older entries; populated by
    # conflict_detector.update_entry_external_conflicts() after each scan.
    # When both match current state, the scan is skipped.
    entry.setdefault("_conflict_signature",    "")
    entry.setdefault("_ks_signature_at_scan",  "")

    return entry


def load():
    """
    Read entries from addon preferences.
    Safe to call at any point — returns empty list if prefs not ready yet.
    """
    global _entries
    prefs = _get_prefs()
    if prefs is None:
        print("[Keymapper] load(): prefs not ready, entries cleared.")
        _entries = []
        return

    # Load from saved stores (only written on explicit Save).
    # If saved store is empty string it means never saved — use empty list.
    # Only fall back to working store if saved store property doesn't exist at all.
    saved_raw = getattr(prefs, "keymapper_saved_json_store", None)
    if saved_raw is None:
        # Property doesn't exist yet (old install) — fall back to working store
        raw = getattr(prefs, "keymapper_json_store", "")
    else:
        raw = saved_raw
    loaded = _entries_from_json(raw)
    # Migrate entries to current schema
    _entries = [_migrate_entry(e) for e in loaded]
    _rebuild_sort_indices()

    # Load folders
    global _folders
    saved_folders_raw = getattr(prefs, "keymapper_saved_folders_store", None)
    if saved_folders_raw is None:
        folders_raw = getattr(prefs, "keymapper_folders_store", "")
    else:
        folders_raw = saved_folders_raw
    if folders_raw and folders_raw.strip():
        try:
            loaded_folders = json.loads(folders_raw)
            if isinstance(loaded_folders, list):
                _folders = loaded_folders
        except Exception as e:
            print(f"[Keymapper] Folders parse error: {e}")
            _folders = []
    else:
        _folders = []
    _rebuild_folder_sort_indices()
    print(f"[Keymapper] Loaded {len(_entries)} entries, {len(_folders)} folders.")


def _deferred_load():
    """
    Called via bpy.app.timers after Blender finishes startup,
    ensuring preferences are fully available before we read them.
    """
    load()
    return None  # returning None cancels the timer (runs once only)


# ---------------------------------------------------------------------------
# JSON File export / import operators
# ---------------------------------------------------------------------------

# NOTE: the Export/Import JSON operators live in operators.py. Older
# duplicates here registered the same bl_idnames first and were then
# replaced at every enable ("has been registered before" console noise);
# removed — operators.py owns keymapper.export_json / import_json.


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

_classes = ()


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    # Defer load so prefs are guaranteed to be initialised
    bpy.app.timers.register(_deferred_load, first_interval=0.1, persistent=True)
    print("[Keymapper] Persistence registered.")


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    if bpy.app.timers.is_registered(_deferred_load):
        bpy.app.timers.unregister(_deferred_load)
    print("[Keymapper] Persistence unregistered.")
