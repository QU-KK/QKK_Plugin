"""Developer-mode A/B compare: high+source material vs low+baked preview.

Show-on-low never mutates highs. This tool is an explicit compare mode that
temporarily swaps role visibility so Glow can flip between the procedural high
and the baked low without hunting outliner eyes.
"""

from __future__ import annotations

import json

from . import constants, project_structure, properties

AB_SIDE_HIGH = "HIGH"
AB_SIDE_LOW = "LOW"


def material_ab_compare_is_active(session_state) -> bool:
    if session_state is None:
        return False
    return bool(getattr(session_state, "material_ab_compare_active", False))


def material_ab_compare_side(session_state) -> str:
    if session_state is None:
        return ""
    side = str(getattr(session_state, "material_ab_compare_side", "") or "").strip().upper()
    return side if side in {AB_SIDE_HIGH, AB_SIDE_LOW} else ""


def restore_material_ab_compare_visibility(session_state) -> None:
    """Unhide whatever an active A/B side hid, without touching the rest of the state."""
    if session_state is None:
        return
    raw = str(getattr(session_state, "material_ab_compare_restore_visibility", "") or "")
    if raw:
        _restore_visibility(raw)


def clear_material_ab_compare_state(session_state) -> None:
    if session_state is None:
        return
    session_state.material_ab_compare_active = False
    session_state.material_ab_compare_side = ""
    session_state.material_ab_compare_project_name = ""
    session_state.material_ab_compare_restore_visibility = ""
    session_state.material_ab_compare_had_preview = False


def _iter_role_meshes(project, role_attr: str):
    for group in getattr(project, "groups", []) or []:
        role = (
            constants.OBJECT_ROLE_HIGH
            if role_attr == "high_meshes"
            else constants.OBJECT_ROLE_LOW
        )
        for obj in project_structure.group_role_targets(group, role) or []:
            if obj is not None:
                yield obj


