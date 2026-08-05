import bpy
from ..base_node import SN_ScriptingBaseNode


def update_input_sockets(self, context):
    # 当 input_count 属性改变时触发，用于动态更新输入端口的数量。
    # 除去第一个 ID String 输入，计算当前实际的 Data 输入数量
    current_data_inputs = len(self.inputs) - 1
    target_count = self.input_count
    
    # 增加接口
    while current_data_inputs < target_count:
        # 使用默认名称添加，用户可以在节点UI上随时改名
        self.add_data_input(f"接口{current_data_inputs}")
        current_data_inputs += 1
        
    # 移除多余的接口
    while current_data_inputs > target_count:
        self.inputs.remove(self.inputs[-1])
        current_data_inputs -= 1


class SN_String_SwitchDataNode(SN_ScriptingBaseNode, bpy.types.Node):
    
    bl_idname = "SN_String_SwitchDataNode"
    bl_label = "名称匹配切换"
    node_color = "DEFAULT"
    
    # 控制输入数量
    input_count: bpy.props.IntProperty(
        name="数量",
        description="数据输入数量",
        default=2,
        min=2,
        max=32,
        update=update_input_sockets
    )

    def on_create(self, context):
        # 1. 接收目标匹配的字符串 (ID)
        self.add_data_input("输入名称") 
        
        # 初始默认创建2个输入，默认给个初始名称
        self.add_data_input("接口1")
        self.add_data_input("接口2")
        self.add_data_output("输出").changeable = True

    def draw_buttons(self, context, layout):
        # 在节点上绘制输入数量控制
        layout.prop(self, "input_count")
        

        # 2. 遍历所有数据接口（排除第1个 ID 接口）
        # 将它们的名字 (name) 暴露在 UI 上，用户可以直接在这里修改
        for i, inp in enumerate(self.inputs[1:]):
            row = layout.row(align=True)
            row.label(text=f"名称:")
            # 这里修改 inp.name 也会自动同步到节点左侧插槽的文字显示上
            row.prop(inp, "name", text="")

    def evaluate(self, context):
        # 目标匹配字符串 (ID) 的 Python 变量表达
        id_value = self.inputs[0].python_value
        
        # 3. 动态生成 Python 字典的内容: {"自定义名1": 数据1, "自定义名2": 数据2, ...}
        dict_elements = []
        for inp in self.inputs[1:]:
            # 使用 repr() 来包裹 inp.name，这样能自动加上引号，并防止用户输入特殊字符导致 Python 语法错误
            key_str = repr(inp.name)
            val_str = inp.python_value
            dict_elements.append(f"{key_str}: {val_str}")
            
        dict_string = "{" + ", ".join(dict_elements) + "}"
        
        # 4. 输出代码逻辑：通过字典的 .get() 提取对应的数据
        # 用 .get() 的好处是，如果输入的 ID 字符串没有匹配项，它会安全地返回 None，而不会抛出 KeyError 阻断整个代码运行
        self.outputs[0].python_value = f"{dict_string}.get({id_value})"