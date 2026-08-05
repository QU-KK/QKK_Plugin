import bpy
from ..common_ui_elements import collapsable


def brekeable_disable(const_settings, rbdlab, ui, rbdlab_const):

    flow = const_settings.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)

    brekeable = flow.row(align=True)
    brekeable.use_property_split = False
    disable = flow.row(align=True)
    disable.use_property_split = False

    brekeable.prop(rbdlab_const, "breakable", text="Breakable")
    
    if ui.active_const_tab == 'EDIT':
        brekeable.scale_x = 0.5
        set_anim_b_add = brekeable.row(align=True)
        set_anim_b_add.alignment = 'RIGHT'
        set_anim_b_rm = brekeable.row(align=True)
        set_anim_b_rm.alignment = 'LEFT'

        set_anim_b_add.operator("rbdlab.const_set_anim_brekeable", text="", icon='KEY_HLT')
        set_anim_b_rm.operator("rbdlab.const_set_anim_brekeable_remove", text="", icon='KEY_DEHLT')
        sz_bt = 2.5
        set_anim_b_add.scale_x = sz_bt
        set_anim_b_rm.scale_x = sz_bt

        if len(rbdlab_const.group_list) > 0:
            _collection = rbdlab_const.group_list[rbdlab_const.active_group_index-1].collection
            if _collection and _collection.name in bpy.data.collections:
                collection = bpy.data.collections[_collection.name]
                if "constraints_brekeable_keyframes_text" in collection:
                    if collection["constraints_brekeable_keyframes_text"]:
                        const_settings.separator()
                        box = const_settings.box()
                        # box.alert = True
                        n = 0
                        for text in collection["constraints_brekeable_keyframes_text"].split(
                                "#####"):
                            if n == 0:
                                box.label(text=rbdlab.keyframes_added_text + ":" + text, icon='INFO')
                            else:
                                box.label(text=text)
                            n += 1
                        set_anim_b_add.enabled = False
                        # content.separator()
        # brekeable.separator()

    else:
        void_space = brekeable.row(align=True)
        void_space.scale_x = 0.6
        void_space.label(text=" ")

    if ui.active_const_tab == 'CREATION':
        brekeable.separator()
        disable.prop(rbdlab_const, "disable_collisions", text="Disable Collisions")
    
    elif ui.active_const_tab == 'EDIT':
        disable.prop(rbdlab_const, "disable_collisions", text="Disable Collisions")
        disable.scale_x = 1
        const_settings.separator()


def glue_strength_and_iterations(const_settings, rbdlab_const):
    
    flow = const_settings.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)
    # flow.alignment = 'LEFT'

    glue = flow.row(align=True)
    glue.use_property_split = False
    iter_cbox = flow.row(align=True)
    iter_cbox.use_property_split = False

    if rbdlab_const.apply_by == 'CLUSTER':
        sub = glue.row(align=True)
        txt1 = "" if rbdlab_const.glue_strength_mode else "Strength"
        sub.prop(rbdlab_const, "glue_strength_mode", text=txt1)

        # Optional constant strength or random range ( in clusters for now ):
        if rbdlab_const.glue_strength_mode:
            s_range = sub.row(align=True)
            s_range.prop(rbdlab_const, "glue_strength_range", text="Random")
        else:
            sub.prop(rbdlab_const, "glue_strength", text="")

    else:
        glue.use_property_split = True
        # glue.alignment = 'LEFT'
        s_label = glue.row(align=True)
        s_label.scale_x = 1.7
        s_label.label(text="Strength")
        glue.prop(rbdlab_const, "glue_strength", text=" ")
        # row.operator("rbdlab.const_set_glue_keyframes", text="", icon='KEY_HLT')
        # row.operator("rbdlab.const_rm_all_glue_keyframes", text="", icon='KEY_DEHLT')

    # iter_cbox = flow.row(heading="Iterations")
    iter_cbox.prop(rbdlab_const, "override_iterations", text="Iterations")
    # iter_cbox.scale_x = 0.2

    sub = iter_cbox.row(align=True)
    sub.use_property_split = True    
    sub.prop(rbdlab_const, "iterations", text="")
    # sub.scale_x = 1.2
    sub.active = rbdlab_const.override_iterations
    const_settings.separator(factor=0.4)


