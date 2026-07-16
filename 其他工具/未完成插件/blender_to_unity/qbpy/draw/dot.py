import bpy
import gpu
from gpu_extras.batch import batch_for_shader


class DrawDot:
    def __init__(self):
        self.shader_info = gpu.types.GPUShaderCreateInfo()
        self.shader_info.vertex_in(0, "VEC3", "pos")
        self.shader_info.push_constant("MAT4", "ModelViewProjectionMatrix")
        self.shader_info.push_constant("VEC3", "color")
        self.shader_info.push_constant("VEC3", "outline")
        self.shader_info.push_constant("FLOAT", "alpha")
        self.shader_info.fragment_out(0, "VEC4", "FragColor")

        self.shader_info.vertex_source("void main()" "{" "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f);" "}")

        self.shader_info.fragment_source(
            "void main()"
            "{"
            "  float offset = 0.5;"
            "  float dist = distance(gl_PointCoord, vec2(offset));"
            "  float line_thickness = 0.35;"
            "  float line = smoothstep(offset, line_thickness, dist) * smoothstep(line_thickness, offset, dist);"
            "  float point = (1.0 - smoothstep(0.425, 1.0, dist + 0.125) / fwidth(gl_PointCoord)).x;"
            "  FragColor = vec4(mix(outline, color, point), max(line * 3.3 * (alpha * 2), point * alpha));"
            "}"
        )

        self.dot_shader = gpu.shader.create_from_info(self.shader_info)

    def draw(
        self,
        coords,
        type: str = "CIRCLE",
        size: float = 12,
        color: tuple = (0.8, 0.8, 0.8),
        outline: tuple = (0, 0, 0),
        alpha: float = 1,
        depth_mode: str = "ALWAYS",
    ):
        """Draw a dot at the given coordinates.

        coords (3D Vector) - The coordinates of the dot.
        size (int) - The size of the dot.
        color (tuple containing RGB) - The color of the dot.
        outline (tuple containing RGB) - The color of the dot outline.
        alpha (float) - The alpha of the dot.
        """

        gpu.state.blend_set("ALPHA")
        gpu.state.point_size_set(size)
        gpu.state.depth_test_set(depth_mode)

        if type == "CIRCLE":
            batch = batch_for_shader(self.dot_shader, "POINTS", {"pos": coords})
            self.dot_shader.uniform_float("color", color)
            self.dot_shader.uniform_float("outline", outline)
            self.dot_shader.uniform_float("alpha", alpha)
        elif type == "SQUARE":
            self.dot_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(self.dot_shader, "POINTS", {"pos": coords})
            self.dot_shader.bind()
            self.dot_shader.uniform_float("color", (*color, alpha))

        batch.draw(self.dot_shader)
