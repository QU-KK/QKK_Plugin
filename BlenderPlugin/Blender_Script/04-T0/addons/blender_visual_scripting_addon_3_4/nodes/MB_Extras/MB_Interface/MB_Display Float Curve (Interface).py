import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_DisplayFloatCurve(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_DisplayFloatCurve"
    bl_label = "MB_Display Float Curve (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        self.add_interface_input()
        self.add_property_input("Float Curve Node")


    def evaluate(self, context):
        if self.inputs["Float Curve Node"].is_linked:
            self.code = f"""
                            {self.active_layout}.template_curve_mapping({self.inputs["Float Curve Node"].python_value}, "mapping")
                        """