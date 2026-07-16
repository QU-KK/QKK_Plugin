# from ..main.main_panel import MainPanel
# from bpy.types import Panel
# from ...addon.naming import RBDLabNaming
from . import scatter_methods
from ....panels.common_ui_elements import collapsable, multiline_print


def draw_particle_settings(context, rbdlab, layout):
    if rbdlab.ui.scatter_mode not in {'STANDARD', 'BOOLEAN'}:
        return

    particle_systems = [obj.particle_systems for obj in context.selected_objects if obj.particle_systems]

    if not particle_systems:
        return

    # prevenir para q no muestre los settings de particulas con las particulas de Edge methods...
    if particle_systems[0][0].name.startswith("Particle_Scatter"):
        return

    col = layout.column()
    ps_obj = [obj.particle_systems for obj in context.selected_objects if "Detail_Scatter" in obj.particle_systems]
    vg_obj = [obj for obj in context.selected_objects if "paint" in obj.vertex_groups]
    if len(ps_obj) > 0 or len(vg_obj) > 0:
        col.prop(rbdlab, "particle_count", text="Painted")
        col.prop(rbdlab, "scatter_detail_size_particles", text="Size")
        col.prop(rbdlab, "scatter_detail_emit_from", text="From")

    # if any([obj.particle_systems for obj in context.selected_objects if RBDLabNaming.SECOND_SCATTER in obj.particle_systems]):
    check = [obj for obj in context.selected_objects if "scatter_plane_accepted" not in obj]

    if check:
        layout.separator()
        block1 = layout.column(align=True)
        colD = block1.column(align=True)
        colD.prop(rbdlab, "particle_secondary_count", text="Density")
        colD.enabled = rbdlab.scatter_secondary_distribution != 'GRID'
        col = block1.column(align=True)
        col.prop(rbdlab, "scatter_secondary_seed", text="Seed")
        if rbdlab.ui.scatter_mode == 'STANDARD':
            col.prop(rbdlab, "scatter_secondary_size_particles", text="Size")
        col.separator()
        col.prop(rbdlab, "scatter_secondary_emit_from", text="From")
        col.prop(rbdlab, "scatter_secondary_use_modifier_stack", text="Use Modifier Stack")

        if rbdlab.scatter_secondary_emit_from in ['VOLUME', 'FACE']:
            col.prop(
                rbdlab, "scatter_secondary_distribution", text="Distribution")
            if rbdlab.scatter_secondary_distribution in ['RAND', 'JIT']:
                col.prop(
                    rbdlab, "scatter_secondary_use_emit_random", text="Random Order")
                col.prop(
                    rbdlab, "scatter_secondary_use_even_distribution", text="Even Distribution")
            else:
                col.prop(
                    rbdlab, "scatter_secondary_invert_grid", text="Invert Grid")
                col.prop(
                    rbdlab, "scatter_secondary_hexagonal_grid", text="Hexagonal Grid")
            if rbdlab.scatter_secondary_distribution == 'JIT':
                col.prop(
                    rbdlab, "scatter_secondary_userjit", text="Particles/Face")
                col.prop(
                    rbdlab, "scatter_secondary_jitter_factor", text="Jittering Amount")
            if rbdlab.scatter_secondary_distribution == 'GRID':
                col.prop(
                    rbdlab, "scatter_secondary_grid_resolution", text="Resolution")
                col.prop(
                    rbdlab, "scatter_secondary_grid_random", text="Random")
        else:
            col.prop(
                rbdlab, "scatter_secondary_use_emit_random", text="Random Order")


def scatter(context, rbdlab, layout):

    main_col = layout.box().column(align=True)

    main_col.use_property_decorate = False
    main_col.use_property_split = False

    working_in_low = rbdlab.low_or_high_visibility_viewport == "Low"
    main_col.enabled = working_in_low

    header_methods_scale_y = 0.5
    methods_scale_y = 1.3

    # switcher_subsection = main_col.row(align=True)
    # switcher_subsection.scale_y = 1.3
    # switcher_subsection.prop(ui, "fracture_switch_scatter", expand=True)
    # main_col.separator()

    # if ui.fracture_switch_scatter == 'SCATTER':
    # Scatter Modes:
    col = main_col.column(align=True)
    box = col.box()
    if rbdlab.scatter_working:
        box.label(text="Working with %s Scatter" % rbdlab.ui.scatter_mode.capitalize(), icon='INFO')
    else:
        box.scale_y = header_methods_scale_y
        box.emboss = 'PULLDOWN_MENU'
        box.label(text="Scatter Methods")
        col_flow = col.column_flow(columns=2, align=True)
        col_flow.scale_y = methods_scale_y

        col_flow.prop(rbdlab.ui, "scatter_mode", text="Standard", expand=True)
        # col_flow.enabled = "BooleanFractureData" not in rbdlab

    # Condiciones para bloquear interfaz.
    if len(context.selected_objects) > 0 and [obj for obj in context.selected_objects if obj.type not in ['MESH', 'CURVE']]:
        # main_col.alert = True
        main_col.separator()
        multiline_print(main_col.box(), text="To continue, select a valid mesh object", max_words=7, first_line_crop=0, without_box=True)
        return

    # Draw settings/properties.
    layout.use_property_split = True
    args = (context, rbdlab, main_col)

    draw_particle_settings(*args)

    draw_scatter_settings = getattr(scatter_methods, "scatter_%s" % rbdlab.ui.scatter_mode.lower())
    draw_scatter_settings(*args)

    layout.separator()
    e_methods = collapsable(
        layout,
        rbdlab.ui,
        "show_hide_edge_methods",
        "Edge Methods",
        align=True,
    )
    if e_methods:

        # Edge Methods:
        main_col = e_methods.column(align=True)
        main_col.use_property_split = False
        col = main_col.column(align=True)
        box = col.box()

        box.scale_y = header_methods_scale_y
        box.emboss = 'PULLDOWN_MENU'
        box.label(text="Edge Methods")
        col_flow = col.column_flow(columns=3, align=True)
        col_flow.scale_y = methods_scale_y

        col_flow.prop(rbdlab.ui, "edge_methods", text="All", expand=True)

        # Draw settings/properties.
        main_col.use_property_split = True
        args = (context, rbdlab, main_col)

        # self.draw_particle_settings(*args)
        draw_edge_method_settings = getattr(scatter_methods, "edge_method_%s" % rbdlab.ui.edge_methods.lower())
        draw_edge_method_settings(*args)
