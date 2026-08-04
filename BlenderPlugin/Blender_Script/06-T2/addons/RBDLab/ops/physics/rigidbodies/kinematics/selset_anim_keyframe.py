import bpy
from bpy.types import Operator
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_sel_set_animated_keyframe(Operator):
    bl_idname = "rbdlab.selset_anim_keyframe"
    bl_label = "Selected objects Set Kinemattic keyframe"
    bl_description = "Set keyframe in to Kinematic attribute to selected objects, from current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if len(context.selected_objects) > 0:
            valid_objects = []
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.visible_get():
                    if obj.rigid_body and RBDLabNaming.RBD_SEL_KINEMATIC in obj and "rbdlab_acetonized" not in obj:
                        valid_objects.append(obj)

            keyframe = bpy.context.scene.frame_current
            # deactivation
            for obj in valid_objects:
                obj.rigid_body.use_deactivation = True
                obj.keyframe_insert(
                    data_path="rigid_body.use_deactivation",
                    frame=keyframe
                )
                obj.rigid_body.use_deactivation = False
                obj.keyframe_insert(
                    data_path="rigid_body.use_deactivation",
                    frame=keyframe+1
                )
                # kinematic
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

            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    if "statics_kinematic_keyframes_text" not in bpy.data.collections[coll_name]:
                        bpy.data.collections[coll_name]["statics_kinematic_keyframes_text"] = ""

                    bpy.data.collections[coll_name]["statics_kinematic_keyframes_text"] += " ##### In Frame: " + str(
                        keyframe)
                    # bpy.data.collections[coll_name]["statics_kinematic_keyframes_text"] = rbdlab.keyframes_added_text

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
