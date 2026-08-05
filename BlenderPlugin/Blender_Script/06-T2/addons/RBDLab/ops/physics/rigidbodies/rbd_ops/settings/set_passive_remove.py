import bpy
from bpy.types import Operator
from ......Global.basics import select_object, set_active_object, deselect_all_objects
from ......addon.paths import RBDLabPreferences
from ......addon.naming import RBDLabNaming


class RBDLAB_OT_rm_passives(Operator):
    bl_idname = "rbdlab.set_passive_remove"
    bl_label = "Remove Passives"
    bl_description = "Remove Passives"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)

        if len(context.selected_objects) > 0:

            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get(
            ) and obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name]
            deselect_all_objects(context)

            if valid_objects:

                for obj in valid_objects:
                    if not hasattr(obj, "rigid_body"):
                        continue
                    if not hasattr(obj.rigid_body, "type"):
                        continue

                    if obj.rigid_body.type == 'PASSIVE':
                        select_object(context, obj)

                        col_passives = list(addon_preferences.col_passives)
                        obj.color_stack.rm_color(col_passives)
                        color = obj.color_stack.get_last_color()
                        if color:
                            obj.color = color

                        if RBDLabNaming.PASSIVE in obj:
                            del obj[RBDLabNaming.PASSIVE]

                set_active_object(context, valid_objects[0])
                bpy.ops.rigidbody.objects_add(type='ACTIVE')

                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "No valid objects!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
