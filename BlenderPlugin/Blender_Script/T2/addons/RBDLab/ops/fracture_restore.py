import bpy
from bpy.types import Operator


class RBDLAB_OT_scatter_restore(Operator):
    bl_idname = "rbdlab.scatter_restore"
    bl_label = "Scatter Restore"
    bl_description = "Restore the scatter system"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("Restore Scatter")
        rbdlab = context.scene.rbdlab
        rbdlab.current_using_cell_fracture = False
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False
        col = layout.column(align=True)
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")


class RBDLAB_OT_fracture_restore(Operator):
    bl_idname = "rbdlab.fracture_restore"
    bl_label = "Fracture Restore"
    bl_description = "Restore the fracture system"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("Restore Fracture")
        rbdlab = context.scene.rbdlab
        # if rbdlab.filtered_target_collection:
        #     tcollection = rbdlab.filtered_target_collection
        #     coll_name = tcollection.name
        #     if coll_name:
        #         if "fracture_applied" in tcollection:
        #             if rbdlab.filtered_target_collection["fracture_applied"] == 0:
        #                 rbdlab.filtered_target_collection["fracture_applied"] = 1
        #             rbdlab.working_in_inner_details = False
        rbdlab.working_in_inner_details = False
        rbdlab.current_using_cell_fracture = False
        # bpy.ops.rbdlab.scatter_end()

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False

        col = layout.column(align=True)
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")


class RBDLAB_OT_not_working_now_in_inner_details(Operator):
    bl_idname = "rbdlab.not_working_now_in_inner_details"
    bl_label = "Not Working Now in Inner Details"
    bl_description = "Not Working Now in Inner Details"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        rbdlab.working_in_inner_details = False
        self.report({'INFO'}, "Done!")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False

        col = layout.column(align=True)
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")
