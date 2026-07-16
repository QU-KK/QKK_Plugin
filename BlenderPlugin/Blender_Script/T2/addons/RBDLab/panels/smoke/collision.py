from ..common_ui_elements import collapsable


def collision_section(layout, ui, domain_mod):

    collision = collapsable(
        layout,
        ui,
        "show_hide_domain_border_collisions",
        "Border Collisions",
        'MOD_EDGESPLIT',
        align=True
    )
    if collision:

        collision.use_property_split = False
        collision.alignment = 'RIGHT'

        grid_coll = collision.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=3)
        grid_coll.box().label(text="")
        grid_coll.box().prop(domain_mod, "use_collision_border_top", text="Top", toggle=True)
        grid_coll.box().label(text="")
        grid_coll.box().prop(domain_mod, "use_collision_border_left", text="Left", toggle=True)

        row = grid_coll.box().row(align=True)
        row.prop(domain_mod, "use_collision_border_front", text="Front", toggle=True)
        row.prop(domain_mod, "use_collision_border_back", text="Back", toggle=True)

        grid_coll.box().prop(domain_mod, "use_collision_border_right", text="Right", toggle=True)
        grid_coll.box().label(text="")
        grid_coll.box().prop(domain_mod, "use_collision_border_bottom", text="Bottom", toggle=True)
        grid_coll.box().label(text="")

        collision.separator()
        collision.prop(domain_mod, "delete_in_obstacle", text="Delete in Obstacle")
