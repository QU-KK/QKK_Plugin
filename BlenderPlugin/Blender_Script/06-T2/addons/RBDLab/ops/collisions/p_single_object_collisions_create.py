import bpy
from ...Global.basics import set_active_object, deselect_all_objects
# from ...addon.paths import RBDLabPreferences
from bpy.types import Operator


class RBDLAB_OT_p_single_object_collisions_create(Operator):
    bl_idname = "rbdlab.p_single_object_collisions_create"
    bl_label = "Single Object Particle collision"

    @classmethod
    def description(cls, _context, properties):
        return "Single Object Particle collision"

    def colors_acction(self, ob, col_p_collision):
        ob.color_stack.add_color(col_p_collision)
        ob.color = col_p_collision

    def execute(self, context):
        if context.selected_objects:
            valid_objects = [ob for ob in context.selected_objects if ob.type == 'MESH']
            if valid_objects:
                # addon_preferences = RBDLabPreferences.get_prefs(context)
                # col_p_collision = list(addon_preferences.col_p_collision)

                deselect_all_objects(context)

                for ob in valid_objects:
                    ob.select_set(True)
                    # self.colors_acction(ob, col_p_collision)

                if len(context.selected_objects):
                    set_active_object(context, context.selected_objects[0])
                    bpy.ops.object.modifier_add(type='COLLISION')

                for ob in valid_objects:
                    if "rbdlab_single_obj_p_collision" not in ob:
                        ob["rbdlab_single_obj_p_collision"] = True

            valid_objects = []
        else:
            self.report({'WARNING'}, "Select any object first!")
            return {'CANCELLED'}

        return {'FINISHED'}
