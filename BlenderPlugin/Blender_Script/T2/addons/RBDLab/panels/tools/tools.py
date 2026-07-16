from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ..common_ui_elements import title_header, collapsable, cheker_item_visibility, multiline_print
from ...addon.naming import RBDLabNaming


def fracture_restore(layout, ui):
    fracture_restore = collapsable(
        layout,
        ui,
        "show_fracture_restore",
        "Restore",
        'RECOVER_LAST',
        align=True,
    )
    if fracture_restore:
        fracture_restore.scale_y = 1.3
        fracture_restore.operator("rbdlab.scatter_restore", text="Scatter Restore")
        fracture_restore.operator("rbdlab.fracture_restore", text="Fracture Restore")
        fracture_restore.operator("rbdlab.not_working_now_in_inner_details", text="Not Working in Inner Details Now")


def clear_attributes(layout, ui):

    # Clear Limbo Blender Special Collections:
    clear_limbo = collapsable(
        layout,
        ui,
        "show_clear_ob_in_limbo_from_special_colls",
        "Clear Objects in limbo",
        'TRASH',
        align=True,
    )
    if clear_limbo:
        "from Blender Special Collections"
        
        feedback = clear_limbo.column(align=True)
        text = "Clear Objects in limbo from Blender Special Collections: " + RBDLabNaming.RBD_WORLD + " and " +RBDLabNaming.RBD_CONSTRAINTS 
        multiline_print(feedback, text, max_words=5, first_line_crop=2)
        clear_limbo.separator()

        buttons = clear_limbo.column(align=True)
        buttons.scale_y = 1.3
        buttons.operator("rbdlab.clear_rigidbody_objects_in_limbo", text="Clear RBD Objects")
        buttons.operator("rbdlab.clear_constraints_objects_in_limbo", text="Clear Constraints Objects")

    layout.separator()
    # Clear Attributes:
    clear_attributes = collapsable(
        layout,
        ui,
        "show_clear_attr",
        "Clear RBDLab Attributes",
        'TRASH',
        align=True,
    )
    if clear_attributes:
        clear_attributes.scale_y = 1.3
        clear_attributes.operator("rbdlab.clear_velocities", text="Clear Velocities")
        clear_attributes.operator("rbdlab.clear_motions", text="Clear Motions")
        clear_attributes.operator("rbdlab.clear_attr", text="Clear All Attrs")
        # clear_attributes.operator("rbdlab.compute_velocities", text="Compute Velocities")

    

def misc(layout, ui):

    # recalculate_neighbors = collapsable(
    #     layout,
    #     ui,
    #     "show_unhide_recalculate_neighbors",
    #     "Recalculate Neighbors",
    #     'LIGHTPROBE_VOLUME',
    #     align=True,
    # )
    # if recalculate_neighbors:
    #     recalculate_neighbors.scale_y = 1.3
    #     recalculate_neighbors.operator("rbdlab.recalculate_neighbors", text="Recalculate Neighbors")
    
    # layout.separator()
    
    visibility = collapsable(
        layout,
        ui,
        "show_unhide_emitters",
        "Visibility",
        'HIDE_OFF',
        align=True,
    )
    if visibility:
        visibility.scale_y = 1.3
        visibility.operator("rbdlab.unhide_emitters_with_particles", text="Unhide Emitters")


    # cleaning_obs = collapsable(
    #     layout,
    #     ui,
    #     "show_unhide_cleaning_obs",
    #     "Cleaning obs",
    #     'TRASH',
    #     align=True,
    # )
    # if cleaning_obs:
    #     cleaning_obs.scale_y = 1.3
    #     cleaning_obs.operator("rbdlab.rm_obs_with_less_than_3_verts",
    #                           text="Clean objects with less than 3 vertices (in Low and High)")
    
    layout.separator()
    select_neighbors = collapsable(
        layout,
        ui,
        "show_unhide_select_neighbors",
        "Select Neighbors",
        'RESTRICT_SELECT_OFF',
        align=True,
    )
    if select_neighbors:
        select_neighbors.scale_y = 1.3
        
        # Usando los vecinos computados por cython:
        select_neighbors.operator("rbdlab.select_debug_neighbours", text="Select Neighbors").incremental = False

        # Incremental metodo propio:
        # select_neighbors.operator("rbdlab.select_neighbors", text="Select Neighbors")
    


def bake_uvs_world(layout, ui, rbdlab):
    bake_uvs_world = collapsable(
        layout,
        ui,
        "show_world_position",
        "Bake UVs World Position",
        'FILE_CACHE',
        align=True,
    )
    if bake_uvs_world:

        feedback = bake_uvs_world.column(align=True)
        text = "For use procedural materials in your external materials."
        multiline_print(feedback, text, max_words=4, first_line_crop=0)

        bake_uvs_world.separator()

        col = bake_uvs_world.column()
        flow = col.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        flow.alignment = 'RIGHT'
        flow.label(text="World Position To:")
        flow.scale_y = 1.3

        wpr = flow.row(align=True)
        wpr.use_property_split = False
        wpr.scale_x = 3.02
        wpr.prop(rbdlab, "world_position_to", text=" ",  expand=True)

        flow.label(text="")
        awp = flow.row(align=True)
        awp.scale_x = 2.05
        awp.operator("rbdlab.add_world_position_attr", text="Add World Position")

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                chunk = None
                for obj in rbdlab.filtered_target_collection.objects:
                    if obj.type == 'MESH' and obj.visible_get():
                        chunk = obj
                        break

                if chunk:
                    if RBDLabNaming.WORLD_POSITION in chunk.data.attributes:
                        bake_uvs_world.separator()
                        feedback = bake_uvs_world.column(align=True)
                        text = "Now you can use an Attribute name node in your external materials to use it as uvs. The the attribute name you must use is \"wpos\"."
                        multiline_print(feedback, text, max_words=7, first_line_crop=0)


class TOOLS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'TOOLS'
    bl_label = "Module"
    bl_idname = "TOOLS_PT_ui"


    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.enabled = cheker_item_visibility(context)

        col = layout.column(align=True)

        title_header(col, "Tools")

        main_col = col.box().column(align=True)

        switch_subcats = main_col.row(align=True)
        switch_subcats.use_property_split = False
        switch_subcats.scale_y = 1.3
        switch_subcats.prop(ui, "tools_switch_subsections", expand=True)
        # main_col.separator()

        if ui.tools_switch_subsections == 'FRACTURE_RESTORE':
            fracture_restore(col, ui)
        elif ui.tools_switch_subsections == 'CLEAR_ATTRIBUTES':
            clear_attributes(col, ui)
        elif ui.tools_switch_subsections == 'MISC':
            misc(col, ui)
        elif ui.tools_switch_subsections == 'BAKE_UVS_WORLD':
            bake_uvs_world(col, ui, rbdlab)
