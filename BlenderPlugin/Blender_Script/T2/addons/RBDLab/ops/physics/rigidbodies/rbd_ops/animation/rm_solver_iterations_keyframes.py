import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming

class RBDLAB_OT_rbd_anim_rm_solver_iterations_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_rm_solver_iterations_keyframes"
    bl_label = "Remove Solver Iterations Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        dpath="rigidbody_world.solver_iterations"
        scn_action = bpy.data.actions['SceneAction']
        for fcu in scn_action.fcurves:
            if fcu.data_path != dpath:
                continue
            scn_action.fcurves.remove(fcu)

        rbd_animation_porps.s_iterations_animated = False
            
        return {'FINISHED'}
