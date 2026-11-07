from __future__ import annotations

import bpy

from . import constants, properties, sidebar_icons
from .ui_group_editor import _draw_custom_cage_controls, _draw_paint_projection_section


def _draw_cage_row(
    layout,
    label: str,
    *,
    slider_data,
    slider_prop_name: str,
    slider_text: str,
    toggle_data=None,
    toggle_prop_name: str | None = None,
    enabled: bool = True,
    trailing=None,
) -> None:
    """One overlay row: right-aligned label in a 40% column (the width of
    Blender's property-split label column), then a checkbox (or a blank icon where a
    row has none), the slider with its text inside, and a trailing column that is
    always two icon slots wide. ``trailing`` draws that column.
    """
    outer = layout.row(align=True)
    # An explicit 40% split instead of the panel's property split: Blender only
    # right-aligns a row heading when the row starts with a checkbox, so the
    # rows without a checkbox came out left-aligned under the heading form.
    outer.use_property_split = False
    outer.use_property_decorate = False
    split = outer.split(factor=0.4, align=True)
    label_row = split.row(align=True)
    label_row.alignment = "RIGHT"
    label_row.label(text=label)
    row = split.row(align=True)
    if toggle_data is not None and toggle_prop_name:
        row.prop(toggle_data, toggle_prop_name, text="")
    else:
        row.label(text="", icon="BLANK1")
    slider_row = row.row(align=True)
    slider_row.enabled = enabled
    # Split off again here or the slider text would be pulled out into a label.
    slider_row.use_property_split = False
    slider_row.prop(slider_data, slider_prop_name, text=slider_text, slider=True)
    trailing_row = row.row(align=True)
    trailing_row.enabled = enabled
    trailing_row.use_property_split = False
    # Fixed width for every row's trailing column; two icon buttons fit exactly,
    # so a lone swatch or toggle packed to the right ends flush with them.
    trailing_row.ui_units_x = 2.0
    if trailing is not None:
        trailing(trailing_row)
    else:
        trailing_row.label(text="", icon="BLANK1")
        trailing_row.label(text="", icon="BLANK1")


def _two_icon_buttons(trailing_row, first: tuple[str, str], second: tuple[str, str]) -> None:
    """Estimate and reset, equal width, touching each other and the row's right edge.

    A 50/50 split left each icon in a slot wider than the button, so a gap opened
    between them and again between reset and the panel edge.
    """
    trailing_row.row(align=True).operator(first[0], text="", icon=first[1])
    trailing_row.row(align=True).operator(second[0], text="", icon=second[1])


def _icon_sized(trailing_row, *, units: float = 1.0):
    """The right half of the trailing column: a swatch or toggle drawn there ends
    flush with the reset button of the offset rows above. A right-packed
    ``ui_units_x`` sub-row did not do it: a colour swatch reserves ~7 px more
    than an icon button and pushed its slider short; an even split does not."""
    halves = trailing_row.split(factor=0.5, align=True)
    halves.row(align=True).label(text="")
    return halves.row(align=True)


def _draw_toggle_slider_color_row(
    layout,
    data,
    bool_prop_name: str,
    slider_prop_name: str,
    label: str,
    *,
    color_prop_name: str | None,
    slider_text: str = "",
    icon_toggle_prop_name: str | None = None,
    icon_toggle_icon: str = "FIXED_SIZE",
) -> None:
    enabled = bool(getattr(data, bool_prop_name, False))

    def trailing(trailing_row):
        if color_prop_name:
            # A colour swatch carries its own inner padding, so at 1.0 unit it
            # took 7 px more than an icon button and pushed its slider short.
            _icon_sized(trailing_row).prop(data, color_prop_name, text="")
        elif icon_toggle_prop_name:
            # Constant Screen Size, like the Normals overlay's button next to its Size slider.
            _icon_sized(trailing_row).prop(data, icon_toggle_prop_name, text="", icon=icon_toggle_icon, toggle=True)
        else:
            trailing_row.label(text="")

    _draw_cage_row(
        layout,
        label,
        slider_data=data,
        slider_prop_name=slider_prop_name,
        slider_text=slider_text,
        toggle_data=data,
        toggle_prop_name=bool_prop_name,
        enabled=enabled,
        trailing=trailing,
    )


def _draw_offset_slider_row(layout, data, prop_name: str, label: str, estimate_op: str, reset_op: str) -> None:
    row = layout.row(align=True)
    row.use_property_split = False
    row.use_property_decorate = False
    split = row.split(factor=0.46, align=True)
    label_row = split.row(align=True)
    label_row.alignment = "LEFT"
    label_row.label(text=label)
    value_row = split.row(align=True)
    value_row.prop(data, prop_name, text="", slider=True)
    buttons = value_row.row(align=True)
    buttons.ui_units_x = 2.0
    _two_icon_buttons(buttons, (estimate_op, "DRIVER_DISTANCE"), (reset_op, "LOOP_BACK"))


