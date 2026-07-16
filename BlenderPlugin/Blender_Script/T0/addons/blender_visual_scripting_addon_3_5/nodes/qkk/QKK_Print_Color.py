import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_Print_Color_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_Print_Color"
    bl_label = "打印颜色（90-97）"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_string_input('字符').default_value = '字符'
        self.add_string_input('颜色编号').default_value ='92'

        # 输出
        self.add_execute_output()
        self.add_string_output('颜色字符')

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    str1 = "\033["
                    str2 = {self.inputs['颜色编号'].python_value}
                    str3 = "m"
                    str4 = {self.inputs['字符'].python_value}
                    str5 = "\033[0m"
                    result = str1 + str2 + str3 + str4 + str5
                    {self.indent(self.outputs[0].python_value, 5)}
                   

        """
        self.outputs["颜色字符"].python_value = f"result" 