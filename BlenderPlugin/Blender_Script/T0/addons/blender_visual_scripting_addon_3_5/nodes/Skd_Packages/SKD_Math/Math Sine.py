import bpy
import math
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Math(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Math"
    bl_label = "Math Sine, Cosine, Tangent, Arctangent"
    node_color = "FLOAT"

    def on_create(self, context):
        self.add_float_input("Float")
        self.add_float_output("Value")

    type: bpy.props.EnumProperty(name="",
                                 items=[("Sine", "Sine", "",),
                                        ("Cosine", "Cosine", "",),
                                        ("Tangent", "Tangent", "",),
                                        ("Arctangent", "Arctangent", "",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)
    
    style: bpy.props.EnumProperty(name="",
                                 items=[("Radians", "Radians", "",),
                                        ("Degrees", "Degrees", "",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)
    def evaluate(self, context):
        self.code_import = """
                            import math
                            """

        self.code_imperative = """
            def skd_math(style, typer, float_value):
                
                if style == "Degrees":
                    if typer == "Sine":
                        return math.sin(math.degrees(float_value))
                    elif typer == "Cosine":
                        return math.cos(math.degrees(float_value))
                    elif typer == "Tangent":
                        return math.tan(math.degrees(float_value))
                    elif typer == "Arctangent":
                        return math.atan(math.degrees(float_value))

                elif style == "Radians":
                    if typer == "Sine":
                        return math.sin(math.radians(float_value))
                    elif typer == "Cosine":
                        return math.cos(math.radians(float_value))
                    elif typer == "Tangent":
                        return math.tan(math.radians(float_value))
                    elif typer == "Arctangent":
                        return math.atan(math.radians(float_value))

            """
        
        self.code = f"""skd_math("{self.style}","{self.type}", {self.inputs[0].python_value})"""
        self.outputs[0].python_value = f"""skd_math("{self.style}","{self.type}", {self.inputs[0].python_value})"""

    def draw_node(self, context, layout):
        layout.prop(self, "style", text="Select Option")
        layout.prop(self, "type", text="Select Option")
