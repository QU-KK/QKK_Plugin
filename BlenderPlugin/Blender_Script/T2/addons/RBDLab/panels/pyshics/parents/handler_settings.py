from ...common_ui_elements import collapsable


def handler_settings(rbdlab, layout, ui, ob):

    subslayout = layout.column(align=True)
    subslayout.enabled = ob is not None

    # handler
    handler_settings = collapsable(
        subslayout,
        ui,
        "show_hide_physics_handler",
        "Handler Settings",
        'MESH_CUBE',
        align=True,
    )
    if handler_settings:
        hrow = handler_settings.row(align=True)
        hrow.scale_y = 1.3
        # hrow.enabled = not rbdlab.working_in_inner_details and has_chunk and not have_rbdlab_boolean_mod
        hrow.operator("rbdlab.rigidbody_add_handler", text="Add Handler", icon='MESH_CUBE')

        hrow.use_property_split = False
        # hrow.separator()
        hrow.prop(rbdlab.physics.rigidbodies, "edit_handler_toggle", text="Edit Transforms", toggle=True, icon='GREASEPENCIL')
        hrow.enabled = not rbdlab.physics.rigidbodies.show_hide_handler_toggle
        
        rm_handler = hrow.row(align=True)
        rm_handler.alert = True
        rm_handler.scale_x = 0.35
        rm_handler.operator("rbdlab.rigidbody_rm_handler", text=" ", icon='TRASH')

        actions = handler_settings.row(align=True)
        hrow = actions.row(align=True)
        hrow.scale_y = 1.3
        hrow.use_property_split = False
        if rbdlab.physics.rigidbodies.show_hide_handler_toggle:
            text_show_hide = "Show"
            show_hide_icon = 'HIDE_OFF'
        else:
            text_show_hide = "Hide"
            show_hide_icon = 'HIDE_ON'

        hrow.prop(rbdlab.physics.rigidbodies, "show_hide_handler_toggle", text=text_show_hide,
                  toggle=True, expand=True, icon=show_hide_icon)
        hrow.operator("rbd.reset_handler", text="Reset Handler", icon='FILE_REFRESH')
