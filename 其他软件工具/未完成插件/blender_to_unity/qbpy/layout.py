import bpy
from .blender import preferences, dpi_factor, panel, collapse_panels
from .draw.draw_text import DrawText
from .draw.draw_2d import Draw2D
import gc
import weakref


class Label(DrawText):
    def __init__(self, text, icon, position, dimension):
        self.text = text
        self.icon = icon
        self.position = position
        self.dimension = dimension

        self.draw_text(text=self.text, position=self.position)


class Row(Label, Draw2D):
    def __init__(self, align, position, dimension):
        self.align = align
        self.position = position
        self.dimension = dimension

    def label(self, text="", icon=""):
        return Label(text, icon, position=self.position, dimension=self.dimension)


class Layout(Row, Label, Draw2D):
    instances = []

    def __init__(self, context, event, position, dimension):
        self.__class__.instances.append(self)
        self.context = context
        self.event = event
        self.position = position
        self.dimension = dimension

        # self.draw_box(position=self.position, dimension=self.dimension, padding=(0, 0), background=None, corner=None)
        self.round_box()
        for instance in list(dict.fromkeys(self.__class__.instances)):
            instance.position[1] += 20
            print(instance.label, instance.position)

    def label(self, text, icon=""):
        return Label(text, icon, position=self.position, dimension=self.dimension)

    def row(self, align=False):
        return Row(align=align, position=self.position, dimension=self.dimension)


class Overlay:
    def overlay(self, context, event, position=None, dimension=(100, 30)):
        if position is None:
            position = [100, 100]
        return Layout(context, event, position, dimension)

    # background = bpy.context.preferences.themes['Default'].user_interface.wcol_tool.inner

    # def __init__(self, align):
    #     margin = 30
    #     self.padding = (10, 10)
    #     if align == 'LEFT':
    #         self.x = margin + panel('TOOLS')[0]
    #         self.y = margin
    #     elif align == 'CENTER':
    #         self.x = bpy.context.region.width/2 - 160/2
    #         self.y = margin
    #     elif align == 'RIGHT':
    #         self.x = bpy.context.region.width - (160 + margin + panel('UI')[0])
    #         self.y = margin
    #     self.draw_box((self.x, self.y), (160, margin), self.padding, self.background)

    # def label(self, text, icon=None):
    #     return self.Label((self.x, self.y), text, icon)

    # def prop(self, data, prop, text='NONE', icon='NONE', expand=False):
    #     return self.Prop((self.x, self.y), data, prop, text, icon, expand)

    # def column(self, align=False):
    #     return self.Column(align)

    # def row(self, align=False):
    #     return self.Row(align)

    # def seperator(self):
    #     pass

    # class Label(Draw2D, DrawText):
    #     def __init__(self, position, text, icon):
    #         self.draw_text(position, text)

    # class Prop(Draw2D, DrawText):
    #     def __init__(self, position, data, prop, text='NONE', icon='NONE', expand=False):
    #         x, y = position
    #         type = data.rna_type.properties[prop].type
    #         subtype = data.rna_type.properties[prop].subtype
    #         unit = data.rna_type.properties[prop].unit
    #         if text == 'NONE':
    #             name = data.rna_type.properties[prop].name
    #         else:
    #             name = text
    #         if type == 'BOOLEAN':
    #             tw = self.get_text_dims(name)[0]
    #             th = round(self.get_text_dims(name)[1])
    #             p = [8, 4]
    #             if expand:
    #                 bw = self.get_text_dims(name)[0] # box width
    #                 bh = 16 * dpi_factor() # box height
    #                 p = [8, 2]

    #                 if getattr(data, prop):
    #                     self.draw_box((x+p[0], y), (bw, bh), p, self.v3d_item_background_sel)
    #                     self.draw_text((x+p[0], y + ((bh - th) /2)), name, self.v3d_text_sel)
    #                 else:
    #                     self.draw_box((x+p[0], y), (bw, bh), p, self.v3d_item_background)
    #                     self.draw_text((x+p[0], y + ((bh - th) /2)), name, self.v3d_text_sel)

    #             else:
    #                 if icon == 'NONE':
    #                     self.draw_checkbox((x, y), default=getattr(data, prop))
    #                     self.draw_text((x+18*dpi_factor(), y + ((14*dpi_factor() - th) /2)), name, self.v3d_text_sel)
    #                 else:
    #                     iw = 16 * dpi_factor() # icon width
    #                     ih = iw # icon height
    #                     p = [2, 2]

    #                     if getattr(data, prop):
    #                         self.draw_box((x+p[0], y), (iw, ih), p, self.v3d_item_background_sel)
    #                     else:
    #                         self.draw_box((x+p[0], y), (iw, ih), p, self.v3d_item_background)
    #                     self.draw_image((x+p[0], y-p[1]/2*dpi_factor()), icon)

    # class Column:
    #     def __init__(self, align):
    #         pass

    #     def label(self, text, icon=None):
    #         return self.Label((self.x, self.y), text, icon)

    #     def prop(self, data, prop, text='NONE', icon='NONE', expand=False):
    #         return self.Prop((self.x, self.y), data, prop, text, icon, expand)

    # class Row:
    #     def __init__(self, align):
    #         pass

    #     def label(self, text, icon=None):
    #         return self.Label((self.x, self.y), text, icon)

    #     def prop(self, data, prop, text='NONE', icon='NONE', expand=False):
    #         return self.Prop((self.x, self.y), data, prop, text, icon, expand)
