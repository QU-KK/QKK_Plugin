import bpy
import math
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Roundup(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Roundup"
    bl_label = "Math Round Up Or Down"
    node_color = "FLOAT"

    def on_create(self, context):
        self.add_float_input("Float")
        self.add_boolean_input("Round Up").default_value = False
        self.add_integer_output("Integer")

    def evaluate(self, context):
        self.code_import = """
                            import math
                            """

        self.code_imperative = """
            def skd_round(RoundNum, round_up):
                
                Rounders = math.ceil(RoundNum) if round_up else math.floor(RoundNum)
                return Rounders    
            """
        
        self.code = f"""skd_round({self.inputs[0].python_value},{self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"skd_round({self.inputs[0].python_value},{self.inputs[1].python_value})"
    