from bpy.types import Operator
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_set_animated_keyframe(Operator):
    bl_idname = "rbdlab.set_anim_keyframe"
    bl_label = "Set Kinemattic keyframe"
    bl_description = "Set keyframe in to Kinematic attribute, from current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll = rbdlab.filtered_target_collection

        if tcoll is not None:
            tcoll_objs = tcoll.objects
            coll_name = tcoll.name

            valid_objects = []
            for obj in tcoll_objs:
                if obj.type == 'MESH' and obj.visible_get():
                    if obj.rigid_body and RBDLabNaming.RBD_SEL_KINEMATIC not in obj and "rbdlab_acetonized" not in obj:
                        valid_objects.append(obj)

            if not valid_objects:
                self.report({'WARNING'}, "Not Rigidbodie Objects in Target Collection!")
                return {'CANCELLED'}

            for obj in valid_objects:
                keyframe = context.scene.frame_current
                obj.rigid_body.kinematic = True
                obj.keyframe_insert(
                    data_path="rigid_body.kinematic",
                    frame=keyframe
                )
                obj.rigid_body.kinematic = False
                obj.keyframe_insert(
                    data_path="rigid_body.kinematic",
                    frame=keyframe+1
                )

            if "kinematic_keyframes_text" not in tcoll:
                tcoll["kinematic_keyframes_text"] = ""

            tcoll["kinematic_keyframes_text"] += " ##### In Frame: " + str(keyframe)

        return {'FINISHED'}
