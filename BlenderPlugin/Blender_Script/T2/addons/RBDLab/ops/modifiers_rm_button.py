from bpy.types import Operator
from bpy.props import StringProperty


class RBDLAB_OT_Modifiers_rm_button(Operator):
    bl_idname = "rbdlab.modifiers_rm_button"
    bl_label = "Remove Modifier"
    bl_description = "Remove Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    mod_to_rm: StringProperty(default="")


    def execute(self, context):

        for ob in context.selected_objects:
            
            if ob.type != 'MESH':
                continue
            
            target_mod = ob.modifiers.get(self.mod_to_rm)
            if not target_mod:
                continue

            # rm modifier:
            ob.modifiers.remove(target_mod)

        return {'FINISHED'}
