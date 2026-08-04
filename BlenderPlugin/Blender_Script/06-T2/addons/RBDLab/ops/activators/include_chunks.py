from ...addon.naming import RBDLabNaming
from bpy.types import Operator


class ACTIVATORS_OT_include_chunks(Operator):
    bl_idname = "rbdlab.act_include_chunks"
    bl_label = "Exclude Chunks"
    bl_description = "Exclude selected chunks for process with Activators"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'ERROR'}, "In valid Target Collection!")
            return {'CANCELLED'}

        ac_layers_list = rbdlab.lists.ac_layers_list
        if ac_layers_list.is_void:
            return {'CANCELLED'}

        valid_objects = [ob for ob in context.selected_objects if ob.type == 'MESH']
        if not valid_objects:
            self.report({'WARNING'}, "To include, you must first have chunks selected!")
            return {'CANCELLED'}
        
        item = ac_layers_list.active
        if not item:
            return {'CANCELLED'}

        col_activators = [item.r_c, item.g_c, item.b_c, item.a_c]
        for ob in valid_objects:
            ob[RBDLabNaming.ACETONABLE] = True
            ob.color_stack.add_color(col_activators)
            ob.color = col_activators
        
        [item.add_ob(ob) for ob in valid_objects]

        return {'FINISHED'}
