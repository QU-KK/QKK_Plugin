import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_View_Hide_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_View_Hide"
    bl_label = "物体视图隐藏"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_string_input('物体名称')
        self.add_boolean_input('隐藏/显示')

        # 输出
        self.add_execute_output()

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    
                    bpy.data.objects[{self.inputs['物体名称'].python_value}].hide_set((not {self.inputs['隐藏/显示'].python_value}))


                    {self.indent(self.outputs[0].python_value, 5)}

        """

        self.code_import = f"""
                            import bpy
                            """