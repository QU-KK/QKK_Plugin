import bpy
import math
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_PageNationAmount(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "PageNationAmount"
    bl_label = "Page Amount"
    node_color = "FLOAT"

    def on_create(self, context):
        self.add_float_input("Item Amount")
        self.add_float_input("Display Amount")
        self.add_integer_output("Total Pages")

    def evaluate(self, context):
        self.code_import = """
                            import math
                            """

        self.code_imperative = """
            def skd_Pages(items, DisplayAmount):
                diver = items / DisplayAmount
                Rounders = math.ceil(diver)
                return Rounders    
            """
        
        self.code = f"""skd_Pages({self.inputs[0].python_value},{self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"skd_Pages({self.inputs[0].python_value},{self.inputs[1].python_value})"
    