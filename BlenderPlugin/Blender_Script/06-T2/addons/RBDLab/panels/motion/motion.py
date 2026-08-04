import bpy
from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, cheker_item_visibility


def particles_to_rbd(context, rbdlab, layout, ui):

    maincol = layout.column(align=True)
    second_col = layout.column(align=True)

    # col2.prop_search(rbdlab, "motion_emitter_target_object", bpy.data, "objects")

    # if rbdlab.motion_emitter_target_object is not None:
    obj = context.active_object
    if obj:
        if obj.type == 'MESH' and RBDLabNaming.GROUND not in obj.name:

            if len(obj.particle_systems) == 0:

                creation_options = collapsable(
                    maincol,
                    ui,
                    "show_motion_p_settings",
                    "Particle Settings",
                    'SETTINGS',
                    align=True,
                )
                if creation_options:
                    creation_options.scale_y = 1.3
                    creation_options.operator("rbdlab.motion_add_emitter", text="Emit", icon='PARTICLES')

                    if len(context.selected_objects) > 0:
                        no_is_a_chunk = RBDLabNaming.FROM not in context.selected_objects[0]
                        if no_is_a_chunk:
                            creation_options.enabled = True
                        else:
                            creation_options.enabled = False
                            colbox = maincol.box()
                            msg = colbox.column()
                            msg.box().label(text="Not valid object", icon='ERROR')
                    else:
                        creation_options.enabled = False

            elif len(obj.particle_systems) == 1:
                # print("UI RBDLabNaming.MOTION_OBJECT_EMITTER in obj", RBDLabNaming.MOTION_OBJECT_EMITTER in obj, rbdlab.motion_emitter_target_object)
                if RBDLabNaming.MOTION_OBJECT_EMITTER in obj:
                    # obj = rbdlab.motion_emitter_target_object

                    if "RBDLab_Emitter_motion_module" in obj.modifiers:
                        if obj.modifiers["RBDLab_Emitter_motion_module"].show_viewport and obj.modifiers["RBDLab_Emitter_motion_module"].show_render:
                            maincol.enabled = True
                        else:
                            maincol.enabled = False

                    creation_options = collapsable(
                        maincol,
                        ui,
                        "show_motion_p_settings",
                        "Particle Settings",
                        'SETTINGS',
                        align=True,
                    )
                    if creation_options:

                        p_emission = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_emission",
                            "Emission",
                            'SETTINGS',
                            align=True,
                        )
                        if p_emission:
                            p_emission.prop(obj.particle_systems[0].settings, "count")
                            p_emission.prop(obj.particle_systems[0], "seed")
                            p_emission.separator()
                            p_emission.prop(obj.particle_systems[0].settings, "frame_start")
                            p_emission.prop(obj.particle_systems[0].settings, "frame_end")
                            p_emission.prop(obj.particle_systems[0].settings, "lifetime")

                        p_velocity = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_velocity",
                            "Velocity",
                            'SETTINGS',
                            align=True,
                        )
                        if p_velocity:
                            p_velocity.prop(obj.particle_systems[0].settings, "normal_factor")
                            p_velocity.separator()
                            p_velocity.prop(obj.particle_systems[0].settings, "object_align_factor")
                            p_velocity.separator()
                            p_velocity.prop(obj.particle_systems[0].settings, "factor_random")

                        p_rotations = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_rotations",
                            "Rotations",
                            'SETTINGS',
                            align=True,
                        )
                        if p_rotations:
                            p_rotations.prop(obj.particle_systems[0].settings, "use_rotations")
                            p_rotations2 = p_rotations.column()
                            p_rotations2.prop(obj.particle_systems[0].settings,
                                              "rotation_factor_random", text="Random")
                            p_rotations2.prop(obj.particle_systems[0].settings, "use_dynamic_rotation")
                            p_rotations2.enabled = obj.particle_systems[0].settings.use_rotations

                        p_physics = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_physics",
                            "Physics",
                            'SETTINGS',
                            align=True,
                        )
                        if p_physics:
                            p_physics.prop(obj.particle_systems[0].settings, "mass")
                            p_physics.prop(obj.particle_systems[0].settings, "use_multiply_size_mass")

                        p_render = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_render",
                            "Render",
                            'SETTINGS',
                            align=True,
                        )
                        if p_render:
                            p_render.prop(obj.particle_systems[0].settings, "particle_size")
                            p_render.prop(obj.particle_systems[0].settings, "size_random")
                            p_render.prop(obj, "show_instancer_for_render", text="Show Emitter")
                            p_render.separator()
                            p_render.prop_search(rbdlab, "motion_object_for_emit", bpy.data, "objects")

                        p_viewport_display = collapsable(
                            creation_options,
                            ui,
                            "show_motion_p_viewport_display",
                            "Viewport Display",
                            'SETTINGS',
                            align=True,
                        )
                        if p_viewport_display:
                            p_viewport_display.prop(obj, "show_instancer_for_viewport", text="Show Emitter")

                        p_conversion = collapsable(
                            creation_options,
                            ui,
                            "show_conversion",
                            "Conversion",
                            'SETTINGS',
                            align=True,
                        )
                        if p_conversion:
                            p_conversion.separator()
                            k_end = p_conversion.column()
                            k_end.prop(rbdlab, "motion_ps_to_rbd_kinematics_end", text="Kinematics End")
                            k_end.separator()
                            row = p_conversion.row(align=True)

                            bt1 = row.column(align=True)
                            bt1.scale_y = 1.5
                            bt1.operator("rbdlab.motion_convert_ps_to_rbd",
                                         text="Convert", icon='OUTLINER_OB_POINTCLOUD')

                            bt2 = row.column(align=True)
                            bt2.scale_y = 1.5
                            bt2.alert = True
                            bt2.operator("rbdlab.motion_remove_emitter", text="Remove", icon='TRASH')
                            k_end.enabled = maincol.enabled
                            bt1.enabled = maincol.enabled
                else:
                    creation_options = collapsable(
                        layout,
                        ui,
                        "show_motion_p_settings",
                        "Particle Settings",
                        'SETTINGS',
                        align=True,
                    )
                    if creation_options:
                        creation_options.scale_y = 1.3
                        creation_options.operator("rbdlab.motion_add_emitter", text="Emit", icon='PARTICLES')
                        creation_options.enabled = len(context.selected_objects) > 0

                # RBD Settings
                #########################################################################################

                if "rbdlab_motion_collection_id" in obj:
                    maincol.separator()
                    rbd_settings = collapsable(
                        second_col,
                        ui,
                        "show_motion_rb_settings",
                        "RigidBodies Settings",
                        'SETTINGS',
                        align=True,
                    )
                    if rbd_settings:
                        rbd_settings.prop(rbdlab, "motion_p_to_rbd_show_hide_toggle", text="Show/Hide Copies")
                        # rbd_settings.prop(rbdlab.motion, "avalidable_mass")
                        rbd_settings.prop(rbdlab.motion, "mass")
                        rbd_settings.prop(rbdlab.motion, "collision_shape")
                        rbd_settings.prop(rbdlab.motion, "friction")
                        rbd_settings.prop(rbdlab.motion, "restitution")
                        rbd_settings.prop(rbdlab.motion, "use_margin")
                        rbd_coll_margin = rbd_settings.column(align=True)
                        rbd_coll_margin.prop(rbdlab.motion, "collision_margin")
                        rbd_coll_margin.enabled = rbdlab.motion.use_margin
        else:
            colbox = maincol.box()
            msg = colbox.column()
            msg.box().label(text="Not valid object", icon='ERROR')
    else:
        colbox = maincol.box()
        msg = colbox.column()
        msg.label(text="Not object selected!", icon='INFO')


