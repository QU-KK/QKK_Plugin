import bpy
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.collection import Collection
from ....qbpy.property import Property
from ...utils.export import Export
import os
import subprocess
import threading
import json
import queue
import time
from contextlib import suppress
from .... import __package__ as package


class UNITY_OT_export_fbx(Operator):
    """Export FBX"""

    bl_label = "Export"
    bl_idname = "unity.export_fbx"
    bl_options = {"REGISTER", "INTERNAL"}

    exported = queue.Queue()
    reports = queue.Queue()
    start_time = 0

    @classmethod
    def poll(cls, context):
        return cls.is_export_possible(context)

    @classmethod
    def description(cls, context, properties):
        return cls.get_description(context)

    @classmethod
    def get_description(cls, context):
        export = context.scene.unity.export
        if export.selection_type == "OBJECT" and not context.selected_objects:
            return "Select object(s)"
        elif export.selection_type == "COLLECTION" and not Collection.selected_collections():
            return "Select collection(s)"

    @classmethod
    def is_export_possible(cls, context):
        export = context.scene.unity.export
        if not cls.is_selection_type_valid(context, export):
            return False

        return cls.is_export_type_valid(export)

    @classmethod
    def is_selection_type_valid(cls, context, export):
        if export.selection_type == "OBJECT" and not context.selected_objects:
            return False
        elif export.selection_type == "COLLECTION" and not Collection.selected_collections():
            return False
        return True

    @classmethod
    def is_export_type_valid(cls, export):
        if export.type == "BOTH":
            return cls.is_both_export_possible(export)
        elif export.type == "DISK":
            return cls.is_disk_export_possible(export)
        elif export.type == "UNITY":
            return cls.is_unity_export_possible(export)

    @classmethod
    def is_both_export_possible(cls, export):
        return cls.is_folder_path_valid(export.unity_folders, export.unity_folder_index) and cls.is_folder_path_valid(
            export.disk_folders, export.disk_folder_index
        )

    @classmethod
    def is_disk_export_possible(cls, export):
        return cls.is_folder_path_valid(export.disk_folders, export.disk_folder_index)

    @classmethod
    def is_unity_export_possible(cls, export):
        return cls.is_folder_path_valid(export.unity_folders, export.unity_folder_index)

    @classmethod
    def is_folder_path_valid(cls, folders, folder_index):
        if folders:
            folder = folders[folder_index]
            if folder.path:
                return True
        return False

    def handle_export(self, process: subprocess.Popen, exported: queue.Queue, reports: queue.Queue):
        while process.poll() is None:
            for line in process.stdout:
                if "UNITY: Exported" in line:
                    exported.put(1)
                elif "UNITY:REPORT" in line:
                    _, _, report_type, *text = line.split(":")
                    reports.put(({report_type}, ":".join(text).strip()))
                elif "UNITY:TOTAL" in line:
                    _, _, total_exports_str, *_ = line.split(":")
                    self.total_exports = int(total_exports_str)
                # else:
                #     print(line)  # DEBUG print lines without useful data

        outs, errs = process.communicate()
        count = 0
        for line in outs.splitlines():
            if "UNITY: Exported" in line:
                count += 1
            elif "UNITY:REPORT" in line:
                _, _, report_type, *text = line.split(":")
                reports.put(({report_type}, ":".join(text).strip()))
            elif "UNITY:TOTAL" in line:
                _, _, total_exports_str, *_ = line.split(":")
                self.total_exports = int(total_exports_str)
            # else:
            #     print(line)  # DEBUG print lines without useful data
        if errs:
            print(errs)
        exported.put(count)

    def invoke(self, context, event):
        fbx_settings = preferences().unity.fbx
        self.export = context.scene.unity.export
        collection_name = []

        if self.export.selection_type == "OBJECT":
            if not context.selected_objects:
                self.report({"WARNING"}, "Select object(s) to export")
                return {"CANCELLED"}
        elif self.export.selection_type == "COLLECTION":
            if not Collection.selected_collections():
                self.report({"WARNING"}, "Select collection(s) to export")
                return {"CANCELLED"}

            collection_name = Collection.selected_collections(name_only=True)
            selected_objects = []

            for collection in Collection.selected_collections():
                selected_objects.extend(object for object in collection.objects if "LOD" not in object.name and "Collider" not in object.name)
                if self.export.use_sub_collection:
                    for collection in collection.children_recursive:
                        selected_objects.extend(object for object in collection.objects if "LOD" not in object.name and "Collider" not in object.name)

            if not selected_objects:
                self.report({"WARNING"}, "Object(s) not found in selected collection(s)")
                return {"CANCELLED"}

        UNITY_OT_export_fbx.start_time = time.time()
        self.finished_exports = 0
        self.total_exports = 1
        self.export.progress = 0
        self.temp_blend_path = os.path.join(bpy.app.tempdir, "unity_export.blend")
        bpy.ops.wm.save_as_mainfile(filepath=self.temp_blend_path, compress=True, copy=True)
        fbx_dict = Property.property_to_python(fbx_settings)
        properties_string = json.dumps(fbx_dict)
        collection_string = json.dumps(collection_name)
        expression = (
            f"import bpy;bpy.ops.unity.background_export_fbx('INVOKE_DEFAULT', properties='{properties_string}', collections='{collection_string}')"
        )
        self.process = subprocess.Popen(
            [
                bpy.app.binary_path,
                "--factory-startup",
                "-b",
                self.temp_blend_path,
                "--addons",
                package,
                "--python-expr",
                expression,
            ],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )
        self.thread = threading.Thread(
            target=self.handle_export,
            args=(self.process, self.exported, self.reports),
            daemon=True,
        )
        self.thread.start()

        context.window_manager.modal_handler_add(self)
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        while not self.exported.empty():
            try:
                self.finished_exports += self.exported.get()
            except queue.Empty as err:
                print(err)
                continue

        while not self.reports.empty():
            try:
                self.report(*self.reports.get())
            except queue.Empty as err:
                print(err)
                continue

        if self.total_exports == 0:
            self.clear(context, self.export)
            return {"CANCELLED"}

        if self.thread.is_alive() or not self.exported.empty():
            self.export.progress = int(self.finished_exports / self.total_exports * 100)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        self.clear(context, self.export)
        context.area.tag_redraw()
        return {"FINISHED"}

    def clear(self, context, export):
        export.progress = -1
        os.remove(self.temp_blend_path)
        self.process.kill()
        self.thread.join()
        while self.thread.is_alive():
            self.thread.join()
        self.exported.queue.clear()
        self.reports.queue.clear()

        with suppress(AttributeError):
            context.window_manager.event_timer_remove(self.timer)


class UNITY_OT_export_fbx_settings(Operator):
    """Export FBX Settings"""

    bl_label = "FBX Settings"
    bl_idname = "unity.fbx_settings"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        bpy.ops.preferences.addon_show(module=package)
        unity = preferences()
        unity.prefs_tabs = "EXPORT"
        unity.fbx_settings = True
        return {"FINISHED"}


classes = (
    UNITY_OT_export_fbx,
    UNITY_OT_export_fbx_settings,
)


register, unregister = bpy.utils.register_classes_factory(classes)
