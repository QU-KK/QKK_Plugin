from bpy.types import UIList
# from bpy.types import UIList, UI_UL_list
from bpy.props import StringProperty, BoolProperty

'''
class MY_UI_UL_list(UI_UL_list):
    # Uso esta clase para poder filtrar con Case Sensitive/Insensitive 

    # These are common filtering or ordering operations (same as the default C ones!).
    @staticmethod
    def filter_items_by_name(pattern, bitflag, items, propname="name", flags=None, reverse=False, case_sensitive=True):

        import fnmatch

        if not pattern or not items:  # Empty pattern or list = no filtering!
            return flags or []

        if flags is None:
            flags = [0] * len(items)

        # Implicitly add heading/trailing wildcards.
        if case_sensitive == False:
            pattern = "*" + pattern.lower() + "*"
        else:
            pattern = "*" + pattern + "*"

        for i, item in enumerate(items):
            name = getattr(item, propname, None)

            # This is similar to a logical xor
            if case_sensitive == False:
                name = name.lower()

            if bool(name and fnmatch.fnmatch(name, pattern)) is not bool(reverse):
                flags[i] |= bitflag
        return flags

'''


class MAT_UL_work_group(UIList):
    filter_by_name: StringProperty(default="", options={'TEXTEDIT_UPDATE'})
    order_by_name: BoolProperty(default=True)
    use_filter_sort_reverse: BoolProperty(default=False)
    case_sensitive: BoolProperty(default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if not item.data:
            layout.prop(item, "remove", text="Clear", icon='X')
            return
        coll = item.data
        row = layout.row()
        row.prop(item, "selected", text="")

        # row.prop(coll, "name", text="", emboss=False, icon_value=layout.icon(coll))
        # prevent rename collections:
        row.label(text=coll.name, icon_value=layout.icon(coll))

        row = layout.row()
        row.alignment = 'RIGHT'
        row.prop(item, "remove", text="", emboss=False, icon='X')
    '''
    def draw_filter(self, context, layout):
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(self, "filter_name", text="")
        # subrow.prop(self, "case_sensitive", text="", icon='SORTALPHA')
        csb = subrow.row(align=True)
        csb.scale_x = 0.28
        csb.prop(self, "case_sensitive", text="Aa", toggle=True)

    def filter_items(self, context, data, propname):

        # coll_list = getattr(data, propname)  # RBDLab_PG_Materials.list
        collections = data.get_all_collections()

        # Default return values.
        filtered = []
        ordered = []
        items = getattr(data, propname)

        # Filtering by name
        if self.filter_name:
            # (pattern, bitflag, items, propname="name", flags=None, reverse=False)
            filtered = MY_UI_UL_list.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, collections, propname="name",
                reverse=self.use_filter_sort_reverse, case_sensitive=self.case_sensitive)

        if not filtered:
            filtered = [self.bitflag_filter_item] * len(items)

        ordered = MY_UI_UL_list.sort_items_by_name(collections, "name")

        # print("filtered, ordered:", filtered, ordered)

        return filtered, ordered
    '''

    def invoke(self, context, event):
        pass


class MAT_UL_dynamic_materials(UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        # assert(isinstance(item, bpy.types.MaterialSlot)
        # ob = data
        slot = item
        ma = slot.material

        layout.context_pointer_set("id", ma)
        layout.context_pointer_set("material_slot", slot)

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if ma:
                layout.prop(ma, "name", text="", emboss=False, icon_value=icon)
            else:
                layout.label(text="", icon_value=icon)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)
