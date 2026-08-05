import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming

class RBDLAB_OT_rbd_anim_rm_world_speed_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_rm_world_speed_keyframes"
    bl_label = "Remove World Speed Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        dpath="rigidbody_world.time_scale"
        scn_action = bpy.data.actions['SceneAction']
        for fcu in scn_action.fcurves:
            if fcu.data_path != dpath:
                continue
            scn_action.fcurves.remove(fcu)

        rbd_animation_porps.world_speed_animated = False
            
        return {'FINISHED'}
