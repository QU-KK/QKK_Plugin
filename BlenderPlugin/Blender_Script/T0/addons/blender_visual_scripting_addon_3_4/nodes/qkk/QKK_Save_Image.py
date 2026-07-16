import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_Save_Image_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_Save_Smage"
    bl_label = "保存图像"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_property_input('图像')
        self.add_string_input('路径').subtype = "FILE_PATH"
        self.add_string_input('名称')

        # 输出
        self.add_execute_output()

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    image = {self.inputs['图像'].python_value}

                    save_path = {self.inputs['路径'].python_value}
                    save_image_name = {self.inputs['名称'].python_value}

                    file_path = os.path.join(save_path, save_image_name)
                    image.save_render(filepath=file_path)


                    {self.indent(self.outputs[0].python_value, 5)}

        """

        self.code_import = f"""
                            import bpy
                            import os

                            """