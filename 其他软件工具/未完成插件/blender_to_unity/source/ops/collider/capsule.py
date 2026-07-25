import bpy
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider


class UNITY_OT_capsule(Operator, Collider):
    bl_label = "Capsule"
    bl_idname = "unity.collider_capsule"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Capsule Collider.\n\nShift  •  Custom collider to active object"""

    def invoke(self, context, event):
        self.unity = preferences().unity
        Collection.remove_collections()

        if event.shift:
            if len(context.selected_objects) > 1:
                self.add_collision(
                    context,
                    mat_name="Capsule_Collider",
                    color=self.unity.collider.capsule,
                )
                self.report({"INFO"}, "Added: Capsule Collider")
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "Select two or more objects")
                return {"CANCELLED"}
        else:
            return self.create_collider(context)
        return {"FINISHED"}

    def create_collider(self, context):
        material = Material.get_material(name="Capsule_Collider", use_nodes=False)

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name:
                if self.unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=collision_object_collection)

                capsule_collision = self.create_capsule(object=object, name=f"{object.name}_Collider")
                Object.parent_object(parent=object, child=capsule_collision, copy_transform=False)
                self.collision_object_color(
                    object=capsule_collision,
                    material=material,
                    color=self.unity.collider.capsule,
                )

                if self.unity.object_collection:
                    Object.link_object(object=capsule_collision, collection=collision_object_collection)
                else:
                    Object.link_object(object=capsule_collision, collection=object.users_collection[0])

        self.report({"INFO"}, "Added: Capsule Collider")
        return {"FINISHED"}


classes = (UNITY_OT_capsule,)

register, unregister = bpy.utils.register_classes_factory(classes)
