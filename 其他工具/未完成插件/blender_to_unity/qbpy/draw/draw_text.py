import bpy, blf
from ..blender import preferences, dpi, ui_scale


class DrawText:
    text_color = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text

    def draw_text(self, position, text="Hello World", text_color=(1, 1, 1), text_size=None):
        """Draw text.

        position (2D Vector) - Position to draw text at.
        text (str) - Text to draw.
        text_color (tuple containing RGB values, optional) - Color of text.
        text_size (int, optional) - Size of text.
        """
        prefs = preferences()
        if text_size is None:
            text_size = bpy.context.preferences.ui_styles[0].widget.points
        x, y = position
        font_id = 0
        blf.enable(font_id, blf.SHADOW)
        blf.shadow(font_id, 3, 0, 0, 0, 0.5)
        blf.shadow_offset(font_id, 0, -1)

        if bpy.app.version >= (4, 0, 0):
            blf.size(font_id, text_size * ui_scale())
        else:
            blf.size(font_id, text_size, dpi())

        r, g, b = text_color
        blf.color(font_id, r, g, b, 1)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)

    def get_text_dims(self, text, text_size=None) -> tuple:
        """Get text dimensions.

        text (str) - Text to get dimensions for.
        text_size (int, optional) - Size of text.
        return (tuple) - Dimension of the text in pixels.
        """
        if text_size is None:
            text_size = bpy.context.preferences.ui_styles[0].widget.points
        font_id = 0

        if bpy.app.version >= (4, 0, 0):
            blf.size(font_id, text_size * ui_scale())
        else:
            blf.size(font_id, text_size, dpi())

        return blf.dimensions(font_id, text)
