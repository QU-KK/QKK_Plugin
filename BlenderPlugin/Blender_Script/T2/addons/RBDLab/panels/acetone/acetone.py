from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ...addon.naming import RBDLabNaming
from ...panels.common_ui_elements import multiline_print

class ACTIVATORS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'ACTIVATORS'
    bl_label = "Activators"
    bl_idname = "ACTIVATORS_PT_ui"
    # bl_parent_id = "CONSTRAINTS_PT_ui"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        rbdlab = scn.rbdlab

        layout.use_property_split = False
        layout.use_property_decorate = False

        section0 = layout.column(align=True)
        header = section0.box().row()
        header.label(text="Settings", icon='SETTINGS')
        content = section0.box().column()

        row = content.row(align=True)
        row.label(text="• Source", icon='BLANK1')
        row.prop(rbdlab.activators, "type_selection", text="")

        row = content.row(align=True)
        row.label(text="• Affect", icon='BLANK1')
        col = row.column(align=True)
        col.prop(rbdlab.activators, "work_with", text=" ")

        row = content.row(align=True)
        row.label(text="• Substeps", icon='BLANK1')
        row.prop(rbdlab.activators, "passes", text="")

        if 'INITIALVEL' in rbdlab.activators.work_with:
            row = content.row(align=True)
            # row.use_property_split = True
            row.label(text="• Automatically set kinematics", icon='BLANK1')
            row.prop(rbdlab.ui, "activators_auto_add_kinematics", text="")

        # row = content.row(align=True)
        # row.label(text="Ignore already acetonizeds", icon='BLANK1')
        # row.prop(rbdlab.ui, "activators_ignore_acetonized", text="")

        section1 = layout.column(align=True)
        header = section1.box().row(align=True)
        header.label(text="Selection", icon='RESTRICT_SELECT_OFF')

        actions = section1.box().row()
        actions.scale_y = 1.2
        actions.operator("rbdlab.act_include_chunks", text="Include Chunks", icon='ADD')
        actions.operator("rbdlab.act_exclude_chunks", text="Exclude Chunks", icon='REMOVE')

        section2 = layout.column(align=True)
        header = section2.box().row(align=True)
        header.label(text="Activators Objects", icon='LIGHTPROBE_SPHERE')

        actions = section2.box().column()
        actions.label(text="Setup From Selected Mesh")
        actions = actions.row()
        actions.scale_y = 1.2
        actions.operator("rbdlab.act_set", text="Set Activators")
        actions.operator("rbdlab.act_unset", text="Unset Activators")

        actions = section2.box().column()
        actions.label(text="Create From Primitive (faster to compute)")
        actions = actions.row()
        actions.scale_y = 1.2

        actions.operator("rbdlab.create_empty", text="Spheric", icon='SPHERE').shape = 'SPHERE'
        actions.operator("rbdlab.create_empty", text="Cubic", icon='CUBE').shape = 'CUBE'

        section3 = layout.column(align=True)
        header = section3.box().row()
        header.label(text="Frames to compute", icon='CON_ACTION')
        content = section3.box().column()

        row = content.row(align=True)
        # row.use_property_split = True
        row.prop(rbdlab.activators, "automatic_range_with_keyframes", text="Automatic Range")

        if rbdlab.activators.automatic_range_with_keyframes:
            row = content.row(align=True)
            col_msg = row.column(align=True).box()
            col_msg.label(text="Automatic mode requires to have animation ", icon='INFO')
            col_msg.label(text="with keyframes in Activators objects or their parents")
        else:
            row = content.row(align=True)
            # row.use_property_split = True
            row.operator("rbdlab.passive_total_frames_from_sim", text="Use All Frames", icon='CENTER_ONLY')
            row.prop(rbdlab.activators, "total_frames", text="Frames to compute")

        section4 = layout.column(align=True)
        if 'CONSTRAINTS' in rbdlab.activators.work_with:
            section0 = layout.column(align=True)
            header = section4.box().row()
            header.label(text="Passive Mode", icon='LOCKVIEW_ON')
            content = section4.box().column()

            row = content.row(align=True)
            # row.use_property_split = True
            row.prop(rbdlab.activators, "passive_mode", text="Passive Mode")
            if rbdlab.activators.passive_mode and rbdlab.activators.automatic_range_with_keyframes:
                row = content.row(align=True)
                col_msg = row.column(align=True).box()
                col_msg.label(text="Passive mode only work without Automatic Range", icon='INFO')
            if rbdlab.activators.passive_mode and not rbdlab.activators.automatic_range_with_keyframes:
                row = content.row(align=True)
                col_msg = row.column(align=True).box()
                col_msg.label(text="Passive mode It is somewhat ", icon='INFO')
                col_msg.label(text="slower because the physics are computed")

        section5 = layout.column(align=True)
        if 'INITIALVEL' in rbdlab.activators.work_with:
            header = section5.box().row(align=True)
            header.label(text="Initial Velocity", icon='FORCE_FORCE')

            content = section5.box()
            content.label(text="• Transformations")

            force = content.column(align=True)
            force.use_property_split = True
            #force.row().prop(rbdlab.activators, "force_mode", expand=True)

            # Direction/Location and explode:
            show_options = rbdlab.ui.show_activators_direction
            dir_col = force.column(align=True)
            dir_header = dir_col.box()
            dir_toggle = dir_header.row(align=True)
            dir_toggle.use_property_split = False
            dir_toggle.alignment = 'LEFT'
            dir_toggle.emboss = 'NONE'
            dir_toggle.prop(rbdlab.ui, "show_activators_direction", icon='DISCLOSURE_TRI_DOWN'
                            if show_options else 'DISCLOSURE_TRI_RIGHT', text="")
            dir_toggle.prop(rbdlab.ui, "show_activators_direction", text="Direction")
            if show_options:
                content = dir_header.column(align=True)
                dir_mode = content.row(align=True)
                dir_col = content.column(align=True)
                dir_mode.prop(rbdlab.ui, "activators_force_loc_mode", text="Mode", toggle=True, expand=True)
                dir_col.separator()
                if rbdlab.ui.activators_force_loc_mode == 'CONST':
                    dir_col.prop(rbdlab.activators, "force_direction", text="Direction", slider=True)
                elif rbdlab.ui.activators_force_loc_mode == 'RAND':
                    rowx = dir_col.row()
                    rowx.prop(rbdlab.activators, "force_x_min_loc_rand", text="Min Max X")
                    rowx.prop(rbdlab.activators, "force_x_max_loc_rand", text="")
                    rowy = dir_col.row()
                    rowy.prop(rbdlab.activators, "force_y_min_loc_rand", text='Y')
                    rowy.prop(rbdlab.activators, "force_y_max_loc_rand", text="")
                    rowz = dir_col.row()
                    rowz.prop(rbdlab.activators, "force_z_min_loc_rand", text='Z')
                    rowz.prop(rbdlab.activators, "force_z_max_loc_rand", text="")
                elif rbdlab.ui.activators_force_loc_mode == 'EXPLODE':
                    row = dir_col.row(align=True)
                    row.prop(rbdlab.activators, "force_explode_amount", text="Amount")
                    row.operator("rbdlab.act_explode_done", text="Done")

                    row = dir_col.row(align=True)
                    row.prop(rbdlab.activators, "explode_empty_size", text="Centroid Size")
                    row.prop(rbdlab.activators, "explode_centroid_visibility", text="", icon='HIDE_OFF')
                    row.prop(rbdlab.activators, "explode_centroid_select", text="", icon='RESTRICT_SELECT_OFF')

                    dir_col = dir_header.column(align=True)
                    mult_offset = dir_col.column(align=True)
                    mult_offset.prop(rbdlab.activators, "force_explode_scale", text="Multiplier", slider=True)
                    mult_offset.prop(rbdlab.activators, "force_explode_frame_offset", text="Offset", slider=True)

                    # dir_col.separator()
                    # dir_col.use_property_split = False
                    # row = dir_col.row(align=True, heading="Ease In-Out")
                    # row.prop(rbdlab.activators, "force_exp_ease_in", text="", slider=True)
                    # row.prop(rbdlab.activators, "force_exp_ease_out", text="", slider=True)

                if rbdlab.ui.activators_force_loc_mode != 'EXPLODE':
                    content.separator()
                    content.prop(rbdlab.activators, "force_loc_scale", text="Multiplier", slider=True)
                    content.prop(rbdlab.activators, "force_loc_frame_offset", text="Offset", slider=True)

                    content.separator()
                    content.use_property_split = False
                    row = content.row(align=True, heading="Ease In-Out")
                    row.prop(rbdlab.activators, "force_loc_ease_in", text="", slider=True)
                    row.prop(rbdlab.activators, "force_loc_ease_out", text="", slider=True)

            # Rotation:
            show_options = rbdlab.ui.show_activators_rotation
            rot_col = force.column(align=True)
            rot_header = rot_col.box()
            rot_toggle = rot_header.row(align=True)
            rot_toggle.use_property_split = False
            rot_toggle.alignment = 'LEFT'
            rot_toggle.emboss = 'NONE'
            rot_toggle.prop(rbdlab.ui, "show_activators_rotation", icon='DISCLOSURE_TRI_DOWN'
                            if show_options else 'DISCLOSURE_TRI_RIGHT', text="")
            rot_toggle.prop(rbdlab.ui, "show_activators_rotation", text="Rotation")
            if show_options:
                content = rot_header.column(align=True)
                rot_mode = content.row(align=True)
                rot_col = content.column(align=True)
                rot_mode.prop(rbdlab.ui, "activators_force_rot_mode", text="Mode", toggle=True, expand=True)
                rot_col.separator()
                if rbdlab.ui.activators_force_rot_mode == 'CONST':
                    rot_col.prop(rbdlab.activators, "force_rotation", text="Rotation", slider=True)
                else:
                    rowx = rot_col.row()
                    rowx.prop(rbdlab.activators, "force_x_min_rot_rand", text="Min Max X")
                    rowx.prop(rbdlab.activators, "force_x_max_rot_rand", text="")
                    rowy = rot_col.row()
                    rowy.prop(rbdlab.activators, "force_y_min_rot_rand", text='Y')
                    rowy.prop(rbdlab.activators, "force_y_max_rot_rand", text="")
                    rowz = rot_col.row()
                    rowz.prop(rbdlab.activators, "force_z_min_rot_rand", text='Z')
                    rowz.prop(rbdlab.activators, "force_z_max_rot_rand", text="")

                content.separator()
                content.prop(rbdlab.activators, "force_rot_scale", text="Multiplier", slider=True)
                content.prop(rbdlab.activators, "force_rot_frame_offset", text="Offset", slider=True)

                content.separator()
                content.use_property_split = False
                row = content.row(align=True, heading="Ease In-Out")
                row.prop(rbdlab.activators, "force_rot_ease_in", text="", slider=True)
                row.prop(rbdlab.activators, "force_rot_ease_out", text="", slider=True)

            force.separator()

            if rbdlab.ui.activators_force_loc_mode == 'EXPLODE' and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
                msg_done = force.column()

                text="Remember that to use the explode: You must first include chunks and Activators objects. Then also use the amount and then press Done button. Can press shift when use Amount."
                multiline_print(msg_done, text, max_words=7, first_line_crop=1)
                
                force.separator()

            prev_buttons = force.row(align=True)
            prev_buttons.scale_y = 1.3
            preview_bt = prev_buttons.row(align=True)
            clear_bt = prev_buttons.row(align=True)

            preview_bt.operator("rbdlab.act_record", text="Preview").mode = 'FORCE_PREVIEW'
            if rbdlab.filtered_target_collection:
                if "activators_force_preview_recorded" in rbdlab.filtered_target_collection:
                    clear_bt.alert = True
                    clear_bt.operator("rbdlab.act_rm_record", text="Clear Preview", icon='TRASH').mode = 'FORCE_PREVIEW'
                    preview_bt.enabled = False
                    # print('8')

                if "activators_recorded" in rbdlab.filtered_target_collection:
                    prev_buttons.enabled = False
                    # print('7')
            else:
                preview_bt.enabled = False
                prev_buttons.enabled = False
                # print('6')

            if rbdlab.ui.activators_force_loc_mode == 'EXPLODE' and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
                preview_bt.enabled = False
                # print('5')

        '''
        content.label(text="• Angular Force")
        
        force = content.column()
        force.use_property_split = True
        #force.row().prop(rbdlab.activators, "force_mode", expand=True)
        force.prop(rbdlab.activators, "angular_range", text="Range", slider=True)
        force.prop(rbdlab.activators, "angular_scale", text="Scale", slider=True)
        '''

        # BUTTONS:
        # ignore = layout.row(align=True)
        col_big = layout.column()

        col_big.scale_y = 1.5

        # mensaje porque hay problemas si usamos el truco de tebito:
        if 'KINEMATIC' in rbdlab.activators.work_with:
            if rbdlab.filtered_target_collection:
                if "kinematic_keyframes_text" in rbdlab.filtered_target_collection:
                    if rbdlab.filtered_target_collection["kinematic_keyframes_text"] != "":
                        msg = col.box().row(align=True)
                        msg.alert = True
                        msg.label(text="Previous Kinematic keyframes will be deleted!!", icon='ERROR')

        #ignore.prop(rbdlab.ui, "activators_ignore_acetonized", text="Ignore already acetonizeds")

        row1 = col_big.row(align=True)
        col = layout.column()
        # msg = col.row(align=True)
        # row = col.row(align=True)
        # if rbdlab.ui.activators_ignore_acetonized:
        #     msg.alert = True
        #     msg.label(text="Ignore Acetonizeds are ON", icon='INFO')

        row1.operator("rbdlab.act_record", text="Record Activators").mode = 'NORMAL'

        # para la condicion de activators necesito saber si tienen keyframes:
        if 'CONSTRAINTS' in rbdlab.activators.work_with:
            ACTIVATORS_OBJECTS = [obj for obj in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in obj]

            all_keyframes = []

            for obj in ACTIVATORS_OBJECTS:

                if obj.animation_data:
                    if hasattr(obj.animation_data.action, "fcurves"):
                        for fc in obj.animation_data.action.fcurves:
                            for key in fc.keyframe_points:
                                all_keyframes.append(key.co.x)

                if len(all_keyframes) == 0:
                    if obj.parent:
                        if obj.parent.animation_data:
                            if hasattr(obj.parent.animation_data.action, "fcurves"):
                                for fc in obj.parent.animation_data.action.fcurves:
                                    for key in fc.keyframe_points:
                                        all_keyframes.append(key.co.x)

            condition_1 = len(all_keyframes) == 0 \
                and not rbdlab.activators.passive_mode \
                and 'CONSTRAINTS' in rbdlab.activators.work_with \
                and not rbdlab.activators.automatic_range_with_keyframes

        if rbdlab.filtered_target_collection:
            # if "activators_force_preview_recorded" in rbdlab.filtered_target_collection or "activators_recorded" in rbdlab.filtered_target_collection:
            if "activators_force_preview_recorded" not in rbdlab.filtered_target_collection:
                # row1.enabled = True
                # si se usa pasive mode pero no esta desactivado el automatic range bloqueo el boton:
                if 'CONSTRAINTS' in rbdlab.activators.work_with:
                    if all([rbdlab.activators.passive_mode, rbdlab.activators.automatic_range_with_keyframes]):
                        row1.enabled = False
                        # print('3')
                    else:
                        if condition_1:
                            # print('2')
                            row1.enabled = False
        else:
            # print('1')
            row1.enabled = False

        row1.operator("rbdlab.select", text="", icon='RESTRICT_SELECT_OFF')
        # row2 = col_big.row()

        if 'EXPLODE' in rbdlab.ui.activators_force_loc_mode and RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
            row1.enabled = False
            # print('13')

        col_big2 = layout.column()
        col_big2.scale_y = 1.5

        work_with = ""
        for w_with in rbdlab.activators.work_with:
            if w_with not in work_with:
                work_with += " " + str(w_with.capitalize())

        if rbdlab.filtered_target_collection:
            if "activators_recorded" in rbdlab.filtered_target_collection:
                col_big2.alert = True
                col_big2.operator("rbdlab.act_rm_record", text="Clear " + work_with, icon='TRASH').mode = 'NORMAL'

        # col.operator("rbdlab.unhide", text="Unhide Acetonizeds")

        if rbdlab.low_or_high_visibility_viewport != "Low":
            section0.enabled = False
            section1.enabled = False
            section2.enabled = False
            section3.enabled = False
            section4.enabled = False
            section5.enabled = False
            col_big.enabled = False
            # print('14')
            alert = layout.row()
            alert.alert = True
            alert.label(text="Please, working in low visualization mode!", icon='ERROR')
        # else:
        #     section0.enabled = True
        #     section1.enabled = True
        #     section2.enabled = True
        #     section3.enabled = True
        #     section4.enabled = True
        #     section5.enabled = True
        #     col_big.enabled = True
        #     print('15')
