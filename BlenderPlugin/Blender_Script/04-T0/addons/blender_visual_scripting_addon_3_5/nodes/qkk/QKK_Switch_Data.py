import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_SwitchDataNodeaa(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SwitchDataNodeaa"
    bl_label = "Switch Dataaa"
    node_color = "DEFAULT"

    def on_create(self, context):
        # 1. 将布尔输入改为整数（编号）输入
        # 注意：如果你的基础节点库中对应的函数叫 add_int_input，请将其替换一下
        self.add_integer_input("Index") 
        
        # 2. 添加数据输入 (这里默认添加两个，你可以根据需要添加更多)
        self.add_data_input("Data 0")
        self.add_data_input("Data 1")
        self.add_data_input("Data 2")
        self.add_data_input("Data 3")
        self.add_data_input("Data 4")

        
        self.add_data_output("Data").changeable = True

    def evaluate(self, context):
        # 获取索引节点的 Python 表达
        index_value = self.inputs[0].python_value
        
        # 动态获取除了第一个(Index)之外的所有 Data 输入项
        data_values = [inp.python_value for inp in self.inputs[1:]]
        
        # 将数据组合成一个 Python 列表格式: [Data0, Data1, ...]
        list_string = f"[{', '.join(data_values)}]"
        
        # 3. 输出代码逻辑：通过编号从列表中提取数据
        self.outputs[0].python_value = f"{list_string}[{index_value}]"