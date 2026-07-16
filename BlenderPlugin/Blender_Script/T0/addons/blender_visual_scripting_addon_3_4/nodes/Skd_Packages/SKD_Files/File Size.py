import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_File_size(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_File_size"
    bl_label = "File Size"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File").subtype = "FILE_PATH"
        self.add_float_output("File Size")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def file_size_skd(file_path):
                    file_size_bytes = os.path.getsize(file_path)
                    # Convert bytes to kilobytes
                    file_size_kb = file_size_bytes / 1024
                    return file_size_kb
                    """
        
        self.code = f"""sizeskd_{self.static_uid} = file_size_skd({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"sizeskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

