from bpy.types import Panel
from ..main.module_panel import ModulePanel

from .draw_create import draw_create_tab
from .draw_edit import draw_edit_tab
from .animation.draw_animation import draw_animation_tab

# from ...addon.naming import RBDLabNaming
# from ...Global.functions import have_constraint_in_target_collection
from ..common_ui_elements import title_header, cheker_item_visibility
from ...props.constraints.constraints import ConstraintGroup, RBDLab_PG_Constraints
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import multiline_print


class CONSTRAINTS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'CONSTRAINTS'
    bl_label = "Module"
    bl_idname = "CONSTRAINTS_PT_ui"

    
    def draw(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        layout = self.layout.column(align=True)
        layout.use_property_decorate = False

        layout.enabled = cheker_item_visibility(context)

        rbdlab_const: RBDLab_PG_Constraints = rbdlab.constraints
        active_group: ConstraintGroup = rbdlab_const.get_active_group

        title_header(layout, "Constraints")
        main_col = layout.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        all_lay = layout.column(align=True)
        all_lay.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        col = all_lay.column(align=True)

        # -----------------------------------------------------------------------------------------
        # Si no tiene computados los vecinos no permitimos trabajar:
        # -----------------------------------------------------------------------------------------
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        if tcoll:
            text = "No Neighbors Computed in " + tcoll.name + "!"
            if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
                multiline_print(main_col.box(), text, max_words=5, first_line_crop=0, without_box=True, icon='ERROR')

            if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
                return
        # -----------------------------------------------------------------------------------------
        

        # have_constraints = have_constraint_in_target_collection()

        # CREATE / EDIT SELECTOR.
        act_tab = main_col.row()
        act_tab.scale_y = 1.3
        act_tab.prop(rbdlab.ui, "active_const_tab", text=" ", expand=True)
        # main_col.separator()

        if rbdlab.ui.active_const_tab == 'CREATE':
            # CREATE TAB.
            draw_create_tab(col, rbdlab, ui, rbdlab_const, active_group)

        elif rbdlab.ui.active_const_tab == 'EDIT':
            # EDIT TAB.
            draw_edit_tab(context, col, rbdlab, ui, rbdlab_const, active_group)
        
        elif rbdlab.ui.active_const_tab == 'ANIMATION':
            # ANIMATION TAB.
            draw_animation_tab(col, rbdlab, ui, active_group)