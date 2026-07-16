import bpy
import subprocess
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_ExternalPython(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_ExternalPython"
    bl_label = "Run External Python"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File").subtype = "FILE_PATH"
        self.add_dynamic_string_input("Vars")
        self.add_string_output("Returned")
        
    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list = [" , " +inp.python_value for inp in self.inputs[2:] if inp.is_linked]
        
        self.code_import = f"""
                            import bpy
                            import subprocess
                            import os
                            """
   
        self.code_imperative = f"""
                def run_python_skd(*args): 
                    try:
                        # Call the external Python script with file path and dynamic variables as separate arguments
                        subprocess.Popen(["python"] + list(args))
                        return 'External script started'
                    except:
                        return 'Failed'
                    """
        
        # Create the Python code to call run_python_skd with script path and dynamic inputs
        self.code = f"""pythonskd_{self.static_uid} = run_python_skd({self.inputs[1].python_value + "".join(vars_list)})"""
        self.outputs[1].python_value = f"pythonskd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