def limit_constraints(const_settings, ui, rbdlab_const):
    if ui.active_const_tab == 'CREATE':
        limit = const_settings.column(align=True)
        limit.use_property_split = False
        
        limit_constraints_e = limit.row(align=True)
        limit_constraints_e.enabled = not rbdlab_const.filter_adjacents
        limit_constraints_e.prop(rbdlab_const, "limit_neighbor_constraints", text="Limit Constraints")
        limit_constraints = limit_constraints_e.row(align=True)
        limit_constraints.enabled = rbdlab_const.limit_neighbor_constraints
        limit_constraints.separator(factor=1.3)
        limit_constraints.prop(rbdlab_const, "maximun_neighbor_constraints", text="")


def adjacents_and_attach(layout, const_settings, rbdlab, ui, rbdlab_const):
    # Adjacents:
    if ui.active_const_tab == 'CREATE':
        # Los adjacents no tienen sentido con los clusters:
        if rbdlab.constraints.apply_by != 'CLUSTER':    

            adjcnts_and_attach = const_settings.row(align=True)
            adjcnts_and_attach.use_property_split = False

            if not rbdlab_const.const_to_ob:
                adjcnts_and_attach.prop(rbdlab_const, "filter_adjacents", text="Adjacents")

            adjcnts_and_attach.prop(rbdlab_const, "const_to_ob", text="Attach Geometry")
            if rbdlab_const.const_to_ob:
                adjcnts_and_attach.prop(rbdlab_const, "to_ob_choose", text="")
            
            # Work with Adjacents:
            if rbdlab_const.filter_adjacents:

                const_settings = layout.box().column(align=True)

                # Recompute Neighbors:
                nsearch = const_settings.column(align=True)
                
                header_nsearch = nsearch.row(align=True)
                header_nsearch.scale_y = 0.4
                header_nsearch.label(text="Search Neighbors")
                nsearch.separator()

                neighbors_search = nsearch.row(align=True)
                neighbors_search.scale_y = 1.3
                neighbors_search.prop(rbdlab_const, "neighbors_search_method", expand=True)
                
                adjacents = const_settings.column(align=True)

                if rbdlab_const.neighbors_search_method != 'BBOX':
                # if rbdlab_const.neighbors_search_method != 'DISTANCE':
                    
                    adjacents.prop(rbdlab_const, "neighbors_virtual_cube_threshold")

                else:
                    # Por BoundingBox:
                    ##################
                    
                    bbox_off = nsearch.row(align=True)
                    if rbdlab_const.bbox_offset_unified_toggle:
                        bbox_off.prop(rbdlab_const, "bbox_offset_x", text="X")
                        bbox_off.prop(rbdlab_const, "bbox_offset_y", text="Y")
                        bbox_off.prop(rbdlab_const, "bbox_offset_z", text="Z")
                    else:
                        bbox_off.prop(rbdlab_const, "bbox_offset_unified", text="Offset")
                    bbox_off.prop(rbdlab_const, "bbox_offset_unified_toggle", text="", toggle=True, icon='TRIA_DOWN' if rbdlab_const.bbox_offset_unified_toggle else 'TRIA_LEFT')

                    # Por Distance:
                    ###############
                    # by_distance = adjacents.row(align=True)
                    # by_distance.prop(rbdlab_const, "threshold_adjacents_selection") # por proximidad
                    # increment = by_distance.row(align=True)
                    # increment.scale_x = 0.3
                    # increment.operator("rbdlab.select_debug_neighbours", text=" ", icon='PLUS').incremental = True

                adjacents.separator()
                adjacents.prop(rbdlab_const, "adjacents_only_between_different_froms", text="(Restriction) Adjacents with different froms")

                # Select Adjacents:
                const_settings.separator(factor=0.5)
                row_adjacents = adjacents.row(align=True)
                row_adjacents.scale_y = 1.3
                row_adjacents.operator("rbdlab.select_adjacents_neighbours", text="Select Adjacents", icon='RESTRICT_SELECT_OFF')

                increment = row_adjacents.row(align=True)
                increment.scale_x = 0.3
                increment.operator("rbdlab.select_debug_neighbours", text=" ", icon='PLUS').incremental = True
                


