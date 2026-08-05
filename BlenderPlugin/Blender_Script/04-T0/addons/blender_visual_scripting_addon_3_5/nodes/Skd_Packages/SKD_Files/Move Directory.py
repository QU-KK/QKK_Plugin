import bpy
import os
import shutil

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_MoveAllFolderFiles(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_MoveAllFolderFiles"
    bl_label = "Move Directory"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Directory").subtype = "FILE_PATH"
        self.add_string_input("New Location").subtype = "FILE_PATH"
        self.add_boolean_output("Moved Directory")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            import shutil
                            """
   
        self.code_imperative = """
                def skd_move_folder_and_files(source_folder, destination_folder):
                    # Ensure the source folder exists
                    if os.path.exists(source_folder):
                        try:
                            shutil.move(source_folder, destination_folder)
                            return True
                        except:
                            return False
                    else:
                        return False
                    """
        
        self.code = f"""skd_move_folder_and_filesskd_{self.static_uid} = skd_move_folder_and_files({self.inputs[1].python_value},{self.inputs[2].python_value} )"""
        self.outputs[1].python_value = f"skd_move_folder_and_filesskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

