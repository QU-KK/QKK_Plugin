import json
from ....addon.naming import RBDLabNaming
from ....panels.common_ui_elements import multiline_print, collapsable
from os.path import dirname, join, realpath
from ....Global.geometry_nodes import get_gn_index_or_identifier_by
feedback_msg = "Is necessary first have a fractured object with few fractures."
feedback_msg2 = "Now you can finish configuring your settings and then you can go to the fracturing tab to fracture the object, otherwise you can cancel this action."


def scatter_standard(context, rbdlab, layout):
    objects_without_scatter = [obj for obj in context.selected_objects if obj.type ==
                               'MESH' and obj.visible_get() and len(obj.particle_systems) == 0]

    # Hay objetos con scatter seleccionados.
    if not objects_without_scatter:  # rbdlab.scatter_working:
        layout.separator()
        col_sel = layout.column()
        col_sel.scale_y = 1.3
        col_sel.operator("rbdlab.scatter_select", text="Select Scattereds")
        col_sel.enabled = not rbdlab.current_using_cell_fracture

        if rbdlab.scatter_working and len(context.selected_objects) > 0:

            layout.separator()
            buttons = layout.row(align=True)
            buttons.scale_y = 1.3
            accept_button = buttons.row(align=True)
            accept_button.operator("rbdlab.scatter_end", text="Accept", icon='CHECKMARK')
            cancel_button = buttons.row(align=True)
            cancel_button.alert = True
            cancel_button.operator("rbdlab.scatter_cancel", text="Cancel", icon='CANCEL')

    else:
        layout.separator()
        row = layout.row()
        row.scale_y = 1.3
        row.operator("rbdlab.scatter_add", text="Add Standard Scatter")
        row.enabled = not rbdlab.current_using_cell_fracture


def scatter_texture(context, rbdlab, layout):
    scatter_props = rbdlab.scatter

    if context.selected_objects:
        ob = context.selected_objects[0]
    else:
        ob = context.object

    if not ob:
        return

    ps_name = "Scatter_by_Texture"
    if "rbdlab_texture_created" not in ob:
        layout.separator()
        row = layout.row()
        row.scale_y = 1.3
        row.operator("rbdlab.scatter_by_texture", text="Add Texture Scatter")
        row.enabled = not rbdlab.current_using_cell_fracture

    if rbdlab.scatter_working:

        tex = None
        if ps_name in ob.particle_systems:
            ps = ob.particle_systems[ps_name]
            tex = ps.settings.active_texture

        if tex:
            # particle settings
            # layout.separator()
            box = layout.box().column(align=True)
            box.label(text="Particle Settings", icon='PARTICLE_TIP')
            box = layout.box().column(align=True)
            # box.prop(ps.settings, "count", text="Number")

            box.prop(scatter_props, "texture_particle_count", text="Number")
            box.separator()
            # box.prop(ps.settings, "emit_from", text="Emit From")
            box.prop(scatter_props, "texture_secondary_emit_from", text="Emit From")

            box.separator()

            density = box.row(align=True)
            density.use_property_decorate = False
            density.prop_search(ps, "vertex_group_density", ob, "vertex_groups", text="Density")
            density.prop(ps, "invert_vertex_group_density", text="", toggle=True, icon='ARROW_LEFTRIGHT')

            # dropdown type:
            layout.separator()
            box = layout.box()
            box.label(text="Texture Settings")
            split = box.split(factor=0.2)
            split.label(text="Type")
            split.prop(tex, "type", text="")

            # preview texture:
            # slot = getattr(obj, "texture_slot", None)
            # box.template_preview(tex, slot=slot)

            # Noise settings:
            # layout.separator()
            box = layout.box()
            box.label(text="Noise Settings", icon='MOD_NOISE')
            box = layout.box().column(align=True)
            # box.prop(tex, "noise_basis", text="Noise Basis")
            box.prop(scatter_props, "texture_noise_basis", text="Noise Basis")
            # box.prop(tex, "noise_type", text="Type")
            box.prop(scatter_props, "texture_noise_type", text="Type")
            # box.prop(tex, "cloud_type")
            box.prop(scatter_props, "texture_cloud_type", text="Color")
            # box.prop(tex, "noise_scale", text="Size")
            box.separator()
            box.prop(scatter_props, "texture_noise_scale", text="Size")
            # box.prop(tex, "noise_depth", text="Depth")
            box.prop(scatter_props, "texture_noise_depth", text="Depth")

            # Cloud Mapping
            # layout.separator()
            box = layout.box()
            box.label(text="Texture Mapping", icon='UV_DATA')
            box = layout.box().column(align=True)
            # texture_slot_0 = ps.settings.texture_slots[0]
            # box.prop(texture_slot_0, "texture_coords", text="Coordinates")
            box.prop(scatter_props, "texture_texture_coords", text="Coordinates")
            box.separator()
            # box.prop(texture_slot_0, "offset")
            box.prop(scatter_props, "texture_mapping_offset", text="Offset")
            # box.prop(texture_slot_0, "scale")
            box.separator()
            box.prop(scatter_props, "texture_mapping_size", text="Size")

            # Color Ramp
            # layout.separator()
            box = layout.box()
            row = box.row()
            row.use_property_split = False
            row.label(text="", icon='COLORSET_10_VEC')
            # row.prop(tex, "use_color_ramp", text="Color Ramp")
            row.prop(scatter_props, "texure_use_color_ramp", text="Color Ramp")
            if tex.use_color_ramp:
                box.template_color_ramp(tex, "color_ramp", expand=True)

            box.separator()
            buttons = box.row(align=True)
            buttons.scale_y = 1.3
            accept_button = buttons.row(align=True)
            accept_button.operator("rbdlab.scatter_by_texture_accept", text="Accept", icon='CHECKMARK')
            cancel_button = buttons.row(align=True)
            cancel_button.alert = True
            cancel_button.operator("rbdlab.scatter_cancel", text="Cancel", icon='CANCEL')


