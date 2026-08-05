from ...common_ui_elements import collapsable, multiline_print
from ....addon.naming import RBDLabNaming


def panel_initial_velocity(rbdlab, ui, layout):

    ui = rbdlab.ui
    main_col = layout.box().column(align=True)
    
    if rbdlab.low_or_high_visibility_viewport != "Low":
        main_col.enabled = False

    row = main_col.row(align=True)

    initial_velocity = main_col.column(align=True)

    header = initial_velocity.box().row(align=True)
    header.label(text="Transformations", icon='ORIENTATION_GLOBAL')

    force = initial_velocity.column(align=True)
    force.use_property_split = True
    # force.row().prop(rbdlab.activators, "force_mode", expand=True)

    # Direction/Location and explode:
    direction = collapsable(
        force,
        ui,
        "show_activators_direction",
        "Direction",
        'FORWARD',
        align=True,
    )
    if direction:
        direction.use_property_split = True
        dir_mode = direction.row(align=True)
        dir_mode.scale_y = 1.3
        dir_col = direction.column(align=True)

        dir_mode.prop(rbdlab.ui, "activators_force_loc_mode", text="Mode", toggle=True, expand=True)

        dir_col.separator()
        if rbdlab.ui.activators_force_loc_mode == 'CONST':
            dir_col.prop(rbdlab.activators, "force_direction", text="Direction", slider=True)
        elif rbdlab.ui.activators_force_loc_mode == 'RAND':
            rowx = dir_col.row()
            rowx.prop(rbdlab.activators, "force_x_min_loc_rand", text="Min Max X")
            rowx.prop(rbdlab.activators, "force_x_max_loc_rand", text="")
            rowy = dir_col.row()
            rowy.prop(rbdlab.activators, "force_y_min_loc_rand", text='Y')
            rowy.prop(rbdlab.activators, "force_y_max_loc_rand", text="")
            rowz = dir_col.row()
            rowz.prop(rbdlab.activators, "force_z_min_loc_rand", text='Z')
            rowz.prop(rbdlab.activators, "force_z_max_loc_rand", text="")
        elif rbdlab.ui.activators_force_loc_mode == 'EXPLODE':
            row = dir_col.row(align=True)
            row.prop(rbdlab.activators, "force_explode_amount", text="Amount")
            row.operator("rbdlab.act_explode_done", text="Done")

            if rbdlab.activators.activators_show_explode_amount_feedback != "":
                flow = dir_col.grid_flow(row_major=True, columns=2, even_columns=False, even_rows=False, align=True)
                empty = flow.row(align=True)
                empty.label(text="")
                empty.scale_x = 5.15
                msg_feedback = flow.box().row(align=True)
                msg_feedback.scale_x = .92
                amount_number = rbdlab.activators.activators_show_explode_amount_feedback[:7]
                msg_feedback.label(text="Amount Set with: " + amount_number)
                # msg_feedback.alignment = 'RIGHT'
                dir_col.separator()

            row = dir_col.row(align=True)
            row.prop(rbdlab.activators, "explode_empty_size", text="Centroid Size")
            row.prop(rbdlab.activators, "explode_centroid_visibility", text="", icon='HIDE_OFF')
            row.prop(rbdlab.activators, "explode_centroid_select", text="", icon='RESTRICT_SELECT_OFF')

            mult_offset = direction.column(align=True)
            mult_offset.prop(rbdlab.activators, "force_explode_scale", text="Multiplier", slider=True)
            mult_offset.prop(rbdlab.activators, "force_explode_frame_offset", text="Offset", slider=True)

            # dir_col.separator()
            # dir_col.use_property_split = False
            # row = dir_col.row(align=True, heading="Ease In-Out")
            # row.prop(rbdlab.activators, "force_exp_ease_in", text="", slider=True)
            # row.prop(rbdlab.activators, "force_exp_ease_out", text="", slider=True)

        if rbdlab.ui.activators_force_loc_mode != 'EXPLODE':
            direction.separator()
            direction.prop(rbdlab.activators, "force_loc_scale", text="Multiplier", slider=True)
            direction.prop(rbdlab.activators, "force_loc_frame_offset", text="Offset", slider=True)

            direction.separator()
            row = direction.row(align=True)
            row.prop(rbdlab.activators, "force_loc_ease_in", text="Ease In-Out", slider=True)
            row = row.row(align=True)
            row.prop(rbdlab.activators, "force_loc_ease_out", text="", slider=True)

    # force.separator()
    # Rotation:
    rotation = collapsable(
        force,
        ui,
        "show_activators_rotation",
        "Rotation",
        'MOD_SCREW',
        align=True,
    )
    if rotation:
        rot_mode = rotation.row(align=True)
        rot_mode.scale_y = 1.3
        rot_col = rotation.column(align=True)
        rot_mode.prop(rbdlab.ui, "activators_force_rot_mode", text="Mode", toggle=True, expand=True)
        rot_col.separator()
        if rbdlab.ui.activators_force_rot_mode == 'CONST':
            rot_col.prop(rbdlab.activators, "force_rotation", text="Rotation", slider=True)
        else:
            rowx = rot_col.row()
            rowx.prop(rbdlab.activators, "force_x_min_rot_rand", text="Min Max X")
            rowx.prop(rbdlab.activators, "force_x_max_rot_rand", text="")
            rowy = rot_col.row()
            rowy.prop(rbdlab.activators, "force_y_min_rot_rand", text='Y')
            rowy.prop(rbdlab.activators, "force_y_max_rot_rand", text="")
            rowz = rot_col.row()
            rowz.prop(rbdlab.activators, "force_z_min_rot_rand", text='Z')
            rowz.prop(rbdlab.activators, "force_z_max_rot_rand", text="")

        rotation.separator()
        rotation.prop(rbdlab.activators, "force_rot_scale", text="Multiplier", slider=True)
        rotation.prop(rbdlab.activators, "force_rot_frame_offset", text="Offset", slider=True)

        rotation.separator()
        row = rotation.row(align=True)
        row.prop(rbdlab.activators, "force_rot_ease_in", text="Ease In-Out", slider=True)
        row = row.row(align=True)
        row.prop(rbdlab.activators, "force_rot_ease_out", text="", slider=True)


    if rbdlab.ui.activators_force_loc_mode == 'EXPLODE' and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
        force.separator()
        msg_done = force.column()

        text="Remember that to use the explode: You must first include chunks and Activators objects. Then also use the amount and then press Done button. Can press shift when use Amount."
        multiline_print(msg_done, text, max_words=7, first_line_crop=1)
        
        force.separator()

    prev_buttons = force.row(align=True)
    prev_buttons.scale_y = 1.3
    preview_bt = prev_buttons.row(align=True)
    clear_bt = prev_buttons.row(align=True)

    # preview_bt.operator("rbdlab.act_record", text="Preview").mode = 'FORCE_PREVIEW'
    if rbdlab.filtered_target_collection:
        
        # if "activators_force_preview_recorded" in rbdlab.filtered_target_collection:
        #     clear_bt.alert = True
        #     clear_bt.operator("rbdlab.act_rm_record", text="Clear Preview", icon='TRASH').mode = 'FORCE_PREVIEW'
        #     preview_bt.enabled = False
        #     # print('8')

        if "activators_recorded" in rbdlab.filtered_target_collection:
            prev_buttons.enabled = False
            # print('7')
    else:
        preview_bt.enabled = False
        prev_buttons.enabled = False
        # print('6')

    if rbdlab.ui.activators_force_loc_mode == 'EXPLODE' and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
        preview_bt.enabled = False
        # print('5')
