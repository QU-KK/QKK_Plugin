from bpy.types import UIList
# from ..my_ui_ul_list import MY_UI_UL_list
from bpy.props import StringProperty, BoolProperty


class CONST_UL_work_group(UIList):
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

        # no permitir renombrar la collection:
        row.label(text=coll.name, icon_value=layout.icon(coll))
        # row.prop(coll, "name", text="", emboss=False, icon_value=layout.icon(coll))

        row = layout.row()
        row.alignment = 'RIGHT'
        row.prop(item, "remove", text="", emboss=False, icon='X')

    def draw_filter(self, context, layout):
        """UI code for the filtering/sorting/search area."""
        layout.separator()
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "filter_name", text="", icon='VIEWZOOM')
        case_sensititve = row.row(align=True)
        case_sensititve.scale_x = 0.35
        case_sensititve.prop(self, "case_sensitive", toggle=True, text="aA")
        row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)

        filtered_flags = []
        new_order = [i for i in range(len(items))]

        for item in items:

            if item.data:

                if self.case_sensitive:
                    match = self.filter_name in item.data.name
                else:
                    match = self.filter_name.lower() in item.data.name.lower()

                if match:
                    filtered_flags.append(self.bitflag_filter_item)
                else:
                    filtered_flags.append(0)

        # print(filtered_flags, new_order)
        return filtered_flags, new_order
