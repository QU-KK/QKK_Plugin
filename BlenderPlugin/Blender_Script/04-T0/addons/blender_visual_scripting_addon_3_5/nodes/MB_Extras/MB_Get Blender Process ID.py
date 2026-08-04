import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_MB_Get_Blender_PID_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_Get_Blender_PID_Node"
    bl_label = "MB_Get Blender Process ID"
    node_color = "PROGRAM"
    bl_width_default = 175

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_execute_input()

        # outputs
        self.add_execute_output()
        self.add_integer_output('PID')

    def evaluate(self, context):
		# generate the code here
        self.code = f"""
                    # Get the process ID using the ctypes library
                    process_id = ctypes.windll.kernel32.GetCurrentProcessId()
                    {self.indent(self.outputs[0].python_value, 5)}
        """
        self.outputs['PID'].python_value = f"process_id"

        self.code_import = f"""
                            import bpy
                            import ctypes
                            """
