import bpy
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import collapsable, draw_collision_collections


def ground_settings(rbdlab, layout, ui):

    all_lay = layout.column(align=True)
    all_lay.enabled = rbdlab.low_or_high_visibility_viewport == "Low"
    
    sublayout = all_lay.column(align=True)

    sublayout.use_property_split = True
    sublayout.use_property_decorate = False

    if rbdlab.root_collection:
        grounds = [obj for obj in rbdlab.root_collection.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    else:
        grounds = [obj for obj in bpy.data.objects if obj.name.startswith(RBDLabNaming.GROUND)]

    if not grounds:
        col1 = sublayout.box().column(align=True)
        col1.operator("rbdlab.add_ground", text="Add Ground")
        col1.scale_y = 1.3
    else:
        ground = grounds[0]

        # col0 = sublayout.column()
        # col1 = col0.column(align=True)

        # layout.use_property_split = False
        # flow = layout.grid_flow(align=True)

        ground_visualization = collapsable(
            sublayout,
            ui,
            "show_hide_physics_ground_visualization",
            "Ground Visualization",
            'VIEW_PERSPECTIVE',
            align=True,
        )
        if ground_visualization:
            row = ground_visualization.row(align=True)
            row.scale_y = 1.3
            row.use_property_split = False

            if rbdlab.show_hide_ground:
                icon_hide_ground = 'HIDE_OFF'
                text_hide = "Visible   "
            else:
                text_hide = "Hidden   "
                icon_hide_ground = 'HIDE_ON'

            row.prop(rbdlab, "show_hide_ground", text=text_hide, expand=True, toggle=True, icon=icon_hide_ground)

            if rbdlab.show_wire_ground:
                text_wire = "Textured"
                icon_wire_ground = 'TEXTURE'
            else:
                text_wire = "Wire      "
                icon_wire_ground = 'MOD_WIREFRAME'

            row.prop(rbdlab, "show_wire_ground", text=text_wire, expand=True, toggle=True, icon=icon_wire_ground)

            row.prop(rbdlab, "selectable_ground", text="Selectable", expand=True, toggle=True,
                     icon='RESTRICT_SELECT_OFF' if rbdlab.selectable_ground else 'RESTRICT_SELECT_ON')

        ground_dimensions = collapsable(
            sublayout,
            ui,
            "show_hide_physics_ground_dimensions",
            "Dimensions",
            'FIXED_SIZE',
            align=True,
        )
        if ground_dimensions:
            ground_dimensions.prop(rbdlab, "ground_x", text="Size X")
            ground_dimensions.prop(rbdlab, "ground_y", text="Size Y")

        ground_rbd_collisions = collapsable(
            sublayout,
            ui,
            "show_hide_physics_ground_rbd_collisions",
            "RigidBodies Collision",
            'CON_SHRINKWRAP',
            align=True,
        )
        if ground_rbd_collisions:
            ground_rbd_collisions.prop(ground.rigid_body, "friction")
            ground_rbd_collisions.prop(ground.rigid_body, "restitution", text="Bounciness")

        ground_particle_collision = collapsable(
            sublayout,
            ui,
            "show_hide_physics_ground_particle_collision",
            "Particle Collision",
            'ANCHOR_TOP',
            align=True,
        )
        if ground_particle_collision:
            ground_particle_collision.prop(ground.collision, "friction_factor")
            ground_particle_collision.prop(ground.collision, "damping_factor")
            ground_particle_collision.prop(ground.collision, "stickiness")
            ground_particle_collision.prop(ground.collision, "use_particle_kill")
        

        if ground:
            collections = collapsable(
                sublayout,
                ui,
                "show_hide_rbd_ground_collections",
                "Collision Collections",
                'OUTLINER_COLLECTION',
                align=True,
            )
            if collections:
                col = draw_collision_collections(collections, ground, "rbd_ground_collections")
