from ..common_ui_elements import collapsable


def weights_section(layout, ui, domain_mod):

    weights = collapsable(
        layout,
        ui,
        "show_hide_domain_weights",
        "Weights",
        'ORIENTATION_GIMBAL',
        align=True
    )
    if weights:
        weights.use_property_split = True
        weights.alignment = 'RIGHT'

        # NOTE: TODO temporarily used until the animate properties are properly skipped.
        weights.use_property_decorate = False  # No animation (remove this later on).

        weights.prop(domain_mod.effector_weights, "collection")

        weights.separator()
        flow = weights.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)

        col = flow.column(align=True)
        col.prop(domain_mod.effector_weights, "gravity", slider=True)
        col.prop(domain_mod.effector_weights, "all", slider=True)
        col.prop(domain_mod.effector_weights, "force", slider=True)
        col.prop(domain_mod.effector_weights, "vortex", slider=True)

        col = flow.column(align=True)
        col.prop(domain_mod.effector_weights, "magnetic", slider=True)
        col.prop(domain_mod.effector_weights, "harmonic", slider=True)
        col.prop(domain_mod.effector_weights, "charge", slider=True)
        col.prop(domain_mod.effector_weights, "lennardjones", slider=True)

        col = flow.column(align=True)
        col.prop(domain_mod.effector_weights, "wind", slider=True)
        col.prop(domain_mod.effector_weights, "curve_guide", slider=True)
        col.prop(domain_mod.effector_weights, "texture", slider=True)

        col.prop(domain_mod.effector_weights, "smokeflow", slider=True)

        col = flow.column(align=True)
        col.prop(domain_mod.effector_weights, "turbulence", slider=True)
        col.prop(domain_mod.effector_weights, "drag", slider=True)
        col.prop(domain_mod.effector_weights, "boid", slider=True)
