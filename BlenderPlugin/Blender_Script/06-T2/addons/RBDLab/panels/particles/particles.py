import bpy
import os
from bpy.types import Panel, UILayout
from bl_ui.utils import PresetPanel
from ..main.module_panel import ModulePanel
from bpy.types import Menu
# from ...Global.functions import get_constraints_from_obj
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, cheker_item_visibility, multiline_print
from ...props.particles import RBDLab_PG_particles_add_props as PG_ParticlesCreate


class PARTICLE_PT_presets(PresetPanel, Panel):
    bl_label = "My Presets"
    preset_subdir = os.path.join("RBDLab", 'PARTICLES')
    preset_operator = "script.execute_preset"
    preset_add_operator = "rbdlab.particles_add_preset"


class PARTICLES_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'PARTICLES'
    bl_label = "Module"
    bl_idname = "PARTICLES_PT_ui"

    rbw = None
    particle_types = ("debris", "dust", "smoke")
    ps_props = None
    p_type = None

    def draw_header_preset(self, _context):
        PARTICLE_PT_presets.draw_panel_header(self.layout)

    def check_if_exist_domain(self, context):
        scene = context.scene
        rbdlab = scene.rbdlab
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            domain_name = RBDLabNaming.DOMAIN_NAME

            have_fluids = []
            for obj in bpy.data.collections[coll_name].objects:
                if RBDLabNaming.SMOKE_MOD in obj.modifiers:
                    have_fluids.append(obj)

            if domain_name in context.scene.objects or len(have_fluids) > 0:
                return True
        else:
            return False

    def draw(self, context):

        scene = context.scene
        rbdlab = scene.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        layout = self.layout
        layout.enabled = cheker_item_visibility(context)

        layout = self.layout.column(align=True)

        self.rbw = scene.rigidbody_world

        exist_domain = self.check_if_exist_domain(context)

        selected_particle = rbdlab.ui.selected_particle_type
        has_selected_particle = rbdlab.has_particles()

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = tcoll is not None

        title_header(layout, 'Particles')
        main_col = layout.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        # Ahora no bloqueo todo, porque se pueden usar particulas con el motion unicamente, por lo que
        # tuve que restringir el uso a solo motion con lo que eso implica. 
        
        # # -----------------------------------------------------------------------------------------
        # # Si no tiene computados los vecinos no permitimos trabajar:
        # # ----------------------------------------------------------------------------------------- 
        # if tcoll:
        #     text = "No Neighbors Computed in " + tcoll.name + "!"
        #     if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
        #         multiline_print(main_col.box(), text, max_words=5, without_box=True, icon='ERROR')

        #     if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
        #         return
        # # -----------------------------------------------------------------------------------------
        
        # si existe domain no permitimos crear particulas
        # if exist_domain:
        #     domain_msg = main_col.column(align=True).box()
        #     domain_msg.alert = True
        #     # col.label(text="Domain detected!, you are skipping the", icon='ERROR')
        #     # col.label(text="creation order and may have unexpected crashes.")
        #     domain_msg.label(text="Domain of fludis in chunks detected!", icon='ERROR')
        #     domain_msg.label(text="You should not generate particles if you have created smoke.")
        #     domain_msg.label(text="Before generating particles, remove the smoke in the smoke module.")

        # testsmoke outdated time compute velocities = 0:00:54.670962
        # testsmoke only played time compute velocities = 0:00:20.226323
        # testsmoke played and current to cache compute velocities = 0:00:25.995441
        # testsmoke baked compute velocities = 0:00:01.408062

        if self.rbw:
            '''
            # comento los msg de outdated
            col_cache_msg = main_col.column(align=True).box()
            msg_cache_status = self.rbw.point_cache.info
            '''
            valid_objects = []

            if not self.rbw.point_cache.is_baked:
                # si se detectan keyframes se da por hecho q tiene bake a keyframes y no se muestra el label:
                if tcoll:

                    wm = context.window_manager

                    # cuando son acetonables (activators) tienen keyframes por eso no salía el feedback.

                    valid_objects = [ob for ob in tcoll.objects
                                    if ob.type == 'MESH' and ob.visible_get() and ob.name != RBDLabNaming.GROUND and
                                    RBDLabNaming.SUFIX_BBOX
                                    not in ob.name and RBDLabNaming.PASSIVE
                                    not in ob and ob.animation_data is
                                    not None and ob.animation_data.action is
                                    not None and len(ob.animation_data.action.fcurves) > 0 and RBDLabNaming.ACETONABLE not in ob]

                    if not valid_objects or RBDLabNaming.DSWITCH_DPARENT_BAKED_TO_KFRAMES in wm:
                        main_col.box().label(text="It is important to bake first!", icon='ERROR')
                        main_col.separator()

            '''
            # comento los msg de outdated
            if msg_cache_status:
                row_2_ch_msg = col_cache_msg.column()

                if "outdated" in msg_cache_status:
                    row_2_ch_msg.alert = True

                if "outdated" in msg_cache_status:
                    icon_cache_msg = 'ERROR'
                else:
                    icon_cache_msg = 'INFO'

                row_2_ch_msg.label(text=msg_cache_status, icon=icon_cache_msg)

                if icon_cache_msg == 'ERROR':
                    row_2_ch_msg.label(text="Your cache is out of date, you should redo bake.")
            '''

        ### PARTICLES SELECTOR ###

        # p_row = main_col.grid_flow(columns=0)
        p_row = main_col.grid_flow(columns=3)
        p_row.scale_y = 1.3
        for p_type in self.particle_types:
            selected = selected_particle == p_type

            p_col = p_row.column(align=False).row(align=True)
            p_col.operator("rbdlab.particles_select", text=p_type.capitalize(), depress=selected).type = p_type

            # visibility particles in viewport and render:
            if rbdlab.has_particles(p_type):  # and selected ?
                v_mode, r_mode = rbdlab.is_particle_visible(p_type)

                # la visibilidad de las particulas en viewport tambien esta en el Target Collection List con un icono

                v_icon = 'RESTRICT_VIEW_OFF' if v_mode else 'RESTRICT_VIEW_ON'
                r_icon = 'RESTRICT_RENDER_OFF' if r_mode else 'RESTRICT_RENDER_ON'

                op_viewport = p_col.operator("rbdlab.particles_visibility",
                                            text="",
                                            icon=v_icon)
                op_viewport.type = p_type
                op_viewport.visibility_particle_type = 'VIEWPORT'

                op_render = p_col.operator("rbdlab.particles_visibility",
                                        text="",
                                        icon=r_icon)
                op_render.type = p_type
                op_render.visibility_particle_type = 'RENDER'

        # container = main_col.box()
        # container = main_col.column()

        self.ps_props = rbdlab.get_particles_properties()
        self.p_type = rbdlab.ui.selected_particle_type

        all_lay = main_col.column(align=True)
        all_lay.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        if not has_selected_particle:  # have_particles_in_motion():
            # Draw particle creation properties.
            self.draw_create_options(context, tcoll_list, tcoll, all_lay, exist_domain, rbdlab)
        else:
            # Draw particle system properties that user can update.
            self.draw_update_options(context, layout, all_lay, rbdlab)

    def draw_create_options(self, context, tcoll_list, tcoll, layout: UILayout, exist_domain, rbdlab):

        # use broken
        # ob = tcoll_list.get_first_valid_ob(context)
        # const = get_constraints_from_obj(ob)

        ######################
        layout.separator()
        section = layout.column(align=True)
        header = section.box().row(align=True)
        header.label(text=f"{self.p_type.title()} Creation Settings", icon='SETTINGS')
        container = section.box()
        p_create: PG_ParticlesCreate = self.ps_props.create

        options = container.row()
        options.use_property_split = False
        options.scale_y = 1.3
        options.prop(p_create, "options", expand=True, text=" ")
        
        tcoll = tcoll_list.active
        if tcoll:
            if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
                text = "If you need to use the Broken, you first have to compute the neighbors."
                multiline_print(container.box(), text, max_words=7, first_line_crop=0, without_box=True)
                options.enabled = False


        if p_create.use_broken:
            broken_section = container.column(align=True)
            broken_section.box().row().label(text="Broken Settings", icon='MOD_PHYSICS')
            broken_section.box().prop(p_create, "distance_threshold", slider=True)

        if p_create.use_motions:
            motions_section = container.column(align=True)
            motions_section.box().row().label(text="Motion Settings", icon='CURVE_PATH')
            motions_content = motions_section.box()

            m_c = motions_content.row(align=True)
            m_c.alignment = 'RIGHT'
            m_c.label(text="Velocity Threshold ")
            # Oculto condition > o < por ahora
            # condition = m_c.row(align=True)
            # condition.scale_x = 0.4
            # condition.prop(p_create, "condition", text="")
            m_c.prop(p_create, "velocity_threshold", text="")

            ps_limiter = motions_content.row(align=True, heading="PS Limit")
            ps_limiter.prop(p_create, "limit_ps_per_chunk", text="")
            ps_limiter = ps_limiter.row(align=True)
            ps_limiter.enabled = p_create.limit_ps_per_chunk
            ps_limiter.prop(p_create, "max_ps_count", text="", slider=True)

        sub = container.column()
        sub.prop(p_create, "by_selection", text="Use Selected Chunks")
        sub.prop(p_create, "force_update_broken_motion", text="Force Update Broken/Motion")

        ######################

        # Create Operator.
        op_create = container.row()
        op_create.scale_y = 1.3
        op_create.operator("rbdlab.particles_create", text="Create %s" % self.p_type.capitalize(),).type = self.p_type

        if rbdlab.low_or_high_visibility_viewport != "Low":
            op_create.enabled = False
            alert = layout.row()
            alert.box().label(text="Please, working in low visualization mode!", icon='ERROR')
        else:
            # op_create.enabled = True

            # si existe domain no permitimos crear particulas:
            # if exist_domain:
            #     op_create.enabled = False
            # else:
            #     op_create.enabled = True

            if self.rbw:

                if not self.rbw.point_cache.is_baked:

                    # si se detectan keyframes se da por hecho q tiene bake a keyframes y no se muestra el label:
                    if tcoll:
                        valid_objects = [
                            obj for obj in tcoll.objects
                            if obj.type == 'MESH' and obj.visible_get() and obj.name != RBDLabNaming.GROUND and
                            RBDLabNaming.SUFIX_BBOX
                            not in obj.name and RBDLabNaming.PASSIVE
                            not in obj and obj.animation_data is not None and obj.animation_data.action is
                            not None and len(obj.animation_data.action.fcurves) > 0]

                        # comento los msg de outdated
                        if not valid_objects:
                            msg_cache_status = self.rbw.point_cache.info
                            if "outdated" in msg_cache_status:
                                op_create.enabled = False

        # lock and message if it is not baked to keyframes:
        # rbdlab = context.scene.rbdlab
        # valid_objects = None
        # if rbdlab.filtered_target_collection:
        #     coll_name = rbdlab.filtered_target_collection.name
        #     if coll_name:
        #         valid_objects = [obj for obj in bpy.data.collections[coll_name].objects if obj.type == 'MESH' and obj.visible_get() and obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name and RBDLabNaming.PASSIVE not in obj and obj.animation_data is not None and obj.animation_data.action is not None and len(obj.animation_data.action.fcurves) > 0]
        #
        # if valid_objects:
        #     op_create.enabled = True
        #     # col_p_col.enabled = True
        # else:
        #     op_create.enabled = False
        #     # col_p_col.enabled = False
        #     col_msg.alert = True
        #     msg_box = col_msg.box()
        #     msg_box.label(text="Bake to keyframes is mandatory!", icon='ERROR')

        # if p_type == "dust":
        #     # op_create.operator("rbdlab.particles_duplicate",
        #     op_create.operator("rbdlab.particles_create",
        #                        text="Create from Debris").from_debris = True

    def acttion_update_buttons(self, context, layout):
        actions = layout.column(align=True)

        # Update Operator.
        op_update = actions.row(align=True)
        op_update.scale_y = 1.3
        op_update.operator("rbdlab.particles_update", text="Update", icon='FILE_REFRESH').type = self.p_type

        # Delete Operator.
        op_delete = op_update.row(align=True)
        # op_delete.scale_y = 1.3
        op_delete.alert = True
        op_delete.operator("rbdlab.particles_remove", text="Remove %s" %
                           self.p_type.capitalize(), icon='TRASH').type = self.p_type

    def draw_update_options(self, context, layout, main_col, rbdlab):
        ui = rbdlab.ui

        tcoll = rbdlab.filtered_target_collection

        rbdlab_particles = getattr(rbdlab.particles, self.p_type)
        # print(self.ps_props)
        # print(self.p_type)
        # print(rbdlab_particles)
        # print(rbdlab_particles.display_method)

        subsections = layout.box().row(align=True)
        subsections.use_property_split = False
        subsections.scale_y = 1.3
        subsections.prop(ui, "particles_update_sections", expand=True, text=" ")

        main_col = layout.box().column(align=True)

        viewport_display = collapsable(
            main_col,
            ui,
            "show_hide_viewport_display",
            "Viewport Display",
            align=True,
        )
        if viewport_display:

            custom_methods = viewport_display.row(align=True)
            custom_methods.scale_y = 1.3
            custom_methods.prop(self.ps_props, "display_method", text="Display", expand=True)

            if rbdlab_particles.display_method != 'NONE':

                # muestro el color de las particulas si esta en modo point
                if rbdlab_particles.display_method == 'DOT' and rbdlab_particles.display_color == 'MATERIAL':

                    if tcoll:

                        valid_objects = [obj for obj in tcoll.objects if RBDLabNaming.INNER_CHUNK in obj]
                        all_mats = []
                        p_mat_name = RBDLabNaming.PARTICLES_MAT

                        for obj in valid_objects:
                            for mat in obj.material_slots:
                                if mat.material is None:
                                    continue
                                mat_name = mat.material.name
                                if mat_name.startswith(p_mat_name) and mat_name.endswith(self.p_type):
                                    all_mats.append(mat.material)

                        # print(self.p_type, all_mats)
                        if all_mats:
                            mat = all_mats[0]
                            # print(mat.name)
                            viewport_display.prop(mat, "diffuse_color", text="Color")

                # la muestro en modo rendered porque también afectará al particle size:
                # esta tendrá que manipular tanto el size render como el size viewport:

                viewport_display.prop(self.ps_props, "display_size", text="Size Particles")

                if rbdlab_particles.display_method == 'RENDER':
                    viewport_display.prop(self.ps_props, "size_random", text="Size Random")

                if rbdlab_particles.display_method == 'DOT':
                    viewport_display.prop(self.ps_props, "display_color", text="Color")

                if rbdlab_particles.display_method == 'RENDER':
                    viewport_display.prop(self.ps_props, "debris_coll", text="Collection")

                if self.p_type != "smoke":
                    disp_2 = viewport_display.column(align=True)
                    disp_2.prop(self.ps_props, "show_instancer_for_viewport", text="Show Emitter in Viewport")
                    disp_2.prop(self.ps_props, "show_instancer_for_render", text="Show Emitter in Render")

        main_col.separator()

        if ui.particles_update_sections == 'EMISSION':
            emission = collapsable(
                main_col,
                ui,
                "show_hide_emission",
                "Emission",
                align=True,
            )
            if emission:
                # emission.prop(ps_props, "seed", text="Seed")
                emission.prop(self.ps_props, "count", text="Count")

                emission.prop(self.ps_props, "frame_offset", slider=True)

                # New neighbor system
                # content.prop(self.ps_props, "offset", text="Offset", slider=True)

                trails = emission.column(align=True, heading="Use End Trails")
                row_trails = trails.row(align=True)
                row_trails.prop(self.ps_props, "enable_end_trails", text="")
                row_sub_trail = row_trails.row(align=True)
                row_sub_trail.prop(self.ps_props, "end_trails", text="")
                row_sub_trail.enabled = self.ps_props.enable_end_trails

                # if p_type == "smoke":
                emission.prop(self.ps_props, "lifetime", text="Lifetime")
                emission.prop(self.ps_props, "lifetime_random", text="Lifetime Random")
                # content.prop(ps_props, "max_trails", text="max_trails")

                # estas estaban en redner pero ahora en emission:
                emission.prop(self.ps_props, "use_dead", text="Dead")

        elif ui.particles_update_sections == 'PHYSICS':
            velocity_and_rotation = collapsable(
                main_col,
                ui,
                "show_hide_velociry_and_rotation",
                "Velocity and Rotation",
                align=True,
            )
            if velocity_and_rotation:
                velocity = velocity_and_rotation.column(align=True)
                velocity.prop(self.ps_props, "normal", text="Normal")
                velocity.separator()
                velocity.prop(self.ps_props, "direction", text="Direction")
                velocity.separator()
                velocity.prop(self.ps_props, "object_velocity", text="Object Velocity")
                velocity.prop(self.ps_props, "velocity_randomize", text="Randomize")

                velocity_and_rotation.separator()
                rotation = velocity_and_rotation.column(align=True)
                rotation.prop(self.ps_props, "use_rotations", text="Rotation")
                if self.ps_props.use_rotations:
                    rotation.prop(self.ps_props, "rotation_mode", text="Orientation Axis")
                    randomize_phase = rotation.row(align=True)

                    randomize_phase.prop(self.ps_props, "rotation_factor_random", text="Randomize | Phase")
                    randomize_phase.prop(self.ps_props, "phase_factor", text="")

                    rotation.prop(self.ps_props, "phase_factor_random", text="Randomize Phase")
                    rotation.prop(self.ps_props, "use_dynamic_rotation", text="Dynamic")

            main_col.separator()
            physics = collapsable(
                main_col,
                ui,
                "show_hide_particles_physics",
                "Physics",
                align=True,
            )
            if physics:
                physics.prop(self.ps_props, "use_multiply_size_mass", text="Multiply Mass with size")
                physics.prop(self.ps_props, "timestep", text="Timestep")
                physics.prop(self.ps_props, "subframes", text="Subframes")

        elif ui.particles_update_sections == 'FIELD_WEIGHTS':
            field_weight = collapsable(
                main_col,
                ui,
                "show_hide_particles_field_weights",
                "Field Weights",
                align=True,
            )
            if field_weight:
                field_weight.prop(self.ps_props, "effector_weights_collection", text="Effector Collection")
                field_weight.separator()
                field_weight.prop(self.ps_props, "all", text="All")
                field_weight.prop(self.ps_props, "gravity", text="Gravity")
                field_weight.prop(self.ps_props, "force", text="Force")
                field_weight.prop(self.ps_props, "vortex", text="Vortex")
                field_weight.prop(self.ps_props, "magnetic", text="Magnetic")
                field_weight.prop(self.ps_props, "harmonic", text="Harmonic")
                field_weight.prop(self.ps_props, "charge", text="Charge")
                field_weight.prop(self.ps_props, "lennardjones", text="Lennard-Jones")
                field_weight.prop(self.ps_props, "wind", text="Wind")
                field_weight.prop(self.ps_props, "curve_guide", text="Curve Guide")
                field_weight.prop(self.ps_props, "texture", text="Texture")
                field_weight.prop(self.ps_props, "smokeflow", text="Fluid Flow")
                field_weight.prop(self.ps_props, "turbulence", text="Turbulence")
                field_weight.prop(self.ps_props, "drag", text="Drag")
                field_weight.prop(self.ps_props, "boid", text="Boid")

        elif ui.particles_update_sections == 'DEBRIS_SETTINGS':
            basic_debris = collapsable(
                main_col,
                ui,
                "show_hide_particles_basic_debris",
                "Basic Debris",
                align=True,
            )
            if basic_debris:
                basic_debris.enabled = all(
                    [self.p_type != "smoke", RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections])

                subdiv_type = basic_debris.row(align=True)
                subdiv_type.scale_y = 1.3
                subdiv_type.prop(self.ps_props, "basic_subdivision_type", expand=True, toggle=True)
                basic_debris.prop(self.ps_props, "basic_subdivision_level", expand=True, toggle=True)

                basic_debris.separator()
                basic_debris.prop(self.ps_props, "basic_decimate_collapse", expand=True, toggle=True)
                basic_debris.prop(self.ps_props, "basic_disp_strength", expand=True, toggle=True)

                basic_debris.separator()
                basic_debris.prop(self.ps_props, "basic_clouds_size", expand=True, toggle=True)
                basic_debris.prop(self.ps_props, "basic_clouds_depth", expand=True, toggle=True)

                basic_debris.separator()
                # materiales ui:
                basic_debris.prop_search(self.ps_props, "basic_outher_material", bpy.data, "materials")
                basic_debris.prop_search(self.ps_props, "basic_inner_material", bpy.data, "materials")

        ########################################################################################
        # botones de abajo:

        main_col.separator()
        self.acttion_update_buttons(self, main_col)

        main_col.separator()

        # link emitters to new collection for compositing
        if self.p_type != "smoke":
            link_button = main_col.row()
            link_button.scale_y = 1.3
            link_button.operator("rbdlab.particles_emitters_to_coll_for_compositor",
                                 text="Link emitters to new collection")

        main_col.separator()

        filter_particles = collapsable(
            main_col,
            ui,
            "show_hide_filter_particles",
            "Filter Particles",
            'FILTER',
            align=True,
        )
        if filter_particles:
            filter_particles.use_property_split = False
            p_type = rbdlab.ui.selected_particle_type

            filter_particles.prop(rbdlab, "particles_mute_size_delimiter", text="Select Small")
            row = filter_particles.row(align=True)
            row.scale_y = 1.3
            row.operator("rbdlab.mute_particles", text="Mute", icon='HIDE_ON').type = p_type
            row.operator("rbdlab.unmute_particles", text="UnMute", icon='HIDE_OFF').type = p_type
            row.operator("rbdlab.select_muted_particles", text="", icon='RESTRICT_SELECT_OFF')

            # texto de feedback de particles muted
            if tcoll:

                filter_particles.separator()
                if "feedback_mute_particles" in tcoll:
                    if tcoll["feedback_mute_particles"]:
                        box = filter_particles.box().column(align=True)
                        # box.alert = True
                        n = 0
                        for text in tcoll["feedback_mute_particles"].split("#####"):
                            if text:
                                if n == 0:
                                    box.label(text=text, icon='INFO')
                                else:
                                    if text.replace(" ", "") == '1':
                                        box.label(text=text + " Chunk")
                                    else:
                                        box.label(text=text + " Chunks")
                                n += 1

            has_particle = rbdlab.has_particles()
            if has_particle:
                filter_particles.enabled = True
            else:
                filter_particles.enabled = False

        custom_debris = collapsable(
            main_col,
            ui,
            "show_hide_custom_debris",
            "Custom Debris",
            align=True,
        )
        if custom_debris:
            # set selection to custom debris:
            custom_debris_col = custom_debris.column(align=True)
            custom_debris_col.scale_y = 1.3
            custom_debris_col.operator("rbdlab.customdebris", text="Create Custom Debris")

            # debris target collection
            # col_tc = layout.column()
            # col_tc.prop(rbdlab, "debris_target_collection", text="Debris", expand=True)

            valid_objects = []

            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.visible_get():
                    if RBDLabNaming.SUFIX_BBOX not in obj.name and RBDLabNaming.GROUND not in obj.name:
                        valid_objects.append(obj)

            if len(valid_objects) > 0:
                custom_debris_col.enabled = True
            else:
                custom_debris_col.enabled = False

        bake_particles = collapsable(
            main_col,
            ui,
            "show_hide_bake_particles",
            "Bake Particles",
            'MOD_PARTICLE_INSTANCE',
            align=True,
        )
        if bake_particles:
            buttons = bake_particles.column(align=True)
            buttons.use_property_split = False

            # bakes de particulas por tipo (es demasiado lento, es inviable):
            # bake_bt = buttons.row(align=True)
            # bake_bt.scale_y = 1.3
            # bake_bt.operator("rbdlab.bake_current_particles_cache", text="Bake " + self.p_type.title() + " Particles")

            # remove bake de particulas por tipo:
            rm_bake_bt = buttons.row(align=True)
            rm_bake_bt.scale_y = 1.3
            rm_bake_bt.operator("rbdlab.bake_free_all_particles_cache",
                                text="Delete " + self.p_type.title() + " Bake Particles").by_type = True