def scatter_organic(context, rbdlab, layout):
    scatter_props = rbdlab.scatter

    if context.selected_objects:
        obj = context.selected_objects[0]
    else:
        obj = context.object

    if not obj:
        return

    layout.separator()
    col = layout.column(align=True)

    if "rbdlab_scatter_organic_accepted" not in obj:
        row = col.row()
        row.scale_y = 1.3
        row.operator("rbdlab.scatter_organic", text="Add Organic Scatter")
        row.enabled = not rbdlab.current_using_cell_fracture

        if "rbdlab_scatter_organic" in obj:
            col.separator()
            col.prop(scatter_props, "scatter_geo_from", text="From")
            col.prop(scatter_props, "scatter_geo_count", text="Count")
            col.prop(scatter_props, "scatter_geo_seed", text="Seed")
            col.prop(scatter_props, "scatter_geo_particle_size", text="Ico Size")
            col.prop(scatter_props, "scatter_geo_size_random", text="Ico Rand Size")
            col_bt = col.column(align=True)
            col_bt.scale_y = 1.3
            col_bt.separator()
            col_bt.operator("rbdlab.scatter_organic_accept", text="Accept", icon='CHECKMARK')
            # col.operator("rbdlab.scatter_organic_cancel", text="Cancel")

    else:
        col.prop(scatter_props, "scatter_geo_ps_child_size", text="Size Childs")
        col.prop(scatter_props, "scatter_geo_child_count", text="Childs particles")
        layout.separator()
        box = layout.box()
        box.label(text="Would now be ready to fracture!", icon='INFO')
        box.label(text="Remember not use Max Chunks 0 now")


