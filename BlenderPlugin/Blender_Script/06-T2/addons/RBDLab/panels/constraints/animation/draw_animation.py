from ....addon.naming import RBDLabNaming
from ...common_ui_elements import collapsable
from ..common_draw_constraint_groups_list import draw_constraint_groups


def draw_animation_tab(layout, rbdlab, ui, active_group):

    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active

    # si no hay grupo activo, o tcoll, no dibujamos nada:
    if not tcoll or not active_group:
        return
    
    rbdlab_const = rbdlab.constraints
    cswitch_list = tcoll.rbdlab.constswitch_list

    # draw constraint groups list:
    main_col = draw_constraint_groups(layout, ui, rbdlab_const, active_group)
    main_col.use_property_decorate = False
    main_col.use_property_split = False

    sc_by_group = collapsable(
        main_col,
        ui,
        "show_hide_const_switch_cons_by_group",
        "Switch Constraints by group",
        'CON_ACTION',
        align=True,
    )
    if sc_by_group:
        sc_by_group.prop(cswitch_list, "by_selection", text="By Selection")
        sc_by_group.template_list("RBDLAB_UL_draw_constswitch", "", cswitch_list, "constswitch_list", cswitch_list, "list_index", rows=4)
        
        add_bt = sc_by_group.row(align=True)
        add_bt.scale_y = 1.3
        add_bt.operator("rbdlab.const_constswitch_add", text="Enable/Disable")

        sw_bt = add_bt.row(align=True)
        sw_bt.operator("rbdlab.const_anim_enable_disable_switcher", text="Switcher between Groups")

    
    main_col.separator()
    ### Animation GlueStrength ############################################################
    rbdlab_const_active = rbdlab_const.get_active_group

    glue_stength = collapsable(
        main_col,
        ui,
        "show_hide_const_glue_strength_anim",
        "Glue Strength",
        'VPAINT_HLT',
        align=True,
    )
    if glue_stength:
        
        glue_strength_list = rbdlab_const_active.glue_strength_list

        glue_stength.prop(rbdlab_const, "glue_anim_by_selection", text="By Selection")
        glue_stength.template_list("RBDLAB_UL_draw_glue_strength_anim", "", glue_strength_list, "glue_strength_list", glue_strength_list, "list_index", rows=4)

        glue_add_kf = glue_stength.row(align=True)
        glue_add_kf.scale_y = 1.3
        glue_add_kf.operator("rbdlab.const_set_glue_keyframes", text="Add   ", icon='KEY_HLT')


    main_col.separator()
    springs_anim = collapsable(
        main_col,
        ui,
        "show_hide_const_springs_anim",
        "Springs",
        'MOD_SIMPLIFY',
        align=True,
    )
    if springs_anim:
        springs_list = rbdlab_const_active.springs_list
        springs_anim.prop(rbdlab_const, "springs_anim_by_selection", text="By Selection")
        springs_anim.template_list("RBDLAB_UL_draw_const_springs_anim", "", springs_list, "springs_list", springs_list, "list_index", rows=4)

        springs_add_kf = springs_anim.row(align=True)
        springs_add_kf.scale_y = 1.3
        springs_add_kf.operator("rbdlab.const_set_springs_keyframes", text="Add   ", icon='KEY_HLT')


    ### Iterations ############################################################
    # iterations = collapsable(
    #     main_col,
    #     ui,
    #     "show_hide_const_iterations_anim",
    #     "Iterations",
    #     'CON_ACTION',
    #     align=True,
    # )
    # if iterations:
    #     ints_x_scale = 1
    #     buttons_y_scale = 1.1

    #     coll = active_group.collection.rbdlab

    #     iterations = iterations.row(align=True)
        
    #     # flow:
    #     de_flow = iterations.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)

    #     # label:
    #     label_st_end = de_flow.row(align=True)
    #     label_st_end.alignment = 'RIGHT'
    #     label_st_end.label(text="Start | End")
        
    #     # int Start | To:
    #     iter_start = de_flow.row(align=True)
    #     iter_start.scale_x = ints_x_scale
    #     iter_start.prop(coll, "iter_start", text="")
    #     iter_start.enabled = not coll.iter_animed

    #     iter_end = de_flow.row(align=True)
    #     iter_end.scale_x = ints_x_scale
    #     iter_end.prop(coll, "iter_end", text="")
    #     iter_end.enabled = not coll.iter_animed

    #     # label From | To
    #     label_ft = de_flow.row(align=True)
    #     label_ft.alignment = 'RIGHT'
    #     label_ft.label(text="From | To")
        
    #     # int From | To:
    #     iter_start = de_flow.row(align=True)
    #     iter_start.scale_x = ints_x_scale
    #     iter_start.prop(coll, "iter_from", text="")
    #     iter_start.enabled = not coll.iter_animed

    #     iter_end = de_flow.row(align=True)
    #     iter_end.scale_x = ints_x_scale
    #     iter_end.prop(coll, "iter_to", text="")
    #     iter_end.enabled = not coll.iter_animed

        # bottones add y remove:
        # de_flow.label(text="")
        # de_buttons = de_flow.row(align=True)
        # de_buttons.scale_x = ints_x_scale
        # de_buttons.scale_y = buttons_y_scale
        # if active_group.disable_enable_animed:
        #     de_buttons.alert = True
        #     de_buttons.operator("rbdlab.const_operador_rm", text="Remove", icon='KEY_DEHLT').mode = "disable_to_enable"
        # else:
        #     de_buttons.operator("rbdlab.const_operador_add", text="Add"+size_hack, icon='KEY_HLT').mode = "disable_to_enable"

    # enable_disable_switcher = main_col.box().row(align=True)
    # enable_disable_switcher.scale_y = 1.3
    # enable_disable_switcher.operator("rbdlab.const_anim_enable_disable_switcher", text="Switcher")
