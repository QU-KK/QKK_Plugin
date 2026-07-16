import bpy
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider


class UNITY_OT_sphere(Operator, Collider):
    bl_label = "Sphere"
    bl_idname = "unity.collider_sphere"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Sphere Collider.\n\nShift  •  Custom collider to active object"""

    def invoke(self, context, event):
        self.unity = preferences().unity
        Collection.remove_collections()

        if not event.shift:
            return self.create_collider(context)
        if len(context.selected_objects) > 1:
            self.add_collision(context, mat_name="Sphere_Collider", color=self.unity.collider.sphere)
            self.report({"INFO"}, "Added: Sphere Collider")
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, "Select two or more objects")
            return {"CANCELLED"}
        return {"FINISHED"}

    def create_collider(self, context):
        material = Material.get_material(name="Sphere_Collider", use_nodes=False)

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name:
                if self.unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=collision_object_collection)

                sphere_collision = self.create_sphere(object=object, name=f"{object.name}_Collider")
                Object.parent_object(parent=object, child=sphere_collision, copy_transform=True)
                self.collision_object_color(
                    object=sphere_collision,
                    material=material,
                    color=self.unity.collider.sphere,
                )

                if self.unity.object_collection:
                    Object.link_object(object=sphere_collision, collection=collision_object_collection)
                else:
                    Object.link_object(object=sphere_collision, collection=object.users_collection[0])

        self.report({"INFO"}, "Added: Sphere Collider")
        return {"FINISHED"}


classes = (UNITY_OT_sphere,)

register, unregister = bpy.utils.register_classes_factory(classes)