def cage_offset_row_label(scope: str, group, slot, pairs) -> str:
    """Left-side title for the offset slider. The subject follows the scope."""
    del slot
    if scope == constants.CAGE_SCOPE_SELECTED:
        count = len(pairs)
        subject = f"Selected ({count})" if count > 1 else "Selected"
    elif scope == constants.CAGE_SCOPE_TEXTURE_SET:
        subject = (str(getattr(group, "texture_set_name", "") or "").strip() or "Texture Set")
    elif scope == constants.CAGE_SCOPE_GLOBAL:
        subject = "Global"
    else:
        subject = str(getattr(group, "name", "") or "").strip() or "Bake Group"
    text = f"Cage Offset - {subject}"
    if properties.cage_offset_scope_mixed(pairs):
        text += " (mixed)"
    return text


def draw_cage_offset_controls(layout, group) -> None:
    """One Offset slider: the FINAL cage distance of what the Apply To scope covers
    (properties: "Cage offset (Distance Based)"), with a range sized to the value and the
    mesh so it can be placed to fractions of a millimetre."""
    if group is None or group.cage_mode != constants.CAGE_MODE_DISTANCE:
        return

    context = getattr(bpy, "context", None)
    _project, target_group, target_slot, scope, pairs = properties.cage_offset_scope_from_context(context)
    scene = getattr(context, "scene", None) if context is not None else None
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    ui_state = properties.scene_ui_state(settings) if settings is not None else None
    if ui_state is None or target_group is None or not pairs:
        # No scene UI state (headless draw, tests): the group offset directly.
        _draw_offset_slider_row(
            layout, group, "cage_offset", "Cage Offset",
            "master_baker.estimate_scoped_cage_offset", "master_baker.reset_scoped_cage_offset",
        )
        return
    prop_name = properties.cage_offset_proxy_name(
        properties.cage_final_offset(target_group, target_slot),
        properties.cage_low_size(target_slot),
    )
    _draw_offset_slider_row(
        layout, ui_state, prop_name, cage_offset_row_label(scope, target_group, target_slot, pairs),
        "master_baker.estimate_scoped_cage_offset", "master_baker.reset_scoped_cage_offset",
    )


def draw_rear_distance_control(layout, group) -> None:
    """Rear Distance: how deep behind the low the projection may reach. Every cage mode.

    Same row shape as the Cage Offset row (left label in a 0.46 column, value, two-slot
    trailing column) so the label, the field and the reset button line up with it; a
    plain split-layout prop right-aligned its label and ran the field to the edge.
    """
    if group is None:
        return
    rear = float(getattr(group, "projection_rear_distance", 0.0) or 0.0)
    row = layout.row(align=True)
    row.use_property_split = False
    row.use_property_decorate = False
    split = row.split(factor=0.46, align=True)
    label_row = split.row(align=True)
    label_row.alignment = "LEFT"
    label_row.label(text="Rear Distance - Auto" if rear <= 0.0 else "Rear Distance")
    value_row = split.row(align=True)
    value_row.prop(group, "projection_rear_distance", text="")
    buttons = value_row.row(align=True)
    buttons.ui_units_x = 2.0
    _icon_sized(buttons).operator("master_baker.reset_rear_distance", text="", icon="LOOP_BACK")


def draw_cage_viewport_overlay_controls(layout, overlay_state) -> None:
    _draw_toggle_slider_color_row(
        layout,
        overlay_state,
        "show_cage_surface",
        "cage_surface_opacity",
        "Surface",
        color_prop_name="cage_surface_color",
        slider_text="Opacity",
    )
    _draw_toggle_slider_color_row(
        layout,
        overlay_state,
        "show_cage_wireframe",
        "cage_wireframe_opacity",
        "Wireframe",
        color_prop_name="cage_wireframe_color",
        slider_text="Opacity",
    )


def draw_skew_needle_controls(layout, overlay_state) -> None:
    """Skew needle size, shown from the arrow beside Paint Skew."""
    _draw_toggle_slider_color_row(
        layout,
        overlay_state,
        "show_skew_debug",
        "skew_debug_length",
        "Skew Needles",
        color_prop_name=None,
        slider_text="Size",
        icon_toggle_prop_name="skew_debug_constant_screen_size",
    )


