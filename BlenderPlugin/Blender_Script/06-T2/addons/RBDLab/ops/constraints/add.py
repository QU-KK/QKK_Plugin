import bpy
from time import time
from typing import List
from mathutils import Matrix
from bpy.types import Operator, Object
from ...addon.naming import RBDLabNaming
from os.path import dirname, realpath, join
from bpy.props import BoolProperty, StringProperty
from ...Global.get_common_vars import get_common_vars
from ...Global.basics import set_active_object, deselect_all_objects
from ...Global.functions import unhide_collection_in_viewport, set_active_collection_to_master_coll
from ...Global.gpu import TempDrawMeshGroupsManager

# from .add_const_methods.add_adjacent_by_distance import add_adjacent_by_distance
from .add_const_methods.add_adjacents import add_adjacent_constraints
from .add_const_methods.add_constraints_to_object import add_constraints_to_object
from .add_const_methods.add_standar_constraints import add_standar_constraints
from .add_const_methods.add_constraints_per_islands import add_constraints_per_islands


class CONSTRAINTS_OT_add(Operator):
    bl_idname = "rbdlab.constraints_add"
    bl_label = "Add Constraints"
    bl_description = "Create a group of constraitns from Source Collections"
    bl_options = {'REGISTER', 'UNDO', 'UNDO_GROUPED'}

    original_empty: Object
    create_inter_cluster_group: BoolProperty(default=False, options={'SKIP_SAVE'})
    create_adjacent_group: BoolProperty(default=False, options={'SKIP_SAVE'})
    adjacent_coll_id: StringProperty(default="", options={'SKIP_SAVE'})
    original_previous_selection = []


    def constraints_centering(self, rbdlab_const, new_empty, chunk, variation, neighbor_chunk):
        #-------------------------------------------------------------------------------------------
        # centrador de constraints
        #-------------------------------------------------------------------------------------------

        # ----------------------------------------------------------------------------------------------------------------
        # Nota
        # Con new_empty.location y neighbor_chunk.location obtienes las coordenadas iniciales de antes de empezar la sim.
        # sin embargo con matrix_world.translation obtienes las coordenadas actuales en el frame actual en el que estes. 
        # (parece que .location son coordenadas en local, y matrix_world.translation son en global.)
        # ----------------------------------------------------------------------------------------------------------------
        
        # para emparentar con el uno y el otro (los pares e impares, repartidos uno si uno no):
        even_and_odd = chunk if variation % 2 == 0 else neighbor_chunk

        # constraint in center:
        # const_in_center = (chunk.location + neighbor_chunk.location) / 2
        const_in_center = (chunk.matrix_world.translation + neighbor_chunk.matrix_world.translation) * 0.5


        even_odd_position = even_and_odd.location
        position = const_in_center if rbdlab_const.constraints_between_chunks else even_odd_position

        # Quería chequear si con los clusters esto estaba funcionando también (el between chunks):
        # print("position == const_in_center", position == const_in_center)
        
        # constraints en el uno y en el otro (pares y impares repartidos):
        new_empty.location = position


        # Parent low level:
        # ----------------------------------------------------------------------------------------------------------------
        new_empty.parent = even_and_odd
        # si es between construyo un matrixworld con const_in_center, sino le copiamos la de par/impar que sea:
        mw = Matrix.Translation(const_in_center) if rbdlab_const.constraints_between_chunks else even_and_odd.matrix_world.copy() 
        new_empty.matrix_world = mw


    def check_first_chunk(self, first_chunk):
        if not first_chunk:
            self.report({'WARNING'}, "Not valid objects in this target collection!")
            return {'CANCELLED'}

        if not hasattr(first_chunk.rigid_body, "type"):
            self.report({'WARNING'}, "Is necessary that the objects in the collection, first have Rigid Bodies on them!")
            return {'CANCELLED'}

        
    @staticmethod
    def append_constraint(obj_name):

        abs_file_path = dirname(dirname(realpath(__file__)))
        fname = "constraint.blend"
        inner_path = "GPencil"
        file_path = join(abs_file_path, "../", "libs", fname)
        
        # print("inner_path", inner_path)

        if obj_name not in bpy.data.objects:
            bpy.ops.wm.append(
                filepath=join(file_path, inner_path, obj_name),
                directory=join(file_path, inner_path),
                filename=obj_name,
            )


    def original_empty_add_constraint(self, context):
        for ob in context.scene.objects:
            if ob.name.startswith("Constraint"):
                self.original_empty = ob
                set_active_object(context, self.original_empty)
                self.original_empty.name = "empty"
                self.original_empty.hide_render = True
                break

        bpy.ops.rigidbody.constraint_add()

    @staticmethod
    def config_some_settings(context, rbdlab):
        rbd_const = context.object.rigid_body_constraint 
        rbd_const.use_breaking = rbdlab.constraints.breakable
        rbd_const.breaking_threshold = rbdlab.constraints.glue_strength
        rbd_const.disable_collisions = rbdlab.constraints.disable_collisions
    

    def prepare_valid_chunks(self, context, rbdlab, apply_by, coll_workgroup) -> List[Object]:
    
        if apply_by in ['SELECTION', 'CLUSTER']:
            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]
        
        elif apply_by == 'COLLECTION':
            valid_objects = [ob for coll in coll_workgroup if coll is not None for ob in coll.objects if ob.type == 'MESH' and ob.visible_get()]

        if not valid_objects:
            return None
   
        first_chunk = valid_objects[0]
        self.check_first_chunk(first_chunk)
        
        # ahora usamos constraints de tipo empty:
        # self.append_constraint("Constraint")
        bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        context.active_object.name = "Constraint"

        self.original_empty_add_constraint(context)
        self.config_some_settings(context, rbdlab)

        return valid_objects
    

    def set_generic_spring_defaults(self, empty_rbd_const, active_group):

        empty_rbd_const.spring_type = active_group.get_default_properties("spring_type")
                    
        active_group.spring_damping_uniq = active_group.get_default_properties("spring_damping_uniq")
        empty_rbd_const.spring_damping_x = active_group.get_default_properties("spring_damping_uniq")
        empty_rbd_const.spring_damping_y = active_group.get_default_properties("spring_damping_uniq")
        empty_rbd_const.spring_damping_z = active_group.get_default_properties("spring_damping_uniq")

        active_group.spring_damping_ang_uniq = active_group.get_default_properties("spring_damping_ang_uniq")
        empty_rbd_const.spring_damping_ang_x = active_group.get_default_properties("spring_damping_ang_uniq")
        empty_rbd_const.spring_damping_ang_y = active_group.get_default_properties("spring_damping_ang_uniq")
        empty_rbd_const.spring_damping_ang_z = active_group.get_default_properties("spring_damping_ang_uniq")

        empty_rbd_const.use_spring_ang_x = active_group.get_default_properties("use_spring_ang_x")
        empty_rbd_const.use_spring_ang_y = active_group.get_default_properties("use_spring_ang_y")
        empty_rbd_const.use_spring_ang_z = active_group.get_default_properties("use_spring_ang_z")

        empty_rbd_const.use_spring_x = active_group.get_default_properties("use_spring_x")
        empty_rbd_const.use_spring_y = active_group.get_default_properties("use_spring_y")
        empty_rbd_const.use_spring_z = active_group.get_default_properties("use_spring_z")

        active_group.spring_stiffness_uniq = active_group.get_default_properties("spring_stiffness_uniq")
        active_group.spring_stiffness_ang_uniq = active_group.get_default_properties("spring_stiffness_ang_uniq")

        active_group.limit_ang_lower_uniq = active_group.get_default_properties("limit_ang_lower_uniq")
        active_group.limit_ang_upper_uniq = active_group.get_default_properties("limit_ang_upper_uniq")
        active_group.limit_lin_lower_uniq = active_group.get_default_properties("limit_lin_lower_uniq")
        active_group.limit_lin_upper_uniq = active_group.get_default_properties("limit_lin_upper_uniq")    


    def execute(self, context):
        op_time = time()

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        
        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}

        # si estamos visualizando metal, lo cambio a chunks para poder trabajar:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        current_metal = metal_list.active

        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}
        
        # si se usa to object y no hay object cancelamos:    
        if rbdlab.constraints.const_to_ob:
            if not rbdlab.constraints.to_ob_choose:
                self.report({'ERROR'}, "If use To Object, the Object is mandatory!")
                return {'CANCELLED'}
            
        # guardo la seleccion original para luego consultarla:
        self.original_previous_selection = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

        # si no esta la collection de constraints la creamos:
        if RBDLabNaming.CONST_COLL not in bpy.data.collections:
            RBDLab_Constraints_coll = context.blend_data.collections.new(name=RBDLabNaming.CONST_COLL)
            rbdlab.root_collection.children.link(RBDLab_Constraints_coll)

        rbdlab_const = rbdlab.constraints
        apply_by = rbdlab_const.apply_by
        coll_workgroup = rbdlab_const.get_selected_work_group_collections

        if rbdlab_const.filter_adjacents:
            apply_by = 'SELECTION'

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # by selection:
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        if apply_by == 'SELECTION':
            
            chunks = self.prepare_valid_chunks(context, rbdlab, apply_by, coll_workgroup)
            
            if not chunks:
                self.report({'WARNING'}, "No valid selected chunks!")
                return {'CANCELLED'}
            
            if RBDLabNaming.OBJECT__COLL_ID in chunks[0]:
                print("CHUNKS ADJACENTS", len(chunks), chunks[0][RBDLabNaming.OBJECT__COLL_ID], self.adjacent_coll_id)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # by collection:
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        elif apply_by == 'COLLECTION':

            if len(coll_workgroup) < 1:
                self.report({'WARNING'}, "Mark fist one Source Collection!")
                return {'CANCELLED'}

            [unhide_collection_in_viewport(context, coll.name) for coll in coll_workgroup if coll is not None]

            chunks = self.prepare_valid_chunks(context, rbdlab, apply_by, coll_workgroup)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # by cluster:
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        elif apply_by == 'CLUSTER':

            deselect_all_objects(context)
            [cluster.select_chunks(True) for cluster in rbdlab_const.clusters]

            chunks = self.prepare_valid_chunks(context, rbdlab, apply_by, coll_workgroup)

        #----------------------------------------------------------------------------------------
        # Se procede
        #----------------------------------------------------------------------------------------
        if not chunks:
            self.report({'WARNING'}, "No valid chunks!")
            return {'CANCELLED'}
        
        # print("chunks[0].location", chunks[0].location)

        # ----------------------------------------------------------------------------
        # Adjacents:
        # ----------------------------------------------------------------------------

        if rbdlab_const.filter_adjacents and rbdlab_const.apply_by != 'CLUSTER':

            add_adjacent_constraints(self, context, rbdlab, chunks)

            # if rbdlab_const.neighbors_search_method == 'DISTANCE':
            #     add_adjacent_by_distance(self, context, rbdlab, chunks)
            # else:
            #     add_adjacent_constraints(self, context, rbdlab, chunks)

        # ----------------------------------------------------------------------------
        # To single Object:
        # ----------------------------------------------------------------------------
        elif rbdlab_const.const_to_ob:
            add_constraints_to_object(self, context, rbdlab, chunks)
        
        # ----------------------------------------------------------------------------
        # Per Islands:
        # ----------------------------------------------------------------------------
        elif rbdlab_const.const_per_islands:
            add_constraints_per_islands(self, context, rbdlab, chunks)
        
        # ----------------------------------------------------------------------------
        # Standar:
        # ----------------------------------------------------------------------------
        else:
            add_standar_constraints(self, context, rbdlab, chunks)
        
        # ----------------------------------------------------------------------------

        deselect_all_objects(context)

        # Si se quieren chunks inter cluster:
        if rbdlab_const.add_inter_clusters:

            if hasattr(self, RBDLabNaming.INTER_CLUSTER_CHUNKS):
                
                if self.inter_cluster_chunks:
                    [ob.select_set(True) for ob in self.inter_cluster_chunks]
                    
                    rbdlab_const.apply_by = 'SELECTION'
                    bpy.ops.rbdlab.constraints_add(create_inter_cluster_group=True)

        #----------------------------------------------------------------------------------------
        # Termiando
        #----------------------------------------------------------------------------------------
        # Return to original section.
        if self.create_inter_cluster_group:
            rbdlab_const.apply_by = 'CLUSTER'
            act_const_group = rbdlab_const.get_active_group
            # Desactivar las constraints por defecto.
            act_const_group.enabled = False

        rbdlab.ui.active_const_tab = 'EDIT'
        feedback = "[TIME] Create Constraint Group: %.2fs" % (time()-op_time) 
        print(feedback)
        self.report({'INFO'}, feedback)

        # al darle a create constraints apagamos los overlays:
        TempDrawMeshGroupsManager.stop(TempDrawMeshGroupsManager.get())

        # seteo RBDLab como collection activa:
        set_active_collection_to_master_coll(context)

        # restauro la visibilidad del metal:
        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state

        # Para evitar recomputar vecinos más veces de la cuenta en adjacents constraints:
        wm = context.window_manager
        if RBDLabNaming.WM_RECOMP_ADJACENT in wm:
         del wm[RBDLabNaming.WM_RECOMP_ADJACENT]

        self.original_previous_selection = []
        return {'FINISHED'}
    