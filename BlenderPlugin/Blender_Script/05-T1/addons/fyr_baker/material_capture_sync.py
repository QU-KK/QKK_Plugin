"""Debounced map-stack synchronization from Fyr capture / custom-output nodes."""
from __future__ import annotations

import time

import bpy

from . import constants
from . import material_graph
from . import naming

_PENDING = False
_LAST_REQUEST = 0.0
_DEBOUNCE_SEC = 0.35


def schedule_sync() -> None:
    """Mark sync needed; mutate collections on a timer outside RNA callbacks."""
    global _PENDING, _LAST_REQUEST
    _PENDING = True
    _LAST_REQUEST = time.monotonic()
    if not bpy.app.timers.is_registered(_timer_poll):
        bpy.app.timers.register(_timer_poll, first_interval=_DEBOUNCE_SEC)


def _timer_poll() -> float | None:
    global _PENDING
    if not _PENDING:
        return None
    if time.monotonic() - _LAST_REQUEST < _DEBOUNCE_SEC:
        return 0.1
    try:
        from . import blender_bake

        if blender_bake.material_isolation_active():
            # The bake's own material.copy() fired the capture nodes' copy() and
            # scheduled this sync; running it now reads the __fyr_matbake_ copies
            # through the objects' slots and stamps rows with node ids that vanish
            # at cleanup. Wait for the isolation to close.
            return 0.25
    except Exception:
        pass
    _PENDING = False
    try:
        _sync_all_projects()
    except Exception as exc:
        print(f"[FyrBaker] material capture sync failed: {exc}")
    return None


def _sync_all_projects() -> None:
    from . import properties

    for scene in bpy.data.scenes:
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []) or []:
            sync_project(project)


def _suppressed_keys(project) -> set[str]:
    keys = set()
    for item in getattr(project, "material_binding_suppressions", []) or []:
        key = str(getattr(item, "binding_key", "") or "").strip()
        if key:
            keys.add(key)
    return keys


def _add_suppression(project, binding_key: str) -> None:
    key = str(binding_key or "").strip()
    if not key or key in _suppressed_keys(project):
        return
    item = project.material_binding_suppressions.add()
    item.binding_key = key


def _find_row_by_binding(project, binding_key: str):
    key = str(binding_key or "").strip()
    matches = []
    for item in getattr(project, "maps", []) or []:
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "material_binding_key", "") or "").strip() == key:
            matches.append(item)
    if not matches:
        return None
    # Prefer an enabled row, then the first match.
    for item in matches:
        if bool(getattr(item, "enabled", False)):
            return item
    return matches[0]


def _find_manual_standard_row(project, channel: str):
    channel = str(channel or "").strip().upper()
    for item in getattr(project, "maps", []) or []:
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        if str(getattr(item, "material_channel", "") or "").strip().upper() != channel:
            continue
        origin = str(getattr(item, "material_origin", "") or constants.MATERIAL_ORIGIN_MANUAL)
        binding = str(getattr(item, "material_binding_key", "") or "").strip()
        if origin == constants.MATERIAL_ORIGIN_MANUAL or not binding:
            return item
    return None


def _apply_row_metadata(item, *, origin: str, binding_key: str, resolve: str, data_type: str, node_ids: list[str], messages: list[str]):
    item.material_origin = origin
    item.material_binding_key = binding_key
    item.material_resolve_state = resolve
    item.material_data_type = data_type
    item.material_source_node_ids = ",".join(dict.fromkeys(node_ids))
    item.material_status_message = "; ".join(messages[:3])


