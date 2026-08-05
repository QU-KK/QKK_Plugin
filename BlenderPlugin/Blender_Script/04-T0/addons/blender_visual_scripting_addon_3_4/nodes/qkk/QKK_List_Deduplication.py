import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_List_Deduplication_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_List_Deduplication"
    bl_label = "列表去重"
    node_color = "LIST"
    bl_width_default = 200

    def on_create(self, context):
        self.add_list_input('列表输入')

        self.add_list_output('列表输出')


    def evaluate(self, context):
        self.outputs['列表输出'].python_value = f"list(dict.fromkeys({self.inputs['列表输入'].python_value}))"