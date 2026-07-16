from typing import List
from bpy.types import Operator, Object
from .base import BaseConstraintOperator


class CONST_OT_set_anim_brekeable_remove(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_set_anim_brekeable_remove"
    bl_label = "Remove Brekeable keyframes"
    bl_description = "Remove Brekeable anim"
    bl_options = {'REGISTER', 'UNDO'}

    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):
        # TODO: move breakable to rbdlab_const
        rbdlab = context.scene.rbdlab

        for const_ob in const_objects:
            # if not obj.rigid_body_constraint:
            #    continue
            if not const_ob.animation_data:
                continue
            ad = const_ob.animation_data
            if not hasattr(ad, "action"):
                continue
            action = ad.action
            if not hasattr(action, "fcurves"):
                continue
            for fc in action.fcurves:
                if fc.data_path == "rigid_body_constraint.use_breaking":
                    action.fcurves.remove(fc)

            const_ob.rigid_body_constraint.use_breaking = rbdlab.constraints.breakable

        collection["constraints_brekeable_keyframes_text"] = ""
