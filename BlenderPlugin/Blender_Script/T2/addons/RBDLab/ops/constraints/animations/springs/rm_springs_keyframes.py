from typing import List
from bpy.props import StringProperty
from ...base import BaseConstraintOperator
# from .....addon.naming import RBDLabNaming
# from ..check_previous_keyframes import check_keyframes
# from .....Global.get_common_vars import get_common_vars
from bpy.types import Context, Operator, Object, Collection
from .....Global.animation import remove_keyframe_x


class SPRINGS_OT_rm_springs_keyframes(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_rm_springs_keyframes"
    bl_label = "Springs Animation"
    bl_description = "Remove keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")

    
    def action(self, context:Context, rbdlab_const, group, collection:Collection, chunks:List[Object], const_objects:List[Object]) -> set:
        
        rbdlab_const_active = rbdlab_const.group_active
        springs_list = rbdlab_const_active.springs_list

        item = springs_list.get_item_from_id(self.id_to_rm)
        if item:
            
            dpaths = springs_list.get_dpaths_from_id(item.id)

            constraints = [c.constraint for c in item.stored_constraints]
            frames = [f.frame for f in item.stored_keyframes]
            
            if constraints:
    
                for dpath in dpaths:

                    for frame in frames:
                        remove_keyframe_x(dpath=dpath, objects=constraints, frame_target=frame)
            

            # Lo quitamos del listado:
            springs_list.remove_item(item.id)

        return {'FINISHED'}
