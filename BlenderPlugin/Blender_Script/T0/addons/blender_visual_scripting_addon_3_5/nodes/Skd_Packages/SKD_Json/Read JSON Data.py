import bpy
import sys
import site
import os
import requests
import json

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_ReadJson_data(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_ReadJson_data"
    bl_label = "Get JSON Data"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_boolean_input("URL")
        self.add_string_input("JSON File")
        self.add_dynamic_string_input("Read")
        self.add_list_output("Args")
        self.add_list_output("Data")

    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list_P = [" , " + inp.python_value for inp in self.inputs[2:-1]]

        self.code_import = f"""
                            import bpy
                            import sys
                            import os
                            import requests
                            import json
                            """

        self.code_imperative = f"""

                def read_json_skd(*args):
                    Argsz = []
                    Data = []
                    package_info = None

                    # Check if we need to fetch from a URL or local file
                    if args[0] is True:
                        if args[1]:
                            file_url = args[1]
                            response = requests.get(file_url)
                            # Check if the request was successful
                            if response.status_code == 200:
                                # Parse the JSON content
                                package_info = response.json()
                    else:
                        file_url = args[1]
                        if os.path.exists(file_url):
                            with open(file_url, "r") as file:
                                package_info = json.load(file)

                    if package_info is None:
                        return ["Error: Unable to load JSON data"], []

                    # Handle dynamic fields from the JSON
                    if len(args) > 2:
                        for i, arg in enumerate(args[2:]):
                            try:
                                # Handle any name with ':' for nested field extraction
                                if ":" in arg:
                                    field_path = arg.split(":")
                                    value = package_info
                                    for key in field_path:
                                        if isinstance(value, dict):
                                            value = value.get(key, "Not in file")
                                        elif isinstance(value, list):
                                            value = [item.get(key, "Not in file") if isinstance(item, dict) else "Invalid structure" for item in value]
                                        else:
                                            value = "Invalid structure"
                                            break
                                    Argsz.append(arg)
                                    Data.append(value)
                                else:
                                    if isinstance(package_info, list):
                                        value = [item.get(arg, "Not in file") if isinstance(item, dict) else "Invalid structure" for item in package_info]
                                    else:
                                        value = package_info.get(arg, "Not in file")
                                    Argsz.append(arg)
                                    Data.append(value)
                            except Exception as e:
                                Argsz.append(arg)
                                Data.append(f"Error: {{e}}")

                    return Argsz, Data
                    """

        self.code = f"""json_read_skd_{self.static_uid} = read_json_skd({self.inputs[1].python_value + "".join(vars_list_P)})"""
        self.outputs[1].python_value = f"json_read_skd_{self.static_uid}[0]"
        self.outputs[2].python_value = f"json_read_skd_{self.static_uid}[1]"
        self.code += f'\n{self.outputs[0].python_value}'
