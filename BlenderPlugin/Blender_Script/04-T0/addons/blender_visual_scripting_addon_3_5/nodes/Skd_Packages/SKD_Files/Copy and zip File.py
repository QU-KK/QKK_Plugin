import bpy
import threading
import zipfile
import queue
import os
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_PackAndMoveNodeThread(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_PackAndMoveNodeThread"
    bl_label = "Thread Pack and Move Zip File"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Source Path").subtype = "FILE_PATH"
        self.add_string_input("Destination Path").subtype = "DIR_PATH"
        self.add_string_input("Zip File Name")
        self.add_boolean_output("Confirmed Pack and Move")

    def evaluate(self, context):
        self.code_import = """
            import bpy
            import threading
            import zipfile
            import queue
            import os
        """

        self.code_imperative = """
            execution_queue = queue.Queue()

            def run_in_main_thread(function):
                execution_queue.put(function)


            class PackAndMoveThread(threading.Thread):
                def __init__(self, source_path, destination_path, zip_file_name, completion_callback):
                    super().__init__()
                    self.source_path = source_path
                    self.destination_path = destination_path
                    self.zip_file_name = zip_file_name
                    self.completion_callback = completion_callback

                def run(self):
                    # Remove ".zip" extension from zip_file_name if present
                    self.zip_file_name = os.path.splitext(self.zip_file_name)[0]

                    zip_file_path = os.path.join(self.destination_path, self.zip_file_name + ".zip")
                    with zipfile.ZipFile(zip_file_path, 'w') as zip_ref:
                        if os.path.isdir(self.source_path):
                            for foldername, subfolders, filenames in os.walk(self.source_path):
                                for filename in filenames:
                                    filepath = os.path.join(foldername, filename)
                                    arcname = os.path.relpath(filepath, self.source_path)
                                    zip_ref.write(filepath, arcname)
                        else:
                            zip_ref.write(self.source_path, os.path.basename(self.source_path))

                    run_in_main_thread(lambda: self.completion_callback(zip_file_path))

            def pack_and_move(source_path, destination_path, zip_file_name, completion_callback):
                pack_thread = PackAndMoveThread(source_path, destination_path, zip_file_name, completion_callback)
                pack_thread.start()
                return True

            def completion_callback(zip_file_path):
                return True
        """

        self.code = f"""zip_loc_threader{self.static_uid} = pack_and_move({self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value}, completion_callback)"""
        self.outputs[1].python_value = f"zip_loc_threader{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
