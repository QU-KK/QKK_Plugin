import bpy
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider


class UNITY_OT_convex(Operator, Collider):
    bl_label = "Convex"
    bl_idname = "unity.collider_convex"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Convex Collider.\n\nShift  •  Custom Convex Collider"""

    def invoke(self, context, event):
        unity = preferences().unity
        Collection.remove_collections()

        if event.shift:
            if len(context.selected_objects) > 1:
                self.add_collision(context, mat_name="Convex_Collider", color=unity.collider.convex)
                self.report({"INFO"}, "Added: Convex Collider")
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "Select two or more objects")
                return {"CANCELLED"}
        else:
            self.execute(context)

        return {"FINISHED"}

    def execute(self, context):
        unity = preferences().unity
        Collection.remove_collections()
        material = Material.get_material(name="Convex_Collider", use_nodes=False)

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name:
                if unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=collision_object_collection)

                convex_collision = self.create_convex(name=f"{object.name}_Collider", object=object)
                Object.parent_object(parent=object, child=convex_collision, copy_transform=False)
                self.collision_object_color(
                    object=convex_collision,
                    material=material,
                    color=unity.collider.convex,
                )

                if unity.object_collection:
                    Object.link_object(object=convex_collision, collection=collision_object_collection)
                else:
                    Object.link_object(object=convex_collision, collection=object.users_collection[0])

        return {"FINISHED"}


classes = (UNITY_OT_convex,)

register, unregister = bpy.utils.register_classes_factory(classes)
