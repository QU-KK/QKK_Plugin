import bpy
from bpy.types import Operator
from ......Global.basics import enter_object_mode, set_active_object
from ......Global.functions import set_shading_color
from ......addon.paths import RBDLabPreferences
from ......addon.naming import RBDLabNaming


class RBDLAB_OT_passive(Operator):
    bl_idname = "rbdlab.set_passive"
    bl_label = "Rigid Bodie Passive"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        addon_preferences = RBDLabPreferences.get_prefs(context)

        tcoll = rbdlab.filtered_target_collection

        if tcoll is not None:

            enter_object_mode(context)
            objects = []

            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.visible_get() and obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name:
                    objects.append(obj)
                else:
                    obj.select_set(False)

            if objects:
                set_active_object(context, objects[0])
                bpy.ops.rigidbody.objects_add(type='PASSIVE')

                # print("rbdlab.set_passive")

                for obj in objects:
                    # if "rbdlab_active" in obj:
                    #     del obj["rbdlab_active"]

                    col_passives = list(addon_preferences.col_passives)
                    obj.color_stack.add_color(col_passives)
                    obj.color = col_passives

                    obj[RBDLabNaming.PASSIVE] = True

            else:
                self.report({'WARNING'}, "First select chunks to make passive!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}

        set_shading_color(context)
        # deselect_all_objects(context)
        return {'FINISHED'}