def per_island_and_between_chunks(const_settings, rbdlab, ui, rbdlab_const):
    # Between Chunks and Per Island: 
    if ui.active_const_tab == 'CREATE':
        per_island_and_between = const_settings.row(align=True)
        per_island_and_between.use_property_split = False
        per_island_and_between.prop(rbdlab_const, "const_per_islands", text="Per Islands")
        if rbdlab.constraints.apply_by != 'CLUSTER':
            per_island_and_between.prop(rbdlab_const, "constraints_between_chunks", text="Between Chunks")
            per_island_and_between.enabled = not rbdlab_const.const_to_ob


def draw_const_settings(layout, rbdlab, ui, rbdlab_const, active_group):

        const_settings = collapsable(
            layout,
            ui,
            "show_hide_constraint_settings",
            "Constraints Settings",
            'SETTINGS',
            align=True,
        )
        if const_settings:

            const_settings.use_property_split = False
            const_type = const_settings.row(align=True)
            const_type.scale_y = 1.3
            const_type.prop(rbdlab_const, "constraint_type", text="Type")

            all_dpaths = active_group.springs_list.get_all_dpaths_stored if active_group is not None else []

            # Spring (plasticidad)
            const_group = rbdlab.constraints.get_active_group
            if const_group is not None and rbdlab.constraints.constraint_type == 'GENERIC_SPRING' and ui.active_const_tab == 'EDIT':

                const_settings.prop(active_group, "spring_type")
                const_settings.separator()

                # (Limit Angle)
                limit_angle = collapsable(
                    const_settings,
                    ui,
                    "show_hide_constraint_spring_limit_angle",
                    "Limit Rotations",
                    align=True,
                )
                if limit_angle:
                    # use axis
                    limit_angle_row = limit_angle.row(align=True)
                    limit_angle_row.use_property_split = True
                    limit_angle_row.prop(active_group, "use_limit_ang_x", text="X", toggle=True)
                    limit_angle_row.prop(active_group, "use_limit_ang_y", text="Y", toggle=True)
                    limit_angle_row.prop(active_group, "use_limit_ang_z", text="Z", toggle=True)
                    
                    limit_angle.use_property_split = True
                    
                    limit_angle.prop(active_group, "limit_ang_both_uniq", text="Rotation")

                    # limit_angle.separator()
                    # lowers_xyz = limit_angle.row()
                    # if active_group.limit_ang_lowers_uniq:
                    #     lowers_xyz.prop(active_group, "limit_ang_x_lower", text="Lowers XYZ")
                    #     lowers_xyz.prop(active_group, "limit_ang_y_lower", text="")
                    #     lowers_xyz.prop(active_group, "limit_ang_z_lower", text="")
                    #     lowers_xyz.prop(active_group, "limit_ang_lowers_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    # else:
                    #     lowers_xyz.prop(active_group, "limit_ang_lower_uniq", text="Lowers XYZ")
                    #     lowers_xyz.prop(active_group, "limit_ang_lowers_uniq", text="", toggle=True, icon='TRIA_LEFT')

                    # uppers_xyz = limit_angle.row()
                    # if active_group.limit_ang_uppers_uniq:
                    #     uppers_xyz.prop(active_group, "limit_ang_x_upper", text="Uppers XYZ")
                    #     uppers_xyz.prop(active_group, "limit_ang_y_upper", text="")
                    #     uppers_xyz.prop(active_group, "limit_ang_z_upper", text="")
                    #     uppers_xyz.prop(active_group, "limit_ang_uppers_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    # else:
                    #     uppers_xyz.prop(active_group, "limit_ang_upper_uniq", text="Uppers XYZ")
                    #     uppers_xyz.prop(active_group, "limit_ang_uppers_uniq", text="", toggle=True, icon='TRIA_LEFT')

                # (Limit Linear)
                limit_linear = collapsable(
                    const_settings,
                    ui,
                    "show_hide_constraint_spring_limit_linear",
                    "Limit Linear Distance",
                    align=True,
                )
                if limit_linear:
                    # use axis
                    limit_linear_row = limit_linear.row(align=True)
                    limit_linear_row.use_property_split = True
                    limit_linear_row.prop(active_group, "use_limit_lin_x", text="X", toggle=True)
                    limit_linear_row.prop(active_group, "use_limit_lin_y", text="Y", toggle=True)
                    limit_linear_row.prop(active_group, "use_limit_lin_z", text="Z", toggle=True)

                    limit_linear.use_property_split = True

                    limit_linear.prop(active_group, "limit_lin_both", text="Distance")

                    # limit_linear.separator()
                    # lowers_xyz = limit_linear.row()
                    # if active_group.limit_lin_lowers_uniq:
                    #     lowers_xyz.prop(active_group, "limit_lin_x_lower", text="Lowers XYZ")
                    #     lowers_xyz.prop(active_group, "limit_lin_y_lower", text="")
                    #     lowers_xyz.prop(active_group, "limit_lin_z_lower", text="")
                    #     lowers_xyz.prop(active_group, "limit_lin_lowers_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    # else:
                    #     lowers_xyz.prop(active_group, "limit_lin_lower_uniq", text="Lowers XYZ")
                    #     lowers_xyz.prop(active_group, "limit_lin_lowers_uniq", text="", toggle=True, icon='TRIA_LEFT')

                    # uppers_xyz = limit_linear.row()
                    # if active_group.limit_lin_x_uppers_uniq:
                    #     uppers_xyz.prop(active_group, "limit_lin_x_upper", text="Uppers XYZ")
                    #     uppers_xyz.prop(active_group, "limit_lin_y_upper", text="")
                    #     uppers_xyz.prop(active_group, "limit_lin_z_upper", text="")
                    #     uppers_xyz.prop(active_group, "limit_lin_x_uppers_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    # else:
                    #     uppers_xyz.prop(active_group, "limit_lin_upper_uniq", text="Uppers XYZ")
                    #     uppers_xyz.prop(active_group, "limit_lin_x_uppers_uniq", text="", toggle=True, icon='TRIA_LEFT')

                # (Spring Angle)
                spring_limit_angle = collapsable(
                    const_settings,
                    ui,
                    "show_hide_constraint_spring_spring_angle",
                    "Spring Angle",
                    align=True,
                )
                if spring_limit_angle:
                    # use axis
                    spring_limit_angle_row = spring_limit_angle.row(align=True)
                    spring_limit_angle_row.use_property_split = True
                    spring_limit_angle_row.prop(active_group, "use_spring_ang_x", text="X", toggle=True)
                    spring_limit_angle_row.prop(active_group, "use_spring_ang_y", text="Y", toggle=True)
                    spring_limit_angle_row.prop(active_group, "use_spring_ang_z", text="Z", toggle=True)

                    spring_limit_angle.use_property_split = True
                    
                    # Stiffness Angle:
                    Stiffness_xyz = spring_limit_angle.row()
                    if active_group.springs_stiffness_ang_uniq:
                        Stiffness_xyz.prop(active_group, "spring_stiffness_ang_x", text="Stiffness")
                        Stiffness_xyz.prop(active_group, "spring_stiffness_ang_y", text="")
                        Stiffness_xyz.prop(active_group, "spring_stiffness_ang_z", text="")
                        Stiffness_xyz.prop(active_group, "springs_stiffness_ang_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    else:
                        Stiffness_xyz.prop(active_group, "spring_stiffness_ang_uniq", text="Stiffness")
                        Stiffness_xyz.prop(active_group, "springs_stiffness_ang_uniq", text="", toggle=True, icon='TRIA_LEFT')

                    Stiffness_xyz.enabled = "rigid_body_constraint.spring_stiffness_ang_x" not in all_dpaths
                    
                    # Damping Angle:
                    Damppings_xyz = spring_limit_angle.row()
                    if active_group.springs_damping_ang_uniq:
                        Damppings_xyz.prop(active_group, "spring_damping_ang_x", text="Dampings")
                        Damppings_xyz.prop(active_group, "spring_damping_ang_y", text="")
                        Damppings_xyz.prop(active_group, "spring_damping_ang_z", text="")
                        Damppings_xyz.prop(active_group, "springs_damping_ang_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    else:
                        Damppings_xyz.prop(active_group, "spring_damping_ang_uniq", text="Dampings")
                        Damppings_xyz.prop(active_group, "springs_damping_ang_uniq", text="", toggle=True, icon='TRIA_LEFT')
                    
                    Damppings_xyz.enabled = "rigid_body_constraint.spring_damping_ang_x" not in all_dpaths

                # (Spring Limit Linear)
                spring_limit_linear = collapsable(
                    const_settings,
                    ui,
                    "show_hide_constraint_spring_spring_linear",
                    "Spring Linear",
                    align=True,
                )
                if spring_limit_linear:
                    # use axis
                    limit_linear_row = spring_limit_linear.row(align=True)
                    limit_linear_row.use_property_split = True
                    limit_linear_row.prop(active_group, "use_spring_x", text="X", toggle=True)
                    limit_linear_row.prop(active_group, "use_spring_y", text="Y", toggle=True)
                    limit_linear_row.prop(active_group, "use_spring_z", text="Z", toggle=True)

                    spring_limit_linear.use_property_split = True

                    # Stiffness Linear:
                    lowers_xyz = spring_limit_linear.row()
                    if active_group.springs_stiffness_uniq:
                        lowers_xyz.prop(active_group, "spring_stiffness_x", text="Stiffness")
                        lowers_xyz.prop(active_group, "spring_stiffness_y", text="")
                        lowers_xyz.prop(active_group, "spring_stiffness_z", text="")
                        lowers_xyz.prop(active_group, "springs_stiffness_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    else:
                        lowers_xyz.prop(active_group, "spring_stiffness_uniq", text="Stiffness")
                        lowers_xyz.prop(active_group, "springs_stiffness_uniq", text="", toggle=True, icon='TRIA_LEFT')

                    lowers_xyz.enabled = "rigid_body_constraint.spring_stiffness_x" not in all_dpaths

                    # Damping Linear:
                    uppers_xyz = spring_limit_linear.row(align=True)
                    if active_group.springs_damping_uniq:
                        uppers_xyz.prop(active_group, "spring_damping_x", text="Damping")
                        uppers_xyz.prop(active_group, "spring_damping_y", text="")
                        uppers_xyz.prop(active_group, "spring_damping_z", text="")
                        uppers_xyz.prop(active_group, "springs_damping_uniq", text="", toggle=True, icon='TRIA_DOWN')
                    else:
                        uppers_xyz.prop(active_group, "spring_damping_uniq", text="Damping")
                        uppers_xyz.prop(active_group, "springs_damping_uniq", text="", toggle=True, icon='TRIA_LEFT')
                    
                    uppers_xyz.enabled = "rigid_body_constraint.spring_damping_x" not in all_dpaths
                    
            
            # const_settings.separator()
            # const_settings.separator()
            if ui.active_const_tab == 'EDIT':
                const_settings.separator()
    
            # End Spring

            # Constraint Settings:
            #---------------------------------------------------------------------------------------------------------

            const_settings.use_property_split = True

            brekeable_disable(const_settings, rbdlab, ui, rbdlab_const)

            # const_settings.separator()

            glue_strength_and_iterations(const_settings, rbdlab_const)
            
            limit_constraints(const_settings, ui, rbdlab_const)

            # HR -------------------------------------------
            if ui.active_const_tab == 'CREATE':
                const_settings = layout.box().column(align=True)

            # Checkboxes:
            # ------------------------------------------------------------------------------------------------

            per_island_and_between_chunks(const_settings, rbdlab, ui, rbdlab_const)    

            adjacents_and_attach(layout, const_settings, rbdlab, ui, rbdlab_const)

            # const_settings.separator()