def scatter_boolean(context, rbdlab, layout):
    
    ui = rbdlab.ui
    scatter_props = rbdlab.scatter

    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active

    layout.separator()
        
    if not tcoll or ui.boolean_method_phase == 'NONE':

        not_scale_applied = next((ob for ob in context.selected_objects if sum(ob.scale[:]) != 3), None)
        if not_scale_applied:
            txt = "It seems that some of your selected objects do not have the scale applied, you should apply the scale first."
            multiline_print(layout, txt, max_words=6, icon='ERROR', first_line_crop=0)
            layout.separator()
        

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("rbdlab.boolean_fracture_add", text="GN Boolean")
        row.enabled = not rbdlab.current_using_cell_fracture
                    
    else:

        # BoolFracture:
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        if not bfracture_gn_list.is_void:

            # esto a cambiado con el back:
            base_plane = bfracture_gn_list.get_base_plane
            if base_plane:

                GN_mod = base_plane.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
                # solidify_mod = base_plane.modifiers.get(RBDLabNaming.SOLIDIFY_MOD)

                if GN_mod and ui.boolean_method_phase == 'SETTINGS_GN':

                    #----------------------------------------------------------------------------
                    # GN UI:

                    # listado:
                    layout.template_list("RBDLAB_UL_draw_bf_gn", "", bfracture_gn_list, "list", bfracture_gn_list, "list_index", rows=4)
                    
                    # boton agregar nuevo GN:
                    add_gn_bool_bt = layout.row(align=True) 
                    add_gn_bool_bt.scale_y = 1.3
                    add_gn_bool_bt.operator("rbdlab.boolean_fracture_append", text="Add GN Boolean")
                    
                    layout.separator()

                    # leemos el .json con la info de la ui:
                    fracture_folder = dirname(realpath(__file__))
                    with open(join(fracture_folder, "GN_UI.json"), "r") as f:
                        data_ui = json.load(f)
                    
                    for slug in data_ui:

                        # para mostrar solo el panel RANDOM o el panel GRID con el enum:
                        if base_plane.rbdlab.bf_gn_distribution_type == 'RANDOM':
                            blacklist_slug = 'GRID'

                        elif base_plane.rbdlab.bf_gn_distribution_type == 'GRID':
                            blacklist_slug = 'RANDOM'
                        
                        if slug in blacklist_slug:
                            continue
                        
                        # poniendo el data en sus variables:
                        title = data_ui[slug]["title"]
                        item = data_ui[slug]
                        bool_path = getattr(rbdlab, item["bool_path"]) # estan guardados en rbdlab.ui
                        bool_toggle = item["bool_toggle"] 
                        items = item["items"]
                        icon = item["icon"]

                        item_collapse = collapsable(
                            layout,
                            bool_path,
                            bool_toggle,
                            title,
                            icon,
                            align=True,
                        )
                        if item_collapse:
                            
                            # si estamos en la section distribution tenemos el toggle que cambia
                            if title == "Distribution":
                                
                                distribution_type = item_collapse.row(align=True)
                                distribution_type.scale_y = 1.3
                                distribution_type.prop(base_plane.rbdlab, "bf_gn_distribution_type", expand=True)
                                item_collapse.separator()

                            item_collapse.use_property_split = True

                            # los items son cada property que contiene la section:
                            for prop_name in items:

                                group_input = GN_mod.node_group.nodes.get("Group Input")
                                if group_input:
                                    identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, prop_name, debug=False)
                                    
                                if not identifier or slug in blacklist_slug:
                                    continue
                                
                                # si estamos en "Planes Transformation":
                                if slug == "planes_transformation":
                                    row = item_collapse.row(align=True)
                                    row.use_property_split = False
                                    row.prop(GN_mod, '["'+ identifier +'"]', text=prop_name)
                                    
                                else:
                                    # el resto:

                                    # un separador antes de ON/OFF Reductor:
                                    if "ON/OFF" in prop_name:
                                        item_collapse.separator()

                                    item_collapse.prop(GN_mod, '["'+ identifier +'"]', text=prop_name)

                        # espacio entre bloques:
                        layout.separator()


                    # old -----------------
                    # ui_props_names = [
                    #     "Density Volume", 
                    #     "Densidad Planes",

                    #     "Switch Targets",

                    #     "----separator----",
                    #     "Switch Planes/Points",
                    #     "Spacing X",
                    #     "Spacing Y",
                    #     "Spacing Z",
                    #     "----separator----",

                    #     "DensityGrid",
                    #     "----separator----",
                    #     "Size Planes",
                    #     "Thickness Planes",
                    #     "----separator----",
                    #     "Translate Planes",
                    #     "----separator----",
                    #     "Rotate Planes",
                    #     "----separator----",
                    #     "Random Rot Planes",
                    #     "----separator----",
                    #     "Seed",
                    #     "----separator----",
                    #     "ON/OFF Reductor",
                    #     "Reductor",
                    #     "Scale Noise",
                    #     "Detail Noise",
                    #     "Noise Strenght",
                    # ]
                    # gn_ui = layout.column(align=True)
                    # gn_ui.use_property_split = True

                    # for prop_name in ui_props_names:

                    #     if prop_name == "----separator----":
                    #         gn_ui.separator()
                    #         continue
                        
                    #     # uso un modifier thinkness en el propio .blend de la lib:
                    #     if prop_name == "Thickness Planes":
                    #         gn_ui.prop(solidify_mod, "thickness")

                    #     group_input = GN_mod.node_group.nodes.get("Group Input")
                    #     if group_input:
                    #         identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, prop_name, debug=False)

                    #         if "Spacing" not in prop_name:
                            
                    #             gn_ui.prop(GN_mod, '["'+ identifier +'"]', text=prop_name)
                            
                    #         else:
                                
                    #             # si son los space XYZ:
                    #             if prop_name == "Spacing X":
                    #                 spacing_ui = gn_ui.column(align=True)
                    #             swt_prop_index = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Switch Planes/Points", debug=False)
                    #             spacing_ui.enabled = swt_prop_index and GN_mod[swt_prop_index]
                    #             spacing_ui.prop(GN_mod, '["'+ identifier +'"]', text=prop_name)
                    
                    # gn_ui.separator()
                    #----------------------------------------------------------------------------

        last_block = layout.column(align=True) 
        last_block.scale_y = 1.3

        if ui.boolean_method_phase == 'SETTINGS_GN':
            # last_block.separator()
            last_block.operator("rbdlab.boolean_fracture_make_real", text="Continue", icon='CHECKMARK')

        elif ui.boolean_method_phase == 'SETTINGS_BOOL_MOD':
            
            booleans_method = last_block.row(align=True)
            booleans_method.prop(scatter_props, "scatter_bfracture_method", text="Method", expand=True)
            
            # mostramos el thinckness:
            bool_plane = bfracture_gn_list.get_bool_plane
            if bool_plane:
                mod = bool_plane.modifiers.get(RBDLabNaming.SOLIDIFY_MOD)
                if mod:
                    # last_block.prop(solidify_mod, "thickness")
                    settings = last_block.row(align=True)
                    settings.prop(bool_plane.rbdlab, "bf_gn_wire_solid", text="Wireframe" if bool_plane.rbdlab.bf_gn_wire_solid else "Textured", toggle=True)
                    settings.prop(bool_plane.rbdlab, "bf_gn_thickness", text="Thickness")
            
            last_block.separator(factor=0.5)
            
            block_chkboxes = last_block.column(align=True) 
            block_chkboxes.scale_y = 0.8

            use_neighbors = block_chkboxes.column(align=True)
            use_neighbors.prop(ui, "bf_gn_compute_neighbors", text="Compute Neighbors")

            if not ui.bf_gn_compute_neighbors:
                use_neighbors.separator(factor=0.5)
                text = "Computing Neighbors is necessary to use constraints and/or particles (Brokens)."
                multiline_print(use_neighbors.box(), text, max_words=5, first_line_crop=0, without_box=True)
                use_neighbors.separator(factor=0.5)

            use_inner_auto_uvs = use_neighbors.column(align=True)
            use_inner_auto_uvs.prop(ui, "bf_gn_use_auto_uv_cube_projection")
            
            use_neighbors.separator(factor=0.5)

            buttons = last_block.row(align=True)
            buttons.operator("rbdlab.boolean_fracture_go_back", text="Go Back", icon='LOOP_BACK')
            buttons.operator("rbdlab.boolean_fracture_apply", text="Apply", icon='CHECKMARK')



