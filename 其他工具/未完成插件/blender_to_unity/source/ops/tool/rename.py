import bpy
from bpy.types import Operator


class UNITY_OT_rename(Operator):
    """Rename selected object and their Collisions, Sockets and LODs"""

    bl_label = "Rename"
    bl_idname = "unity.rename"
    bl_options = {"REGISTER", "INTERNAL"}
    bl_property = "name"

    @classmethod
    def poll(cls, context):
        if context.object:
            return (
                context.object.type == "MESH"
                and "LOD" not in context.object.name.split("_")[-1]
                and "Collider" not in context.object.name.split("_")[-1]
            )

    name: bpy.props.StringProperty(name="Name")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", text="", icon="OBJECT_DATA")

    def invoke(self, context, event):
        self.name = context.object.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        context.object.name = self.name
        context.object.data.name = context.object.name

        for child in context.object.children:
            child.users_collection[0].name = f"{context.object.name}"

            if "LOD" in child.name.split("_")[-1]:
                child.name = f'{context.object.name}_{child.name.split("_")[-1]}'
                if child.type == "MESH":
                    child.data.name = child.name

            if "Collider" in child.name.split("_")[-1]:
                child.name = f'{context.object.name}_{child.name.split("_")[-1]}'
                if child.type == "MESH":
                    child.data.name = child.name

        self.report({"INFO"}, f"Renamed: {context.object.name}")
        return {"FINISHED"}


classes = (UNITY_OT_rename,)


register, unregister = bpy.utils.register_classes_factory(classes)
