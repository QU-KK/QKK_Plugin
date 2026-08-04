import bpy
import random
from uuid import uuid4
from typing import List
from os.path import join
from datetime import datetime
from bpy.types import Operator, Object
from .....addon.paths import RBDLabPaths
from .....addon.naming import RBDLabNaming
from bpy.props import BoolProperty, StringProperty
from .....Global.basics import rm_ob, set_active_object
from .....Global.geometry_nodes import set_exposed_attributes_of_gn
from .....Global.functions import set_active_collection_to_master_coll, move_objects_to_collection, create_new_collection, remove_collection, add_material, create_originals_coll_if_not_exist
from .boolfracture_name_increment import name_increment


class BFRACTURE_OT_add(Operator):
    bl_idname = "rbdlab.boolean_fracture_add"
    bl_label = "Boolean Fracture"
    bl_description = "Boolean Fracture"
    bl_options = {'REGISTER', 'UNDO'}

    single_output: BoolProperty(default=False, name="Single Output", description="Use a single collection or each collections")
    single_output_name: StringProperty(default="", name="Name", description="Collection Name")


    def single_output_or_not(self, context, tcoll_list, original_selection) -> None:

        tcoll = None

        if self.single_output:

            # Si se dejo el nombre en blanco cancelamos:
            if not self.single_output_name:
                self.report({'ERROR'}, "Invalid Single Output name!")
                return {'CANCELLED'}
            
            coll_name = self.single_output_name
            tcoll = create_new_collection(context, coll_name)
            # la agregamos a Target Collections:
            tcoll_list.add_tcoll(tcoll)
        
        else:

            for ob in original_selection:
                coll_name = ob.name
                tcoll = create_new_collection(context, coll_name)

                # la agregamos a Target Collections:
                tcoll_list.add_tcoll(tcoll)
        
        return tcoll


    def remove_void_material_slots(self, context, objects_list:List[Object]) ->None:
        
        # eliminamos si hay slots vacios primero:

        for ob in objects_list:
            set_active_object(context, ob)

            # veces maximas de pasadas, la cantidad de slots:
            for i in range(len(ob.material_slots)):

                # obtenemos solo 1 indice malo:
                bad_index = next((i for i, ms in enumerate(ob.material_slots) if not ms.material), None)
                
                # si ya no hay indice malo seleccionado, entonces paramos:
                if bad_index is None:
                    break

                # borramos el indice malo:
                ob.active_material_index = bad_index
                bpy.ops.object.material_slot_remove()  

    
    def check_minimum_materials(self, context, objects_list:List[Object]) -> None:

        white = [0.8, 0.8, 0.8, 1.0]

        self.remove_void_material_slots(context, objects_list)

        # si no tiene material se lo asignamos:
        for ob in objects_list:
            mat_outher_name = ob.name + RBDLabNaming.SUFIX_OUTER_MAT
            if len(ob.material_slots) <= 0:
                if mat_outher_name not in ob.material_slots:
                    add_material(context, ob.name, mat_outher_name, white)
        

    def execute(self, context):
        
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        tcoll_list = rbdlab.lists.target_coll_list

        # original_active = context.active_object
        original_selection = [ob for ob in context.selected_objects if ob.type == 'MESH' and ob.visible_get()]

        # chequear si traen minimo un materail, sino se les crea:
        self.check_minimum_materials(context, original_selection)

        # creando la estructura de carpetas RBDLab:
        set_active_collection_to_master_coll(context)
    
        # si no esta seteada la coll originals entonces la creo y la seteo:
        originals_coll = create_originals_coll_if_not_exist(context, rbdlab)
    
        tcoll = self.single_output_or_not(context, tcoll_list, original_selection)

        # Mi objeto se llama "BooleanFracture" y mi GN también y el modifier también
        object_name = RBDLabNaming.BOOLFRACTURE_GN_OB # Nombre del objecto con el GN

        # Hacemos el Append:
        # Nota: El node_group de GN al finalizar se eliminará (en bf_apply.py).
        if object_name not in bpy.data.node_groups:
            blend_file = "BooleanFracture.blend"
            lib_path = join(RBDLabPaths.LIBS, blend_file)
            inner_path = "Object"
            file_path = join(lib_path, inner_path, object_name)
            directory = join(lib_path, inner_path)
            bpy.ops.wm.append(
                filepath=file_path,
                directory=directory,
                filename=object_name
            )

        # Capturamos el objecto que contiene el GN que se convertira en los planos:
        GN_ob = context.view_layer.objects.get(object_name)
        if not GN_ob:
            self.report({'ERROR'}, "Not GN Object!")
            return {'CANCELLED'}

        # Una vez existe la coll originals podemos mover los objetos a esa coll:
        move_objects_to_collection(context, original_selection, originals_coll.name)
        
        all_new_obs = []
        
        # creo un id:
        item_id = str(uuid4())[:6]
        
        for ob in original_selection:

            # depende de si se usa single output o no:
            coll_name = self.single_output_name if self.single_output else ob.name

            # Duplicamos objeto en low level:
            ob_to_fracture = ob.copy()
            ob_to_fracture.data = ob.data.copy()
            ob_to_fracture.animation_data_clear()

            # si ya tenía un from, es porque había sido fracturado previamente:
            if RBDLabNaming.FROM in ob:
                # por lo tanto respetamos el primer from:
                ob_to_fracture[RBDLabNaming.FROM] = ob[RBDLabNaming.FROM]
            else:
                # no fue nunca fracturado así que guardamos el from:
                ob_to_fracture[RBDLabNaming.FROM] = ob.name
            
            # Para poder transferir el material con el modifier boolean fast, es necesario q tenga el material ambos objetos:
            if RBDLabNaming.BF_INNER_MAT_NAME not in ob_to_fracture.data.materials:
                # si el objeto no tiene el material se lo pasamos del plano al objeto:
                # bf_inner_mat = bpy.data.materials.get(RBDLabNaming.BF_INNER_MAT_NAME)
                bf_inner_mat = next((mat for mat in GN_ob.data.materials if RBDLabNaming.SUFIX_INNER_MAT in mat.name), None)
                if bf_inner_mat:
                    ob_to_fracture.data.materials.append(bf_inner_mat)
            else:
                # Si refracturamos para que respete el material interno, tengo que
                # asegurarme de que usan el mismo inner material, por lo tanto:
                # Si el objeto ya lo tenia, le ponemos al plano el del objeto:
                bf_inner_mat = next((mat for mat in ob_to_fracture.data.materials if RBDLabNaming.SUFIX_INNER_MAT in mat.name), None)
                if bf_inner_mat:
                    GN_ob.material_slots[0].material = bf_inner_mat


            # Guardamos los nuevos objetos (los que seran fracturados):
            all_new_obs.append(ob_to_fracture)

            # y los muevo a su collection (Sino existe la ceamos):
            move_objects_to_collection(context, [ob_to_fracture], coll_name)
            # ob.hide_viewport = True # ocultar monitor
            ob.hide_set(True) # ocultar ojito

            # Copiamos los planos por cada objeto (recordamos q funciona multiobjeto) 
            # NOTA: esto copiada un gn por cada objeto, ya que el gn solo admitia 1 objeto, pero ahora lo preparamos para usar por collection
            # GN_ob_copy = GN_ob.copy()
            # GN_ob_copy.data = GN_ob.data.copy()

            # pongo el ProtoPlano en el origen del objeto:
            # GN_ob_copy.matrix_world = ob_to_fracture.matrix_world
            GN_ob.matrix_world = ob_to_fracture.matrix_world
            
            gn_coll = move_objects_to_collection(context, [GN_ob], RBDLabNaming.BF_GN_COLL)

            # creando collection temporal y linkando los objetos:

            if item_id not in GN_ob.name:
                GN_ob.name = GN_ob.name + "_" + item_id

            # tmp_coll = bpy.data.collections.get(item_id)
            valid_colls = [coll for coll in bpy.data.collections if RBDLabNaming.BF_COLL_ID in coll]
            tmp_coll = next((coll for coll in valid_colls if coll[RBDLabNaming.BF_COLL_ID] == item_id), None)
            if not tmp_coll:
                tmp_coll = bpy.data.collections.new(item_id)
                gn_coll.children.link(tmp_coll)

            tmp_coll[RBDLabNaming.BF_COLL_ID] = item_id
            tmp_coll.objects.link(ob_to_fracture)

            if gn_coll:

                # set_active_object(context, ob=GN_ob_copy, only_selected_ob=True)
                set_active_object(context, ob=GN_ob, only_selected_ob=True)

                # GN_mod = GN_ob_copy.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
                GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
                
                # Seteamos el object al input del modifier de GN:
                set_exposed_attributes_of_gn(GN_mod, "Collection", tmp_coll, debug=False)
                set_exposed_attributes_of_gn(GN_mod, "Seed", random.randint(0, 3000), debug=False)

            # El dummy es un cubo en el BooleanFracture.blend para poder hacer cambiso al GN en desarrollo:
            dummy_ob = bpy.data.objects.get("Dummy")
            if dummy_ob:
                rm_ob(dummy_ob)
            
            dummy_coll = bpy.data.collections.get("Dummy")
            if dummy_coll:
                remove_collection(context, dummy_coll)


        # cuado duplicaba el gn por cada uno, luego borraba el original:
        # rm_ob(GN_ob)

        # guardamos la información relevante:
        # guardo los objetos con los gn en el listado:
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        
        # si ya existe el nombre lo incrementamos con 0x:
        new_name = name_increment(bfracture_gn_list)

        DEBUG = False
        if DEBUG:
            if item_id not in new_name:
                new_name = new_name + "_" + item_id


        bfracture_gn_list.add_item(new_name, item_id, tcoll, base_planes=[GN_ob], objects_to_fracture=all_new_obs)

        ui.boolean_method_phase = 'SETTINGS_GN'
        print("[boolean_fracture.add] End: " + str(datetime.now() - start))
        return {'FINISHED'}

    def invoke(self, context, event):
        
        if len(context.selected_objects) == 0:
            self.report({'WARNING'}, "No selected Objects!")
            return {'CANCELLED'}
        
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False

        left = layout.row(align=True)
        left.prop(self, "single_output", text="Single Output")
        right = left.row(align=True)
        right.enabled = self.single_output
        right.alert = self.single_output and len(self.single_output_name) <= 0
        right.prop(self, "single_output_name", text="")
