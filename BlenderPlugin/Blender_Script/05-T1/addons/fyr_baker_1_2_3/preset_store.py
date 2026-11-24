from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import constants, properties

try:  # pragma: no cover - exercised only inside Blender
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - exercised by the unit tests
    bpy = None


PRESET_SCHEMA = "master_baker.project_preset.v1"

# Two tiers, the same discipline export_templates.py uses:
#
# * an optional read-only tier shipped beside the addon, for a studio that wants
#   to hand its artists a starting project;
# * the user's own presets under ``extension_path_user``, which is where every
#   save goes and which survives an addon update.
#
# PRESET_DIR used to be the ONLY tier and pointed at
# ``Path(__file__).parents[1] / "presets" / "project_presets"``. Packaging copies
# the contents of ``addon/`` to the root of the zip, so in an installed extension
# ``parents[1]`` is the extensions *repository* directory -- outside the addon
# entirely, next to every other installed extension. Saves landed there.
BUILTIN_PRESET_DIR = Path(__file__).resolve().parents[1] / "presets" / "project_presets"
BUILTIN_PRESET_DIR_PACKAGED = Path(__file__).resolve().parent / "presets" / "project_presets"
USER_PRESET_SUBDIR = "project_presets"

_NON_TOKEN = re.compile(r"[^A-Za-z0-9_.-]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


def sanitize_preset_name(value: str) -> str:
    cleaned = _NON_TOKEN.sub("_", (value or "").strip())
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned).strip("._-")
    return cleaned or "BakeProject"


def user_preset_dir(create: bool = False) -> Path | None:
    """Where this user's project presets live, or ``None`` outside Blender.

    Monkeypatch this in tests. Mirrors ``export_templates.user_template_dir``,
    including its fallback: ``extension_path_user`` raises for a dev install
    loaded as a legacy add-on, and a save must not fail because of that.
    """
    if bpy is None:
        return None
    try:
        path = bpy.utils.extension_path_user(__package__, path=USER_PRESET_SUBDIR, create=create)
        if path:
            return Path(path)
    except Exception:
        pass
    try:
        base = bpy.utils.user_resource("CONFIG", path=f"fyr_baker/{USER_PRESET_SUBDIR}", create=create)
    except Exception:
        return None
    return Path(base) if base else None


def builtin_preset_dir() -> Path:
    """Where shipped project presets live. Packaged copy wins when it exists."""
    if BUILTIN_PRESET_DIR_PACKAGED.is_dir():
        return BUILTIN_PRESET_DIR_PACKAGED
    return BUILTIN_PRESET_DIR


def preset_path_for_name(preset_name: str) -> Path:
    """The file a preset name resolves to, user tier first.

    Reads find a shipped preset when the user has none by that name; a save
    always targets the user tier, so a shipped preset is never overwritten.
    """
    filename = f"{sanitize_preset_name(preset_name)}.json"
    user_dir = user_preset_dir()
    if user_dir is not None and (user_dir / filename).is_file():
        return user_dir / filename
    builtin = builtin_preset_dir() / filename
    if builtin.is_file():
        return builtin
    return (user_dir or builtin_preset_dir()) / filename


def ensure_preset_dir() -> Path:
    """Create and return the directory a save writes into."""
    user_dir = user_preset_dir(create=True)
    if user_dir is not None:
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    target = builtin_preset_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def list_preset_paths() -> list[Path]:
    """Every readable preset, user tier shadowing a shipped one of the same name."""
    by_stem: dict[str, Path] = {}
    for directory in (builtin_preset_dir(), user_preset_dir()):
        if directory is None or not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            by_stem[path.stem] = path
    return sorted(by_stem.values(), key=lambda path: path.stem.lower())


# Blender does not keep a reference to the strings an EnumProperty items callback
# returns: it stores each tuple's char* and reads them again on the next redraw. A
# list built fresh inside the callback is freed as soon as the callback returns, so
# the dropdown draws garbage. properties.py keeps _EXPORT_TEMPLATE_ENUM_ITEMS alive
# in a module global for exactly this reason (see also _PREVIEW_MAP_ITEMS_CACHE);
# this matches that pattern by rewriting one list IN PLACE and returning it.
#
# The same global doubles as a redraw-rate fix: the callback runs on every redraw of
# the dropdown and used to re-glob BOTH preset directories each time. The cache is
# versioned by the two directories' mtimes -- adding or removing a preset file
# updates its directory's mtime -- and save_project_preset invalidates it directly,
# which covers the one writer whose change could land inside a single mtime tick.
_PRESET_ENUM_ITEMS: list[tuple[str, str, str, int]] = []
_PRESET_ENUM_SIGNATURE: tuple | None = None


def _preset_dir_signature() -> tuple:
    """Cheap change stamp for the two preset directories (two stats, no glob)."""
    signature = []
    for directory in (builtin_preset_dir(), user_preset_dir()):
        if directory is None:
            signature.append((None, None))
            continue
        try:
            signature.append((str(directory), directory.stat().st_mtime_ns))
        except OSError:
            # Missing directory: a real state, and one that must invalidate as soon
            # as the directory appears.
            signature.append((str(directory), None))
    return tuple(signature)


def invalidate_preset_items_cache() -> None:
    global _PRESET_ENUM_SIGNATURE
    _PRESET_ENUM_SIGNATURE = None


