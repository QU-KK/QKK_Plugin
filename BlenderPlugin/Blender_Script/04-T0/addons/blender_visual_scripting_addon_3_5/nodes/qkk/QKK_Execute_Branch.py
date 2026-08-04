import bpy
from ..base_node import SN_ScriptingBaseNode

# 这个函数会在你调节节点上的“分支数量”滑块时自动触发
def update_branches(self, context):
    target_count = self.branch_count
    current_count = len(self.outputs) # 当前实际的输出端口数量 (即分支数)

    # 如果目标数量大于当前数量，说明需要增加分支
    if target_count > current_count:
        for i in range(current_count, target_count):
            self.add_boolean_input(f"开关 {i+1}")
            self.add_execute_output(f"运行 {i+1}")
            
    # 如果目标数量小于当前数量，说明需要减少分支
    elif target_count < current_count:
        for i in range(current_count, target_count, -1):
            # 删除最后一个输入端 (不会影响索引为 0 的主执行端)
            self.inputs.remove(self.inputs[-1])
            # 删除最后一个输出端
            self.outputs.remove(self.outputs[-1])


class SN_ExecuteMultiBranchNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_ExecuteMultiBranchNode"
    bl_label = "分支运行"
    node_color = "EXECUTE"

    # 1. 注册一个整数属性来控制分支数量
    branch_count: bpy.props.IntProperty(
        name="分支数量",
        description="控制可以连接的运行分支数目",
        default=4,
        min=1,       # 至少保留 1 个分支
        max=32,      # 设置一个合理的上限防止卡顿
        update=update_branches  # 关联上面的更新函数
    )

    def on_create(self, context):
        # 基础执行输入
        self.add_execute_input("Execute")
        
        # 初始按照默认值 (4) 创建分支
        for i in range(self.branch_count):
            self.add_boolean_input(f"开关 {i+1}")
            self.add_execute_output(f"运行 {i+1}")

    # 2. 将属性暴露到节点面板上 (绘制UI)
    def draw_buttons(self, context, layout):
        layout.prop(self, "branch_count")

    def evaluate(self, context):
        code_lines = []
        
        # 3. 生成代码时，不再固定 range(4)，而是根据当前实际输出端数量来遍历
        current_count = len(self.outputs)
        
        for i in range(current_count):
            bool_input = self.inputs[i + 1]
            exec_output = self.outputs[i]
            
            # 如果输出端口没有连接后面的执行节点，直接跳过
            if not exec_output.is_linked:
                continue

            # 获取布尔条件和后续分支的代码
            condition_val = bool_input.python_value
            branch_code = exec_output.python_value
            
            if not branch_code:
                continue

            if condition_val in (True, "True", 1, "1"):
                code_lines.append(branch_code)
            elif condition_val in (False, "False", 0, "0"):
                pass
            else:
                code_lines.append(f"if {condition_val}:")
                indented_code = "    " + str(branch_code).replace("\n", "\n    ")
                code_lines.append(indented_code)
        
        # 将生成的代码交给主执行输入端口
        final_code = "\n".join(code_lines)
        if final_code:
            self.inputs[0].python_value = final_code