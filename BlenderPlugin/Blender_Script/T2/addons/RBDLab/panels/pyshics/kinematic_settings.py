from ..common_ui_elements import collapsable
from ...addon.naming import RBDLabNaming

def kinematic_settings(rbdlab, layout, ui, ob, have_rbd, have_rbdlab_boolean_mod, working_in_inner_details):

    tcoll = rbdlab.filtered_target_collection

    subslayout = layout.column(align=True)
    subslayout.enabled = ob is not None

    # kinematic settings:
    kinematics_settings = collapsable(
        subslayout,
        ui,
        "show_hide_physics_kinematics_settings",
        "Kinematics Settings",
        'SETTINGS',
        align=True,
    )
    if kinematics_settings:

        actions = kinematics_settings.row(align=True)

        row = actions.row(align=True)
        row.use_property_split = False
        row.scale_y = 1.3
        row.prop(rbdlab.physics.rigidbodies, "kinematic", text="Kinematic", expand=True, toggle=True)

        actions = kinematics_settings.row(align=True)
        row = actions.row(align=True)
        row.scale_y = 1.3
        # row.operator("rbdlab.set_anim_keyframe", text="Add Keyframe", icon='KEY_HLT')
        # row.operator("rbdlab.rigidbody_rm_all_anim_keyframes", text="Remove Keyframe", icon='KEY_DEHLT')
        row.operator("rbdlab.set_anim_keyframe", text="Add Keyframe")
        row.operator("rbdlab.rigidbody_rm_all_anim_keyframes", text="Remove Keyframe")

        if not have_rbd:
            have_rbd = False

        row.enabled = have_rbd and rbdlab.physics.rigidbodies.kinematic

        # for text in rbdlab.kinematic_keyframes.split("# "):
        #     if text:
        #         rowx = col.row(align=True)
        #         rowx.alert = True
        #         rowx.label(text="Info Keyfanes: " + text)

        # texto de feedback de kinematic
        # rowx = col.row(align=True)
        # rowx.alert = True
        # rowx.label(text="Info:" + rbdlab.kinematic_keyframes)

        if tcoll:
            coll_name = tcoll.name
            if coll_name:

                if "kinematic_keyframes_text" in tcoll:
                    if tcoll["kinematic_keyframes_text"]:
                        colf = kinematics_settings.column(align=True)
                        colf.separator()
                        actions = colf.row(align=True)
                        box = actions.box()
                        # box.alert = True
                        text = tcoll["kinematic_keyframes_text"].split("#####")
                        if text:
                            box.label(text=rbdlab.keyframes_added_text + text[1], icon='INFO')
                        # n = 0
                        # for text in tcoll["kinematic_keyframes_text"].split("#####"):
                        #     if n == 0:
                        #         box.label(text=rbdlab.keyframes_added_text + ": " + text, icon='INFO')
                        #     else:
                        #         box.label(text=text)
                        #     n += 1

    # KINEMATIC BY SELECTION:
    kinematics_by_selection = collapsable(
        subslayout,
        ui,
        "show_hide_physics_kinematics_by_selection_settings",
        "By Selection",
        'CON_KINEMATIC',
        align=True,
    )
    if kinematics_by_selection:

        if not rbdlab.physics.rigidbodies.show_hide_sele_kinematics:
            hide_icon = 'HIDE_ON'
        else:
            hide_icon = 'HIDE_OFF'

        row2 = kinematics_by_selection.row(align=True)
        row2.scale_y = 1.3
        row2.operator("rbdlab.set_kinematic", text="Set Kinematic")
        row2.prop(rbdlab.physics.rigidbodies, "show_hide_sele_kinematics", text="", toggle=False, icon=hide_icon)
        row2.operator("rbdlab.set_kinematic_select", text="", icon='RESTRICT_SELECT_OFF')
        # row2.separator()
        row2.alert = True
        row2.scale_x = 1.2
        row2.operator("rbdlab.set_kinematic_remove", text="", icon='TRASH')
        row2.enabled = working_in_inner_details

        actions = kinematics_by_selection.row(align=True)
        row3 = actions.row(align=True)
        row3.scale_y = 1.3
        # row3.operator("rbdlab.selset_anim_keyframe", text="Add Key", icon='KEY_HLT')
        # row3.operator("rbdlab.rigidbody_rm_sel_anim_keyframe", text="Remove Key", icon='KEY_DEHLT')
        row3.operator("rbdlab.selset_anim_keyframe", text="Add Key")
        row3.operator("rbdlab.rigidbody_rm_sel_anim_keyframe", text="Remove Key")
        row3.enabled = all([working_in_inner_details, not have_rbdlab_boolean_mod])

        # # texto de feedback de kinematic
        if tcoll:
            coll_name = tcoll.name
            if coll_name:
                if "statics_kinematic_keyframes_text" in tcoll:
                    if tcoll["statics_kinematic_keyframes_text"]:
                        # actions = actions_col.row(align=True)
                        actions = kinematics_by_selection.row(align=True)
                        box = actions.box()
                        # box.alert = True
                        box.scale_x = 1.6
                        text = tcoll["statics_kinematic_keyframes_text"].split("#####")
                        if text:
                            box.label(text=rbdlab.keyframes_added_text + text[1], icon='INFO')
        if ob:
            if RBDLabNaming.BOOLEAN_MOD not in ob.modifiers:
                row2.enabled = True
            else:
                row2.enabled = False
    
    # END KINEMATIC BY SELECTION

    if have_rbd:
        update_button = subslayout.box().row(align=True)
        update_button.scale_y = 1.3
        update_button.operator("rbdlab.rigidbody_update", text="Update", icon='FILE_REFRESH')