def list_preset_items(self=None, context=None):
    global _PRESET_ENUM_SIGNATURE
    signature = _preset_dir_signature()
    if _PRESET_ENUM_ITEMS and signature == _PRESET_ENUM_SIGNATURE:
        return _PRESET_ENUM_ITEMS
    items = []
    for index, path in enumerate(list_preset_paths()):
        items.append((path.stem, path.stem, str(path), index))
    if not items:
        items.append(("__none__", "No presets found", "Save a preset first", 0))
    # In place: Blender may still be holding the previous list's char*.
    _PRESET_ENUM_ITEMS[:] = items
    _PRESET_ENUM_SIGNATURE = signature
    return _PRESET_ENUM_ITEMS


def _collection_items(collection):
    return list(collection or [])


def _clear_collection(collection):
    if hasattr(collection, "clear"):
        collection.clear()
        return
    while collection:
        collection.pop()


class _PresetCollection(list):
    def add(self):
        item = type("PresetItem", (), {})()
        self.append(item)
        return item

    def clear(self):
        del self[:]


def _ensure_collection(owner, attribute_name):
    collection = getattr(owner, attribute_name, None)
    if collection is None:
        collection = _PresetCollection()
        setattr(owner, attribute_name, collection)
    return collection


def _get_resolved_object(name: str, object_lookup=None):
    if not name:
        return None
    if object_lookup is None:
        return None
    return object_lookup(name)


def _images_datablock():
    """``bpy.data.images``, or ``None`` outside Blender.

    Image pointers cannot be serialized, so every image in a payload travels as a NAME
    and is resolved here on restore. Outside Blender there is nothing to resolve
    against, and callers must then leave the target pointer alone rather than clearing
    it -- the legacy adapters and the unit tests have no datablocks at all.
    """
    try:
        import bpy as _bpy

        return getattr(getattr(_bpy, "data", None), "images", None)
    except Exception:
        return None


def _group_metadata_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "metadata", None) or group
    return _properties.group_metadata_state(group)


def _group_role_assignments_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "role_assignments", None) or group
    return _properties.group_role_assignments_state(group)


def _group_projection_settings_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "projection_settings", None) or group
    return _properties.group_projection_settings_state(group)


def _group_paint_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "paint_projection_settings", None) or group
    getter = getattr(_properties, "group_paint_projection_settings_state", None)
    if getter is None:
        return getattr(group, "paint_projection_settings", None) or group
    return getter(group)


def _restore_texture_sets(project, payload) -> None:
    """Rebuild project.texture_sets from the payload, or derive them for legacy presets."""
    sets = getattr(project, "texture_sets", None)
    if sets is None or not hasattr(sets, "add") or not hasattr(sets, "clear"):
        return
    entries = payload.get("texture_sets")
    if entries is None:
        # Legacy preset: reconstruct from whatever set names the groups reference so the
        # loaded project is self-consistent instead of prompting for a migration.
        seen: list[str] = []
        for group_data in payload.get("groups", []) or []:
            name = str(group_data.get("texture_set_name", "") or "").strip()
            if name and name not in seen:
                seen.append(name)
        entries = [{"name": name, "name_mode": ""} for name in seen]
    try:
        sets.clear()
    except Exception:
        return
    for entry in entries:
        name = str((entry or {}).get("name", "") or "").strip()
        if not name:
            continue
        try:
            apply_payload_to_texture_set(sets.add(), entry)
        except Exception:
            continue


def _group_field(group, state, name, default):
    """Read a group field from its canonical home.

    ``group_*_settings_state()`` returns a nested PropertyGroup that
    ``properties._sync_group_*`` rewrites FROM the group on every access, so the group
    owns the value and the nested object is a read-through mirror. Prefer the group and
    fall back to the mirror only for the legacy adapters, where the group has no such
    attribute.
    """
    if hasattr(group, name):
        return getattr(group, name, default)
    return getattr(state, name, default) if state is not None else default


def _set_group_field(group, state, name, value) -> None:
    """Write to the group (canonical) and mirror it onto the nested state if present."""
    for target in (group, state):
        if target is None or not hasattr(target, name):
            continue
        try:
            setattr(target, name, value)
        except Exception:
            continue


def _apply_paint_payload_to_group(group, group_data) -> None:
    """Restore Paint Offset & Skew. Missing images resolve to None, as on a fresh group."""
    state = _group_paint_state(group)
    for key in ("paint_offset_scale", "paint_skew"):
        if key in group_data:
            try:
                _set_group_field(group, state, key, float(group_data.get(key, 0.0)))
            except Exception:
                pass
    images = _images_datablock()
    if images is None:
        return
    for key, attribute in (
        ("paint_offset_image_name", "paint_offset_image"),
        ("paint_skew_image_name", "paint_skew_image"),
    ):
        if key not in group_data:
            continue
        name = str(group_data.get(key, "") or "").strip()
        _set_group_field(group, state, attribute, images.get(name) if name else None)


# --- Generic property sweep --------------------------------------------------
#
# Map rows and project scalars used to be hand-written field lists. That list
# drifted twice in a single day (first ``image_format``, then
# ``material_channel`` + the whole lighting block + row uuids), and every drift
# silently dropped a user's setting on save/load. Serialization now ENUMERATES
# the RNA properties of whatever it is handed, so a new user-facing property in
# ``properties.py`` travels in presets with no change here. The denylists below
# name the fields that must NOT travel: runtime/status state, identity that the
# addon manages, and Blender's implicit ``name``.
#
# The known failure direction is now "a newly added runtime field gets saved"
# (harmless round-trip) rather than "a user setting is lost", which is why the
# denylists are explicit rather than an allowlist.

_SERIALIZABLE_PROPERTY_TYPES = frozenset({"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"})
# Only fixed-size float vectors are serializable; the only ones in the stack are
# the 3-component env-light colors.
_MAX_SERIALIZABLE_VECTOR_LENGTH = 4

