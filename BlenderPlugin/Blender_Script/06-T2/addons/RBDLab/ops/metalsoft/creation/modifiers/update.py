from bpy.types import Operator
from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars
from ...common.update_method import update_modifiers


class RBDLAB_OT_metal_update_modifiers(Operator):
    bl_idname = "rbdlab.metalsoft_creation_update_modifiers"
    bl_label = "Update Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, _context, properties):
        return "Update Modifiers"


    def execute(self, context):
        rbdlab = get_common_vars(context, get_rbdlab=True)
        tcoll_item = rbdlab.lists.target_coll_list.active_item
        metal_item = tcoll_item.metal_list.active
        modifier_list = metal_item.modifiers
        modifiers_names = modifier_list.get_all_mod_names

        all_obs = modifier_list.get_all_objects
        first_ob = modifier_list.get_first_object
        
        # le quitamos el primero:
        all_obs.remove(first_ob)

        # los modifiers principales de arriba, no me interesa updatearles nada:
        blacklist = (RBDLabNaming.DISPLACE, RBDLabNaming.SURFACE_DEFORM, RBDLabNaming.ACT_CANVAS_MOD)

        # Para el resto de los objetos:
        update_modifiers(first_ob, all_obs, blacklist, modifiers_names)
        

        return {'FINISHED'}