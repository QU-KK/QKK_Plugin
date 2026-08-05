import bpy
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_CreateFolder(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CreateFolder"
    bl_label = "Create Folder"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Folder Name").subtype = "FILE_PATH"
        self.add_string_input("Directory").subtype = "DIR_PATH"
        self.add_boolean_output("Folder Created")
        
    def evaluate(self, context):
        self.code_import = """
            import os
        """
   
        self.code_imperative = """
            def create_folder_skd(folder_name, directory_path):
                try:
                    folder_path = os.path.join(directory_path, folder_name)
                    os.makedirs(folder_path)
                    return True
                except:
                    return False
        """
        
        self.code = f"""createskdf_{self.static_uid} = create_folder_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"createskdf_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
