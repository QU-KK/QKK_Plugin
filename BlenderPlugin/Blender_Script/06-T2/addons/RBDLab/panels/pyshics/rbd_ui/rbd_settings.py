from ....addon.naming import RBDLabNaming
from ...common_ui_elements import collapsable, draw_collision_collections
from ....Global.get_common_vars import get_common_vars


def rbd_settings(context, rbdlab, layout, ui, ob, have_rbd, have_rbdlab_boolean_mod, fracture_applied, working_in_inner_details):

    rbd_props = rbdlab.physics.rigidbodies
    rbd_animation_porps = rbd_props.animation

    tcoll_list = get_common_vars(context, get_tcoll_list=True)
    tcoll = tcoll_list.active

    if tcoll:
        tcoll_item = tcoll_list.active_item
        metal_props = tcoll_item.metal_props

    all_lay = layout.column(align=True)
    all_lay.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

    sublayout = all_lay.column(align=True)
    sublayout.use_property_split = True
    sublayout.use_property_decorate = False



    rbd_world = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_acuracy",
        "RigidBody World",
        'WORLD',
        align=True,
    )
    if rbd_world:

        scene = context.scene
        rbw = scene.rigidbody_world
        if rbw:
            rbd_world.prop(rbw.point_cache, "frame_start", text="Simulation Start")
            rbd_world.prop(rbw.point_cache, "frame_end", text="Simulation End")
            rbd_world.separator()

            substeps = rbd_world.row(align=True)
            substeps.prop(rbw, "substeps_per_frame")
            substeps.enabled = not rbd_animation_porps.substeps_animated
            
            s_iterations = rbd_world.row(align=True)
            s_iterations.prop(rbw, "solver_iterations")
            s_iterations.enabled = not rbd_animation_porps.s_iterations_animated

            world_seed = rbd_world.row(align=True)
            world_seed.prop(rbw, "time_scale", text="World Speed")
            world_seed.enabled = not rbd_animation_porps.world_speed_animated

        else:
            rbd_world.box().label(
                text="No rigid bodies at the moment in the scene", icon='INFO')

    rbd_settings = collapsable(
        sublayout,
        ui,
        "show_hide_physics_rbd_settings",
        "RigidBody Settings",
        'SETTINGS',
        align=True,
    )
    if rbd_settings:

        cboxes = rbd_settings.column(align=True)
        actions = cboxes.column(align=True)
        
        # esto solo lo ejecuta el boton de add, por eso lo oculto cuando estamos en update:
        if not have_rbd:
            rm_low_mass = actions.row(align=True)
            rm_low_mass.alignment = 'RIGHT'
            # rm_low_mass.use_property_split = False
            rm_low_mass.label(text="Remove chunks with extremely low mass")
            rm_low_mass2 = rm_low_mass.row(align=True)
            rm_low_mass2.alignment = 'LEFT'
            rm_low_mass2.prop(rbd_props, "rm_chunks_with_low_mass", text="")
            rm_low_mass2.separator(factor=2)

        if tcoll:
        
            actions.prop(metal_props, "metal_soft_mass", text="MetalSoft", toggle=True)
            if metal_props.metal_soft_mass:
                # para usar custom mass pero en forma de bool:
                actions.prop(rbd_props, "metal_mass", text=" ")
            
            else:

                actions.prop(rbd_props, "avalidable_mass", text="Mass")

                if rbd_props.avalidable_mass == "Custom":
                    actions.prop(rbd_props, "custom_mass", text="Custom:")


        cboxes.prop(rbd_props, "collision_shape", text="Shape")

        if tcoll:
            cboxes.prop(metal_props, "mesh_source", text="Source")


        rbd_settings.separator()
        actions = rbd_settings.row(align=True)

        col1 = actions.column(align=False, heading="Collision Margin")
        col1.use_property_decorate = False
        row = col1.row(align=True)
        sub = row.row(align=True)
        sub.prop(rbd_props, "use_collision_margin", text="")
        sub = sub.row(align=True)
        sub.active = rbd_props.use_collision_margin
        sub.prop(rbd_props, "collision_margin", text="")

        flow = col1.grid_flow(
            row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
        flow.use_property_split = False
        flow.prop(rbd_props, "rb_friction", text="Friction")
        flow.prop(rbd_props, "d_translation", text="Damp Translation")

        # col.prop(rbdlab, "dynamic", text="Dynamic")
        flow.prop(rbd_props, "restitution", text="Bounciness")
        flow.prop(rbd_props, "d_rotation", text="Damp Rotation")

    # col.prop(rbdlab, "deactivation", text="Deactivation")
    ### Deactivation ############################################################

    show_options = collapsable(
        sublayout,
        ui,
        "show_deactivation",
        "Deactivation",
        'LOCKVIEW_OFF',
        align=True,
    )
    if show_options:
        row1 = show_options.row(align=True)
        row2 = show_options.row(align=True)
        decol = row2.column(align=True)
        decol.enabled = rbd_props.deactivation
        row1.prop(rbd_props, "deactivation", text="Deactivation")
        decol.prop(rbd_props, "use_start_deactivated", text="Start Deactivated")
        decol.prop(rbd_props, "deactivate_linear_velocity", text="Linear Velocity")
        decol.prop(rbd_props, "deactivate_angular_velocity", text="Angular")

    passives_by_sel = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_passives_by_sel",
        "Passives by Selection",
        'FREEZE',
        align=True,
    )
    if passives_by_sel:
        row1 = passives_by_sel.row(align=True)
        # row.label(text="Selected to Passive")

        # hide/unhide
        if not rbd_props.show_hide_passives:
            hide_icon = 'HIDE_ON'
        else:
            hide_icon = 'HIDE_OFF'

        row1.operator("rbdlab.set_passive", text="Set Passive")
        row1.scale_y = 1.3
        row1.prop(rbd_props, "show_hide_passives", text="", toggle=False, icon=hide_icon)
        row1.operator("rbdlab.set_passive_select", text="", icon='RESTRICT_SELECT_OFF')
        # row1.separator()
        row1.alert = True
        row1.scale_x = 1.2
        row1.operator("rbdlab.set_passive_remove", text="", icon='TRASH')

        row1.enabled = working_in_inner_details

    join_separate_by_sel = collapsable(
        sublayout,
        ui,
        "show_hide_rbd_merge_by_sel",
        "Join by Selection",
        'MOD_TRIANGULATE',
        align=True,
    )
    if join_separate_by_sel:
        join_separate_by_sel_row = join_separate_by_sel.row(align=True)
        join_separate_by_sel_row.scale_y = 1.3
        join_separate_by_sel_row.operator("rbdlab.join_by_selection", text="Join")
        join_separate_by_sel_row.operator("rbdlab.separate_by_selection", text="Separate")

    if have_rbdlab_boolean_mod:
        if not fracture_applied:
            label = sublayout.row().box()
            # label.alert = True
            label.label(text="Apply Fracture to add Rigidbody!", icon='INFO')
            sub.enabled = False
    
    if ob:
        collections = collapsable(
            sublayout,
            ui,
            "show_hide_rbd_collections",
            "Collision Collections",
            'OUTLINER_COLLECTION',
            align=True,
        )
        if collections:
            col = draw_collision_collections(collections, ob, "rbd_collections")
            col.enabled = have_rbd

    buttons = sublayout.box().row(align=True)
    buttons.scale_y = 1.3
    if not have_rbd:
        # sub.enabled = not rbdlab.working_in_inner_details and has_chunk and not have_rbdlab_boolean_mod
        buttons.operator("rbdlab.rigidbody_add", text="Add RigidBodies")
    else:
        buttons.operator("rbdlab.rigidbody_update", text="Update", icon='FILE_REFRESH')
        remove_op = buttons.row(align=True)
        remove_op.alert = True
        remove_op.operator("rbdlab.rigidbody_rm", text="Remove Rigid Bodies", icon='TRASH')

    if rbdlab.low_or_high_visibility_viewport != "Low":
        sublayout.enabled = False
        sublayout.box().label(text="Please, working in low visualization mode!", icon='ERROR')
    else:
        sublayout.enabled = True

    # 1.1 HOTFIX.
    # Draw buttons anyways and also show some alert if apply fracture is needed.
    has_chunk = ob is not None

    # col.enabled = has_chunk and fracture_applied
    # col.enabled = has_chunk and not have_rbdlab_boolean_mod
    sublayout.enabled = not rbdlab.working_in_inner_details and has_chunk and not have_rbdlab_boolean_mod

    # si muteo los rbd en esta collection:
    current_active_tcoll = rbdlab.lists.target_coll_list.active
    if current_active_tcoll:
        sublayout.enabled = not RBDLabNaming.RBD_DISABLED in current_active_tcoll
