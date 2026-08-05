import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_CreateFile(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CreateFile"
    bl_label = "Create File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File Name").subtype = "FILE_PATH"
        self.add_string_input("Directory").subtype = "DIR_PATH"
        self.add_boolean_output("File Created")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def create_file_skd(File, directory_path):
                    try:
                        file_path = os.path.join(directory_path, File)

                        with open(file_path, 'w') as f:
                            pass
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""createskd_{self.static_uid} = create_file_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"createskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