def sync_project(project, *, clear_suppressions: bool = False) -> dict:
    """Synchronize capture/custom detections into the project's map stack."""
    from . import material_capture_nodes
    from . import properties

    if project is None:
        return {"added": 0, "updated": 0, "missing": 0}

    if clear_suppressions:
        while len(getattr(project, "material_binding_suppressions", []) or []):
            project.material_binding_suppressions.remove(0)

    # Migrate legacy material rows to manual standard bindings once.
    for item in getattr(project, "maps", []) or []:
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
            continue
        if str(getattr(item, "material_binding_key", "") or "").strip():
            continue
        channel = str(getattr(item, "material_channel", "") or "").strip().upper()
        binding = constants.CAPTURE_CHANNEL_TO_BINDING.get(channel, "")
        if binding:
            item.material_origin = constants.MATERIAL_ORIGIN_MANUAL
            item.material_binding_key = binding
            item.material_resolve_state = constants.MATERIAL_RESOLVE_RESOLVED
            item.material_data_type = (
                constants.MATERIAL_DATA_COLOR
                if channel in {constants.MATERIAL_CHANNEL_ALBEDO, constants.MATERIAL_CHANNEL_EMISSION}
                else constants.MATERIAL_DATA_VALUE
            )

    materials = material_capture_nodes.project_materials(project)
    # Only auto-create rows when at least one active capture or custom output exists.
    has_sources = False
    for material in materials:
        if material_capture_nodes.find_active_capture(material) is not None:
            has_sources = True
            break
        if any(True for _ in material_capture_nodes.iter_custom_outputs(material)):
            has_sources = True
            break

    profile = str(getattr(project, "material_profile", "") or constants.MATERIAL_PROFILE_STANDARD)
    suppressed = _suppressed_keys(project)
    added = updated = missing = 0

    if not has_sources:
        # Mark previously auto-managed rows missing when all captures disappear.
        for item in getattr(project, "maps", []) or []:
            if getattr(item, "is_add_phantom", False):
                continue
            origin = str(getattr(item, "material_origin", "") or "")
            if origin not in {constants.MATERIAL_ORIGIN_CAPTURE, constants.MATERIAL_ORIGIN_CUSTOM}:
                continue
            if str(getattr(item, "material_resolve_state", "") or "") == constants.MATERIAL_RESOLVE_MISSING:
                continue
            if not hasattr(item, "material_previous_enabled"):
                continue
            item.material_previous_enabled = bool(getattr(item, "enabled", False))
            item.enabled = False
            item.material_resolve_state = constants.MATERIAL_RESOLVE_MISSING
            missing += 1
        return {"added": added, "updated": updated, "missing": missing}

    bindings = material_graph.meaningful_bindings_for_materials(materials, profile=profile)
    present_keys = set(bindings.keys())

    for binding_key, meta in bindings.items():
        if binding_key in suppressed:
            continue
        origin = meta["origin"]
        resolve = meta["resolve"]
        # Normal / Height from capture map to existing geometry map types.
        channel_key = str(meta.get("channel_key") or "")
        if channel_key == "NORMAL":
            row = _find_row_by_binding(project, binding_key)
            if row is None:
                # Prefer an existing Normal row without claiming geometry normals away.
                for item in project.maps:
                    if getattr(item, "is_add_phantom", False):
                        continue
                    if str(getattr(item, "map_type", "") or "").upper() != constants.MAP_NORMAL:
                        continue
                    if str(getattr(item, "material_binding_key", "") or "").strip():
                        continue
                    row = item
                    break
            if row is None:
                if origin == constants.MATERIAL_ORIGIN_CAPTURE:
                    row = properties.add_map_setting(project, constants.MAP_NORMAL)
                    row.enabled = True
                    row.material_detail_mode = constants.MATERIAL_DETAIL_MATERIAL_ONLY if hasattr(constants, "MATERIAL_DETAIL_MATERIAL_ONLY") else row.material_detail_mode
                    added += 1
                else:
                    continue
            else:
                # Restore enabled state if returning from missing.
                if str(getattr(row, "material_resolve_state", "") or "") == constants.MATERIAL_RESOLVE_MISSING:
                    row.enabled = bool(getattr(row, "material_previous_enabled", True))
                updated += 1
            _apply_row_metadata(
                row,
                origin=origin,
                binding_key=binding_key,
                resolve=resolve,
                data_type=constants.MATERIAL_DATA_VECTOR,
                node_ids=meta.get("node_ids") or [],
                messages=meta.get("messages") or [],
            )
            continue

        if channel_key == "HEIGHT":
            row = _find_row_by_binding(project, binding_key)
            if row is None:
                for item in project.maps:
                    if getattr(item, "is_add_phantom", False):
                        continue
                    if str(getattr(item, "map_type", "") or "").upper() != constants.MAP_HEIGHT:
                        continue
                    if str(getattr(item, "material_binding_key", "") or "").strip():
                        continue
                    row = item
                    break
            if row is None:
                row = properties.add_map_setting(project, constants.MAP_HEIGHT)
                row.enabled = True
                added += 1
            else:
                if str(getattr(row, "material_resolve_state", "") or "") == constants.MATERIAL_RESOLVE_MISSING:
                    row.enabled = bool(getattr(row, "material_previous_enabled", True))
                updated += 1
            _apply_row_metadata(
                row,
                origin=origin,
                binding_key=binding_key,
                resolve=resolve,
                data_type=constants.MATERIAL_DATA_VALUE,
                node_ids=meta.get("node_ids") or [],
                messages=meta.get("messages") or [],
            )
            continue

        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            row = _find_row_by_binding(project, binding_key)
            if row is None:
                row = properties.add_map_setting(project, constants.MAP_MATERIAL)
                row.enabled = True
                row.material_channel = constants.MATERIAL_CHANNEL_ALBEDO
                row.output_suffix = naming.sanitize_token(meta.get("display_name") or "Custom") if hasattr(naming, "sanitize_token") else str(meta.get("display_name") or "Custom")
                added += 1
            else:
                if str(getattr(row, "material_resolve_state", "") or "") == constants.MATERIAL_RESOLVE_MISSING:
                    row.enabled = bool(getattr(row, "material_previous_enabled", True))
                updated += 1
            row.material_custom_name = str(meta.get("display_name") or "Custom")
            if meta.get("vector_encoding"):
                row.material_vector_encoding = meta["vector_encoding"]
            _apply_row_metadata(
                row,
                origin=origin,
                binding_key=binding_key,
                resolve=resolve,
                data_type=str(meta.get("data_type") or constants.MATERIAL_DATA_COLOR),
                node_ids=meta.get("node_ids") or [],
                messages=meta.get("messages") or [],
            )
            continue

        # Standard material channel.
        channel = constants.CAPTURE_BINDING_TO_CHANNEL.get(binding_key)
        if not channel:
            continue
        row = _find_row_by_binding(project, binding_key)
        if row is None:
            row = _find_manual_standard_row(project, channel)
            if row is not None:
                # Bind without changing origin to auto-managed.
                _apply_row_metadata(
                    row,
                    origin=constants.MATERIAL_ORIGIN_MANUAL,
                    binding_key=binding_key,
                    resolve=resolve,
                    data_type=str(meta.get("data_type") or constants.MATERIAL_DATA_VALUE),
                    node_ids=meta.get("node_ids") or [],
                    messages=meta.get("messages") or [],
                )
                updated += 1
                continue
            row = properties.add_map_setting(project, constants.MAP_MATERIAL)
            row.material_channel = channel
            row.enabled = True
            effective = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel, constants.MAP_MATERIAL_ALBEDO)
            row.output_suffix = naming.resolved_map_file_label(effective)
            added += 1
            created_row = True
        else:
            if str(getattr(row, "material_resolve_state", "") or "") == constants.MATERIAL_RESOLVE_MISSING:
                row.enabled = bool(getattr(row, "material_previous_enabled", True))
            updated += 1
            created_row = False
        # Preserve MANUAL only on a row that was already there. add_map_setting stamps
        # every fresh row MANUAL, and reading that back made auto-created standard rows
        # MANUAL too: deleting one recorded no suppression (on_map_removed returns early
        # for MANUAL) so the next debounced sync recreated it, and deleting the capture
        # node left the row enabled, because both cleanup loops below skip MANUAL. The
        # NORMAL/HEIGHT/CUSTOM branches always passed origin through; only this one did not.
        origin_out = origin
        if not created_row and str(getattr(row, "material_origin", "") or "") == constants.MATERIAL_ORIGIN_MANUAL:
            origin_out = constants.MATERIAL_ORIGIN_MANUAL
        _apply_row_metadata(
            row,
            origin=origin_out,
            binding_key=binding_key,
            resolve=resolve,
            data_type=str(meta.get("data_type") or constants.MATERIAL_DATA_VALUE),
            node_ids=meta.get("node_ids") or [],
            messages=meta.get("messages") or [],
        )

    # Missing auto rows whose binding disappeared.
    for item in list(getattr(project, "maps", []) or []):
        if getattr(item, "is_add_phantom", False):
            continue
        origin = str(getattr(item, "material_origin", "") or "")
        if origin not in {constants.MATERIAL_ORIGIN_CAPTURE, constants.MATERIAL_ORIGIN_CUSTOM}:
            continue
        binding_key = str(getattr(item, "material_binding_key", "") or "").strip()
        if not binding_key or binding_key in present_keys:
            continue
        if str(getattr(item, "material_resolve_state", "") or "") != constants.MATERIAL_RESOLVE_MISSING:
            item.material_previous_enabled = bool(getattr(item, "enabled", False))
            item.enabled = False
            item.material_resolve_state = constants.MATERIAL_RESOLVE_MISSING
            missing += 1

    return {"added": added, "updated": updated, "missing": missing}


def on_map_removed(project, binding_key: str, origin: str) -> None:
    """Record suppression when the user deletes an auto-created row while its source remains."""
    if origin not in {constants.MATERIAL_ORIGIN_CAPTURE, constants.MATERIAL_ORIGIN_CUSTOM}:
        return
    if not binding_key:
        return
    _add_suppression(project, binding_key)


def register():
    pass


def unregister():
    if bpy.app.timers.is_registered(_timer_poll):
        bpy.app.timers.unregister(_timer_poll)
