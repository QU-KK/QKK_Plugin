import bpy
import random
from typing import List
from operator import setitem
from addon_utils import check
from datetime import datetime
from collections import defaultdict
from ...addon.naming import RBDLabNaming
from ...addon.paths import RBDLabPreferences
from bpy.types import Operator, Context, Object, Collection
from ...Global.functions import (
    add_material,
    set_active_collection_to_master_coll,
    remove_special_chars_in_name,
    set_shading_color,
    move_objects_to_collection,
    store_inner_faces_in_attribute,
    create_originals_coll_if_not_exist,
    #  remove_collection_if_is_empty,
)
from ...Global.basics import enter_edit_mode, select_object, set_active_object, deselect_all_objects, rm_ob
# from ..constraints.detect import calcute_chunks_neighbors


# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD
boolean_mod_name_up = RBDLabNaming.BOOLEAN_MOD_UP


class CELL_FRACTURE_OT_custom(Operator):
    bl_idname = "rbdlab.cellfracture"
    bl_label = "RBDLab Cell Fracture GUI"
    bl_description = "Fracture objects with Cell Fracture"
    bl_options = {'REGISTER', 'UNDO'}

    chunks_created = []

    # optimizacion unlink
    multiple_fractures = None
    new_collection_and_obj_hidden = {}

    def clean_void_chunks(self, context, collection: Collection) -> None:
        depsgraph = context.evaluated_depsgraph_get()
        for obj in collection.objects:
            if obj.type != 'MESH':
                continue
            obj_eval = obj.evaluated_get(depsgraph)

            if len(obj_eval.data.vertices) <= 3:
                print("Remove void chunk:", obj.name)
                if obj in self.chunks_created:
                    self.chunks_created.remove(obj)
                rm_ob(obj)

    def remove_rbdlab_properties(self, obj: object) -> None:
        # Eliminamos todas las custom properties que empiecen por rbdlab:
        custom_properties = list(obj.keys())
        for cp in custom_properties:
            cpl = cp.lower()
            if cpl.startswith("rbdlab"):
                if cpl in obj:
                    del obj[cpl]

    def remove_rbdlab_materials(self, context:Context, ob: object) -> None:

        # Verifica si el objeto es None antes de pasarle a set_active_object()
        if ob is not None:

            # guardamos la seleccion previa:
            previous_selection = context.selected_objects

            # prevengo materiales anteriores y borro materiales residuales al original:
            # necesito que este tambien seleccionado para que no pete material_slot_remove()
            only_selected_ob = True
            set_active_object(context, ob, only_selected_ob)

            for i, mat_slot in enumerate(ob.material_slots):
                # if mat.name.endswith("Outer_mat") or mat.name.endswith("Inner_mat") or not mat.name:
                if mat_slot.name.endswith(RBDLabNaming.SUFIX_INNER_MAT) or mat_slot.name == "" or RBDLabNaming.INNER_MAT_TAG in mat_slot.material:
                    ob.active_material_index = i
                    bpy.ops.object.material_slot_remove()

            set_active_object(context, ob)
            bpy.ops.object.material_slot_remove_unused()

            # restore previous selection:
            [ob.select_set(True) for ob in previous_selection]

        else:
            print(ob, " Object is None!")
            return

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
    
    def add_color_per_chunks_froms(self, context, target_collections):

        ob_by_from: dict[str, List[Object]] = defaultdict(list)
        
        all_chunks = set([ob for target_coll in target_collections for ob in target_coll.objects])
        
        for ob in all_chunks:
            from_name = ob.get(RBDLabNaming.FROM)
            if from_name:
                ob_by_from[from_name].append(ob)
        
        for chunks in ob_by_from.values():
            # por cada from creo un color random:
            rand_color = self.randColor(context)
            
            # y se los aplicamos a sus chunks:
            for ob in chunks:
                ob.color_stack.add_color(rand_color)
                ob.color = rand_color



    def setup_boolean_modifier(self, context, rbdlab, ob):
        # obj.modifiers["Boolean"].solver = 'FAST'
        if "Boolean" in ob.modifiers:
            ob.modifiers["Boolean"].solver = rbdlab.rbdlab_cf_fast_exact
            # guardo a donde apuntaba el boolean:
            # obj["rbdlab_boolean"] = obj.modifiers["Boolean"].object.name
            # obj[RBDLabNaming.FROM] = obj.modifiers["Boolean"].object.name
            ob.modifiers["Boolean"].name = boolean_mod_name

    def create_vertex_groups(self, context) -> None:
        if len(context.selected_objects) > 0:
            for obj in context.selected_objects:
                vertex_selected = [i.index for i in obj.data.vertices if i.select]
                v_group_name = "Interior"
                if len(vertex_selected):
                    vg = obj.vertex_groups.get(v_group_name)
                    if vg is None:
                        vg = obj.vertex_groups.new(name=v_group_name)
                    vg.add(vertex_selected, 1.0, 'ADD')
        else:
            print("[Create Vertex Group]: Not selected objects found!")

    def cell_fracture(self, context, ob, coll_name):
        # capturo el objeto original:
        org_ob = ob

        rbdlab = context.scene.rbdlab
        set_active_collection_to_master_coll(context)

        # deselect_all_objects(context)
        # select_object(context, obj)
        # set_active_object(context, obj)

        if 'PARTICLE_OWN' in rbdlab.rbdlab_cf_source and len(ob.particle_systems) == 0:
            bpy.ops.rbdlab.scatter_add()

        # Cell Fracture Options:
        # source = {'PARTICLE_OWN'},
        # source_limit = 100,
        # source_noise = 0,
        # cell_scale = (1, 1, 1),
        # recursion = 0,
        # recursion_source_limit = 8,
        # recursion_clamp = 250,
        # recursion_chance = 0.25,
        # recursion_chance_select = 'SIZE_MIN',
        # use_smooth_faces = False,
        # use_sharp_edges = True,
        # use_sharp_edges_apply = True,
        # use_data_match = True,
        # use_island_split = True,
        # margin = 0.001,
        # material_index = 0,
        # use_interior_vgroup = False,
        # mass_mode = 'VOLUME',
        # mass = 1,
        # use_recenter = True,
        # use_remove_original = True,
        # coll_name = "",
        # use_debug_points = False,
        # use_debug_redraw = True,
        # use_debug_bool = False
        source = rbdlab.rbdlab_cf_source
        source_limit = rbdlab.rbdlab_cf_source_limit
        noise = float("%f" % rbdlab.rbdlab_cf_noise)
        scale = rbdlab.rbdlab_cf_cell_scale
        recursion = rbdlab.rbdlab_cf_recursion
        recursion_source_limit = rbdlab.rbdlab_cf_recursion_source_limit
        recursion_clamp = rbdlab.rbdlab_cf_recursion_clamp
        recursion_chance = float("%f" % rbdlab.rbdlab_cf_recursion_chance)
        recursion_chance_select = rbdlab.rbdlab_cf_recursion_chance_select
        # use_sharp_edges_apply = rbdlab.rbdlab_cf_use_sharp_edges_apply
        # use_sharp_edges_apply = True  # parece que con objetos con shade smooth queda mejor asi que lo activo por defecto

        margin = float("%f" % rbdlab.rbdlab_cf_margin)

        bpy.ops.rbdlab.add_fracture_cell_objects(
            source=source,
            source_limit=source_limit,
            source_noise=noise,
            cell_scale=scale,
            recursion=recursion,
            recursion_source_limit=recursion_source_limit,
            recursion_clamp=recursion_clamp,
            recursion_chance=recursion_chance,
            recursion_chance_select=recursion_chance_select,
            # use_sharp_edges_apply=use_sharp_edges_apply,
            margin=margin,
            material_index=len(ob.material_slots)-1,
            # use_interior_vgroup=1, # al usar debug no hace el split ni los grupos
            # use_debug_bool=inner_detail,
            use_debug_redraw=False,
            use_debug_bool=True,
            collection_name=coll_name
        )

        # self.chunks_created.extend(context.selected_objects)

        for ob in context.selected_objects:

            # me aseguro de que el inner material contenga el suffix
            last_mat = ob.material_slots[-1]
    
            if RBDLabNaming.SUFIX_INNER_MAT not in last_mat.name: 
                # cropeo a 63 que es el maximo de chars y agrego el suffix:
                inner_mat_name = last_mat.name[:63-len(RBDLabNaming.SUFIX_INNER_MAT)] + RBDLabNaming.SUFIX_INNER_MAT
                last_mat.material.name = inner_mat_name

            if ob not in self.chunks_created and len(ob.data.vertices) > 3:
                self.chunks_created.append(ob)
            
            ob[RBDLabNaming.FROM] = org_ob.name

            # para no usar los facemaps ya que serán eliminados de blender:

            # guardo en otro attributo el attributo Inner_faces:
            store_inner_faces_in_attribute(ob)

        # print("post fracture: borrando/ocultando orignal...")
        if rbdlab.post_original == 'HIDE':
            org_ob.hide_set(True)
            org_ob.hide_render = True
        else:
            rm_ob(org_ob)
            rbdlab.post_original = 'HIDE'

        # optimizacion unlink
        new_collection = bpy.data.collections[coll_name]
        if self.multiple_fractures:
            if coll_name not in self.new_collection_and_obj_hidden:
                self.new_collection_and_obj_hidden[coll_name] = context.selected_objects
            else:
                self.new_collection_and_obj_hidden[coll_name].extend(context.selected_objects)

            unlink_obj = new_collection.objects.unlink
            {unlink_obj(obj) for obj in context.selected_objects}

        deselect_all_objects(context)

    def uv_cube_projection(self, context):
        # deselect_all_objects(context)
        # print(self.chunks_created)

        for obj in self.chunks_created:
            select_object(context, obj)

        if context.selected_objects:
            active_obj = context.selected_objects[0]
            set_active_object(context, active_obj)
            # store previous mode:
            current_mode = active_obj.mode
            enter_edit_mode(context)
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.cube_project(cube_size=1.0, correct_aspect=True,
                                    clip_to_bounds=True, scale_to_bounds=True)

            # restore previous mode:
            bpy.ops.object.mode_set(mode=current_mode)
        else:
            print("[UV Cube Projection]: Not selected Objects!")

        deselect_all_objects(context)

    def add_attribute(self, item_target, attribute_name: str, attribute_value: bool) -> None:
        item_target[attribute_name] = attribute_value

    def add_inner_material(context, self, obj, mat_inner_name, darkgrey):
        # print("Adding Inner material to: " + obj.name)
        # solo agrego inner material si no tiene ya uno:
        inner_mats = [mat for mat in obj.material_slots if RBDLabNaming.INNER_MAT_TAG in mat.material]
        if len(inner_mats) == 0:

            # si vienen de edge fracture:
            if RBDLabNaming.FROM in obj and RBDLabNaming.FROM_EDGE_FRACTURE in obj:
                if obj[RBDLabNaming.FROM] in bpy.data.objects:
                    # obj_from = bpy.data.objects[obj[RBDLabNaming.FROM]]
                    mat_inner_name = obj[RBDLabNaming.FROM] + RBDLabNaming.SUFIX_INNER_MAT

            add_material(context, obj, mat_inner_name, darkgrey)

    def execute(self, context):
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        tcoll_list = rbdlab.lists.target_coll_list

        self.chunks_created = []
        self.new_collection_and_obj_hidden = {}

        # el maximo de caracteres permitidos por nombre es 63 chars:
        coll_name = rbdlab.rbdlab_cf_collection_name[:63]

        if len(context.selected_objects) < 1:
            self.report({'WARNING'}, "No Selected Objects!")
            return {'CANCELLED'}

        # Filtramos y cogemos los valid objects
        valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not valid_objects:
            self.report({'WARNING'}, "No Selected MESH Objects!")
            return {'CANCELLED'}

        if rbdlab.use_single_collection_name:

            if not coll_name:
                self.report({'WARNING'}, "Single Output Collection Name is mandatory!")
                return {'CANCELLED'}

        addon_preferences = RBDLabPreferences.get_prefs(context)
        set_shading_color(context, color_type='OBJECT')

        original_selection = context.selected_objects
        # original_active = context.active_object

        childrens = []
        helpers = None
        edge_fracture = None
        previous_collection = []

        white = [0.8, 0.8, 0.8, 1.0]
        darkgrey = [0.250, 0.250, 0.250, 1.0]
        delimiters = []

        # para los edge fracture:
        if rbdlab.filtered_target_collection:

            use_edge_fractures = False
            tags_with_edge_fractures = ["edge_extracted_all_accepted",
                                        "edge_extracted_inners_accepted", "edge_extracted_innerfaces"]

            for tag in tags_with_edge_fractures:
                if tag in rbdlab.filtered_target_collection:
                    use_edge_fractures = True

            # si son chunks que vienen de los metodos de edge fracture
            if use_edge_fractures:
                for obj in valid_objects:

                    self.remove_rbdlab_materials(context, obj)

                    # guardo sus collections previas para despues si se quedan vacias borrarlas
                    if obj.users_collection is not None:
                        for coll in obj.users_collection:
                            if coll not in previous_collection:
                                previous_collection.append(coll)

                    for child in obj.children:
                        childrens.append(child)

                if childrens:
                    helpers = [obj for obj in childrens if "rbdlab_fracture_helper_simple" in obj]
                    if helpers:
                        edge_fracture = True

                # print("previous_collection", previous_collection)

                # limpieza estados edge methods:
                if "edge_extracted_all" in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection["edge_extracted_all"]
                    edge_fracture = True

                if "edge_extracted_all_accepted" in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection["edge_extracted_all_accepted"]
                    edge_fracture = True

                if "edge_extracted_inners" in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection["edge_extracted_inners"]
                    edge_fracture = True

                if "edge_extracted_inners_accepted" in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection["edge_extracted_inners_accepted"]
                    edge_fracture = True

                if "edge_extracted_innerfaces" in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection["edge_extracted_innerfaces"]
                    edge_fracture = True
                # end limpieza estados edge methods.

        # aplico la escala a los objetos
        # [bpy.ops.object.transform_apply(location=False, rotation=False, scale=True) for obj in valid_objects]

        first_processed_object = False
        output_collection = None
        i = 0

        self.multiple_fractures = bool(len(valid_objects) > 1)
        if self.multiple_fractures:
            self.hidden_objects = []

        for obj in valid_objects:

            if not obj.visible_get():
                obj.hide_set(False)
                obj.hide_render = False

            deselect_all_objects(context)
            select_object(context, obj)
            set_active_object(context, obj)

            obj.name = remove_special_chars_in_name(obj.name)
            mat_outher_name = obj.name + RBDLabNaming.SUFIX_OUTER_MAT
            mat_inner_name = obj.name + RBDLabNaming.SUFIX_INNER_MAT

            self.remove_rbdlab_materials(context, obj)

            total_materials = len(obj.material_slots)
            if total_materials == 0:
                if mat_outher_name not in obj.material_slots:
                    add_material(context, obj.name, mat_outher_name, white)
                    self.add_inner_material(context, obj, mat_inner_name, darkgrey)
            if total_materials >= 1:
                if mat_inner_name not in obj.material_slots:
                    self.add_inner_material(context, obj, mat_inner_name, darkgrey)

            self.remove_rbdlab_properties(obj)

            # forzando actualizar el depsgraph:
            # context.scene.frame_set(context.scene.frame_current+1)
            # context.scene.frame_set(context.scene.frame_current-1)

            if not rbdlab.use_single_collection_name:
                coll_name = obj.name + RBDLabNaming.SUFIX_LOW
                # el maximo de caracteres permitidos por nombre es 63 chars:
                coll_name = coll_name[:63]

            # esto no debería suceder porque ya agrego
            if 'PARTICLE_OWN' in rbdlab.rbdlab_cf_source and len(obj.particle_systems) == 0:
                bpy.ops.rbdlab.scatter_add()

            # print("* COLLECTION NAME: ", coll_name)

            if coll_name:
                ##################### CELL FRACTURE FUNCTION #####################
                set_active_collection_to_master_coll(context)

                # originals to Original collection
                if addon_preferences.move_originals:
                    # si no esta seteada la coll originals entonces la creo y la seteo:
                    originals_coll = create_originals_coll_if_not_exist(context, rbdlab)
                    # una vez existe la coll originals podemos mover el objeto a esa coll:
                    move_objects_to_collection(context, [obj], originals_coll.name)

                # guardo antes de crear nada que colecciones hay ya disponibles en RBDLab
                # para posteriormente comparar y saber cuales son las nuevas
                if not first_processed_object:
                    previous_collections = list(rbdlab.root_collection.children)
                    # print("previous_collections", previous_collections)
                    first_processed_object = True

                self.cell_fracture(context, obj, coll_name)

                output_collection = bpy.data.collections[coll_name]

                i += 1

                if i == len(valid_objects):
                    after_collections = list(rbdlab.root_collection.children)
                    # print("after_collections", after_collections)
                ##################################################################

                # agregamos la collection nueva por cada objeto al target colllections list:
                all_collections_in_list = tcoll_list.get_all_target_collections
                if output_collection not in all_collections_in_list:
                    tcoll_list.add_tcoll(output_collection)

            delimiters.append(len(output_collection.objects))

        # optimizacion unlink
        if self.multiple_fractures:
            for coll_name, hidden_objects in self.new_collection_and_obj_hidden.items():
                coll = bpy.data.collections[coll_name]
                link_obj = coll.objects.link
                {link_obj(obj) for obj in hidden_objects}

        # set tag inner material, for use materials, independent name mat:
        # store inner material custom property:
        # for obj in self.chunks_created:
        #     for mat_slot in obj.material_slots:
        #         if RBDLabNaming.SUFIX_INNER_MAT in mat_slot.name:
        #             mat_slot.material[RBDLabNaming.INNER_MAT_TAG] = True
        inner_materials = [
            [mat_slot.material for mat_slot in obj.material_slots if RBDLabNaming.SUFIX_INNER_MAT in mat_slot.name]
            for obj in self.chunks_created if obj.name in bpy.data.objects
        ]
        if inner_materials:  # fix list out of range
            inner_materials = inner_materials[0]
            {self.add_attribute(mat, RBDLabNaming.INNER_MAT_TAG, True) for mat in inner_materials}

        # agregamos el Target collection:
        rbdlab.filtered_target_collection = output_collection

        rbdlab.filtered_target_collection["fracture_applied"] = 0
        # Debe visualizarse en LOW cuando hacemos el fracture.
        rbdlab.low_or_high_visibility_viewport = "Low"

        # Clear a los originales de particle systems, materiales, etc:
        blacklist_particles_names = [
            RBDLabNaming.SECOND_SCATTER,
            "Detail_Scatter",
            "Scatter_by_Texture",
            "scatter_organic"
        ]

        # for obj in valid_objects:

        # restore viewport display
        # obj.display_type = 'TEXTURED'

        # clear residual materials
        # self.remove_rbdlab_materials(context, obj)

        {(
            setattr(obj, "display_type", 'TEXTURED'),
            self.remove_rbdlab_materials(context, obj)
        ) for obj in valid_objects}

        # clear particles systems:
        for obj in valid_objects:
            for mod in obj.modifiers:
                bad_mods = [mod for bln in blacklist_particles_names if mod.name.startswith(bln)]
                if bad_mods:
                    obj.modifiers.remove(mod)

        # imprimo si hay nuevas colecciones creadas
        # y guardo las ultimas nuevas colecciones creadas
        new_created_collections = [new_coll for new_coll in after_collections if new_coll not in previous_collections]

        # Marcar collection como creada con RBDLab.
        {setitem(coll, 'RBDLAB', 1) for coll in new_created_collections}

        for coll in new_created_collections:
            coll[RBDLabNaming.LAST_CREATED_COLLS] = new_created_collections

        # si se usa single output puede que no existan nuevas collections:
        if not new_created_collections:
            # entonces la ultima collection se guarda como last created para que el resto funcione bien
            if output_collection:
                rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS] = [output_collection]

        # padding = len(str(len(bpy.data.collections[coll_name].objects))) + 1

        # start = datetime.now()

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            from uuid import uuid4


            self.add_color_per_chunks_froms(context, target_collections)

            # {ob_by_from[key] for key in ob_by_from}

            for target_coll in target_collections:
                coll_name = target_coll.name

                target_collection = bpy.data.collections[coll_name]

                collection_id = uuid4().hex
                target_collection[RBDLabNaming.COLLECTION__COLL_ID] = collection_id

                # print("coll_name", coll_name)
                for ob in target_collection.objects:

                    if ob.type != 'MESH' and not ob.visible_get():
                        continue

                    ob[RBDLabNaming.OBJECT__COLL_ID] = collection_id

                    # select_object(context, obj)
                    self.setup_boolean_modifier(context, rbdlab, ob)
                    # para luego hacer el split
                    set_active_object(context, ob)
                    ob.active_material_index = 1

                if rbdlab.use_single_collection_name:
                    target_collection["used_single_output"] = True
                else:
                    target_collection["used_single_output"] = False

                self.clean_void_chunks(context, target_collection)

        # creando split por material (solo lo esta aplicando sin inner...):
        # self.create_vertex_groups(context)

        # print(str(datetime.now() - start))
        if addon_preferences.clear_single_output_collection_name_after_fracture:
            rbdlab.rbdlab_cf_collection_name = ""
            rbdlab.use_single_collection_name = False

        # eliminamos todas las posibles icospheres
        for obj in original_selection:
            objs = bpy.data.objects
            [objs.remove(ob, do_unlink=True) for ob in context.scene.objects if ob.parent == obj]

        rbdlab.ui.show_mesh_visualization_settings = False
        rbdlab.scatter_working = False
        rbdlab.current_using_cell_fracture = True

        # bpy.ops.rbdlab.rm_void_chunks()
        deselect_all_objects(context)

        if rbdlab.filtered_target_collection:
            if "starting_fracture" not in rbdlab.filtered_target_collection:
                rbdlab.filtered_target_collection["starting_fracture"] = True

        if helpers:
            rbdlab.filtered_target_collection["rbdlab_fracture_helper_simple"] = True

        if edge_fracture:
            # Por cada collection de los edge fractures
            # limpiamos el listado de target collections:
            for coll in previous_collection:
                id_name = tcoll_list.get_id_name_from_coll_name(coll.name)
                tcoll_item = tcoll_list.get_item_by_id_name(id_name)
                tcoll_item.remove = True

        if rbdlab.ui.use_auto_uv_cube_projection:
            self.uv_cube_projection(context)

        # auto load collections for constraints:
        # bpy.ops.rbdlab.const_init_work_group() # este lo estoy haciendo ahora en el add_coll
        bpy.ops.rbdlab.materials_init_collections()

        # en el Constraints Source Collection, seteamos solo selected la ultima creada:
        if len(rbdlab.constraints.list) > 0:
            for sc in rbdlab.constraints.list:
                sc.selected = False
            rbdlab.constraints.list[len(rbdlab.constraints.list)-1].selected = True

        self.chunks_created = []
        self.new_collection_and_obj_hidden = {}

        rbdlab.thumbnails.by_selection = 'COLLECTION'

        ui.compute_neighbors = ui.get_default_properties("compute_neighbors")

        # start = datetime.now()
        # calcute_chunks_neighbors(context, list(target_collection.objects))
        # print("[RBDLab NeighbourChunksDetection]: " + str(datetime.now() - start))
        rbdlab.ui.fracture_switch_subsections = 'FRACTURE_DETAILS'

        print("[RBDLab CellFracture]: " + str(datetime.now() - start))
        return {'FINISHED'}
