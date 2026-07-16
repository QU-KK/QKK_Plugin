import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_SKD_Property_Type(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_Property_Type"
    bl_label = "Custom Property Type"
    node_color = "PROPERTY"


    def on_create(self, context):
        self.add_property_input("Blend Data")
        self.add_string_input("Property")
        self.add_string_output("Type")


    def evaluate(self, context):
        if self.inputs[0].is_linked:
            self.outputs[0].python_value = f"type({self.inputs[0].python_value}[{self.inputs[1].python_value}]).__name__"
        else:
            self.outputs[0].python_value = f""