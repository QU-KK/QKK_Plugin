from bpy.types import Operator
from ...common.update_method import update_modifiers


class RBDLAB_OT_metalsoft_remesh_update_modifiers(Operator):
    bl_idname = "rbdlab.metalsoft_remesh_update_modifiers"
    bl_label = "Update Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, _context, properties):
        return "Update Modifiers"


    def execute(self, context):
        # rbdlab = get_common_vars(context, get_rbdlab=True)

        active_ob = context.active_object

        if active_ob.type != 'MESH':
            self.report({'WARNING'}, "Invalid Active Object!")
            return {'CANCELLED'}

        update_modifiers(active_ob, context.selected_objects)

        return {'FINISHED'}
    