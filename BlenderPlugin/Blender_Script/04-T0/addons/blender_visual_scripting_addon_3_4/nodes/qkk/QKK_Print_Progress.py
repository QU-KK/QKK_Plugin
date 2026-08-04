import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_Print_Progress_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_Print_Progress "
    bl_label = "打印进度"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_string_input('字符1').default_value = '进度：'
        self.add_string_input('字符2').default_value = '100%'
        self.add_string_input('进度').default_value = '100%'

        # 输出
        self.add_execute_output()

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    import bpy
                    import os

                    # 清空控制台
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print({self.inputs['字符1'].python_value})
                    print({self.inputs['字符2'].python_value})
                    print({self.inputs['进度'].python_value})

                    {self.indent(self.outputs[0].python_value, 5)}

        """