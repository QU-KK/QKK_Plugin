import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_circle_2d
from math import radians, sin, cos
from mathutils import Vector, Matrix
from ..blender import ui_scale, dpi


class Draw3D:
    def draw_line(self, coords, color=(1, 1, 1, 1), line_width=1, depth_mode: str = "ALWAYS"):
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set(depth_mode)

        shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": coords, "color": (color, color)})
        shader.bind()
        shader.uniform_float("lineWidth", line_width * ui_scale())
        batch.draw(shader)

    def draw_line_blend(
        self,
        coords,
        color=((1, 0, 0, 1), (0, 0, 1, 1)),
        line_width=1,
        depth_mode: str = "ALWAYS",
    ):
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set(depth_mode)

        shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": coords, "color": color})
        shader.bind()
        shader.uniform_float("lineWidth", line_width * ui_scale())
        batch.draw(shader)

    def draw_polygon(self, coords, indices, color=(1, 1, 1, 0.5), depth_mode: str = "ALWAYS"):
        """
        Draw a smooth blend polygon in the viewport.
        """
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set(depth_mode)

        colors = [color] * len(coords)
        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": coords, "color": colors}, indices=indices)
        shader.uniform_float("color", color)
        shader.bind()
        batch.draw(shader)

    def draw_axis(self, context, object, axis):
        """Draw axis from the origin of the object.

        object (bpy.types.Object) - The object to draw the axis for.
        axis (str) - The axis to draw the line to.
        """
        if axis == "X":
            x = context.region.width
            y = object.location.y
            z = object.location.z
            coords = [(-x, y, z), (x, y, z)]
            color = (
                *bpy.context.preferences.themes["Default"].user_interface.axis_x,
                0.8,
            )
        elif axis == "Y":
            x = object.location.x
            y = context.region.width
            z = object.location.z
            coords = [(x, -y, z), (x, y, z)]
            color = (
                *bpy.context.preferences.themes["Default"].user_interface.axis_y,
                0.8,
            )
        elif axis == "Z":
            x = object.location.x
            y = object.location.y
            z = context.region.height
            coords = [(x, y, -z), (x, y, z)]
            color = (
                *bpy.context.preferences.themes["Default"].user_interface.axis_z,
                0.8,
            )

        gpu.state.blend_set("ALPHA")
        shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": coords, "color": color})
        shader.bind()
        shader.uniform_float("lineWidth", 2)
        shader.uniform_float("color", color)
        batch.draw(shader)
