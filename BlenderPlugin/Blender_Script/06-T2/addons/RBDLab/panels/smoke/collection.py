from ..common_ui_elements import collapsable


def collection_section(layout, ui, domain_mod):

    collections = collapsable(
        layout,
        ui,
        "show_hide_domain_collections",
        "Collections",
        'OUTLINER_COLLECTION',
        align=True
    )
    if collections:
        collections.prop(domain_mod, "fluid_group", text="Flow")
        collections_grid = collections.grid_flow(
            row_major=True, even_columns=False, even_rows=True, align=True, columns=2)
        collections_grid.use_property_split = False
        if domain_mod.fluid_group != domain_mod.fluid_group:
            if domain_mod.fluid_group:
                collections_grid.label(text="")
                fedback_txt = collections_grid.row(align=True)
                fedback_txt.scale_x = 1.57
                fedback_txt.box().label(text="Current in real use: " + domain_mod.fluid_group.name, icon='ERROR')
            else:
                collections_grid.label(text="")
                fedback_txt = collections_grid.row(align=True)
                fedback_txt.scale_x = 2
                fedback_txt.box().label(text="Current in real use: \"\"", icon='ERROR')

        collections.prop(domain_mod, "effector_group", text="Effector")

    guides = collapsable(
        layout,
        ui,
        "show_hide_domain_guides",
        "Guides",
        'VIEW_ORTHO',
        align=True
    )
    if guides:
        row_guides = guides.row(align=True)
        row_guides.use_property_split = False
        guides.prop(domain_mod, "use_guide", text="Guides", toggle=True)

        guides.use_property_split = True
        guides.separator()
        rest_props = guides.column(align=True)
        rest_props.enabled = domain_mod.use_guide == 'ENABLE'
        rest_props.prop(domain_mod, "guide_alpha", text="Weight")
        rest_props.prop(domain_mod, "guide_beta", text="Size")
        rest_props.prop(domain_mod, "guide_vel_factor", text="Velocity Factor")
        rest_props.prop(domain_mod, "guide_source", text="Velocity Source")
        rest_props.prop(domain_mod, "guide_parent", text="Guide Parent")
