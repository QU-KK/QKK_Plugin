import bpy
from ...base_node import SN_ScriptingBaseNode

class SKD_SN_DrawImageNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SKD_SN_DrawImageNode"
    bl_label = "Draw Image with flip"
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_string_input("Asset")
        inp = self.add_float_input("Width")
        inp.default_value = 100
        inp = self.add_float_input("Height")
        inp.default_value = 100
        inp = self.add_float_vector_input("Location")
        inp.size = 2
        inp = self.add_boolean_input("Flip")
        inp.default_value = False
        self.add_execute_output()

    def evaluate(self, context):
        
        self.code_import = f"""
            import gpu
            import gpu_extras
            import os
        """
        
        bl = self.inputs["Location"].python_value

        coords = f"""
            coords = (
                ({bl}[0], {bl}[1]),
                ({bl}[0] + {self.inputs["Width"].python_value}, {bl}[1]),
                ({bl}[0] + {self.inputs["Width"].python_value}, {bl}[1] + {self.inputs["Height"].python_value}),
                ({bl}[0], {bl}[1] + {self.inputs["Height"].python_value})
            )
        """

        flip = self.inputs["Flip"].python_value

        texCoord = f"""
            texCoord = (
                (1, 0) if {flip} else (0, 0),
                (0, 0) if {flip} else (1, 0),
                (0, 1) if {flip} else (1, 1),
                (1, 1) if {flip} else (0, 1)
            )
        """

        self.code = f"""
            {coords}
            {texCoord}
            bpy.data.images.load(filepath={self.inputs["Asset"].python_value}, check_existing=True)
            
            def get_img_name():
                this = os.path.basename({self.inputs["Asset"].python_value})
                for i in range(len(bpy.data.images)):
                    if bpy.data.images[i].name == bpy.data.images[this].name:
                        return bpy.data.images[i]

            texture = gpu.texture.from_image(get_img_name())
            blender_version = bpy.app.version
            if blender_version >= (4, 0, 0):
                shader = gpu.shader.from_builtin('IMAGE')
            else:
                shader = gpu.shader.from_builtin('2D_IMAGE')

            batch = gpu_extras.batch.batch_for_shader(
                shader, 'TRI_FAN',
                {{
                    "pos": coords,
                    "texCoord": texCoord,
                }},
            )

            shader.bind()
            gpu.state.blend_set('ALPHA')
            shader.uniform_sampler("image", texture)
            batch.draw(shader)
            {self.indent(self.outputs[0].python_value, 3)}
        """
