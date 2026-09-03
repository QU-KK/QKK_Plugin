# SPDX-License-Identifier: GPL-2.0-or-later
"""Reusable UI foldouts and generation/shape/UV/material/finish/normal sections.

Loaded into the add-on package shared namespace by __init__.py.
"""



def draw_edge_decal_foldout(
    layout,
    owner,
    property_name,
    label,
    icon=None,
    prominent=False,
):
    """Draw a compact disclosure row and return its expanded state."""
    expanded = bool(getattr(owner, property_name))
    row = layout.row(align=True)
    row.scale_y = 1.2 if prominent else 1.05
    if icon:
        icon_cell = row.row(align=True)
        icon_cell.scale_x = 0.7
        icon_cell.label(text="", icon=icon)
    row.prop(
        owner,
        property_name,
        text=(
            label
            if expanded or not prominent
            else f"Show {label}"
        ),
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=prominent,
    )
    return expanded


def draw_generation_actions(layout, context, settings):
    box = layout.box()
    box.label(text="Generate", icon="OUTLINER_OB_MESH")
    body = box.column(align=True)

    if context.mode == "EDIT_MESH":
        face_select_mode = bool(context.tool_settings.mesh_select_mode[2])
        body.label(
            text=(
                "Face selection: wrapped bevel decals"
                if face_select_mode
                else "Edge selection: sharp edge paths"
            ),
            icon="FACESEL" if face_select_mode else "EDGESEL",
        )
        button = body.column()
        button.scale_y = 1.45
        button.operator(
            EDGEDECAL_OT_generate_contextual.bl_idname,
            text="Generate From Selection",
            icon="PLAY",
        )

        interactive = body.column()
        interactive.scale_y = 1.2
        interactive.operator(
            EDGEDECAL_OT_interactive_generate.bl_idname,
            text="Interactive Generate",
            icon="RESTRICT_SELECT_OFF",
            depress=EDGEDECAL_INTERACTIVE_RUNNING,
        )
    else:
        body.prop(settings, "auto_edge_angle")
        body.prop(settings, "auto_follow_edge_loops")

        button = body.column()
        button.scale_y = 1.45
        button.operator(
            EDGEDECAL_OT_generate_contextual.bl_idname,
            text="Generate Automatically",
            icon="SHARPCURVE",
        )

        boolean_actions = body.row(align=True)
        boolean_actions.scale_y = 1.2
        boolean_actions.operator(
            EDGEDECAL_OT_generate_intersections.bl_idname,
            text="Generate Intersections",
            icon="MOD_BOOLEAN",
        )
        boolean_actions.operator(
            EDGEDECAL_OT_generate_boolean.bl_idname,
            text="Generate From Booleans",
            icon="SELECT_INTERSECT",
        )

        interactive = body.column()
        interactive.scale_y = 1.2
        interactive.operator(
            EDGEDECAL_OT_interactive_generate.bl_idname,
            text="Interactive Generate",
            icon="RESTRICT_SELECT_OFF",
            depress=EDGEDECAL_INTERACTIVE_RUNNING,
        )


def draw_shape_settings(layout, settings):
    box = layout.box()
    if not draw_edge_decal_foldout(
        box,
        settings,
        "show_geometry_settings",
        "Geometry",
        icon="MESH_DATA",
    ):
        return

    body = box.column(align=True)
    body.prop(settings, "surface_offset")
    body.prop(settings, "maximum_decal_length", text="Maximum Decal Length")
    body.prop(settings, "auto_trim_corner_ends")
    corner_trim = body.row()
    corner_trim.enabled = settings.auto_trim_corner_ends
    corner_trim.prop(settings, "corner_end_trim_multiplier")

    body.separator()
    body.label(text="Filtering & Width Control", icon="FILTER")
    advanced = body.column(align=True)
    advanced.prop(settings, "use_face_loop_slide")
    advanced.prop(settings, "use_edge_split")
    split_row = advanced.row()
    split_row.enabled = settings.use_edge_split
    split_row.prop(settings, "split_angle")

    advanced.separator()
    advanced.prop(settings, "remove_short_edges")
    minimum_row = advanced.row()
    minimum_row.enabled = settings.remove_short_edges
    minimum_row.prop(settings, "minimum_edge_length")

    advanced.separator()
    advanced.prop(settings, "auto_face_width")
    advanced.prop(settings, "clamp_edge_overlaps")
    samples = advanced.row()
    samples.enabled = (
        settings.auto_face_width or settings.clamp_edge_overlaps
    )
    samples.prop(settings, "auto_width_samples")
    clearance = advanced.row()
    clearance.enabled = settings.auto_face_width
    clearance.prop(settings, "auto_width_clearance")
    overlap = advanced.row()
    overlap.enabled = settings.clamp_edge_overlaps
    overlap.prop(settings, "overlap_clearance")


