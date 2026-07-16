from typing import List
from bpy.types import Operator, Object
from .base import BaseConstraintOperator


class CONST_OT_set_anim_brekeable(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_set_anim_brekeable"
    bl_label = "Set Brekeable keyframes"
    bl_description = "Set Brekeable anim, from current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):
        last_status = const_objects[0].rigid_body_constraint.use_breaking
        keyframe = context.scene.frame_current
        for const_ob in const_objects:
            const_ob.keyframe_insert(
                data_path="rigid_body_constraint.use_breaking",
                frame=keyframe
            )
            const_ob.rigid_body_constraint.use_breaking = not const_ob.rigid_body_constraint.use_breaking
            const_ob.keyframe_insert(
                data_path="rigid_body_constraint.use_breaking",
                frame=keyframe + 1
            )

        new_status = const_objects[0].rigid_body_constraint.use_breaking

        if last_status:
            last_status = "Enabled"
        else:
            last_status = "Disabled"

        if new_status:
            new_status = "Enabled"
        else:
            new_status = "Disabled"

        if "constraints_brekeable_keyframes_text" not in collection:
            collection["constraints_brekeable_keyframes_text"] = ""
        
        collection["constraints_brekeable_keyframes_text"] += " ##### In Frame: " + \
            str(keyframe) + " ##### From: " + last_status + " To: " + new_status