_SKIP = object()

# Never saved and never applied, on either owner.
_COMMON_DENIED_NAMES = frozenset(
    {
        # Every PropertyGroup inherits an implicit ``name``; on map rows it is not
        # a user setting. The project's real ``name`` is handled explicitly.
        "name",
        "rna_type",
    }
)

_MAP_DENIED_NAMES = _COMMON_DENIED_NAMES | frozenset(
    {
        "is_add_phantom",  # transient "+" row in the stack UI
        # Procedural-capture provenance and binding status: recomputed from the
        # scene's materials, never restored from a preset.
        "material_origin",
        "material_binding_key",
        "material_resolve_state",
        "material_source_node_ids",
        "material_status_message",
        "material_previous_enabled",
    }
)

# Project runtime/status/output tracking. Prefixes cover the whole ``last_*``
# progress block, the ``active_bake_*`` in-flight job snapshot, and the
# ``reproject_*`` live-reprojection status.
_PROJECT_DENIED_NAMES = frozenset(
    {
        "rna_type",
        "hierarchy_focus",  # which panel is focused, not a bake setting
        "active_texture_set_index",
        "active_output_index",
    }
)
_PROJECT_DENIED_PREFIXES = ("last_", "active_bake_", "reproject_")

# Applied before the sweep because their update callbacks REWRITE sibling fields:
# a named lighting_quality preset stamps its transport tuple over
# lighting_direct_samples/indirect_paths/max_bounces/noise_threshold, and
# ao_mode=DIFFUSIVE_ESCAPE clears the AO toggles it is incompatible with. The
# saved sibling values must win, so the driver goes first.
_MAP_DRIVER_FIELDS = ("map_type", "ao_mode", "lighting_quality")

# Handled explicitly in the loader (identity, driver ordering, or a legacy
# sibling derivation) and therefore skipped by the generic sweep.
_MAP_KEYS_APPLIED_ELSEWHERE = frozenset(
    {
        "uuid",
        "map_type",
        "ao_mode",
        "lighting_quality",
        "normal_format",
        "flip_green",
        "position_normalization",
        "ao_cavity_weight",
        # Carried as a datablock NAME, not as the pointer the sweep skips.
        "material_detail_image_name",
    }
)

# Payload envelope, nested collections, and the project fields whose update
# callbacks depend on assignment order (the resolution trio rewrites its own
# siblings; aa_samples falls back to the legacy anti_aliasing enum; the index
# fields must land after the collections they point into).
_PROJECT_KEYS_APPLIED_ELSEWHERE = frozenset(
    {
        "schema",
        "version",
        "schema_version",
        "maps",
        "groups",
        "name",
        "resolution_preset",
        "lock_resolution",
        "resolution_x",
        "resolution_y",
        "anti_aliasing",
        "aa_samples",
        "ignore_backface",
        "active_map_index",
        "active_group_index",
    }
)

# The nested ``*_settings`` sub-groups on a map row (normal_settings,
# ao_settings, curvature_settings, ...) are PURE ONE-WAY MIRRORS of the flat
# fields: properties.map_*_settings_state() re-syncs them from the flat values on
# every read and nothing ever writes them directly. They hold no independent
# state, so serializing them would only duplicate the flat fields -- they are
# PointerProperties and the sweep skips them by type.


def _name_is_denied(identifier: str, denied_names, denied_prefixes) -> bool:
    if identifier in denied_names:
        return True
    return any(identifier.startswith(prefix) for prefix in denied_prefixes)


def _property_is_serializable(prop) -> bool:
    prop_type = str(getattr(prop, "type", "") or "")
    if prop_type not in _SERIALIZABLE_PROPERTY_TYPES:
        return False
    if getattr(prop, "is_readonly", False):
        return False
    if getattr(prop, "is_enum_flag", False):
        # Enum-flag properties hold a set, not a scalar; nothing in the bake
        # stack uses one, and a set has no stable JSON form here.
        return False
    array_length = int(getattr(prop, "array_length", 0) or 0)
    if array_length and (prop_type != "FLOAT" or array_length > _MAX_SERIALIZABLE_VECTOR_LENGTH):
        return False
    return True


def _coerce_rna_value(prop_type: str, array_length: int, value):
    if array_length:
        return [float(component) for component in value]
    if prop_type == "BOOLEAN":
        return bool(value)
    if prop_type == "INT":
        return int(value)
    if prop_type == "FLOAT":
        return float(value)
    return str(value)


