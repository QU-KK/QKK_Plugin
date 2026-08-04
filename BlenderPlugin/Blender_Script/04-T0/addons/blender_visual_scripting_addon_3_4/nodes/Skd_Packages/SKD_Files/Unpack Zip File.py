import bpy
import threading
import zipfile
import queue
import os
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_UnpackFileNodeThread(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_UnpackFileNodeThread"
    bl_label = "Thread unpack Zip File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Zip File").subtype = "FILE_PATH"
        self.add_string_input("Save Path").subtype = "DIR_PATH"
        self.add_boolean_output("Confirmed Download")
        
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


                class UnpackThread(threading.Thread):
                    def __init__(self, zip_path, extract_path, completion_callback, label_update_callback):
                        super().__init__()
                        self.zip_path = zip_path
                        self.extract_path = extract_path
                        self.completion_callback = completion_callback
                        self.label_update_callback = label_update_callback
                        self.total_bytes = 0
                        self.extracted_bytes = 0

                    def run(self):
                        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                            self.total_bytes = sum(info.file_size for info in zip_ref.infolist())

                            for entry in zip_ref.namelist():
                                zip_ref.extract(entry, self.extract_path)
                                self.extracted_bytes += os.path.getsize(os.path.join(self.extract_path, entry))
                                progress = self.extracted_bytes / self.total_bytes if self.total_bytes > 0 else 0

                                # Update the label in the UI in the main thread
                                run_in_main_thread(lambda: self.label_update_callback(progress))

                            # Call the completion callback in the main thread
                            run_in_main_thread(self.completion_callback)

                def unpack_zip(zip_path, extract_path, completion_callback, label_update_callback):
                    unpack_thread = UnpackThread(zip_path, extract_path, completion_callback, label_update_callback)
                    unpack_thread.start()
                    return True

                label_variable = 0

                def label_update_callback(progress):
                    # Set the label_variable for UI update
                    label_variable = int(progress * 100)
                    

                def completion_callback():
                    # Return True if needed
                    return True
                    """
        
        self.code = f"""zip_loc_th{self.static_uid} = unpack_zip({self.inputs[1].python_value},{self.inputs[2].python_value},  completion_callback, label_update_callback )"""
        self.outputs[1].python_value = f"zip_loc_th{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
