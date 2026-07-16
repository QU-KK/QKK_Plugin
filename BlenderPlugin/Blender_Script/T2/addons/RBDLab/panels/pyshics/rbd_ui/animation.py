# from ....addon.naming import RBDLabNaming
from ...common_ui_elements import collapsable, multiline_print



def rbd_animation(context, rbdlab, layout, ui):


    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active
    if not tcoll:
        return
    
    dynamic_list = tcoll.rbdlab.dynamic_list
    rbdlab_physics = rbdlab.physics
    rbdlab_phscs_rbd = rbdlab_physics.rigidbodies
    rbd_animation_porps = rbdlab_phscs_rbd.animation

    all_lay = layout.column(align=True)
    all_lay.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

    sublayout = all_lay.column(align=True)
    layout.use_property_split = True
    layout.use_property_decorate = False

    rbd_dynamic = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_animation_dynamic",
        "RBD Dynamic",
        'ORIENTATION_GIMBAL',
        align=True,
    )
    if rbd_dynamic:

        if rbdlab_phscs_rbd.deactivation:
            text="Remember you have activated the 'Deactivation' option in your settings"
            multiline_print(rbd_dynamic, text, max_words=6, first_line_crop=2)

        rbd_dynamic.prop(rbd_animation_porps, "by_selection", text="By Selection")
        rbd_dynamic.template_list("RBDLAB_UL_draw_rbd_anim_dynamic", "", dynamic_list, "dynamic_list", dynamic_list, "list_index", rows=4)
        
        buttons_list = rbd_dynamic.row(align=True)
        buttons_list.scale_y = 1.3
        buttons_list.operator("rbdlab.physics_rbd_anim_add_off_on", text="Add")

        if not dynamic_list.is_void:
            rbd_dynamic.separator()
            offset = rbd_dynamic.row(align=True)
            offset.prop(rbd_animation_porps, "offset_duration", text="Offset Duration")
    
    # sublayout.separator()
    substeps_per_frame = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_animation_substeps_per_frame",
        "Substeps Per Frame",
        'GP_MULTIFRAME_EDITING',
        align=True,
    )
    if substeps_per_frame:
        substeps_per_frame.use_property_split = True
        substeps_per_frame.use_property_decorate = False

        grid = substeps_per_frame.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=2)
        
        txt0_left = grid.row(align=True)
        txt0_left.label(text="Frame")
        txt0_left.alignment = 'RIGHT'
        grid.prop(rbd_animation_porps, "substeps_frame", text="")
        
        txt1_left = grid.row(align=True)
        txt1_left.label(text="From | To")
        txt1_left.alignment = 'RIGHT'

        group1 = grid.row(align=True)
        grp1_ints = group1.row(align=True)

        grp1_ints.prop(rbd_animation_porps, "substeps_from", text="")
        grp1_ints.prop(rbd_animation_porps, "substeps_to", text="")

        substeps_per_frame.separator()
        button = substeps_per_frame.row()
        button.scale_y = 1.3
        button.label(text="")

        grid.enabled = not rbd_animation_porps.substeps_animated

        if rbd_animation_porps.substeps_animated:
            button.alert = True
            button.operator(
                "rbdlab.rbd_anim_rm_substep_per_frame_keyframes",
                text="Remove",
                icon='KEY_DEHLT')
        else:
            button.operator(
                "rbdlab.rbd_anim_add_substep_per_frame_keyframes",
                text="Add",
                icon='KEY_HLT')


    solver_iterations = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_animation_solver_iterations",
        "Solver Iterations",
        'MOD_SIMPLIFY',
        align=True,
    )
    if solver_iterations:
        solver_iterations.use_property_split = True
        solver_iterations.use_property_decorate = False

        grid = solver_iterations.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=2)
        
        txt0_left = grid.row(align=True)
        txt0_left.label(text="Frame")
        txt0_left.alignment = 'RIGHT'
        grid.prop(rbd_animation_porps, "s_iterations_frame", text="")

        txt1_left = grid.row(align=True)
        txt1_left.label(text="From | To")
        txt1_left.alignment = 'RIGHT'

        group1 = grid.row(align=True)
        grp1_ints = group1.row(align=True)

        grp1_ints.prop(rbd_animation_porps, "s_iterations_from", text="")
        grp1_ints.prop(rbd_animation_porps, "s_iterations_to", text="")

        solver_iterations.separator()
        button = solver_iterations.row()
        button.scale_y = 1.3
        button.label(text="")

        grid.enabled = not rbd_animation_porps.s_iterations_animated

        if rbd_animation_porps.s_iterations_animated:
            button.alert = True
            button.operator(
                "rbdlab.rbd_anim_rm_solver_iterations_keyframes",
                text="Remove",
                icon='KEY_DEHLT')
        else:
            button.operator(
                "rbdlab.rbd_anim_add_solver_iterations_keyframes",
                text="Add",
                icon='KEY_HLT')
    
    # el world speed se hará con el modulo principal de slow motion
    # world_speed = collapsable(
    #     sublayout,
    #     ui,
    #     "show_hide_rbd_animation_world_speed",
    #     "World Speed",
    #     'WORLD_DATA',
    #     align=True,
    # )
    # if world_speed:
    #     world_speed.use_property_split = True
    #     world_speed.use_property_decorate = False

    #     grid = world_speed.grid_flow(row_major=True, even_columns=True, even_rows=True, align=True, columns=2)
        
    #     txt0_left = grid.row(align=True)
    #     txt0_left.label(text="Frame")
    #     txt0_left.alignment = 'RIGHT'
    #     grid.prop(rbd_animation_porps, "world_speed_frame", text="")

    #     txt1_left = grid.row(align=True)
    #     txt1_left.label(text="From | To")
    #     txt1_left.alignment = 'RIGHT'

    #     group1 = grid.row(align=True)
    #     grp1_ints = group1.row(align=True)

    #     grp1_ints.prop(rbd_animation_porps, "world_speed_from", text="")
    #     grp1_ints.prop(rbd_animation_porps, "world_speed_to", text="")

    #     world_speed.separator()
    #     button = world_speed.row()
    #     button.scale_y = 1.3
    #     button.label(text="")

    #     grid.enabled = not rbd_animation_porps.world_speed_animated

    #     if rbd_animation_porps.world_speed_animated:
    #         button.alert = True
    #         button.operator(
    #             "rbdlab.rbd_anim_rm_world_speed_keyframes",
    #             text="Remove",
    #             icon='KEY_DEHLT')
    #     else:
    #         button.operator(
    #             "rbdlab.rbd_anim_add_world_speed_keyframes",
    #             text="Add",
    #             icon='KEY_HLT')