def _coerce_plain_value(value):
    """JSON form of a plain Python attribute, or ``_SKIP`` when it is not scalar."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (tuple, list)) and 2 <= len(value) <= _MAX_SERIALIZABLE_VECTOR_LENGTH:
        if all(isinstance(component, (int, float)) and not isinstance(component, bool) for component in value):
            return [float(component) for component in value]
    return _SKIP


def _serialize_properties(owner, *, denied_names, denied_prefixes=()) -> dict:
    values: dict = {}
    if owner is None:
        return values
    rna_properties = getattr(getattr(owner, "bl_rna", None), "properties", None)
    if rna_properties is None:
        # Outside Blender (unit tests, legacy adapters) there is no RNA to walk;
        # fall back to the object's own simple-typed attributes.
        try:
            attributes = sorted(vars(owner).items())
        except TypeError:
            return values
        for identifier, value in attributes:
            if identifier.startswith("_") or _name_is_denied(identifier, denied_names, denied_prefixes):
                continue
            coerced = _coerce_plain_value(value)
            if coerced is not _SKIP:
                values[identifier] = coerced
        return values
    for prop in rna_properties:
        identifier = str(getattr(prop, "identifier", "") or "")
        if not identifier or _name_is_denied(identifier, denied_names, denied_prefixes):
            continue
        if not _property_is_serializable(prop):
            continue
        try:
            value = getattr(owner, identifier)
        except (AttributeError, TypeError):
            continue
        values[identifier] = _coerce_rna_value(
            str(prop.type), int(getattr(prop, "array_length", 0) or 0), value
        )
    return values


def _assign_property(owner, identifier: str, value) -> bool:
    try:
        setattr(owner, identifier, value)
    except (AttributeError, TypeError, ValueError):
        # An unknown key from a newer build, or an enum value this build no longer
        # defines, must skip that one field instead of aborting the whole load.
        return False
    return True


def _apply_serialized_properties(owner, data: dict, *, denied_names, denied_prefixes=(), skip_names=frozenset()) -> None:
    for identifier in sorted(data):
        if identifier in skip_names or _name_is_denied(identifier, denied_names, denied_prefixes):
            continue
        value = data[identifier]
        if isinstance(value, dict):
            continue
        if isinstance(value, (list, tuple)) and _coerce_plain_value(value) is _SKIP:
            continue
        _assign_property(owner, identifier, value)


def _map_row_to_payload(item) -> dict:
    """Serialize one map row.

    ``uuid`` is included deliberately: restoring the SAME row identity keeps
    tracked outputs, dirty state, and export channel aliases attached to the row
    across a save/load round-trip instead of orphaning them on every load.
    """
    payload = _serialize_properties(item, denied_names=_MAP_DENIED_NAMES)
    # ``material_detail_image`` is a PointerProperty, so the RNA sweep skips it by
    # type -- yet it is a real user setting (Material Detail = Manual picks the AO
    # source image) and its absence is a BLOCKING preflight error: "Manual Material
    # Detail requires an AO source image" (validation.py). A row saved as Manual came
    # back as Manual with no image from every preset load and from Undo Remove
    # Project / Undo Remove Map, so the restored project would not bake at all.
    # Images are datablocks; it travels by NAME like the group paint images do.
    payload["material_detail_image_name"] = str(
        getattr(getattr(item, "material_detail_image", None), "name", "") or ""
    )
    return payload


def map_row_to_payload(item) -> dict:
    """Public single-row serializer.

    Same payload the project preset carries per map row, so a row stashed by
    ``remove_map`` and a row loaded from a preset go through one code path.
    """
    return _map_row_to_payload(item)


def apply_payload_to_map(item, map_data: dict) -> None:
    """Write one serialized map row onto ``item``.

    Extracted from the project-preset loop so a single restored row is rebuilt by
    exactly the same rules -- including the driver-field ordering below, which is
    the difference between a restored AO row keeping its mode and silently reverting.
    """
    map_data = map_data or {}
    preset_uuid = str(map_data.get("uuid", "") or "").strip()
    if preset_uuid:
        item.uuid = preset_uuid
    else:
        # Presets saved before uuids were persisted: a fresh identity is the
        # only option, and downstream orphan handling covers the fallout.
        properties.ensure_map_setting_uuid(item)
    # Driver fields first: their update callbacks rewrite siblings, so the
    # saved sibling values must be written after them (see _MAP_DRIVER_FIELDS).
    _assign_property(item, "map_type", map_data.get("map_type", ""))
    for driver_field in _MAP_DRIVER_FIELDS[1:]:
        if driver_field in map_data:
            _assign_property(item, driver_field, map_data[driver_field])
    _apply_legacy_map_aliases(item, map_data)
    _apply_material_detail_image(item, map_data)
    # Enum values from older/foreign presets may no longer exist and newer
    # presets may carry keys this build has never heard of; either way a bad
    # field is skipped rather than aborting the load mid-stack.
    _apply_serialized_properties(
        item,
        map_data,
        denied_names=_MAP_DENIED_NAMES,
        skip_names=_MAP_KEYS_APPLIED_ELSEWHERE,
    )
    # The sweep above wrote the four lighting transport fields, and each write
    # fires _lighting_transport_update outside the quality sync guard, which
    # promotes a named Quality to Custom: a preset saved as Balanced loaded as
    # Custom. Re-assert the saved quality last (its own update re-syncs the
    # transports from the named preset, which the payload carried anyway).
    quality = str(map_data.get("lighting_quality", "") or "").strip()
    if quality and hasattr(item, "lighting_quality") and str(getattr(item, "lighting_quality", "") or "") != quality:
        _assign_property(item, "lighting_quality", quality)


def _apply_material_detail_image(item, map_data: dict) -> None:
    """Resolve the Manual Material Detail AO source back onto ``item`` by name.

    Mirrors _apply_paint_payload_to_group: a missing key leaves the current pointer
    alone (a preset written before the key existed must not clear it), an empty name
    clears it, and a name that no longer exists in this blend resolves to None -- the
    same state a fresh row is in, which validation already reports.
    """
    if "material_detail_image_name" not in map_data or not hasattr(item, "material_detail_image"):
        return
    images = _images_datablock()
    if images is None:
        return
    name = str(map_data.get("material_detail_image_name", "") or "").strip()
    _assign_property(item, "material_detail_image", images.get(name) if name else None)


def texture_set_to_payload(texture_set) -> dict:
    """Serialize one texture set: identity, output-name mode, and UDIM configuration."""
    tiles = []
    for tile in _collection_items(getattr(texture_set, "udim_tiles", [])):
        tiles.append(
            {
                "number": int(getattr(tile, "number", 0) or 0),
                "override": str(getattr(tile, "override", "") or ""),
                "use_resolution_override": bool(getattr(tile, "use_resolution_override", False)),
                "resolution_x": int(getattr(tile, "resolution_x", 0) or 0),
                "resolution_y": int(getattr(tile, "resolution_y", 0) or 0),
            }
        )
    return {
        "name": str(getattr(texture_set, "name", "") or ""),
        "name_mode": str(getattr(texture_set, "name_mode", "") or ""),
        "udim_mode": str(getattr(texture_set, "udim_mode", "") or ""),
        "udim_tiles": tiles,
    }


def apply_payload_to_texture_set(item, data: dict) -> None:
    """Write one serialized texture set onto ``item``.

    Every write is individually guarded: a set restored into a build whose enum
    values moved on must still come back with its name and its member links, which
    is the part the artist cannot retype.
    """
    data = data or {}
    name = str(data.get("name", "") or "").strip()
    if name:
        item.name = name
    for key in ("name_mode", "udim_mode"):
        value = str(data.get(key, "") or "").strip()
        if not value or not hasattr(item, key):
            continue
        try:
            setattr(item, key, value)
        except Exception:
            continue
    tiles = data.get("udim_tiles") or []
    collection = getattr(item, "udim_tiles", None)
    if not tiles or collection is None or not hasattr(collection, "add"):
        return
    try:
        _clear_collection(collection)
    except Exception:
        return
    for tile_data in tiles:
        try:
            tile = collection.add()
        except Exception:
            continue
        for key, caster in (
            ("number", int),
            ("override", str),
            ("use_resolution_override", bool),
            ("resolution_x", int),
            ("resolution_y", int),
        ):
            if key not in tile_data:
                continue
            try:
                setattr(tile, key, caster(tile_data[key]))
            except Exception:
                continue


def _slot_collection_to_payload(collection) -> list:
    """Object name + per-mesh cage offset (+ Casts AO when off) for every filled slot, in list order."""
    payload = []
    for slot in _collection_items(collection):
        if getattr(slot, "object_ref", None) is None:
            continue
        entry = {
            "name": getattr(getattr(slot, "object_ref", None), "name", ""),
            "cage_offset_delta": float(getattr(slot, "cage_offset_delta", 0.0)),
        }
        # Written only when off, so presets saved before the toggle existed round-trip unchanged.
        if not bool(getattr(slot, "casts_ao", True)):
            entry["casts_ao"] = False
        payload.append(entry)
    return payload


def slot_collection_to_payload(collection) -> list:
    """Public form of the role-slot serializer (used by the role-slot undo stash)."""
    return _slot_collection_to_payload(collection)


def sync_slot_payload_to_collections(payload, target_collections, object_lookup=None) -> None:
    """Public form of the role-slot restorer.

    A bake group mirrors each role list across two collections (the group and its
    nested role-assignments state), so a restore has to rewrite both or the two
    disagree about what is assigned.
    """
    _sync_slot_payload_to_collections(payload or [], target_collections, object_lookup)


def group_to_payload(group, *, project_ignore_backface: bool | None = None) -> dict:
    """Serialize one bake group: metadata, cage state, paint state, and both role lists.

    Hand-shaped rather than swept, because it flattens nested state groups and
    resolves object pointers to names -- neither of which a generic sweep can do.
    """
    metadata_state = _group_metadata_state(group)
    projection_state = _group_projection_settings_state(group)
    paint_state = _group_paint_state(group)
    if project_ignore_backface is None:
        project_ignore_backface = bool(getattr(projection_state, "ignore_backface", False))
    return {
        "name": getattr(metadata_state, "name", ""),
        "texture_set_name": getattr(metadata_state, "texture_set_name", ""),
        "id_collection_name": getattr(metadata_state, "id_collection_name", ""),
        "id_color_set_name": getattr(metadata_state, "id_color_set_name", ""),
        "uv_layer_name": getattr(projection_state, "uv_layer_name", ""),
        "cage_mode": getattr(projection_state, "cage_mode", ""),
        "cage_offset": float(getattr(projection_state, "cage_offset", 0.0)),
        "projection_rear_distance": float(_group_field(group, projection_state, "projection_rear_distance", 0.0)),
        "average_normals": bool(getattr(projection_state, "average_normals", True)),
        "ignore_backface": bool(project_ignore_backface),
        "isolate_in_viewport": bool(getattr(group, "isolate_in_viewport", False)),
        "use_low_as_high": bool(getattr(_group_role_assignments_state(group), "use_low_as_high", False)),
        "match_by_isolation": bool(_group_field(group, projection_state, "match_by_isolation", False)),
        # Paint Offset & Skew shipped for 1.0 but never survived a preset. Images are
        # datablocks, so they travel by name and resolve on load like every other pointer.
        "paint_offset_scale": float(_group_field(group, paint_state, "paint_offset_scale", 1.0)),
        "paint_skew": float(_group_field(group, paint_state, "paint_skew", 0.0)),
        "paint_offset_image_name": getattr(
            _group_field(group, paint_state, "paint_offset_image", None), "name", ""
        ),
        "paint_skew_image_name": getattr(
            _group_field(group, paint_state, "paint_skew_image", None), "name", ""
        ),
        "custom_cage_name": getattr(getattr(projection_state, "custom_cage", None), "name", ""),
        "low_meshes": _slot_collection_to_payload(getattr(group, "low_meshes", [])),
        "high_meshes": _slot_collection_to_payload(getattr(group, "high_meshes", [])),
    }


def apply_payload_to_group(group, group_data: dict, object_lookup=None, *, project=None) -> None:
    """Write one serialized bake group onto ``group``, resolving meshes by name.

    ``project`` is optional and only supplies the project-wide ``ignore_backface``,
    which outranks the per-group copy in the payload (the field moved to the project
    and the group value is a legacy mirror).
    """
    group_data = group_data or {}
    group.name = group_data.get("name", "")
    group.texture_set_name = group_data.get("texture_set_name", "")
    group.id_collection_name = group_data.get("id_collection_name", "")
    group.id_color_set_name = group_data.get("id_color_set_name", "")
    group.uv_layer_name = group_data.get("uv_layer_name", "")
    # The cage pointer's update callback forces cage_mode to CUSTOM whenever it
    # is set, so it has to land BEFORE the stored mode or a group with a cage
    # object still assigned but Cage Mode set back to Distance/Automatic came
    # back as Custom on every preset load and every undo-restore.
    group.custom_cage = _get_resolved_object(group_data.get("custom_cage_name", ""), object_lookup)
    group.cage_mode = group_data.get("cage_mode", "")
    group.cage_offset = float(group_data.get("cage_offset", 0.0))
    group.average_normals = bool(group_data.get("average_normals", True))
    if project is None:
        group.ignore_backface = bool(group_data.get("ignore_backface", False))
    else:
        group.ignore_backface = bool(getattr(project, "ignore_backface", group_data.get("ignore_backface", False)))
    group.isolate_in_viewport = bool(group_data.get("isolate_in_viewport", False))
    group.use_low_as_high = bool(group_data.get("use_low_as_high", False))
    if "projection_rear_distance" in group_data:
        _set_group_field(
            group,
            _group_projection_settings_state(group),
            "projection_rear_distance",
            max(0.0, float(group_data.get("projection_rear_distance", 0.0) or 0.0)),
        )
    if "match_by_isolation" in group_data:
        _set_group_field(
            group,
            _group_projection_settings_state(group),
            "match_by_isolation",
            bool(group_data.get("match_by_isolation", False)),
        )
    _apply_paint_payload_to_group(group, group_data)

    role_state = _group_role_assignments_state(group)
    if hasattr(role_state, "use_low_as_high"):
        role_state.use_low_as_high = group.use_low_as_high
    low_meshes = _ensure_collection(group, "low_meshes")
    high_meshes = _ensure_collection(group, "high_meshes")
    nested_low_meshes = _ensure_collection(role_state, "low_meshes")
    nested_high_meshes = _ensure_collection(role_state, "high_meshes")

    legacy_low_mesh_names = group_data.get("low_mesh_names", [])
    low_mesh_payload = group_data.get(
        "low_meshes",
        [{"name": object_name, "cage_offset_delta": 0.0} for object_name in legacy_low_mesh_names],
    )
    _sync_slot_payload_to_collections(low_mesh_payload, [low_meshes, nested_low_meshes], object_lookup)

    legacy_high_mesh_names = group_data.get("high_mesh_names", [])
    high_mesh_payload = group_data.get(
        "high_meshes",
        [{"name": object_name, "cage_offset_delta": 0.0} for object_name in legacy_high_mesh_names],
    )
    _sync_slot_payload_to_collections(high_mesh_payload, [high_meshes, nested_high_meshes], object_lookup)
    if hasattr(role_state, "low_mesh_index"):
        role_state.low_mesh_index = int(getattr(group, "low_mesh_index", 0))
    if hasattr(role_state, "high_mesh_index"):
        role_state.high_mesh_index = int(getattr(group, "high_mesh_index", 0))


def _apply_legacy_map_aliases(item, map_data: dict) -> None:
    """Restore the field pairs whose older presets only stored one half."""
    normal_format = map_data.get(
        "normal_format",
        constants.NORMAL_FORMAT_DIRECTX
        if bool(map_data.get("flip_green", False))
        else constants.NORMAL_FORMAT_OPENGL,
    )
    _assign_property(item, "normal_format", normal_format)
    _assign_property(
        item,
        "flip_green",
        bool(map_data.get("flip_green", normal_format == constants.NORMAL_FORMAT_DIRECTX)),
    )
    _assign_property(
        item,
        "position_normalization",
        str(
            map_data.get(
                "position_normalization",
                constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX
                if bool(map_data.get("relative_to_bounding_box", True))
                else constants.MAP_POSITION_NORMALIZATION_OBJECT_ORIGIN,
            )
        ),
    )
    # The neutral cavity weight depends on the row's map type, so it cannot fall
    # back to the property default.
    _assign_property(
        item,
        "ao_cavity_weight",
        float(
            map_data.get(
                "ao_cavity_weight",
                constants.default_ao_cavity_weight_for_map(getattr(item, "map_type", "")),
            )
        ),
    )


def _sync_slot_payload_to_collections(payload, target_collections, object_lookup) -> None:
    unique_targets = []
    for collection in target_collections:
        if collection is None or any(existing is collection for existing in unique_targets):
            continue
        _clear_collection(collection)
        unique_targets.append(collection)
    for slot_payload in payload:
        object_name = slot_payload.get("name", "")
        obj = _get_resolved_object(object_name, object_lookup)
        if obj is None:
            continue
        for collection in unique_targets:
            slot = collection.add()
            slot.object_ref = obj
            slot.cage_offset_delta = float(slot_payload.get("cage_offset_delta", 0.0))
            if not bool(slot_payload.get("casts_ao", True)):
                slot.casts_ao = False


_EXPORT_SETTINGS_ROW_COLLECTIONS = ("set_overrides", "excluded_texture_sets")


def _export_settings_to_payload(export_settings) -> dict:
    if export_settings is None:
        return {}
    payload = _serialize_properties(export_settings, denied_names=frozenset(_EXPORT_SETTINGS_ROW_COLLECTIONS))
    for collection_name in _EXPORT_SETTINGS_ROW_COLLECTIONS:
        payload[collection_name] = [
            _serialize_properties(row, denied_names=frozenset())
            for row in _collection_items(getattr(export_settings, collection_name, []))
        ]
    return payload


def copy_serializable_properties(source, target, *, denied_names=frozenset(), denied_prefixes=(), skip_names=frozenset()) -> None:
    """Copy every serializable scalar from ``source`` onto ``target`` by RNA reflection.

    Deliberately the same rules the preset sweep uses: Duplicate Project and a preset
    save/load must agree on which properties are user settings, or one of them drifts
    behind properties.py. project_structure.copy_project was a hand-written field list
    and had drifted by ~15 fields (workflow, image_format, the material-detail block,
    the paint block, UDIM), so a duplicated MATERIAL project came back as HIGH_TO_LOW.
    """
    _apply_serialized_properties(
        target,
        _serialize_properties(source, denied_names=denied_names, denied_prefixes=denied_prefixes),
        denied_names=denied_names,
        denied_prefixes=denied_prefixes,
        skip_names=skip_names,
    )


def export_settings_to_payload(export_settings) -> dict:
    """Public form of the export-settings serializer (used by Duplicate Project)."""
    return _export_settings_to_payload(export_settings)


def apply_export_settings_payload(export_settings, data) -> None:
    """Public form of the export-settings restorer (used by Duplicate Project)."""
    _apply_export_settings_payload(export_settings, data)


def _apply_export_settings_payload(export_settings, data) -> None:
    if export_settings is None or not isinstance(data, dict):
        return
    scalars = {key: value for key, value in data.items() if key not in _EXPORT_SETTINGS_ROW_COLLECTIONS}
    _apply_serialized_properties(export_settings, scalars, denied_names=frozenset())
    for collection_name in _EXPORT_SETTINGS_ROW_COLLECTIONS:
        rows = data.get(collection_name)
        collection = getattr(export_settings, collection_name, None)
        if not isinstance(rows, list) or collection is None or not hasattr(collection, "add"):
            continue
        _clear_collection(collection)
        for row_data in rows:
            if not isinstance(row_data, dict):
                continue
            row = collection.add()
            _apply_serialized_properties(row, row_data, denied_names=frozenset())


def project_to_payload(project) -> dict:
    projection_groups = list(_collection_items(getattr(project, "groups", [])))
    project_ignore_backface = bool(
        getattr(
            project,
            "ignore_backface",
            any(bool(getattr(_group_projection_settings_state(group), "ignore_backface", False)) for group in projection_groups),
        )
    )
    payload = {
        "schema": PRESET_SCHEMA,
        "version": 1,
        # The migration stamp describes the DATA, so it travels with it. Without it
        # a restored or preset-loaded project started at schema 0 and every one-time
        # migration re-ran on current settings: an explicit OpenGL Normal row came
        # back as DirectX and the curvature probe mirrors were reset (2026-09-06).
        "schema_version": int(getattr(project, "schema_version", 0) or 0),
    }
    # Every simple, writable project scalar travels automatically; see the sweep
    # notes above for why this is not a hand-maintained list.
    payload.update(_serialize_properties(project, denied_names=_PROJECT_DENIED_NAMES, denied_prefixes=_PROJECT_DENIED_PREFIXES))
    # Legacy fallbacks that the sweep cannot express: both are derived when the
    # project predates the field.
    payload["name"] = getattr(project, "name", "")
    payload["lock_resolution"] = bool(
        getattr(
            project,
            "lock_resolution",
            int(getattr(project, "resolution_x", 0)) == int(getattr(project, "resolution_y", 0)),
        )
    )
    payload["ignore_backface"] = project_ignore_backface
    # Texture sets are a sibling collection of groups, not a scalar, so the generic
    # property sweep never saw them. Without this a preset restored groups that named a
    # set with no matching entry -- the exact state that surfaces the "Migrate Texture
    # Sets" prompt on a brand-new project (RC sweep 2026-08-29, findings 3 and 4).
    payload["texture_sets"] = [
        texture_set_to_payload(texture_set)
        for texture_set in _collection_items(getattr(project, "texture_sets", []))
    ]
    payload["maps"] = [_map_row_to_payload(item) for item in _collection_items(getattr(project, "maps", []))]
    # export_settings is a PointerProperty, which the RNA sweep skips by type, so
    # the output directory, template choice, per-set overrides and exclusions
    # never travelled in a project preset.
    payload["export_settings"] = _export_settings_to_payload(getattr(project, "export_settings", None))
    # Group / low-high / cage serialization stays hand-shaped: it flattens nested
    # state groups and resolves object pointers to names, which no generic sweep
    # can do (see group_to_payload).
    payload["groups"] = [
        group_to_payload(group, project_ignore_backface=project_ignore_backface)
        for group in projection_groups
    ]
    return payload


class PresetError(RuntimeError):
    """A save that would destroy an existing preset, reported to the artist."""


def save_project_preset(project, preset_name: str) -> Path:
    # Always the user tier: a shipped preset is read-only, exactly as a built-in
    # output template is.
    directory = ensure_preset_dir()
    name = str(preset_name or "").strip()
    file_stem = sanitize_preset_name(name)
    # Two different names can sanitize onto one file ("My Project" and "My_Project"),
    # and list_preset_paths keys by stem, so the artist never saw both: saving the
    # second silently destroyed the first. Same rule export_templates enforces.
    for existing in list_preset_paths():
        if existing.stem.casefold() != file_stem.casefold():
            continue
        if existing.stem.casefold() != name.casefold() and existing.stem != name:
            raise PresetError(
                f"'{name}' would be saved over the preset '{existing.stem}'; choose another name"
            )
    path = directory / f"{file_stem}.json"
    # Temp + replace, with the pid in the temp name. A direct write_text truncates the
    # artist's existing preset first, so a crash, a full disk or a second Blender
    # session saving the same name left it torn -- and a torn preset is a project
    # setup they cannot get back.
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(project_to_payload(project), indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    # Directory mtime alone would usually catch this, but Windows' system clock ticks
    # at ~15 ms while a save + reopening the dropdown does not: invalidate directly so
    # the preset the artist just saved is always in the list.
    invalidate_preset_items_cache()
    return path


def load_project_preset_data(preset_name: str) -> dict:
    path = preset_path_for_name(preset_name)
    return json.loads(path.read_text(encoding="utf-8"))


def apply_payload_to_project(project, payload: dict, object_lookup=None) -> None:
    # Payload application assigns every role slot of every group; per-slot
    # membership cascades are both slow (see suspend_group_membership_updates)
    # and re-entrant (the preview-visibility sync reads back the half-applied
    # group). Callers run properties.bulk_group_membership_refresh() once after.
    with properties.suspend_group_membership_updates():
        _apply_payload_to_project_inner(project, payload, object_lookup)


def apply_payload_to_project_scalars(project, payload: dict, *, apply_name: bool = True) -> None:
    """Write every project-level scalar from ``payload`` onto ``project``.

    Split out of the loader so Duplicate Project applies the SAME fields in the SAME
    order without also rebuilding the collections (it copies object pointers directly
    rather than resolving them by name). ``apply_name`` is off for the copy, which
    names itself ``<source>_Copy``.
    """
    # Only fields with an assignment-order constraint or a legacy derivation are
    # written by hand here; _PROJECT_KEYS_APPLIED_ELSEWHERE lists them and the
    # generic sweep at the end of this block carries everything else.
    if apply_name:
        project.name = payload.get("name", getattr(project, "name", "BakeProject"))
    resolution_x = int(payload.get("resolution_x", getattr(project, "resolution_x", 2048)))
    resolution_y = int(payload.get("resolution_y", getattr(project, "resolution_y", 2048)))
    lock_resolution = bool(payload.get("lock_resolution", resolution_x == resolution_y))
    resolution_preset = str(payload.get("resolution_preset", "") or "")
    if not resolution_preset:
        resolution_preset = constants.output_size_preset_from_dimensions(resolution_x, resolution_y)
    project.resolution_preset = resolution_preset
    project.lock_resolution = lock_resolution
    project.resolution_x = resolution_x
    project.resolution_y = resolution_y
    project.anti_aliasing = str(payload.get("anti_aliasing", getattr(project, "anti_aliasing", constants.DEFAULT_ANTI_ALIASING)))
    # Prefer the exact sample count when present; fall back to the legacy enum
    # mapping for presets saved before the samples control existed.
    project.aa_samples = int(payload.get("aa_samples", constants.anti_aliasing_to_samples(project.anti_aliasing)))
    legacy_group_ignore_backface = any(bool(group_data.get("ignore_backface", False)) for group_data in payload.get("groups", []))
    project.ignore_backface = bool(payload.get("ignore_backface", getattr(project, "ignore_backface", legacy_group_ignore_backface)))
    # Missing keys are simply skipped, so a preset saved before a field existed
    # leaves the project's CURRENT value untouched instead of resetting it.
    _apply_serialized_properties(
        project,
        payload,
        denied_names=_PROJECT_DENIED_NAMES,
        denied_prefixes=_PROJECT_DENIED_PREFIXES,
        skip_names=_PROJECT_KEYS_APPLIED_ELSEWHERE,
    )
    # A payload without the stamp predates it (or was hand-edited), so it stays at
    # 0 and migrates. A stamp above this build's schema cannot be trusted: clamp it.
    try:
        stamped = int(payload.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        stamped = 0
    if hasattr(project, "schema_version"):
        project.schema_version = max(0, min(stamped, int(constants.PROJECT_SCHEMA_VERSION)))


def _apply_payload_to_project_inner(project, payload: dict, object_lookup=None) -> None:
    apply_payload_to_project_scalars(project, payload)

    _clear_collection(project.maps)
    for map_data in payload.get("maps", []):
        apply_payload_to_map(project.maps.add(), map_data)

    # Texture sets before groups: a group's texture_set_name must land on an entry that
    # already exists, or the project comes back in the "needs Migrate Texture Sets" state.
    # Presets written before this key existed fall back to deriving the sets from the
    # group names they carry, so old presets load clean too.
    _restore_texture_sets(project, payload)
    _apply_export_settings_payload(getattr(project, "export_settings", None), payload.get("export_settings"))

    _clear_collection(project.groups)
    for group_data in payload.get("groups", []):
        apply_payload_to_group(project.groups.add(), group_data, object_lookup, project=project)

    project.active_map_index = int(payload.get("active_map_index", 0))
    project.active_group_index = int(payload.get("active_group_index", 0))


def load_project_preset(project, preset_name: str, object_lookup=None) -> dict:
    payload = load_project_preset_data(preset_name)
    apply_payload_to_project(project, payload, object_lookup=object_lookup)
    return payload
