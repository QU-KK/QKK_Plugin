import bpy
import json
import os
import ast

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_DeleteJsonTemplateItems(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_DeleteJsonTemplateItems"
    bl_label = "Json Delete Template Items"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Json File Location").subtype = "FILE_PATH"
        self.add_string_input("Template Name").default_value = "Template"
        self.add_list_input("Items to Delete")  # List of items to remove from the template
        
    def evaluate(self, context):
        template_name = self.inputs[2].python_value.replace('"', '')

        # Define imperative code
        self.code_import = """
            import json
            import os
            import ast
            """

        self.code_imperative = """
            def delete_json_template_items(template_name, items_to_delete, filename):
                items_to_delete = ast.literal_eval(items_to_delete)

                # Load existing templates from JSON file
                existing_templates = load_existing_templates(filename)

                # Check if template exists
                if template_name in existing_templates:
                    # Remove specified items
                    for item in items_to_delete:
                        existing_templates[template_name].pop(item, None)

                    # If template is empty after deletion, remove it
                    if not existing_templates[template_name]:
                        del existing_templates[template_name]

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

        self.code = f"delete_json_template_items({template_name}, json.dumps({self.inputs[3].python_value}), {self.inputs[1].python_value})"
        self.code += f"\n{self.outputs[0].python_value}"
