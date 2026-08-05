import bpy
import importlib.metadata
import sys
import site
import subprocess
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_ExternalPythonFolder(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_ExternalPythonFolder"
    bl_label = "Get Users Python Modules"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_boolean_input("Get All Locations").default_value = True
        self.add_dynamic_string_input("Module")
        self.add_list_output("Modules")
        self.add_list_output("Modules Installed")
        
    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list_P = [" , " + inp.python_value for inp in self.inputs[2:-1]]


        self.code_import = f"""
                            import bpy
                            import importlib.metadata
                            import sys
                            import site
                            import subprocess
                            import os
                            """
        self.code_imperative = f"""

                def mod_python_skd(*args):
                    modules = []
                    versions = []

                    if args[0]:
                        
                        # Retrieve the user-specific site-packages path
                        user_site_packages = site.getusersitepackages()

                        # Append the path to sys.path if it isn't already included
                        if user_site_packages not in sys.path:
                            sys.path.append(user_site_packages)

                        # Optionally, add paths from PYTHONPATH environment variable if defined
                        pythonpath_env = os.getenv('PYTHONPATH')

                    if len(args) > 1:
            
                        for i, arg in enumerate(args[1:]):
                            try:
                                # Get the version of the package
                                version = importlib.metadata.version(arg)
                                modules.append(arg)
                                versions.append(version)

                            except:
                                modules.append(arg)
                                versions.append(False)

                    return modules, versions
                    """
        
        self.code = f"""python_mods_skd_{self.static_uid} = mod_python_skd({self.inputs[1].python_value + "".join(vars_list_P)})"""
        self.outputs[1].python_value = f"python_mods_skd_{self.static_uid}[0]"
        self.outputs[2].python_value = f"python_mods_skd_{self.static_uid}[1]"
        self.code += f'\n{self.outputs[0].python_value}'