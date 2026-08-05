import bpy
from ..common_ui_elements import collapsable


def fracture(context, layout, ui):
    main_col = layout.box().column(align=True)

    sublayout = main_col.column(align=True)
    if context.scene.rbdlab.scatter_working:
        if context.scene.rbdlab.ui.scatter_mode == 'BOOLEAN' or context.scene.rbdlab.ui.scatter_mode == 'ORGANIC':
            sublayout.enabled = False

    rbdlab = context.scene.rbdlab

    # sublayout.separator()
    sublayout.use_property_split = True
    sublayout.use_property_decorate = False

    flow = sublayout.grid_flow(align=True)

    # Fracture ####################################################

    obj = context.active_object
    objects = len(context.selected_objects)

    col = flow.column()
    col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

    col.prop(rbdlab, "rbdlab_cf_source", text="Source")

    col.prop(rbdlab, "rbdlab_cf_source_limit", text="Max Chunks")
    col.prop(rbdlab, "rbdlab_cf_noise", text="Noise")

    col.prop(rbdlab, "rbdlab_cf_wood_directions", text="Wood Directions")
    rowsub = col.row()
    rowsub.prop(rbdlab, "rbdlab_cf_cell_scale", text="Scale")
    if obj and objects:
        if obj.type == 'MESH':
            # col.enabled = True
            col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"
        else:
            col.enabled = False

    # margin ######################################################
    objects = len(context.selected_objects)

    col = flow.column()
    col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

    # col.prop(rbdlab, "rbdlab_cf_inner_detail", text="Inner Detail")
    # col.prop(rbdlab, "rbdlab_cf_use_sharp_edges_apply")
    col.prop(rbdlab, "rbdlab_cf_margin", text="Margin")
    if obj and objects:
        if obj.type == 'MESH':
            # col.enabled = True
            col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"
        else:
            col.enabled = False

    # Output #######################################################
    sublayout.separator()
    output = collapsable(
        sublayout,
        ui,
        "show_hide_fracture_output",
        "Output",
        'OUTLINER_COLLECTION',
        align=True,
    )
    if output:
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        col = output.column()
        if obj and objects:
            if obj.type == 'MESH' and obj.mode == 'OBJECT':
                col.enabled = True
            else:
                col.enabled = False

        container_fracture = output.column(align=False)

        col = container_fracture.column(align=False, heading="Single Output")
        col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"
        col.use_property_decorate = False
        row = col.row(align=True)
        row.prop(rbdlab, "use_single_collection_name", text="")

        sub = row.row(align=True)
        sub.alert = rbdlab.use_single_collection_name and len(rbdlab.rbdlab_cf_collection_name) <= 0
        sub.enabled = rbdlab.use_single_collection_name
        sub.prop(rbdlab, "rbdlab_cf_collection_name", text="")

        # col.prop(rbdlab, "post_original", text="Original")

        # row = output.row()
        # row.prop(rbdlab, "rbdlab_cf_fast_exact", text="Bool Method", expand=True)

        # row.prop(addon_preferences, "rbdlab_cf_fast_exact_prefs", text="Bool Method", expand=True)

        sub.separator()
        col = container_fracture.column(align=False)
        col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        col.use_property_split = True
        col.prop(rbdlab.ui, "use_auto_uv_cube_projection", text="  Auto UVs for inners")

        big_col = col.row(align=True)
        big_col.scale_y = 1.3

        big_col.operator("rbdlab.cellfracture", text="Fracture", icon='MOD_PHYSICS')

        fracture_applied = rbdlab.is_fractured()
        have_rbdlab_boolean_mod = rbdlab.have_rbdlab_boolean_modifier()

        if obj and objects:
            if obj.type == 'MESH' and obj.mode == 'OBJECT':
        
                if "rbdlab_scatter_organic" in obj or rbdlab.scatter_working or rbdlab.working_in_inner_details:
                    big_col.enabled = False
                else:
                    if not fracture_applied and have_rbdlab_boolean_mod:
                        big_col.enabled = False
                    else:
                        big_col.enabled = True
        
            else:
                big_col.enabled = False
        else:
            big_col.enabled = False

        # big_col = output.column()
        # big_col.scale_y = 1.5
        # if "Annotations" in bpy.data.grease_pencils and not rbdlab.in_annotation_mode:
        #     if len(bpy.data.grease_pencils["Annotations"].layers) > 0:
        #         big_col.operator("gpencil.layer_annotation_remove", text="Clear Annotations")

        if rbdlab.filtered_target_collection:
            col = output.column()
            row = col.row(align=True)
            row.alignment = 'EXPAND'
