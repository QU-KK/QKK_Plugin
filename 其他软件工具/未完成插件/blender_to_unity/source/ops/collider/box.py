import bpy
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider


class UNITY_OT_box(Operator, Collider):
    bl_label = "Box"
    bl_idname = "unity.collider_box"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Box Collider.\n\nShift  •  Custom collider to active object.\nCtrl    •  Bounding box collider for multiple selection.\nAlt      •  Single collider for multiple selection"""

    def invoke(self, context, event):
        self.unity = preferences().unity
        Collection.remove_collections()

        if event.shift:
            if len(context.selected_objects) > 1:
                self.add_collision(context, mat_name="Box_Collider", color=self.unity.collider.box)
                self.report({"INFO"}, "Added: Box Collider")
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "Select two or more objects")
                return {"CANCELLED"}
        elif event.alt:
            return self.create_single_collider(context)
        else:
            return self.create_collider(context, event)
        return {"FINISHED"}

    def create_collider(self, context, event):
        material = Material.get_material(name="Box_Collider", use_nodes=False)

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name:
                if self.unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=collision_object_collection)

                if event.ctrl:
                    box_collision = self.create_box(object=object, name=f"{object.name}_Collider")
                else:
                    box_collision = self.create_oriented_box(object=object, name=f"{object.name}_Collider")

                Object.parent_object(parent=object, child=box_collision, copy_transform=False)
                self.collision_object_color(
                    object=box_collision,
                    material=material,
                    color=self.unity.collider.box,
                )

                if self.unity.object_collection:
                    Object.link_object(object=box_collision, collection=collision_object_collection)
                else:
                    Object.link_object(object=box_collision, collection=object.users_collection[0])

        self.report({"INFO"}, "Added: Box Collider")
        return {"FINISHED"}

    def create_single_collider(self, context):
        material = Material.get_material(name="Box_Collider", use_nodes=False)

        if self.unity.object_collection:
            collision_object_collection = Collection.get_collection(collection=context.object.name)
            Collection.link_collection(collection=collision_object_collection)

        box_collision = self.create_single_box(context, name=f"{context.object.name}_Collider")
        Object.parent_object(parent=context.object, child=box_collision, copy_transform=True)
        self.collision_object_color(object=box_collision, material=material, color=self.unity.collider.box)

        if self.unity.object_collection:
            Object.link_object(object=box_collision, collection=collision_object_collection)
        else:
            Object.link_object(object=box_collision, collection=context.object.users_collection[0])

        self.report({"INFO"}, "Added: Box Collider")
        return {"FINISHED"}


classes = (UNITY_OT_box,)

register, unregister = bpy.utils.register_classes_factory(classes)
