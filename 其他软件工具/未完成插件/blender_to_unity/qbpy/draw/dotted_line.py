import bpy
import gpu
from gpu_extras.batch import batch_for_shader


class DrawDotLine:
    def __init__(self):
        self.vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
        self.vert_out.smooth("FLOAT", "v_ArcLength")

        self.shader_info = gpu.types.GPUShaderCreateInfo()
        self.shader_info.push_constant("MAT4", "ModelViewProjectionMatrix")
        self.shader_info.push_constant("FLOAT", "u_Scale")
        self.shader_info.vertex_in(0, "VEC3", "position")
        self.shader_info.vertex_in(1, "FLOAT", "arcLength")
        self.shader_info.vertex_out(self.vert_out)
        self.shader_info.fragment_out(0, "VEC4", "FragColor")

        self.shader_info.vertex_source(
            "void main()" "{" "  v_ArcLength = arcLength;" "  gl_Position = ModelViewProjectionMatrix * vec4(position, 1.0f);" "}"
        )

        self.shader_info.fragment_source(
            "void main()" "{" "  if (step(sin(v_ArcLength * u_Scale), 0.5) == 1) discard;" "  FragColor = vec4(1.0);" "}"
        )

        self.dotted_shader = gpu.shader.create_from_info(self.shader_info)

    def draw(self, coords, color=(1, 1, 1, 1), line_width=1):
        """
        Draw a dotted line.

        coords (3D Vector) - The coordinates of the dot.
        color (tuple containing RGBA) - The color of the dot.
        line_width (int) - Line width of the dotted line.
        """
        position = [Vector(coords[0]), Vector(coords[1])]
        arc_lengths = [0]

        for a, b in zip(position[:-1], position[1:]):
            arc_lengths.append(arc_lengths[-1] + (a - b).length)

        batch = batch_for_shader(
            self.dotted_shader,
            "LINES",
            {"position": position, "arcLength": arc_lengths},
        )
        self.dotted_shader.uniform_float("u_Scale", 30)
        batch.draw(self.dotted_shader)
