from ....props.constraints.constraints import RBDLab_PG_Constraints


def panel_constraints(rbdlab, layout):

    layout = layout.box()
    
    main_col = layout.column(align=True)
    main_col.use_property_split = True

    rbdlab_const: RBDLab_PG_Constraints = rbdlab.constraints
    header = main_col.box().row(align=True)
    header.label(text="Constraints Groups", icon='STICKY_UVS_LOC')
    main_col.template_list("CONST_UL_const_group", "", rbdlab_const, "group_list", rbdlab_const, "active_group_index", rows=3)
