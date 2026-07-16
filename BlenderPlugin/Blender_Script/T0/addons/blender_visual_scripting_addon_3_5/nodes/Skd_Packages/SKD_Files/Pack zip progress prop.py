import bpy
import threading
from pathlib import Path
import os
import zipfile
import queue

from ...base_node import SN_ScriptingBaseNode
from ...templates.PropertyReferenceNode import PropertyReferenceNode


class SN_SKD_PackAndMoveNodeThreadProgressProp(SN_ScriptingBaseNode, bpy.types.Node, PropertyReferenceNode):
    bl_idname = "SN_SKD_PackAndMoveNodeThreadProgressProp"
    bl_label = "Pack And Move Zip File Progress Property"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Source Path").subtype = "FILE_PATH"
        self.add_string_input("Destination Path").subtype = "DIR_PATH"
        self.add_string_input("Zip File Name")
        self.add_boolean_output("Confirmed Pack and Move")
        self.ref_ntree = self.node_tree

    def evaluate(self, context):
        prop_src = self.get_prop_source()
        # Check if the property source and property name exist
        if prop_src is None or self.prop_name not in prop_src.properties:
            return

        prop = prop_src.properties[self.prop_name]

        # Check if the property has the required attribute
        if not hasattr(prop, "python_name"):
            return

        if prop_src is None:
            return

        self.code_import = """
                            import threading
                            from pathlib import Path
                            import os
                            import zipfile
                            import queue
                            """

        self.code_imperative = f"""
                                execution_queue = queue.Queue()

                                def run_in_main_thread(function):
                                    execution_queue.put(function)

                                # Placeholder completion callback
                                def completion_callback(result):
                                    print(f"Completed: {{result}}")

                                def pack_zip_prop(source_path, destination_path, zip_file_name, completion_callback):
                                    bpy.context.scene.{prop.python_name} = 0.0

                                    class PackAndMoveThread(threading.Thread):
                                        def __init__(self, source_path, destination_path, zip_file_name, completion_callback):
                                            super().__init__()
                                            self.source_path = source_path
                                            self.destination_path = destination_path
                                            self.zip_file_name = zip_file_name
                                            self.completion_callback = completion_callback
                                            self.progress = 0
                                            self.completed = False
                                            self.error = None
                                            self.lock = threading.Lock()

                                        def run(self):
                                            try:
                                                # Remove ".zip" extension from zip_file_name if present
                                                self.zip_file_name = os.path.splitext(self.zip_file_name)[0]

                                                zip_file_path = os.path.join(self.destination_path, self.zip_file_name + ".zip")
                                                total_files = 0
                                                files_processed = 0

                                                # Count total files to calculate progress
                                                if os.path.isdir(self.source_path):
                                                    for _, _, filenames in os.walk(self.source_path):
                                                        total_files += len(filenames)

                                                with zipfile.ZipFile(zip_file_path, 'w') as zip_ref:
                                                    if os.path.isdir(self.source_path):
                                                        for foldername, subfolders, filenames in os.walk(self.source_path):
                                                            for filename in filenames:
                                                                filepath = os.path.join(foldername, filename)
                                                                arcname = os.path.relpath(filepath, self.source_path)
                                                                zip_ref.write(filepath, arcname)
                                                                files_processed += 1
                                                                with self.lock:
                                                                    self.progress = (files_processed / total_files) * 100
                                                    else:
                                                        zip_ref.write(self.source_path, os.path.basename(self.source_path))
                                                        with self.lock:
                                                            self.progress = 100

                                                run_in_main_thread(lambda: self.completion_callback(zip_file_path))

                                                with self.lock:
                                                    self.completed = True

                                            except Exception as e:
                                                with self.lock:
                                                    self.error = f"Error: {{str(e)}}"

                                    thread = PackAndMoveThread(source_path, destination_path, zip_file_name, completion_callback)
                                    thread.start()

                                    def update_progress():
                                        for area in bpy.context.screen.areas:
                                            if area.type == 'VIEW_3D':
                                                area.tag_redraw()
                                        with thread.lock:
                                            if thread.error:

                                                print(f"Error: {{thread.error}}")
                                                return None
                                            if not thread.completed:
                                                bpy.context.scene.{prop.python_name} = round(thread.progress, 2)
                                                return 0.1
                                            bpy.context.scene.{prop.python_name} = 100
                                            return None

                                    bpy.app.timers.register(update_progress)
                                """

        self.code = f"""zip_loc_threaderzz{self.static_uid} = pack_zip_prop({self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value}, completion_callback)"""
        self.outputs[1].python_value = f"zip_loc_threaderzz{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_reference_selection(layout)
        prop_src = self.get_prop_source()
        if self.prop_name and prop_src and self.prop_name in prop_src.properties:
            if prop_src.properties[self.prop_name].property_type == "Group":
                self.draw_warning(layout, "Can't return Group properties!")

        if self.prop_name is None:
            layout.label(text="Property not set!", icon="ERROR")