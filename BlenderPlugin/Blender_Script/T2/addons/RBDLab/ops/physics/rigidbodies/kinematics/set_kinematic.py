import bpy
from bpy.types import Operator
from .....Global.basics import select_object, set_active_object, deselect_all_objects
from .....Global.functions import set_shading_color
from .....addon.paths import RBDLabPreferences
from .....addon.naming import RBDLabNaming
from ...common_rigidbodies_functs import remove_fcurves_keyframes


class RBDLAB_OT_sel_to_kinematic(Operator):
    bl_idname = "rbdlab.set_kinematic"
    bl_label = "Selected to Kinematic and Deactived"
    bl_description = "Convert selected objects in Kinematic and Deactived"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)

        if len(context.selected_objects) > 0:

            valid_ojects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get(
            ) and obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name]

            if valid_ojects:

                deselect_all_objects(context)
                [select_object(context, obj) for obj in valid_ojects if hasattr(
                    obj, "rigid_body") and hasattr(obj.rigid_body, "type")]

                # si no tenían rigid bodies:
                if len(context.selected_objects) == 0:
                    [select_object(context, obj) for obj in valid_ojects]
                    bpy.ops.rigidbody.objects_add(type='ACTIVE')

                active_obj = valid_ojects[0]
                select_object(context, active_obj)
                set_active_object(context, active_obj)

                # print("rbdlab.set_kinematic")
                for obj in valid_ojects:
                    if hasattr(obj, "rigid_body"):
                        if hasattr(obj.rigid_body, "kinematic"):
                            remove_fcurves_keyframes(obj, "rigid_body.kinematic")
                            obj.rigid_body.kinematic = True
                            obj[RBDLabNaming.RBD_SEL_KINEMATIC] = True
                            obj.rigid_body.use_deactivation = True

                            col_kinematics = list(addon_preferences.col_kinematics)
                            obj.color_stack.add_color(col_kinematics)
                            obj.color = col_kinematics

                set_shading_color(context)
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "No valid objects!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
