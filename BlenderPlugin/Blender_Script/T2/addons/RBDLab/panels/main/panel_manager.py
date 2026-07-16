from bpy.types import Panel
from .visualization import draw_visualization_settings
from ...addon.icons import get_icon
from ...__init__ import bl_info
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import collapsable, multiline_print
from ...Global.functions import get_high_collection_objects
# para el popup que salia a la derecha del target collection
# ahora no se usa


class RBDLAB_PT_utils_dropdown(Panel):
    bl_label = "Utilities"
    bl_category = "RBDLab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = 'NONE'

    def draw(self, context):
        layout = self.layout
        # rbdlab = context.scene.rbdlab

        # Colors...
        colors = layout.column()
        colors.operator("rbdlab.randcolor", text="Random Colors")
        colors.operator("rbdlab.selecbycolor", text="Select by Color")
        colors.active = context.active_object is not None

        # col = layout.column()
        # if rbdlab.show_boundingbox:
        #     text_show_hide_bbox = "Hide BoundingBox"
        # else:
        #     text_show_hide_bbox = "Show BoundingBox"
        # col.prop(rbdlab, "show_boundingbox", text=text_show_hide_bbox, toggle=True)


class PanelManager(Panel):
    bl_idname = "RBDLAB_PT_panel_manager"
    bl_category = "RBDLab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    # bl_options = {'HIDE_HEADER'}
    # bl_label = ""
    bl_label = "RBDLab %s MetalSoft" % str(bl_info["version"])[1:-1].replace(",", ".").replace("\'", "").replace(" ", "")
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("RBDLab_Logo_256"))

    def draw(self, context):
        layout = self.layout.column(align=True)

        scn = context.scene
        rbdlab = scn.rbdlab
        
        ui = rbdlab.ui
        
        # Target Collection
        tcoll_coll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_coll_list.active

        have_tc = rbdlab.filtered_target_collection is not None
        if have_tc:
            have_tc_name = rbdlab.filtered_target_collection.name is not None
            if have_tc_name:
                tc_name = rbdlab.filtered_target_collection.name

        # row = layout.row(align=True)
        # row.prop_search(rbdlab, "filtered_target_collection", bpy.data, "collections", text="")
        # layout.separator()

        # listado de target collections:
        fracture_applied = rbdlab.is_fractured()

        # button_settings1 = {
        #     "type": "operator",
        #     "prop": "rbdlab.add_custom_collection",
        #     "text": "+",
        #     "icon": None,
        #     "scale_x": 0.6,
        # }
        tc_list = collapsable(
            layout,
            ui,
            "show_hide_target_coll_list",
            "Target Collections",
            'OUTLINER_COLLECTION',
            align=True,
            # button_settings1=button_settings1,
        )

        if tc_list:
            tc_list_row = tc_list.row(align=True)
            col_left = tc_list_row.column(align=True)
            col_left.template_list("RBDLAB_UL_draw_target_coll_list", "", tcoll_coll_list, "list", tcoll_coll_list, "list_index", rows=4)
            if fracture_applied:
                col_left.enabled = fracture_applied

            col_right = tc_list_row.column(align=True)
            col_right.alignment = 'LEFT'
            col_right.scale_x = 0.67
            col_right.scale_y = 1.04

            # sidebar_right.use_property_split = True
            # sidebar_right.use_property_decorate = False

            select_by_color = col_right.row(align=True)
            select_by_color.scale_x = 0.66

            # si hay algún mesh seleccionado:
            if tcoll:

                # recopilamos los objetos de low y de high:
                high_objects = get_high_collection_objects(tcoll)

                # Convierte ambas listas en conjuntos para eliminar duplicados
                conjunto1 = set(tcoll.objects[:])
                conjunto2 = set(high_objects)

                # Agrega el conjunto2 al conjunto1
                conjunto1.update(conjunto2)

                # Convierte el conjunto1 de nuevo a una lista si lo deseas
                all_objects = list(conjunto1)

                # Verifica si algún objeto de la colección "high" está seleccionado
                select_by_color.enabled = any(ob.type == 'MESH' and ob in all_objects for ob in context.selected_objects)

            else:
                select_by_color.enabled = False 

            select_by_color.operator("rbdlab.selecbycolor", text="Sel Color")

            col_right.prop(rbdlab, "size_delimiter_big", text=">", icon='BLANK1')
            col_right.prop(rbdlab, "size_delimiter_small", text="<", icon='BLANK1')
            col_right.operator("rbdlab.invert_selection", text="Invert", icon='ARROW_LEFTRIGHT')
            
            rand_color = col_right.column(align=True)
            rand_color.scale_x = 0.67
            rand_color.enabled = not rbdlab.filtered_target_collection is None
            rand_color.operator("rbdlab.randcolor", text="Rand Color")

            # Recompute Neighbors:
            col_right.operator("rbdlab.recalculate_neighbors", text="Nbrs")

            buttons_below = col_left.row(align=True)
            buttons_below.scale_y = 1
            buttons_below.operator("rbdlab.add_custom_collection", text="Add Custom Collection")

            sbg_b = buttons_below.row(align=True)
            sbg_b.enabled = len(tcoll_coll_list.list) > 0

            sbg_b.alignment = 'RIGHT'
            sbg_b.operator("rbdlab.target_collection_list_item_move", icon='TRIA_UP', text="").direction = 'UP'
            sbg_b.operator("rbdlab.target_collection_list_item_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
            
            dropdown = sbg_b.row(align=True)
            dropdown.alignment = 'CENTER'
            dropdown.menu("RBDLAB_MT_target_collection_submenu", text="")

        if tcoll:

            item = tcoll_coll_list.active_item
            if not item.visibility:
                feedback = layout.box().column(align=True)
                text = "Cannot work with " + tcoll.name + " collection if it is hidden."
                max_words = 5
                multiline_print(feedback, text, max_words)

            else:
                layout.box().box().label(text=RBDLabNaming.WORKING_WITH + tcoll.name, icon='INFO')

        # if rbdlab.filtered_target_collection:
        #     row.prop(rbdlab.ui, "show_target_collection_info", text="", icon='INFO')
        # row.operator("rbdlab.rm_target_coll", text="", icon='TRASH')

        # sub = row.row(align=True)
        # sub.enabled = rbdlab.filtered_target_collection is not None
        # sub.popover(panel="RBDLAB_PT_utils_dropdown", text="", icon='PROPERTIES')

        # feedback have velocities, motions:
        if have_tc and rbdlab.ui.show_target_collection_info:
            if have_tc_name:
                content_feedback = layout.column(align=True).box()
                content_feedback.alert = True
                if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection or "computed_motions" in rbdlab.filtered_target_collection:
                    have_velocities = content_feedback.row()
                    if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection:
                        have_velocities.alert = False
                        have_velocities.label(text=tc_name + " have velocities", icon='INFO')
                    else:
                        have_velocities.alert = True
                        have_velocities.label(text=tc_name + " not have velocities", icon='INFO')

                    have_motions = content_feedback.row()
                    if "computed_motions" in rbdlab.filtered_target_collection:
                        have_motions.alert = False
                        have_motions.label(text=tc_name + " have motions", icon='INFO')
                    else:
                        have_motions.alert = True
                        have_motions.label(text=tc_name + " not have motions", icon='INFO')
                else:
                    content_feedback.row().label(text=tc_name + " not have velocities", icon='INFO')
                    content_feedback.row().label(text=tc_name + " not have motions", icon='INFO')

        layout.separator()

        # header_methods_scale_y = 0.5
        # methods_scale_y = 1.3

        # Selection Tools:
        # col = layout.column(align=True)
        # box = col.box().row()
        # box.alignment = 'CENTER'
        # box.scale_x = 1.1

        # box.scale_y = header_methods_scale_y
        # box.emboss = 'PULLDOWN_MENU'
        # box.label(text="Selection Tools")
        # selection_tools = col.column(align=True)
        # selection_tools.scale_y = methods_scale_y
        # st_size_y = 0.9

        # st_row1 = selection_tools.row(align=True)
        # st_row1.scale_y = st_size_y

        # (posible utilizacion) st_row1.operator("rbdlab.randcolor", text="Random Color")

        # selection_tools.separator()

        # st_row2 = selection_tools.row(align=True)
        # st_row2.scale_y = st_size_y

        # st_row2.operator("rbdlab.selecbycolor", text="Select by Color")
        # st_row2.operator("rbdlab.invert_selection", text="", icon='ARROW_LEFTRIGHT')

        # (posible utilizacion) st_row2.operator("rbdlab.chunks_without_movement", text="Select Chunks without movement")
        # (posible utilizacion) st_row2.prop(rbdlab.ui, "show_motion_threshold", text="", icon='SETTINGS')
        # (posible utilizacion) if rbdlab.ui.show_motion_threshold:
        # (posible utilizacion)     motion_threshold = selection_tools.row(align=True)
        # (posible utilizacion)     motion_threshold.prop(rbdlab, "motion_threshold", text="")
        # (posible utilizacion)     if not have_tc or not have_tc_name:
        # (posible utilizacion)         motion_threshold.enabled = False
        # (posible utilizacion) if not have_tc or not have_tc_name:
        # (posible utilizacion)     st_row2.enabled = False

        # big_small = selection_tools.row(align=True)
        # big_small.prop(rbdlab, "size_delimiter_big", text="Big")
        # big_small.prop(rbdlab, "size_delimiter_small", text="Small")

        # sel_compound = selection_tools.row(align=True)
        # sel_compound.use_property_split = False
        # sel_compound.operator("rbdlab.select_compounds", text="Select Compounds")
        # if rbdlab.filtered_target_collection is None or RBDLabNaming.EDGE_COMPOUND_PARENTED not in rbdlab.filtered_target_collection:
        #     sel_compound.enabled = False

        # selection_tools.separator()

        # Select by size:
        # layout.use_property_split = True
        # layout.use_property_decorate = False
        # st_row3 = selection_tools.row(align=True)
        # st_row3.scale_y = st_size_y
        # st_row1.operator("rbdlab.invert_selection", text="", icon='ARROW_LEFTRIGHT')
        # big_small = selection_tools.row(align=True)
        # big_small.prop(rbdlab, "size_delimiter_big", text="Big")
        # big_small.prop(rbdlab, "size_delimiter_small", text="Small")
        # if not have_tc or not have_tc_name:
        #     st_row3.enabled = False
        # layout.use_property_split = False

        # layout.separator()

        # Main Modules
        # Sections selector...
        sections = layout.column(align=True)
        box = sections.box().row()
        box.scale_y = 0.8

        header_1 = box.row(align=True)
        header_1.emboss = 'PULLDOWN_MENU'
        header_1.alignment = 'LEFT'

        if rbdlab.ui.collapse_module_selector:

            # renaming on the fly: Activators to Activators
            main_modules = rbdlab.ui.main_modules
            if main_modules == 'ACTIVATORS':
                main_modules = "Activators"

            header_1.prop(rbdlab.ui, "collapse_module_selector", text="Main Modules [ %s ]" % (
                main_modules.capitalize()), icon='WINDOW', emboss=False)

        else:
            header_1.prop(rbdlab.ui, "collapse_module_selector", text="Main Modules", icon='WINDOW', emboss=False)

        header_2 = box.row(align=True)
        header_2.emboss = 'PULLDOWN_MENU'
        header_2.alignment = 'RIGHT'
        header_2.prop(rbdlab.ui, "collapse_module_selector", text="", icon='ADD' if rbdlab.ui.collapse_module_selector else 'REMOVE', emboss=False)

        if rbdlab.ui.collapse_module_selector:
            size_items = len(rbdlab.ui.module_items)
            sections = sections.grid_flow(
                row_major=True, even_columns=True,
                even_rows=True, align=True, columns=size_items
            )
            sections.scale_y = 1.3
            sections.prop(rbdlab.ui, "main_modules_collapsed", text="",  expand=True)
        else:
            sections = sections.grid_flow(
                row_major=True, even_columns=True,
                even_rows=True, align=True, columns=2
            )
            sections.scale_y = 1.3
            sections.prop(rbdlab.ui, "main_modules", expand=True)
        
        # Oculto las tools temporales de testing solo si estamos viendo el main module tools:
        # if ui.main_modules == 'TOOLS':

            # ----------------------------------------------------------------
            # DEBUG - Select Adjacents
            # layout.separator()
            # layout.operator("rbdlab.select_acjacents", text="Select Adjacents")
            # layout.prop(ui, "select_adjacents", text="Select Adjacents")
            # ----------------------------------------------------------------
            
            # ----------------------------------------------------------------
            # DEBUG - DEVELOPER OPTIONS - ONLY FOR DEVELOPMENT
            # layout.separator()
            # layout.operator("rbdlab.select_debug_neighbours", text="Select (Debug) Neighbors")
            # layout.operator("rbdlab.clear_debug_neighbours", text="Clear (Debug) Neighbors")
            # ----------------------------------------------------------------


        layout.separator()
        have_rbdlab_boolean_mod = rbdlab.have_rbdlab_boolean_modifier()
        # fracture_applied = rbdlab.is_fractured()
        
        # si no tiene modifiers booleans, o si se esta en alguna fase del boolean fracture nuevo (GN Boolean):
        if have_rbdlab_boolean_mod or ui.boolean_method_phase != 'NONE':
            if not fracture_applied:
                label = layout.row().box().box()
                # label.alert = True
                multiline_print(label, text="To continue, it is necessary first apply the fractures in: Fracture > Details", max_words=8, first_line_crop=2, without_box=True, icon='ERROR')
                sections.enabled = False
        else:
            # Mesh Visualization Options
            draw_visualization_settings(layout, context)
