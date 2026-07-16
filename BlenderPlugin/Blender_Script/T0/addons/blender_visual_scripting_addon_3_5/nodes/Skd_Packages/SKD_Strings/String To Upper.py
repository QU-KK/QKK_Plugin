import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_StringToUpperNode(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_StringToUpperNode"
    bl_label = "String To Upper"
    node_color = "STRING"

    def on_create(self, context):
        self.add_string_input("String")
        self.add_string_output("String")

    def evaluate(self, context):
        self.outputs["String"].python_value = f"""{self.inputs["String"].python_value}.upper()"""