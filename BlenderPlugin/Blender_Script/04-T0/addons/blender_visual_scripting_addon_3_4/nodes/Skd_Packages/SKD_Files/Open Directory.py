import bpy
import os
import subprocess
import platform


from ...base_node import SN_ScriptingBaseNode
class SN_SKD_Folder_open(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Folder_open"
    bl_label = "Open Directory"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File Location").subtype = "DIR_PATH"
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            import subprocess
                            import platform
                            """
   
        self.code_imperative = """
                def open_folder_skd(directory):
                    # Normalize the path
                    path = os.path.abspath(directory)
                    
                    if platform.system() == "Windows":
                        os.startfile(path)
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.Popen(["open", path])
                    else:  # Linux and other Unix-based systems
                        subprocess.Popen(["xdg-open", path])
                    """
        
        self.code = f"""open_folder_skd({self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"open_folder_skd({self.inputs[1].python_value})"
        self.code += f'\n{self.outputs[0].python_value}'

