import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_RemovePlus(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_RemovePlus"
    bl_label = "Replace In String Plus"
    bl_width_default = 200
    node_color = "STRING"
    
    def on_create(self, context):
        self.add_string_input("String")  # The main string input
        self.add_dynamic_string_input("Old")  # Characters to replace (one per input)
        self.add_string_input("New")  # The string to replace "Old" characters with
        self.add_string_output("String")  # Output string

    def evaluate(self, context):
        # Construct a list of inputs dynamically
        inputs_list = [input_socket.python_value for input_socket in self.inputs if input_socket.name.startswith("Old")]

        # Update the imperative code with the correct references
        self.code_imperative = f"""
            def replace_plus(modified_string, new_str, old_list):
                
                for old_char in old_list:
                    modified_string = modified_string.replace(old_char, new_str)
                return modified_string
            """
        self.code = f"""replace_plus({self.inputs[0].python_value},{self.inputs['New'].python_value},{[self.inputs[i].python_value[1:-1] for i in range(1, len(self.inputs) - 2)]})"""
        self.outputs[0].python_value = f"""replace_plus({self.inputs[0].python_value},{self.inputs['New'].python_value},{[self.inputs[i].python_value[1:-1] for i in range(1, len(self.inputs) - 2)]})"""
