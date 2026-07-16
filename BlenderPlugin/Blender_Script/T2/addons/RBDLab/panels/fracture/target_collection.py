from ..main.module_panel import ModulePanel
from bpy.types import Panel
# from ...addon.paths import RBDLabPreferences


class TARGET_COLL_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'FRACTURE'
    bl_idname = "TARGET_COLL_PT_ui"
    bl_label = "Target Collection"

    def draw(self, context):
        layout = self.layout
        # rbdlab = context.scene.rbdlab
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        layout.use_property_split = True
        layout.use_property_decorate = False
        flow = layout.grid_flow(align=True)
        col = layout.column()

        # (data, property, search_data, search_property, text, text_ctxt, translate, icon)

        # col.prop_search(rbdlab, "target_collection", bpy.data, "collections", text="Target")
        # col.prop_search(rbdlab, "filtered_target_collection", bpy.data, "collections", text="Target")

        # col.prop(rbdlab, "show_boundingbox", text="Bounding Box")

        # col = flow.column()
        # col = layout.column(align=False, heading="Auto Smooth")
        # col.use_property_decorate = False
        # row = col.row(align=True)
        # sub = row.row(align=True)
        # sub.prop(rbdlab, "use_auto_smooth", text="")
        # sub = sub.row(align=True)
        # sub.active = rbdlab.use_auto_smooth
        # sub.prop(rbdlab, "auto_smooth", text="")

        # if addon_preferences.i_love_colors:
        #     row = col.row(align=True)
        #     row.alignment = 'EXPAND'
