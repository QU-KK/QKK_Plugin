from bpy.types import UIList
# from ..my_ui_ul_list import MY_UI_UL_list
from bpy.props import StringProperty, BoolProperty


class CONST_UL_const_group(UIList):
    filter_by_name: StringProperty(default="", options={'TEXTEDIT_UPDATE'})
    order_by_name: BoolProperty(default=True)
    use_filter_sort_reverse: BoolProperty(default=False)
    case_sensitive: BoolProperty(default=False)

    def draw_item(self, context, layout, data, group, icon, active_data, active_propname, index):
        
        group_coll = group.collection
        if not group_coll:
            layout.prop(group, "remove", text="Clear", icon='X')
            return
        
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        row = layout.row(align=True)
        _row = row.row()
        _row.ui_units_x = 1

        if context.scene.rbdlab.ui.main_modules == 'CONSTRAINTS':
            _row.prop(group, "icon", text="", emboss=False)
            _row = row.row()
            
            icon = 'RESTRICT_SELECT_OFF' if group.type == 'SELECTION' else 'MOD_BUILD' if group.type == 'CLUSTER' else 'CON_OBJECTSOLVER' if group.type == 'INTER_CLUSTER' else 'UV_FACESEL' if group.type == 'ADJACENTS' else 'OUTLINER_COLLECTION'
            _row = row.row()
            _row.label(text="", icon=icon)
        
            _row.ui_units_x = 1.0

            row = layout.row()
            _row = row.row()
            _row.ui_units_x = 0.3
            _row.label(text="|")
            _row.enabled = False
            _row = row.row(align=True)
            _row.ui_units_x = 1

        # Dependiendo de si estamos mostrando el listado en Constraints o en Activators usamos un checkbox u otro:
        checkbox_text_mapping = {
            'CONSTRAINTS': "enabled",
            'ACTIVATORS': "compute",
        }
        bool_target = checkbox_text_mapping[ui.main_modules]
        _row.prop(group, bool_target, text="")

        row = layout.row(align=True)
        row.prop(group, "name", text="", emboss=False)

        row = layout.row(align=True)
        row.alignment = 'RIGHT'
        _row = row.row(align=True)
        _row.enabled = getattr(group, bool_target)       

        if group.type == 'CLUSTER':
            # _row.ui_units_x = 2.5
            # _row.prop(group, "cluster_select", text="", emboss=False)
            _row.prop(group, "select_cluster_by_chunk", text="", icon='PMARKER_SEL', emboss=True)
            _row.prop(group, "show_clusters", text="", icon='SHADERFX', emboss=True)

        _row.prop(group, "visible", text="", icon='HIDE_OFF' if group.visible else 'HIDE_ON', emboss=True)

        # condition = any([group.selection, context.selected_objects])
        # print(context.scene.rbdlab.constraints.get_active_group)
        # print(group.name)
        _row.prop(group, "selection", text="", icon='RESTRICT_SELECT_OFF' if group.selection else 'RESTRICT_SELECT_ON', emboss=True)

        _row.separator(factor=0.5)

        if context.scene.rbdlab.ui.main_modules == 'CONSTRAINTS':
            rm_bt = row.row(align=True)
            rm_bt.alignment = 'RIGHT'
            rm_bt.alert = True
            rm_bt.operator("rbdlab.rm_constraint_group", text="", emboss=False, icon='X').to_rm=group.collection.name

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

            if item:

                if self.case_sensitive:
                    match = self.filter_name in item.name
                else:
                    match = self.filter_name.lower() in item.name.lower()

                if match:
                    filtered_flags.append(self.bitflag_filter_item)
                else:
                    filtered_flags.append(0)

        # print(filtered_flags, new_order)
        return filtered_flags, new_order
