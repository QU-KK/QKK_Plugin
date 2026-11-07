from __future__ import annotations

from typing import Any
from types import SimpleNamespace
import uuid as _uuid

from . import constants


def _set_attr(target: Any, name: str, value: Any, *fallback_names: str) -> None:
    for candidate in (name, *fallback_names):
        if hasattr(target, candidate):
            setattr(target, candidate, value)
            return


def _iter_map_items(project: Any) -> list[Any]:
    maps = getattr(project, "maps", None)
    if maps is None:
        return []
    return list(maps)


def _apply_row_defaults(project: Any, item: Any, map_type: str) -> None:
    """Give a freshly created row the same defaults ``add_map`` would give it.

    ``properties.apply_default_map_setting_values`` is the single definition of
    what a new row looks like, and it covers fields this module never knew about
    (denoising, AO distance, curvature response). It lives in ``properties``,
    which needs ``bpy``, so it is imported late and the inline fallback below
    keeps this module importable -- and unit-testable -- outside Blender.
    """
    try:
        from . import properties as _properties
    except Exception:
        _properties = None
    applier = getattr(_properties, "apply_default_map_setting_values", None)
    if applier is not None:
        try:
            applier(project, item, enabled=True)
            return
        except Exception:
            pass
    item.map_type = map_type
    item.enabled = True
    item.samples = constants.default_samples_for_map(map_type)
    item.ao_cavity_weight = constants.default_ao_cavity_weight_for_map(map_type)
    item.normal_format = constants.default_normal_format_for_map(map_type)
    item.flip_green = item.normal_format == constants.NORMAL_FORMAT_DIRECTX
    item.denoising_enabled = constants.default_denoising_for_map(map_type)


def _ensure_map_setting(project: Any, map_type: str):
    for item in _iter_map_items(project):
        if getattr(item, "map_type", "") == map_type:
            return item

    maps = getattr(project, "maps", None)
    if maps is None:
        raise ValueError("Project does not expose a maps collection")

    if hasattr(maps, "add"):
        item = maps.add()
    else:
        item = SimpleNamespace()
        maps.append(item)

    if not getattr(item, "uuid", ""):
        if hasattr(item, "ensure_uuid"):
            item.ensure_uuid()
        else:
            item.uuid = str(_uuid.uuid4())
    item.map_type = map_type
    _apply_row_defaults(project, item, map_type)
    return item


def _configure_map_stack(project: Any, enabled_map_types: set[str]) -> None:
    """Enable exactly ``enabled_map_types`` and leave every other row's tuning alone.

    Sample counts come from ``default_samples_for_map`` and nowhere else. The
    retired presets carried hardcoded overrides (Unity Core asked for 16 AO rays
    against a 697 default, below MAP_LOW_SAMPLE_WARNING_THRESHOLD, so the preset
    tripped our own noisy-bake warning) and two of them -- Normal and Curvature --
    could not affect the result at all, since neither map reads a ray budget.
    Denoising is likewise left to the per-map default a new row is born with, so
    a preset never silently reverses a choice the artist made on an existing row.
    """
    for map_type in sorted(enabled_map_types):
        _ensure_map_setting(project, map_type)
    for map_item in _iter_map_items(project):
        map_type = getattr(map_item, "map_type", "")
        map_item.enabled = map_type in enabled_map_types
        if map_type in enabled_map_types:
            map_item.samples = constants.default_samples_for_map(map_type)


def apply_map_stack_preset(project: Any, preset: str) -> str:
    normalized = str(preset or "").strip().upper()
    normalized = constants.LEGACY_MAP_STACK_ALIASES.get(normalized, normalized)

    if normalized == constants.MAP_STACK_TEXTURING:
        _configure_map_stack(project, set(constants.MAP_STACK_TEXTURING_MAPS))
        return "Texturing Mesh Maps"

    if normalized == constants.MAP_STACK_TEXTURING_PLUS:
        _configure_map_stack(
            project,
            set(constants.MAP_STACK_TEXTURING_MAPS) | set(constants.MAP_STACK_DETAIL_MASK_MAPS),
        )
        return "Texturing Mesh Maps+"

    if normalized == constants.MAP_STACK_DETAIL_MASKS:
        _configure_map_stack(project, set(constants.MAP_STACK_DETAIL_MASK_MAPS))
        return "Detail Masks"

    if normalized == constants.MAP_STACK_LIGHTING_BAKE:
        _configure_map_stack(
            project,
            {
                constants.MAP_SCENE_LIGHTING,
                constants.MAP_BENT_NORMAL,
                constants.MAP_ENV_LIGHT,
                constants.MAP_AO,
            },
        )
        return "Lighting Bake"

    if normalized == constants.MAP_STACK_NORMAL_ONLY:
        _configure_map_stack(project, {constants.MAP_NORMAL})
        return "Normal Only"

    if normalized == constants.MAP_STACK_AO_ONLY:
        _configure_map_stack(project, {constants.MAP_AO})
        return "AO Only"

    if normalized == constants.MAP_STACK_CUSTOM:
        return "Custom"

    raise ValueError(f"Unsupported map stack preset: {preset!r}")
