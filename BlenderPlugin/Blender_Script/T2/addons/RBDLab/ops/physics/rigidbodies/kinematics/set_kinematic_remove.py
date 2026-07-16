import bpy
from bpy.types import Operator
from .....Global.basics import deselect_all_objects
from .....addon.paths import RBDLabPreferences
from .....addon.naming import RBDLabNaming
from ...common_rigidbodies_functs import remove_fcurves_keyframes


class RBDLAB_OT_rm_sel_to_kinematics(Operator):
    bl_idname = "rbdlab.set_kinematic_remove"
    bl_label = "Remove Kinematics"
    bl_description = "Remove \"Selected to Kinematics\" to selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)

        if len(context.selected_objects) > 0:

            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get(
            ) and obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name]
            deselect_all_objects(context)

            if valid_objects:

                for obj in valid_objects:

                    if hasattr(obj, "rigid_body"):
                        if hasattr(obj.rigid_body, "kinematic"):
                            if RBDLabNaming.RBD_SEL_KINEMATIC in obj:

                                obj.rigid_body.kinematic = False
                                obj.rigid_body.use_deactivation = False

                                remove_fcurves_keyframes(obj, "rigid_body.use_deactivation")
                                remove_fcurves_keyframes(obj, "rigid_body.kinematic")

                                col_kinematics = list(addon_preferences.col_kinematics)
                                # print(col_kinematics)
                                obj.color_stack.rm_color(col_kinematics)
                                color = obj.color_stack.get_last_color()
                                if color:
                                    obj.color = color
                                if RBDLabNaming.RBD_SEL_KINEMATIC in obj:
                                    del obj[RBDLabNaming.RBD_SEL_KINEMATIC]

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
