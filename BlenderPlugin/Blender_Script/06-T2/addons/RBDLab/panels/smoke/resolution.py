from ..common_ui_elements import collapsable


def resolution_section(main_col, ui, domain_mod):

    resolution = collapsable(
        main_col,
        ui,
        "show_hide_domain_resolution",
        "Resolution",
        'MOD_MULTIRES'
    )
    if resolution:
        resolution.prop(domain_mod, "resolution_max", text="Resolution")
        resolution.prop(domain_mod, "time_scale", text="Time Scale")
        resolution.prop(domain_mod, "cfl_condition", text="CFL Number")

    # main_col.separator()
    adaptative = collapsable(
        main_col,
        ui,
        "show_hide_domain_adaptative",
        "Adaptative Domain",
        'FULLSCREEN_ENTER'
    )
    if adaptative:
        use_adaptative = adaptative.row(align=True)
        use_adaptative.prop(domain_mod, "use_adaptive_domain", text="Use Adaptative", expand=True, toggle=True)
        use_adaptative_settings = adaptative.column(align=True)
        use_adaptative_settings.enabled = domain_mod.use_adaptive_domain
        # adaptative.prop(domain_settings, "use_adaptive_domain", text="Use Adaptative")
        use_adaptative_settings.prop(domain_mod, "additional_res", text="Add Resolution")
        use_adaptative_settings.prop(domain_mod, "adapt_margin", text="Margin")
        use_adaptative_settings.prop(domain_mod, "adapt_threshold", text="Threshold")

    # main_col.separator()
    noise = collapsable(
        main_col,
        ui,
        "show_hide_domain_noise",
        "Noise",
    )
    if noise:
        use_domain = noise.row(align=True)
        use_domain.prop(domain_mod, "use_noise", text="Use Noise", expand=True, toggle=True)
        use_noise_settings = noise.column(align=True)
        use_noise_settings.enabled = domain_mod.use_noise
        # noise.prop(domain_settings, "use_noise", text="Use Noise")
        use_noise_settings.prop(domain_mod, "noise_scale", text="Upres Scale")

        # Noise Strength
        nose_strength = use_noise_settings.row(align=True)
        nose_strength.prop(domain_mod, "noise_strength", text="Strength")
        use_noise_settings.prop(domain_mod, "noise_pos_scale", text="Scale")
        use_noise_settings.prop(domain_mod, "noise_time_anim", text="Time")
