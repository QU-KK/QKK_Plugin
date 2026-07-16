from .draw_const_settings import draw_const_settings


def draw_create_filter(layout, rbdlab):
        rbdlab_const = rbdlab.constraints
        section = layout.column(align=True)

        content = section.column(align=True)
        content.use_property_split = False

        content.separator()
        source_filter = content.box().column(align=True)
        header = source_filter.row(align=True)
        header.scale_y = 0.4
        header.label(text="Source Filter")
        source_filter.separator()

        _row = source_filter.row(align=True)
        _row.scale_y = 1.3
        _row.prop(rbdlab_const, "apply_by", text=" ", expand=True)

        if rbdlab_const.apply_by == 'CLUSTER':
            cluster_section = content.box().column()
            cluster_section.use_property_decorate = False
            cluster_section.use_property_split = True

            # CLUSTER OPTIONS.
            cluster_section.label(text="Cluster Options", icon='MOD_BUILD')
            cluster_section.prop(rbdlab_const, "cluster_count", text="Cluster Count")
            cluster_section.prop(rbdlab_const, "cluster_min_chunks", text="Min Chunks")

            # CLUSTER SEARCH.
            cluster_section.label(text="Cluster Search", icon='VIEWZOOM')
            cluster_section.prop(rbdlab_const, "clusters_search_method", text="Method")
            col = cluster_section.column(align=True, heading="Radius")
            sub = col.row(align=True)
            sub.prop(rbdlab_const, "use_random_search_radius", text="Random")
            sub = col.row(align=True)
            sub.use_property_split = True
            if rbdlab_const.use_random_search_radius:
                sub.prop(rbdlab_const, "search_radius_range", text=" ")
            else:
                sub.prop(rbdlab_const, "search_radius", text=" ")

            cluster_section.separator()

            # SEARCH EXECUTE.
            clust_row = cluster_section.row()
            clust_row.use_property_split = False
            clust_row.prop(rbdlab_const, "search_over_selection", text="Use Selection")
            clust_row.prop(rbdlab_const, "add_inter_clusters")

            _row = cluster_section.row()
            _row.scale_y = 1.5
            _row.use_property_split = False
            _row.prop(rbdlab_const, "search_execute", toggle=True, text="Generate Clusters", icon='FILE_REFRESH')



def draw_create_tab(layout, rbdlab, ui, rbdlab_const, active_group):

        main_col = layout.box().column(align=True)

        # Input Collections to work with.
        # ++++++++++++++++++++++++++++++++++++
        section = main_col.column(align=True)
        section.use_property_split = False
        header = section.box().row(align=True)
        header.label(text="Source Collections", icon='GROUP')
        if not rbdlab_const.list:
            content = section.box().column(align=True)
            content.scale_y = 2
            content.operator("rbdlab.const_init_work_group", text="Load Collections", icon='FILE_REFRESH')
        else:
            header.operator("rbdlab.const_init_work_group", text="", icon='FILE_REFRESH')
            section.template_list("CONST_UL_work_group", "", rbdlab_const, "list", rbdlab_const, "list_index", rows=3)

        # Constraints Filter (apply by).
        # ++++++++++++++++++++++++++++++++++++
        draw_create_filter(main_col, rbdlab)

        # Constraints Settings.
        # ++++++++++++++++++++++++++++++++++++
        draw_const_settings(main_col, rbdlab, ui, rbdlab_const, active_group)

        # New Constraint settings.
        # ++++++++++++++++++++++++++++++++++++

        # main_col.separator()
        # row = main_col.column()
        # row.use_property_split = False
        # row.prop(rbdlab_const, "ignore_chunks_with_constraints")


        
        # CREATE!
        main_col.separator()
        alert = main_col.row()
        const_add_bt = main_col.row()
        const_add_bt.scale_y = 1.5
        if rbdlab.low_or_high_visibility_viewport != "Low":
            alert.box().label(text="Please, work in low visualization mode!", icon='ERROR')
            const_add_bt.enabled = False

        if rbdlab_const.filter_adjacents and rbdlab_const.apply_by != 'CLUSTER':
            label = "Create Adjacent Constraint Group"
        else:
            label = "Create Constraint Group"

        const_add_bt.operator("rbdlab.constraints_add", text=label)  # Add Glue Constraint

        # disable Create Constraint Group if is in clustering mode and not loadeed list:
        if not rbdlab_const.list and rbdlab.constraints.apply_by == 'CLUSTER':
            const_add_bt.enabled = False

        if rbdlab.filtered_target_collection is None:
            const_add_bt.enabled = False
