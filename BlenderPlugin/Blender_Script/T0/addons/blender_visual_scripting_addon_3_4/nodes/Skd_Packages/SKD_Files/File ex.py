import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_File_ex(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_File_ex"
    bl_label = "File Exists"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File Name").subtype = "FILE_PATH"
        self.add_string_input("File Location").subtype = "DIR_PATH"
        self.add_boolean_output("File Exists")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def Exists_file_skd(filename,directory):

                    file_path = os.path.join(directory, filename)

                    if os.path.exists(file_path):
                        return True
                    else:
                        return False
                    """
        
        self.code = f"""ex_skd_{self.static_uid} = Exists_file_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"ex_skd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

