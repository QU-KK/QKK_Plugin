import bpy
import json
import os
import ast

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_CreateJsonTemplate(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CreateJsonTemplate"
    bl_label = "Json Create Template"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Json File Location").subtype = "FILE_PATH"
        self.add_string_input("Template Name").default_value = "Template"
        self.add_list_input("Template Items List")
        self.add_list_input("Template Values List")
        
    def evaluate(self, context):
        template_name = self.inputs[2].python_value.replace('"', '')

        # Define imperative code
        self.code_import = """
            import json
            import os
            import ast
            """

        self.code_imperative = """
            def create_or_update_json_template(template_name, items, values, filename):
                items = ast.literal_eval(items)
                values = ast.literal_eval(values)

                # Load existing templates from JSON file
                existing_templates = load_existing_templates(filename)

                # Initialize empty dictionary if no templates exist
                if not existing_templates:
                    existing_templates = {}

                # Initialize empty dictionary for the specified template
                if template_name not in existing_templates:
                    existing_templates[template_name] = {}

                # Combine items and values into a dictionary of key-value pairs
                item_value_pairs = dict(zip(items, values))

                # Update or add key-value pairs to the template
                existing_templates[template_name].update(item_value_pairs)

                # Save updated templates back to the JSON file
                save_json_template(existing_templates, filename)

            def load_existing_templates(filename):
                existing_templates = {}
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, 'r') as file:
                        try:
                            existing_templates = json.load(file)
                        except json.JSONDecodeError:
                            pass  # Handle invalid JSON or empty file gracefully
                return existing_templates

            def save_json_template(template, filename):
                sorted_template = {}
                for key in sorted(template.keys()):  # Sort keys alphabetically
                    sorted_template[key] = template[key]

                with open(filename, 'w', encoding='utf-8') as file:
                    json.dump(sorted_template, file, indent=4)
            """

        #self.code = f"create_or_update_json_template({template_name}, {self.inputs[3].python_value}, {self.inputs[4].python_value}, {self.inputs[1].python_value})"
        self.code = f"create_or_update_json_template({template_name}, json.dumps({self.inputs[3].python_value}), json.dumps({self.inputs[4].python_value}), {self.inputs[1].python_value})"
        self.code += f"\n{self.outputs[0].python_value}"
