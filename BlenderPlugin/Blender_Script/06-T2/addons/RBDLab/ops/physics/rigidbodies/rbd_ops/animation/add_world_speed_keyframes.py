import bpy
from bpy.types import Operator
# from ......addon.naming import RBDLabNaming


class RBDLAB_OT_rbd_anim_add_world_speed_keyframes(Operator):
    bl_idname = "rbdlab.rbd_anim_add_world_speed_keyframes"
    bl_label = "Add World speed Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        rigidbody_world = scn.rigidbody_world
        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        # current_frame = scn.frame_current
        current_frame = rbd_animation_porps.world_speed_frame

        rigidbody_world.time_scale = rbd_animation_porps.world_speed_from
        rigidbody_world.keyframe_insert(data_path="time_scale", frame=current_frame-1)

        rigidbody_world.time_scale = rbd_animation_porps.world_speed_to
        rigidbody_world.keyframe_insert(data_path="time_scale", frame=current_frame)

        # bloqueo con el candado los keyframes del world:
        dpath="rigidbody_world.time_scale"
        scn_action = bpy.data.actions['SceneAction']
        [setattr(fcu, "lock", True) for fcu in scn_action.fcurves if fcu.data_path == dpath]

        rbd_animation_porps.world_speed_animated = True
            
        return {'FINISHED'}
