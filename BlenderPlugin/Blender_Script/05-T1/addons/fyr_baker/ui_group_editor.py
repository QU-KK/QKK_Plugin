from __future__ import annotations

import bpy

from . import bake_backends, constants, properties, runtime, sidebar_icons
from .ui_utils import _hide_icon_for_objects, _icon_kwargs, _ui_list_rows


def _draw_undo_removed_role_slot(layout, role: str) -> None:
    """Restore for the mesh this list just dropped.

    Scoped by role so only the list the mesh came out of offers it -- the low and
    high lists are drawn side by side, and one shared row would read as ambiguous.
    """
    label = runtime.removed_item_undo_label(runtime.STASH_KIND_ROLE_SLOT, role=str(role))
    if not label:
        return
    layout.row(align=True).operator("master_baker.restore_removed_item", text=label, icon="LOOP_BACK")


def _draw_group_role_slot_list(layout, group, *, role: str, list_id: str, rows: int = 3) -> None:
    icon_name = "high_poly" if role == constants.OBJECT_ROLE_HIGH else "low_poly"
    slot_prop = "high_meshes" if role == constants.OBJECT_ROLE_HIGH else "low_meshes"
    index_prop = "high_mesh_index" if role == constants.OBJECT_ROLE_HIGH else "low_mesh_index"
    role_state = properties.group_role_assignments_state(group)
    slot_items = list(getattr(role_state, slot_prop, []))
    role_objects = [getattr(slot, "object_ref", None) for slot in slot_items if getattr(slot, "object_ref", None) is not None]
    has_role_objects = bool(role_objects)
    use_low_as_high = role == constants.OBJECT_ROLE_HIGH and properties.group_uses_low_as_high(group)

    list_box = layout.box()
    header_row = list_box.row(align=True)
    header_row.label(text="", icon_value=sidebar_icons.get_icon_value(icon_name))
    header_row.label(text=f"Meshes ({len(slot_items)})")
    if role == constants.OBJECT_ROLE_HIGH:
        # "Use Low as High" never fit this header at any sidebar width tried (it rendered
        # as "Use Low as ..." even at 750 px, RC sweep 2026-08-29, finding 21). The short
        # label fits; the property's own name carries the full phrase in the tooltip.
        header_row.prop(group, "use_low_as_high", text="Use Low", toggle=True)
    # Hide / unhide EVERY mesh of this role, pinned to the header's right edge.
    header_hide = header_row.row(align=True)
    header_hide.alignment = "RIGHT"
    header_hide.enabled = has_role_objects and not use_low_as_high
    hide_all_role = header_hide.operator(
        "master_baker.toggle_group_role_visibility",
        text="",
        icon=_hide_icon_for_objects(role_objects),
        emboss=False,
    )
    hide_all_role.role = role
    contents = list_box.column()
    contents.enabled = not use_low_as_high
    # The active row lives on the group's own index: role-state sync copies the group's
    # index over the nested one on every read, so a list bound to the nested index
    # (arrow keys, ctrl-scroll) snapped back and Remove dropped the wrong mesh.
    index_owner = group if hasattr(group, index_prop) else role_state
    contents.template_list(
        "MASTER_BAKER_UL_object_slots",
        list_id,
        role_state,
        slot_prop,
        index_owner,
        index_prop,
        rows=_ui_list_rows(slot_items, max_rows=max(1, rows)),
    )

    row = contents.row(align=True)
    # The label names the ROLE, not the action. Sharing "Add Selected Meshes" with the
    # group-list button (which splits a selection by suffix) is how a tester put the
    # same low+high pair into both lists in turn and hit "Low and High assignments
    # contain the same mesh" -- each press did exactly what it said, just not what the
    # instruction "highlight both, then Add Selected Meshes" meant.
    add_role = row.operator(
        "master_baker.add_selected_to_role",
        text=f"Add as {role.title()}",
        icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
    )
    add_role.role = role
    remove_row = row.row(align=True)
    remove_row.enabled = bool(slot_items)
    remove_role = remove_row.operator("master_baker.clear_role_slot", text="", **_icon_kwargs("remove_group", "REMOVE"))
    remove_role.role = role
    select_row = row.row(align=True)
    select_row.enabled = has_role_objects
    select_role = select_row.operator("master_baker.select_group_role_objects", text="", icon="RESTRICT_SELECT_OFF")
    select_role.role = role
    # Visibility toggle moved to the list header (top-right).
    _draw_undo_removed_role_slot(contents, role)


