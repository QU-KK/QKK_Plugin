import bpy
from bpy.types import Operator
from bpy.props import IntProperty
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider


class UNITY_OT_cylinder(Operator, Collider):
    bl_label = "Cylinder"
    bl_idname = "unity.collider_cylinder"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Cylinder Collider"""

    segments: IntProperty(
        name="Segments",
        description="Number of segments",
        min=8,
        max=16,
        default=8,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "segments")

    def execute(self, context):
        unity = preferences().unity
        Collection.remove_collections()
        material = Material.get_material(name="Convex_Collider", use_nodes=False)

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name:
                if unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=collision_object_collection)

                cylinder_collision = self.create_cylinder(
                    object=object,
                    name=f"{object.name}_Collider",
                    segments=self.segments,
                )
                Object.parent_object(parent=object, child=cylinder_collision, copy_transform=False)
                self.collision_object_color(
                    object=cylinder_collision,
                    material=material,
                    color=unity.collider.convex,
                )

                if unity.object_collection:
                    Object.link_object(
                        object=cylinder_collision,
                        collection=collision_object_collection,
                    )
                else:
                    Object.link_object(object=cylinder_collision, collection=object.users_collection[0])

        self.report({"INFO"}, "Added: Cylinder Collider")
        return {"FINISHED"}


classes = (UNITY_OT_cylinder,)

register, unregister = bpy.utils.register_classes_factory(classes)
