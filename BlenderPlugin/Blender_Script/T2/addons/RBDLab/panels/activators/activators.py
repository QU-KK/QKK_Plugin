from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, multiline_print, horizontal_line_separator #, cheker_item_visibility

from .panels.dynamics import panel_dynamics
from .panels.initial_velocity import panel_initial_velocity
from .panels.vertex_groups import panel_vertex_group
from .panels.constraints import panel_constraints


def common_settings(context, layout, ui, rbdlab, active_item):

    common_setts = collapsable(
        layout,
        ui,
        "show_activators_common_settings",
        "Record Settings",
        'SETTINGS',
        align=True,
    )
    if common_setts:

        # settings_flow = common_setts.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        settings_flow = common_setts.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        settings_flow.use_property_split = True

        col_left = settings_flow.column(align=True)
        col_right = settings_flow.column(align=True)

        use_single_activ = col_left.row(align=True)
        use_single_activ.alignment = 'RIGHT'
        use_single_activ.label(text="Use Single Activation")
        use_single_activ.prop(ui, "use_single_activation", text=" ")

        # settings_flow.prop(active_item, "activator_margin", text="Margin")
        col_right.prop(ui, "activator_margin", text="Margin")

        common_setts = layout.box().column(align=True)
        common_setts.use_property_split = True

        settings_flow = common_setts.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        settings_flow.use_property_split = True

        col_left = settings_flow.column(align=True)
        col_right = settings_flow.column(align=True)

        use_auto_range = col_left.row(align=True)
        use_auto_range.alignment = 'RIGHT'
        use_auto_range.label(text="Auto Range")
        use_auto_range.prop(rbdlab.activators, "automatic_range_with_keyframes", text=" ")
        common_setts.separator(factor=0.5)

        if rbdlab.activators.automatic_range_with_keyframes:
            feedback = common_setts.row(align=True)
            # feedback.alignment = 'RIGHT'
            # responsive multiline print panel with:
            current_area = context.area
            if current_area.type == 'VIEW_3D':
                panel_width = context.region.width
                bias = 350
                mw = int(panel_width*bias/25000)
                # print(mw)
                text = "Automatic mode requires having keyframed animation on the Activator objects or their parents."
                multiline_print(feedback, text, max_words=mw, first_line_crop=0)

        else:
            substeps = common_setts.row(align=True)
            substeps.prop(rbdlab.activators, "rbdw_substeps_per_frame", text="Substeps")
            bt_grbw = substeps.row(align=True)
            bt_grbw.scale_x = 1
            bt_grbw.operator("rbdlab.transfer_substeps", text="", icon='WORLD')

            use_all_f = common_setts.row(align=True)
            use_all_f.prop(rbdlab.activators, "total_frames", text="Frames")
            use_all_f.operator("rbdlab.passive_total_frames_from_sim", text="", icon='PREVIEW_RANGE')

        # settings_flow.prop(ui, "activator_kf_offset", text="KF Offset")
        
        # settings_flow.prop(ui, "activator_extend", text="Extend")
        # settings_flow.prop(ui, "activator_offset_extend", text="Offset Extend")


