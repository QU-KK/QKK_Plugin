import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming

class RBDLAB_OT_rbd_anim_rm_substep_per_frame_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_rm_substep_per_frame_keyframes"
    bl_label = "Remove Substeps per frame Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        dpath="rigidbody_world.substeps_per_frame"
        scn_action = bpy.data.actions['SceneAction']
        for fcu in scn_action.fcurves:
            if fcu.data_path != dpath:
                continue
            scn_action.fcurves.remove(fcu)

        rbd_animation_porps.substeps_animated = False
            
        return {'FINISHED'}
