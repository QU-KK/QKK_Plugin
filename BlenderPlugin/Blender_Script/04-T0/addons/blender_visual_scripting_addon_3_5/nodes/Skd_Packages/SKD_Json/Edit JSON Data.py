import bpy
import sys
import site
import os
import requests
import json

from ...base_node import SN_ScriptingBaseNode
from ....utils import unique_collection_name, get_python_name

class SN_SKD_EditJson_data(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_EditJson_data"
    bl_label = "Change JSON Data"
    bl_width_default = 240
    node_color = "PROGRAM"

    

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("JSON File")
        inp = self.add_dynamic_data_input("Change Me")
        inp.index_type = "String"
        inp.is_variable = True
        inp.changeable = True
        self.add_list_output("Args")
        self.add_list_output("Data")

    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list_P  = ["" + inp.python_value.strip("'") for inp in self.inputs[2:-1]]
        vars_list_P2 = ["" + inp.name for inp in self.inputs[2:-1]]
        # Create a dictionary linking corresponding elements
        args_string = dict(zip(vars_list_P2, vars_list_P))


        self.code_import = f"""
                            import bpy
                            import sys
                            import os
                            import requests
                            import json
                            """

        self.code_imperative = f"""
                    def write_json_skd(file, *args):
                        Argsz = []
                        Data = []

                        if not args:
                            return Argsz, Data

                        try:
                            # Load the JSON file
                            with open(file, "r") as f:
                                package_info = json.load(f)
                        except FileNotFoundError:
                            return ["Error"], ["JSON file not found."]
                        except json.JSONDecodeError:
                            return ["Error"], ["Invalid JSON format."]

                        # args[0] is expected to be a dictionary
                        updates_dict = args[0] if isinstance(args[0], dict) else {{}}

                        for key, value in updates_dict.items():
                            Argsz.append(key)  # Add the key to the Argsz list

                            if ":" in key:
                                # Handle nested keys like "nodes:name"
                                parent, nested_key = key.split(":", 1)
                                if parent in package_info and isinstance(package_info[parent], list):
                                    updated = False
                                    for item in package_info[parent]:
                                        if isinstance(item, dict) and nested_key in item:
                                            item[nested_key] = value
                                            updated = True
                                    Data.append(value if updated else "Value not found")
                                else:
                                    Data.append("Value not found")
                            else:
                                # Handle top-level keys
                                if key in package_info:
                                    package_info[key] = value
                                    Data.append(package_info[key])
                                else:
                                    Data.append("Value not found")

                        # Write the updated JSON back to the file
                        try:
                            with open(file, "w") as f:
                                json.dump(package_info, f, indent=4)
                        except Exception as e:
                            return ["Error"], [f"Failed to write JSON: {{e}}"]

                        return Argsz, Data

                    """
        
        self.code = f"""json_write_skd_{self.static_uid} = write_json_skd({self.inputs[1].python_value}, {args_string})"""
        self.outputs[1].python_value = f"json_write_skd_{self.static_uid}[0]"
        self.outputs[2].python_value = f"json_write_skd_{self.static_uid}[1]"
        self.code += f'\n{self.outputs[0].python_value}'
