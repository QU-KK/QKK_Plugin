import bpy
import shutil

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_CopyFile(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CopyFile"
    bl_label = "Copy File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File").subtype = "FILE_PATH"
        self.add_string_input("New Directory").subtype = "DIR_PATH"
        self.add_boolean_output("File Copied")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import shutil
                            """
   
        self.code_imperative = """
                def copy_file_skd(FileLocation, SaveFileLocation):
                    try:
                        shutil.copy(FileLocation, SaveFileLocation)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""copyskd_{self.static_uid} = copy_file_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"copyskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