def edge_method_all(context, rbdlab, layout):
    scatter_props = rbdlab.scatter
    layout.enabled = rbdlab.low_or_high_visibility_viewport == "Low"
    
    col = layout.column()

    if rbdlab.filtered_target_collection:

        if "edge_extracted_all" not in rbdlab.filtered_target_collection and "starting_fracture" not in rbdlab.filtered_target_collection:
            col.separator()
            col.prop(rbdlab.ui, "edge_methods_type")
            col2 = col.column(align=True)
            col2.separator()
            col2.operator("rbdlab.scatter_edges_all", text="Generate All Inners")
            col2.scale_y = 1.3
            if "edge_extracted_inners" in rbdlab.filtered_target_collection or "edge_extracted_innerfaces" in rbdlab.filtered_target_collection:
                col.enabled = False
            else:
                col.enabled = True

        if rbdlab.filtered_target_collection:
            if "edge_extracted_all" in rbdlab.filtered_target_collection and "edge_extracted_all_accepted" not in rbdlab.filtered_target_collection:
                col.prop(scatter_props, "edge_curve_bevel_depth")
                row_buttons = col.row(align=True)
                accept_bt = row_buttons.column(align=True)
                cancel_bt = row_buttons.column(align=True)
                cancel_bt.alert = True
                cancel_bt.scale_y = 1.3
                accept_bt.scale_y = 1.3

                accept_bt.operator("rbdlab.scatter_edges_all_accept", text="Accept", icon='CHECKMARK')
                cancel_bt.operator("rbdlab.scatter_edges_all_cancel", text="Cancel", icon='CANCEL')

            if "edge_extracted_all" in rbdlab.filtered_target_collection and "edge_extracted_all_accepted" in rbdlab.filtered_target_collection:
                col.prop(scatter_props, "edge_count")
                col.prop(scatter_props, "edge_seed")
                col.prop(scatter_props, "edge_p_size")
                col.prop(scatter_props, "egde_emit_from")
                col.prop(scatter_props, "edge_use_modifier_stack")

                col.prop(scatter_props, "edge_distribution")

                if scatter_props.edge_distribution == 'GRID':
                    col.prop(scatter_props, "edge_invert_grid")
                    col.prop(scatter_props, "edge_hexagonal_grid")
                    col.prop(scatter_props, "edge_grid_resolution")
                    col.prop(scatter_props, "edge_grid_random")

                if scatter_props.edge_distribution != 'GRID':
                    col.prop(scatter_props, "edge_use_emit_random")
                    col.prop(scatter_props, "edge_use_even_distribution")

                if scatter_props.edge_distribution == 'JIT':
                    col.prop(scatter_props, "edge_userjit")
                    col.prop(scatter_props, "edge_jitter_factor")

                multiline_print(col, feedback_msg2, max_words=6, first_line_crop=0)
                cancel_bt = col.column()
                cancel_bt.alert = True
                cancel_bt.scale_y = 1.3
                cancel_bt.operator("rbdlab.scatter_edges_all_cancel", text="Cancel", icon='X')
    else:
        col.separator()
        multiline_print(col, feedback_msg, max_words=6, first_line_crop=0)


