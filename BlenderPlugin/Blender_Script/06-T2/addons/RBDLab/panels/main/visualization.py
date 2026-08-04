from ...addon.paths import RBDLabPreferences
from ..common_ui_elements import cheker_item_visibility
from ...addon.naming import RBDLabNaming

def draw_visualization_settings(layout, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        target_coll = rbdlab.filtered_target_collection
        # for disable mesh visualization options:
        valid_objects = [obj for obj in target_coll.objects if obj.type == 'MESH' and obj.visible_get()]
        booleans_in_chunks = [obj for obj in valid_objects if RBDLabNaming.BOOLEAN_MOD in obj.modifiers]
    else:
        target_coll = None

    # Visualize Options...
    # and "use_highs" in target_coll
    show_options = rbdlab.ui.show_mesh_visualization_settings and target_coll is not None and not rbdlab.working_in_inner_details
    visual = layout.column(align=True)
    visual_header = visual.box()

    # visual_header.scale_y = 1.3
    visual_toggle = visual_header.row()
    visual_toggle.emboss = 'PULLDOWN_MENU'
    visual_toggle.prop(rbdlab.ui, "show_mesh_visualization_settings",
                       icon='DISCLOSURE_TRI_DOWN' if show_options else 'DISCLOSURE_TRI_RIGHT', emboss=False)
    # for disable mesh visualization options:
    visual.enabled = target_coll is not None and not rbdlab.working_in_inner_details and not booleans_in_chunks

    if show_options:

        content = visual.column(align=True)  # visual.box().column(align=True)

        content.enabled = cheker_item_visibility(context)

        # content.enabled = enabled

        use_highs = "use_highs" in target_coll and not rbdlab.working_in_inner_details

        ''' Optimization Options. '''

        ### LOW/HIGH - VIEWPORT/RENDER ###
        visualizations = content.column(align=True)
        col0 = visualizations.column(align=True).box()
        col0.prop(rbdlab.ui, "show_low_high_to_all_or_tc", text="For all RBDLab collections")

        visual_row = col0.row(align=True)
        col1 = visual_row.column(align=True).box()
        col2 = visual_row.column(align=True).box()

        col1.label(text="Viewport:", icon='RESTRICT_VIEW_OFF')
        col1.prop(rbdlab, "low_or_high_visibility_viewport", expand=True, text="Viewport")

        col2.label(text="Render:", icon='RESTRICT_RENDER_OFF')
        col2.prop(rbdlab, "low_or_high_visibility_render", expand=True, text="Render")
        visualizations.enabled = use_highs

        ### Optimize... ###
        optimize = content.column(align=True).box()
        optimize.enabled = target_coll is not None  # and rbdlab.low_or_high_visibility_viewport == "Low"

        row_dec1 = optimize.row()
        row_dec1.prop(rbdlab, "fracture_low_decimate_on_off", expand=True, text="Decimate lows")
        row_rat_dec1 = row_dec1.row()
        row_rat_dec1.prop(rbdlab, "rbdlab_fracture_low_decimate_angle", expand=True, text="Angle")
        row_rat_dec1.enabled = rbdlab.fracture_low_decimate_on_off

        row_dec2 = content.box().row(align=True)
        row_dec2.prop(rbdlab, "fracture_high_decimate_on_off", expand=True, text="Decimate highs")
        row_rat_dec2 = row_dec2.row()
        row_rat_dec2.prop(rbdlab, "rbdlab_fracture_high_decimate_ratio", expand=True, text="Ratio")
        row_rat_dec2.enabled = rbdlab.fracture_high_decimate_on_off

        optimize.enabled = use_highs

        # SHADING - auto-smooth per edit mode:
        smooth_box = content.box()
        smooths_col = smooth_box.column(align=True)
        smooths_row1 = smooths_col.row(align=True)
        smooths_row2 = smooths_col.row(align=True)
        smooths_row1.operator("rbdlab.shade_smooth_inner", text="Smooth Inner").type = "smooth_inner"
        smooths_row1.operator("rbdlab.shade_smooth_inner", text="Flat Inner").type = "flat_inner"
        smooths_row2.operator("rbdlab.shade_smooth_inner", text="Smooth Outer").type = "smooth_outher"
        smooths_row2.operator("rbdlab.shade_smooth_inner", text="Flat Outer").type = "flat_outher"

        # smooth_box.enabled = use_highs
        se_uso_bool_fracture_con_highs = "fractured_by_boolean_scatter" in target_coll and "use_highs" in target_coll
        smooth_box.enabled = not se_uso_bool_fracture_con_highs

        row_dec1.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        if "fracture_applied" in rbdlab.filtered_target_collection and "use_highs" not in rbdlab.filtered_target_collection:
            row_dec2.enabled = True
        else:
            row_dec2.enabled = rbdlab.low_or_high_visibility_viewport == "High"

        ''' Shading/Display/Aspect Options. '''
        # section_shade = content.box()

        ### PRETTY SHADING ###
        bbox_box = content.box()
        col = bbox_box.column(align=True)
        col.label(text="Misc:", icon='MATSHADERBALL')
        bbox_box = content.box()

        bbox_row = bbox_box.row(align=True)
        bbox_row.scale_y = 1.3
        # bbox_row.prop(rbdlab, "show_boundingbox", expand=True, toggle=True, text="Bounding Box")
        if rbdlab.low_or_high_visibility_viewport == "Low":
            depress_condition = rbdlab.status_show_boundingbox_in_low
        else:
            depress_condition = rbdlab.status_show_boundingbox_in_high
        bbox_row.operator("rbdlab.show_boundingbox", depress=depress_condition,
                          text="Bounding Box").enable = not depress_condition

        wire_box = content.box()

        ### WIREFRAME ###

        wire_col = wire_box.column()
        wire_row = wire_col.row(align=True)

        wire_row.prop(context.space_data.overlay, "show_wireframes", text="Wireframe")

        ### SHADING - auto-smooth per object ###
        asmooth = wire_col.row(align=True)
        asmooth.prop(rbdlab, "use_auto_smooth", text="Auto-Smooth")
        _asmooth = asmooth.row(align=True)
        _asmooth.active = rbdlab.use_auto_smooth
        _asmooth.prop(rbdlab, "auto_smooth", text="Angle")

        #### SPEED VISUALIZATION ###
        '''
        # se estaba usando este bloque la ultima vez
        rbw = context.scene.rigidbody_world
        if rbw:
            if rbw.point_cache.is_baked:
                show_options = rbdlab.ui.show_hide_speed_visualization
                speed_visualization_header = content.box()
                speed_visualization_toggle = speed_visualization_header.row(align=True)
                speed_visualization_toggle.use_property_split = False
                speed_visualization_toggle.alignment = 'LEFT'
                speed_visualization_toggle.emboss = 'NONE'
                speed_visualization_toggle.prop(
                    rbdlab.ui, "show_hide_speed_visualization", icon='DISCLOSURE_TRI_DOWN'
                    if show_options else 'DISCLOSURE_TRI_RIGHT', text="")
                speed_visualization_toggle.prop(rbdlab.ui, "show_hide_speed_visualization", text="Speed Visualization")
                if show_options:
                    content_collapse = speed_visualization_header.column(align=True)
                    col = content_collapse.row(align=True)
                    col.label(text="Visual Speed")
                    row = col.row(align=True)
                    row.operator("rbdlab.visual_speed", text='ON', depress=rbdlab.ui.visual_speed)
                    row.operator("rbdlab.visual_speed_remove", text='OFF', depress=not rbdlab.ui.visual_speed)
        '''

        # rbw = context.scene.rigidbody_world
        # if rbw:
        #     if rbw.point_cache.is_baked:
        #         wire_box = content.box()
        #         col = wire_box.row(align=True)
        #         col.label(text="Visual Speed")
        #         row = col.row(align=True)
        #         row.operator("rbdlab.visual_speed", text='ON', depress=rbdlab.ui.visual_speed)
        #         row.operator("rbdlab.visual_speed_remove", text='OFF', depress=not rbdlab.ui.visual_speed)
        #         # col = section_shade.row(align=True)
        #         # col.label(text="OLD Visual Speed")
        #         # row = col.row(align=True)
        #         # row.operator("rbdlab.speed_visualization", text="OLD ON")
        #         # row.operator("rbdlab.speed_visualization_rm", text="OLD OFF")

        # wframe = section_shade.row(align=True)

        wire_row.prop(context.space_data.overlay, "wireframe_threshold", text="Wireframe")
        wire_row.prop(context.space_data.overlay, "wireframe_opacity", text="Opacity")

        box = content.box()

        col = box.column(align=True)
        col.label(text="Pretty Shading:", icon='SHADING_RENDERED')
        box = content.box()
        flip_col = box.column(align=True)

        flip_col.use_property_split = False

        addon_preferences = RBDLabPreferences.get_prefs(context)
        flipbooks_path = addon_preferences.flipbooks_path
        if not flipbooks_path:
            fb_path = flip_col.row(align=True)
            fb_path.use_property_split = False
            fb_path.prop(addon_preferences, "flipbooks_path", text="Flibook Path")
            flip_col.separator()

        flip_row = flip_col.row(align=True)
        has_pretty_shading = "has_pretty_shading" in context.workspace and context.workspace["has_pretty_shading"]
        flip_row.operator("rbdlab.pretty_shading", text='ON', depress=has_pretty_shading).enable = True
        flip_row.operator("rbdlab.pretty_shading", text='OFF', depress=(not has_pretty_shading)).enable = False
        flip_row.operator("rbdlab.flipbook", icon='RENDER_ANIMATION', text="")
        flip_row.operator("render.play_rendered_anim", icon='RENDER_STILL', text="")

        rd = context.scene.render
        image_settings = rd.image_settings
        flip_row = flip_col.row(align=True)
        flip_row.prop(rd, "resolution_x", text="")
        flip_row.prop(rd, "resolution_y", text="")
        flip_col.prop(rd, "resolution_percentage", text="%")
        flip_col.separator()
        flip_col.template_image_settings(image_settings, color_management=False)

        if rd.image_settings.file_format in {'FFMPEG', 'XVID', 'H264', 'THEORA'}:
            flip_col.separator()
            flip_col.alignment = 'RIGHT'
            flip_col.use_property_split = False
            rd = context.scene.render
            ffmpeg = rd.ffmpeg

            # flip_col.prop(ffmpeg, "use_autosplit")
            flip_col.prop(rd.ffmpeg, "format")
            flip_col.separator()

        ''' Explode Visualization Options. '''
        section_expl = content.column(align=True)
        draw_explode_visualization(section_expl, context)


def draw_explode_visualization(layout, context):
    scn = context.scene
    rbdlab = scn.rbdlab
    tcoll_list = rbdlab.lists.target_coll_list

    box = layout.box()
    col = box.column(align=True)
    col.label(text="Explode Visualization:", icon='PIVOT_CURSOR')
    box = layout.box()

    row = box.row(align=True)

    row.scale_y = 1.3

    if not rbdlab.exploding:
        row.operator("rbdlab.explode_start", text="Start Explode")
    else:
        col = box.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        row.operator("rbdlab.explode_finish", text="End Explode")

        col.prop(rbdlab, "colorize", text="Colorize")

        axis = col.row(align=True)
        axis.prop(rbdlab, "explode_axis_x", text="X", toggle=True)
        axis.prop(rbdlab, "explode_axis_y", text="Y", toggle=True)
        axis.prop(rbdlab, "explode_axis_z", text="Z", toggle=True)

        amount = col.row(align=True)
        amount.prop(rbdlab, "explode_slider", text="Amount")
        amount.enabled = any([rbdlab.explode_axis_x, rbdlab.explode_axis_y, rbdlab.explode_axis_z])
        # layout.operator("rbdlab.explode_restart", text="Well, let's start again")

    if rbdlab.filtered_target_collection:
        row.enabled = True
        # ob = tcoll_list.get_first_valid_ob(context)
        # if ob:
        #     if RBDLabNaming.BOOLEAN_MOD not in ob.modifiers:
        #         row.enabled = True
        #     else:
        #         row.enabled = False
        # else:
        #     row.enabled = False
    else:
        row.enabled = False
