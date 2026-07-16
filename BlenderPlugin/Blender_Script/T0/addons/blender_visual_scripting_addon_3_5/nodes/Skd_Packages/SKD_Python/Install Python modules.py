import bpy
import subprocess
import sys

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_Install_Python_mod(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Install_Python_mod"
    bl_label = "Install Python Modules"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Module")
        self.add_boolean_output("Module Installed")
        
    def evaluate(self, context):

        self.code_import = f"""
                            import bpy
                            import subprocess
                            import sys
                            """
        self.code_imperative = f"""

                def install_mod_python_skd(modx):

                    python_executable = sys.executable

                    try:
                        subprocess.check_call([python_executable, "-m", "pip", "install", modx])
                        return True
                    except:
                        return False

                    """
        
        self.code = f"""python_mods_install_skd_{self.static_uid} = install_mod_python_skd({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"python_mods_install_skd_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'