def settings_section(rbdlab, layout, current_types, ACTIVATORS_OBJECTS, active_item):

    activators_list = active_item.activators_list
    main_col = layout.box().column(align=True)
    
    if ACTIVATORS_OBJECTS is not None:
        if not activators_list.is_void:


            if rbdlab.low_or_high_visibility_viewport != "Low":
                main_col.enabled = False
            
            # main_col.separator()

            # row = main_col.row(align=True)
            # row.label(text="Ignore already acetonizeds", icon='BLANK1')
            # row.prop(rbdlab.ui, "activators_ignore_acetonized", text="")

            activators_objects = main_col.column(align=True)
            # header_act_obs = activators_objects.box().row(align=True)
            # header_act_obs.label(text="Activators Objects", icon='LIGHTPROBE_SPHERE')

            # block1 = activators_objects.box().column(align=True)
            # block1.label(text="Create From Primitive (faster to compute)")
            
            # activators_objects.separator()
            # header_parents_act = activators_objects.box().row(align=True)
            # header_parents_act.label(text="Parents Activators", icon='PARTICLE_DATA')
            
            # sub_block1 = block1.row(align=True)
            # sub_block1.scale_y = 1.3
            # sub_block1.operator("rbdlab.create_empty", text="Spheric", icon='SPHERE').shape = 'SPHERE'
            # sub_block1.operator("rbdlab.create_empty", text="Cubic", icon='CUBE').shape = 'CUBE'


            #----------------------------------------------------------------------------------------
            # Vertex Group Activators brush settings:
            #----------------------------------------------------------------------------------------
            if active_item.type == 'VERTEX_GROUPS':

                act = activators_list.get_current_activator
                # act = activators_list.active # esto me da el item no el activator
                dpaint_paint_source = rbdlab.activators.dpaint_paint_source

                if act:

                    header_brush = activators_objects.box().row(align=True)
                    header_brush.label(text= act.name + " Settings", icon='BRUSHES_ALL')
                    brush = activators_objects.box().column(align=True)
                    brush.use_property_split = True

                    brush.prop(rbdlab.activators, "dpaint_target_acts", text="Set To")
                    
                    activators_objects.use_property_split = True
                    brush = activators_objects.box().column(align=True)

                    brush.prop(rbdlab.activators, "dpaint_paint_source", text="Paint")
                    brush.separator()
                    
                    if dpaint_paint_source not in ['VOLUME', 'PARTICLE_SYSTEM']:
                        brush.prop(rbdlab.activators, "dpaint_paint_distance", text="Distance")                
                        brush.prop(rbdlab.activators, "dpaint_proximity_falloff", text="Fallof")

                        brush_mod = act.modifiers.get(RBDLabNaming.ACT_BRUSH_MOD)
                        
                        if dpaint_paint_source == 'VOLUME_DISTANCE':
                            brush.prop(rbdlab.activators, "dpaint_invert_proximity", text="Inner Proximity")
                            brush.prop(rbdlab.activators, "dpaint_use_negative_volume", text="Negate Volume")
                        
                        if dpaint_paint_source in ['DISTANCE', 'VOLUME_DISTANCE']:
                            brush.prop(rbdlab.activators, "dpaint_use_proximity_project", text="Project")                            
                            ray_dir = brush.row(align=True)
                            ray_dir.prop(rbdlab.activators, "dpaint_ray_direction", text="Ray Direction")
                            ray_dir.enabled = rbdlab.activators.dpaint_use_proximity_project

                        if brush_mod:
                            if brush_mod.brush_settings.proximity_falloff == 'RAMP':
                                
                                colramp = collapsable(
                                    activators_objects,
                                    rbdlab.ui,
                                    "show_activators_act_col_ramp",
                                    "Falloff Ramp",
                                    'COLOR',
                                    align=False,
                                )
                                if colramp:
                                    brush_settings = brush_mod.brush_settings
                                    colramp.prop(brush_settings, "use_proximity_ramp_alpha", text="Only Use Alpha")
                                    colramp.use_property_split = False
                                    colramp.template_color_ramp(brush_settings, "paint_ramp", expand=True)

            #----------------------------------------------------------------------------------------
            

            #----------------------------------------------------------------------------------------
            # Common Activators Settings:
            #----------------------------------------------------------------------------------------

            header_scale = activators_objects.box().row(align=True)
            header_scale.label(text="Setup Scale", icon='FULLSCREEN_ENTER')
            
            
            scale = activators_objects.box().column(align=True)
            scale.use_property_split = True
            scale.prop(activators_list.active, "activators_scale", text="Activators Scale")
            scale.prop(activators_list.active, "all_activators_scales", text="All Scales")


            header_setup_parents = activators_objects.box().row(align=True)
            header_setup_parents.label(text="Setup Parents", icon='COMMUNITY')
            parents = activators_objects.box().row(align=True)
            parents.scale_y = 1.3
            parents.operator("rbdlab.act_parent", text="Parent to objects").call = 'PARENT'
            parents.operator("rbdlab.act_parent", text="Clear Parents").call = 'DEPARENT'

            # activators_objects.separator()
            # header_setup_from_mesh = activators_objects.box().row(align=True)
            # header_setup_from_mesh.label(text="Setup From Selected Mesh", icon='URL')
            
            # sub_block3 = activators_objects.box().row(align=True)
            # sub_block3.scale_y = 1.3
            # sub_block3.operator("rbdlab.act_set", text="Set Activators")
            # sub_block3.operator("rbdlab.act_unset", text="Unset Activators")

            # activators_objects.separator()
            interpolation = activators_objects.box().row(align=True)
            interpolation.label(text="Set yours Animation Activators interpolation as", icon='IPO_EASE_IN_OUT')
            interpolation_bt = activators_objects.box().row(align=True)
            interpolation_bt.scale_y = 1.3
            interpolation_bt.prop(rbdlab.ui, "interpolation_type", text="")
            interpolation_bt.operator("rbdlab.act_set_interpolation", text="Set Interpolation")


    if 'CONSTRAINTS' in current_types:
        main_col.separator()
        passive_mode = main_col.column(align=True)
        header = passive_mode.box().row()
        header.label(text="Passive Mode", icon='LOCKVIEW_ON')
        content = passive_mode.box().column()

        row = content.row(align=True)
        # row.use_property_split = True
        row.prop(rbdlab.activators, "passive_mode", text="Passive Mode")
        if rbdlab.activators.passive_mode and rbdlab.activators.automatic_range_with_keyframes:
            row = content.row(align=True)
            col_msg = row.column(align=True).box()
            col_msg.label(text="Passive mode only work without Automatic Range", icon='INFO')
        if rbdlab.activators.passive_mode and not rbdlab.activators.automatic_range_with_keyframes:
            row = content.row(align=True)
            col_msg = row.column(align=True).box()
            col_msg.label(text="Passive mode It is somewhat ", icon='INFO')
            col_msg.label(text="slower because the physics are computed")

    '''
    content.label(text="• Angular Force")
    
    force = content.column()
    force.use_property_split = True
    #force.row().prop(rbdlab.activators, "force_mode", expand=True)
    force.prop(rbdlab.activators, "angular_range", text="Range", slider=True)
    force.prop(rbdlab.activators, "angular_scale", text="Scale", slider=True)
    '''




