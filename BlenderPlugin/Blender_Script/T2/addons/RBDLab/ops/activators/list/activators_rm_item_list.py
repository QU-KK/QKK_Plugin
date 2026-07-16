import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ....addon.naming import RBDLabNaming
from ....Global.functions import rm_ob


class ACTIVATORS_OT_activators_rm_item(Operator):
    bl_idname = "rbdlab.act_rm_item"
    bl_label = "Remove Item"
    bl_description = "Remove Item from list"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")


    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if not tcoll:
            return {'CANCELLED'}

        ac_layers_list = rbdlab.lists.ac_layers_list
    
        if ac_layers_list.is_void:
            return {'CANCELLED'}
        
        layers_item = ac_layers_list.active

        if not layers_item:
            return {'CANCELLED'}

        
        activators_list = layers_item.activators_list
        activator_item = activators_list.get_item_from_id(self.id_to_rm)
        
        if not activator_item:
            return {'CANCELLED'}
        
        activator = activator_item.activator

        # Elimino este Activator del listado guardado en los chunks:
        includes = ac_layers_list.get_all_includes
        for ob in includes:
            
            if RBDLabNaming.CHUNK_ACTIVATORS not in ob:
                continue

            if activator not in ob[RBDLabNaming.CHUNK_ACTIVATORS]:
                continue

            new_list = ob[RBDLabNaming.CHUNK_ACTIVATORS]
            new_list.remove(activator)
            ob[RBDLabNaming.CHUNK_ACTIVATORS] = new_list
        
        
        # Lo quitamos del listado:
        activators_list.remove_item(self.id_to_rm)
        
        if activator["activator"] == 'MESH':
    
            if RBDLabNaming.ACT_RECORD_TYPE in activator:
                del activator[RBDLabNaming.ACT_RECORD_TYPE]
    
            if "activator" in activator:
                del activator["activator"]
            
            if RBDLabNaming.ACT_RM_MESH in activator:
                org_ob = bpy.data.objects.get(activator[RBDLabNaming.ACT_RM_MESH])
                if org_ob:
                    org_ob.hide_set(False)
                del ob[RBDLabNaming.ACT_RM_MESH]
        
        rm_ob(activator)
    
        return {'FINISHED'}