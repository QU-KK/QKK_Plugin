from ...common_ui_elements import collapsable
from ....addon.naming import RBDLabNaming


def compound_settings(context, rbdlab, layout, ui, have_rbd):
    tcoll = rbdlab.filtered_target_collection
    rbd_props = rbdlab.physics.rigidbodies

    ### Parent Edge Compound #######################################################################################
    if tcoll:
        # si tienen rigidbodies o si esta hecho el bake a keyframes
        baked_to_keyframes = [obj for obj in tcoll.objects if RBDLabNaming.BAKED_TO_KFRAMES in obj]

        if have_rbd or len(baked_to_keyframes) > 0:
            if "rbdlab_fracture_helper_simple" in tcoll:

                edge_compound = collapsable(
                    layout,
                    ui,
                    "show_edge_parent_compound",
                    "Parent Edge Compound",
                    align=True,
                )
                if edge_compound:
                    if RBDLabNaming.EDGE_COMPOUND_PARENTED not in tcoll:

                        if not context.selected_objects:
                            edge_compound.label(text="First select the big chunks", icon='INFO')
                            edge_compound.separator()

                        parent_button = edge_compound.row(align=True)
                        parent_button.scale_y = 1.3
                        parent_button.operator("rbdlab.edges_pyshics_parent", text="Parent")

                        valid_objects_selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
                        if valid_objects_selected:
                            edge_compound.enabled = True
                        else:
                            edge_compound.enabled = False
                    else:
                        kt_button = edge_compound.row(align=True)
                        kt_button.use_property_split = False
                        kt_button.prop(rbd_props, "edge_remove_keep_transforms")

                        # sel_col = edge_compound.column(align=True)
                        # sel_col.use_property_split = False
                        # sel_buttons = sel_col.row(align=True)

                        # sel_buttons.scale_y = 1.2

                        rm_section_buttons = edge_compound.row(align=True)
                        rm_section_buttons.scale_y = 1.3

                        rm_section_buttons.alert = True
                        rm_section_buttons.operator("rbdlab.edges_pyshics_parent_remove",
                                                    text="Remove", icon='TRASH')
                        rm_section_buttons.alert = False

                        selection_button = rm_section_buttons.row(align=True)

                        selection_button.operator("rbdlab.select_compounds", text="", icon='RESTRICT_SELECT_OFF')

                        sel_buttons = rm_section_buttons.row(align=True)
                        sel_buttons.prop(rbd_props, "select_edges_parent_not_childs_compounds",
                                         text="", icon='RADIOBUT_OFF')
                        sel_buttons.prop(rbd_props, "select_edges_parent_childs_compounds",
                                         text="", icon='RADIOBUT_ON')

                        visibility_button = rm_section_buttons.row(align=True)
                        visibility_button.prop(
                            rbd_props, "edge_compound_visibility", text="", icon='HIDE_OFF'
                            if rbd_props.edge_compound_visibility else 'HIDE_ON', toggle=True)

                        if rbd_props.edge_compound_visibility:
                            selection_button.enabled = True
                        else:
                            selection_button.enabled = False
        else:
            layout.box().label(text="Not have rbd or are baked to keyframes", icon='INFO')

    else:
        layout.box().label(text="Not valid Target Collection", icon='INFO')

        # End Parent Edge Compound #####################################################################################
