import bpy
from ...Global.basics import set_active_object, deselect_all_objects
# from ...addon.paths import RBDLabPreferences
from bpy.types import Operator


class RBDLAB_OT_p_single_object_collisions_remove(Operator):
    bl_idname = "rbdlab.p_single_object_collisions_remove"
    bl_label = "Single Object Remove Particle collision"

    @classmethod
    def description(cls, _context, properties):
        return "Single Object Remove Particle collision"

    def colors_acction(self, ob, col_p_collision):
        ob.color_stack.rm_color(col_p_collision)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color

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
                    bpy.ops.object.modifier_remove(modifier="Collision")

                for ob in valid_objects:
                    if "rbdlab_single_obj_p_collision" in ob:
                        del ob["rbdlab_single_obj_p_collision"]

            valid_objects = []
        else:
            self.report({'WARNING'}, "Select any object first!")
            return {'CANCELLED'}

        return {'FINISHED'}