def edge_method_inners(context, rbdlab, layout):
    scatter_props = rbdlab.scatter
    col = layout.column()

    if rbdlab.filtered_target_collection:

        if "edge_extracted_inners" not in rbdlab.filtered_target_collection and "starting_fracture" not in rbdlab.filtered_target_collection:
            col.separator()
            col.prop(rbdlab.ui, "edge_methods_type")
            col2 = col.column(align=True)
            col2.separator()
            col2.operator("rbdlab.scatter_edges_inners", text="Generate Inners")
            col2.scale_y = 1.3
            if "edge_extracted_all" in rbdlab.filtered_target_collection or "edge_extracted_innerfaces" in rbdlab.filtered_target_collection:
                col.enabled = False
            else:
                col.enabled = True

        if "edge_extracted_inners" in rbdlab.filtered_target_collection and "edge_extracted_inners_accepted" not in rbdlab.filtered_target_collection:
            col.prop(scatter_props, "edge_curve_bevel_depth")
            row_buttons = col.row(align=True)
            accept_bt = row_buttons.column(align=True)
            cancel_bt = row_buttons.column(align=True)
            cancel_bt.alert = True
            cancel_bt.scale_y = 1.3
            accept_bt.scale_y = 1.3
            accept_bt.operator("rbdlab.scatter_edges_inners_accept", text="Accept", icon='CHECKMARK')
            cancel_bt.operator("rbdlab.scatter_edges_inners_cancel", text="Cancel", icon='CANCEL')

        if "edge_extracted_inners" in rbdlab.filtered_target_collection and "edge_extracted_inners_accepted" in rbdlab.filtered_target_collection:
            col.prop(scatter_props, "edge_count")
            col.prop(scatter_props, "edge_seed")
            col.prop(scatter_props, "edge_p_size")
            col.prop(scatter_props, "egde_emit_from")
            col.prop(scatter_props, "edge_use_modifier_stack")

            col.prop(scatter_props, "edge_distribution")

            if scatter_props.edge_distribution == 'GRID':
                col.prop(scatter_props, "edge_invert_grid")
                col.prop(scatter_props, "edge_hexagonal_grid")
                col.prop(scatter_props, "edge_grid_resolution")
                col.prop(scatter_props, "edge_grid_random")

            if scatter_props.edge_distribution != 'GRID':
                col.prop(scatter_props, "edge_use_emit_random")
                col.prop(scatter_props, "edge_use_even_distribution")

            if scatter_props.edge_distribution == 'JIT':
                col.prop(scatter_props, "edge_userjit")
                col.prop(scatter_props, "edge_jitter_factor")

            multiline_print(col, feedback_msg2, max_words=6, first_line_crop=0)
            cancel_bt = col.column()
            cancel_bt.alert = True
            cancel_bt.scale_y = 1.3
            cancel_bt.operator("rbdlab.scatter_edges_inners_cancel", text="Cancel", icon='CANCEL')
    else:
        col.separator()
        multiline_print(col, feedback_msg, max_words=6, first_line_crop=0)


