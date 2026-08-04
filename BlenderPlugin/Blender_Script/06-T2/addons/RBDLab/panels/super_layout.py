

class SuperLayout():
    def __init__(self, layout: "UILayout", parent: "SuperLayout" = None) -> "SuperLayout":
        self.layout = layout
        self.parent = parent

    def parent(self) -> "SuperLayout":
        return self.parent if self.parent is not None else self

    def separator(self) -> "SuperLayout":
        self.layout.separator()
        return self

    def alert(self, state: bool = False) -> "SuperLayout":
        self.layout.alert = state
        return self

    def use_split(self, state: bool = True):
        self.layout.use_property_split = state
        return self

    def scale(self, value: float = 1) -> "SuperLayout":
        self.layout.scale_y = value
        return self

    def label(self, *args, **kwargs) -> "SuperLayout":
        self.layout.label(*args, **kwargs)
        return self

    def prop(self, *args, **kwargs) -> "SuperLayout":
        self.layout.prop(*args, **kwargs)
        return self

    def operator(self, *args, **kwargs) -> "SuperLayout":
        self.layout.operator(*args, **kwargs)
        return self

    def grid_flow(self, *args, **kwargs) -> "SuperLayout":
        return SuperLayout(self.layout.grid_flow(*args, **kwargs), self)

    def column_flow(self, *args, **kwargs) -> "SuperLayout":
        return SuperLayout(self.layout.column_flow(*args, **kwargs), self)

    def row(self, *args, **kwargs) -> "SuperLayout":
        return SuperLayout(self.layout.row(*args, **kwargs), self)

    def column(self, enabled: bool = True, *args, **kwargs) -> "SuperLayout":
        return SuperLayout(self.layout.column(*args, **kwargs), self)

    def enabled(self, enabled: bool = False) -> "SuperLayout":
        self.layout.enabled = enabled
        return self

    def box(self) -> "SuperLayout":
        return SuperLayout(self.layout.box(), self)

    def section_custom(self) -> "SuperLayout":
        section = self.column(align=True)
        self.header = section.box().row()
        self.content = section.box().column(align=True)
        return self

    def section(self, title: str, icon: str = "", attached: bool = True, use_split: bool = True) -> "SuperLayout":
        if not attached:
            self.separator()
        section = self.column(align=True)
        section.box().label(text=title, icon=icon) # Header.
        return section.box().column(align=True).use_split(use_split) # Content.
        # Lo que es lo mismo que...
        # self.column(align=True).box().label(text=title, icon=icon).parent().box().column(align=True).use_split(use_split)

    def set_emboss_normal(self):
        self.layout.emboss = 'NORMAL'
        return self

    def set_emboss_none(self):
        self.layout.emboss = 'NONE'
        return self

    def set_emboss_pulldown(self):
        self.layout.emboss = 'PULLDOWN_MENU'
        return self

    def get(self) -> "UILayout":
        return self.layout

    def __call__(self) -> "UILayout":
        return self.layout
