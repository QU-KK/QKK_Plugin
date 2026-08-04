import bpy
import threading
import requests
from pathlib import Path
import os
import zipfile

from ...base_node import SN_ScriptingBaseNode
from ...templates.PropertyReferenceNode import PropertyReferenceNode

class SN_SKD_UnpackFileNodeThreadProp(SN_ScriptingBaseNode, bpy.types.Node, PropertyReferenceNode):
    bl_idname = "SN_SKD_UnpackFileNodeThreadProp"
    bl_label = "Thread Unpack Zip File Property"
    bl_width_default = 240
    node_color = "PROGRAM"


    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Zip File").subtype = "FILE_PATH"
        self.add_string_input("Save Path").subtype = "DIR_PATH"
        self.add_boolean_output("Completed")
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

                                def unpack_zip_prop(zip_file, save_dir):
                                    bpy.context.scene.{prop.python_name} = 0.0

                                    class UnpackZipThread(threading.Thread):
                                        def __init__(self, zip_file, save_dir):
                                            super().__init__()
                                            self.zip_file = Path(zip_file)
                                            self.save_dir = Path(save_dir)
                                            self.progress = 0
                                            self.completed = False
                                            self.error = None
                                            self.lock = threading.Lock()

                                        def run(self):
                                            try:
                                                if not self.zip_file.exists() or self.zip_file.suffix != ".zip":
                                                    raise FileNotFoundError("Invalid ZIP file path.")

                                                with zipfile.ZipFile(self.zip_file, 'r') as zip_ref:
                                                    total_files = len(zip_ref.infolist())
                                                    extracted_files = 0

                                                    for file_info in zip_ref.infolist():
                                                        zip_ref.extract(file_info, self.save_dir)
                                                        extracted_files += 1
                                                        with self.lock:
                                                            self.progress = (extracted_files / total_files) * 100

                                                with self.lock:
                                                    self.completed = True

                                            except Exception as e:
                                                with self.lock:
                                                    self.error = f"Error: {{str(e)}}"

                                    thread = UnpackZipThread(zip_file, save_dir)
                                    thread.start()

                                    def update_progress():
                                        for area in bpy.context.screen.areas:
                                            if area.type == 'VIEW_3D':
                                                area.tag_redraw()
                                        with thread.lock:
                                            if thread.error:
                                                bpy.context.scene.{prop.python_name} = thread.error
                                                print(f"Error: {{thread.error}}")
                                                return None
                                            if not thread.completed:
                                                bpy.context.scene.{prop.python_name} = thread.progress
                                                return 0.1
                                            bpy.context.scene.{prop.python_name} = 100
                                            return None

                                    bpy.app.timers.register(update_progress)
                                    """

        self.code = f"""unpack_zip_thread_prop{self.static_uid} = unpack_zip_prop({self.inputs[1].python_value}, {self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"unpack_zip_thread_prop{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_reference_selection(layout)
        prop_src = self.get_prop_source()
        if self.prop_name and prop_src and self.prop_name in prop_src.properties:
            if prop_src.properties[self.prop_name].property_type == "Group":
                self.draw_warning(layout, "Can't return Group properties!")

        if self.prop_name is None:
            layout.label(text="Property not set!", icon="ERROR")
