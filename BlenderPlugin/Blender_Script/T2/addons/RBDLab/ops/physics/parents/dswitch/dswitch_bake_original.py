import bpy
from bpy.types import Operator
from .....Global.basics import deselect_all_objects, select_object, set_active_object
from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars


class RBDLAB_OT_physics_parents_bake_original(Operator):
    bl_idname = "rbdlab.phyisics_dswitch_bake_original"
    bl_label = "Bake Original"
    bl_description = "Bake Original Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)
        
        org_ob = rbdlab.physics.dswitch.dynamic_parent.select_original

        # chequeo que no tengan rigidbodies los chunks:
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        have_rbd = next((True for chunk in chunks if chunk.rigid_body), False)
        if have_rbd:
            self.report({'ERROR'}, "Your chunks must not have rigidbodies!")
            return {'CANCELLED'}

        if org_ob is None:
            self.report({'ERROR'}, "Invalid RigidBody Object!")
            return {'CANCELLED'}   
        
        if RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in org_ob:
            self.report({'WARNING'}, org_ob.name + " Already Baked Object!")
            return {'CANCELLED'}

        if org_ob.type != 'MESH':
            self.report({'ERROR'}, "Invalid Type Object!")
            return {'CANCELLED'}

        if org_ob.hide_select:
            self.report({'WARNING'}, org_ob.name + " is not selectable!!")
            return {'CANCELLED'}
        
        # Si no tiene rigidbodies le aviso al usuario:
        if org_ob.rigid_body is None:
            # set_active_object(context, org_ob)
            # select_object(context, org_ob)
            # bpy.ops.rigidbody.objects_add(type='ACTIVE')
            self.report({'INFO'}, org_ob.name + " not have rigidbodies!!")
            return {'CANCELLED'}
        
        scn.frame_set(scn.frame_start)
        deselect_all_objects(context)
        select_object(context, org_ob)
        set_active_object(context, org_ob)
        org_ob[RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES] = True

        # si los chunks tuviera rigidbodies los desactivamos del target collection:
        item_list = tcoll_list.active_item
        if item_list.enable_disable_rbd:
            item_list.enable_disable_rbd = False

        # Guardo en el propio objeto, su información de rbd para luego poder restaurarlo con el cleare bake:
        org_ob[RBDLabNaming.DSWITCH_DPARENT_STORE_RBD_SETTINGS] = {
            "type": org_ob.rigid_body.type,
            "mass": org_ob.rigid_body.mass,
            "enabled": org_ob.rigid_body.enabled,
            "kinematic": org_ob.rigid_body.kinematic,
            "use_deactivation": org_ob.rigid_body.use_deactivation,
            "use_start_deactivated": org_ob.rigid_body.use_start_deactivated,
            "deactivate_linear_velocity": org_ob.rigid_body.deactivate_linear_velocity,
            "deactivate_angular_velocity": org_ob.rigid_body.deactivate_angular_velocity,
        }

        # Guardo su animación/action original para luego poder restaurarlo con el reset:
        # if org_ob.animation_data is not None:
        #     if org_ob.animation_data.action is not None:
        #         org_ob[RBDLabNaming.DSWITCH_DPARENT_ACTION] = org_ob.animation_data.action
        #         org_ob.animation_data.action = org_ob.animation_data.action.copy()  # guardo una copia que sera machacada por el bake

        bpy.ops.rigidbody.bake_to_keyframes('INVOKE_DEFAULT')

        return {'FINISHED'}
