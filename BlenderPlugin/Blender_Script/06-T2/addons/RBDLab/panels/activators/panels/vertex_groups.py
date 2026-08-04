from ...common_ui_elements import collapsable


def panel_vertex_group(ui, layout):

    main_col = layout.box().column(align=True)
    sub_box = main_col.box().column(align=True)
    
    sub_box.label(text="Layer Vertex Group Settings", icon='DOCUMENTS')
    sub_box = main_col.box().column(align=True)

    sub_box.use_property_split = True 
    
    sub_box.prop(ui, "dpaint_brush_influence_scale", slider=True)
    sub_box.prop(ui, "dpaint_brush_radius_scale", slider=True)

    dissolve = collapsable(
        main_col,
        ui,
        "dpaint_use_dissolve",
        "Use Dissolve",
        'CHECKBOX_HLT' if ui.dpaint_use_dissolve else 'CHECKBOX_DEHLT',
        align=True,
    )
    if dissolve:
        dissolve.use_property_split = True
        dissolve_time = dissolve.row(align=True)
        dissolve_time.enabled = ui.dpaint_use_dissolve
        dissolve_time.prop(ui,"dpaint_dissolve_speed")
        dissolve.prop(ui, "dpaint_use_dissolve_log")