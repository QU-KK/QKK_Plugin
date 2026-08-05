from ...addon.naming import RBDLabNaming
from ..common_ui_elements import collapsable
from ...Global.get_common_vars import get_common_vars


def dswitch_dparent_panel(context, scn, rbdlab, ui, layout):
    dynamic_parent_props = rbdlab.physics.dswitch.dynamic_parent
    org_ob = dynamic_parent_props.select_original

    setup_org = collapsable(
        layout,
        ui,
        "parents_ds_setup_original",
        "Setup Original Object",
        'SETTINGS',
        align=True,
    )
    if setup_org:
        settings = setup_org.column(align=True)
        settings.use_property_split = True
        settings.use_property_decorate = False
        settings.prop(dynamic_parent_props, "select_original", text="Original")
        settings.separator()
        bake_bt = settings.row(align=True)
        bake_bt.scale_y = 1.3
        bake_bt.operator("rbdlab.phyisics_dswitch_bake_original", text="Bake Original")
        clear_bt = bake_bt.row(align=True)
        clear_bt.alert = True
        clear_bt.operator("rbdlab.phyisics_dswitch_clear_bake_original", text="Clear Bake", icon='TRASH')


    layout.separator()
    dparent = collapsable(
        layout,
        ui,
        "dswitch_dynamic_parent",
        "Dynamic Parent",
        'CONSTRAINT',
        align=True,
    )
    if dparent:

        switch_bts = dparent.row(align=True)
        switch_bts.scale_y = 1.3
        switch_bts.operator("rbdlab.phyisics_dswitch_dynamic_parent", text="Switch at frame " + str(scn.frame_current))

        
        reset_bt = switch_bts.row(align=True)
        # reset_bt.scale_y = 1.3
        
        if org_ob is None:
            switch_bts.enabled = False
            reset_bt.enabled = False
        else:
            switch_bts.enabled = RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in org_ob
            reset_bt.enabled = RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in org_ob

        reset_bt.operator("rbdlab.phyisics_dswitch_dynamic_parent_reset", text="Reset", icon='FILE_REFRESH')

        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        active_item = tcoll_list.active_item
        if active_item.dswitch_at_frame != -1 and dparent:
            layout.box().label(text="Switched in frame: " + str(active_item.dswitch_at_frame), icon='INFO')