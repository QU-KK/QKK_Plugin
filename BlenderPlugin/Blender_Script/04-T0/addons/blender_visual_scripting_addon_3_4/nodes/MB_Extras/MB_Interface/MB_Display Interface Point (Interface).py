import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_DisplayInterfacePoint(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_DisplayInterfacePoint"
    bl_label = "MB_Display Interface Point (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        self.add_interface_input()
        socket = self.add_float_vector_input("Color")
        socket.subtype = "COLOR_ALPHA"
        self.add_interface_output().passthrough_layout_type = True

    def evaluate(self, context):
        self.code = f"""
                        point_color = {self.inputs["Color"].python_value}
                        {self.active_layout}.template_node_socket(color=point_color)
                        {self.indent(self.outputs[0].python_value, 3)}
                    """
                    
