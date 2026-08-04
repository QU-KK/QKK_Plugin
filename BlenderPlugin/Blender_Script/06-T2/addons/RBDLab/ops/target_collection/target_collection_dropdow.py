import bpy
from ...addon.naming import RBDLabNaming
from bpy.types import Operator, Collection
from ...Global.get_common_vars import get_common_vars
from ...Global.functions import set_active_collection_to_master_coll, remove_collection_if_is_empty

class RBLAB_OT_target_collection_dropdown_select_objects(Operator):
    bl_label = "Select all objects"
    bl_description = "Select all objects in the active target collection"
    bl_idname = "rbdlab.target_collection_dropdown_select_objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                for obj in rbdlab.filtered_target_collection.objects:
                    obj.select_set(True)

        return {'FINISHED'}


class RBLAB_OT_target_collection_dropdown_merge_collections(Operator):
    bl_label = "Merge Collections"
    bl_description = "Merge collection to another collection"
    bl_idname = "rbdlab.target_collection_dropdown_merge_collections"
    bl_options = {'REGISTER', 'UNDO'}


    def invoke(self, context, event):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        rcoll = rbdlab.root_collection
        
        mrg_coll_list = rbdlab.lists.merge_collections_list
        mrg_coll_list.clear_all_colls

        # por defecto sugerimos el active target collection:
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if tcoll:
            rbdlab.ui.coll_to = tcoll

        if rcoll:

            blacklist_collections = [
                                        rcoll.name, 
                                        RBDLabNaming.RBD_CONSTRAINTS, 
                                        RBDLabNaming.RBD_WORLD, 
                                        RBDLabNaming.ORIGINALS, 
                                        RBDLabNaming.CONSTRAINTS, 
                                        RBDLabNaming.CONST_COLL,
                                        RBDLabNaming.METAL_MESHES, 
                                        RBDLabNaming.METAL_LINKS_COLL
                                    ]
            
            for coll in rcoll.children_recursive:
                
                if coll is None:
                    continue
                
                if not coll.name:
                    continue
                    
                if coll.name in blacklist_collections or "_GlueConstraints" in coll.name or "Debris" in coll.name or \
                    coll.name.endswith(RBDLabNaming.SUFIX_HIGH) or coll.name.startswith(RBDLabNaming.PREFIX_CONST) or RBDLabNaming.METAL_LINKS_COLL in coll:
                    continue
                
                mrg_coll_list.add_item(coll)
                blacklist_collections.append(coll)

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        rbdlab, ui = get_common_vars(context, get_rbdlab=True, get_ui=True)
        
        mrg_coll_list = rbdlab.lists.merge_collections_list

        main_row = layout.row(align=True)
        main_row.use_property_decorate = False
        main_row.use_property_split = False
        
        left_col = main_row.column(align=True)
        # left_col.scale_x = 0.5
        left_col.template_list("RBDLAB_UL_draw_merge_collections", "", mrg_coll_list, "list", mrg_coll_list, "list_index", rows=6)

        main_row.separator()
        right_col = main_row.column(align=True)

        coll_to = right_col.row(align=True)

        # si las que se quieren traer no son el destino deseado bloqueamos:
        all_selected_colls = mrg_coll_list.get_all_selected_collections
        # coll_to.enabled = ui.coll_to not in all_selected_colls
        coll_to.alert = ui.coll_to in all_selected_colls
        coll_to.prop(ui, "coll_to", text="")

        # feedback:
        # no me deja importar multiline_print aqui, por eso uso el codigo directo, daba circular import...
        right_col.separator()
        text = "Here you will move the chunks of the collections on the left side to the desired Collection on the right side."
        max_words = 5
        words = text.split()
        feedback = right_col.box().column(align=True)
        for i in range(0, len(words), max_words):
            sentence = words[i:i+max_words]
            sentence = " ".join(sentence)
            if i == 0:
                feedback.label(text=sentence, icon='INFO')
            else:
                feedback.label(text=sentence)


    def has_constraints(self, collection:Collection) -> bool:
        # si el chunk tiene rbdlab_constraints es que tiene constraints:
        if collection is not None:
            return next((True for ob in collection.objects if RBDLabNaming.CONSTRAINTS in ob), False)
    

    def process_highs(self, context, coll_from:Collection, coll_to:Collection) -> None:
        if coll_from is None:
            return
        
        # Si hay highs, procedemos con los low:
        if coll_from.name.endswith(RBDLabNaming.SUFIX_LOW):
            coll_from_high_name = coll_from.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        else:
            coll_from_high_name = coll_from.name + RBDLabNaming.SUFIX_HIGH
        
        if coll_to.name.endswith(RBDLabNaming.SUFIX_LOW):
            coll_to_high_name = coll_to.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        else:
            coll_to_high_name = coll_to.name + RBDLabNaming.SUFIX_HIGH

        coll_from_high = bpy.data.collections.get(coll_from_high_name)
        coll_to_high = bpy.data.collections.get(coll_to_high_name)

        if coll_from_high and coll_to_high:

            coll_from_high_objects = coll_from_high.objects

            if coll_from_high_objects:

                for ob in coll_from_high_objects:

                    # lo meto en la nueva si no estuviera:
                    if ob.name not in coll_to_high.objects:
                        coll_to_high.objects.link(ob)

                    # lo quito de la collection original
                    if ob.name in coll_from_high_objects:
                        coll_from_high_objects.unlink(ob)
                
                remove_collection_if_is_empty(context, coll_from_high)


    def execute(self, context):

        rbdlab, ui, tcoll_list = get_common_vars(context, get_rbdlab=True, get_ui=True, get_tcoll_list=True)
        coll_to = ui.coll_to
        

        if coll_to is None:
            self.report({'ERROR'}, "The Destination Collection has been left empty!")
            return {'CANCELLED'}
        
        rbdlab_const_list = rbdlab.constraints

        mrg_coll_list = rbdlab.lists.merge_collections_list
        all_selected_colls = mrg_coll_list.get_all_selected_collections
        
        if coll_to in all_selected_colls:
            self.report({'ERROR'}, "The Source Collections cannot be the same as the Destination Collection!")
            return {'CANCELLED'}
        
        # Comprobar constraints en la colección destino:
        if self.has_constraints(coll_to):
            self.report({'WARNING'}, "The Collection " + coll_to.name + " has Constraints")
            return {'CANCELLED'}

        # Comprobar constraints las colecciones de origen:
        for coll_from in all_selected_colls:
            if self.has_constraints(coll_from):
                self.report({'WARNING'}, "The Collection " + coll_from.name + " has Constraints")
                return {'CANCELLED'}
        
        # comprobar si tiene metal en la colección destino:
        
        c_to_item = tcoll_list.get_item_by_name(coll_to.name)
        if not c_to_item:
            self.report({'WARNING'}, "Not " + coll_to.name + " Collection!")
            return {'CANCELLED'}
        
        if c_to_item.metal_list.is_void == False:
            self.report({'WARNING'}, "The Collection " + coll_to.name + " has Metal")
            return {'CANCELLED'}

        # comprobar si tiene metal en las colecciones de origen:
        for coll_from in all_selected_colls:
            
            if coll_from is None:
                continue

            c_from_item = tcoll_list.get_item_by_name(coll_from.name)
            if not c_from_item:
                self.report({'WARNING'}, "Not " + coll_from.name + " Collection!")
                return {'CANCELLED'}
            
            if c_from_item.metal_list.is_void == False:
                self.report({'WARNING'}, "The Collection " + coll_from.name + " has Metal")
                return {'CANCELLED'}

        #----------------------------------------------------------------------------------------------
        # impedimos mover una collection coll_from si tiene alguna de las siguientes propiedades:
        blacklist_props = [
            #"rbdlab_id",
            #"RBDLAB",
            #"computed_velocities",
            #"used_single_output",
            #RBDLabNaming.LAST_CREATED_COLLS,
            # "kinematic_keyframes_text"
            # "fracture_applied",
            # "disable_constraints_toggle",
            # "enable_constraints_toggle",
            "has_smoke",
            "particles_debris",
            "particles_debris_render",
            "particles_debris_viewport",
            "particles_dust",
            "particles_dust_render",
            "particles_dust_viewport",
            "particles_smoke",
            "particles_smoke_render",
            "particles_smoke_viewport",
            RBDLabNaming.COLL_WITH_PARTICLES,
            RBDLabNaming.COLL_WITH_RBD,
            RBDLabNaming.COLL_WITH_SMOKE,
            RBDLabNaming.HAS_BROKEN,
            RBDLabNaming.HAS_MOTIONS,
            RBDLabNaming.VELOCITIES,
            RBDLabNaming.BAKED_ACTION,
            RBDLabNaming.PART_COLLISION,
        ]
        # si tiene alguna de las propiedades prohibidas:
        for coll_from in all_selected_colls:
            
            if coll_from is None:
                continue

            prohibited_prop = next((prop for prop in blacklist_props if prop in coll_from), None)
            if prohibited_prop:
                self.report({'WARNING'}, "The collection " + coll_from.name + " has " + prohibited_prop)
                return {'CANCELLED'}
        #----------------------------------------------------------------------------------------------
        
        # procedemos:

        
        all_source_colls = rbdlab_const_list.get_work_group_collections

        for coll_from in all_selected_colls:

            if coll_from is None:
                continue

            self.process_highs(context, coll_from, coll_to)
            
            # procedemos con los low:
            coll_from_objects = coll_from.objects
            if coll_from_objects and coll_to:

                set_active_collection_to_master_coll(context)
            
                # lo quitamos del target list:
                item = tcoll_list.get_item_by_name(coll_from.name)

                # Si estuviera en el listado de source constraints la eliminamos:
                sc_item = rbdlab_const_list.get_source_collections_item(all_source_colls.index(coll_from))
                if sc_item:
                    sc_item.remove = True

                tcoll_list.remove_coll_list(item)
                tcoll_list.list_index = len(tcoll_list.list)-1

                for ob in coll_from_objects:

                    # lo meto en la nueva si no estuviera:
                    if ob.name not in coll_to.objects:
                        coll_to.objects.link(ob)

                    # lo quito de la collection original
                    if ob.name in coll_from.objects:
                        coll_from.objects.unlink(ob)
                    
                    # Transferimos la id de la coll al ob:
                    if RBDLabNaming.COLLECTION__COLL_ID in coll_to:
                        coll_id = coll_to[RBDLabNaming.COLLECTION__COLL_ID]
                        # le ponemos su mismo id
                        ob[RBDLabNaming.OBJECT__COLL_ID] = coll_id
                
                remove_collection_if_is_empty(context, coll_from)

        return {'FINISHED'}