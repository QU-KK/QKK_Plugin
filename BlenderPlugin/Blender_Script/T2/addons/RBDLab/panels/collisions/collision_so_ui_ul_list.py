from bpy.types import UIList
# from ..my_ui_ul_list import MY_UI_UL_list
from bpy.props import StringProperty, BoolProperty


class COLLISION_SO_UL_group(UIList):
    filter_by_name: StringProperty(default="", options={'TEXTEDIT_UPDATE'})
    order_by_name: BoolProperty(default=True)
    use_filter_sort_reverse: BoolProperty(default=False)
    case_sensitive: BoolProperty(default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if not item.data:
            layout.prop(item, "remove", text="This object is no longer available", icon='X')
            return
        obj = item.data
        main_row = layout.row(align=True)
        main_row.use_property_split = False
        main_row.use_property_decorate = False

        main_row.separator()

        main_row.prop(item, "visible", text="", icon='HIDE_ON' if item.visible else 'HIDE_OFF', emboss=False)

        sel_obj = main_row.row(align=True)
        sel_obj.prop(item, "select_obj", text="",
                     icon='RESTRICT_SELECT_OFF' if item.select_obj else 'RESTRICT_SELECT_ON', emboss=False)
        sel_obj.enabled = not item.visible

        main_row.separator()
        main_row.prop(obj, "name", text="", emboss=False, icon_value=layout.icon(obj))
        # prevent rename object:
        # row.label(text=obj.name, icon_value=layout.icon(obj))

        rm_button = main_row.row(align=True)
        rm_button.alignment = 'RIGHT'
        rm_button.alert = True
        rm_button.prop(item, "remove", text="", emboss=False, icon='X')

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
        objects = data.get_all_objects()

        # Default return values.
        filtered = []
        ordered = []
        items = getattr(data, propname)

        # Filtering by name
        if self.filter_name:
            # (pattern, bitflag, items, propname="name", flags=None, reverse=False)
            filtered = MY_UI_UL_list.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, objects, propname="name",
                reverse=self.use_filter_sort_reverse, case_sensitive=self.case_sensitive)

        if not filtered:
            filtered = [self.bitflag_filter_item] * len(items)

        ordered = MY_UI_UL_list.sort_items_by_name(objects, "name")

        # print("filtered, ordered:", filtered, ordered)

        return filtered, ordered
    '''

    def invoke(self, context, event):
        pass
