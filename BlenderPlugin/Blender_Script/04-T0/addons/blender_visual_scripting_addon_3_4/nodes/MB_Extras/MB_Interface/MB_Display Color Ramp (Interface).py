import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_DisplayColorRamp(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_DisplayColorRamp"
    bl_label = "MB_Display Color Ramp (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        self.add_interface_input()
        self.add_property_input("Color Ramp Node")


    def evaluate(self, context):
        if self.inputs["Color Ramp Node"].is_linked:
            self.code = f"""
                            {self.active_layout}.template_color_ramp({self.inputs["Color Ramp Node"].python_value}, "color_ramp")
                        """

