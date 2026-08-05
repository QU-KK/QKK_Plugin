import bpy
from bpy.types import Operator
from bpy.props import StringProperty
# from ..addon.naming import RBDLabNaming
from ..Global.functions import set_active_object
# from ..Global.get_common_vars import get_common_vars


class RBDLAB_OT_Modifier_apply_mod(Operator):
    bl_idname = "rbdlab.modifiers_apply_mod"
    bl_label = "Apply Modifier"
    bl_description = "Apply Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    mod_to_apply: StringProperty(default="")

    def execute(self, context):
        
        for ob in context.selected_objects:
            
            if ob.type != 'MESH':
                continue
            
            target_mod = ob.modifiers.get(self.mod_to_apply)
            if not target_mod:
                continue

            # apply modifier:
            set_active_object(context, ob)
            bpy.ops.object.modifier_apply(modifier=self.mod_to_apply)


        return {'FINISHED'}
