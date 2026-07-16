from ..common_ui_elements import collapsable
from .draw_const_settings import draw_const_settings
from .common_draw_constraint_groups_list import draw_constraint_groups


def draw_edit_tab(context, layout, rbdlab, ui, rbdlab_const, active_group):

        # draw constraint groups list:
        main_col = draw_constraint_groups(layout, ui, rbdlab_const, active_group)

        # CONSTRAINT SETTINGS.
        draw_const_settings(main_col, rbdlab, ui, rbdlab_const, active_group)

        # new mutes
        const_display = collapsable(
            main_col,
            ui,
            "show_hide_constraint_display",
            "Mute/Unmute Constraints",
            align=True,
        )
        if const_display:

            actions = const_display.row(align=True)
            actions.scale_y = 1.3

            actions.operator("rbdlab.const_mute", text="Mute", icon='GHOST_DISABLED').state = True
            actions.operator("rbdlab.const_mute", text="Unmute", icon='GHOST_ENABLED').state = False
            actions.operator("rbdlab.const_select_muted", text="", icon='RESTRICT_SELECT_OFF')

            feedback = const_display.column(align=True)
            wm = context.window_manager
            if "Constraints_MuteUnmute_str" in wm:
                feedback.separator()
                feedback.box().label(text=wm["Constraints_MuteUnmute_str"], icon='INFO')
   

        # update/remove buttons:
        main_col.separator()

        feedback = main_col.row()
        update_bt = main_col.row()
        update_bt.scale_y = 1.5
        update_bt.operator("rbdlab.const_update", text="Update", icon='FILE_REFRESH')

        if rbdlab.low_or_high_visibility_viewport != "Low":
            alert = feedback.row()
            update_bt.enabled = False
            alert.box().label(text="Please, working in low visualization mode!", icon='ERROR')

        # el viejo remove de constraints
        # TODO: sera necesario eliminar el operador cuando este terminado
        # row.operator("rbdlab.const_rm", text="Remove Constraints", icon='TRASH')