def draw_uv_settings(layout, settings):
    box = layout.box()
    if not draw_edge_decal_foldout(
        box,
        settings,
        "show_uv_settings",
        "More UV Settings",
        icon="UV",
    ):
        return

    body = box.column(align=True)
    body.prop(settings, "auto_unwrap_uvs")
    source_projection_required = bool(
        getattr(settings, "match_source_material", False)
    )
    if not source_projection_required:
        second_uv = body.row()
        second_uv.enabled = settings.auto_unwrap_uvs
        second_uv.prop(
            settings,
            "generate_second_uv",
            text="Conformal Second UV",
        )
    advanced = body.column(align=True)
    advanced.prop(settings, "use_integrated_quadrify")

    quadrify = advanced.column(align=True)
    quadrify.enabled = (
        settings.auto_unwrap_uvs
        and settings.use_integrated_quadrify
    )
    quadrify.prop(settings, "integrated_quadrify_average_shape")
    quadrify.prop(settings, "integrated_quadrify_even_shape")

    advanced.prop(settings, "set_target_texel_density")
    density = advanced.column(align=True)
    density.enabled = (
        settings.auto_unwrap_uvs
        and (
            settings.set_target_texel_density
            or (
                settings.generate_second_uv
                and not source_projection_required
            )
        )
    )
    density.prop(settings, "target_texel_density")
    density.prop(settings, "texture_resolution")

    advanced.prop(settings, "average_uv_island_scale")
    advanced.prop(settings, "align_uvs_horizontally")
    advanced.prop(settings, "place_in_quarter_strips")

    strips = advanced.column(align=True)
    strips.enabled = (
        settings.auto_unwrap_uvs
        and settings.place_in_quarter_strips
    )
    strips.prop(settings, "randomize_quarter_strip")
    strips.prop(settings, "randomize_horizontal_offset")
    amount_row = strips.row()
    amount_row.enabled = settings.randomize_horizontal_offset
    amount_row.prop(settings, "horizontal_randomize_amount")
    strips.prop(settings, "uv_strip_padding")


def draw_finish_settings(layout, settings):
    box = layout.box()
    if not draw_edge_decal_foldout(
        box,
        settings,
        "show_options_settings",
        "Modifiers",
        icon="MODIFIER",
    ):
        return

    body = box.column(align=True)
    body.prop(settings, "replace_previous")
    body.separator()

    # Present modifiers in the same order enforced in the generated stack.
    weld = body.box()
    weld.prop(settings, "add_weld_modifier")
    if settings.add_weld_modifier:
        weld.prop(settings, "weld_distance")

    shrinkwrap = body.box()
    shrinkwrap.prop(settings, "add_shrinkwrap_modifier")
    if settings.add_shrinkwrap_modifier:
        shrinkwrap.prop(
            settings,
            "surface_offset",
            text="Shrinkwrap Offset",
        )

    center_displace = body.box()
    center_displace.prop(settings, "add_center_displace_modifier")
    if settings.add_center_displace_modifier:
        center_displace.prop(settings, "center_displace_strength")

    bevel = body.box()
    bevel.prop(settings, "add_bevel_modifier")
    if settings.add_bevel_modifier:
        bevel_settings = bevel.column(align=True)
        bevel_settings.prop(settings, "bevel_edge_center")
        if settings.bevel_edge_center:
            bevel_settings.label(
                text="Vertex Group: EdgeDecal_Center",
                icon="GROUP_VERTEX",
            )

        source_obj = edge_decal_context_source(bpy.context)
        source_bevel = last_source_bevel_modifier(source_obj)
        if source_bevel is not None:
            linked = bevel_settings.row()
            linked.label(
                text=f"Linked to: {source_bevel.name}",
                icon="LINKED",
            )
            display = bevel_settings.column(align=True)
            display.enabled = False
            display.prop(settings, "center_bevel_width")
            display.prop(settings, "center_bevel_segments")
            display.prop(settings, "center_bevel_profile")
            if not settings.bevel_edge_center:
                display.prop(settings, "bevel_angle")
        else:
            warning = bevel_settings.row()
            warning.label(text="Using custom bevel settings", icon="MOD_BEVEL")
            bevel_settings.prop(settings, "center_bevel_width")
            bevel_settings.prop(settings, "center_bevel_segments")
            bevel_settings.prop(settings, "center_bevel_profile")
            if not settings.bevel_edge_center:
                bevel_settings.prop(settings, "bevel_angle")
    subdivision = body.box()
    subdivision.prop(settings, "add_subdivision_modifier")

    decimate = body.box()
    decimate.prop(settings, "add_decimate_modifier")


def draw_normals_settings(layout, settings):
    box = layout.box()
    if not draw_edge_decal_foldout(
        box,
        settings,
        "show_normals_settings",
        "Normals",
        icon="NORMALS_FACE",
    ):
        return

    body = box.column(align=True)
    body.prop(settings, "normal_mode")
    harden = body.row()
    harden.enabled = settings.add_bevel_modifier
    harden.prop(settings, "bevel_harden_normals")
    normals = body.column(align=True)
    normals.enabled = settings.normal_mode != "SHADE_SMOOTH"
    normals.prop(settings, "normal_keep_sharp")

    weight = normals.row()
    weight.enabled = settings.normal_mode == "WEIGHTED"
    weight.prop(settings, "normal_weight")
    normals.prop(settings, "normal_threshold")