class ACTIVATORS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'ACTIVATORS'
    bl_label = "Module"
    bl_idname = "ACTIVATORS_PT_ui"
    # bl_parent_id = "CONSTRAINTS_PT_ui"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        # por defecto void, lo relleno luego:
        current_types = {}
                    
        ac_layers_list = rbdlab.lists.ac_layers_list
        active_item = ac_layers_list.active

        if active_item:
            # current_types = list(set([t.type for t in active_item.types]))
            current_types = active_item.type

        # Bloquea toda la ui si no hay chunks visibles en el TColl:
        # layout.enabled = cheker_item_visibility(rbdlab, layout)

        col = layout.column(align=True)
        title_header(col, "Activators")
        main_col = col.box().column(align=True)

        modes = main_col.row(align=True)
        modes.use_property_split = False
        modes.scale_y = 1.3
        modes.prop(ui, "activators_mode", expand=True)
        main_col = horizontal_line_separator(col)
        # main_col = col

        ACTIVATORS_OBJECTS = next((ob for ob in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in ob), None)

        # main_col.separator()
        if ui.activators_mode == 'CREATION':
            
            if rbdlab.low_or_high_visibility_viewport != "Low":
                feedback = main_col.box().column(align=True)

            main_col = main_col.column(align=True)
            if rbdlab.low_or_high_visibility_viewport != "Low":
                main_col.enabled = False
                col_box = feedback.column(align=True)
                alert = col_box.row(align=True)
                alert.label(text="Please, working in low visualization mode!", icon='ERROR')
                main_col.separator()

            # header_source = main_col.box().row(align=True)
            # header_source.label(text="Source", icon='IMPORT')
            # content_source = main_col.box().row(align=True)
            # type_row = content_source.row(align=True)
            # type_row.scale_x = 1.02
            # type_row.scale_y = 1.3
            # type_row.prop(rbdlab.activators, "type_selection", expand=True)
            # main_col.separator()

            type_sel_cont = main_col.column(align=True)
            type_selection = collapsable(
                type_sel_cont,
                ui,
                "show_activators_source_type",
                "Source",
                'IMPORT',
                align=True,
            )
            if type_selection:
                type_row = type_selection.row(align=True)
                type_row.scale_x = 1.02
                type_row.scale_y = 1.3
                type_row.prop(rbdlab.activators, "type_selection", expand=True)
            
            type_sel_cont.enabled = 'VERTEX_GROUPS' not in rbdlab.activators.work_with
            
            main_col.separator()

            # Include Chunks | Exclude Chunks
            # header_sel = main_col.box().row(align=True)
            # header_sel.label(text="Selection", icon='RESTRICT_SELECT_OFF')
            # content_sel = main_col.box().row(align=True)
            # content_sel.scale_y = 1.3
            # content_sel.operator("rbdlab.act_include_chunks", text="Include Chunks", icon='ADD')
            # content_sel.operator("rbdlab.act_exclude_chunks", text="Exclude Chunks", icon='REMOVE')
            # main_col.separator()
            
            header_affect = main_col.box().row(align=True)
            header_affect.label(text="Layer Type", icon='FORCE_MAGNETIC')
            content_affect = main_col.box().row(align=True)
            flow = content_affect.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
            flow.scale_y = 1.3
            flow.prop(rbdlab.activators, "work_with", text=" ", expand=True)

        else:
                
            if rbdlab.low_or_high_visibility_viewport != "Low":
                feedback = main_col.box().column(align=True)
            
            main_col = main_col.column(align=True)
            if rbdlab.low_or_high_visibility_viewport != "Low":
                main_col.enabled = False
                col_box = feedback.column(align=True)
                alert = col_box.row(align=True)
                alert.label(text="Please, working in low visualization mode!", icon='ERROR')
                main_col.separator()

            lists_row = main_col.row(align=True)

            # columnas princpipales de Layers y Activators:
            layers_list = lists_row.column(align=True)
            actvat_list = lists_row.column(align=True)
            lists_row.scale_x = 0.6

            # Header Layers List:
            layers_header = layers_list.box().row(align=True)
            layers_header.alignment = 'CENTER'
            
            title_layer = layers_header.row()
            title_layer.label(text="Layers List", icon='DOCUMENTS')

            # Layers List:
            layers_list.template_list("RBDLAB_UL_draw_ac_layers", "", ac_layers_list, "list", ac_layers_list, "list_index", rows=3)
            # botones de abajo del listado:
            if not ac_layers_list.is_void:
                ac_layers_list_bts = layers_list.row(align=True)
                ac_layers_list_bts.scale_y = 1.3
                ac_layers_list_bts.operator("rbdlab.act_include_chunks", text="Include Chunks", icon='ADD')
                ac_layers_list_bts.operator("rbdlab.act_exclude_chunks", text="Exclude Chunks", icon='REMOVE')

            # Header Activators List:
            ac_header = actvat_list.box().row(align=True)
            ac_header.alignment = 'CENTER'
            
            title_act = ac_header.row()
            title_act.label(text="Activators List", icon='LIGHTPROBE_SPHERE')
            
            ac_header.scale_x = 0.65 if active_item else 1 # <- hack para tener el encabezado bien

            if active_item:
                activators_list = active_item.activators_list

            # Si hay grupo activo en el listado Layers:
            if active_item:

                # Activators List:
                
                actvat_list.scale_x = 1.73 if activators_list.is_void else 1.3 # <- hack para tener el mismo tamaño de listado derecho
                
                actvat_list.template_list("RBDLAB_UL_draw_activators", "", activators_list, "list", activators_list, "list_index", rows=3)
                # botones de abajo del listado:
                ac_list_bts = actvat_list.row(align=True)
                ac_list_bts.scale_y = 1.3
                ac_list_bts.operator("rbdlab.act_add")
                
                dropdown = ac_list_bts.row(align=True)
                dropdown.scale_x = 1.1 if activators_list.is_void else  1.25
                dropdown.alignment = 'CENTER'
                dropdown.menu("RBDLAB_MT_activators_dropdow", text="")

            else:

                actvat_list.scale_x = 1.09 # <- hack para tener el mismo tamaño de listado derecho
                # Si no hay grupo activo usamos un fake list:
                fakelist = actvat_list.box()
                fakelist.label(text="")
                fakelist.scale_y = 3.5
                # hueco de abajo del listado:
                # ac_layers_list_bts = actvat_list.box().row(align=True)
                # ac_layers_list_bts.label(text="")
            

            if active_item:
                
                # list_settings = main_col.box().column(align=True)
                # list_settings = horizontal_line_separator(main_col)

                common_settings(context, main_col, ui, rbdlab, active_item)

                # if ACTIVATORS_OBJECTS is None:
                #     main_col.box().label(text="First Add Activators", icon='INFO')
                # else:
                if ACTIVATORS_OBJECTS is not None:

                    if active_item.type == 'KINEMATIC' and not activators_list.is_void:

                        cont_prev = main_col.column(align=True)
                        cont_prev.use_property_split = False
                        # cont_prev.enabled = not activators_list.is_void
                        preview_bt = collapsable(
                            cont_prev,
                            ui,
                            "show_activators_preview_bt",
                            "Preview",
                            'ONIONSKIN_ON',
                            align=True,
                        )
                        if preview_bt:
                            preview_bt = preview_bt.row(align=True)
                            preview_bt.scale_y = 1.3
                            preview_bt.operator("rbdlab.act_record", text="Preview").mode = 'FORCE_PREVIEW'

                            if tcoll:
                                if "activators_force_preview_recorded" in tcoll:
                                    rm_preview_bt = preview_bt.row(align=True)
                                    rm_preview_bt.alert = True
                                    rm_preview_bt.operator("rbdlab.act_rm_record", text="Remove Preview", icon='TRASH').mode = 'FORCE_PREVIEW'

                main_col = main_col.box().column(align=True)
                main_col.use_property_split = True

                # work_with = None
                # if current_types:
                #     work_with = ""
                #     for w_with in current_types:
                #         if w_with not in work_with:
                #             work_with += " " + str(w_with.capitalize())

                # solo muestro los substeps si tenemos algún activator de tipo mesh (osea un custom del usuario):
                if ac_layers_list.has_any_activator_with_mesh_type:
                    main_col.separator()
                    main_col.prop(active_item, "passes", text="Substeps", slider=True)
                    main_col.separator()

                # Feedback para el usuario:
                if activators_list.is_void:
                    main_col.box().label(text="First add Activators", icon='INFO')
                    if active_item.type != 'VERTEX_GROUPS':
                        main_col.separator()

                # Feedback para el usuario:
                if ACTIVATORS_OBJECTS is None:
                    if not activators_list.is_void:
                        main_col.box().label(text="First add valid Activators", icon='INFO')
                        if active_item.type != 'VERTEX_GROUPS':
                            main_col.separator()

                if active_item.type == 'VERTEX_GROUPS':
                    text = "When using VertexGroups it is not necessary to make recordings."
                    multiline_print(main_col, text, max_words=7, first_line_crop=2)
                    
                else:
                    
                    bts_record = main_col.row(align=True)
                    bts_record.scale_y = 1.7
                    bts_record.operator("rbdlab.act_record", text="Record", icon='RADIOBUT_OFF').mode = 'NORMAL'
                    
                    # if tcoll and work_with:
                    if ui.activators_mode != 'CREATION':
                        rm_bt = bts_record.row(align=True)
                        rm_bt.alert = True
                        
                        rm_bt.enabled = active_item.recorded and "activators_force_preview_recorded" not in tcoll
                        # rm_bt.enabled = active_item.recorded

                        # rm_bt.operator("rbdlab.act_rm_record", text="Remove " + work_with, icon='TRASH').mode = 'NORMAL'
                        rm_bt.operator("rbdlab.act_rm_record", text="Remove", icon='TRASH').mode = 'NORMAL'


            if current_types:

                col.separator()
                switcher = col.box().row(align=True)
                switcher.use_property_split = False
                switcher.scale_y = 1.3

                # nueva ui:
                show_settings = False
                # show_deactivation = False
                show_dynamic = False
                show_init_vel = False
                show_vertex_group = False
                show_consts = False

                #--------------------------------------------------------------------------
                # NOTA quizás deberia guardarlo en active_item en lugar de en ui las props
                #--------------------------------------------------------------------------
                if 'DEACTIVATION' in current_types:
                    switcher.prop(active_item, "activators_sect_deactivation", expand=True)
                    show_settings = True if active_item.activators_sect_deactivation == 'ACTIVATORS' else False
                    # show_deactivation = True if active_item.activators_sect_deactivation == 'DEACTIVATION' else False
            
                elif 'CONSTRAINTS' in current_types:
                    switcher.prop(active_item, "activators_sect_constraints", expand=True)
                    show_settings = True if active_item.activators_sect_constraints == 'ACTIVATORS' else False
                    show_consts = True if active_item.activators_sect_constraints == 'CONSTRAINT' else False

                elif 'KINEMATIC' in current_types or 'INITIALVEL' in current_types:
                    switcher.prop(active_item, "activators_sect_init_vel", expand=True)
                    show_settings = True if active_item.activators_sect_init_vel == 'ACTIVATORS' else False
                    show_init_vel = True if active_item.activators_sect_init_vel == 'INIT_VEL' else False

                elif 'DYNAMIC' in current_types:
                    switcher.prop(active_item, "activators_sect_dynamics", expand=True)
                    show_settings = True if active_item.activators_sect_dynamics == 'ACTIVATORS' else False
                    show_dynamic = True if active_item.activators_sect_dynamics == 'DYNAMIC' else False

                elif 'VERTEX_GROUPS' in current_types:
                    switcher.prop(active_item, "activators_sect_vertex_group", expand=True)
                    show_settings = True if active_item.activators_sect_vertex_group == 'ACTIVATORS' else False
                    show_vertex_group = True if active_item.activators_sect_vertex_group == 'VERTEX_GROUPS' else False

                # col.separator()

                if show_settings:
                    settings_section(rbdlab, col, current_types, ACTIVATORS_OBJECTS, active_item)
                
                # Deactivation no tiene opciones:
                # elif show_deactivation:
                #     col.box().label(text="Settings Deactivation")

                elif show_consts:
                    panel_constraints(rbdlab, col)

                elif show_dynamic:
                    panel_dynamics(col, active_item)
                    
                elif show_init_vel:
                    panel_initial_velocity(rbdlab, ui, col)
                
                elif show_vertex_group:
                    panel_vertex_group(ui, col)
                    
                
        # BUTTONS:

        # if ACTIVATORS_OBJECTS is None:
        #     feedback_add_activators = col.box().column(align=True)

        if ui.activators_mode == 'CREATION':
            col_big = col.box().column(align=True)
        else:
            col_big = col.column(align=True)
        
        col_big.scale_y = 1.3
        col_big.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        # mensaje porque hay problemas si usamos el truco de tebito:
        if current_types:
            if 'KINEMATIC' in current_types:
                if tcoll:
                    if "kinematic_keyframes_text" in tcoll:
                        if tcoll["kinematic_keyframes_text"] != "":
                            msg = col.box().row(align=True)
                            msg.label(text="Previous Kinematic keyframes will be deleted!!", icon='ERROR')

        # ignore.prop(rbdlab.ui, "activators_ignore_acetonized", text="Ignore already acetonizeds")

        
        record_bt = col_big.row(align=True)
        record_bt.scale_y = 1.3

        # col = layout.column()
        # msg = col.row(align=True)
        # row = col.row(align=True)
        # if rbdlab.ui.activators_ignore_acetonized:
        #     msg.alert = True
        #     msg.label(text="Ignore Acetonizeds are ON", icon='INFO')
        
        if ui.activators_mode == 'CREATION':
            # col_big.separator()
            col_big.operator("rbdlab.act_add_layer", text="Add Layer")

        # else:

            # if ACTIVATORS_OBJECTS is None:
            #     feedback_add_activators.box().label(text="Add First Activators", icon='INFO')
            #     col_big.separator()

            # el viejo Record:
            # record_bt.operator("rbdlab.act_record", text="Record").mode = 'NORMAL'

        
        # para la condicion de activators necesito saber si tienen keyframes:
        if current_types:
            if 'CONSTRAINTS' in current_types:

                all_keyframes = []
                if ACTIVATORS_OBJECTS is not None:

                    act_obs = [ob for ob in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in ob]

                    for ob in act_obs:
                        if ob.animation_data:
                            if hasattr(ob.animation_data.action, "fcurves"):
                                for fc in ob.animation_data.action.fcurves:
                                    for key in fc.keyframe_points:
                                        all_keyframes.append(key.co.x)

                        if len(all_keyframes) == 0:
                            if ob.parent:
                                if ob.parent.animation_data:
                                    if hasattr(ob.parent.animation_data.action, "fcurves"):
                                        for fc in ob.parent.animation_data.action.fcurves:
                                            for key in fc.keyframe_points:
                                                all_keyframes.append(key.co.x)

                condition_1 = len(all_keyframes) == 0 \
                    and not rbdlab.activators.passive_mode \
                    and 'CONSTRAINTS' in current_types \
                    and not rbdlab.activators.automatic_range_with_keyframes

        if tcoll:
            record_bt.enabled = True
            # if "activators_force_preview_recorded" in tcoll or "activators_recorded" in tcoll:
            if "activators_force_preview_recorded" not in tcoll:
                # print(0, record_bt.enabled)
                # record_bt.enabled = True
                # si se usa pasive mode pero no esta desactivado el automatic range bloqueo el boton:
                if current_types:

                    if 'CONSTRAINTS' in current_types:
                        if all([rbdlab.activators.passive_mode, rbdlab.activators.automatic_range_with_keyframes]):
                            record_bt.enabled = False
                            # print('1')
                        else:
                            if condition_1:
                                # print('2')
                                record_bt.enabled = False
                else:
                    record_bt.enabled = False
                    # print('5', record_bt.enabled)


            # print('3', record_bt.enabled)
        else:
            # print('4')
            record_bt.enabled = False

        if 'EXPLODE' in rbdlab.ui.activators_force_loc_mode and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in tcoll:
            # print('6', record_bt.enabled)
            record_bt.enabled = False

        # ** el viejo remove clear:
        # work_with = None
        # if current_types:
        #     work_with = ""
        #     for w_with in current_types:
        #         if w_with not in work_with:
        #             work_with += " " + str(w_with.capitalize())

        # if tcoll:
        #     if "activators_recorded" in tcoll: # and work_with:
        #         if ui.activators_mode != 'CREATION':
        #             # col_box = col.column(align=True)
        #             # row_bt = col_box.row(align=True)
        #             # row_bt.scale_y = 1.3

        #             # col_big2 = row_bt.row(align=True)
        #             # col_big2.alert = True
        #             # ** el viejo remove clear:
        #             # col_big2.operator("rbdlab.act_rm_record", text="Remove " + work_with, icon='TRASH').mode = 'NORMAL'

        # col.operator("rbdlab.unhide", text="Unhide Acetonizeds")

        