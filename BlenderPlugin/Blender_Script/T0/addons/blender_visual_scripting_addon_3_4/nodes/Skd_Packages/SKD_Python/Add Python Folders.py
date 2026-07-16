import bpy
import importlib.metadata
import sys
import subprocess
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_PythonAddFolder(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_PythonAddFolder"
    bl_label = "Add Folder to Modules"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_dynamic_string_input("Add Module").subtype = "FILE_PATH"
        
    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list_P = [" , " + inp.python_value for inp in self.inputs[1:-1]]

        self.code_import = """
                            import bpy
                            import importlib.metadata
                            import sys
                            import subprocess
                            import os
                            """
        self.code_imperative = """
                def mod_python_folder_skd(*args):
                    for arg in args:
                        if arg and arg not in sys.path:
                            sys.path.append(arg)
"""
        
        self.code = f"""mod_python_folder_skd({self.inputs[1].python_value + "".join(vars_list_P)})"""
        self.code += f'\n{self.outputs[0].python_value}'