def _draw_paint_projection_section(layout, group) -> None:
    """Paint Offset / Paint Skew launchers, their scalars and the live brush settings."""
    if not bake_backends.control_supported(
        bake_backends.CONTROL_SCOPE_GROUP,
        "paint_offset_image",
    ):
        return
    from . import paint_brush, paint_sampling

    paint_box = layout.box()
    paint_box.label(text="Offset and Skew", icon_value=sidebar_icons.get_icon_value("paint_offset"))

    in_offset_paint = paint_brush.session_owns(group, paint_brush.KIND_OFFSET)
    in_skew_paint = paint_brush.session_owns(group, paint_brush.KIND_SKEW)

    btn_row = paint_box.row(align=True)
    btn_row.scale_y = 1.2
    btn_row.operator(
        "master_baker.create_paint_offset_image",
        text="Exit Offset Paint" if in_offset_paint else "Paint Offset",
        depress=in_offset_paint,
        **(
            {"icon": "CANCEL"}
            if in_offset_paint
            else {"icon_value": sidebar_icons.get_icon_value("paint_offset")}
        ),
    )
    skew_pair = btn_row.row(align=True)
    # Paint Skew corrects toward the flat face normal in every cage mode (Painter / Marmoset),
    # so it is always available; the needle settings arrow sits beside it.
    skew_button = skew_pair.row(align=True)
    skew_button.operator(
        "master_baker.create_paint_skew_image",
        text="Exit Skew Paint" if in_skew_paint else "Paint Skew",
        depress=in_skew_paint,
        **(
            {"icon": "CANCEL"}
            if in_skew_paint
            else {"icon_value": sidebar_icons.get_icon_value("paint_skew")}
        ),
    )
    skew_settings = skew_pair.row(align=True)
    skew_settings.ui_units_x = 1.5
    skew_settings.popover("MASTER_BAKER_PT_skew_needle_settings", text="", icon="DOWNARROW_HLT")

    if in_offset_paint or in_skew_paint:
        # ID-property read, so it has to tolerate a scene stand-in that has no .get
        # (the UI-layout tests draw this panel against a stub scene).
        _scene_get = getattr(getattr(bpy.context, "scene", None), "get", None)
        isolated = bool(_scene_get("_fyr_paint_isolated")) if callable(_scene_get) else False
        isolate = paint_box.box().row()
        isolate.label(text="Isolate Painted Meshes", icon="RESTRICT_VIEW_ON" if isolated else "RESTRICT_VIEW_OFF")
        isolate.operator(
            "master_baker.toggle_paint_isolate",
            text="",
            icon="CHECKBOX_HLT" if isolated else "CHECKBOX_DEHLT",
            emboss=False,
        )
        paint_brush.draw_brush_sections(
            paint_box,
            bpy.context,
            paint_brush.KIND_OFFSET if in_offset_paint else paint_brush.KIND_SKEW,
            group,
        )
        return

    low_meshes = [
        getattr(slot, "object_ref", None)
        for slot in getattr(group, "low_meshes", []) or []
        if getattr(slot, "object_ref", None) is not None
    ]
    has_offset = getattr(group, "paint_offset_image", None) is not None or any(
        paint_sampling.has_paint_layer(getattr(obj, "data", None), paint_sampling.OFFSET_ATTRIBUTE)
        for obj in low_meshes
    )
    has_skew = getattr(group, "paint_skew_image", None) is not None or paint_sampling.has_skew_correction(group)
    if has_offset or has_skew:
        param_row = paint_box.row(align=True)
        if has_offset:
            param_row.prop(group, "paint_offset_scale", text="Offset Scale", slider=True)
        # Skew Amount scales the 1.0.x skew image only; the painted correction map is used
        # as painted.
        if getattr(group, "paint_skew_image", None) is not None:
            param_row.prop(group, "paint_skew", text="Skew Amount", slider=True)
        clear_row = paint_box.row(align=True)
        if has_offset:
            clear_offset = clear_row.operator("master_baker.clear_paint_image", text="Clear Offset", icon="TRASH")
            clear_offset.target = "OFFSET"
        if has_skew:
            clear_skew = clear_row.operator("master_baker.clear_paint_image", text="Clear Skew", icon="TRASH")
            clear_skew.target = "SKEW"


def _draw_custom_cage_controls(layout, group, *, include_edit_tools: bool = True) -> None:
    cage_row = layout.row(align=True)
    cage_row.prop(group, "custom_cage", text="Custom Cage")
    cage_row.operator("master_baker.set_custom_cage_from_selection", text="", icon="EYEDROPPER")
    if include_edit_tools and getattr(group, "custom_cage", None) is not None:
        custom_tools = layout.row(align=True)
        inflate = custom_tools.operator("master_baker.adjust_custom_cage_mesh", text="Inflate")
        inflate.delta = 0.005
        relax = custom_tools.operator("master_baker.adjust_custom_cage_mesh", text="Relax")
        relax.delta = -0.005
        smooth = custom_tools.operator("master_baker.smooth_custom_cage_mesh", text="Smooth")
        smooth.factor = 0.5
        smooth.iterations = 2
        clean = custom_tools.operator("master_baker.cleanup_custom_cage_spikes", text="Clean")
        clean.spike_ratio = 2.5
        clean.blend = 0.85


