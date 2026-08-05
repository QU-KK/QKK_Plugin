import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming


class RBDLAB_OT_rbd_anim_add_substep_per_frame_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_add_substep_per_frame_keyframes"
    bl_label = "Add Substeps per frame Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        rigidbody_world = scn.rigidbody_world
        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        # current_frame = scn.frame_current
        current_frame = rbd_animation_porps.substeps_frame

        rigidbody_world.substeps_per_frame = rbd_animation_porps.substeps_from
        rigidbody_world.keyframe_insert(data_path="substeps_per_frame", frame=current_frame-1)

        rigidbody_world.substeps_per_frame = rbd_animation_porps.substeps_to
        rigidbody_world.keyframe_insert(data_path="substeps_per_frame", frame=current_frame)

        # bloqueo con el candado los keyframes del world:
        dpath="rigidbody_world.substeps_per_frame"
        scn_action = bpy.data.actions['SceneAction']
        [setattr(fcu, "lock", True) for fcu in scn_action.fcurves if fcu.data_path == dpath]

        rbd_animation_porps.substeps_animated = True
            
        return {'FINISHED'}
