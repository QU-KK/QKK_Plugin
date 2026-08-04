from ..common_ui_elements import collapsable


def display_section(layout, ui, domain_mod):

    vd = collapsable(
        layout,
        ui,
        "show_hide_domain_display",
        "viewport display",
        'RESTRICT_VIEW_OFF',
        align=True
    )
    if vd:

        flow = vd.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)

        col = flow.column(align=False)
        col.prop(domain_mod, "display_thickness")

        sub = col.column()
        sub.prop(domain_mod, "display_interpolation")

        if domain_mod.use_color_ramp and domain_mod.color_ramp_field == 'FLAGS':
            sub.enabled = False

        col = col.column()
        col.active = not domain_mod.use_slice
        col.prop(domain_mod, "slice_per_voxel")

        col.separator()

        button_settings1 = {
            "type": "prop",
            "from": domain_mod,
            "prop": "use_slice",
            "text": " ",
            "toggle": False,
            "icon": None,
            "expand": False
        }
        slice = collapsable(
            vd,
            ui,
            "show_hide_domain_display_slice",
            "Slice",
            'SELECT_SUBTRACT',
            align=True,
            button_settings1=button_settings1,
        )
        if slice:

            # slice = vd.box().column(align=True)
            # slice.use_property_split = False
            # slice.prop(domain_mod, "use_slice", text="Use Slice")
            slice.enabled = domain_mod.use_slice

            slice.prop(domain_mod, "slice_axis")
            slice.prop(domain_mod, "slice_depth")

            sub = slice.column()
            sub.prop(domain_mod, "show_gridlines")

            sub.active = domain_mod.display_interpolation == 'CLOSEST' or domain_mod.color_ramp_field == 'FLAGS'

        button_settings1 = {
            "type": "prop",
            "from": domain_mod,
            "prop": "show_velocity",
            "text": " ",
            "toggle": False,
            "icon": None,
            "expand": False
        }
        vector_display = collapsable(
            vd,
            ui,
            "show_hide_domain_display_vector_display",
            "Vector Display",
            'EMPTY_SINGLE_ARROW',
            align=True,
            button_settings1=button_settings1,
        )
        if vector_display:

            vector_display.active = domain_mod.show_velocity
            vector_display.prop(domain_mod, "vector_display_type", text="Display As")

            if domain_mod.vector_display_type == 'MAC':
                sub = vector_display.column(heading="MAC Grid")
                sub.prop(domain_mod, "vector_show_mac_x")
                sub.prop(domain_mod, "vector_show_mac_y")
                sub.prop(domain_mod, "vector_show_mac_z")
            else:
                vector_display.prop(domain_mod, "vector_scale_with_magnitude")

            vector_display.prop(domain_mod, "vector_field")
            vector_display.prop(domain_mod, "vector_scale")

            if not domain_mod.use_guide and domain_mod.vector_field == 'GUIDE_VELOCITY':
                note = vector_display.split()
                note.label(icon='INFO', text="Enable Guides first! Defaulting to Fluid Velocity")

        button_settings1 = {
            "type": "prop",
            "from": domain_mod,
            "prop": "use_color_ramp",
            "text": " ",
            "toggle": False,
            "icon": None,
            "expand": False
        }
        grid_display = collapsable(
            vd,
            ui,
            "show_hide_domain_display_grid_display",
            "Grid Display",
            'VIEW_ORTHO',
            align=True,
            button_settings1=button_settings1,
        )
        if grid_display:

            grid_display.active = domain_mod.use_color_ramp
            grid_display.prop(domain_mod, "color_ramp_field")

            if not domain_mod.color_ramp_field == 'FLAGS':
                grid_display.prop(domain_mod, "color_ramp_field_scale")

            grid_display.use_property_split = False

            if domain_mod.color_ramp_field[
                    : 3] != 'PHI' and domain_mod.color_ramp_field not in {
                    'FLAGS', 'PRESSURE'}:
                grid_display = grid_display.column()
                grid_display.template_color_ramp(domain_mod, "color_ramp", expand=True)
