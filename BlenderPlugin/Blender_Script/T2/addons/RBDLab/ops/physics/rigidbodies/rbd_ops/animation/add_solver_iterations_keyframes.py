import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming


class RBDLAB_OT_rbd_anim_add_solver_iterations_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_add_solver_iterations_keyframes"
    bl_label = "Add Solver Iterations Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab
        rigidbody_world = scn.rigidbody_world
        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        # current_frame = scn.frame_current
        current_frame = rbd_animation_porps.s_iterations_frame

        rigidbody_world.solver_iterations = rbd_animation_porps.s_iterations_from
        rigidbody_world.keyframe_insert(data_path="solver_iterations", frame=current_frame-1)

        rigidbody_world.solver_iterations = rbd_animation_porps.s_iterations_to
        rigidbody_world.keyframe_insert(data_path="solver_iterations", frame=current_frame)

        # bloqueo con el candado los keyframes del world:
        dpath="rigidbody_world.solver_iterations"
        scn_action = bpy.data.actions['SceneAction']
        [setattr(fcu, "lock", True) for fcu in scn_action.fcurves if fcu.data_path == dpath]

        rbd_animation_porps.s_iterations_animated = True

        return {'FINISHED'}
