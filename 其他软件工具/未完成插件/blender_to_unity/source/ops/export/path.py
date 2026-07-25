import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, IntProperty
from ....qbpy.blender import preferences
import os


class UNITY_OT_folder_add(Operator):
    """Add a folder"""

    bl_label = "Add Folder"
    bl_idname = "unity.folder_add"
    bl_options = {"REGISTER", "INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")

    type: EnumProperty(
        name="Type",
        items=(
            ("UNITY", "Export to Unity", ""),
            ("DISK", "Export to Disk", ""),
        ),
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        export = context.scene.unity.export

        if self.type == "UNITY":
            folder = export.unity_folders.add()
            export.unity_folder_index = len(export.unity_folders) - 1
        else:
            folder = export.disk_folders.add()
            export.disk_folder_index = len(export.disk_folders) - 1

        if os.path.basename(os.path.dirname(self.directory)):
            folder.name = os.path.basename(os.path.dirname(self.directory))
        else:
            folder.name = os.path.dirname(self.directory)

        folder.path = self.directory
        context.area.tag_redraw()
        return {"FINISHED"}


class UNITY_OT_folder_remove(Operator):
    bl_label = "Remove Folder"
    bl_idname = "unity.folder_remove"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, event):
        return """Remove the active folder.\n\nShift  •  Remove all the folders"""

    type: EnumProperty(
        name="Type",
        items=(
            ("UNITY", "Export to Unity", ""),
            ("DISK", "Export to Disk", ""),
        ),
    )

    index: IntProperty()

    def invoke(self, context, event):
        self.export = context.scene.unity.export

        if not event.shift:
            return self.unity(context) if self.type == "UNITY" else self.disk(context)

        if self.type == "UNITY":
            self.export.unity_folders.clear()
            self.export.unity_folder_index = 0
        else:
            self.export.disk_folders.clear()
            self.export.disk_folder_index = 0
        return {"FINISHED"}

    def unity(self, context):
        self.export.unity_folders.remove(self.index)
        self.export.unity_folder_index = min(
            max(0, self.export.unity_folder_index - 1),
            len(self.export.unity_folders) - 1,
        )
        return {"FINISHED"}

    def disk(self, context):
        self.export.disk_folders.remove(self.index)
        self.export.disk_folder_index = min(max(0, self.export.disk_folder_index - 1), len(self.export.disk_folders) - 1)
        return {"FINISHED"}


class UNITY_OT_folder_load(Operator):
    """Load sub folders"""

    bl_label = "Load Folders"
    bl_idname = "unity.folder_load"
    bl_options = {"REGISTER", "INTERNAL"}

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    type: EnumProperty(
        name="Type",
        items=(
            ("UNITY", "Export to Unity", ""),
            ("DISK", "Export to Disk", ""),
        ),
    )

    def invoke(self, context, event):
        self.export = context.scene.unity.export
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return self.unity(context) if self.type == "UNITY" else self.disk(context)

    def unity(self, context):
        if not self.directory:
            self.report({"WARNING"}, "Select a unity assets folder")
            return {"CANCELLED"}

        self.export.unity_folders.clear()
        self.export.unity_path_index = 0

        folder = self.export.unity_folders.add()
        self.export.unity_path_index = len(self.export.unity_folders) - 1
        if os.path.basename(os.path.dirname(self.directory)):
            folder.name = os.path.basename(os.path.dirname(self.directory))
        else:
            folder.name = os.path.dirname(self.directory)
        folder.path = self.directory

        for dir in os.scandir(self.directory):
            if dir.is_dir():
                folder = self.export.unity_folders.add()
                folder.name = os.path.basename(dir.path)
                folder.path = bpy.path.abspath(os.path.join(dir.path, ""))
                folder.use_subfolder = True

        context.area.tag_redraw()
        return {"FINISHED"}

    def disk(self, context):
        if not self.directory:
            self.report({"WARNING"}, "Select a disk assets folder")
            return {"CANCELLED"}

        self.export.disk_folders.clear()
        self.export.disk_folder_index = 0

        folder = self.export.disk_folders.add()
        self.export.disk_folder_index = len(self.export.disk_folders) - 1
        if os.path.basename(os.path.dirname(self.directory)):
            folder.name = os.path.basename(os.path.dirname(self.directory))
        else:
            folder.name = os.path.dirname(self.directory)
        folder.path = self.directory

        for dir in os.scandir(self.directory):
            if dir.is_dir():
                folder = self.export.disk_folders.add()
                folder.name = os.path.basename(dir.path)
                folder.path = bpy.path.abspath(os.path.join(dir.path, ""))
                folder.use_subfolder = True

        context.area.tag_redraw()
        return {"FINISHED"}


classes = (
    UNITY_OT_folder_add,
    UNITY_OT_folder_remove,
    UNITY_OT_folder_load,
)

register, unregister = bpy.utils.register_classes_factory(classes)
