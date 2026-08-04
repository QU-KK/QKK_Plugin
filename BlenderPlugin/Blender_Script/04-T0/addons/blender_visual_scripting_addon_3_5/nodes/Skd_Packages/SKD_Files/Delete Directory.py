import bpy
import os
import shutil

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_DeleteAllFolderFiles(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_DeleteAllFolderFiles"
    bl_label = "Delete Directory"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Directory").subtype = "FILE_PATH"
        self.add_boolean_output("Deleted Directory")
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import os
                            import shutil
                            """
   
        self.code_imperative = """
                def delete_all_in_folder(folder_path):
                    # Ensure the folder exists
                    if os.path.exists(folder_path):
                        try:
                            shutil.rmtree(folder_path)  # Remove the main folder and all its contents
                            return True
                        except:
                            return False
                    else:
                        return False
                    """
        
        self.code = f"""delete_all_in_folderskd_{self.static_uid} = delete_all_in_folder({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"delete_all_in_folderskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

