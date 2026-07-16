import bpy
from random import uniform
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_ColNode(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_ColNode"
    bl_label = "Custom Color"
    node_color = "VECTOR"
    bl_width_default = 260


    def update_sizer(self, context):
        # change our input size
        self.inputs[0].size = self.size
        self.outputs[0].size = self.size

    size: bpy.props.IntProperty(
            default=3,
            min=3,
            max=4,
            name="Size",
            description="Size of this the vector",
            update=update_sizer
        )
    
    def _update_custom_colorer(self, context):
        # If no numeric values found, set a default color or handle the case appropriately
        quicker_l = self.inputs[0].python_value.replace("'", '')
        quicker_l2 = quicker_l.replace("(", '')
        quicker_l3 = quicker_l2.replace(")", '')
        fl = [round(float(val.strip()), 4) for val in quicker_l3.split(',')]

        
        # Adjusting float values based on size
        if self.size == 3:
            float1, float2, float3 = fl
            float1 = max(0, min(float(float1), 1))
            float2 = max(0, min(float(float2), 1))
            float3 = max(0, min(float(float3), 1))
            float4 = 1.0  # Set float4 to default value 1.0
            output_value = f"({float1}, {float2}, {float3})"
        else:
            float1, float2, float3, float4 = fl
            # Ensure float values are within range [0, 1]
            float1 = max(0, min(float(float1), 1))
            float2 = max(0, min(float(float2), 1))
            float3 = max(0, min(float(float3), 1))
            float4 = max(0, min(float(float4), 1))
            output_value = f"({float1}, {float2}, {float3}, {float4})"

        self.custom_colorer = (float1, float2, float3, float4)
        return output_value  # Return output_value
    
    custom_colorer: bpy.props.FloatVectorProperty(
            name="Color",
            size=4,
            min=0,
            max=1,
            subtype="COLOR",
            description="The color of this node"
        )
    

    def on_create(self, context):
        self.add_float_vector_input("Colour")
        self.add_float_vector_output("Colour")

    def _evaluate(self, context):
           
        output_value = self._update_custom_colorer(context)  
        self.outputs[0].python_value = f"{output_value}"

    def draw_buttons(self, context, layout):
        layout.prop(self, "size")
        layout.prop(self, "custom_colorer", text="Custom Color")

    def draw_node(self, context, layout):
        # Draw the node
        self.draw_buttons(context, layout)

    def draw_node_panel(self, context, layout):
        # Draw the node in the n panel
        self.draw_buttons(context, layout)