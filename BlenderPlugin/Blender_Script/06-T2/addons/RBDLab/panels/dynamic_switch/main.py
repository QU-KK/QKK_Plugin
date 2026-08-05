from bpy.types import Panel
from ..main.module_panel import ModulePanel
# from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header

from .dswitch_dparent_panel import dswitch_dparent_panel
from .dswitch_visual_switching_panel import dswitch_visual_switching_panel

class DYNAMIC_SWITCH_MAIN_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'DSWITCH'
    bl_label = "Module"
    bl_idname = "DYNAMIC_SWITCH_MAIN_PT_ui"

    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        layout = self.layout

        col = layout.column(align=True)
        title_header(col, "Dynamic Switch")
        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        subsections_sw = main_col.row(align=True)
        subsections_sw.scale_y = 1.3
        subsections_sw.prop(ui, "dswitch_subsections", expand=True)
        # main_col.separator()

        main_col = col.box().column(align=True)
        main_col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        if ui.dswitch_subsections == 'DYNAMIC_PARENT':
            dswitch_dparent_panel(context, scn, rbdlab, ui, main_col)

        elif ui.dswitch_subsections == 'VISUAL_SWITCHING':
            dswitch_visual_switching_panel(rbdlab, ui, main_col)
        
