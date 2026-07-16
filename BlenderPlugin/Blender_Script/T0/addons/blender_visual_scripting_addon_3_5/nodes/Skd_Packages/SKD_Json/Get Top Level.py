import bpy
import json
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Get_top_level(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Get_top_level"
    bl_label = "Json Get Top Level"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Json File Location").subtype = "FILE_PATH"
        self.add_list_output("Top Level Items")
        
    def evaluate(self, context):
        self.code_import = """
                            import json
                            import os
                            """

        self.code_imperative = """
            def get_top_level_keys(filename):
                existing_templates = {}
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, 'r') as file:
                        try:
                            existing_templates = json.load(file)
                        except json.JSONDecodeError:
                            pass  # Handle invalid JSON or empty file gracefully

                return list(existing_templates.keys())  # Return only top-level keys
            """


        self.code = f"""ret_json_top{self.static_uid} = get_top_level_keys({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"ret_json_top{self.static_uid}"

        self.code += f'\n{self.outputs[0].python_value}'
