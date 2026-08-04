from ...addon.naming import RBDLabNaming
from ..common_ui_elements import multiline_print, horizontal_line_separator


def dswitch_visual_switching_panel(rbdlab, ui, layout):
    
    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active
    vs_props = rbdlab.physics.dswitch.visual_switching

    main_col = layout.column(align=True)

    siwtcher_type = main_col.row(align=True)
    siwtcher_type.scale_y = 1.3
    siwtcher_type.prop(ui, "visual_switch_type", expand=True)

    if tcoll is not None:
        # main_col = col.box().box().column(align=True)
        main_col = horizontal_line_separator(layout)

        # esta vez para que tenga el segundo box():
        main_col = horizontal_line_separator(main_col)

        main_col.use_property_split = True
        main_col.use_property_decorate = False

        # main_col.separator()

        if ui.visual_switch_type == 'FRAME_SWITCH':

            text = "Move the timeline to the exact moment where you want the switch to happen. Then press the switch button to create it."
            multiline_print(main_col, text, max_words=6, first_line_crop=0)
            main_col.separator()

            offset = main_col.row(align=True)
            offset.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED in tcoll
            offset.prop(vs_props, "offset", slider=True)

            main_col.separator()
            buttons = main_col.row(align=True)
            visibility_bt = buttons.row(align=True)
            visibility_bt.scale_y = 1.3
            visibility_bt.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED not in tcoll
            visibility_bt.operator("rbdlab.visual_switching", text="Switch Visibility")

            restore_bt = buttons.row(align=True)
            restore_bt.scale_y = 1.3
            restore_bt.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED in tcoll
            restore_bt.operator("rbdlab.visual_switching_restore", text="Restore")

        elif ui.visual_switch_type == 'DYNAMIC_SWITCH':

            # Broken:
            broken_motion = main_col.row(align=True)
            broken_motion.scale_y = 1.3
            broken_motion.prop(vs_props, "options")

            main_col.separator()
            distance_t = main_col.column(align=True)
            distance_t.box().row().label(text="Broken Settings", icon='MOD_PHYSICS')
            distance_t.box().prop(vs_props, "distance_threshold")
            distance_t.separator()

            # Motion:
            velocity_t = main_col.column(align=True)
            velocity_t.box().row().label(text="Motion Settings", icon='CURVE_PATH')
            velocity_t.box().prop(vs_props, "velocity_threshold")

            # ---------------------------------------------------------
            main_col.separator()
            offset = main_col.row(align=True)
            offset.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED in tcoll
            offset.prop(vs_props, "offset", slider=True)

            main_col.separator()
            buttons = main_col.row(align=True)
            vs_motions_bt = buttons.row(align=True)
            vs_motions_bt.scale_y = 1.3
            vs_motions_bt.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED not in tcoll
            vs_motions_bt.operator("rbdlab.visual_switching", text="Compute")

            restore_bt = buttons.row(align=True)
            restore_bt.scale_y = 1.3
            restore_bt.enabled = RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED in tcoll
            restore_bt.operator("rbdlab.visual_switching_restore", text="Restore")
