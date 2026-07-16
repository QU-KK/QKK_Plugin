import bpy
import math
from ...base_node import SN_ScriptingBaseNode

class PageNationIndexes(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "PageNationIndexes"
    bl_label = "Page Index Items"
    node_color = "FLOAT"

    def on_create(self, context):
        self.add_integer_input("Page Number")
        self.add_integer_input("Display Amount")
        self.add_boolean_input("Start at position 1")
        self.add_integer_output("Start Item")
        self.add_integer_output("End Item")

    def evaluate(self, context):
        self.code_import = """
                            import math
                            """

        self.code_imperative = """
            def skd_Items(page, DisplayAmount, startat):
                
                if startat:
                    Start = (page - 1) * DisplayAmount + 1 
                else:
                    Start = (page - 1) * DisplayAmount 
                
                End = Start + DisplayAmount - 1
                
                return Start, End
         
                """
        
        self.code = f"""skd_Items({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[0].python_value = f"skd_Items({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[2].python_value})[0]"
        self.outputs[1].python_value = f"skd_Items({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[2].python_value})[1]"
    