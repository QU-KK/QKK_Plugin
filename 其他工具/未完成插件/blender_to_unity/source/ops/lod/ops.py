import bpy
from bpy.types import Operator
from bpy.props import IntProperty
from bl_operators.presets import AddPresetBase
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.collection import Collection


class UNITY_OT_lod_preset_add(AddPresetBase, Operator):
    """LOD Preset"""

    bl_label = "Preset"
    bl_idname = "unity.lod_preset_add"
    preset_menu = "UNITY_MT_lod_preset"
    preset_subdir = "Unity/lod"
    preset_defines = [
        "unity = bpy.context.scene.unity",
    ]
    preset_values = [
        "unity.lods",
    ]


class UNITY_OT_lod_add(Operator):
    """Add a LOD"""

    bl_label = "Add"
    bl_idname = "unity.lod_add"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        unity = context.scene.unity

        item = unity.lods.add()
        unity.lod_index = len(unity.lods) - 1
        return {"FINISHED"}


class UNITY_OT_lod_remove(Operator):
    bl_label = "Remove"
    bl_idname = "unity.lod_remove"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Remove the LOD.\n\nShift  •  Remove all the LODs"""

    index: IntProperty()

    def invoke(self, context, event):
        self.unity = context.scene.unity

        if not event.shift:
            self.unity.lods.remove(self.index)
            self.unity.lod_index = min(max(0, self.unity.lod_index - 1), len(self.unity.lods) - 1)
            return {"FINISHED"}

        self.unity.lods.clear()
        self.unity.lod_index = 0
        return {"FINISHED"}


class UNITY_OT_lod_create(Operator):
    bl_label = "Create"
    bl_idname = "unity.lod_create"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        for object in context.selected_objects:
            if object.type != "MESH":
                return False
            return "LOD" not in object.name.split("_")[-1] and "Collider" not in object.name.split("_")[-1]

    @classmethod
    def description(cls, context, event):
        return """Create LODs.\n\nShift             •  Offset LODs location.\nCtrl               •  Create cascade LODs.\nCtrl + Shift  •  Offset cascade LODs location"""

    def invoke(self, context, event):
        self.prefs = preferences()
        self.unity = context.scene.unity
        self.lod_offset = self.prefs.unity.lod.offset

        if event.ctrl:
            self.cascade_lod(context, event)
        else:
            for object in [
                obj
                for obj in context.selected_objects
                if obj.type == "MESH" and "LOD" not in obj.name.split("_")[-1] and "Collider" not in obj.name.split("_")[-1]
            ]:
                for child in object.children:
                    if "LOD" in child.name.split("_")[-1]:
                        if child.data == object.data:
                            bpy.data.objects.remove(child)
                        else:
                            bpy.data.meshes.remove(child.data)

            for object in [
                obj
                for obj in context.selected_objects
                if obj.type == "MESH" and "LOD" not in obj.name.split("_")[-1] and "Collider" not in obj.name.split("_")[-1]
            ]:
                if self.prefs.unity.object_collection:
                    self.lod_object_collection = Collection.get_collection(collection=object.name)
                    Collection.link_collection(collection=self.lod_object_collection)

                for i, lod in enumerate(self.unity.lods):
                    lod_object = bpy.data.objects.get(f"{object.name}_LOD{str(i + 1)}")
                    if not lod_object:
                        lod_object = bpy.data.objects.new(
                            name=f"{object.name}_LOD{str(i + 1)}",
                            object_data=object.data.copy(),
                        )
                        lod_object.data.name = f"{object.name}_LOD{str(i + 1)}"
                        Object.link_object(object=lod_object, collection=self.lod_object_collection)

                        if self.prefs.unity.object_collection:
                            Object.link_object(object=lod_object, collection=self.lod_object_collection)
                        else:
                            Object.link_object(object=lod_object, collection=object.users_collection[0])

                        Object.parent_object(parent=object, child=lod_object, copy_transform=False)

                    decimate = lod_object.modifiers.get(f"LOD{str(i + 1)}")
                    if not decimate:
                        decimate = lod_object.modifiers.new(name=f"LOD{str(i + 1)}", type="DECIMATE")
                    decimate.ratio = lod.ratio
                    decimate.show_render = False

                    if event.shift:
                        lod_object.location[0] = self.lod_offset
                        self.lod_offset += self.prefs.unity.lod.offset

                self.lod_offset = self.prefs.unity.lod.offset

            self.report({"INFO"}, "Created: LODs")

        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        return {"FINISHED"}

    def cascade_lod(self, context, event):
        for object in [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and "LOD" not in obj.name.split("_")[-1] and "Collider" not in obj.name.split("_")[-1]
        ]:
            for child in object.children:
                if "LOD" in child.name.split("_")[-1]:
                    if child.data == object.data:
                        bpy.data.objects.remove(child)
                    else:
                        bpy.data.meshes.remove(child.data)

        for object in [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and "LOD" not in obj.name.split("_")[-1] and "Collider" not in obj.name.split("_")[-1]
        ]:
            if object.type != "MESH" or "LOD" in object.name.split("_")[-1] or "Collider" in object.name.split("_")[-1]:
                continue

            if self.prefs.unity.object_collection:
                self.lod_object_collection = Collection.get_collection(collection=object.name)
                Collection.link_collection(collection=self.lod_object_collection)

            self.base_object = object

            for i, lod in enumerate(self.unity.lods):
                self.base_object = self.cascade(
                    context,
                    event,
                    parent=object,
                    object=self.base_object,
                    index=i,
                    lod=lod,
                )

            self.lod_offset = self.prefs.unity.lod.offset
            context.view_layer.objects.active = object

        self.report({"INFO"}, "Created: Cascade LODs")
        return {"FINISHED"}

    def cascade(self, context, event, parent, object, index, lod):
        lod_object = bpy.data.objects.new(name=f"{parent.name}_LOD{str(index + 1)}", object_data=object.data.copy())
        lod_object.data.name = f"{parent.name}_LOD{str(index + 1)}"

        if self.prefs.unity.object_collection:
            Object.link_object(object=lod_object, collection=self.lod_object_collection)
        else:
            Object.link_object(object=lod_object, collection=object.users_collection[0])
        Object.parent_object(parent=parent, child=lod_object, copy_transform=False)

        decimate = lod_object.modifiers.get(f"LOD{str(index + 1)}")
        if not decimate:
            decimate = lod_object.modifiers.new(name=f"LOD{str(index + 1)}", type="DECIMATE")

        decimate.ratio = lod.ratio
        decimate.show_render = False
        context.view_layer.objects.active = lod_object

        if event.shift and event.ctrl:
            lod_object.location[0] = self.lod_offset
            self.lod_offset += self.prefs.unity.lod.offset

        bpy.ops.object.modifier_apply(modifier=decimate.name)
        return lod_object


classes = (
    UNITY_OT_lod_preset_add,
    UNITY_OT_lod_add,
    UNITY_OT_lod_remove,
    UNITY_OT_lod_create,
)

register, unregister = bpy.utils.register_classes_factory(classes)
