from ..main.module_panel import ModulePanel
from bpy.types import Panel, Object
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, get_props_in_order, ui_remesh_modifier, ui_smooth_modifier, ui_subsurf_modifier, ui_displace_modifier, ui_decimate_modifier, ui_solidify_modifier, multiline_print
from ...Global.get_common_vars import get_common_vars


class METAL_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'METAL'
    bl_label = "Module"
    bl_idname = "METAL_PT_ui"


    def draw(self, context):

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rbdlab, ui, tcoll_list = get_common_vars(context, get_rbdlab=True, get_ui=True, get_tcoll_list=True)
        
        # tcoll = tcoll_list.active
        tcoll_item = tcoll_list.active_item

        col = layout.column(align=True)
        title_header(col, "MetalSoft")

        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()
        
        switcher = main_col.row(align=True)
        switcher.use_property_split = False
        switcher.scale_y = 1.3
        switcher.prop(ui, "metal_subsections", expand=True)

        main_col = col.box().column(align=True)
        main_col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        # Listado:
        if tcoll_item:
            metal_list = tcoll_item.metal_list
            metal_active = metal_list.active
            if metal_active:
                metal_modifiers_list = metal_active.modifiers
        
        if ui.metal_subsections == 'REMESH':


            def headers(layout, mod, ui_text, ui_icon, active_ob:Object=None):
    
                if ui_icon != 'MOD_REMESH':
                    layout.separator()
    
                head = layout.box().row(align=True)
                head.label(text=ui_text, icon=ui_icon)
                right_bts = head.row(align=True)
                right_bts.alignment = 'RIGHT'

                if active_ob and ui_icon == 'MOD_REMESH': # muestro en el remesh un boton para verlo o no en wireframe:
                    right_bts.prop(active_ob.rbdlab, "metalsoft_remesh_toggle_wireframe_ob", toggle=True, text="", icon='SHADING_WIRE')
                
                right_bts.prop(mod, "show_viewport", text="")
                right_bts.prop(mod, "show_render", text="")

                close_bt = right_bts.row(align=True)
                close_bt.alert = True
                close_bt.operator("rbdlab.modifiers_rm_button", text="", icon='CANCEL').mod_to_rm = mod.name
                
                mod_settings = layout.box().column(align=True)
                return mod_settings

            def add_remesh(layout) -> None:
                create_bt = layout.row(align=True)
                create_bt.scale_y = 1.3
                create_bt.operator("rbdlab.metalsoft_add_modifier", text="Add Remesh").mod_type = 'REMESH'
            
            def add_decimate(layout) -> None:
                add_decimate_mod_bt = layout.row(align=True)
                add_decimate_mod_bt.scale_y = 1.3
                add_decimate_mod_bt.operator("rbdlab.metalsoft_add_modifier", text="Add Decimate").mod_type = 'DECIMATE'

            def apply_bt(layout, mod_name:str, stattus_bt:bool=True) -> None:
                apply_mod = layout.row(align=True)
                apply_mod.scale_y = 1.3
                apply_mod.enabled = stattus_bt
                apply_mod.operator("rbdlab.modifiers_apply_mod", icon='CHECKMARK').mod_to_apply = mod_name

            def update_bt(layout) -> None:
                update_mod = layout.row(align=True)
                update_mod.scale_y = 1.3
                update_mod.operator("rbdlab.metalsoft_remesh_update_modifiers")
                        
            # UI Remesh Modifiers:
            # main_col.separator()
            active_ob = context.active_object
            if active_ob:

                remesh_mod = active_ob.modifiers.get(RBDLabNaming.REMESH_ORIGNAL)
                decimate_mod = active_ob.modifiers.get(RBDLabNaming.DECIMATE_ORIGINAL)

                if any([remesh_mod, decimate_mod]):

                    feedback_text = "Configure settings for active object. Update button syncs changes for the remaining selected objects."
                    feedback = main_col.row(align=True)
                    multiline_print(feedback, feedback_text, max_words=6, first_line_crop=1)

                # main_col.separator()
                
                if remesh_mod:
                    mod_settings = headers(main_col, remesh_mod, "Remesh Modifier Original", 'MOD_REMESH', active_ob)
                    ui_remesh_modifier(context, mod_settings, remesh_mod)
                    row_bts = main_col.row(align=True)
                    apply_bt(row_bts, remesh_mod.name)
                    update_bt(row_bts)
                
                else:
                    add_remesh(main_col)
            
                if decimate_mod:
                    mod_settings = headers(main_col, decimate_mod, "Decimate Modifier", 'MOD_DECIM')
                    ui_decimate_modifier(context, mod_settings, decimate_mod)

                    row_bts = main_col.row(align=True)
                    # NOTA: Hasta que no esté (aplicado/o sin el) el de arriba, lo pongo en gris.
                    # esto lo hago porque en blender hay q aplicar los modificadores de arriba a abajo.
                    apply_bt(row_bts, decimate_mod.name, not remesh_mod)
                    update_bt(row_bts)

                else:
                    main_col.separator()
                    add_decimate(main_col)
            
            else:
                main_col.box().label(text="Not valid Active Object!", icon='INFO')

        elif ui.metal_subsections == 'METAL_CREATION':
            # main_col.separator()

            if not tcoll_item:
                main_col.box().label(text="Not valid Target Collection", icon='INFO')
                return

            
            main_col.template_list("RBDLAB_UL_draw_metal", "", metal_list, "list", metal_list, "list_index", rows=1)
            
            # Botones del listado:
            buttons = main_col.row(align=True)
            buttons.scale_y = 1.3

            create = buttons.row(align=True)
            create.operator("rbdlab.metalsoft_creation_create_metal_mesh", text="Create Mesh Deform")
            # solo permito crear si no hay ya creados metales en este tcoll:
            create.enabled = metal_list.is_void

            rebind = buttons.row(align=True)
            rebind.operator("rbdlab.metalsoft_creation_rebind", text="Rebind")

            #------------------------------------------------------------------------------------------
            
            metal_mesh_created = True
            metal_props = tcoll_item.metal_props

            proxys = main_col.box().column(align=True)
            proxys.use_property_split = False

            other_org = proxys.row(align=True)
            other_org.enabled = not metal_props.use_multiple_proxys 
            other_org.use_property_split = False
            other_org.prop(metal_props, "other_original")
            
            other_ob = other_org.row(align=True)
            other_ob.alert = metal_props.other_original and metal_props.ob_original_selector is None 
            other_ob.prop(metal_props, "ob_original_selector", text="")
            other_ob.enabled = metal_props.other_original

            proxys.prop(metal_props, "use_multiple_proxys", text="Use Multiple Originals") # Use Multiple Proxys
            if metal_props.use_multiple_proxys:
                proxys.separator(factor=0.5)
                proxys.box().label(text="Proxies must share the same origin as originals.", icon='INFO')
                proxys.separator(factor=0.5)


            add_bts = proxys.row(align=True)
            add_bts.scale_y = 1.3
            add_bts.operator("rbdlab.metalsoft_creation_add_proxy_mesh", text="Set Proxy Meshes")
            add_bts.separator(factor=0.7)
            add_bts.operator("rbdlab.metalsoft_creation_add_original_mesh", text="Set Original Meshes")
            add_bts.enabled = metal_props.use_multiple_proxys

            # listado de modifiers:
            if metal_active:
                main_col.separator()
                metal_modifiers = main_col.box().column(align=True)
                metal_modifiers.label(text="Modifiers Layers", icon='MODIFIER')
                
                
                m_modifiers = main_col.column(align=True)
                m_modifiers.template_list("RBDLAB_UL_draw_metal_modifiers", "", metal_modifiers_list, "list", metal_modifiers_list, "list_index", rows=3)
                
                add_modifiers_bt = m_modifiers.row(align=True)
                add_modifiers_bt.scale_y = 1.3
                add_modifiers_bt.operator("rbdlab.metalsoft_creation_add_modifiers", text="Add Modifier")

                add_modifiers_bt.operator("rbdlab.metalsoft_creation_modifiers_list_item_move", icon='TRIA_UP', text="").direction = 'UP'
                add_modifiers_bt.operator("rbdlab.metalsoft_creation_modifiers_list_item_move", icon='TRIA_DOWN', text="").direction = 'DOWN'


                main_col.separator()


                if metal_mesh_created:
                    main_col.box().label(text="Layer Settings", icon='SETTINGS')
                    mod_settings = main_col.column(align=True)

                    if metal_mesh_created:

                        active_item = metal_modifiers_list.active
                        if active_item:
            

                            active_mod = metal_modifiers_list.get_active_mod_in_first_object

                            header = main_col.box().row(align=True)
                            header.alignment = 'RIGHT'
                            # header.use_property_split = False
                            mod_settings = main_col.box().column(align=True)

                            # Itera a través de las propiedades del modificador
                            header.label(text="Modifier ")
                            mod_name_fake = header.box()
                            mod_name_fake.scale_y = 0.55 
                            mod_name_fake.scale_x = 0.81 
                            mod_name_fake.label(text=active_item.label_txt + " ")

                            if active_item:
                                vali_props = [prop for prop in active_mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False] 

                            # Utilidades para la ui de modifiers ----------------------------------------------------------------------------
                            
                            def headers(layout, header_target:list) -> None:
                                header_props = get_props_in_order(vali_props, header_target)
                                for head_prop in header_props:
                                    layout.prop(active_mod, head_prop, text="")
                            
                            # header_props_light = ["show_in_editmode", "show_viewport", "show_render"]
                            # header_props_full = ["show_on_cage", "show_in_editmode", "show_viewport", "show_render"] 
                            header_props_light = ["show_in_editmode"]
                            # Oculto los iconos "show_on_cage" y "show_in_editmode":
                            # header_props_full = ["show_on_cage", "show_in_editmode"]
                            header_props_full = []


                            # End Utilidades para la ui de modifiers ------------------------------------------------------------------------

                            if active_item.mod_type == 'REMESH' :

                                headers(header, header_props_light)
                                ui_remesh_modifier(context, mod_settings, active_mod)
                            
                            elif active_item.mod_type == 'SMOOTH':

                                headers(header, header_props_full)
                                ui_smooth_modifier(context, mod_settings, active_mod)
                                
                            elif active_item.mod_type == 'SUBSURF':
                                
                                headers(header, header_props_full)
                                ui_subsurf_modifier(context, mod_settings, active_mod)

                            elif active_item.mod_type == 'DISPLACE':
                                
                                headers(header, header_props_full)
                                ui_displace_modifier(context, mod_settings, active_mod)
                            
                            elif active_item.mod_type == 'SOLIDIFY':
                                
                                headers(header, header_props_full)
                                ui_solidify_modifier(context, mod_settings, active_mod)
                            
                            elif active_item.mod_type == 'DECIMATE':
                                
                                headers(header, header_props_full)
                                ui_decimate_modifier(context, mod_settings, active_mod)

                            update_bt = main_col.box().row(align=True)
                            update_bt.scale_y = 1.3
                            update_bt.operator("rbdlab.metalsoft_creation_update_modifiers")


                    #----------------------------------------------------------------------------------------------
                    item = metal_list.active
                    if item:
                        mod_settings.enabled = 'METAL' in item.metal_or_fractures
                    else:
                        mod_settings.enabled = False

                    main_col.separator()

            clean_collection = main_col.column(align=True)
            clean_coll = collapsable(
                clean_collection,
                ui,
                "show_hide_metal_clean_collection",
                "Clean Collection",
                'BRUSH_DATA',
                align=True,
            )
            if clean_coll:

                clean_coll.use_property_split = False
                clean_coll.prop(metal_props, "metal_decimate_planar", text="Decimate Planar")
                clean_coll.prop(metal_props, "metal_triangulate", text="Triangulate")

                clean_coll.prop(metal_props, "use_multi_face", text="Multiple Faces")
                clean_coll.prop(metal_props, "use_boundary", text="Boundary")

                clean_coll.prop(metal_props, "metal_remove_doulbes", text="Remove Doubles")
                clean_bt = clean_coll.row(align=True)
                clean_bt.scale_y = 1.3
                clean_bt.operator("rbdlab.metalsoft_creation_clean_fractures", text="Mesh Clean Fractures")
                clean_bt.enabled = any([metal_props.metal_decimate_planar, metal_props.metal_triangulate, metal_props.use_multi_face, metal_props.use_boundary, metal_props.metal_remove_doulbes])