def edge_method_innerfaces(context, rbdlab, layout):
    scatter_props = rbdlab.scatter
    col = layout.column()

    if rbdlab.filtered_target_collection:

        if "edge_extracted_innerfaces" not in rbdlab.filtered_target_collection and "starting_fracture" not in rbdlab.filtered_target_collection:
            col.separator()
            col.prop(rbdlab.ui, "edge_methods_type")
            col2 = col.column(align=True)
            col2.separator()
            col2.operator("rbdlab.scatter_edges_innerfaces", text="Generate Inner Faces")
            col2.scale_y = 1.3
            if "edge_extracted_all" in rbdlab.filtered_target_collection or "edge_extracted_inners" in rbdlab.filtered_target_collection:
                col.enabled = False
            else:
                col.enabled = True

        if rbdlab.filtered_target_collection:
            if "edge_extracted_innerfaces" in rbdlab.filtered_target_collection:
                col.prop(scatter_props, "edge_solidify_thickness")
                col.prop(scatter_props, "edge_displace_strength")
                col.prop(scatter_props, "edge_count")
                col.prop(scatter_props, "edge_seed")
                col.prop(scatter_props, "edge_p_size")
                col.prop(scatter_props, "egde_emit_from")
                col.prop(scatter_props, "edge_use_modifier_stack")

                col.prop(scatter_props, "edge_distribution")

                if scatter_props.edge_distribution == 'GRID':
                    col.prop(scatter_props, "edge_invert_grid")
                    col.prop(scatter_props, "edge_hexagonal_grid")
                    col.prop(scatter_props, "edge_grid_resolution")
                    col.prop(scatter_props, "edge_grid_random")

                if scatter_props.edge_distribution != 'GRID':
                    col.prop(scatter_props, "edge_use_emit_random")
                    col.prop(scatter_props, "edge_use_even_distribution")

                if scatter_props.edge_distribution == 'JIT':
                    col.prop(scatter_props, "edge_userjit")
                    col.prop(scatter_props, "edge_jitter_factor")

                multiline_print(col, feedback_msg2, max_words=6, first_line_crop=0)
                cancel_bt = col.column()
                cancel_bt.alert = True
                cancel_bt.scale_y = 1.3
                cancel_bt.operator("rbdlab.scatter_edges_innerfaces_cancel", text="Cancel", icon='X')
    else:
        col.separator()
        multiline_print(col, feedback_msg, max_words=6, first_line_crop=0)
