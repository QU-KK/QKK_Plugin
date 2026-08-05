from bpy.types import Operator
from ...addon.naming import RBDLabNaming


class ACTIVATORS_OT_unset_activators(Operator):
    bl_idname = "rbdlab.act_unset"
    bl_label = "Unconvert/Restore Activators objects"
    bl_description = "Unconvert/Restore selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) == 0:
            return False
        return any([True for ob in context.selected_objects if RBDLabNaming.ACTIVATORS_OBJECTS in ob])
        # self.report({'WARNING'}, "First select the helpers you want to unset!")

    def execute(self, context):
        
        for obj in context.selected_objects:
            
            if RBDLabNaming.ACTIVATORS_OBJECTS not in obj:
                continue
            del obj[RBDLabNaming.ACTIVATORS_OBJECTS]
            
            if "activator" in obj:
                del obj["activator"]

            obj.display_type = 'SOLID'
            obj.hide_render = False

        return {'FINISHED'}
