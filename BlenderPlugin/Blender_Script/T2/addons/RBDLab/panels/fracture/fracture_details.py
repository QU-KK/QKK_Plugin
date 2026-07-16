import bpy
from ..common_ui_elements import collapsable, multiline_print
from ...addon.naming import RBDLabNaming


def draw_boolean_settings(rbdlab, layout, ui):

    booleans = collapsable(
        layout,
        ui,
        "show_hide_boolean_method",
        "Booleans",
        'MOD_BOOLEAN',
        align=True,
    )
    if booleans:
        content = booleans.row(align=True)
        content.scale_y = 1.3
        content.use_property_split = True
        content.prop(rbdlab, "rbdlab_cf_fast_exact", text="Method", expand=True)

    row1 = layout.box().row(align=True, heading="Fixing")
    row2 = layout.column(align=True)
    section_header = row1.column(align=True)
    section_header.use_property_split = False
    section_header.prop(rbdlab.ui, "select_bad_chunks_by_selection")
    content = row2.box().row(align=True)
    content.scale_y = 1.3
    content.use_property_split = True
    content.operator("rbdlab.select_bad_chunks", text="Select Bad Chunks", icon='SELECT_DIFFERENCE')
    content.operator("rbdlab.auto_fix_chunks", text="Auto Fix", icon='SELECT_EXTEND')

    if rbdlab.filtered_target_collection:
        if "fracture_applied" in rbdlab.filtered_target_collection:
            if rbdlab.working_in_inner_details:
                decimate = row2.box().row(align=True)
                decimate.scale_y = 1.3
                decimate.label(text="Fix fissures:")
                decimate.separator()

                # draw_decimate_toggle
                valid_objects = [obj for obj in bpy.context.selected_objects
                                 if obj.type == 'MESH' and RBDLabNaming.DECIMATE in obj.modifiers]

                if valid_objects:
                    result_any = any([obj for obj in valid_objects
                                      if obj.modifiers[RBDLabNaming.DECIMATE].show_render and obj.modifiers
                                      [RBDLabNaming.DECIMATE].show_viewport])
                    have_modifiers_off = result_any
                else:
                    have_modifiers_off = True

                decimate.operator("rbdlab.high_details_toggle_decimate", text='ON',
                                  depress=not have_modifiers_off).type = 'ENABLE_PLANAR'
                decimate.operator("rbdlab.high_details_toggle_decimate", text='OFF',
                                  depress=have_modifiers_off).type = 'DISABLE_PLANAR'

                # end draw_decimate_toggle


def toggle_decimate_collapse(rbdlab, layout):

    if rbdlab.filtered_target_collection:
        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:

            if RBDLabNaming.SUFIX_LOW in coll_name:
                coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            else:
                coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

            # valid_objects = [obj for obj in context.selected_objects
            #                  if obj.type == 'MESH' and "RBDLab_Decimate_collapse" in obj.modifiers]

            # Decimate collapse
            if coll_high_name in bpy.data.collections:
                valid_objects = [obj for obj in bpy.data.collections[coll_high_name].objects
                                 if obj.type == 'MESH' and "RBDLab_Decimate_collapse" in obj.modifiers]

                if valid_objects:
                    result_any = any([obj for obj in valid_objects
                                      if obj.modifiers["RBDLab_Decimate_collapse"].show_render and obj.modifiers
                                      ["RBDLab_Decimate_collapse"].show_viewport])
                    have_modifiers_off = not result_any
                else:

                    have_modifiers_off = False

                buttons_decimate = layout.row(align=True)
                # buttons_decimate.scale_y = 1.3
                buttons_decimate.operator("rbdlab.high_details_toggle_decimate", text='ON',
                                          depress=not have_modifiers_off).type = 'ENABLE_COLLAPSE'
                buttons_decimate.operator("rbdlab.high_details_toggle_decimate", text='OFF',
                                          depress=have_modifiers_off).type = 'DISABLE_COLLAPSE'


