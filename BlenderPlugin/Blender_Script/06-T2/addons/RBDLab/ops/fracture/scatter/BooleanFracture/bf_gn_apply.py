import bpy
import random
from typing import List
from collections import defaultdict
from datetime import datetime
from bpy.types import Operator, Object
from ....constraints.detect import calcute_chunks_neighbors
from .....Global.geometry_nodes import get_gn_index_or_identifier_by
from .....Global.basics import enter_edit_mode, enter_object_mode, set_active_object
from .....Global.functions import rm_ob, remove_collection, store_inner_faces_in_attribute, set_shading_color
from .....addon.naming import RBDLabNaming
from .....addon.paths import RBDLabPreferences


class BFRACTURE_OT_apply(Operator):
    bl_idname = "rbdlab.boolean_fracture_apply"
    bl_label = "Apply Boolean Fracture"
    bl_description = "Apply Boolean Fracture"
    bl_options = {'REGISTER', 'UNDO'}

    all_objects = set()


    def get_org_ob_from_gn_mod(self, GN_ob):
        # capturamos el objeto original desde el GN mod:
        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if GN_mod:
            group_input = GN_mod.node_group.nodes.get("Group Input")
            if group_input:
                identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Object", debug=False)
                return GN_mod[identifier]
        return None
    

    def separate_planes_from_gn(self, context, GN_ob):
        solidify_mod = GN_ob.modifiers.new(name=RBDLabNaming.SOLIDIFY_MOD, type='SOLIDIFY')
        solidify_mod.thickness = 0.001
        self.apply_modifiers(context, GN_ob)
        self.separate(context, GN_ob)


    def add_boolean_mod(self, ob, plane):
        bool_mod = ob.modifiers.new(name=RBDLabNaming.BOOLEAN_MOD, type='BOOLEAN')
        bool_mod.solver = 'FAST'
        bool_mod.object = plane


    def apply_modifiers(self, context, ob):
        set_active_object(context, ob=ob, only_selected_ob=True)
        bpy.ops.object.convert(target='MESH')


    def separate(self, context):
        enter_edit_mode(context)
        bpy.ops.mesh.separate(type='LOOSE')
        enter_object_mode(context)
        # guardamos los trozos separados:
        self.all_objects.update(context.selected_objects)
    

    def uv_cube_projection(self, context, bfracture_gn_list):
        
        # a las caras internas les ponemos uvs de cube projection

        all_bool_planes = bfracture_gn_list.get_all_bool_planes
        
        bpy.ops.object.select_all(action='DESELECT')

        for ob in all_bool_planes:

            if not ob:
                continue
                        
            # si el usuario borra un plano manualmente ya no estará:
            if ob.name not in context.view_layer.objects:
                continue

            ob.hide_set(False)
            ob.select_set(True)

        # active_obj = all_bool_planes[0]
        active_obj = next((ob for ob in all_bool_planes if ob and ob.name in context.view_layer.objects), None)
        set_active_object(context, active_obj)

        # store previous mode:
        current_mode = active_obj.mode
        enter_edit_mode(context)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.cube_project(cube_size=1.0, correct_aspect=True, clip_to_bounds=True, scale_to_bounds=True)

        # restore previous mode:
        bpy.ops.object.mode_set(mode=current_mode)

        for ob in all_bool_planes:
            
            if not ob:
                continue
            
            if ob.name not in context.view_layer.objects:
                continue

            ob.hide_set(True)

        bpy.ops.object.select_all(action='DESELECT')
    

    def randColor(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)
        rand_color_between_from = addon_preferences.rand_color_between_from
        rand_color_between_to = addon_preferences.rand_color_between_to
        rand_color = [
            random.uniform(
                rand_color_between_from,
                rand_color_between_to),
            random.uniform(
                rand_color_between_from,
                rand_color_between_to),
            random.uniform(
                rand_color_between_from,
                rand_color_between_to
            ), 1.0]
        return rand_color


    def add_color_per_chunks_froms(self, context, chunks):
        
        set_shading_color(context, color_type='OBJECT')
        ob_by_from: dict[str, List[Object]] = defaultdict(list)

        for ob in chunks:
            from_name = ob.get(RBDLabNaming.FROM)
            if from_name:
                ob_by_from[from_name].append(ob)
        
        for chunks in ob_by_from.values():
            # por cada from creo un color random:
            rand_color = self.randColor(context)
            
            # y se los aplicamos a sus chunks:
            for ob in chunks:
                
                # si ya tiene seteado color no se lo vuelvo a setear:
                if ob.color_stack.get_all_colors() is not None:
                    continue

                ob.color_stack.add_color(rand_color)
                ob.color = rand_color


    def limpieza_de_chunks(self, chunks:List[Object]) -> List[Object]:
        # limpieza de chunks:
        obs_to_rm = [ob for ob in chunks if len(ob.data.vertices) <= 3]
        # eliminamos los chunks de menos o igual a 3 vertices:
        [rm_ob(ob) for ob in obs_to_rm]
        
        # los quitamos del listado de chunks los chunks eliminados:
        [chunks.remove(ob) for ob in chunks if ob in obs_to_rm]
        # se puede ver si hacer una limpieza a nivel edit con:
        # bpy.ops.mesh.delete_loose()

        return chunks


    def execute(self, context):
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list

        if ui.bf_gn_use_auto_uv_cube_projection:
            self.uv_cube_projection(context, bfracture_gn_list)

        all_items = bfracture_gn_list.get_all_items
        all_from_coll = set() # aquí están guardadas las tcoll creadas

        for item in all_items:
            
            to_fracture_obs = [otf.ob for otf in item.stored_objects_to_fracture]

            if not to_fracture_obs:
                continue

            all_from_coll.add(item.from_coll)

            bpy.ops.object.select_all(action='DESELECT')
            
            # los seleccionamos y convertimos en mesh:
            [ob.select_set(True) for ob in to_fracture_obs]
            set_active_object(context, to_fracture_obs[0])
            bpy.ops.object.convert(target='MESH')
            self.separate(context)
            chunks = context.selected_objects

            # guardando el attributo de material:
            [store_inner_faces_in_attribute(ob) for ob in chunks]

            # les pongo el random color:
            self.add_color_per_chunks_froms(context, chunks)

            # limpieza:
            chunks = self.limpieza_de_chunks(chunks)

            # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
            # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='BOUNDS')
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='BOUNDS')

            # borramos sus planos:
            all_planes = [bop.ob for bop in item.stored_bool_planes]
            
            if not all_planes:
                continue
            
            for plane in all_planes:
                rm_ob(plane)

        # eliminamos los items del listado:
        all_items_ids = bfracture_gn_list.get_all_items_ids
        [bpy.ops.rbdlab.boolean_fracture_rm(id_to_rm=item_id) for item_id in all_items_ids]   
        
        # eliminamos el nodegroup:
        node_group = bpy.data.node_groups.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if node_group:
            bpy.data.node_groups.remove(node_group, do_unlink=True)

        # eliminamos la collection de planos:
        bool_obs_coll = bpy.data.collections.get(RBDLabNaming.BOOL_OBS)
        if bool_obs_coll:    
            remove_collection(context, bool_obs_coll)
        
        # eliminamos la collection temporal de backups para el back:
        base_planes_coll_tmp = bpy.data.collections.get(RBDLabNaming.BF_BASE_PLANES_COLL_TMP)
        if base_planes_coll_tmp: 
            remove_collection(context, base_planes_coll_tmp)
        
        # Computando vecinos:
        if ui.bf_gn_compute_neighbors:
            # Calculando vecinos:
            # Con VERT_KDTREE tardaba mucho al tener muchas subdivisiones, con BBOX va más rápido:
            # calcute_chunks_neighbors(context, self.all_objects, search_method='BBOX')
            calcute_chunks_neighbors(
                                        context, 
                                        list(self.all_objects), 
                                        # search_method='CYTHON',
                                        search_method='BBOX',
                                    )

        # las marcamos como que fuero aplicadas las fracturas:
        for from_coll in all_from_coll:
            from_coll["fracture_applied"] = 1
            # Marcamos como que se computaron los vecinos:
            from_coll[RBDLabNaming.COMPUTED_NEIGHBORS] = True

        ui.boolean_method_phase = 'NONE'
        context.space_data.shading.type = 'SOLID'

        bpy.ops.object.select_all(action='DESELECT')
        print("[boolean_fracture.apply] End: " + str(datetime.now() - start))
        return {'FINISHED'}
