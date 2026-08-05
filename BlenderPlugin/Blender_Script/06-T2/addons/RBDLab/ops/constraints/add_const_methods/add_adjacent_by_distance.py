import bpy
from typing import List
from  mathutils import Vector
from bpy.types import Object
from ....addon.naming import RBDLabNaming
from ....Global.basics import rm_ob
from ....Global.functions import hide_collection_in_viewport, append_attribute_to_obj, remove_collection_if_is_empty, hide_collection_in_render
from ....ops.constraints.detect import restore_default_neighbors


def add_adjacent_by_distance(self, context, rbdlab, chunks: List[Object]) -> None:

    rbdlab_const = rbdlab.constraints

    const_counter = 0

    # Create Constraint Group.
    # ++++++++++++++++++++++++++++
    group = rbdlab_const.create_group()
    group_id = group.idname

    # [On Create] Guardo el glue strength en el active_group:
    group.glue_strength = rbdlab.constraints.glue_strength

    # Create Constraint Collection.
    # ++++++++++++++++++++++++++++
    # NOTA: Ya no usamos el nombre del target collection sino del grupo.
    constraints_coll_name = group.idname  # Nombre temporal para identificar la collection con el grupo.

    # Prepare collection
    constraints_coll = bpy.data.collections.get(constraints_coll_name)
    if not constraints_coll:
        constraints_coll = bpy.data.collections.new(constraints_coll_name)
        const_coll = bpy.data.collections.get(RBDLabNaming.CONST_COLL)
        if const_coll:
            const_coll.children.link(constraints_coll)

    # Add the collection reference to the group.
    group.collection = constraints_coll
    group.name = "Adjacent Group"
    group.name = group.name
    group.type = 'ADJACENTS'
    
    # Find and Process Constraints.
    # ++++++++++++++++++++++++++++

    name_iter = 0
    const_ob_name_prefix = ".GlueConstraint_" + group.idname[:6] + "_"

    # Utils Functions.
    new_constraint_empty = self.original_empty.copy
    link_to_const_group_collection = group.collection.objects.link

    def get_neighbors(chunk):            
        return chunk.neighbor_chunks.get_neighbors(use_cluster=False)
            
    variation = 0
    added_chunks = set()

    threshold = rbdlab_const.threshold_adjacents_selection
    selected_objects = {}

    chunk_and_from = { chunk : chunk.get("rbdlab_from") for chunk in chunks if "rbdlab_from" in chunk }
    for chunk, chunk_from in chunk_and_from.items(): 


        for neighbor in chunks:
            
            if chunk == neighbor: 
                continue

            if neighbor in selected_objects:
                continue

            if chunk_from == neighbor.get("rbdlab_from"):
                continue
            
            # neighbors = [chk.object.name for chk in chunk.neighbor_chunks.chunks]
            # # print(neighbors)

            # if neighbor.name not in neighbors:
            #     print(neighbor.name, "Skip")
            #     continue

            distance = Vector(chunk.location - neighbor.location).length 
            if  distance < threshold:
                selected_objects[neighbor] = distance

        for neighbor_chunk, neighbor_distance in selected_objects.items():

            # if neighbor_distance > 0.2:
            #     continue
            
            # por alguna razon que desconozco a veces el neighbor_chunk es None y daba errores, con esto se continua
            if neighbor_chunk is None:
                # print(1)
                continue
            
            # si alguno de los involucrados no estaba seleccionado previamente y es by selection los descatamos:
            if chunk not in self.original_previous_selection or neighbor_chunk not in self.original_previous_selection:
                # print(2)
                continue
            
            ### Aquí se comprueba si apuntan a nombres iguales o distintos, para saber si son o no adjacents:
            ### Solo adjacents directos:
            if rbdlab.constraints.adjacents_only_between_different_froms:
                if chunk_from == neighbor_chunk.get("rbdlab_from"):
                    # print(3)
                    continue

            # print("---##########################################################################---")

            # Agregar chunks al constraint group.
            if chunk not in added_chunks:
                group.add_chunk(chunk)
                added_chunks.add(chunk)

            if neighbor_chunk not in added_chunks:
                group.add_chunk(neighbor_chunk)
                added_chunks.add(neighbor_chunk)

            new_empty = new_constraint_empty()
            new_empty[RBDLabNaming.GROUP_ID] = group_id  # Para identificar el grupo con el constraint object.
            new_empty.color = (1, 0, 0, 1)
            new_empty.name = const_ob_name_prefix + str(name_iter)

            group.total_constrainst +=1

            const_counter += 1

            self.constraints_centering(rbdlab_const, new_empty, chunk, variation, neighbor_chunk)

            variation += 1

            # linking to the scene
            name_iter += 1

            link_to_const_group_collection(new_empty)
            # size by default:
            size = float("%f" % rbdlab.constraints.visual_size)
            new_empty.scale = [size, size, size]

            empty_rbd_const = new_empty.rigid_body_constraint
            empty_rbd_const.type = rbdlab.constraints.constraint_type

            context.view_layer.objects.active = new_empty

            # Vinculando los Pares:
            empty_rbd_const.object1 = chunk
            empty_rbd_const.object2 = neighbor_chunk

            # store information in objects
            key_constraints = RBDLabNaming.CONSTRAINTS

            new_empty[RBDLabNaming.CONST_DIST] = neighbor_distance  # Use cached distance from neighbor chunk data.

            # use iterations an iterations on create:
            empty_rbd_const.use_override_solver_iterations = rbdlab.constraints.override_iterations
            empty_rbd_const.solver_iterations = rbdlab.constraints.iterations

            # seteando valores por defecto on create:
            if rbdlab.constraints.constraint_type == 'GENERIC_SPRING':
                self.set_generic_spring_defaults(empty_rbd_const, group)

            if key_constraints not in chunk:
                chunk[key_constraints] = new_empty.name
            else:
                append_attribute_to_obj(chunk, key_constraints, new_empty.name)

            if key_constraints not in neighbor_chunk:
                neighbor_chunk[key_constraints] = new_empty.name
            else:
                append_attribute_to_obj(neighbor_chunk, key_constraints, new_empty.name)

    rm_ob(self.original_empty)

    # ???
    rbdlab.filtered_target_collection["enable_constraints_toggle"] = True
    rbdlab.filtered_target_collection["disable_constraints_toggle"] = False

    # Get updated collection name from group.
    constraints_coll_name = group.collection.name
    hide_collection_in_viewport(context, constraints_coll_name)
    hide_collection_in_render(constraints_coll_name)
    remove_collection_if_is_empty(context, constraints_coll_name)

    # Reestablecemos los venicos por defecto:
    restore_default_neighbors(context)

    del chunks
    del added_chunks

    print("Info! Created %i Constraints" % const_counter)
