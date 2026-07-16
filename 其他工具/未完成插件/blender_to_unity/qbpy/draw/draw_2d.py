import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from math import radians, sin, cos
from mathutils import Vector
from ..blender import ui_scale, icons_dir


class Draw2D:
    OPTION_INNER = bpy.context.preferences.themes["Default"].user_interface.wcol_option.inner
    TOOL_INNER_SEL = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner_sel
    LINE_WIDTH = bpy.context.preferences.system.ui_line_width
    if bpy.app.version >= (4, 0, 0):
        TOOL_OUTLINE = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.outline
    else:
        TOOL_OUTLINE = (
            *bpy.context.preferences.themes["Default"].user_interface.wcol_tool.outline[:3],
            1.0,
        )

    def __box(self, position, dimension, padding, corner):
        """Create a box with rounded corners.

        position (2D Vector) - Position where the box will be drawn.
        dimension (tuple) - Size of the box.
        padding (tuple) - Padding of the box.
        corner ([BOTTOM_LEFT, BOTTOM_RIGHT, TOP_RIGHT, TOP_LEFT], booleans) - Draw corners.
        return (list) - coords, indices, line_indices.
        """
        if corner is True:
            corner = [True, True, True, True]
        elif corner is False:
            corner = [False, False, False, False]
        x, y = position
        width, height = dimension
        p = padding
        radius = bpy.context.preferences.themes["Default"].user_interface.wcol_regular.roundness * 10
        smooth = 5

        bl_corner = []
        if corner[0]:
            bl_corner.extend(
                (
                    x - p[0] + radius + radius * cos(radians(i)),
                    y - p[1] + radius + radius * sin(radians(i)),
                )
                for i in range(180, 270, smooth)
            )
        else:
            bl_corner.append((x - p[0], y - p[1]))

        br_corner = []
        if corner[1]:
            br_corner.extend(
                (
                    x + p[0] + width - radius + radius * cos(radians(i)),
                    y - p[1] + radius + radius * sin(radians(i)),
                )
                for i in range(270, 360, smooth)
            )
        else:
            br_corner.append((x + width + p[0], y - p[1]))

        tr_corner = []
        if corner[2]:
            tr_corner.extend(
                (
                    x + p[0] + width - radius + radius * cos(radians(i)),
                    y + p[1] + height - radius + radius * sin(radians(i)),
                )
                for i in range(0, 90, smooth)
            )
        else:
            tr_corner.append((x + width + p[0], y + height + p[1]))

        tl_corner = []
        if corner[3]:
            tl_corner.extend(
                (
                    x - p[0] + radius + radius * cos(radians(i)),
                    y + p[1] + height - radius + radius * sin(radians(i)),
                )
                for i in range(90, 180, smooth)
            )
        else:
            tl_corner.append((x - p[0], y + height + p[1]))

        coords = bl_corner + br_corner + tr_corner + tl_corner
        indices = [(0, x + 1, x + 2) for x in range(len(coords) - 2)]
        line_indices = [(x, (x + 1) % len(coords)) for x in range(len(coords))]
        tex_coord = [
            (
                (coord[0] - position[0]) / dimension[0],
                (coord[1] - position[1]) / dimension[1],
            )
            for coord in coords
        ]

        return coords, indices, line_indices, tex_coord

    def shader(self, coords, indices=None, type="POINTS", color=None, line_width=2):
        """Shader for drawing.

        coords (list) - List of coordinates.
        indices (list, optional) - List of indices.
        type (str, optional) - Type of drawing.
        builtin (str, optional) - Builtin shader.
        color (tuple, optional) - Color of the drawing.
        line_width (int, optional) - Width of the line.
        """
        if type in {"LINES", "LINE_STRIP", "LINE_LOOP"}:
            gpu.state.blend_set("ALPHA")
            gpu.state.line_width_set(line_width)

        gpu.state.blend_set("ALPHA")
        builtin = "UNIFORM_COLOR"

        shader = gpu.shader.from_builtin(builtin)
        if indices:
            batch = batch_for_shader(shader, type, {"pos": coords}, indices=indices)
        else:
            batch = batch_for_shader(shader, type, {"pos": coords})

        shader.bind()
        shader.uniform_float("color", (1, 1, 1, 1) if color is None else color)
        batch.draw(shader)

    def image_shader(self, coords, indices=None, texture=None, color=(0, 0, 0, 0)):
        """Shader for drawing.

        coords (list) - List of coordinates.
        indices (list, optional) - List of indices.
        color (tuple, optional) - Color of the drawing.
        """
        gpu.state.blend_set("ALPHA")
        builtin = "IMAGE_COLOR"

        shader = gpu.shader.from_builtin(builtin)
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": coords, "texCoord": indices})  #'texCoord': ((0, 0), (1, 0), (1, 1), (0, 1))
        shader.bind()
        shader.uniform_sampler("image", texture)
        shader.uniform_sampler("color", color)
        batch.draw(shader)

    def draw_box(self, position, dimension, padding=(0, 0), background=None, corner=True):
        """Draw a box with rounded corners.

        position (2D Vector) - Position where the box will be drawn.
        dimension (tuple) - Size of the box.
        padding (tuple) - Padding of the box.
        background (tuple containing RGBA values) - Color of the box.
        corner ([BOTTOM_LEFT, BOTTOM_RIGHT, TOP_RIGHT, TOP_LEFT], booleans) - Draw corners.
        """
        coords, indices, line_indices, tex_coord = self.__box(position, dimension, padding, corner)
        self.shader(
            coords,
            indices=indices,
            type="TRIS",
            color=bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner if background is None else background,
        )
        self.shader(
            coords,
            indices=line_indices,
            type="LINES",
            color=self.TOOL_OUTLINE,
            line_width=self.LINE_WIDTH,
        )

    def selected(self, position, dimension, padding, corner=None, pause_modal=False):
        """Draw a selected box with rounded corners.

        position (2D Vector) - Position where the box will be drawn.
        dimension (tuple) - Size of the box.
        padding (tuple) - Padding of the box.
        background (tuple containing RGBA values) - Color of the box.
        corner ([BOTTOM_LEFT, BOTTOM_RIGHT, TOP_RIGHT, TOP_LEFT], booleans) - Draw corners.
        """
        if corner is None:
            corner = [True, True, True, True]
        coords, indices, line_indices, tex_coord = self.__box(position, dimension, padding, corner)

        if pause_modal:
            background = (*self.TOOL_INNER_SEL[:3], 0.5)
            self.shader(coords, indices=indices, type="TRIS", color=background)
            self.shader(
                coords,
                indices=line_indices,
                type="LINES",
                color=background,
                line_width=self.LINE_WIDTH,
            )
        else:
            self.shader(coords, indices=indices, type="TRIS", color=self.TOOL_INNER_SEL)
            self.shader(
                coords,
                indices=line_indices,
                type="LINES",
                color=self.TOOL_INNER_SEL,
                line_width=self.LINE_WIDTH,
            )

    def draw_checkbox(self, position, default=False, pause_modal=False):
        """Draw a checkbox.

        position (2D Vector) - Position where the checkbox will be drawn.
        default (bool, optional) - Default state of the checkbox.
        """
        x, y = position
        dimension = (14 * ui_scale(), 14 * ui_scale())
        width, height = dimension
        padding = (0, 0)

        if default:
            if pause_modal:
                background = (*self.TOOL_INNER_SEL[:3], 0.5)
                self.draw_box(position, dimension, padding, background)
            else:
                self.draw_box(position, dimension, padding, self.TOOL_INNER_SEL)
        elif pause_modal:
            background = (*self.OPTION_INNER[:3], 0.5)
            self.draw_box(position, dimension, padding, background)
        else:
            background = self.OPTION_INNER
            self.draw_box(position, dimension, padding, background)

        if default:
            l = (x + (width / 4), y + (height / 2.3))
            b = (x + (width / 2.3), y + (height / 2) / 2)
            r = (x + (width / 2) + (width / 3.5), y + (height / 2) + (height / 4.5))

            if pause_modal:
                background = (
                    *bpy.context.preferences.themes["Default"].user_interface.wcol_option.item[:3],
                    0.5,
                )
                self.shader(
                    (l, b, r),
                    type="LINE_STRIP",
                    color=background,
                    line_width=self.LINE_WIDTH + 0.5,
                )
            else:
                background = bpy.context.preferences.themes["Default"].user_interface.wcol_option.item
                self.shader(
                    (l, b, r),
                    type="LINE_STRIP",
                    color=background,
                    line_width=self.LINE_WIDTH + 0.5,
                )

    def draw_image(self, image, position, dimension=(16, 16), border=None, corner=None):
        """Draw an image.

        position (2D Vector) - Position where the image will be drawn.
        image (str, optional) - Image to draw.
        texture (gpu.types.GPUTexture) - GPUTexture to draw (e.g. gpu.texture.from_image(image) for bpy.types.Image).
        """
        img = bpy.data.images.load(icons_dir() + image + ".png", check_existing=True)
        texture = gpu.texture.from_image(img)

        if corner is None:
            corner = [True, True, True, True]
        coords, indices, line_indices, tex_coord = self.__box(position, dimension, padding=(0, 0), corner=corner)

        self.shader(coords, indices=tex_coord, type="TRI_FAN", builtin="IMAGE", texture=texture)
        if border:
            self.shader(
                coords,
                indices=line_indices,
                type="LINES",
                color=self.TOOL_OUTLINE,
                line_width=self.LINE_WIDTH,
            )

        if image and img.gl_load():
            raise Exception()

        bpy.data.images.remove(img)

    def draw_preview(self, texture, position, dimension=(16, 16), border=None, corner=None):
        """Draw an image.

        position (2D Vector) - Position where the image will be drawn.
        image (str, optional) - Image to draw.
        texture (gpu.types.GPUTexture) - GPUTexture to draw (e.g. gpu.texture.from_image(image) for bpy.types.Image).
        """
        if corner is None:
            corner = [True, True, True, True]
        coords, indices, line_indices, tex_coord = self.__box(position, dimension, padding=(0, 0), corner=corner)

        self.image_shader(coords, indices=tex_coord, texture=texture)
        if border:
            self.shader(
                coords,
                indices=line_indices,
                type="LINES",
                color=self.TOOL_OUTLINE,
                line_width=self.LINE_WIDTH,
            )

    # WIP

    # def round_box(self, position=(500, 500), dimension=(200, 200), corner=None):
    #     '''Draw round box

    #     position (2D Vector) - Position where the box will be drawn.
    #     dimension (tuple) - Size of the box.
    #     corner ([BOTTOM_LEFT, BOTTOM_RIGHT, TOP_RIGHT, TOP_LEFT], booleans) - Draw corners.
    #     '''
    #     vertices = (
    #         (position[0], position[1]), # bl
    #         (position[0] + dimension[0], position[1]), # br
    #         (position[0], position[1] + dimension[1]), # tl
    #         (position[0] + dimension[0], position[1] + dimension[1])) # tr

    #     indices = (
    #         (0, 1, 2), (2, 1, 3))

    #     vertex_shader = '''
    #         uniform mat4 ModelViewProjectionMatrix;
    #         in vec2 pos;

    #         void main()
    #         {
    #             gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0, 1.0);
    #         }
    #     '''

    #     fragment_shader = '''
    #         uniform vec3 color;
    #         uniform float alpha;

    #         out vec4 FragColor;

    #         void main() {
    #             FragColor = vec4(color, alpha);
    #             FragColor = blender_srgb_to_framebuffer_space(FragColor);
    #         }
    #     '''

    #     shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
    #     batch = batch_for_shader(shader, 'TRIS', {'pos': vertices}, indices=indices)

    #     shader.bind()
    #     shader.uniform_float('color', (0, 1, 1))
    #     shader.uniform_float('alpha', 1)
    #     # shader.uniform_float('outline', 1)
    #     # shader.uniform_float('outline_color', (0.8, 0.8, 0.8))
    #     # shader.uniform_float('radius', 4)
    #     batch.draw(shader)

    # def round_box(self, position=(500, 500), dimension=(200, 200), corner=None):
    #     '''Draw round box

    #     position (2D Vector) - Position where the box will be drawn.
    #     dimension (tuple) - Size of the box.
    #     corner ([BOTTOM_LEFT, BOTTOM_RIGHT, TOP_RIGHT, TOP_LEFT], booleans) - Draw corners.
    #     '''
    #     vertices = (
    #         (position[0], position[1]), # bl
    #         (position[0] + dimension[0], position[1]), # br
    #         (position[0], position[1] + dimension[1]), # tl
    #         (position[0] + dimension[0], position[1] + dimension[1])) # tr

    #     indices = (
    #         (0, 1, 2), (2, 1, 3))

    #     vertex_shader = '''
    #         uniform mat4 ModelViewProjectionMatrix;
    #         in vec2 pos;

    #         void main() {
    #             gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0, 1.0);
    #         }
    #     '''

    #     fragment_shader = '''

    #         float rounded_box_SDF(vec2 center_position, vec2 size, float radius) {
    #             return length(max(abs(center_position) - size + radius, 0.0)) - radius;
    #         }

    #         void main() {
    #             out vec4 FragColor;

    #             vec2 size = vec2(300.0, 50.0);

    #             vec2 location = vec2(100, 100);

    #             float edgeSoftness  = 1.0;

    #             float radius = 4.0;

    #             float distance = rounded_box_SDF(gl_FragCoord.xy - location - size, size, radius);

    #             float smoothedAlpha = 1.0 - smoothstep(0.0, edgeSoftness * 2.0, distance);

    #             vec4 quadColor = mix(vec4(0.5, 0.5, 0.5, 1.0), vec4(vec3(0.239216), smoothedAlpha), smoothedAlpha);

    #             float shadowSoftness = 4.0;
    #             vec2 shadowOffset = vec2(0, 2);
    #             float shadowDistance = rounded_box_SDF(gl_FragCoord.xy - location + shadowOffset - size, size, radius);
    #             float shadowAlpha = 1.0 - smoothstep(-shadowSoftness, shadowSoftness, shadowDistance);
    #             vec4 shadowColor = vec4(vec3(0.239216), 1.0);
    #             vec3 fragColor = vec3(mix(quadColor, shadowColor, shadowAlpha - smoothedAlpha));

    #             FragColor = vec4(fragColor, 1.0);
    #             FragColor = blender_srgb_to_framebuffer_space(FragColor);
    #         }
    #     '''

    #     shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
    #     batch = batch_for_shader(shader, 'TRIS', {'pos': vertices}, indices=indices)

    #     shader.bind()
    #     batch.draw(shader)