def draw_group_editor(layout, project, group):
    row = layout.row()
    row.template_list(
        "MASTER_BAKER_UL_groups",
        "",
        project,
        "groups",
        project,
        "active_group_index",
        rows=3,
    )
    column = row.column(align=True)
    column.operator("master_baker.add_group", text="", **_icon_kwargs("add_group", "ADD"))
    column.operator("master_baker.remove_group", text="", **_icon_kwargs("remove_group", "REMOVE"))
    column.separator()
    column.operator("master_baker.auto_group_selected_by_suffix", text="", icon="MODIFIER")

    if group is None:
        layout.label(text="Add a bake group to assign low/high/cage meshes.")
        return

    layout.prop(group, "ui_name")
    _ts_row = layout.row(align=True)
    _ts_row.label(text="Texture Set")
    from .ui import _draw_texture_set_menu_button
    _draw_texture_set_menu_button(_ts_row, group)
    mode_row = layout.row(align=True)
    mode_row.prop(group, "cage_mode", expand=True)
    projection_box = layout.box()
    projection_box.label(text="Projection")
    projection_row = projection_box.row(align=True)
    projection_row.prop(group, "average_normals", text="Smooth Cage")
    projection_row.prop(group, "match_by_isolation")
    id_box = layout.box()
    id_box.label(text="ID")
    id_box.prop(group, "id_collection_name", text="Collection")
    id_box.prop(group, "id_color_set_name", text="Color Set")
    if group.cage_mode == constants.CAGE_MODE_CUSTOM:
        _draw_custom_cage_controls(layout, group)
    elif group.cage_mode == constants.CAGE_MODE_AUTOMATIC:
        _draw_paint_projection_section(layout, group)
    else:
        layout.prop(group, "cage_offset", text="Bake Group Offset")
        active_low_slot = properties.peek_active_low_slot(group)
        if active_low_slot is not None and getattr(active_low_slot, "object_ref", None) is not None:
            local_box = layout.box()
            local_box.label(text=f"Active Low Mesh: {active_low_slot.object_ref.name}")
            local_box.prop(active_low_slot, "cage_offset_delta", text="Per-Mesh Offset")
            total_offset = max(0.0, float(group.cage_offset) + float(getattr(active_low_slot, "cage_offset_delta", 0.0)))
            local_box.label(text=f"Final Distance Offset: {total_offset:.4f}")
        _draw_paint_projection_section(layout, group)

    # One button that fills BOTH lists from a single selection, reading each mesh's own
    # suffix. This is what "highlight both, then add" is supposed to do; the per-role
    # buttons below stay for meshes whose names can't decide it.
    auto_split = layout.row(align=True)
    auto_split.operator(
        "master_baker.add_selected_split_by_role",
        text="Add Selected (Auto Low/High)",
        icon_value=sidebar_icons.get_icon_value("add_selected_mesh"),
    )

    split = layout.split(factor=0.5)
    low_col = split.column()
    _draw_group_role_slot_list(low_col, group, role=constants.OBJECT_ROLE_LOW, list_id="low")

    high_col = split.column()
    _draw_group_role_slot_list(high_col, group, role=constants.OBJECT_ROLE_HIGH, list_id="high")
    cage_row = high_col.row(align=True)
    if group.cage_mode in {constants.CAGE_MODE_DISTANCE, constants.CAGE_MODE_AUTOMATIC}:
        cage_row.operator("master_baker.create_custom_cage_from_low", text="Convert", icon="ADD")
    if group.cage_mode == constants.CAGE_MODE_DISTANCE:
        cage_row.operator("master_baker.auto_fit_cage", text="Auto-Fit", icon="MOD_SHRINKWRAP")
    cage_row.prop(group, "custom_cage", text="")
    select_cage = cage_row.row(align=True)
    select_cage.enabled = getattr(group, "custom_cage", None) is not None
    select_cage.operator("master_baker.select_group_slot_object", text="", icon="RESTRICT_SELECT_OFF").role = constants.OBJECT_ROLE_CAGE
    hide_cage = cage_row.row(align=True)
    hide_cage.enabled = getattr(group, "custom_cage", None) is not None
    hide_cage.operator(
        "master_baker.toggle_group_slot_visibility",
        text="",
        icon=_hide_icon_for_objects([getattr(group, "custom_cage", None)]),
    ).role = constants.OBJECT_ROLE_CAGE

    auto_box = layout.box()
    auto_box.label(text="Auto Match")
    auto_row = auto_box.row(align=True)
    auto_row.operator("master_baker.auto_group_selected_by_suffix", text="Suffix", icon="SORTBYEXT")
    auto_row.operator("master_baker.auto_group_selected_by_collection", text="Collection", icon="OUTLINER_COLLECTION")
    auto_row.operator("master_baker.auto_group_selected_by_name_group", text="Name", icon="SORTALPHA")
