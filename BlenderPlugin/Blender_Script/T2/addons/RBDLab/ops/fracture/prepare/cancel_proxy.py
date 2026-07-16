import bpy
from bpy.types import Operator
# from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import rm_ob, set_active_object


class RBDLAB_OT_Cancel_proxy(Operator):
    bl_idname = "rbdlab.prepare_cancel_proxy"
    bl_label = "Cancel Proxy"
    bl_description = "Cancel Proxy Object"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)
        
        if rbdlab.current_proxy_ob:
            
            ob = rbdlab.current_proxy_ob
            org_ob = bpy.data.objects.get(ob.name.replace("_proxy", ""))
            if not org_ob:
                self.report({'WARNING'}, "Could not obtain the object " + ob.name.replace("_proxy", ""))
                return {'CANCELLED'}
            
            rm_ob(ob)
            org_ob.hide_set(False)
            org_ob.hide_render = False

            bpy.ops.object.select_all(action='DESELECT')          
            org_ob.select_set(True)
            set_active_object(context, org_ob)

        return {'FINISHED'}
