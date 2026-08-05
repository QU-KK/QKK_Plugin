import bpy
from typing import Union
from datetime import datetime
from bpy.types import Operator, Object, Collection
from .....Global.functions import move_objects_to_collection, copy_modifier_by_name_from_active_to_selected, create_new_collection
from .....Global.basics import enter_edit_mode, enter_object_mode, set_active_object
from .....Global.geometry_nodes import get_gn_index_or_identifier_by
from .....addon.naming import RBDLabNaming


class BFRACTURE_OT_make_real(Operator):
    bl_idname = "rbdlab.boolean_fracture_make_real"
    bl_label = "Make Real"
    bl_description = "Boolean Fracture Make Real"
    bl_options = {'REGISTER', 'UNDO'}


    def get_org_ob_from_gn_mod_ob(self, GN_ob):
        # capturamos el objeto original desde el GN mod:
        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if GN_mod:
            group_input = GN_mod.node_group.nodes.get("Group Input")
            if group_input:
                identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Object", debug=False)
                return GN_mod[identifier]
        return None
    
    def get_coll_from_gn_mod(self, GN_ob):
        # capturamos el objeto original desde el GN mod:
        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if GN_mod:
            group_input = GN_mod.node_group.nodes.get("Group Input")
            if group_input:
                identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Collection", debug=False)
                return GN_mod[identifier]
        return None


    def apply_modifiers(self, context, ob):
        set_active_object(context, ob=ob, only_selected_ob=True)
        bpy.ops.object.convert(target='MESH')


    def separate(self, context, ob):
        # set_active_object(context, ob=ob, only_selected_ob=True)
        enter_edit_mode(context)
        bpy.ops.mesh.separate(type='LOOSE')
        enter_object_mode(context)


    def separate_planes_from_gn(self, context, GN_ob):
        self.apply_modifiers(context, GN_ob)
        self.separate(context, GN_ob)
    

    def add_boolean_mod(self, ob:Object, target_coll:Collection):
        if RBDLabNaming.BOOLEAN_MOD in ob.modifiers:
            return
        
        bool_mod = ob.modifiers.new(name=RBDLabNaming.BOOLEAN_MOD, type='BOOLEAN')
        bool_mod.solver = 'FAST'
        # bool_mod.object = plane
        bool_mod.operand_type = 'COLLECTION'
        bool_mod.collection = target_coll
        # tengo que ponerlo apagado para que se puedan aplicar los siguientes gn:
        bool_mod.show_viewport = False
        # eso ayuda a hacer mejor las fracturas:
        bool_mod.double_threshold = 0.00000001

    
    def clean_empty_materials_slots(self, context, new_planes):
        # limpiando slots de material vacios a los planos:
        bpy.ops.object.select_all(action='DESELECT')
        [ob.select_set(True) for ob in new_planes]
        set_active_object(context, new_planes[0])
        bpy.ops.object.material_slot_remove_unused()

    def same_inner_mat_for_refratures(self, new_planes, bfracture_gn_list):
        # si refracturamos para que respete el material interno, tengo que
        # asegurarme de que usan el mismo inner material:
        to_fracture_obs = bfracture_gn_list.get_objects_to_fracture
        if to_fracture_obs and new_planes:
            first_new_ob = to_fracture_obs[0]
            if RBDLabNaming.BF_INNER_MAT_NAME in first_new_ob.data.materials:
                bf_inner_mat = next((mat for mat in first_new_ob.data.materials if RBDLabNaming.SUFIX_INNER_MAT in mat.name), None)
                if bf_inner_mat:
                    for plane in new_planes:
                        plane.material_slots[0].material = bf_inner_mat


    def backups_for_back(self, context, GN_ob:Object) -> Union[Object,Collection]:
        
        # Duplicamos, y movemos los baseplanes_originales a una collection tmp, para poder hacer el "back":
        
        new_ob = GN_ob.copy()
        new_ob.data = GN_ob.data.copy()
        new_ob.animation_data_clear()

        bool_obs_coll = bpy.data.collections.get(RBDLabNaming.BOOL_OBS)
        if not bool_obs_coll:
            bool_obs_coll = create_new_collection(context, RBDLabNaming.BOOL_OBS)
        
        bool_obs_coll.objects.link(new_ob)
        move_objects_to_collection(context, [GN_ob], RBDLabNaming.BF_BASE_PLANES_COLL_TMP)

        # los dejamos neutralizados:
        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if GN_mod:
            GN_mod.show_viewport = False
            GN_mod.show_render = False
            GN_mod.show_in_editmode = False

            # eso provoca un crash:
            # [setattr(node, "mute", True) for node in GN_mod.node_group.nodes]
            # group_input = GN_mod.node_group.nodes.get("Group Input")
            # if group_input:
            #     identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Collection", debug=False)
            #     GN_mod[identifier] = None
        
        GN_ob.hide_set(True)
        GN_ob.hide_viewport = True
        GN_ob.hide_render = True

        return [new_ob, bool_obs_coll]


    def execute(self, context):

        # Continue or Make Real

        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        
        ui = rbdlab.ui
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        all_new_planes = []

        ui.boolean_method_phase = 'SETTINGS_BOOL_MOD'
        
        all_base_planes = bfracture_gn_list.get_all_base_planes
        all_ob_with_booleans = set()

        # para restaurar como estuviera el index:
        previous_index = bfracture_gn_list.list_index

        for i, GN_ob in enumerate(all_base_planes):

            # GN_obs = [ob for ob in bpy.data.objects if ob.name.startswith(RBDLabNaming.BOOLFRACTURE_GN_OB)]
            if not GN_ob:
                continue

            # tengo que ir cambiando el item activo para ir guardando sus planos en el.
            bfracture_gn_list.list_index = i

            # hacemos los backups para poder hacer el boton de back:
            GN_ob, bool_obs_coll = self.backups_for_back(context, GN_ob)
            
            bpy.ops.object.select_all(action='DESELECT')
            new_planes = []

            # Nos aseguramos de que se este viendo en modo planes:
            set_active_object(context, ob=GN_ob, only_selected_ob=True)
            GN_ob.select_set(True)

            GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
            group_input = GN_mod.node_group.nodes.get("Group Input")
            if group_input:
                identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Switch Planes/Points", debug=False)
                GN_mod[identifier] = True


            coll = self.get_coll_from_gn_mod(GN_ob)
            if not coll:
                continue

            # separamos los planos del GN:
            self.separate_planes_from_gn(context, GN_ob)

            # print(len(context.selected_objects), context.selected_objects)
            [new_planes.append(ob) for ob in context.selected_objects]
            [all_new_planes.append(ob) for ob in context.selected_objects]
            
            # muevo los bool planos a BF_Bool_Objects 
            # (si tengo la linea) GN_ob, bool_obs_coll = self.backups_for_back(context, GN_ob) puedo comentar esta linea:
            # bool_obs_coll = move_objects_to_collection(context, context.selected_objects, RBDLabNaming.BOOL_OBS, with_print=False)

            # por cada objeto original de la collection les agrego el boolean:
            for org_ob in coll.objects:
                self.add_boolean_mod(org_ob, bool_obs_coll)
                all_ob_with_booleans.add(org_ob)

            rbdlab.scatter.scatter_bfracture_method = 'FAST'

            self.clean_empty_materials_slots(context, new_planes)
            self.same_inner_mat_for_refratures(new_planes, bfracture_gn_list)

            # seleccionado los objetos:
            # bpy.ops.object.select_all(action='DESELECT')
            # [ob.select_set(True) for ob in to_fracture_obs]

            # los seteamos como wireframe:
            # [setattr(ob, "display_type", 'WIRE')  for ob in to_fracture_obs]

            # guardamos los planos:
            # primero lo vaciamos de planos previamente guardados (recordemos q ahora se puede hacer back y podría tener planos que ya no existen):
            
            bfracture_gn_list.clear_bool_planes
            bfracture_gn_list.store_bool_planes(bool_planes=list(set(new_planes)))
        
        # Restauramos como estuviera el index:
        bfracture_gn_list.list_index = previous_index 
        
        # les ponemos el triangulate y el solidify a los planos:
        if all_new_planes:

            first_plane = all_new_planes[0]
            bpy.ops.object.select_all(action='DESELECT')
            set_active_object(context, first_plane)
            first_plane.select_set(True)

            # agrego un triangulate (el triangulate ayuda a que no fallen las booleans):
            triangulate_target = RBDLabNaming.TRIANGULATE
            triangulate_mod = first_plane.modifiers.new(name=triangulate_target, type='TRIANGULATE')
            
            # agrego un solidify:
            solidify_target = RBDLabNaming.SOLIDIFY_MOD
            solidify_mod = first_plane.modifiers.new(name=solidify_target, type='SOLIDIFY')
            solidify_mod.thickness = 0.001
            solidify_mod.use_even_offset = True

            # se lo copioamos al resto:
            [plane.select_set(True) for plane in all_new_planes if plane != first_plane]
            copy_modifier_by_name_from_active_to_selected(context, [solidify_target, triangulate_target])

            # ocultamos los planos:
            [ob.hide_set(True) for ob in all_new_planes]

        # volvemos a hacer visibles las boleanas, las tuvimos que desactivar para poder seguir aplicando los GN
        if all_ob_with_booleans:
            for ob in all_ob_with_booleans:
                bool_mod = ob.modifiers.get(RBDLabNaming.BOOLEAN_MOD)
                if bool_mod:
                   bool_mod.show_viewport = True
      
        context.space_data.shading.type = 'WIREFRAME'

        ui.bf_gn_compute_neighbors = ui.get_default_properties("bf_gn_compute_neighbors")
        ui.bf_gn_use_auto_uv_cube_projection = ui.get_default_properties("bf_gn_use_auto_uv_cube_projection")

        print("[boolean_fracture.make_real] End: " + str(datetime.now() - start))
        return {'FINISHED'}