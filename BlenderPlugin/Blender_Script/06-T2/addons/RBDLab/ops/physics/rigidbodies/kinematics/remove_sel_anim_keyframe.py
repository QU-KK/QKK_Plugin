import bpy
from bpy.types import Operator
from ...common_rigidbodies_functs import remove_fcurves_keyframes
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_rm_sel_animated_keyframes(Operator):
    bl_idname = "rbdlab.rigidbody_rm_sel_anim_keyframe"
    bl_label = "Remove selected Kinematic keyframes"
    bl_description = "Remove selected objects keyframes in to Kineematic attribute"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if len(context.selected_objects) > 0:
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.visible_get():
                    if obj.rigid_body and RBDLabNaming.RBD_SEL_KINEMATIC in obj and "rbdlab_acetonized" not in obj:
                        remove_fcurves_keyframes(obj, "rigid_body.use_deactivation")
                        remove_fcurves_keyframes(obj, "rigid_body.kinematic")
                        if hasattr(obj.rigid_body, "kinematic"):
                            obj.rigid_body.use_deactivation = True
                            obj.rigid_body.kinematic = True

            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    bpy.data.collections[coll_name]["statics_kinematic_keyframes_text"] = ""

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
