from typing import List
import bpy
from bpy.types import Operator, Object
from ...addon.naming import RBDLabNaming


class CONSTRAINTS_OT_rm(Operator):
    bl_idname = "rbdlab.const_rm"
    bl_label = "Remove Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        tcoll_list = rbdlab.lists.target_coll_list
        chunks: List[Object] = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'WARNING'}, "Not valid chunks!")
            return {'CANCELLED'}

        const_objects = [child for chunk in chunks for child in chunk.children
                         if child.rigid_body_constraint and child.type == RBDLabNaming.CONST_TYPE]
        if const_objects:

            remove_object = bpy.data.objects.remove
            remove_chunk_from_constraint_groups = rbdlab.constraints.remove_chunk_from_constraint_groups
            while const_objects:
                remove_object(const_objects.pop(0))
            while chunks:
                remove_chunk_from_constraint_groups(chunks.pop(0))
            del const_objects

            if "enable_constraints_toggle" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["enable_constraints_toggle"]

            if "disable_constraints_toggle" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["disable_constraints_toggle"]

        scn.frame_set(scn.frame_start)
        return {'FINISHED'}
