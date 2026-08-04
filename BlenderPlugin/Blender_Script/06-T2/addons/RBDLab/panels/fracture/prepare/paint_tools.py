from ...common_ui_elements import collapsable
from .proxy import proxy


def paint_tools(context, rbdlab, layout, ui):
    main_col = layout.box().column(align=True)

    # Subdivisions
    subdivision = collapsable(
        main_col,
        ui,
        "show_hide_paint_tools_subdivisions",
        "Subdivision",
        'MOD_SUBSURF',
        align=True,
    )
    if subdivision:

        subdivision.prop(rbdlab, "subdivision_level", text="Subdivision")
        if rbdlab.subdivision_level > 0:
            subdivision.prop(rbdlab, "subdivision_simple", text="Catmull Clark")

        if rbdlab.subdivision_level > 0:
            apply_button = subdivision.row(align=True)
            apply_button.scale_y = 1.3
            apply_button.operator("rbdlab.paint_tools_apply_subdivision", text="Apply", icon='CHECKMARK')

        if len(context.selected_objects) == 1:
            obj = context.selected_objects[0]
            if obj.type == 'MESH':
                if context.mode == 'OBJECT':
                    
                    # subdivision.enabled = True
                    subdivision.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

                else:
                    subdivision.enabled = False
            else:
                subdivision.enabled = False
        elif len(context.selected_objects) == 0:
            subdivision.enabled = False

    # paint
    paint = collapsable(
        main_col,
        ui,
        "show_hide_paint_tools_paint",
        "Paint",
        # 'BRUSH_PAINT_SELECT', # no existe en 3.2.2
        'GREASEPENCIL',
        align=True,
    )
    if paint:

        paint.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        start_end_col = paint.column(align=True)
        start_end_col.scale_y = 1.3
        clear_col = paint.column(align=True)
        clear_col.scale_y = 1.3

        if len(context.selected_objects) == 1:
            obj = context.selected_objects[0]
            if obj.type == 'MESH':
                if context.mode == 'PAINT_WEIGHT':
                    start_end_col.operator("rbdlab.goto_weightpaint", text="End Paint", icon='CHECKMARK')
                    start_end_col.enabled = True
                    clear_col.operator("rbdlab.clear_weightpaint", text="Clear")
                    clear_col.enabled = True
                else:
                    start_end_col.operator("rbdlab.goto_weightpaint", text="Start to Paint")

                if rbdlab.subdivision_level > 0:
                    start_end_col.enabled = False
                    clear_col.enabled = False
                else:
                    start_end_col.enabled = True
                    clear_col.enabled = True
            else:
                start_end_col.operator("rbdlab.goto_weightpaint", text="Start to Paint")
                start_end_col.enabled = False
        else:
            start_end_col.operator("rbdlab.goto_weightpaint", text="Start to Paint")
            start_end_col.enabled = False

    # annotate
    annotate = collapsable(
        main_col,
        ui,
        "show_hide_paint_tools_annotate",
        "Annotate",
        'STROKE',
        align=True,
    )
    if annotate:

        annotate.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        start_end_col = annotate.column(align=True)
        start_end_col.scale_y = 1.3
        clear_col = annotate.column(align=True)
        clear_col.scale_y = 1.3

        if not rbdlab.in_annotation_mode:
            start_end_col.operator("rbdlab.goto_annotation", text="Start to Annotation")
        else:
            start_end_col.operator("rbdlab.goto_annotation", text="End Annotation", icon='CHECKMARK')

        if rbdlab.in_annotation_mode:
            clear_col.operator("gpencil.layer_annotation_remove", text="Clear")

        if len(context.selected_objects) > 0:
            if any([obj for obj in context.selected_objects if obj.type != 'MESH']):
                start_end_col.enabled = False
                clear_col.enabled = False
            else:
                start_end_col.enabled = True
                clear_col.enabled = True


    # Proxy Section 
    proxy(context, main_col, rbdlab, ui)