import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_NEW_Collection_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_NEW_Collection "
    bl_label = "新建集合"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_string_input('name').default_value = '新建集合'

        # 输出
        self.add_execute_output()

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    # 创建一个新集合
                    new_collection = bpy.data.collections.new({self.inputs['name'].python_value})

                    # 将新集合添加到场景集合中
                    bpy.context.scene.collection.children.link(new_collection)

                    {self.indent(self.outputs[0].python_value, 5)}

        """