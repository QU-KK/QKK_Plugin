import bpy
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_DeleteFile(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_DeleteFile"
    bl_label = "Delete File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File").subtype = "FILE_PATH"
        self.add_boolean_output("Deleted File")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def delete_file_skd(File_del):
                    try:
                        os.remove(File_del)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""delskd_{self.static_uid} = delete_file_skd({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"delskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

