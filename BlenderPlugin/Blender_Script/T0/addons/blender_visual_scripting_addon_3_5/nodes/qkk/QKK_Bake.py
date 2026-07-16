import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_QKK_Bake_Blender_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "QKK_Bake"
    bl_label = "渲染器设置（烘焙）"
    node_color = "PROGRAM"
    bl_width_default = 250

    def on_create(self, context):
        # 输入
        self.add_execute_input()
        self.add_string_input('CPU/GPU').default_value = 'GPU'
        self.add_integer_input('采样').default_value = 512
        self.add_boolean_input('降噪').default_value = True

        # 输出
        self.add_execute_output()

    def evaluate(self, context):
		# 生成代码

        self.code = f"""
                    bpy.context.scene.render.engine = 'CYCLES'  #引擎

                    bpy.context.scene.cycles.device = {self.inputs['CPU/GPU'].python_value}
                    bpy.context.scene.cycles.samples = {self.inputs['采样'].python_value}
                    bpy.context.scene.cycles.use_denoising = {self.inputs['降噪'].python_value}

                    #降噪配置
                    bpy.context.scene.cycles.denoiser = 'OPENIMAGEDENOISE'
                    bpy.context.scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
                    bpy.context.scene.cycles.denoising_prefilter = 'ACCURATE'
                    bpy.context.scene.cycles.denoising_quality = 'HIGH'
                    bpy.context.scene.cycles.denoising_use_gpu = True

                    {self.indent(self.outputs[0].python_value, 5)}

        """
        self.code_import = f"""
                            import bpy

                            """