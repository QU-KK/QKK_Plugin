from __future__ import annotations

import bpy

from . import sidebar_icons


def _object_hidden(obj) -> bool:
    if obj is None:
        return False
    hide_get = getattr(obj, "hide_get", None)
    if callable(hide_get):
        try:
            return bool(hide_get())
        except Exception:
            return False
    return False


def _hide_icon_for_objects(objects) -> str:
    targets = [obj for obj in objects if obj is not None]
    if targets and all(_object_hidden(obj) for obj in targets):
        return "HIDE_ON"
    return "HIDE_OFF"


def _builtin_icon_available(icon_name: str) -> bool:
    try:
        items = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
        return any(item.identifier == icon_name for item in items)
    except Exception:
        return False


def _icon_kwargs(custom_icon: str, fallback_icon: str = "NONE") -> dict[str, object]:
    icon_value = sidebar_icons.get_icon_value(custom_icon)
    if icon_value:
        return {"icon_value": icon_value}
    return {"icon": fallback_icon}


def duplicate_warning_icon_kwargs() -> dict[str, object]:
    """Exact-duplicate map-stack warning glyph (project PNG, then Blender built-ins)."""
    custom = _icon_kwargs("mapstack_duplicate_warning", "NONE")
    if custom.get("icon_value"):
        return custom
    for icon in ("STATUS_WARNING", "WARNING_LARGE"):
        if _builtin_icon_available(icon):
            return {"icon": icon}
    return {"icon": "NONE"}


def _ui_list_rows(items, *, empty_rows: int = 1, max_rows: int = 4) -> int:
    try:
        count = len(items)
    except Exception:
        count = int(items or 0)
    return max(1, min(max_rows, count if count > 0 else empty_rows))


def _begin_collapsible_section(
    layout, data, prop_name: str, title: str, *, icon="NONE", icon_value=0,
    header_popover: str | None = None, header_popover_icon="PREFERENCES",
    header_draw=None,
):
    """Collapsible section drawn with Blender's own layout panel, like every other
    collapsible in the addon: disclosure triangle on the left, then icon and title.
    *prop_name* names the section (and seeds the first open/closed state from the
    stored bool); Blender keeps the live state itself. Returns the body layout, or
    None while collapsed.

    *header_draw*, when set, receives the header layout after the title so a section
    can place compact header buttons beside a popover. Those stay visible while the
    body is collapsed.
    """
    icon_kwargs = {"icon_value": icon_value} if icon_value else ({"icon": icon} if icon != "NONE" else {})

    def _draw_header_extras(header) -> None:
        if header_draw is not None:
            header_draw(header)
        if header_popover:
            header.popover(header_popover, text="", icon=header_popover_icon)

    panel = getattr(layout, "panel", None)
    if callable(panel):
        header, body = panel(f"MASTER_BAKER_PT_section_{prop_name}", default_closed=not bool(getattr(data, prop_name, True)))
        header.label(text=title, **icon_kwargs)
        _draw_header_extras(header)
        return body
    # Hosts without layout panels: the old hand-rolled header.
    box = layout.box()
    header = box.row(align=True)
    header.scale_y = 0.85
    expanded = bool(getattr(data, prop_name, True))
    if icon_kwargs:
        header.label(text="", **icon_kwargs)
    toggle = header.operator(
        "master_baker.toggle_settings_section",
        text=title,
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    toggle.prop_name = prop_name
    _draw_header_extras(header)
    if not expanded:
        return None
    return box.column(align=False)
