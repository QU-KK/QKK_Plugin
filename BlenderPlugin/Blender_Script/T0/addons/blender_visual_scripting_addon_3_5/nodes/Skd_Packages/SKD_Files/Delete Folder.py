import bpy
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_DeleteFolder(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_DeleteFolder"
    bl_label = "Delete Empty Folder"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Folder").subtype = "DIR_PATH"
        self.add_boolean_output("Deleted Folder")
        
        
    def evaluate(self, context):
        self.code_import = """
                            import os
                            """
   
        self.code_imperative = """
                def delete_folder_skd(Folder_del):
                    try:
                        os.rmdir(Folder_del)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""delskdf_{self.static_uid} = delete_folder_skd({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"delskdf_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