def _draw_cage_header_toggles(header, overlay_state, group) -> None:
    """Icon toggles in the Cage header: each button, then its settings arrow.

    Cage visibility opens the surface/wireframe overlay popover. Coverage opens the
    inside/outside color popover. A short gap separates the two pairs.
    """
    is_cage_visible = bool(getattr(overlay_state, "show_cage_overlay", False))
    cage_pair = header.row(align=True)
    cage_pair.operator(
        "master_baker.toggle_cage_overlay",
        text="",
        icon_value=sidebar_icons.get_icon_value("cage_ui"),
        depress=is_cage_visible,
    )
    cage_pair.popover("MASTER_BAKER_PT_cage_viewport_overlays", text="", icon="DOWNARROW_HLT")
    # The two pairs are separate controls. A separator keeps them from reading as one strip.
    header.separator(factor=0.8)

    coverage_target = group if group is not None else overlay_state
    coverage_prop = "show_cage_coverage" if group is not None else "show_error_heatmap"
    coverage_pair = header.row(align=True)
    if coverage_target is not None:
        coverage_pair.prop(
            coverage_target,
            coverage_prop,
            text="",
            toggle=True,
            icon_value=sidebar_icons.get_icon_value("cage_coverage"),
        )
    coverage_pair.popover("MASTER_BAKER_PT_cage_coverage_settings", text="", icon="DOWNARROW_HLT")


def draw_sidebar_viewport_controls(layout, settings, project, group):
    ui_state = properties.scene_ui_state(settings)
    overlay_state = properties.overlay_settings_state(settings)
    viewport_box = layout.box()

    # Scope selector at the very top of the cage panel: choose whether an edit to a
    # cage setting below reaches only the active bake group, its whole texture set,
    # or every group in the project. Session-only (resets to Bake Group).
    scope_col = viewport_box.column(align=True)
    # Drawn as set_ui_enum operators rather than prop(expand=True) so the Bake
    # Group / Texture Set entries can use their own custom icons (prop_enum can't take a
    # custom icon_value). Global keeps the built-in globe. The operator reports each
    # enum item's own description; wm.context_set_enum only says "Set a context value".
    scope_row = scope_col.row(align=True)
    scope_row.scale_y = 1.1
    current_scope = str(getattr(ui_state, "cage_settings_scope", "") or "")
    # Selected shows how many groups own a selected low mesh, so it is obvious
    # what the next edit touches (the active group is always edited itself).
    selected_count = 0
    if project is not None:
        try:
            import bpy

            selected_count = len(properties.groups_owning_selected_low_meshes(
                project, getattr(bpy.context, "selected_objects", None) or ()
            ))
        except Exception:
            selected_count = 0
    selected_label = f"Selected ({selected_count})" if selected_count else "Selected"
    for value, label, icon_name, builtin_icon in (
        (constants.CAGE_SCOPE_BAKE_GROUP, "Bake Group", "bake_group", "NONE"),
        (constants.CAGE_SCOPE_SELECTED, selected_label, "", "RESTRICT_SELECT_OFF"),
        (constants.CAGE_SCOPE_TEXTURE_SET, "Texture Set", "texture_set", "NONE"),
        (constants.CAGE_SCOPE_GLOBAL, "Global", "", "WORLD"),
    ):
        icon_value = sidebar_icons.get_icon_value(icon_name) if icon_name else 0
        set_scope = scope_row.operator(
            "master_baker.set_ui_enum",
            text=label,
            icon=builtin_icon if not icon_value else "NONE",
            icon_value=icon_value,
            depress=(current_scope == value),
        )
        set_scope.data_path = "scene.fyr_baker_settings.ui_state.cage_settings_scope"
        set_scope.value = value

    # Cage visibility is global; coverage stays per bake group so it follows the
    # groups the user enabled rather than the active selection. The toggles stay
    # on a plain row: the Cage tab is already the section, so this is not a
    # second collapsible menu.
    sections = viewport_box.column(align=False)
    sections.enabled = group is not None
    toggle_row = sections.row(align=True)
    toggle_row.alignment = "RIGHT"
    _draw_cage_header_toggles(toggle_row, overlay_state, group)
    if group is not None:
        mode_row = sections.row(align=True)
        mode_row.prop(group, "cage_mode", expand=True)
        flags = sections.row(align=True)
        flags.prop(group, "average_normals", text="Smooth Cage")
        # Match By Mesh Name had a property, a working backend and no way to click it:
        # its only draw call lived in ui_group_editor.draw_group_editor(), which nothing
        # calls. It sits beside Smooth Cage because both shape the projection.
        flags.prop(group, "match_by_isolation")
        # Split layout from here down so labels and values take the theme's
        # high-contrast text. Without it these rows sit muted on charcoal and read
        # as disabled -- a tester asked for "the numbers in white" while actively
        # editing Group Offset, so they were never disabled, just hard to read.
        # The mode enum and the two flags above keep full-width buttons.
        sections.use_property_split = True
        sections.use_property_decorate = False
        if group.cage_mode == constants.CAGE_MODE_CUSTOM:
            _draw_custom_cage_controls(sections, group)
            draw_rear_distance_control(sections, group)
        elif group.cage_mode == constants.CAGE_MODE_AUTOMATIC:
            draw_rear_distance_control(sections, group)
            _draw_paint_projection_section(sections, group)
        else:
            draw_cage_offset_controls(sections, group)
            draw_rear_distance_control(sections, group)
            _draw_paint_projection_section(sections, group)
    # Skew needle size opens from the arrow beside Paint Skew.
