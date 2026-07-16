from ...common_ui_elements import horizontal_line_separator


def panel_dynamics(layout, active_item):

    layout = layout.box()
    
    main_col = layout.column(align=True)
    main_col.use_property_split = True

    header = main_col.box().row(align=True)
    header.label(text="Dynamics Animations")
    main_col = horizontal_line_separator(main_col)
    
    start_mode = main_col.row(align=True)
    start_mode.scale_y = 1.3
    start_mode.use_property_split = False
    start_mode.prop(active_item, "start_on_off_toggle", text=" ", expand=True)

    main_col.label(text="Actions when activated:")
    actions = main_col.row(align=True)
    actions.use_property_split = False
    actions.scale_y = 1.3
    actions.prop(active_item, "actions", expand=True)
    
    main_col.separator()
    
    frames_btw = main_col.row(align=True)
    frames_btw.label(text="Frames Between Actions")
    fbtw = frames_btw.row(align=True)
    fbtw.scale_x = 0.6
    fbtw.prop(active_item, "frames_between_actions", text="")
    fbtw.enabled = active_item.actions == 'ON_OFF' or active_item.actions == 'OFF_ON'

    # main_col.use_property_split = False
    # main_col.prop(active_item, "copy_to_dynamic_anim", text="Copy To Dynamic Animation")