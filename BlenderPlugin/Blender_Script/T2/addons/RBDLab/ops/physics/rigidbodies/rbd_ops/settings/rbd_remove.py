import bpy
from datetime import datetime
from bpy.types import Operator
from ......addon.naming import RBDLabNaming
from ......Global.functions import remove_all_keyframes_in_action
from ......Global.basics import select_object, set_active_object, deselect_all_objects


class RBDLAB_OT_rm(Operator):
    bl_idname = "rbdlab.rigidbody_rm"
    bl_label = "Remove Rigid Bodies"
    bl_description = "Remove Rigid Bodies to the current target collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if tcoll is None:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}
        
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'WARNING'}, "Not valid chunks in this collection!")
            return {'CANCELLED'}
       
        deselect_all_objects(context)

        # seleccionamos los passive su hubiera:
        bpy.ops.rbdlab.set_passive_select()
        if context.selected_objects:
            # eliminamos los passive:
            bpy.ops.rbdlab.set_passive_remove()
        
        deselect_all_objects(context)

        # seleccionamos los kinemaitc su hubiera:
        bpy.ops.rbdlab.set_kinematic_select()
        if context.selected_objects:
            # eliminamos los kinematic:
            bpy.ops.rbdlab.set_kinematic_remove()

        deselect_all_objects(context)

        bpy.ops.rbdlab.const_rm()

        ob = tcoll_list.get_first_valid_ob(context)
        set_active_object(context, ob)

        for ob in chunks:

            if RBDLabNaming.ACTIVE in ob:
                del ob[RBDLabNaming.ACTIVE]
            
            if RBDLabNaming.RBD_KINEMATIC in ob:
                del ob[RBDLabNaming.RBD_KINEMATIC]
            
            if RBDLabNaming.RBD_SEL_KINEMATIC in ob:
                del ob[RBDLabNaming.RBD_SEL_KINEMATIC]

            if RBDLabNaming.PASSIVE in ob:
                del ob[RBDLabNaming.PASSIVE]

            remove_all_keyframes_in_action(context, ob, "rigid_body.kinematic")
            
            # si ya tiene el constraint, se los reliminamos:
            prev_const = ob.constraints.get(RBDLabNaming.CHILD_OF)
            if prev_const:
                # eliminamos sus keyframes de sus child of enable:
                dpath = "constraints[\"" + RBDLabNaming.CHILD_OF + "\"].enabled"
                remove_all_keyframes_in_action(context, ob, dpath)
                ob.constraints.remove(prev_const)

            select_object(context, ob)
            if RBDLabNaming.CURRENT_MASS in ob:
                del ob[RBDLabNaming.CURRENT_MASS]

            if RBDLabNaming.RBD_WORLD in bpy.data.collections:
                if ob.name in bpy.data.collections[RBDLabNaming.RBD_WORLD]:
                    bpy.data.collections[RBDLabNaming.RBD_WORLD].objects.unlink(ob)

        if "kinematic_keyframes_text" in tcoll:
            del tcoll["kinematic_keyframes_text"]
        
        rbds_obs = [ob for ob in context.selected_objects if ob.rigid_body]
        if rbds_obs:
            set_active_object(context, rbds_obs[0])
            bpy.ops.rigidbody.objects_remove()
        
        # les reseteamos las collision layers:
        # con hacerlo solo a uno vale (por rendimiento):
        chunks[0].rbdlab.rbd_collections = {'1'}

        deselect_all_objects(context)

        if RBDLabNaming.COLL_WITH_RBD in tcoll:
            del tcoll[RBDLabNaming.COLL_WITH_RBD]

        # recargo la ui
        rbdlab.lists.target_coll_list.list_index = rbdlab.lists.target_coll_list.list_index

        scn.frame_set(scn.frame_start)
        print("[rbdlab.rigidbody_rm] End: " + str(datetime.now() - start))
        return {'FINISHED'}
