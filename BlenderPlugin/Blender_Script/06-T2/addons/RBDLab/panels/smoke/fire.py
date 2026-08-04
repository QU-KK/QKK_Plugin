from ..common_ui_elements import collapsable


def fire_section(layout, ui, domain_mod):

    fire = collapsable(
        layout,
        ui,
        "show_hide_domain_fire",
        "Fire",
        'SEQ_HISTOGRAM',
        align=True
    )
    if fire:
        fire.prop(domain_mod, "burning_rate", text="Reaction Speed")
        fire.prop(domain_mod, "flame_smoke", text="Flame Smoke")
        fire.prop(domain_mod, "flame_vorticity", text="Vorticity")
        fire.prop(domain_mod, "flame_max_temp", text="Temperature Maximum")
        fire.prop(domain_mod, "flame_ignition", text="Minimum")
        fire.prop(domain_mod, "flame_smoke_color", text="Flame Color")
