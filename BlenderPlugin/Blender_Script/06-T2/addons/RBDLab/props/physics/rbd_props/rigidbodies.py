import bpy
from ....addon.naming import RBDLabNaming
from bpy.types import PropertyGroup, Area
from .animations import RBDLAB_PG_rbd_animations
from ....Global.basics import select_object, context_override
from bpy.props import EnumProperty, BoolProperty, FloatProperty, StringProperty, PointerProperty


class RBDLAB_PG_rigidbodies(PropertyGroup):
    """ context.scene.rbdlab.physics.rigidbodies.x """

    animation: PointerProperty(type=RBDLAB_PG_rbd_animations)

    custom_mass: FloatProperty(
        name="custom_mass",
        description="Density value (kg/m^3), allows custom value",
        default=1,
        min=0,
        soft_min=1,
        max=1000000000,
    )
    metal_mass: FloatProperty(
        name="metal_mass",
        description="Metallic mass",
        default=0.5,
        min=0,
        max=1000000000,
    )

    def avalidable_mass_update(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if not tcoll:
            return
        
        if len(tcoll.objects) < 1:
            return
        
        ob = tcoll.objects[0]
        if not ob:
            return
        
        physics_props = rbdlab.physics
        rbd_props = physics_props.rigidbodies
        
        if RBDLabNaming.CUSTOM_MASS in ob:
            rbd_props.custom_mass = ob[RBDLabNaming.CUSTOM_MASS]
        else:
            rbd_props.custom_mass = rbd_props.get_default_properties("custom_mass")

        if RBDLabNaming.METAL_MASS in ob:
            rbd_props.metal_mass = ob[RBDLabNaming.METAL_MASS]
        else:
            rbd_props.metal_mass = rbd_props.get_default_properties("metal_mass")


    avalidable_mass: EnumProperty(
        items = [
            ("Air",                     "Air",                      "",     0),
            ("Acrylic",                 "Acrylic",                  "",     1),
            ("Asphalt (Crushed)",       "Asphalt (Crushed)",        "",     2),
            ("Bark",                    "Bark",                     "",     3),
            ("Beans (Cocoa)",           "Beans (Cocoa)",            "",     4),
            ("Beans (Soy)",             "Beans (Soy)",              "",     5),
            ("Brick (Pressed)",         "Brick (Pressed)",          "",     6),
            ("Brick (Common)",          "Brick (Common)",           "",     7),
            ("Brick (Soft)",            "Brick (Soft)",             "",     8),
            ("Brass",                   "Brass",                    "",     9),
            ("Bronze",                  "Bronze",                   "",     10),
            ("Carbon (Solid)",          "Carbon (Solid)",           "",     11),
            ("Cardboard",               "Cardboard",                "",     12),
            ("Cast Iron",               "Cast Iron",                "",     13),
            ("Chalk (Solid)",           "Chalk (Solid)",            "",     14),
            ("Concrete",                "Concrete",                 "",     15),
            ("Charcoal",                "Charcoal",                 "",     16),
            ("Cork",                    "Cork",                     "",     17),
            ("Copper",                  "Copper",                   "",     18),
            ("Garbage",                 "Garbage",                  "",     19),
            ("Glass (Broken)",          "Glass (Broken)",           "",     20),
            ("Glass (Solid)",           "Glass (Solid)",            "",     21),
            ("Gold",                    "Gold",                     "",     22),
            ("Granite (Broken)",        "Granite (Broken)",         "",     23),
            ("Granite (Solid)",         "Granite (Solid)",          "",     24),
            ("Gravel",                  "Gravel",                   "",     25),
            ("Ice (Crushed)",           "Ice (Crushed)",            "",     26),
            ("Ice (Solid)",             "Ice (Solid)",              "",     27),
            ("Iron",                    "Iron",                     "",     28),
            ("Lead",                    "Lead",                     "",     29),
            ("Limestone (Broken)",      "Limestone (Broken)",       "",     30),
            ("Limestone (Solid)",       "Limestone (Solid)",        "",     31),
            ("Marble (Broken)",         "Marble (Broken)",          "",     32),
            ("Marble (Solid)",          "Marble (Solid)",           "",     33),
            ("Paper",                   "Paper",                    "",     34),
            ("Peanuts (Shelled)",       "Peanuts (Shelled)",        "",     35),
            ("Peanuts (Not Shelled)",   "Peanuts (Not Shelled)",    "",     36),
            ("Plaster",                 "Plaster",                  "",     37),
            ("Plastic",                 "Plastic",                  "",     38),
            ("Polystyrene",             "Polystyrene",              "",     39),
            ("Rubber",                  "Rubber",                   "",     40),
            ("Silver",                  "Silver",                   "",     41),
            ("Steel",                   "Steel",                    "",     42),
            ("Stone",                   "Stone",                    "",     43),
            ("Stone (Crushed)",         "Stone (Crushed)",          "",     44),
            ("Timber",                  "Timber",                   "",     45),
            ("Custom",                  "Custom",                   "",     46)
    ],
        name="avalidable_mass",
        description="Item",
        default="Concrete",
        update=avalidable_mass_update
    )

    # collision_shape_combobox: EnumProperty(
    #     items=(
    #         ('CONVEX_HULL', "Convex Hull",
    #          "Convex dont support concave objects but is very fast", 0),
    #         ('MESH', "Mesh", "Mesh allow concave objects bus is very slow", 1)
    #     ),
    #     name="Collision Shape",
    #     description="Type of collision shape",
    #     default='CONVEX_HULL'
    # )

    # Physics > RBD Settings:
    collision_shape: EnumProperty(
        name="Shape",
        description="Type of collision shape",
        items=[
            ('BOX',         "Box", "", 'MESH_CUBE', 0),
            ('SPHERE',      "Sphere", "", 'MESH_UVSPHERE', 1),
            ('CAPSULE',     "Capsule", "", 'MESH_CAPSULE', 2),
            ('CYLINDER',    "Cylinder", "", 'MESH_CYLINDER', 3),
            # ('CONE',        "Cone", "", 'MESH_CONE', 4),
            ('CONVEX_HULL', "Convex Hull", "", 'MESH_ICOSPHERE', 5),
            ('MESH',        "Mesh", "", 'MESH_MONKEY', 6),
            # ('COMPOUND',    "Compound Parent", "", 'MESH_DATA', 7),
        ],
        default='CONVEX_HULL',
    )
    rm_chunks_with_low_mass: BoolProperty(name="Remove chunks", description="Remove chunks with extremely low mass", default=True)

    use_collision_margin: BoolProperty(
        default=True,
    )
    collision_margin: FloatProperty(
        default=0.00001,
        min=0.00000,
        max=1,
        precision=5,
        name="Collision Margin",
    )

    rb_friction: FloatProperty(
        name="Friction",
        default=0.7,
        min=0,
        max=1
    )
    restitution: FloatProperty(
        name="Bounciness",
        min=0,
        max=1,
        default=0
    )

    dynamic: BoolProperty(
        default=True
    )

    d_translation: FloatProperty(
        name="Damping Translation",
        default=0.1,
        min=0,
        max=1,
    )
    d_rotation: FloatProperty(
        name="Damping Rotation",
        default=0.5,
        min=0,
        max=1,
    )

    deactivation: BoolProperty(
        default=True,
        description="Enable deactivation of resting rigid bodies (increases performance and stability but can cause glitches)."
    )

    use_start_deactivated: BoolProperty(
        default=False,
        description="Deactivate rigid body at the start of the simulation."
    )

    deactivate_linear_velocity: FloatProperty(
        min=0,
        default=0.4,
        unit='VELOCITY',
        description="Linear velocity below which simulation stops simulating object."
    )

    deactivate_angular_velocity: FloatProperty(
        min=0,
        default=0.5,
        unit='VELOCITY',
        description="Angular velocity below which simulation stops simulating object."
    )

    kinematic: BoolProperty(
        default=False,
        description="In blender is (Animated attribute) and is used to animate objects with rigid body properties."
    )
    kinematic_keyframes: StringProperty(
        default='0'
    )

    def show_hide_passives_update(self, context):
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                if hasattr(obj, "rigid_body"):
                    if hasattr(obj.rigid_body, "type"):
                        if obj.rigid_body.type == 'PASSIVE' and obj.name.lower() != "ground":
                            if not self.show_hide_passives:
                                obj.hide_set(True)
                            else:
                                obj.hide_set(False)

    show_hide_passives: BoolProperty(
        default=True,
        update=show_hide_passives_update
    )

    def show_hide_sele_kinematics_update(self, context):
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                if RBDLabNaming.RBD_SEL_KINEMATIC in obj:
                    # obj.hide_viewport = self.show_hide_sele_kinematics
                    if not self.show_hide_sele_kinematics:
                        obj.hide_set(True)
                    else:
                        obj.hide_set(False)

    show_hide_sele_kinematics: BoolProperty(
        default=True,
        update=show_hide_sele_kinematics_update
    )

    def edit_handler_toggle_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                objects = rbdlab.filtered_target_collection.objects
                if objects:
                    

                    # guardo transform orientation y lo seteo en local:
                    if context.scene.transform_orientation_slots[0].type != 'LOCAL':
                        rbdlab.eth_trans_orientation = context.scene.transform_orientation_slots[0].type
                        context.scene.transform_orientation_slots[0].type = 'LOCAL'

                    if not hasattr(bpy.types.WindowManager, "user_snap"):
                        bpy.types.WindowManager.user_snap = context.scene.tool_settings.snap_elements
                    else:
                        if context.scene.tool_settings.snap_elements != {'VERTEX'}:
                            bpy.types.WindowManager.user_snap = context.scene.tool_settings.snap_elements

                    # obtenemos su handler del listado de target collections:
                    active_item = rbdlab.lists.target_coll_list.active_item
                    handler = active_item.handler
                    if handler:
                        select_object(context, handler)

                    if rbdlab.physics.rigidbodies.edit_handler_toggle:
                        context.scene.tool_settings.snap_elements = {'VERTEX'}
                        
                        # sobreescribir el contexto:
                        def callback(area:Area) -> None:
                            area = context.area  # Accedemos al área desde el contexto
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    context.space_data.show_gizmo_object_translate = True
                                    context.space_data.show_gizmo_object_rotate = True
                                    context.space_data.show_gizmo_object_scale = True
                            area.tag_redraw()
                        context_override(context=context, area_type='VIEW_3D', callback=callback)
                        context.scene.tool_settings.use_transform_skip_children = True

                    else:
                        if hasattr(bpy.types.WindowManager, "user_snap"):
                            context.scene.tool_settings.snap_elements = bpy.types.WindowManager.user_snap
                        
                        # sobreescribir el contexto:
                        def callback(area:Area) -> None:
                            area = context.area  # Accedemos al área desde el contexto
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    context.space_data.show_gizmo_object_translate = rbdlab.eth_icons_t
                                    context.space_data.show_gizmo_object_rotate = rbdlab.eth_icons_r
                                    context.space_data.show_gizmo_object_scale = rbdlab.eth_icons_s
                            area.tag_redraw()
                        context_override(context=context, area_type='VIEW_3D', callback=callback)

                        # restore transform orientation:
                        context.scene.transform_orientation_slots[0].type = rbdlab.eth_trans_orientation

                        # if bbox_name in bpy.context.scene.objects:
                        #     context.scene.objects[bbox_name].select_set(False)
                        context.scene.tool_settings.use_transform_skip_children = False
                    # del bpy.types.WindowManager.user_snap

    edit_handler_toggle: BoolProperty(
        default=False,
        update=edit_handler_toggle_update
    )

    def show_hide_handler_toggle_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                objects = rbdlab.filtered_target_collection.objects
                if objects:

                    bbox_name = RBDLabNaming.SUFIX_BBOX
                    valid_bboxes = [ob for ob in context.view_layer.objects if bbox_name in ob.name]
                    if valid_bboxes:
                        bbox_object = valid_bboxes[-1]
                        if bbox_object:
                            if rbdlab.physics.rigidbodies.show_hide_handler_toggle:
                                bbox_object.hide_set(True)
                            else:
                                bbox_object.hide_set(False)

    show_hide_handler_toggle: BoolProperty(
        default=False,
        update=show_hide_handler_toggle_update
    )

    # compounds parented visibility
    def edge_compound_visibility_update(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and RBDLabNaming.NO_SHAPE_OBJ in obj]

                if valid_objects:

                    for obj in valid_objects:
                        if self.edge_compound_visibility:
                            obj.hide_set(False)
                            obj.select_set(True)
                        else:
                            obj.hide_set(True)

    edge_compound_visibility: BoolProperty(
        name="Hide/Show",
        default=True,
        update=edge_compound_visibility_update
    )

    edge_remove_keep_transforms: BoolProperty(
        name="Keep Transforms",
        description="When Remove, the original chunks are set to the initial coordinates",
        default=True
    )

    @staticmethod
    def select_edges_parent_childs_compounds_update(self, context, condition):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                coll_objs = rbdlab.filtered_target_collection.objects

                compounds = [obj for obj in coll_objs if obj.type == 'MESH' and RBDLabNaming.NO_SHAPE_OBJ in obj]

                # with or without parents:
                if condition:
                    targets = [obj for obj in coll_objs if obj.parent in compounds and RBDLabNaming.NO_SHAPE_OBJ not in obj]
                else:
                    targets = [
                        obj for obj in coll_objs
                        if obj.parent not in compounds and RBDLabNaming.NO_SHAPE_OBJ not in obj]

                # print("compounds:", compounds)
                # print("targets:", targets)

                if len(targets) > 0:
                    # deselect_all_objects(context)
                    for obj in targets:
                        if condition:
                            if self.select_edges_parent_childs_compounds:
                                obj.select_set(True)
                            else:
                                obj.select_set(False)
                        else:
                            if self.select_edges_parent_not_childs_compounds:
                                obj.select_set(True)
                            else:
                                obj.select_set(False)

    select_edges_parent_childs_compounds: BoolProperty(
        name="Select/Deselect",
        description="Select those who are children of Compounds",
        default=False,
        update=lambda self, context: self.select_edges_parent_childs_compounds_update(self, context, True)
    )

    select_edges_parent_not_childs_compounds: BoolProperty(
        name="Select/Deselect",
        description="Select/Deselect those who are not children Compounds",
        default=False,
        update=lambda self, context: self.select_edges_parent_childs_compounds_update(self, context, False)
    )

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default
