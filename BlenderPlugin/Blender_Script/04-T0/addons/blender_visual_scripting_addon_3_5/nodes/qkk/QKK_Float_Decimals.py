import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_Float_Decimals_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_Float_Decimals"
    bl_label = "保留小数"
    node_color = "PROGRAM"
    bl_width_default = 200

    def on_create(self, context):
        self.add_float_input('输入')
        self.add_integer_input('位数').default_value = 3

        self.add_float_output('输出')


    def evaluate(self, context):
        self.outputs['输出'].python_value = f"round({self.inputs['输入'].python_value},{self.inputs['位数'].python_value})"