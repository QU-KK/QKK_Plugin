from ...addon.naming import RBDLabNaming
from bpy.types import Operator
from ...Global.get_common_vars import get_common_vars


class ACTIVATORS_OT_exclude_chunks(Operator):
    bl_idname = "rbdlab.act_exclude_chunks"
    bl_label = "Exclude Chunks"
    bl_description = "Exclude selected chunks for process with Activators"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        ac_layers_list = rbdlab.lists.ac_layers_list
        objects = ac_layers_list.get_current_includes

        if not objects:
            self.report({'WARNING'}, "No objects are included in this layer!")
            return {'CANCELLED'}

        valid_objects = [ob for ob in objects if ob.select_get()]
        if not valid_objects:
            self.report({'WARNING'}, "To exclude, you must first have included chunks selected!")
            return {'CANCELLED'}
        
        item = ac_layers_list.active
        color_to_rm = ac_layers_list.get_color_by_id(item.id_name)

        for ob in valid_objects:
            
            if RBDLabNaming.ACETONABLE in ob:
                del ob[RBDLabNaming.ACETONABLE]

            # borramos ob de stored_includes:
            item.remove_ob_by_name(ob)

            ob.color_stack.rm_color(color_to_rm)
            color = ob.color_stack.get_last_color()
            if color:
                ob.color = color

        return {'FINISHED'}
