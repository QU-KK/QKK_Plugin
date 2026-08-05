from bpy.types import Operator
# from ......addon.naming import RBDLabNaming
from bpy.props import StringProperty
from ......Global.get_common_vars import get_common_vars


class RBDLAB_OT_physics_rbd_anim_dynamic_list_rm_item(Operator):
    bl_idname = "rbdlab.physics_rbd_anim_dynamic_list_rm_item"
    bl_label = "Reemove Item"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")

    def execute(self, context):

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)

        tcoll = tcoll_list.active

        # si estamos visualizando metal, lo cambio a chunks para poder trabajar:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        current_metal = metal_list.active

        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}

        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks or not tcoll:
            return {'CANCELLED'}
        
        dynamic_list = tcoll.rbdlab.dynamic_list
        target_id = self.id_to_rm

        item = dynamic_list.get_item_from_id(target_id)
        keyframes_to_rm = [kf.frame for kf in item.stored_keyframes]

        # si tenemos info guardada del item la borramos primero:
        if item.id in rbdlab:
            del rbdlab[item.id]

        # el data path:
        dpath="rigid_body.enabled"
        
        # eliminamos los keyframes deseados:
        for chunk in chunks:
            
            if not chunk.animation_data:
                continue

            if not chunk.animation_data.action:
                continue

            if not chunk.animation_data.action.fcurves:
                continue

            if not chunk.animation_data.action.fcurves.find(dpath):
                continue

            for kf in keyframes_to_rm:    

                chunk.keyframe_delete(dpath, frame=kf)
        
            chunk.rigid_body.enabled = True

        # lo quitamos de la lista:
        dynamic_list.remove_item(target_id)

        # restauro la visibilidad del metal:
        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state

        return {'FINISHED'}