def quick_rbd(context, rbdlab, layout, ui, obj, rbo):
    quick_rbd = collapsable(
        layout,
        ui,
        "show_fracture_restore",
        "Selected Single Object",
        'PHYSICS',
        align=True,
    )
    if quick_rbd:
        quick_rbd.scale_y = 1.3
        quick_rbd_row = quick_rbd.row(align=True)
        quick_rbd_row.operator("rbdlab.motion_set_rbd", text="Set RBD")
        quick_rbd_row.operator("rbdlab.motion_set_kinematic", text="Set Kinematic", icon='KEY_HLT')
        if obj:

            if obj.type == 'MESH':
                if rbo is None and len(context.selected_objects) == 1 and RBDLabNaming.ACTIVATORS_OBJECTS not in obj:
                    quick_rbd.enabled = True
                else:
                    quick_rbd.enabled = False
            else:
                quick_rbd.enabled = False
                box1 = layout.box()
                col1 = box1.column()
                col1.box().label(text="Not valid object", icon='ERROR')

        if obj:
            if obj.type == 'MESH' and rbo is not None and len(context.selected_objects) == 1:
                if "rbdlab_motion_rbd" in obj or "rbdlab_motion_kinematic" in obj:
                    box1 = layout.box()
                    col1 = box1.column()
                    # col1.alert = True

                    # rbdlab_motion_kinematic
                    if "rbdlab_motion_kinematic" in obj:
                        # col1.label(text=obj.name + " " + rbo.type.capitalize(), icon='INFO')
                        col1.box().label(text=obj.name + " Kinematic", icon='INFO')

                    if "rbdlab_motion_rbd" in obj:
                        # col1.label(text=obj.name + " " + rbo.type.capitalize(), icon='INFO')
                        col1.box().label(text=obj.name + " " + obj.rigid_body.type.capitalize(), icon='INFO')

                    col1.alert = False
                    # col1.prop(rbdlab.motion, "mass", text="Mass")
                    if "rbdlab_motion_kinematic" in obj:
                        col1.prop(rbo, "mass", text="Mass")

                    if "rbdlab_motion_kinematic" not in obj:
                        col1.prop(rbo, "type", text="Type")
                        col1.prop(rbo, "mass", text="Mass")

                        col1.prop(rbo, "kinematic", text="Kinematic")

                    # Motion > Particles to Rigidbodies:
                    col1.prop(rbo, "collision_shape", text="Shape")
                    col1.prop(rbo, "friction", text="Friction")
                    col1.prop(rbo, "restitution", text="Bounciness")

                    row1 = col1.row(align=True)
                    row1.prop(rbo, "use_margin", text="Collision Margin")
                    row2 = col1.row(align=True)
                    row2.prop(rbo, "collision_margin", text="Margin")
                    row2.enabled = rbo.use_margin
                    row3 = col1.row(align=True)
                    if "rbdlab_motion_kinematic" in obj:
                        row3.prop(rbdlab.motion, "offset_amount", text="Offset Keyframes")
                        row3.operator("rbdlab.motion_offset", text="<-").direction = "backward"
                        row3.operator("rbdlab.motion_offset", text="->").direction = "forward"
                    # col1.alert = True
                    if "rbdlab_motion_kinematic" in obj:
                        col1.box().label(
                            text="Deactivate in frame: " + str(obj["rbdlab_motion_kinematic"]),
                            icon='INFO')
                        bt = col1.row(align=True)
                        bt.scale_y = 1.3
                        bt.alert = True
                        bt.operator("rbdlab.motion_rm_kinematic", text="Remove Kinematic", icon='TRASH')

                    if "rbdlab_motion_rbd" in obj:
                        bt = col1.row(align=True)
                        bt.scale_y = 1.3
                        bt.alert = True
                        bt.operator(
                            "rbdlab.motion_rm_rbd", text="Remove " + obj.rigid_body.type.capitalize(),
                            icon='TRASH')
            # else:
            #     if obj.type != 'MESH':
            #         box1 = layout.box()
            #         col1 = box1.column()
            #         # col1.alert = True
            #         # col1.scale_y = 1.3
            #         col1.box().label(text="Not valid object", icon='ERROR')

            # box2 = col.box()
            # col2 = box2.column(align=True)
            # col2.label(text="Convert particle system in rigidbodies")
            # col2.prop_search(rbdlab, "motion_emitter_target_object", bpy.data, "objects")
            # col2.prop_search(rbdlab, "motion_object_for_emit", bpy.data, "objects")
            # col2.prop(rbdlab, "motion_ps_to_rbd_kinematics_end", text="So Far")
            # col2.operator("rbdlab.motion_convert_ps_to_rbd", text="Convert")


class QUICK_RIGIDBODIES_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'MOTION'
    bl_label = "Module"
    bl_idname = "QUICK_RIGIDBODIES_PT_ui"


    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ui = rbdlab.ui

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # layout.enabled = cheker_item_visibility(rbdlab, layout)

        col = layout.column(align=True)

        title_header(col, "Motion")

        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        switch_subcats = main_col.row(align=True)
        switch_subcats.use_property_split = False
        switch_subcats.scale_y = 1.3
        switch_subcats.prop(ui, "motion_switch_subsections", expand=True)
        # main_col.separator()

        obj = context.active_object
        rbo = None
        if obj:
            rbo = obj.rigid_body

        if ui.motion_switch_subsections == 'QUICK_RIGIDBODIES':
            quick_rbd(context, rbdlab, col, ui, obj, rbo)

        elif ui.motion_switch_subsections == 'PARTICLES_TO_RIGIDBODIES':
            col_particles = col.column(align=True)
            col_particles.enabled = cheker_item_visibility(context)
            particles_to_rbd(context, rbdlab, col_particles, ui)
