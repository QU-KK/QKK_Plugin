import bpy
from ..base_node import SN_ScriptingBaseNode


def update_input_sockets(self, context):
    """
    当 input_count 属性改变时触发，用于动态更新输入端口的数量。
    """
    # 除去第一个 Index 输入，计算当前实际的 Data 输入数量
    current_data_inputs = len(self.inputs) - 1
    target_count = self.input_count
    
    # 如果目标数量大于当前数量，增加接口
    while current_data_inputs < target_count:
        self.add_data_input(f"Data {current_data_inputs}")
        current_data_inputs += 1
        
    # 如果目标数量小于当前数量，移除多余的接口
    while current_data_inputs > target_count:
        # 移除最后一个接口
        self.inputs.remove(self.inputs[-1])
        current_data_inputs -= 1


class SN_SwitchDataNode6(SN_ScriptingBaseNode, bpy.types.Node):
    
    bl_idname = "SN_SwitchDataNode6"
    bl_label = "Switch Data6"
    node_color = "DEFAULT"
    
    # 1. 定义一个整数属性来控制输入数量
    input_count: bpy.props.IntProperty(
        name="Input Count",
        description="Number of data inputs to switch between",
        default=2,
        min=2, # 至少保留2个数据输入
        max=32, # 可以根据需要设置上限
        update=update_input_sockets
    )

    def on_create(self, context):
        self.add_integer_input("Index")
        # 初始默认创建2个输入（与 input_count 的 default 对应）
        self.add_data_input("Data 0")
        self.add_data_input("Data 1")
        self.add_data_output("Data").changeable = True

    def draw_buttons(self, context, layout):
        # 2. 在节点 UI 上绘制这个属性，让用户可以动态修改
        layout.prop(self, "input_count")

    def evaluate(self, context):
        # Index 输入的值
        index_value = self.inputs[0].python_value
        
        # 动态获取当前存在的所有 Data 输入项 (排除第一个 Index)
        data_values = [inp.python_value for inp in self.inputs[1:]]
        
        # 生成列表表达式: [Data0, Data1, Data2, ...]
        list_string = f"[{', '.join(data_values)}]"
        
        # 3. 输出生成的 Python 代码
        self.outputs[0].python_value = f"{list_string}[{index_value}]"