import bpy
from bpy.types import Operator
from .....Global.basics import select_object, deselect_all_objects
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_select_sel_kinematics(Operator):
    bl_idname = "rbdlab.set_kinematic_select"
    bl_label = "Select Kinematics by selection"
    bl_description = "Select Kinematics by selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        deselect_all_objects(context)
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and obj.visible_get():
                if obj.rigid_body and RBDLabNaming.RBD_SEL_KINEMATIC in obj:
                    select_object(context, obj)

        return {'FINISHED'}
