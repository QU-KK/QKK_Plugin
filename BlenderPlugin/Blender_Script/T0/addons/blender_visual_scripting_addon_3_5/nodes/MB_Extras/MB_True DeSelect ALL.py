import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_MB_True_DeSelect_ALL_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_True_DeSelect_ALL_Node"
    bl_label = "MB_True DeSelect ALL"
    node_color = "PROGRAM"
    bl_width_default = 160


    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_execute_input()

        # outputs
        self.add_execute_output()

    def evaluate(self, context):
		# generate the code here
        self.code = f"""
                    if (bpy.context.view_layer.objects.selected or bpy.context.view_layer.objects.active):
                        bpy.ops.object.select_all(action='DESELECT')
                        bpy.context.view_layer.objects.active = None
                    """
