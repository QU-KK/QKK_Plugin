import bpy
from bpy.types import Operator, Object, Context
from .....Global.basics import set_active_object
from .....addon.naming import RBDLabNaming
from .....Global.functions import remove_all_keyframes_in_action
from .....Global.get_common_vars import get_common_vars


class RBDLAB_OT_physics_parents_clear_bake_original(Operator):
    bl_idname = "rbdlab.phyisics_dswitch_clear_bake_original"
    bl_label = "Clear Bake Original"
    bl_description = "Clear Bake Original Object"
    bl_options = {'REGISTER', 'UNDO'}


    def add_rbd_if_not_have(self, context:Context, org_ob:Object) -> None:
        if org_ob.rigid_body is None:
            set_active_object(context, org_ob)
            org_ob.select_set(True)
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

        scn, rbdlab = get_common_vars(context, get_scn=True, get_rbdlab=True)
        org_ob = rbdlab.physics.dswitch.dynamic_parent.select_original

        if org_ob is None:
            self.report({'ERROR'}, "Invalid RigidBody Object!")
            return {'CANCELLED'}

        # scn.frame_set(scn.frame_start) # <- este ya lo hace el reset.

        # Primero hago un reset:
        bpy.ops.rbdlab.phyisics_dswitch_dynamic_parent_reset()
        
        # Al original:
        #---------------------------------------------------------------
        # eliminamos sus keyframes de kinematic:
        dpath = "location"
        remove_all_keyframes_in_action(context, org_ob, dpath)
        dpath = "rotation_euler"
        remove_all_keyframes_in_action(context, org_ob, dpath)
        
        # Si existe la copia de seguridad del rigidbodie del original, lo restauro:
        self.add_rbd_if_not_have(context, org_ob)      
        self.restore_rbd_settings(org_ob)

        # if not item_list.enable_disable_rbd:
        #     item_list.enable_disable_rbd = True
        
        if RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in org_ob:
            del org_ob[RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES]
        
        # A los chunks:
        #---------------------------------------------------------------
        bpy.ops.rbdlab.rigidbody_rm()

        return {'FINISHED'}
