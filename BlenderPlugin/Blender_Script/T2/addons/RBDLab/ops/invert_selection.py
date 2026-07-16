import bpy

from bpy.types import Operator
from ..Global.basics import select_object, deselect_object


class RBDLAB_OT_invert_selection(Operator):
    bl_idname = "rbdlab.invert_selection"
    bl_label = "Invert"
    bl_description = "Invert Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        coll_name = rbdlab.filtered_target_collection.name
        if not coll_name:
            self.report({'INFO'}, "Target Collection is Empty!")
            return {'FINISHED'}

        objects = context.selected_objects
        if not objects:
            self.report({'INFO'}, "No selection to invert!")
            return {'FINISHED'}

        for obj in bpy.data.collections[coll_name].objects:
            if obj.type == 'MESH' and obj.visible_get():
                if obj in objects:
                    deselect_object(obj)
                else:
                    select_object(context, obj)

        # rbdlab.chunks_selected = len(context.selected_objects)

        return {'FINISHED'}
