import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_RenameFile(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_RenameFile"
    bl_label = "Rename File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File").subtype = "FILE_PATH"
        self.add_string_input("New Name").subtype = "FILE_PATH"
        self.add_boolean_output("File Renamed")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def rename_file_skd(File, new_file_name):
                    try:
                        new_file_name = os.path.join(os.path.dirname(File), new_file_name)
                        os.rename(File, new_file_name)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""renameskd_{self.static_uid} = rename_file_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"renameskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

