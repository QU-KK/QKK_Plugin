import bpy
from bpy.types import NodeSocket


class Socket(NodeSocket):
    """Base Node Socket Class"""

    color = (0.5, 0.5, 0.5, 1)
    compatible_sockets = []

    @property
    def display_name(self):
        """Get the display name of the socket"""

        label = self.text if self.text != "" else self.name
        if self.is_output:
            label += f": {self.ui_value}"
        return label

    def draw(self, context, layout, node, text):
        col = layout.column(align=1)
        if self.is_linked or self.is_output:
            layout.label(text=self.display_name)
        else:
            col.prop(self, "default_value", text=self.display_name)  # column for vector

    def draw_color(self, context, node):
        return self.color
