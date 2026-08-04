import bpy
from bpy.types import Operator
from .....addon.naming import RBDLabNaming
from ...common_rigidbodies_functs import remove_fcurves_keyframes


class RBDLAB_OT_rm_all_animated_keyframes(Operator):
    bl_idname = "rbdlab.rigidbody_rm_all_anim_keyframes"
    bl_label = "Remove all Kinematic keyframes"
    bl_description = "Remove all keyframes in to Kineematic attribute"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll = rbdlab.filtered_target_collection

        if tcoll is not None:
            tcoll_objs = tcoll.objects

            valid_objects = [obj for obj in tcoll_objs if obj.type == 'MESH' and obj.visible_get()]

            if valid_objects:

                for obj in valid_objects:
                    if RBDLabNaming.PASSIVE not in obj and RBDLabNaming.RBD_SEL_KINEMATIC not in obj and "rbdlab_acetonized" not in obj:
                        if obj.rigid_body:
                            remove_fcurves_keyframes(obj, "rigid_body.kinematic")

                        rbdlab.kinematic = True
                        if hasattr(obj, "rigid_body"):
                            if hasattr(obj.rigid_body, "kinematic"):
                                obj.rigid_body.kinematic = rbdlab.kinematic

                tcoll["kinematic_keyframes_text"] = ""

        return {'FINISHED'}
