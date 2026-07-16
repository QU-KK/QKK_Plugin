from ..main.module_panel import ModulePanel
from bpy.types import Panel


class SPEED_PT_visualizer(Panel, ModulePanel):
    rbdlab_section = 'PARTICLES'
    bl_label = "Speed Visualizer"
    bl_idname = "SPEED_PT_visualizer"
    # bl_parent_id = "PARTICLES_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}


    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        flow = layout.grid_flow(align=True)
        col = flow.column()

        # speed visualization
        col.separator()
        # col.label(text="Speed Visualization")
        # col.operator("rbdlab.speed_visualization", text="Speed Visualizer")
        # col.operator("rbdlab.speed_visualization_rm", text="Remove Speed Visualizer")