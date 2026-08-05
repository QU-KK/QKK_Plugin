from ..main.module_panel import ModulePanel
from bpy.types import Panel


class CF_PT_recursive_shatter_ui(Panel, ModulePanel):
    rbdlab_section = 'FRACTURE'
    bl_label = "Recursive Shatter"
    bl_idname = "CF_PT_recursive_shatter_ui"
    bl_parent_id = "FRACTURE_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rbdlab = context.scene.rbdlab

        layout.use_property_split = True
        layout.use_property_decorate = False
        flow = layout.grid_flow(align=True)

        obj = context.active_object
        objects = len(context.selected_objects)

        col = flow.column()

        col.prop(rbdlab, "rbdlab_cf_recursion", text="Recursion")
        col.prop(rbdlab, "rbdlab_cf_recursion_source_limit", text="Recursion Source Limit")
        col.prop(rbdlab, "rbdlab_cf_recursion_clamp", text="Recursion Clamp")

        rowsub = col.row()
        rowsub.prop(rbdlab, "rbdlab_cf_recursion_chance")
        rowsub = col.row()
        rowsub.prop(rbdlab, "rbdlab_cf_recursion_chance_select", expand=True)
        if obj and objects:
            if obj.type == 'MESH':
                col.enabled = True
            else:
                col.enabled = False
