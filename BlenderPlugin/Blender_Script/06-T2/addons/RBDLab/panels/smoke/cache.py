from ..common_ui_elements import collapsable


def cache_section(rbdlab, layout, ui, domain_mod):

    y_scale = 0.8
    y_correction_scale = 1.45

    container = layout.column(align=True)
    container.use_property_split = False

    bake_incomplete = (domain_mod.cache_frame_pause_data < domain_mod.cache_frame_end)
    cache_resumable = domain_mod.cache_resumable
    has_baked_data = domain_mod.has_cache_baked_data
    has_cache_baked_noise = domain_mod.has_cache_baked_noise
    is_cache_baking_data = domain_mod.is_cache_baking_data
    is_cache_baking_noise = domain_mod.is_cache_baking_noise

    # if domain_mod.cache_type != 'REPLAY':

    container.separator()

    start_end = container.row(align=True)
    start_end.use_property_split = True
    start_end.prop(domain_mod, "cache_frame_start", text="Start | End")
    start_end.prop(domain_mod, "cache_frame_end", text="")
    container.separator()

    if domain_mod.cache_type == 'REPLAY':
        grid1 = container.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=3)
        grid1.scale_y = y_scale
        grid1.prop(domain_mod, "cache_type", text="")
        grid1.box().label(text="")
        grid1.box().label(text="")
        grid1.box().prop(domain_mod, "cache_resumable", text="Resumable")
        grid1.box().label(text="")
        grid1.box().label(text="")

    elif domain_mod.cache_type == 'MODULAR':
        grid1 = container.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=3)
        grid1.prop(domain_mod, "cache_type", text="")
        grid1.scale_y = y_scale

        # bake data & resume:
        if is_cache_baking_data:
            txt_data = "Baking Data - ESC to pause"
            # grid1.>luid_bake_data", text=txt_data)
            grid1.operator("rbdlab.domain_modular_baking_data", text=txt_data)
        else:
            if cache_resumable and has_baked_data and bake_incomplete and not is_cache_baking_data:
                txt_data = "Resume Data"
            else:
                txt_data = "Baking Data"

            # grid1.operator("rbdlab.fluid_bake_data", text=txt_data)
            grid1.operator("rbdlab.domain_modular_baking_data", text=txt_data)

        # bake noise & resume:
        bake_noise = grid1.grid_flow(align=True, columns=0)
        # bake_noise.scale_y = y_scale
        bake_noise.enabled = cache_resumable and has_baked_data
        if is_cache_baking_noise:
            txt_data = "Baking Noise - ESC to pause"
            # bake_noise.operator("rbdlab.fluid_bake_noise", text=txt_data)
            bake_noise.operator("rbdlab.domain_modular_baking_noise", text=txt_data)
        else:
            if cache_resumable and has_cache_baked_noise and bake_incomplete and not is_cache_baking_data and not is_cache_baking_noise:
                txt_data = "Resume Noise"
            else:
                txt_data = "Baking Noise"
            # bake_noise.operator("rbdlab.fluid_bake_noise", text=txt_data)
            bake_noise.operator("rbdlab.domain_modular_baking_noise", text=txt_data)

        grid1.box().prop(domain_mod, "cache_resumable", text="Resumable")

        # free data
        free_data = grid1.grid_flow(align=True, columns=0)
        free_data.scale_y = y_correction_scale
        # free_data.operator("rbdlab.fluid_free_data", text="Free Data")
        free_data.operator("rbdlab.domain_modular_free_data", text="Free Data")
        free_data.enabled = has_baked_data and not is_cache_baking_data

        free_noise = grid1.grid_flow(align=True, columns=0)
        free_noise.scale_y = y_correction_scale
        # free_noise.operator("rbdlab.fluid_free_noise", text="Free Noise")
        free_noise.operator("rbdlab.domain_modular_free_noise", text="Free Noise")
        free_noise.enabled = has_cache_baked_noise and not is_cache_baking_noise

    elif domain_mod.cache_type == 'ALL':
        btype = container.row(align=True)
        btype.scale_x = 0.5
        btype.scale_y = 1.2
        btype.prop(domain_mod, "cache_type", text="")

        bk_all = btype.row(align=True)
        bk_all.scale_x = 0.96

        bk_all_condition = not is_cache_baking_data
        if bk_all_condition:
            bk_all_txt = "Bake All"
        else:
            bk_all_txt = "Baking All - ESC to pause"

        # bk_all.operator("rbdlab.fluid_bake_all", text=bk_all_txt)
        bk_all.operator("rbdlab.domain_bake_all", text=bk_all_txt)
        bk_all.enabled = bk_all_condition and not has_baked_data

        grid1 = container.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=3)
        grid1.box().prop(domain_mod, "cache_resumable", text="Resumable")
        grid1.scale_y = y_scale + 0.05

        resume_condition = (cache_resumable and has_baked_data and not is_cache_baking_data)

        resume = grid1.column(align=True)
        resume.scale_y = y_correction_scale
        resume.enabled = resume_condition and bake_incomplete
        # resume.operator("rbdlab.fluid_bake_all", text="Resume")
        resume.operator("rbdlab.domain_bake_all", text="Resume")

        free_all = grid1.column(align=True)
        free_all.scale_y = y_correction_scale
        free_all.enabled = has_baked_data

        if bake_incomplete and cache_resumable:
            text_free = "Free"
        else:
            text_free = "Free All"

        # free_all.operator("rbdlab.fluid_free_all", text=text_free)
        free_all.operator("rbdlab.domain_bake_free_all", text=text_free)

    ##########################################################################################

    layout.separator()
    layout.separator()
    row2 = layout.row(align=True)
    row2.use_property_split = False
    row2.prop(domain_mod, "cache_directory", text="")

    layout.separator()
    cache = collapsable(
        layout,
        ui,
        "show_hide_domain_cache",
        "Cache Settings",
        'FILE_CACHE',
        align=True
    )
    if cache:
        cache.use_property_split = True
        cache.use_property_decorate = False

        # start_end = cache.row(align=True)
        # start_end.use_property_split = True
        # start_end.prop(domain, "cache_frame_start", text="Start | End")
        # start_end.prop(domain, "cache_frame_end", text="")

        cache.separator()
        offset = cache.row(align=True)
        offset.enabled = domain_mod.cache_type in {'MODULAR', 'ALL'}
        offset.prop(domain_mod, "cache_frame_offset", text="Offset")

        cache.separator()
        format_vol = cache.row(align=True)
        is_baking_any = domain_mod.is_cache_baking_any
        has_baked_data = domain_mod.has_cache_baked_data
        format_vol.enabled = not is_baking_any and not has_baked_data
        format_vol.prop(domain_mod, "cache_data_format", text="Format Volumes")

        if domain_mod.cache_data_format == 'OPENVDB':
            compression = cache.column(align=True)
            compression.enabled = not is_baking_any and not has_baked_data
            compression.prop(domain_mod, "openvdb_cache_compress_type", text="Compression Volumes")

            precision = cache.column(align=True)
            precision.prop(domain_mod, "openvdb_data_depth", text="Precision Volumes")
