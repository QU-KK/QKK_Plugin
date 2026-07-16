import bpy
from bpy.types import Operator
from ......Global.basics import select_object, deselect_all_objects
from ......addon.naming import RBDLabNaming


class RBDLAB_OT_select_passives(Operator):
    bl_idname = "rbdlab.set_passive_select"
    bl_label = "Select Passives"
    bl_description = "Select Passives"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        deselect_all_objects(context)
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and obj.visible_get():
                if RBDLabNaming.PASSIVE in obj:
                    select_object(context, obj)
                # if obj.rigid_body:
                    # if obj.rigid_body.type == 'PASSIVE' and RBDLabNaming.PASSIVE in obj and obj.name.lower() != "ground":

        return {'FINISHED'}
