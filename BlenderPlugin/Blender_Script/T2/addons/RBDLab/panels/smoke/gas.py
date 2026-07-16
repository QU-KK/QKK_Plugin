from ..common_ui_elements import collapsable


def gas_section(layout, ui, domain_mod):

    gas = collapsable(
        layout,
        ui,
        "show_hide_domain_gas",
        "Gas",
        'FORCE_FLUIDFLOW',
        align=True
    )
    if gas:
        # Buoyancy
        gas_buoyancy = gas.row(align=True)
        gas_buoyancy.prop(domain_mod, "alpha", text="Buoyancy Density")
        # Gas Heat
        gas_heat = gas.row(align=True)
        gas_heat.prop(domain_mod, "beta", text="Heat")
        # Vorticity
        gas_vorticity = gas.row(align=True)
        gas_vorticity.prop(domain_mod, "vorticity", text="Vorticity")

    dissolve = collapsable(
        layout,
        ui,
        "show_hide_domain_gas",
        "Dissolve",
        'OUTLINER_DATA_LIGHTPROBE',
        align=True
    )
    if dissolve:
        en_dis = dissolve.row(align=True)
        en_dis.use_property_split = False
        en_dis.prop(domain_mod, "use_dissolve_smoke", text="Dissolve", toggle=True)
        dissolve.separator()
        rest_props = dissolve.column(align=True)
        rest_props.enabled = domain_mod.use_dissolve_smoke
        rest_props.prop(domain_mod, "dissolve_speed", text="Time")
        rest_props.prop(domain_mod, "use_dissolve_smoke_log", text="Slow")
