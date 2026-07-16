import bpy
# from bpy.props import StringProperty
from bpy.types import Operator, Object, Context
from .....Global.functions import remove_all_keyframes_in_action
from .....Global.basics import deselect_all_objects, select_object, set_active_object, rm_ob
from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars


class RBDLAB_OT_physics_parents_reset(Operator):
    bl_idname = "rbdlab.phyisics_dswitch_dynamic_parent_reset"
    bl_label = "Reset"
    bl_description = "Reset"
    bl_options = {'REGISTER', 'UNDO'}


    def add_rbd_if_not_have(self, context:Context, org_ob:Object) -> None:
        if org_ob.rigid_body is None:
            set_active_object(context, org_ob)
            select_object(context, org_ob)
            bpy.ops.rigidbody.objects_add(type='ACTIVE')

    
    def restore_rbd_settings(self, org_ob:Object) -> None:
        # restauramos los settings de rbd que tuviera:
        if RBDLabNaming.DSWITCH_DPARENT_STORE_RBD_SETTINGS in org_ob:

            my_dict = org_ob[RBDLabNaming.DSWITCH_DPARENT_STORE_RBD_SETTINGS]

            for k, v in my_dict.items():
                setattr(org_ob.rigid_body, k, v)

            # eliminamos sus settings guardados
            del org_ob[RBDLabNaming.DSWITCH_DPARENT_STORE_RBD_SETTINGS]


    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)
        scn.frame_set(scn.frame_start)
        org_ob = rbdlab.physics.dswitch.dynamic_parent.select_original
        active_item = tcoll_list.active_item
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        deselect_all_objects(context)

        # A los chunks:
        have_handlers = False
        first_chunk = chunks[0]
        set_active_object(context, first_chunk)
        for ob in chunks:

            ob.select_set(True)

            if RBDLabNaming.HANDLER in ob:
                have_handlers = True

            # eliminamos sus keyframes de kinematic:
            dpath = "rigid_body.kinematic"
            remove_all_keyframes_in_action(context, ob, dpath)
            # ob.rigid_body.kinematic = False

            # si ya tiene el child of, se los eliminamos:
            prev_const = ob.constraints.get(RBDLabNaming.CHILD_OF)
            if prev_const:
                # eliminamos sus keyframes de sus child of enable:
                dpath = "constraints[\"" + RBDLabNaming.CHILD_OF + "\"].enabled"
                remove_all_keyframes_in_action(context, ob, dpath)
                ob.constraints.remove(prev_const)
            
        if first_chunk.rigid_body:
            bpy.ops.rigidbody.objects_remove()

        # Al original object:

        #---------------------------------------------------------------------------
        # Si existe la copia de seguridad de la animacion:
        #---------------------------------------------------------------------------
        # prev_action_name = RBDLabNaming.DSWITCH_DPARENT_ACTION
        # if prev_action_name in org_ob:

        #     # borramos todos sus keyframes al original:
        #     for fcurve in org_ob.animation_data.action.fcurves:
        #         org_ob.animation_data.action.fcurves.remove(fcurve)

        #     # restauramos la copia:
        #     prev_action = bpy.data.actions.get(org_ob[prev_action_name].name)
        #     if prev_action:
        #         org_ob.animation_data.action = prev_action
        #         del org_ob[prev_action_name]
        
        #---------------------------------------------------------------------------
        # Si existe la copia de seguridad del rigidbodie del original, lo restauro:
        #---------------------------------------------------------------------------
        # self.add_rbd_if_not_have(context, org_ob)
        # self.restore_rbd_settings(org_ob)

        #---------------------------------------------------------------------------
        # le quitamos el rigidbodie si lo tuviera:
        #---------------------------------------------------------------------------
        if org_ob.rigid_body:
            set_active_object(context, org_ob)
            bpy.ops.rigidbody.objects_remove()

        active_item.dswitch_at_frame = -1
    
        if active_item.enable_disable_rbd:
            active_item.enable_disable_rbd = False

        # if RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in org_ob:
        #     del org_ob[RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES]

        if have_handlers:
            if RBDLabNaming.HANDLER in ob:
                rm_ob(ob[RBDLabNaming.HANDLER])
            bpy.ops.rbdlab.rigidbody_add_handler()

        deselect_all_objects(context)
        return {'FINISHED'}
