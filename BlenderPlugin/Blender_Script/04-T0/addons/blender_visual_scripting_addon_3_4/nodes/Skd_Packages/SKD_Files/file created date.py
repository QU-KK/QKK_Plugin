import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_Created_date(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Created_date"
    bl_label = "Files Creation Dates"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File Path").subtype = "DIR_PATH"
        self.add_list_output("Files List")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def get_files_by_creation_time(folder_path):
                    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
                    files_with_time = [(f, os.path.getctime(os.path.join(folder_path, f))) for f in files]

                    # Sort files based on creation time (oldest to newest)
                    sorted_files = sorted(files_with_time, key=lambda x: x[1])

                    # Extract file names from the sorted list
                    sorted_file_names = [item[0] for item in sorted_files]

                    return sorted_file_names  
                    """
        
        self.code = f"""filedatesskd_{self.static_uid} = get_files_by_creation_time({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"filedatesskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'