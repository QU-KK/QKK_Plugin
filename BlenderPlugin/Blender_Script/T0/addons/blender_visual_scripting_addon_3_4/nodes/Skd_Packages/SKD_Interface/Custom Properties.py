import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Custom_Properties(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Custom_Properties"
    bl_label = "Object Custom Properties"
    node_color = "INTERFACE"

    def on_create(self, context):
        self.add_interface_input()
        self.add_interface_output()
        self.add_property_input("Object Property")
        self.add_list_output("Property Name")

    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def custom_p(obj):
                nam = []
                if obj:
                        # Check if the object has custom properties
                    if obj.keys():
                        # Iterate through the custom properties and store their names and values
                        for prop_name in obj.keys():
                            # Skip properties with name "cycles"
                            if prop_name == "cycles":
                                continue
                            
                            nam.append(prop_name)
               
                return nam 
            """
        self.code = f"""cus_{self.static_uid} = custom_p({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"cus_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'