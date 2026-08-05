import bpy
from typing import List, Set
from bpy.types import Object
from ....addon.naming import RBDLabNaming
from ....Global.basics import rm_ob
from ....Global.functions import hide_collection_in_viewport, append_attribute_to_obj, remove_collection_if_is_empty, hide_collection_in_render


def add_standar_constraints(self, context, rbdlab, chunks: List[Object]) -> None:
        
    rbdlab_const = rbdlab.constraints

    apply_by = rbdlab_const.apply_by
    use_clusters = apply_by == 'CLUSTER'
    coll_workgroup = rbdlab_const.get_selected_work_group_collections

    const_counter = 0

    # Create Constraint Group.
    # ++++++++++++++++++++++++++++
    group = rbdlab_const.create_group()
    group.type = apply_by
    group_id = group.idname

    # [On Create] Guardo el glue strength en el active_group:
    group.glue_strength = rbdlab.constraints.glue_strength

    coll_name = coll_workgroup[0].name

    # para los nombres de los grupos:
    const_type = rbdlab.constraints.constraint_type
    if const_type == 'FIXED':
        const_type = "Fixed"
    elif const_type == 'GENERIC_SPRING':
        const_type = "Soft"
    elif const_type == 'POINT':
        const_type = "Point"

    if len(coll_workgroup) > 1:
        group.name = "Constraints Group"
    else:
        # group.name = "Constraints " + const_type + " " + coll_name
        group.name = const_type + " " + coll_name

    if apply_by == 'CLUSTER':

        if len(coll_workgroup) > 1:
            group.name = "Clusters Group"
        else:
            group.name = "Clusters " + const_type + " " +  coll_name

        clusters = rbdlab_const.clusters
        for cluster in clusters:
            cluster_item = group.add_cluster(custom_id=cluster.id, custom_color=cluster.color)
            cluster_item.add_chunks(cluster.get_chunk_objects())

    # Create Constraint Collection.
    # ++++++++++++++++++++++++++++
    # NOTE: Ya no usamos el nombre del target collection sino del grupo.
    constraints_coll_name = group.idname  # Nombre temporal para identificar la collection con el grupo.

    # prepare collection
    if constraints_coll_name not in bpy.data.collections:
        constraints_coll = bpy.data.collections.new(constraints_coll_name)
        if RBDLabNaming.CONST_COLL in bpy.data.collections:
            bpy.data.collections[RBDLabNaming.CONST_COLL].children.link(constraints_coll)
    else:
        constraints_coll = bpy.data.collections[constraints_coll_name]

    # Add the collection reference to the group.
    group.collection = constraints_coll
    # HACK: para triggear el update_group_name que resolverá las posibles coincidencias del nombre.
    if self.create_inter_cluster_group:
        group.name = "Inter Cluster Group"
        group.name = group.name
        group.type = 'INTER_CLUSTER'
    elif self.create_adjacent_group:
        group.name = "Adjacent Group"
        group.name = group.name
        group.type = 'ADJACENTS'
    else:
        group.name = group.name

    # Find and Process Constraints.
    # ++++++++++++++++++++++++++++
    # total_chunks = len(chunks)
    # kd = kdtree.KDTree(total_chunks)
    name_iter = 0
    const_ob_name_prefix = ".GlueConstraint_" + group.idname[:6] + "_"


    # for i, chunk in enumerate(chunks):
    #    kd.insert(chunk.location, i)
    #    kd.balance()

    # INTER-CLUSTERS.
    if use_clusters:
        inter_cluster_chunks: Set[Object] = set()

    # Utils Functions.
    new_constraint_empty = self.original_empty.copy
    link_to_const_group_collection = group.collection.objects.link

    if rbdlab_const.limit_neighbor_constraints:
        limit_const = rbdlab_const.maximun_neighbor_constraints
    else:
        limit_const = 0

    def get_neighbors(chunk):            
        return chunk.neighbor_chunks.get_neighbors(use_cluster=use_clusters) if limit_const == 0 else chunk.neighbor_chunks.get_n_nearest_neighbors(limit_const, use_cluster=use_clusters)
    
    variation = 0
    added_chunks = set()

    for chunk in chunks:
        
        if chunk is None:
            continue

        for (neighbor_chunk, neighbor_distance) in get_neighbors(chunk):

            # por alguna razon que desconozco a veces el neighbor_chunk es None y daba errores, con esto se continua
            if neighbor_chunk is None:
                continue

            # print(chunk.name, "\t->\t", neighbor_chunk)

            # print(chunk.name, neighbor_chunk.name, neighbor_distance)

            # compruenbo si es by selection:
            if apply_by == 'SELECTION':
                # si alguno de los involucrados no estaba seleccionado previamente y es by selection los descatamos:
                if chunk not in self.original_previous_selection or neighbor_chunk not in self.original_previous_selection:
                    # print('WTF')
                    continue

            if use_clusters:

                # intentando fixear key cluster_id not found:
                if RBDLabNaming.CLUSTER_ID not in chunk or RBDLabNaming.CLUSTER_ID not in neighbor_chunk:
                    continue

                # Skip si las cluster_id son diferentes.
                if chunk[RBDLabNaming.CLUSTER_ID] != neighbor_chunk[RBDLabNaming.CLUSTER_ID]:
                    # INTER-CLUSTERS.
                    if rbdlab_const.add_inter_clusters:
                        inter_cluster_chunks.add(chunk)
                        inter_cluster_chunks.add(neighbor_chunk)
                    continue

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

    del chunks
    del added_chunks

    if use_clusters:
        rbdlab_const.clear_clusters()

        self.inter_cluster_chunks = inter_cluster_chunks

    print("Info! Created %i Constraints" % const_counter)
