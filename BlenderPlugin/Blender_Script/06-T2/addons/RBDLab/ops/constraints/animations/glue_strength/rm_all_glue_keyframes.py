import bpy
from typing import List
from bpy.props import StringProperty
from bpy.types import Operator, Object
from ...base import BaseConstraintOperator
# from .....addon.naming import RBDLabNaming
from .....Global.animation import remove_keyframe_x
from .....Global.get_common_vars import get_common_vars


class GLUE_OT_rm_all_glue_keyframes(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_rm_all_glue_keyframes"
    bl_label = "Remove all Glue keyframes"
    bl_description = "Remove all keyframes in to Glue attribute"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")


    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):
        
        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, tcoll_list=True)
        
        tcoll = tcoll_list.active

        if not tcoll:
            return {'CANCELLED'}

        rbdlab_const = rbdlab.constraints
        rbdlab_const_active = rbdlab_const.get_active_group
        glue_strength_list = rbdlab_const_active.glue_strength_list
        
        target_id = self.id_to_rm
        item = glue_strength_list.get_item_from_id(target_id)
        keyframes_to_rm = [kf.frame for kf in item.stored_keyframes]
        constrainst = [const.constraint for const in item.stored_constraints]

        dpath = "rigid_body_constraint.breaking_threshold"

        short_id = "rbdlab_glue_" + self.id_to_rm[:6]

        # eliminamos los keyframes deseados:
        for kf in keyframes_to_rm:

            conts_without_kf = remove_keyframe_x(dpath, constrainst, kf)

            # solo para los que se le borrarón los keyfrmaes
            for const in conts_without_kf:
                const.rigid_body_constraint.enabled = True

        # lo quitamos de la lista:
        glue_strength_list.remove_item(target_id)

        # bpy.ops.rbdlab.const_update()

        for const in constrainst:
            if short_id in const:
                const.rigid_body_constraint.breaking_threshold = float(const[short_id])
                del const[short_id]
        
        return {'FINISHED'}
