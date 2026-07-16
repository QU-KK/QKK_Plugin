import bpy
from typing import List
from bpy.types import Object
from ....addon.naming import RBDLabNaming
from ....Global.basics import rm_ob
from ....Global.functions import hide_collection_in_viewport, append_attribute_to_obj, remove_collection_if_is_empty, hide_collection_in_render


def add_constraints_to_object(self, context, rbdlab, chunks: List[Object]) -> None:

    rbdlab_const = rbdlab.constraints
    apply_by = rbdlab_const.apply_by
    coll_workgroup = rbdlab_const.get_selected_work_group_collections
    target_ob = rbdlab.constraints.to_ob_choose

    const_counter = 0

    # Create Constraint Group.
    # ++++++++++++++++++++++++++++
    group = rbdlab_const.create_group()
    group.type = apply_by
    group_id = group.idname

    coll_name = coll_workgroup[0].name

    if len(coll_workgroup) > 1:
        group.name = "Attach Group"
    else:
        group.name = "Attach " + coll_name

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
    
    group.name = group.name

    name_iter = 0
    const_ob_name_prefix = ".GlueConstraint_" + group.idname[:6] + "_"


    # Utils Functions.
    new_constraint_empty = self.original_empty.copy
    link_to_const_group_collection = group.collection.objects.link
    
    variation = 0
    added_chunks = set()

    for chunk in chunks:

        # Agregar chunks al constraint group.
        if chunk not in added_chunks:
            group.add_chunk(chunk)
            added_chunks.add(chunk)

        new_empty = new_constraint_empty()
        new_empty[RBDLabNaming.GROUP_ID] = group_id  # Para identificar el grupo con el constraint object.
        new_empty.color = (1, 0, 0, 1)
        new_empty.name = const_ob_name_prefix + str(name_iter)

        group.total_constrainst +=1

        const_counter += 1

        self.constraints_centering(rbdlab_const, new_empty, chunk, variation, target_ob)

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
        empty_rbd_const.object2 = target_ob

        # store information in objects
        key_constraints = RBDLabNaming.CONSTRAINTS

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
        
        if key_constraints not in target_ob:
            target_ob[key_constraints] = new_empty.name
        else:
            append_attribute_to_obj(target_ob, key_constraints, new_empty.name)

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

    print("Info! Created %i Constraints" % const_counter)