def _capture_visibility(project) -> str:
    entries = []
    seen = set()
    for role_attr in ("high_meshes", "low_meshes"):
        for obj in _iter_role_meshes(project, role_attr):
            name = str(getattr(obj, "name", "") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            entries.append(
                {
                    "name": name,
                    "hide_get": bool(obj.hide_get()),
                    "hide_viewport": bool(getattr(obj, "hide_viewport", False)),
                }
            )
    return json.dumps(entries)


def _restore_visibility(raw: str) -> None:
    text = str(raw or "").strip()
    if not text:
        return
    try:
        entries = json.loads(text)
    except json.JSONDecodeError:
        return
    import bpy

    for entry in entries or []:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        try:
            obj.hide_viewport = bool(entry.get("hide_viewport", False))
        except Exception:
            pass
        try:
            obj.hide_set(bool(entry.get("hide_get", False)))
        except Exception:
            pass


def _set_role_visibility(project, *, show_high: bool, show_low: bool) -> None:
    for obj in _iter_role_meshes(project, "high_meshes"):
        try:
            obj.hide_set(not show_high)
        except Exception:
            pass
    for obj in _iter_role_meshes(project, "low_meshes"):
        try:
            obj.hide_set(not show_low)
        except Exception:
            pass


def _ensure_material_preview_on_low(
    context,
    project,
    *,
    activate_preview_on_low_fn,
    resolve_map_source_fn,
    active_group_name_fn,
) -> bool:
    """Ensure a baked Material (albedo preferred) preview is applied on lows."""
    settings = getattr(context.scene, "fyr_baker_settings", None)
    session = properties.preview_session_state(settings) if settings is not None else None
    if session is not None and bool(getattr(session, "preview_on_low_active", False)):
        map_type = str(getattr(session, "preview_on_low_map_type", "") or "")
        if "MATERIAL" in map_type.upper():
            return True

    # Prefer albedo / first MATERIAL output.
    preferred = None
    for target in getattr(project, "latest_outputs", []) or []:
        map_type = str(getattr(target, "map_type", "") or "").upper()
        if map_type in {"MATERIAL_ALBEDO", "MATERIAL"} or map_type.startswith("MATERIAL"):
            preferred = target
            if "ALBEDO" in map_type or str(getattr(target, "output_suffix", "") or "") in {
                "",
                "Material",
                "_Material",
            }:
                break
    if preferred is None:
        return False

    group_name = str(active_group_name_fn(project) or "") if active_group_name_fn else ""
    source = resolve_map_source_fn(
        project,
        map_type=str(getattr(preferred, "map_type", "") or "MATERIAL"),
        group_name=group_name,
        map_uuid=str(getattr(preferred, "map_uuid", "") or ""),
        output_suffix=str(getattr(preferred, "output_suffix", "") or ""),
        scene=getattr(context, "scene", None),
    )
    if not source:
        return False
    activate_preview_on_low_fn(context, project, source)
    return True


def apply_material_ab_side(project, side: str) -> None:
    side = str(side or "").strip().upper()
    if side == AB_SIDE_HIGH:
        _set_role_visibility(project, show_high=True, show_low=False)
    elif side == AB_SIDE_LOW:
        _set_role_visibility(project, show_high=False, show_low=True)


def cycle_material_ab_compare(
    context,
    project,
    *,
    activate_preview_on_low_fn,
    resolve_map_source_fn,
    active_group_name_fn,
    deactivate_preview_on_low_fn,
    suppress_bg_prepare_fn,
) -> tuple[str, str]:
    """Cycle Off → High → Low → Off. Returns (status_message, side_or_empty)."""
    if suppress_bg_prepare_fn is not None:
        # Visibility swaps on multi-million highs tag Object geometry/xform updates;
        # keep speculative prepare suppressed for the whole A/B interaction.
        suppress_bg_prepare_fn(5.0)

    settings = getattr(context.scene, "fyr_baker_settings", None)
    session = properties.preview_session_state(settings) if settings is not None else None
    if session is None:
        return "A/B compare unavailable", ""

    project_name = str(getattr(project, "name", "") or "")
    active = material_ab_compare_is_active(session)
    side = material_ab_compare_side(session)

    if not active:
        session.material_ab_compare_restore_visibility = _capture_visibility(project)
        session.material_ab_compare_had_preview = bool(
            getattr(session, "preview_on_low_active", False)
            or getattr(session, "preview_pbr_on_low_active", False)
        )
        session.material_ab_compare_active = True
        session.material_ab_compare_project_name = project_name
        session.material_ab_compare_side = AB_SIDE_HIGH
        _ensure_material_preview_on_low(
            context,
            project,
            activate_preview_on_low_fn=activate_preview_on_low_fn,
            resolve_map_source_fn=resolve_map_source_fn,
            active_group_name_fn=active_group_name_fn,
        )
        apply_material_ab_side(project, AB_SIDE_HIGH)
        return "A/B: High (source material)", AB_SIDE_HIGH

    if side == AB_SIDE_HIGH:
        session.material_ab_compare_side = AB_SIDE_LOW
        _ensure_material_preview_on_low(
            context,
            project,
            activate_preview_on_low_fn=activate_preview_on_low_fn,
            resolve_map_source_fn=resolve_map_source_fn,
            active_group_name_fn=active_group_name_fn,
        )
        apply_material_ab_side(project, AB_SIDE_LOW)
        return "A/B: Low (baked)", AB_SIDE_LOW

    # LOW → exit
    restore = str(getattr(session, "material_ab_compare_restore_visibility", "") or "")
    had_preview = bool(getattr(session, "material_ab_compare_had_preview", False))
    clear_material_ab_compare_state(session)
    _restore_visibility(restore)
    if not had_preview and deactivate_preview_on_low_fn is not None:
        try:
            deactivate_preview_on_low_fn(context)
        except Exception:
            pass
    return "A/B compare off", ""
