import bpy
import json
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_GetJsonTemplate(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_GetJsonTemplate"
    bl_label = "Json Get Template"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Json File Location").subtype = "FILE_PATH"
        self.add_string_input("Template Name").default_value = "Template"
        self.add_list_output("Template Items")
        self.add_list_output("Template Values")
        
    def evaluate(self, context):
        self.code_import = """
                        import json
                        import os
                        """

        self.code_imperative = """
                def get_template_values(template_name, filename):
                    existing_templates = {}
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        with open(filename, 'r') as file:
                            try:
                                existing_templates = json.load(file)
                            except json.JSONDecodeError:
                                pass  # Handle invalid JSON or empty file gracefully

                    return (list(existing_templates.get(template_name, {}).keys()),
                            list(existing_templates.get(template_name, {}).values()))
                """


        self.code = f"""ret_json_{self.static_uid} = get_template_values({self.inputs[2].python_value}, {self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"ret_json_{self.static_uid}[0]"
        self.outputs[2].python_value = f"ret_json_{self.static_uid}[1]"

        self.code += f'\n{self.outputs[0].python_value}'
