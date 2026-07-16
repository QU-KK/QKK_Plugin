from ...addon.naming import RBDLabNaming
from ..common_ui_elements import collapsable

def draw_constraint_groups(layout, ui, rbdlab_const, active_group):

    main_col = layout.box().column(align=True)

    # CONSTRAINT GROUPS ui list
    # +++++++++++++++++++++++++++++++++

    section = main_col.column(align=True)

    header = section.box().row(align=True)
    header.label(text="Constraints Groups", icon='STICKY_UVS_LOC')
    section.template_list("CONST_UL_const_group", "", rbdlab_const, "group_list", rbdlab_const, "active_group_index", rows=3)

    if active_group:
        information = collapsable(
            main_col,
            ui,
            "show_const_group_info",
            "Information",
            'INFO',
            align=True,
        )
        if information:
            information.label(text=RBDLabNaming.WORKING_WITH + active_group.name)
            information.label(text="Total Constraints " + str(active_group.total_constrainst))

    main_col.separator()

    return main_col