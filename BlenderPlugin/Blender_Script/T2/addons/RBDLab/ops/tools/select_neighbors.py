import bpy
from bpy.types import Operator
# from ...addon.naming import RBDLabNaming


class RAND_OT_select_neighbors(Operator):
    bl_idname = "rbdlab.select_neighbors"
    bl_label = "Select Neighbors"
    bl_description = "Select Neighbors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'WARNING'}, "No valid chunks in Target Collection!")
            return {'CANCELLED'}

        valid_chunks = [chunk for chunk in chunks if chunk in context.selected_objects]
        bpy.ops.object.select_all(action='DESELECT')

        for chunk in valid_chunks:
            
            for neighbor in chunk.neighbor_chunks.chunks:
                neighbor.object.select_set(True)

        return {'FINISHED'}
