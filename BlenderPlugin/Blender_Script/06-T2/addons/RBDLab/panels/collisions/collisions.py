
import bpy
# from ...Global.basics import set_active_object
from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, cheker_item_visibility, multiline_print


class COLLISIONS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'COLLISIONS'
    bl_label = "Module"
    bl_idname = "COLLISIONS_PT_ui"


    def draw(self, context):
        scene = context.scene
        rbdlab = scene.rbdlab

        layout = self.layout

        layout.enabled = cheker_item_visibility(context)

        has_p_collision = rbdlab.has_p_collision()
        ui = rbdlab.ui

        col = layout.column(align=True)
        title_header(col, "Collisions")
        main_col = col.box().column(align=True)
        main_col.use_property_decorate = False

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        # Collision / Collision Static Objects / Single Object Collision
        collision_subsections = main_col.row(align=True)
        collision_subsections.use_property_split = False
        collision_subsections.scale_y = 1.3
        collision_subsections.prop(ui, "collision_module_subsections", expand=True)

        # para saber si hay chunks bakeados a keyframes:
        valid_objects = None
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                valid_objects = [
                    obj for obj in bpy.data.collections[coll_name].objects
                    if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.BAKED_TO_KFRAMES in obj and obj.name
                    != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX
                    not in obj.name and RBDLabNaming.PASSIVE
                    not in obj and obj.animation_data is not None and obj.animation_data.action is
                    not None and len(obj.animation_data.action.fcurves) > 0]

        # have_particles = None
        # if rbdlab.filtered_target_collection:
        #     have_particles = any(
        #         ["particles_debris" in rbdlab.filtered_target_collection or "particles_dust" in rbdlab.filtered_target_collection])

        # main_col.use_property_split = True

        main_col.separator()
        col = main_col.column(align=False)

        col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        if ui.collision_module_subsections == 'COLLISION':

            # collection particle collisions
            particle_collisions = collapsable(
                col,
                ui,
                "show_p_collisions",
                "Particle Collisions",
                'ANCHOR_TOP',
                align=True,
            )
            if particle_collisions:

                # if not have_particles:
                #     col_msg = particle_collisions.box()
                #     # col_msg.alert = True
                #     col_msg.label(text="Is necessary have particles first!", icon='INFO')

                # else:

                # content.label(text="Collision to:")
                # content = p_collision_header.row(align=True)
                # selected_collision = rbdlab.ui.collision_to
                # collision_types = ("low", "high")
                # for p_type in collision_types:
                #     col = content.column(align=True)
                #     selected = selected_collision == p_type
                #     col.scale_y = 1.3
                #     col.operator("rbdlab.collision_select", text=p_type.capitalize(), depress=selected).type = p_type

                # container = p_collision_header.row()
                particle_collisions.prop(rbdlab.ui, "hide_emmiters", text="Hide/UnHide inner faces emitters")
                particle_collisions.separator()

                # print("has_p_collision", has_p_collision)
                if has_p_collision:
                    self.draw_update_options(particle_collisions, rbdlab, ui)
                else:
                    self.draw_create_options(particle_collisions, rbdlab, ui, valid_objects)

        elif ui.collision_module_subsections == 'COLLISION_STATIC_OBJECTS':

            # COLLISIONS STATICK:
            show_coll_to_so_sel = collapsable(
                col,
                ui,
                "show_hide_collision_to_static_objs",
                "Collision to Static Objects",
                'META_CUBE',
                align=True,
            )
            if show_coll_to_so_sel:
                # static_objects = col_static_objs.row(align=True)

                if len(rbdlab.lists.collision_so_list.obj_list) > 0:
                    static_objects_list = show_coll_to_so_sel.column(align=True)
                    static_objects_props = show_coll_to_so_sel.column(align=True)
                    rbdlab_collision_static_objects = rbdlab.lists.collision_so_list
                    static_objects_list.template_list(
                        "COLLISION_SO_UL_group", "", rbdlab_collision_static_objects, "obj_list",
                        rbdlab_collision_static_objects, "obj_list_index", rows=3)

                    # Static Objects properties:
                    static_objects_props.separator()
                    static_objects_props.use_property_split = True
                    static_objects_props.prop(rbdlab.collision, "so_stickiness", text="Stickness", slider=True)
                    static_objects_props.prop(rbdlab.collision, "so_use_particle_kill",
                                              text="Kill Particles", slider=True)
                    static_objects_props.prop(rbdlab.collision, "so_damping_factor",
                                              text="Damping Factor", slider=True)
                    static_objects_props.prop(rbdlab.collision, "so_damping_random",
                                              text="Damping Random", slider=True)
                    static_objects_props.prop(rbdlab.collision, "so_friction_factor",
                                              text="Friction Factor", slider=True)
                    static_objects_props.prop(rbdlab.collision, "so_friction_random",
                                              text="Friction Random", slider=True)
                    static_objects_props.separator()
                    static_objects_update_button = static_objects_props.column(align=True)
                    static_objects_update_button.scale_y = 1.5
                    static_objects_update_button.operator(
                        "collisions.to_static_objects_update", text="Update", icon='FILE_REFRESH')

                static_objects = show_coll_to_so_sel.column(align=True)
                static_objects.scale_y = 1.3
                static_objects.operator("rbdlab.collisions_to_static_objects",
                                        text="Add Static Objects", icon='RESTRICT_SELECT_OFF')
                static_objects.enabled = rbdlab.filtered_target_collection is not None

            # if have_particles is not None:
            #     p_collision_col.enabled = have_particles
            #     content.enabled = have_particles
            #     # container.enabled = have_particles

            # lock and message if it is not baked to keyframes:

        elif ui.collision_module_subsections == 'SINGLE_OBJECT_COLLISION':

            # single object collision:
            have_collision = False
            obj = context.active_object

            show_options = rbdlab.ui.show_p_single_objecy_collisions
            p_collision_col = col.column(align=True)
            p_collision_header = p_collision_col.box()
            p_collision_toggle = p_collision_header.row(align=True)
            p_collision_toggle.use_property_split = False
            p_collision_toggle.alignment = 'LEFT'
            p_collision_toggle.emboss = 'NONE'
            p_collision_toggle.prop(
                rbdlab.ui, "show_p_single_objecy_collisions", icon='DISCLOSURE_TRI_DOWN'
                if show_options else 'DISCLOSURE_TRI_RIGHT', text="")
            p_collision_toggle.prop(rbdlab.ui, "show_p_single_objecy_collisions",
                                    text="Single Object Particle Collisions", icon='ANCHOR_TOP')
            if show_options:
                content = p_collision_header.column(align=True)

                if obj:

                    if "rbdlab_single_obj_p_collision" not in obj:
                        self.draw_creation_single_object_p_collision(content, valid_objects)

                    if obj.type == 'MESH':
                        content.enabled = True
                    else:
                        content.enabled = False

                    for mod in obj.modifiers:
                        if mod.type == 'COLLISION':
                            have_collision = True
                            break

                    if have_collision:
                        if "rbdlab_single_obj_p_collision" in obj:
                            self.draw_settings_single_object_p_collision(content, context, rbdlab, obj)
                            self.draw_remove_single_object_p_collision(p_collision_header, context, rbdlab, obj)
                else:
                    msg_no_active_object = content.row(align=True).box()
                    # msg_no_active_object.alert = True
                    msg_no_active_object.box().label(text="No active Object!", icon='INFO')

            if obj is None:
                p_collision_toggle.enabled = False

    @staticmethod
    def draw_creation_single_object_p_collision(layout, valid_objects):
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.row(align=True)
        col.scale_y = 1.3
        col.operator("rbdlab.p_single_object_collisions_create", text="Add Collision")
        # if not valid_objects:
        #     col.enabled = False
        #     col_msg = layout.box()
        #     col_msg.alert = True
        #     col_msg.label(text="Bake to keyframes is mandatory!", icon='ERROR')

    @staticmethod
    def draw_remove_single_object_p_collision(layout, context, rbdlab, obj):
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()
        col.alert = True
        col.scale_y = 1.5
        col.operator("rbdlab.p_single_object_collisions_remove", text="Remove Collision", icon='TRASH')

    @staticmethod
    def draw_settings_single_object_p_collision(layout, context, rbdlab, obj):
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()

        # rbdlab_motion_kinematic
        if "rbdlab_single_obj_p_collision" in obj:
            col.box().label(text=obj.name + " Particle Collision", icon='INFO')
            col.separator()

        col_prop = col.column()
        # col_prop.prop(rbdlab.collision, "permeability")
        col_prop.prop(obj.collision, "stickiness")
        col_prop.prop(obj.collision, "use_particle_kill")
        col_prop.prop(obj.collision, "damping_factor")
        # col_prop.prop(obj.collision, "damping_random")
        col_prop.prop(obj.collision, "friction_factor")
        col_prop.prop(obj.collision, "friction_random")

    def draw_create_options(self, layout, rbdlab, ui, valid_objects):
        # print("draw create")

        # BAKE ACTION UI:
        show_bake_action_ui = collapsable(
            layout,
            ui,
            "show_hide_bake_action_ui",
            "Bake for collision particles",
            'ONIONSKIN_ON',
            align=True,
        )
        if show_bake_action_ui:
            # content.prop(rbdlab.bake, "bake_action_by_selection", text="By Selection")

            show_bake_action_ui.separator()
            show_bake_action_ui.use_property_split = True
            show_bake_action_ui.prop(rbdlab.bake, "bake_action_start", text="Start")
            show_bake_action_ui.prop(rbdlab.bake, "bake_action_end", text="End")
            show_bake_action_ui.prop(rbdlab.bake, "frame_step", text="Frame Step")
            show_bake_action_ui.use_property_split = False
            show_bake_action_ui.separator()

            # show_bake_action_ui.operator("rbdlab.bake_action_visual_keying", text="Bake Action")
            # check if have baked action

            if rbdlab.filtered_target_collection:
                if RBDLabNaming.BAKED_ACTION in rbdlab.filtered_target_collection:
                    rm_bake_action = show_bake_action_ui.row(align=True)
                    rm_bake_action.alert = True
                    rm_bake_action.scale_y = 1.3
                    rm_bake_action.operator("rbdlab.bake_remove_bake_action", text="Remove Bake Action")

        # COLLISIONS TO:
        layout = layout.column(align=True)
        show_coll_to_options = rbdlab.ui.show_hide_collision_to_sel_coll
        collision_to_sel_coll_header = layout.box()
        collision_to_sel_coll_toggle = collision_to_sel_coll_header.row(align=True)
        collision_to_sel_coll_toggle.use_property_split = False
        collision_to_sel_coll_toggle.alignment = 'LEFT'
        collision_to_sel_coll_toggle.emboss = 'NONE'
        collision_to_sel_coll_toggle.prop(
            rbdlab.ui, "show_hide_collision_to_sel_coll", icon='DISCLOSURE_TRI_DOWN'
            if show_coll_to_options else 'DISCLOSURE_TRI_RIGHT', text="")
        collision_to_sel_coll_toggle.prop(rbdlab.ui, "show_hide_collision_to_sel_coll",
                                          text="Collision to:", icon='CON_SHRINKWRAP')

        # Collisions to Selection/Collection:
        if show_coll_to_options:
            content = collision_to_sel_coll_header.column(align=True)

            if not valid_objects:
                col_msg = content.column(align=True)
                buttons_coll_to = col_msg.row(align=True)
            else:
                buttons_coll_to = content.row(align=True)

            content.prop(rbdlab.collision, "use_clear_parents", text="Clear Parent")
            buttons_coll_to.enabled = True
            buttons_coll_to.scale_y = 1.3
            # op_create.operator("rbdlab.p_collision_to", text="Collisions to %s" % c_type.capitalize(), ).type = c_type

            buttons_coll_to.operator("rbdlab.p_collision_to", text="Selection",
                                     icon='RESTRICT_SELECT_OFF').collision_type = 'SELECTION'
            buttons_coll_to.operator("rbdlab.p_collision_to", text="Collection",
                                     icon='OUTLINER_COLLECTION').collision_type = 'COLLECTION'

            # if not valid_objects:
            #     buttons_coll_to.enabled = False
            #     col_msg.alert = True
            #     msg_box = col_msg.box()
            #     msg_box.label(text="Bake to keyframes is mandatory!", icon='ERROR')

    def draw_update_options(self, layout, rbdlab, ui):
        # print("draw update")

        c_type = rbdlab.ui.collision_to
        layout.use_property_split = True

        col = layout.column().box()
        col_prop = col.column(align=True)

        col_prop.label(text="Update Settings", icon='OPTIONS')
        col_prop.separator()

        col_prop.prop(rbdlab.collision, "permeability")
        col_prop.prop(rbdlab.collision, "stickiness")
        col_prop.prop(rbdlab.collision, "use_particle_kill", toggle=True)
        col_prop.prop(rbdlab.collision, "damping_factor")
        # col_prop.prop(rbdlab.collision, "damping_random")
        col_prop.prop(rbdlab.collision, "friction_random")
        col_prop.prop(rbdlab.collision, "friction_factor")

        col_prop.separator()
        show_options = collapsable(
            col_prop,
            ui,
            "show_collision_through_offset",
            "Through Offset",
            align=True,
        )
        if show_options:

            text = "An offset for the Animated attributes Permeability and Damping"
            multiline_print(show_options, text, max_words=6, first_line_crop=0, without_box=True)

            # offset = content.row()
            offset = show_options.row(align=True)
            offset.scale_y = 1.3
            # offset.prop(rbdlab.collision, "through_offset_direction", toggle=True, expand=True)

            # offset.operator("rbdlab.p_collision_set_through_offset", text="Backward").direction = "backward"
            # offset.operator("rbdlab.p_collision_set_through_offset", text="Forward").direction = "forward"
            show_options.use_property_split = False
            show_options.prop(rbdlab.collision, "through_offset", slider=True)

        buttons = col.row(align=True)
        op_update = buttons.row(align=True)
        op_update.scale_y = 1.3
        op_update.operator("rbdlab.p_collision_update", text="Update", icon='FILE_REFRESH').type = c_type

        # buttons.separator()
        # buttons.prop(rbdlab.ui, "preserve_bake_action", text="Preserve Bake")

        op_remove = buttons.row(align=True)
        op_remove.scale_y = 1.3
        op_remove.alert = True
        # op_remove.operator("rbdlab.p_collision_remove", text="Remove %s Collisions" % c_type.capitalize(), icon='TRASH').type = c_type
        op_remove.operator("rbdlab.p_collision_remove", text="Remove Collisions", icon='TRASH')
