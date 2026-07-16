import bpy

from bpy.types import Operator
from ..Global.functions import (
    set_active_collection_to_master_coll,
    remove_collection_if_is_empty,
    hide_collection_in_viewport,
)
from ..Global.basics import enter_object_mode, select_object, set_active_object, deselect_all_objects
from ..addon.naming import RBDLabNaming


class CUSTOM_OT_debris(Operator):
    bl_idname = "rbdlab.customdebris"
    bl_label = "Custom Debris"
    bl_description = "Create a collection of custom debries from selected objects for later use with particle systems"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        valid_objects = []

        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH' and obj.visible_get():
                if RBDLabNaming.SUFIX_BBOX not in obj.name and RBDLabNaming.GROUND not in obj.name:
                    valid_objects.append(obj)

        objects = valid_objects
        if objects:
            custom_name_debris_collection = rbdlab.custom_name_debris_collection
            if custom_name_debris_collection:
                set_active_collection_to_master_coll(context)

                new_coll_target_name = custom_name_debris_collection + "_Custom_Debris"

                if new_coll_target_name not in bpy.data.collections:
                    new_coll_target = bpy.data.collections.new(new_coll_target_name)
                    rbdlab.root_collection.children.link(new_coll_target)

                padding = len(str(len(objects))) + 1
                enter_object_mode(context)

                for i, obj in enumerate(objects):
                    if obj.type == 'MESH' and obj.visible_get():
                        set_active_object(context, obj)
                        new_obj = obj.copy()
                        new_obj.data = obj.data.copy()
                        if "." in obj.name:
                            new_obj.name = obj.name.replace(".", "_") + "_custom_debri_" + str(i).zfill(padding)
                        else:
                            new_obj.name = obj.name + "_custom_debri_" + str(i).zfill(padding)

                        if new_obj.parent:
                            new_obj.parent = None

                        if new_obj.name not in bpy.data.collections[new_coll_target_name].objects:
                            bpy.data.collections[new_coll_target_name].objects.link(new_obj)
                            new_obj.hide_render = False
                            # new_obj.hide_set(False)

                        deselect_all_objects(context)
                        select_object(context, new_obj)
                        bpy.ops.transform.translate(value=(-0, -0, -50))

                        if new_obj.rigid_body:
                            bpy.ops.rigidbody.objects_remove()
                        if len(new_obj.particle_systems) > 0:
                            bpy.ops.object.particle_system_remove()

                deselect_all_objects(context)
                hide_collection_in_viewport(context, new_coll_target_name)
                remove_collection_if_is_empty(context, new_coll_target_name)
                rbdlab.debris_target_collection = bpy.data.collections[new_coll_target_name]
                self.report(
                    {'INFO'},
                    str(len(objects)) + " added in new " + new_coll_target_name + " Custom Collection Debris.")
            else:
                self.report({'WARNING'}, "Invalid name for new collection!!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Select firs some objects!")
            return {'CANCELLED'}

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        rbdlab = context.scene.rbdlab

        col = layout.column()
        col.label(text="The new name that the collection will have")
        col.prop(rbdlab, "custom_name_debris_collection", text="Name")


class CUSTOM_OT_view_debris(Operator):
    bl_idname = "rbdlab.view_customdebris"
    bl_label = "View Custom Debris"
    bl_description = "View Custom Debris"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pass
