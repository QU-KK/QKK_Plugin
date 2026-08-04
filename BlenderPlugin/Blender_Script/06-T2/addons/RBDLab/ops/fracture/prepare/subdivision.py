import bpy
from bpy.types import Operator
from ....Global.basics import select_object, set_active_object, deselect_all_objects
from ....Global.get_common_vars import get_common_vars


class RBDLAB_OT_surface(Operator):
    bl_idname = "rbdlab.paint_tools_apply_subdivision"
    bl_label = "Apply Subdivision modifier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)
        
        objects = context.selected_objects
        if objects:
            deselect_all_objects(context)
            for obj in objects:
                select_object(context, obj)
                set_active_object(context, obj)
                bpy.ops.object.modifier_apply(modifier="Subdivision")
                obj.show_wire = False
                rbdlab.subdivision_level = 0

        return {'FINISHED'}