def draw_remesh_settings(rbdlab, layout):
    col = layout.column(align=True)
    col.separator()
    row1 = col.row(align=True)
    row1.scale_y = 1.3
    row1.use_property_split = False
    row1.prop(rbdlab, "remesh_mode", text=" ", expand=True)

    row2 = col.row()
    col = row2.column()
    col.separator()

    if rbdlab.remesh_mode == 'VOXEL':
        col = col.column(align=True)
        col.use_property_split = True
        col.prop(rbdlab, "voxel_size", text="Voxel Size")
        col.prop(rbdlab, "remesh_voxel_adaptivity", text="Adaptivity")
    else:  # SMOOTH, SHARP
        row2.use_property_split = False
        col.operator("rbdlab.octree_deepth_uniform", text="Octree Depth Uniform")
        row = col.row(align=True)
        row.use_property_split = True
        row.prop(rbdlab, "range_min", text="min - max")
        row.prop(rbdlab, "range_max", text="")
        col = col.column(align=True)
        col.use_property_split = True
        col.prop(rbdlab, "octree_depth", text="Octree Depth")
        col.prop(rbdlab, "remesh_scale", text="Scale")

    col.separator()
    # Controls RBDLab_Remesh Modifier "Smooth Shading" prop.
    col.prop(rbdlab, "use_smooth_shade", text="Use Smooth Shade")
    # Controls RBDLab_Boolean Modifier visibility.
    col.prop(rbdlab, "external_roughness", text="External Roughness")

    if not rbdlab.external_roughness:
        col.prop(rbdlab, "remesh_with_material", text="With Inner Material")

    col.separator()

    # decimate in Remesh panel:
    # col.label(text="Decimate:")
    # decimate1 = col.column(align=True)
    # decimate1.use_property_split = False
    # row_decimate = decimate1.row(align=True)
    # row_decimate.scale_y = 1.3
    # toggle_decimate_collapse(rbdlab, row_decimate)
    # row_decimate.prop(rbdlab, "ratio", text="Ratio")
    # col.separator()


def draw_subdiv_settings(context, rbdlab, layout0, layout):
    ui = rbdlab.ui
    layout.use_property_split = True

    row1 = layout.row(align=True)
    row1.prop(rbdlab, "inner_subdivision", text="Subdivisions")

    layout.separator()
    if rbdlab.inner_subdivision > 3:
        feedback = layout.column(align=True)
        text = "When using many subdivisions it can slow down the task, you can speed it up a bit if you don't use the \"Remove Loose vertices\" but you will have to manually clean the loose vertices of your high chunks."
        multiline_print(feedback, text, max_words=8, first_line_crop=0)

    layout.separator()
    rm_loose = layout.row(align=True)
    rm_loose.use_property_split = False
    rm_loose.prop(rbdlab, "remove_loose_verts", text="Remove Loose vertices to high (when apply)")

    layout.separator()

    # decimate in Subdivision panel (este era el decimate collapse de los high pero ya no se pone):
    # col = layout.column(align=True)
    # col.label(text="Decimate:")
    # decimate1 = col.column(align=True)
    # decimate1.use_property_split = False
    # row_decimate = decimate1.row(align=True)
    # row_decimate.scale_y = 1.3
    # toggle_decimate_collapse(rbdlab, row_decimate)
    # row_decimate.prop(rbdlab, "ratio", text="Ratio")

    # layout.separator()

    # row2 = layout.row(align=True)
    # row2.separator()
    # row2.separator()
    # row2.use_property_split = True
    # row2.label(text="Decimate:")
    # toggle_decimate_collapse(context, row2)
    # row2 = layout.row()
    # row2.prop(rbdlab, "ratio", text="Ratio")

    # LaplacianSmooth:
    laplacian_smooth = collapsable(
        layout,
        ui,
        "show_hide_lapshmooth",
        "Laplacian Smooth",
        'MOD_SMOOTH',
        align=True,
    )
    if laplacian_smooth:
        laplacian_smooth.prop(rbdlab, "lapsmooth_toggle", toggle=True, text="Enable"
                              if not rbdlab.lapsmooth_toggle else "Dissable")
        laplacian_smooth.prop(rbdlab, "iterations", text="Laplacian Smooth", toggle=True)
        axis = laplacian_smooth.row(align=True)
        axis.prop(rbdlab, "use_x", text='X', expand=True, toggle=True)
        axis.prop(rbdlab, "use_y", text='Y', expand=True, toggle=True)
        axis.prop(rbdlab, "use_z", text='Z', expand=True, toggle=True)
        laplacian_smooth.prop(rbdlab, "lambda_factor")
        laplacian_smooth.prop(rbdlab, "lambda_border")
        laplacian_smooth.prop(rbdlab, "use_volume_preserve")
        laplacian_smooth.prop(rbdlab, "use_normalized")


