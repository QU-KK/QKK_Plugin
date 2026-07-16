from ..main.module_panel import ModulePanel
from bpy.types import Panel

# from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, cheker_item_visibility

from .ground import ground_settings

from .rbd_ui.rbd_settings import rbd_settings
from .rbd_ui.animation import rbd_animation

from .kinematic_settings import kinematic_settings
from .parents.handler_settings import handler_settings
from .parents.compound_setting import compound_settings


class RBD_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'PHYSICS'
    bl_label = "Module"
    bl_idname = "RBD_PT_ui"

    def draw(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        tcoll_list = rbdlab.lists.target_coll_list

        layout = self.layout

        layout.enabled = cheker_item_visibility(context)

        col = layout.column(align=True)
        title_header(col, "Physics")
        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        switcher = main_col.row(align=True)
        switcher.use_property_split = False
        switcher.scale_y = 1.3
        switcher.prop(ui, "physics_switch_subsections", expand=True)
        # main_col.separator()

        ob = tcoll_list.get_first_valid_ob(context)
        have_rbd = tcoll_list.has_rigidbodies
        have_rbdlab_boolean_mod = rbdlab.have_rbdlab_boolean_modifier()
        fracture_applied = rbdlab.is_fractured()
        working_in_inner_details = not rbdlab.working_in_inner_details

        if ui.physics_switch_subsections == 'GROUND':
            ground_settings(rbdlab, col, ui)

        elif ui.physics_switch_subsections == 'RBD':

            rbd_subcats = col.box().row(align=True)
            rbd_subcats.scale_y = 1.3
            rbd_subcats.prop(ui, "physics_rbd_subsections", expand=True)

            if ui.physics_rbd_subsections == 'SETTINGS':
                rbd_settings(context, rbdlab, col, ui, ob, have_rbd, have_rbdlab_boolean_mod,
                            fracture_applied, working_in_inner_details)
            else:
                rbd_animation(context, rbdlab, col, ui)

        elif ui.physics_switch_subsections == 'KINEMATICS':
            kinematic_settings(rbdlab, col, ui, ob, have_rbd, have_rbdlab_boolean_mod, working_in_inner_details)

        elif ui.physics_switch_subsections == 'PARENTS':

            switcher = col.box().row(align=True)
            switcher.use_property_split = False
            switcher.scale_y = 1.3
            switcher.prop(ui, "parents_switch_subsections", expand=True)

            if ui.parents_switch_subsections == 'HANDLER':
                handler_settings(rbdlab, col, ui, ob)

            elif ui.parents_switch_subsections == 'COMPOUND':
                compound_settings(context, rbdlab, col, ui, have_rbd)
