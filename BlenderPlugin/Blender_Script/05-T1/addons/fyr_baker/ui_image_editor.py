from __future__ import annotations

from . import constants, export, external_handoff, output_thumbnails, preferences, properties, runtime, sidebar_icons, texture_reprojection, uv_snapshot
from .ui_map_settings import _map_stack_item_label
from .ui_utils import _icon_kwargs


def _map_thumbnail_icon_value(project, map_item, map_uuid: str) -> int:
    for out in getattr(project, "latest_outputs", []):
        if map_uuid == str(getattr(out, "map_uuid", "") or "").strip():
            return output_thumbnails.get_output_icon_value(getattr(out, "file_path", ""))
    map_type_upper = str(getattr(map_item, "map_type", "") or "").strip().upper()
    for out in getattr(project, "latest_outputs", []):
        if map_type_upper and map_type_upper == str(getattr(out, "map_type", "") or "").strip().upper():
            return output_thumbnails.get_output_icon_value(getattr(out, "file_path", ""))
    return 0


def draw_image_editor_controls(layout, context, project):
    settings = context.scene.fyr_baker_settings
    editor_state = properties.image_editor_state(settings)
    session_state = properties.preview_session_state(settings)
    active_group = properties.peek_active_group(project)
    active_map = properties.peek_active_map(project)
    active_group_name = str(getattr(active_group, "name", "") or "")
    # The N-panel's own resolver, not a second copy: Blender's Cycles material queue
    # outlives the backend process, and last_job_id is stamped by every prepare. Doing
    # it by hand here re-enabled Bake All and every per-map button (and hid Cancel)
    # while Blender was still baking material detail, so a click started a second bake
    # on top of the first.
    from .ui import _bake_state

    active_bake, bake_running, project_bake_running = _bake_state(project)
    stored_pbr_group = str(getattr(session_state, "preview_pbr_on_low_group_name", "") or "")
    preview_pbr_active = bool(
        getattr(session_state, "preview_pbr_on_low_active", False)
        and str(getattr(session_state, "preview_pbr_on_low_project_name", "") or "") == str(getattr(project, "name", "") or "")
        and (not stored_pbr_group or stored_pbr_group == active_group_name)
    )

    # --- Map Stack (click a row to load its output into the editor) ---
    map_stack_box = layout.box()
    map_stack_box.label(text="Map Stack", icon_value=sidebar_icons.get_icon_value("maps"))
    maps = [m for m in getattr(project, "maps", []) if not getattr(m, "is_add_phantom", False)]
    if not maps:
        map_stack_box.label(text="No maps in stack.", icon="INFO")
    else:
        active_map_uuid = properties.ensure_map_setting_uuid(active_map) if active_map is not None else ""
        stack_col = map_stack_box.column(align=True)
        for map_item in maps:
            map_uuid = properties.ensure_map_setting_uuid(map_item)
            is_active = bool(active_map_uuid) and active_map_uuid == map_uuid
            thumbnail_icon_value = _map_thumbnail_icon_value(project, map_item, map_uuid)
            icon_value = thumbnail_icon_value if thumbnail_icon_value else sidebar_icons.get_icon_value("texture_missing")
            enabled = bool(getattr(map_item, "enabled", False))

            item_label = _map_stack_item_label(project, map_item)
            effective_output_suffix = properties.effective_map_output_suffix(project, map_item) or ""
            same_type_count = sum(
                1
                for candidate in maps
                if str(getattr(candidate, "map_type", "") or "").strip().upper()
                == str(getattr(map_item, "map_type", "") or "").strip().upper()
            )
            if same_type_count > 1 and effective_output_suffix:
                item_label = f"{item_label} \u2192 {effective_output_suffix}"

            row = stack_col.row(align=True)
            row.active = enabled
            load_op = row.operator(
                "master_baker.load_output_image",
                text=item_label,
                icon_value=icon_value,
                depress=is_active,
            )
            load_op.map_type = getattr(map_item, "map_type", "")
            load_op.map_uuid = map_uuid

            action_sub = row.row(align=True)
            action_sub.enabled = enabled and not bake_running
            bake_op = action_sub.operator("master_baker.bake_map", text="", **_icon_kwargs("bake", "RENDER_STILL"))
            bake_op.map_type = getattr(map_item, "map_type", "")
            bake_op.map_uuid = map_uuid

            ext_row = row.row(align=True)
            ext_op = ext_row.operator("master_baker.external_edit_map_output", text="", icon="GREASEPENCIL")
            ext_op.map_type = getattr(map_item, "map_type", "")
            ext_op.map_uuid = map_uuid
            ext_op.group_name = active_group_name

    # --- Action row ---
    action_row = layout.row(align=True)
    if project_bake_running:
        cancel_row = action_row.row(align=True)
        cancel_row.alert = True
        cancel_row.operator("master_baker.cancel_bake", text="Cancel", icon="CANCEL")
    else:
        bake_row = action_row.row(align=True)
        bake_row.enabled = not bake_running
        bake_row.operator("master_baker.bake_project", text="Bake All", **_icon_kwargs("bake", "RENDER_STILL"))
    changed_row = action_row.row(align=True)
    changed_row.enabled = not bake_running
    changed_row.operator("master_baker.rebuild_changed_maps", text="Bake Changed", icon="FILE_REFRESH")
    action_row.operator("master_baker.refresh_outputs", text="Refresh", icon="FILE_REFRESH")
    action_row.operator("master_baker.open_output_folder", text="", icon_value=sidebar_icons.get_icon_value("open_folder"))
    copy_op = action_row.operator("master_baker.copy_output_path", text="", icon="COPY_ID")
    try:
        copy_op.filepath = str(export.resolve_output_root_path(project)[0])
    except Exception:
        copy_op.filepath = ""

    # --- Nav row ---
    nav = layout.row(align=True)
    nav.operator("master_baker.previous_output", text="", icon="TRIA_LEFT")
    nav.operator("master_baker.next_output", text="", icon="TRIA_RIGHT")
    pbr_row = nav.row(align=True)
    pbr_row.alert = preview_pbr_active
    preview_pbr = pbr_row.operator("master_baker.preview_pbr_output", text="Material Preview", icon="SHADING_TEXTURE", depress=preview_pbr_active)
    preview_pbr.group_name = active_group_name

    # --- UV Tools ---
    uv_box = layout.box()
    uv_box.label(text="UV Tools", icon="UV")

    # UV Selection Preview toggle
    uv_preview_settings = getattr(context.scene, "fyr_baker_uv_selection_preview", None)
    if uv_preview_settings is not None:
        sync_enabled = bool(context.scene.tool_settings.use_uv_select_sync)
        preview_row = uv_box.row(align=True)
        preview_row.active = not sync_enabled
        preview_row.prop(
            uv_preview_settings,
            "show_uv_selection_in_3d",
            toggle=True,
            icon="UV_VERTEXSEL",
        )
        if sync_enabled:
            preview_row.label(text="Sync is on", icon="INFO")

    # Active UV layer indicator + picker for the active group
    if active_group is not None:
        active_low_slot = properties.peek_active_low_slot(active_group)
        active_low = getattr(active_low_slot, "object_ref", None) if active_low_slot is not None else None
        active_low_data = getattr(active_low, "data", None) if active_low is not None else None
        if active_low is not None and getattr(active_low, "type", None) == "MESH" and active_low_data is not None:
            projection = properties.group_projection_settings_state(active_group)
            requested_uv = (getattr(projection, "uv_layer_name", "") or "").strip()
            active_uv = getattr(getattr(active_low_data, "uv_layers", None), "active", None)
            if requested_uv:
                dropdown_text = requested_uv
            elif active_uv is not None:
                dropdown_text = f"Active: {active_uv.name}"
            else:
                dropdown_text = "No UV layers"
            uv_row = uv_box.row(align=True)
            uv_row.label(text="Bake UV")
            uv_row.menu("MASTER_BAKER_MT_group_uv_layer_picker", text=dropdown_text, icon="GROUP_UVS")
            if requested_uv:
                uv_row.operator("master_baker.clear_group_uv_override", text="", icon="X")

    optimize_row = uv_box.row(align=True)
    optimize_row.enabled = not bake_running
    optimize_row.operator("master_baker.optimize_uv_seams", text="Optimize UV Seams", icon="MOD_UVPROJECT")

    reproject_row = uv_box.row(align=True)
    reproject_row.enabled = not project_bake_running
    reproject_row.prop(project, "live_reproject", text="Live Reproject", toggle=True, icon="UV_SYNC_SELECT")
    texture_reprojection.draw_status_icon(reproject_row, project)
    reproject_row.operator("master_baker.restore_last_bake_outputs", text="", icon="RECOVER_LAST")

    snapshot_obj = getattr(context, "active_object", None)
    has_snapshot = snapshot_obj is not None and uv_snapshot.find_snapshot(settings, snapshot_obj) is not None
    snapshot_row = uv_box.row(align=True)
    snapshot_row.enabled = getattr(context, "mode", "OBJECT") in {"OBJECT", "EDIT_MESH"} and snapshot_obj is not None and getattr(snapshot_obj, "type", None) == "MESH"
    snapshot_row.operator("master_baker.capture_uv_snapshot", text="Update Snapshot" if has_snapshot else "Capture Snapshot", icon="IMPORT")
    restore_col = snapshot_row.row(align=True)
    restore_col.enabled = has_snapshot
    restore_col.operator("master_baker.restore_uv_snapshot", text="Restore UVs", icon="RECOVER_LAST")


    # --- Send To ---
    prefs = preferences.get_preferences(migrate=False)
    if external_handoff.any_send_to_destination_enabled(prefs):
        send_box = layout.box()
        send_box.label(text="Send To", icon="EXPORT")
        if external_handoff.send_to_destination_enabled(prefs, "painter"):
            send_row = send_box.row(align=True)
            send_row.enabled = not bake_running
            send_row.operator("master_baker.send_to_painter", text="Painter", icon_value=sidebar_icons.get_icon_value("send_to_painter"))
            send_row.operator("master_baker.update_in_painter", text="Update", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "toolbag"):
            toolbag_row = send_box.row(align=True)
            toolbag_row.enabled = not bake_running
            toolbag_row.operator("master_baker.send_to_toolbag", text="Toolbag", icon_value=sidebar_icons.get_icon_value("send_to_marmoset"))
            toolbag_row.operator("master_baker.update_in_toolbag", text="Update", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "photoshop"):
            photo_row = send_box.row(align=True)
            photo_row.enabled = not bake_running
            photo_row.operator("master_baker.send_to_photoshop", text="Photoshop", icon="IMAGE_DATA")
        if external_handoff.send_to_destination_enabled(prefs, "designer"):
            designer_row = send_box.row(align=True)
            designer_row.enabled = not bake_running
            designer_row.operator("master_baker.send_to_designer", text="Designer", icon="NODETREE")
            designer_row.operator("master_baker.update_in_designer", text="Update", icon="FILE_REFRESH")
        if external_handoff.send_to_destination_enabled(prefs, "3dcoat"):
            coat_row = send_box.row(align=True)
            coat_row.enabled = not bake_running
            coat_row.operator("master_baker.send_to_3dcoat", text="3DCoat", icon="SCULPTMODE_HLT")
        if external_handoff.send_to_destination_enabled(prefs, "mari"):
            mari_row = send_box.row(align=True)
            mari_row.enabled = not bake_running
            mari_row.operator("master_baker.send_to_mari", text="Mari", icon="MATERIAL")

    # --- Channels ---
    channel_box = layout.box()
    channel_box.label(text="Channels")
    channel_row = channel_box.row(align=True)
    for channel_mode, label, _description in constants.IMAGE_CHANNEL_MODE_ITEMS:
        operator = channel_row.operator(
            "master_baker.set_image_editor_channel_mode",
            text=label,
            depress=(getattr(editor_state, "channel_mode", constants.IMAGE_CHANNEL_COLOR) == channel_mode),
        )
        operator.channel_mode = channel_mode

    # --- Mip level ---
    mip_box = layout.box()
    mip_row = mip_box.row(align=True)
    mip_row.label(text="Mip")
    for mip_level in range(constants.IMAGE_EDITOR_MAX_MIP_LEVEL + 1):
        operator = mip_row.operator(
            "master_baker.set_image_editor_mip_level",
            text=str(mip_level),
            depress=(getattr(editor_state, "mip_level", 0) == mip_level),
        )
        operator.mip_level = mip_level
