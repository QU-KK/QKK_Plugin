import bpy

from bpy.types import Operator
from ...Global.functions import remove_collection_by_name, remove_collection, remove_collection_if_is_empty
from ...Global.basics import rm_ob
from ...Global.get_common_vars import get_common_vars
from ...addon.naming import RBDLabNaming
from bpy.props import StringProperty


class RM_OT_target_coll_from_list(Operator):
    bl_idname = "rbdlab.rm_target_coll_from_list"
    bl_label = "Remove Target Collection"
    bl_description = "Permanently deletes the collection and child objects in both the low and high version"
    bl_options = {'REGISTER', 'UNDO'}

    to_rm: StringProperty(default="")

    def execute(self, context):

        id_name = self.to_rm

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)

        item = tcoll_list.get_item_by_id_name(id_name)

        # obtengo la collection real antes de eliminar el item del listado:
        coll = item.coll

        if not coll:
            print("Cant get Collection fom id:" + id_name)
            return {'CANCELLED'}

        coll_name = coll.name
        constraints = []

        # Si tuvieran metal soft los borramos:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        if not metal_list.is_void:
            item = metal_list.active
            if item:
                # Quitamos el metal soft del listado:
                bpy.ops.rbdlab.metalsoft_creation_rm_metal_mesh(id_to_rm="[\"" + item.id_name + "\", " + "\"" + item.from_coll_id + "\"]")

        # los sacamos de los rigidbodies de blender antes de borrarlos:
        rbd_coll = bpy.data.collections.get("RigidBodyWorld")
        if rbd_coll:

            for chunk in coll.objects:
                if chunk.name in rbd_coll.objects:

                    # recolectamos los constraints de cada chunk:
                    if RBDLabNaming.CONST_COLL.lower() in chunk:
                        constraints_names = chunk[RBDLabNaming.CONST_COLL.lower()].split()
                        for c_name in constraints_names:
                            c_obj = context.view_layer.objects.get(c_name)
                            if c_obj:
                                if c_obj not in constraints:
                                    constraints.append(c_obj)

                    # lo quitamos de RigidBodiyWorld:
                    rbd_coll.objects.unlink(chunk)

        # Elimino las collections:
        # ------------------------------------------------------------------

        # si tuviera high:
        if RBDLabNaming.SUFIX_LOW in coll_name:
            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            if coll_high_name in bpy.data.collections:
                remove_collection_by_name(context, coll_high_name, and_objects=True)

        # si tuviera constraints: # OLD
        # const_coll_name = coll_name + "_GlueConstraints"
        # if const_coll_name in collections:
        #     remove_collection_by_name(context, const_coll_name, True)

        # si tuviera constraints:
        if constraints and RBDLabNaming.CONST_COLL in bpy.data.collections:

            # Primero eliminamos los constraints objects:
            # for const in constraints:
            #     rm_ob(const)
            
            # Los mandamos al limbo:
            for const in constraints:
                for user_coll in const.users_collection:
                    user_coll.objects.unlink(const)

            root_constraints_coll = bpy.data.collections.get(RBDLabNaming.CONST_COLL)
            if root_constraints_coll:

                all_source_collections = rbdlab.constraints.get_selected_work_group_collections
                all_constraint_groups = rbdlab.constraints.get_all_constraints_groups

                for const_coll in root_constraints_coll.children:

                    # si tiene constraints la ignoramos:
                    if len(const_coll.objects) > 0:
                        continue

                    # para los grupos vacios:

                    # preparamos el name target:
                    constr_group_name = const_coll.name.replace(RBDLabNaming.PREFIX_CONST, "")

                    # buscamos el target group:
                    for cg in all_constraint_groups:
                        if cg.name == constr_group_name:
                            # eliminamos el grupo:
                            rbdlab.constraints.remove_group(cg)
                            # rbdlab.constraints.active_group_index = len(rbdlab.constraints.group_list)-1

                    # elimino del listado del source collection (ya que quedara un clear sino al borrar las collections vacias):
                    for i, sc in enumerate(all_source_collections):
                        if sc.name == coll_name:
                            if -1 < i <= (rbdlab.constraints.length-1):
                                rbdlab.constraints.list[i].remove = True

                    # si queda la collection vacia la eliminamos:
                    remove_collection_if_is_empty(context, const_coll)

            # Si RBDLab_Constratins queda vacia la eliminamos:
            if len(root_constraints_coll.children_recursive) == 0:
                remove_collection(context, root_constraints_coll)

        # si tuviera handler:
        bbox_handler_name = coll_name + RBDLabNaming.SUFIX_BBOX
        if bbox_handler_name in context.view_layer.objects:
            rm_ob(bbox_handler_name)

        # eliminamos la low (las custom coll no eliminamos la collection del usuario):
        if RBDLabNaming.CUSTOM_COLL not in coll:
            remove_collection(context, coll, and_objects=True)

        # Lo quitamos del listado:
        tcoll_list.remove_coll_list(tcoll_item)
        tcoll_list.list_index = len(tcoll_list.list)-1

        return {'FINISHED'}


'''
class RM_OT_target_coll(Operator):
    bl_idname = "rbdlab.rm_target_coll"
    bl_label = "Remove Target Collection"
    bl_description = "Permanently deletes the collection and child objects in both the low and high version"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    coll = bpy.data.collections[coll_name]

                    # lo dejamos en low por si estuvieramos en high
                    rbdlab.low_or_high_visibility_viewport = "Low"

                    if "RigidBodyWorld" in bpy.data.collections:
                        rbd_coll = bpy.data.collections["RigidBodyWorld"]

                        # los sacamos de los rigidbodies de blender antes de borrarlos:
                        for chunk in coll.objects:
                            if chunk.name in rbd_coll.objects:
                                rbd_coll.objects.unlink(chunk)

                    # los borramos:
                    remove_collection_by_name(context, coll_name, True)
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    if coll_high_name in bpy.data.collections:
                        remove_collection_by_name(context, coll_high_name, True)

                    const_coll_name = coll_name + "_GlueConstraints"
                    if const_coll_name in bpy.data.collections:
                        remove_collection_by_name(context, const_coll_name, True)

                    bbox_handler_name = coll_name + RBDLabNaming.SUFIX_BBOX
                    rm_ob(bbox_handler_name)


        return {'FINISHED'}

    def invoke(self, context, event):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    return context.window_manager.invoke_props_dialog(self)
        else:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="You are about to delete the collection")
        col.label(text="and everything related to it")
        col.label(text="are you sure?")
'''
