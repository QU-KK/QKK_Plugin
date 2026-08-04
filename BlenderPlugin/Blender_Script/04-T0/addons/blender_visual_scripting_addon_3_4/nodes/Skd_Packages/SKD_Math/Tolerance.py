import bpy
import mathutils
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_tolerance(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_tolerance"
    bl_label = "Vector Tolerance"
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_float_vector_input("Vector 1")
        self.add_float_vector_input("Vector 2")
        self.add_integer_input("amount").default_value = 6
        self.add_boolean_output("Result")

    

    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            import mathutils
                            """

        self.code_imperative = """
            def skd_tolerance(vector1, vector2, typers): 

                diff = (mathutils.Vector(vector1) - mathutils.Vector(vector2)).length 
                return diff <  10 ** -float(typers)

            """
        
        self.code = f"""contol_{self.static_uid} = skd_tolerance({self.inputs[1].python_value},{self.inputs[2].python_value}, {self.inputs[3].python_value})"""
        self.outputs[1].python_value = f"contol_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'
