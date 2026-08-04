from typing import List
from bpy.props import StringProperty
from bpy.types import Operator, Object
from ...base import BaseConstraintOperator
# from .....Global.basics import ocultar_post_panel_settings
# from ....addon.naming import RBDLabNaming


class RBDLAB_OT_constswitch_rm(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_constswitch_rm"
    bl_label = "Animation Enable/Disable"
    bl_description = "Remove keyframes for Enable and Disable Constrinats"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")


    def remove_keyframes(self, dpath:str, objects:List[Object], frame_target):

        axis = 0 # X
    
        for ob in objects:
            if not ob.animation_data:
                continue

            if not ob.animation_data.action:
                continue

            if not ob.animation_data.action.fcurves:
                continue

            if not ob.animation_data.action.fcurves.find(dpath):
                continue

            action = ob.animation_data.action
    
            fcurve = action.fcurves.find(data_path=dpath, index=axis)
            if fcurve:

                # con esta manera de eliminar keyframes, parece que siempre 
                # tiene que existir un ultimo keyframe sin borrar en la curva:
                for p in fcurve.keyframe_points:
                    if int(p.co.x) == frame_target:
                        fcurve.keyframe_points.remove(p)
                    
                # si solo queda un solo keyframe en la curva la borramos por completo:
                if len(fcurve.keyframe_points) == 1:
                    action.fcurves.remove(fcurve)
                
                ob.rigid_body_constraint.enabled = True

    def action(self, context, rbdlab_const, active_group, const_coll, chunks: List[Object], const_objects: List[Object]):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            return {'CANCELLED'}
        
        # ocultar_post_panel_settings()

        constswitch_list = tcoll.rbdlab.constswitch_list
        
        target_id = self.id_to_rm
        item = constswitch_list.get_item_from_id(target_id)
        keyframes_to_rm = [kf.frame for kf in item.stored_keyframes]
        constrainst = [const.constraint for const in item.stored_constraints]

        # el data path:
        dpath = "rigid_body_constraint.enabled"
        
        # eliminamos los keyframes deseados:
        for kf in keyframes_to_rm:
            self.remove_keyframes(dpath, constrainst, kf)

        # restauro el enabled que tuviera:
        item_id = "rbdlab_constswitch_" + item.id_name
        for const in constrainst:
            if item_id in const:
                const.rigid_body_constraint.enabled = bool(const[item_id])
                del const[item_id]

        # para togglear necesito capturar el from_active_group antes de eliminar el item:
        active_group = rbdlab.constraints.get_group_by_idname(item.from_active_group)
        
        # lo quitamos de la lista:
        constswitch_list.remove_item(target_id)

        # toggleamos el enabled del active group para refrescar los estados a como deberían estar:
        if active_group:
            active_group.enabled = not active_group.enabled
            active_group.enabled = not active_group.enabled
   
        return {'FINISHED'}