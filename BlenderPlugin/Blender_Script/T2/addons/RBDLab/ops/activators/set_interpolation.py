from bpy.types import Operator
from ...addon.naming import RBDLabNaming
from ...Global.functions import set_interpolation_curve_to


class ACTIVATORS_OT_set_interpolation(Operator):
    bl_idname = "rbdlab.act_set_interpolation"
    bl_label = "Set interpolation"
    bl_description = "Set the interpolation of the animation of your Activators"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ACTIVATORS_OBJECTS = [ob for ob in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in ob]

        interpolation = rbdlab.ui.interpolation_type
        for ob in ACTIVATORS_OBJECTS:
            set_interpolation_curve_to(ob, "location", interpolation)
            set_interpolation_curve_to(ob, "rotation_euler", interpolation)
            set_interpolation_curve_to(ob, "scale", interpolation)

        return {'FINISHED'}
