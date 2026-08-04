from ...Global.get_common_vars import get_common_vars

from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ..common_ui_elements import title_header, cheker_item_visibility

from .prepare.paint_tools import paint_tools
from .scatter.scatter import scatter
from .fracture import fracture
from .fracture_details import fracture_details


class FRACTURE_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'FRACTURE'
    bl_label = "Module"
    bl_idname = "FRACTURE_PT_ui"

    def draw(self, context):

        rbdlab, ui = get_common_vars(context, get_rbdlab=True, get_ui=True)

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.enabled = cheker_item_visibility(context)

        col = layout.column(align=True)
        title_header(col, "Fracture")
        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        switcher = main_col.row(align=True)
        switcher.use_property_split = False
        switcher.scale_y = 1.3
        switcher.prop(ui, "fracture_switch_subsections", expand=True)
        # main_col.separator()
        

        if ui.fracture_switch_subsections == 'PREPARE':
            paint_tools(context, rbdlab, col, ui)

        elif ui.fracture_switch_subsections == 'SCATTER':
            scatter(context, rbdlab, col)

        elif ui.fracture_switch_subsections == 'FRACTURE':
            fracture(context, col, ui)

        elif ui.fracture_switch_subsections == 'FRACTURE_DETAILS':
            fracture_details(context, rbdlab, col, ui)
