import bpy
from bpy.types import Operator
# from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import set_active_object


class RBDLAB_OT_Prepare_Accept_proxy(Operator):
    bl_idname = "rbdlab.prepare_accept_proxy"
    bl_label = "Accept Proxy"
    bl_description = "Accept Proxy Object"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)
        
        if rbdlab.current_proxy_ob:

            ob = rbdlab.current_proxy_ob
            bpy.ops.object.select_all(action='DESELECT')          

            if ob:
                set_active_object(context, ob)
                ob.select_set(True)
                bpy.ops.object.convert(target='MESH')
                rbdlab.current_proxy_ob = None

        return {'FINISHED'}
