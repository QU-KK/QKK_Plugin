from bpy.types import Object, PropertyGroup
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty, CollectionProperty, FloatVectorProperty

class Colors(PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0
    )


class ColorStack(PropertyGroup):
    name = "ColosStack"

    # usage:
    #     C.object.color_stack.add_color([1, 1, 1, 1])
    #     C.object.color_stack.add_color([2, 2, 2, 1])
    #     C.object.color_stack.add_color([3, 3, 3, 1])
    #     C.object.color_stack.get_color(0)
    #     C.object.color_stack.get_last_color()
    #     C.object.color_stack.get_all_colors()

    colors: CollectionProperty(type=Colors)

    def add_color(self, a_c):
        if a_c != self.get_last_color():
            _item = self.colors.add()
            _item.color = a_c

    def get_len_colors(self):
        return len(self.colors)

    def is_void(self):
        if self.get_len_colors() == 0:
            return True
        return False

    def overwrite_first_color(self, color: list):
        if self.get_len_colors() > 0:
            self.colors[0].color = color

    def get_color(self, index: int):
        if self.get_len_colors() > 0:
            color = self.colors[index].color
            return list(color)
        return None

    def get_last_color(self):
        if self.get_len_colors() > 0:
            last_color = self.colors[-1].color
            return list(last_color)
        return None

    def get_first_color(self):
        if self.get_len_colors() > 0:
            first_color = self.colors[0].color
            return list(first_color)
        return None

    def get_all_colors(self):
        if self.get_len_colors() > 0:
            tmp_a = []
            for col in self.colors:
                color = list(col.color)
                tmp_a.append(color)
            return list(tmp_a)
        return None

    def rm_color(self, color: list):
        if self.is_void():
            return None
        colors = self.get_all_colors()
        if color not in colors:
            return None
        idx = colors.index(color)
        self.colors.remove(idx)

    def rm_by_index_color(self, index: int):
        if self.is_void():
            return None
        self.colors.remove(index)

    def rm_last_color(self):
        if self.is_void():
            return None
        self.colors.remove(len(self.colors)-1)


def register():
    register_class(Colors)
    register_class(ColorStack)
    Object.color_data = CollectionProperty(type=Colors)
    Object.color_stack = PointerProperty(type=ColorStack)


def unregister():
    del Object.color_data
    del Object.color_stack
    unregister_class(Colors)
    unregister_class(ColorStack)
