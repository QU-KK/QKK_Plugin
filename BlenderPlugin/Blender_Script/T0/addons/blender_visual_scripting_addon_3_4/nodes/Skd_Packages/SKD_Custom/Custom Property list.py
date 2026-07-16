import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Property_Type_List(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Property_Type_List"
    bl_label = "Custom Properties List"
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_property_input("Blend Data")
        self.add_list_output("Properties Name")
        self.add_list_output("Properties Value")
        self.add_list_output("Properties Type")

    def evaluate(self, context):
        # Define imperative code
        self.code_imperative = """
            def get_custom_properties(data_block):
                # Initialize lists for names, values, and types
                property_names = []
                property_values = []
                property_types = []

                # Check if the data block has custom properties
                if data_block.items():
                    for key, value in data_block.items():
                        if not key.startswith("cycles"):
                            property_names.append(key)
                            property_values.append(value)
                            property_types.append(type(value).__name__)
                    
                    return property_names, property_values, property_types

                else:
                    return [], [], []
            """

        # Call get_template_values function with correct arguments
        self.code = f"""ret_prop_{self.static_uid} = get_custom_properties({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"ret_prop_{self.static_uid}[0]"
        self.outputs[2].python_value = f"ret_prop_{self.static_uid}[1]"
        self.outputs[3].python_value = f"ret_prop_{self.static_uid}[2]"
        self.code += f'\n{self.outputs[0].python_value}'