def fracture_details(context, rbdlab, layout, ui):
    main_col = layout.box().column(align=True)

    # Si no hay un target, bloquear propiedades...
    sublayout = main_col.column(align=True)
    # sublayout.separator()
    sublayout.enabled = rbdlab.filtered_target_collection is not None and rbdlab.have_rbdlab_boolean_modifier()

    ''' RBDLab_Boolean '''
    draw_boolean_settings(rbdlab, sublayout, ui)

    col_as = sublayout.column(align=True).box()

    row_as = col_as.row(align=True)
    row_as.use_property_split = False
    row_as.prop(rbdlab, "use_auto_smooth", text="Auto-Smooth")
    row_row = row_as.row(align=True)
    row_row.enabled = rbdlab.use_auto_smooth
    row_row.prop(rbdlab, "auto_smooth", text="Angle")


    comp_neighbors = col_as.row(align=True)
    comp_neighbors.use_property_split = False
    comp_neighbors.prop(ui, "compute_neighbors", text="Compute Neighbors")

    if not ui.compute_neighbors:
        text = "Computing Neighbors is necessary to use constraints and/or particles (Brokens)."
        multiline_print(col_as.box(), text, max_words=5, first_line_crop=0, without_box=True)

    ''' First Step Operators to apply fracture or add more details...
        - lo mostramos cuando no estamos trabajando en detalle o el fracture ya está aplicado.
    '''

    if not rbdlab.working_in_inner_details or (
            sublayout.enabled and rbdlab.filtered_target_collection["fracture_applied"]):
        if sublayout.enabled:
            alert = True
        else:
            alert = False

        col_options = sublayout.box()
        col_options.box().label(text="For apply fractures, choose an option:", icon='ERROR')

        col_options.scale_y = 1.3
        col_options = col_options.row(align=True)
        col_options.operator("rbdlab.apply_mods",    text="Apply Fracture NOW", icon='CHECKMARK')
        col_options.separator()
        col_options.operator("rbdlab.add_highs_mods", text="Add EXTRA Details", icon='MOD_NOISE')
    else:
        ''' When working on details... SHOW PROPS TO ADD MORE DETAILS... '''

        # sin SuperLayaout:
        extra_details = collapsable(
            main_col,
            ui,
            "show_fracture_details_extras",
            "Extra Details",
            'MOD_NOISE',
            align=True,
        )
        if extra_details:

            if not rbdlab.ui.show_fracture_details_extras:
                # drop_header.set_emboss_normal().operator("rbdlab.apply_mods", text='APPLY')
                return

            is_in_local_view = len([area for area in context.screen.areas if area.type == 'VIEW_3D' and area.spaces[0].local_view]) > 0

            if is_in_local_view:
                icon_isolate = 'OBJECT_DATA'
            else:
                icon_isolate = 'OBJECT_HIDDEN'

            row1 = extra_details.row(align=True)
            row1.scale_y = 1.3
            row2 = extra_details.row(align=True)
            row2.scale_y = 1.3

            # row1.prop(rbdlab, "isolate_or_not", text="Isolate", expand=True, toggle=True, icon=icon_isolate)
            row1.prop(rbdlab, "isolate_or_not", text="Isolate", expand=True, toggle=True)

            row1.enabled = len(context.selected_objects) > 0 or is_in_local_view

            content = row2.row(align=True)
            content.scale_y = 1.3
            content.enabled = len(context.selected_objects) > 0 or is_in_local_view

            row2.prop(rbdlab, "remesh_or_subdivision", text=" ", expand=True)

            MODIFIER = rbdlab.remesh_or_subdivision.upper()
            if MODIFIER == 'REMESH':
                row3 = extra_details.row(align=True)
                draw_remesh_settings(rbdlab, row3)
            else:
                row3 = extra_details.column(align=True)
                draw_subdiv_settings(context, rbdlab, extra_details, row3)

            col = extra_details.column(align=True)

            noise = collapsable(
                extra_details,
                ui,
                "show_fracture_details_noise",
                "Noise",
                'FORCE_TURBULENCE',
                align=True,
            )
            if noise:
                noise.prop(rbdlab, "noise_basis", text="Noise Basis")
                noise.prop(rbdlab, "noise_type", text="Noise Type")
                noise.prop(rbdlab, "clouds_size", text="Size")
                noise.prop(rbdlab, "depth_displace_texture", text="Depth")
                noise.prop(rbdlab, "displace_strength", text="Strength")
                noise.separator()

            extra_details.separator()

            feedback = extra_details.box().column(align=True)
            text = "Once the high details have been applied, we continue working with the low version. In the final rendering the high details version will be displayed."
            multiline_print(feedback, text, max_words=7, first_line_crop=1)

            extra_details.separator()
            col = extra_details.row(align=True)
            col.scale_y = 1.3
            col.operator("rbdlab.apply_mods", text="Apply", icon='CHECKMARK')
            col.alert = True
            col.operator("rbdlab.working_in_inner_details_cancel", text="Cancel", icon='CANCEL')

            if rbdlab.isolate_or_not:
                col.enabled = False
            else:
                col.enabled = True
