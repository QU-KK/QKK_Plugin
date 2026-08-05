from ...common_ui_elements import collapsable, ui_remesh_modifier, ui_decimate_modifier, ui_solidify_modifier
from ....addon.naming import RBDLabNaming


def proxy(context, layout, rbdlab, ui):

    proxy_section = collapsable(
        layout,
        ui,
        "show_hide_paint_tools_proxy_section",
        "Proxy",
        'MESH_ICOSPHERE',
        align=True,
    )
    if proxy_section:

        proxy_section.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        def add_remesh(layout) -> None:
            create_bt = layout.row(align=True)
            create_bt.scale_y = 1.3
            create_bt.operator("rbdlab.prepare_proxy_add_modifier", text="Add Remesh").mod_type = 'REMESH'
        
        def add_decimate(layout) -> None:
            add_decimate_mod_bt = layout.row(align=True)
            add_decimate_mod_bt.scale_y = 1.3
            add_decimate_mod_bt.operator("rbdlab.prepare_proxy_add_modifier", text="Add Decimate").mod_type = 'DECIMATE'
        
        def add_solidify(layout) -> None:
            add_decimate_mod_bt = layout.row(align=True)
            add_decimate_mod_bt.scale_y = 1.3
            add_decimate_mod_bt.operator("rbdlab.prepare_proxy_add_modifier", text="Add Solidify").mod_type = 'SOLIDIFY'

        if rbdlab.current_proxy_ob is None:
            add_remesh(proxy_section)
            proxy_section.separator()
            add_decimate(proxy_section)
            proxy_section.separator()
            add_solidify(proxy_section)

        else:

            def headers(layout, mod, ui_text, ui_icon):
    
                if ui_icon != 'MOD_REMESH':
                    layout.separator()
    
                head = layout.box().row(align=True)
                head.label(text=ui_text, icon=ui_icon)
                right_bts = head.row(align=True)
                right_bts.alignment = 'RIGHT'
                right_bts.prop(mod, "show_viewport", text="")
                right_bts.prop(mod, "show_render", text="")
                mod_settings = layout.box().column(align=True)
                return mod_settings

            # Modifier properties:
            remesh_mod = rbdlab.current_proxy_ob.modifiers.get(RBDLabNaming.REMESH)
            if remesh_mod:
                mod_settings = headers(proxy_section, remesh_mod, "Remesh Modifier", 'MOD_REMESH')
                ui_remesh_modifier(context, mod_settings, remesh_mod)
            else:
                add_remesh(proxy_section)

            decimate_mod = rbdlab.current_proxy_ob.modifiers.get(RBDLabNaming.DECIMATE)
            if decimate_mod:             
                mod_settings = headers(proxy_section, decimate_mod, "Decimate Modifier", 'MOD_DECIM')
                ui_decimate_modifier(context, mod_settings, decimate_mod)
            else:
                proxy_section.separator()
                add_decimate(proxy_section)
            
            solidify_mod = rbdlab.current_proxy_ob.modifiers.get(RBDLabNaming.SOLIDIFY_MOD)
            if solidify_mod:
                mod_settings = headers(proxy_section, solidify_mod, "Solidify Modifier", 'MOD_SOLIDIFY')
                ui_solidify_modifier(context, mod_settings, solidify_mod)
            else:
                proxy_section.separator()
                add_solidify(proxy_section)

            # Down buttons:
            proxy_section.separator()
            down_buttons = proxy_section.row(align=True)
            down_buttons.scale_y = 1.3
            down_buttons.operator("rbdlab.prepare_accept_proxy", text="Accept", icon='CHECKMARK')
            cancel_bt = down_buttons.row(align=True)
            cancel_bt.alert = True
            cancel_bt.operator("rbdlab.prepare_cancel_proxy", text="Cancel", icon='TRASH')
    