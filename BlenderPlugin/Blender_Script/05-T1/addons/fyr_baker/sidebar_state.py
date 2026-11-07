from __future__ import annotations

from . import constants


SECTION_IDS = tuple(item[0] for item in constants.SIDEBAR_SECTION_ITEMS)
DEFAULT_PRIMARY_SECTION = constants.SIDEBAR_MESHES
DEFAULT_SELECTED_SECTIONS = (DEFAULT_PRIMARY_SECTION,)
_LEGACY_SECTION_MAP = {
    # Setup was removed; its content lives in the hierarchy now, so any persisted
    # Setup/legacy selection falls back to the Cage section.
    constants.SIDEBAR_SETUP: constants.SIDEBAR_CAGE,
    "ACTIVE_GROUP": constants.SIDEBAR_CAGE,
    constants.SIDEBAR_BAKE: constants.SIDEBAR_CAGE,
    constants.SIDEBAR_DASHBOARD: constants.SIDEBAR_CAGE,
    "SESSION": constants.SIDEBAR_CAGE,
}


def normalize_section(section_id: str) -> str:
    section_id = _LEGACY_SECTION_MAP.get(section_id, section_id)
    if section_id in SECTION_IDS:
        return section_id
    return DEFAULT_PRIMARY_SECTION


def parse_selected_sections(value) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_values = [item.strip() for item in value.split(",") if item.strip()]
    else:
        raw_values = [str(item).strip() for item in value or [] if str(item).strip()]
    normalized_raw_values = [normalize_section(item) for item in raw_values]

    seen = set()
    selected: list[str] = []
    for section_id in SECTION_IDS:
        if section_id in normalized_raw_values and section_id not in seen:
            selected.append(section_id)
            seen.add(section_id)

    if not selected:
        return DEFAULT_SELECTED_SECTIONS
    return tuple(selected)


def serialize_selected_sections(sections) -> str:
    return ",".join(parse_selected_sections(sections))


def _ui_state_surface(settings):
    if settings is None:
        return None
    nested_state = getattr(settings, "ui_state", None)
    if nested_state is not None:
        return nested_state
    return settings


def get_selected_sections(settings) -> tuple[str, ...]:
    state = _ui_state_surface(settings)
    if state is None:
        return DEFAULT_SELECTED_SECTIONS
    return parse_selected_sections(getattr(state, "sidebar_selected_sections", ""))


def get_primary_section(settings) -> str:
    state = _ui_state_surface(settings)
    selected_sections = get_selected_sections(settings)
    primary_section = normalize_section(getattr(state, "sidebar_primary_section", ""))
    if primary_section not in selected_sections:
        return selected_sections[0]
    return primary_section


def _apply_state(settings, primary_section: str, selected_sections) -> tuple[str, tuple[str, ...]]:
    normalized_selected = parse_selected_sections(selected_sections)
    normalized_primary = normalize_section(primary_section)
    if normalized_primary not in normalized_selected:
        normalized_selected = parse_selected_sections((normalized_primary, *normalized_selected))

    state = _ui_state_surface(settings)
    if state is not None:
        state.sidebar_primary_section = normalized_primary
        state.sidebar_selected_sections = serialize_selected_sections(normalized_selected)

    return normalized_primary, normalized_selected


def normalize_preferences(settings) -> tuple[str, tuple[str, ...]]:
    return _apply_state(settings, get_primary_section(settings), get_selected_sections(settings))


def select_single(settings, section_id: str) -> tuple[str, tuple[str, ...]]:
    normalized_section = normalize_section(section_id)
    return _apply_state(settings, normalized_section, (normalized_section,))


def toggle_section(settings, section_id: str) -> tuple[str, tuple[str, ...]]:
    normalized_section = normalize_section(section_id)
    selected_sections = list(get_selected_sections(settings))
    current_primary = get_primary_section(settings)

    if normalized_section in selected_sections:
        if len(selected_sections) == 1:
            return _apply_state(settings, normalized_section, selected_sections)
        selected_sections.remove(normalized_section)
        if current_primary == normalized_section:
            current_primary = selected_sections[0]
        return _apply_state(settings, current_primary, selected_sections)

    selected_sections.append(normalized_section)
    return _apply_state(settings, normalized_section, selected_sections)


def handle_selector_click(settings, section_id: str, multi_select: bool = False) -> tuple[str, tuple[str, ...]]:
    if multi_select:
        return toggle_section(settings, section_id)
    return select_single(settings, section_id)


def ordered_visible_sections(settings) -> tuple[str, ...]:
    primary = get_primary_section(settings)
    selected = get_selected_sections(settings)
    ordered = [primary]
    ordered.extend(section_id for section_id in selected if section_id != primary)
    return tuple(ordered)
