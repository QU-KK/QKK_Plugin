import bpy
from typing import List
from collections import defaultdict
from ..addon.naming import RBDLabNaming
from ..Global.functions import set_shading_color, set_active_object
from ..Global.basics import context_override
from bpy.types import PropertyGroup, Collection, Object, Area
from .when_updating_property import get_objects_centroids
from bpy.props import EnumProperty, BoolProperty, PointerProperty, FloatProperty, IntProperty, StringProperty
from ..Global.get_common_vars import get_common_vars
import datetime


# User Interface management properties.


class RBDLab_PG_UI(PropertyGroup):

    show_hide_target_coll_list: BoolProperty(default=True)

    # Para filtrar las colecciones a mostrar
    def filter_custom_collections(self, coll):
        RBDLAB = RBDLabNaming._RBDLAB_name
        RBDLab = RBDLabNaming._RBDLab_name

        # Filtro las collection de metal links:
        metal_link_coll = bpy.data.collections.get(RBDLabNaming.METAL_LINKS_COLL)
        if metal_link_coll:
            if coll in metal_link_coll.children_recursive:
                return False

        return RBDLAB not in coll and coll.name != RBDLab and "RigidBodyConstraints" != coll.name and "RigidBodyWorld" != coll.name and "constraint" not in coll.name.lower()

    def custom_collections_update(self, context):
        pass

    custom_collections: PointerProperty(
        name="Custom Collection", description="Select your collection", type=Collection,
        poll=filter_custom_collections, update=custom_collections_update)

    @staticmethod
    def main_modules_update(self, context):

        # print("[main_modules_update] update")

        rbdlab = get_common_vars(context, get_rbdlab=True)

        if "has_pretty_shading" in context.workspace:
            if not context.workspace["has_pretty_shading"]:
                condition = True
            else:
                condition = False
        else:
            condition = True

        if condition:
            if self.main_modules == 'MATERIALS':
                target_mode = 'MATERIAL'
            else:
                target_mode = 'SOLID'

            set_shading_color(context, shading=target_mode)

        # para mantenerlos ambos sincronizados:
        if self.main_modules_collapsed != self.main_modules:
            self.main_modules_collapsed = self.main_modules

        # Tebito comenta que era más lento la ui, por eso ya no lo hago.
        # al cambiar a cada modulo refresco la ui:
        # porque puede no haber sido refrescada al agregarse al listado por los
        # if self.main_modules == 'MODULEX': de cada section del target_collection_update
        # solo refrescar si entramos al physics:
        # if self.main_modules == 'PHYSICS':
        #     rbdlab.lists.target_coll_list.list_index = rbdlab.lists.target_coll_list.list_index

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        tcoll_item = tcoll_list.active_item

        # si no tiene computados los vecinos solo permitimos usar los motions:
        if self.main_modules == 'PARTICLES':
            if tcoll:
                if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
                    rbdlab.particles.debris.create.options = {'MOTION'}
                    rbdlab.particles.dust.create.options = {'MOTION'}
                    rbdlab.particles.smoke.create.options = {'MOTION'}

    module_items = [
        ('FRACTURE',        "Fracture",         "",     'MOD_PHYSICS',          0),
        ('BAKE',            "Bake",             "",     'FILE_BACKUP',         1),
        ('PHYSICS',         "Physics",          "",     'PHYSICS',              2),
        ('PARTICLES',       "Particles",        "",     'PARTICLES',            3),
        ('CONSTRAINTS',     "Constraints",      "",     'MOD_SIMPLIFY',         4),
        ('COLLISIONS',      "Collisions",       "",     'CON_SHRINKWRAP',       5),
        ('ACTIVATORS',      "Activators",       "",     'GROUP_VERTEX',         6),
        ('SMOKE',           "Smoke",            "",     'OUTLINER_OB_VOLUME',   7),
        ('METAL',           "MetalSoft",        "",     'MOD_SIMPLEDEFORM',     8),
        ('TOOLS',           "Tools",            "",     'TOOL_SETTINGS',        9),
        ('MOTION',          "Motion",           "",     'ARMATURE_DATA',        10),
        ('DSWITCH',         "Dynamic Switch",   "",     'MOD_DECIM',           11),
        # ('MATERIALS',     "Materials",        "",     'MATERIAL',             13),
    ]

    # para setear lo mismo en ambos enums:
    main_modules_name = "Main Modules"
    main_modules_description = "Main areas of work"
    main_modules_default = 'FRACTURE'

    main_modules: EnumProperty(
        items=module_items,
        name=main_modules_name,
        description=main_modules_description,
        default=main_modules_default,
        update=lambda self, context: self.main_modules_update(self, context)
    )

    collapse_module_selector: BoolProperty(
        name="Main Modules", description="Main Modules Sections", default=False)

    # para el main modules, collapsed con otro orden:
    module_items_collapsed = [
        ('FRACTURE',        "Fracture",         "",     'MOD_PHYSICS',          0),
        ('PHYSICS',         "Physics",          "",     'PHYSICS',              1),
        ('CONSTRAINTS',     "Constraints",      "",     'MOD_SIMPLIFY',         2),
        ('ACTIVATORS',      "Activators",       "",     'GROUP_VERTEX',         3),
        ('BAKE',            "Bake",             "",     'FILE_BACKUP',         4),
        ('PARTICLES',       "Particles",        "",     'PARTICLES',            5),
        ('COLLISIONS',      "Collisions",       "",     'CON_SHRINKWRAP',       6),
        ('SMOKE',           "Smoke",            "",     'OUTLINER_OB_VOLUME',   7),
        ('METAL',           "MetalSoft",        "",     'MOD_SIMPLEDEFORM',     8),
        ('TOOLS',           "Tools",            "",     'TOOL_SETTINGS',        9),
        ('MOTION',          "Motion",           "",     'ARMATURE_DATA',        10),
        ('DSWITCH',         "Dynamic Switch",   "",     'MOD_DECIM',           11),
        # ('MATERIALS',     "Materials",        "",     'MATERIAL',             13),
    ]

    @staticmethod
    def main_modules_collapsed_update(self, context):
        # para mantenerlos ambos sincronizados:
        if self.main_modules != self.main_modules_collapsed:
            self.main_modules = self.main_modules_collapsed

    main_modules_collapsed: EnumProperty(
        items=module_items_collapsed,
        name=main_modules_name,
        description=main_modules_description,
        default=main_modules_default,
        update=lambda self, context: self.main_modules_collapsed_update(self, context)
    )

    show_const_group_info: BoolProperty(
        default=True
    )

    def active_const_tab_update(self, context):
        
        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        tcoll_item = tcoll_list.active_item
        rbdlab_constraints = rbdlab.constraints

        if self.active_const_tab == 'CREATE':

            # en create cargamos los por default:
            rbdlab_constraints.breakable = rbdlab_constraints.get_default_properties("breakable")
            rbdlab_constraints.disable_collisions = rbdlab_constraints.get_default_properties("disable_collisions")
            rbdlab_constraints.glue_strength_mode = rbdlab_constraints.get_default_properties("glue_strength_mode")
            rbdlab_constraints.glue_strength_range[0] = 400
            rbdlab_constraints.glue_strength_range[1] = 1200
            rbdlab_constraints.glue_strength = rbdlab_constraints.get_default_properties("glue_strength")
            rbdlab_constraints.override_iterations = rbdlab_constraints.get_default_properties("override_iterations")
            rbdlab_constraints.iterations = rbdlab_constraints.get_default_properties("iterations")

            # Si estamos usando metal:
            metal_props = tcoll_item.metal_props
            if metal_props.metal_soft_mass:
                rbdlab_constraints.breakable = False
                rbdlab_constraints.constraint_type = 'GENERIC_SPRING'
                rbdlab_constraints.limit_neighbor_constraints = False
                rbdlab_constraints.constraints_between_chunks = True


        else:
            # en edit cargamos el del active group en la lista:

            coll_to_work = rbdlab_constraints.get_active_group
            if coll_to_work is not None:
                coll_to_work = coll_to_work.collection

                if coll_to_work:

                    ob = coll_to_work.objects[0]
                    rbdlab_constraints.breakable = ob.rigid_body_constraint.use_breaking
                    rbdlab_constraints.disable_collisions = ob.rigid_body_constraint.disable_collisions

                    if "rbdlab_use_glue_strength_random" not in ob:
                        rbdlab_constraints.glue_strength_mode = False

                        # rbdlab_constraints.glue_strength = ob.rigid_body_constraint.breaking_threshold

                        # lo leemos del glue_strength guardado en el active group:
                        active_group = rbdlab_constraints.get_active_group
                        rbdlab_constraints.glue_strength = active_group.glue_strength
                    
                    else:
                        rbdlab_constraints.glue_strength_mode = True
                        if "rbdlab_glue_strength_random_from" in ob:
                            rbdlab_constraints.glue_strength_range[0] = ob["rbdlab_glue_strength_random_from"]
                        if "rbdlab_glue_strength_random_to" in ob:
                            rbdlab_constraints.glue_strength_range[1] = ob["rbdlab_glue_strength_random_to"]

                    rbdlab_constraints.override_iterations = ob.rigid_body_constraint.use_override_solver_iterations
                    rbdlab_constraints.iterations = ob.rigid_body_constraint.solver_iterations

    active_const_tab: EnumProperty(
        items=(
            ('CREATE',      "Create",       "Create constraint groups"),
            ('EDIT',        "Edit",         "Edit constraint groups"),
            ('ANIMATION',   "Animation",    "Animation constraint groups"),

        ),
        default='CREATE',
        name="Active Constraint Tab",
        description="Create/Edit constraints",
        update=active_const_tab_update
    )

    show_mesh_visualization_settings: BoolProperty(
        default=False, name="Mesh Visualization Options", description="Show visualization options")
    show_fracture_details_extras: BoolProperty(
        default=False, name="Fracture Extra Details", description="Show Fracture Extra Details Settings")
    show_fracture_details_noise: BoolProperty(default=True)

    selected_particle_type: EnumProperty(name="Selected particle type",
                                         items=(
                                             ("debris", "Debris", ""),
                                             ("dust", "Dust", ""),
                                             ("smoke", "Smoke", "")
                                         ),
                                         default="debris")
    show_p_viewport_display: BoolProperty(
        default=True
    )
    show_motion_p_viewport_display: BoolProperty(
        default=False
    )
    show_motion_p_settings: BoolProperty(
        default=True
    )
    show_motion_rb_settings: BoolProperty(
        default=True
    )
    show_motion_p_emission: BoolProperty(
        default=True
    )
    show_motion_p_velocity: BoolProperty(
        default=True
    )
    show_motion_p_rotations: BoolProperty(
        default=True
    )
    show_motion_p_physics: BoolProperty(
        default=False
    )
    show_motion_p_render: BoolProperty(
        default=True
    )
    show_conversion: BoolProperty(
        default=True
    )
    motion_convert_ps_to_rbd_with_hide: BoolProperty(
        name="Hide Copies",
        description="Hide copies when particles are not visible",
        default=True
    )

    show_hide_speed_visualization: BoolProperty(
        default=False
    )
    show_hide_rbd_acuracy: BoolProperty(
        default=False
    )
    show_hide_rbd_animation_dynamic: BoolProperty(
        default=True
    )
    show_hide_rbd_animation_substeps_per_frame: BoolProperty(
        default=True
    )
    show_hide_rbd_animation_solver_iterations: BoolProperty(
        default=True
    )
    show_hide_rbd_animation_world_speed: BoolProperty(
        default=True
    )

    selected_smoke_entity: EnumProperty(name="Selected Smoke Entity",
                                        items=(
                                            ('FLOW', "Flow Emitter",
                                             "Smoke emiters flow"),
                                            ('DOMAIN', "Domain", "Smoke domain"),
                                        ),
                                        default='DOMAIN')

    scatter_mode: EnumProperty(
        name="Scatte Mode", description="Method to scatter points on selected mesh for fracture",
        items=(('STANDARD', "Standard", "Standard method to scatter points for fracture", 'STICKY_UVS_DISABLE', 0),
               ('TEXTURE', "Texture", "Use a procedural texture to scatter points for fracture", 'TEXTURE', 1),
               ('BOOLEAN', "Boolean", "Use planes to scatter points for fracture", 'MESH_GRID', 2),
               ('ORGANIC', "Organic", "Use geometry to scatter points for fracture", 'MESH_ICOSPHERE', 3),),
        default='STANDARD'
    )
    boolean_method_phase: EnumProperty(
        items=[
            ('NONE',                "None",                 "", 0),
            ('SETTINGS_GN',         "Settings GN",          "", 1),
            ('SETTINGS_BOOL_MOD',   "Settings Bool Mod",    "", 2),
        ], 
        default='NONE'
    )

    show_hide_edge_methods: BoolProperty(name="Edge Methods", default=False)
    edge_methods: EnumProperty(
        name="Edge Methods",
        description="Methods for fracture with edges (Need to have previously made a fracture with a few chunks, 4 or 5)",
        items=(('ALL', "All", "Scatter in all edges", 'MOD_EDGESPLIT', 0),
               ('INNERS', "Inners", "Scatter in inner edges", 'MOD_SOLIDIFY', 1),
               ('INNERFACES', "Inner Faces", "Scatter in inner faces", 'FACE_MAPS', 3),),
        default='ALL')
    edge_methods_type: EnumProperty(name="Edge Methods Type",
                                    description="Simple Method or Organic Method",
                                    items=(
                                        ('SIMPLE',   "Simple",   "Scatter in all edges",     'OUTLINER_OB_LATTICE', 0),
                                        ('ORGANIC',  "Organic",  "Scatter in inner edges",   'FCURVE', 1)
                                    ),
                                    default='SIMPLE'

                                    )

    show_edge_parent_compound: BoolProperty(
        default=True
    )

    visual_speed: BoolProperty(
        default=False
    )

    show_deactivation: BoolProperty(
        default=False
    )

    show_hide_constraint_by_string: BoolProperty(
        default=True
    )

    show_hide_constraint_settings: BoolProperty(
        default=True
    )
    # Spring (plasticidad)
    show_hide_constraint_spring_limit_angle: BoolProperty(
        default=False
    )
    show_hide_constraint_spring_limit_linear: BoolProperty(
        default=False
    )
    show_hide_constraint_spring_spring_angle: BoolProperty(
        default=True
    )
    show_hide_constraint_spring_spring_linear: BoolProperty(
        default=True
    )
    # End Spring
    show_hide_constraint_display: BoolProperty(
        default=False
    )

    # Constraints panel Animation:
    show_hide_const_switch_cons_by_group: BoolProperty(
        default=True
    )
    show_hide_const_glue_strength_anim: BoolProperty(
        default=True
    )
    show_hide_const_springs_anim: BoolProperty(
        default=True
    )
    show_hide_const_iterations_anim: BoolProperty(
        default=True
    )
    
    show_collision_through_offset: BoolProperty(
        default=True
    )
    show_fracture_restore: BoolProperty(
        default=True
    )
    show_clear_attr: BoolProperty(
        default=True
    )
    show_clear_ob_in_limbo_from_special_colls: BoolProperty(
        default=True
    )
    show_unhide_emitters: BoolProperty(
        default=True
    )
    show_unhide_select_neighbors: BoolProperty(
        default=True
    )
    show_unhide_recalculate_neighbors: BoolProperty(
        default=True
    )
    show_unhide_cleaning_obs: BoolProperty(
        default=True
    )
    show_world_position: BoolProperty(
        default=True
    )

    show_motions_selection_tools: BoolProperty(
        default=True
    )

    select_bad_chunks_by_selection: BoolProperty(
        name="In PreSelection",
        description="We tell Select Bad Chunks to find in the previous selection created by the user",
        default=True
    )
    show_activators_direction: BoolProperty(
        default=True
    )
    show_activators_rotation: BoolProperty(
        default=True
    )
    show_low_high_to_all_or_tc: BoolProperty(
        name="Visualization Target",
        description="For Visualization in current Target Collection or for all RBDLab collections",
        default=True
    )

    def activators_force_loc_mode_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if self.activators_force_loc_mode != 'EXPLODE':
            rbdlab.activators.force_explode_amount = 0
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    valid_objects = [obj for obj in bpy.data.collections[coll_name].objects]
                    if len(valid_objects) > 0:
                        for obj in valid_objects:
                            if RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE in obj:
                                obj.matrix_world.translation = obj[RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE]
                                del obj[RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE]
                            if RBDLabNaming.ACTIVATORS_EXPLODED_DEST in obj:
                                del obj[RBDLabNaming.ACTIVATORS_EXPLODED_DEST]

            if "Activators_explode_centroid" in context.scene.objects:
                objs = bpy.data.objects
                objs.remove(objs["Activators_explode_centroid"], do_unlink=True, do_id_user=True)

            if RBDLabNaming.ACTIVATORS_EXPLODE_DONE in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection[RBDLabNaming.ACTIVATORS_EXPLODE_DONE]

        else:

            centroid, total_objects, v_objects = get_objects_centroids(context)
            if "Activators_explode_centroid" not in context.scene.objects:
                # if it were switched off in the ui the visibility would be switched on.
                rbdlab.activators.explode_centroid_visibility = True
                bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD',
                                         location=(centroid),
                                         scale=(1, 1, 1))
                empty_centroid = context.active_object
                empty_centroid.empty_display_size = rbdlab.activators.explode_empty_size
                empty_centroid.name = "Activators_explode_centroid"

    activators_force_loc_mode: EnumProperty(
        name="Constant or Random direction",
        items=(
            ('CONST', "Constant", ""),
            ('RAND', "Random", ""),
            ('EXPLODE', "Explode", ""),  # este se puede ocultar si no da tiempo
        ),
        default='CONST',
        update=activators_force_loc_mode_update  # este se puede ocultar si no da tiempo
    )
    activators_force_rot_mode: EnumProperty(
        name="Constant or Random direction",
        items=(
            ('CONST', "Constant", ""),
            ('RAND', "Random", ""),
        ),
        default='CONST'
    )
    # activators_ignore_acetonized: BoolProperty(
    #     name="Ignore",
    #     description="Ignore previous chunks acetonizeds",
    #     default=False
    # )

    show_activators_source_type: BoolProperty(
        default=False
    )

    show_activators_common_settings: BoolProperty(
        default=True
    )
    show_activators_preview_bt: BoolProperty(
        default=False
    )
    show_activators_act_col_ramp: BoolProperty(
        default=True
    )

    use_single_activation: BoolProperty(
        name="Use single Activation",
        description="Activate and then do not re-compute that chunk/constraint",
        default=False
    )

    activator_margin: FloatProperty(
        name="Activator Margin",
        description="Activator margin",
        min=0,
        # default=0.1,
        default=1,
    )
    activator_kf_offset: IntProperty(
        name="Keyframes Offset",
        description="Keyframes Offset",
        min=0,
        default=0,
    )
    activator_extend: IntProperty(
        name="Chunks Extend",
        description="Chunks Extend",
        min=0,
        default=0,
    )
    activator_offset_extend: IntProperty(
        name="Offset Extend",
        description="Offsed Extend",
        min=0,
        default=0,
    )

    def dpaint_canvas_update(_self, self, context, call_from):
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        layer = ac_layers_list.active
        if layer:

            prop_value = getattr(self, "dpaint_" + call_from)

            includes = [o.ob for o in layer.stored_includes]            
            for ob in includes:

                canvas_mod = ob.modifiers.get(RBDLabNaming.ACT_CANVAS_MOD)
                if not canvas_mod:
                    continue

                active_surface = canvas_mod.canvas_settings.canvas_surfaces.active

                # solo se setea si es diferente:
                if prop_value != getattr(active_surface, call_from):
                    setattr(active_surface, call_from, prop_value)

    dpaint_brush_influence_scale: FloatProperty(
                                                name="Influence Scale", 
                                                description="Adjust influence brush objects have on this surface", 
                                                default=1, min=0, max=1,
                                                update=lambda self, context: self.dpaint_canvas_update(self, context, "brush_influence_scale")
    )
    dpaint_brush_radius_scale: FloatProperty(
                                                name="Radius Scale",
                                                description="Adjust radius of proximity brushes or particles for this surface",
                                                default=1, min=0, soft_max=1, max=10,
                                                update=lambda self, context: self.dpaint_canvas_update(self, context, "brush_radius_scale")
    )
    dpaint_use_dissolve: BoolProperty(
                                        name="Dissolve",
                                        description="Enable to make surface changes disappear over time",
                                        default=False,
                                        update=lambda self, context: self.dpaint_canvas_update(self, context, "use_dissolve")
    )
    dpaint_dissolve_speed: IntProperty(
                                        name="Dissolve Time",
                                        description="Approximately in how many frames should dissolve happen",
                                        default=250, min=1, max=10000,
                                        update=lambda self, context: self.dpaint_canvas_update(self, context, "dissolve_speed")
    )
    dpaint_use_dissolve_log: BoolProperty(
                                            name="Slow",
                                            description="Use logarithmic dissolve (makes high values to fade faster than low values)",
                                            default=True,
                                            update=lambda self, context: self.dpaint_canvas_update(self, context, "use_dissolve_log")
    )


    # setters:

    def select_particle(self, type: str):
        if type:
            self.selected_particle_type = type

    # collisions:
    show_p_collisions: BoolProperty(
        default=True
    )

    show_p_single_objecy_collisions: BoolProperty(
        default=True
    )

    # preserve_bake_action: BoolProperty(default=False)

    collision_to: EnumProperty(name="Collision to",
                               items=(
                                   ("Low", "Low", ""),
                                   ("High", "High", ""),
                               ),
                               default="Low")

    def set_collision_to(self, type: str):
        if type:
            self.collision_to = type

    show_target_collection_info: BoolProperty(
        name="Show/Hide Information",
        default=False,
        description="Show Target Collection Information",
    )

    use_auto_uv_cube_projection: BoolProperty(
        name="UV Cube Projection",
        default=True,
        description="Use Auto UV Cube Projection for inner materials",
    )
    show_hide_collision_to_sel_coll: BoolProperty(default=True)
    show_hide_collision_to_compound_sel_coll: BoolProperty(default=True)
    show_hide_collision_to_static_objs: BoolProperty(default=True)

    def hide_emmiters_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        if rbdlab.filtered_target_collection:
            emitters = [obj for obj in rbdlab.filtered_target_collection.objects
                        if RBDLabNaming.INNER_EMISOR in obj]
            for emitter in emitters:
                emitter.hide_set(self.hide_emmiters)
                emitter.hide_viewport = self.hide_emmiters

    hide_emmiters: BoolProperty(
        default=False,
        update=hide_emmiters_update
    )

    show_hide_bake_action_ui: BoolProperty(default=True)

    show_motion_threshold: BoolProperty(
        name="Options",
        description="Options for Select Chunks without movement",
        default=False
    )
    show_hide_boolean_method: BoolProperty(default=False)
    show_hide_lapshmooth: BoolProperty(default=False)

    motion_switch_subsections: EnumProperty(
        name="Motion",
        items=(
            ('QUICK_RIGIDBODIES',           "Quick Rigidbodies",        "", 0),
            ('PARTICLES_TO_RIGIDBODIES',    "Particles to Rigidbodies", "", 1),
        ),
        default='QUICK_RIGIDBODIES'
    )

    tools_switch_subsections: EnumProperty(
        name="Tools",
        items=(
            ('MISC',                "Misc",             "", 0),
            ('FRACTURE_RESTORE',    "Restore",          "", 1),
            ('CLEAR_ATTRIBUTES',    "Clear Attributes", "", 2),
            ('BAKE_UVS_WORLD',      "Bake UVs",         "", 3),
        ),
        default='MISC'
    )

    fracture_switch_subsections: EnumProperty(
        name="Fracture",
        items=(
            ('PREPARE',             "Prepare",  "", 0),
            ('SCATTER',             "Scatter",  "", 1),
            ('FRACTURE',            "Fracture", "", 2),
            ('FRACTURE_DETAILS',    "Details",  "", 3),
        ),
        default='SCATTER'
    )
    show_hide_fracture_output: BoolProperty(name="Fracture Output", default=True)
    show_hide_paint_tools_subdivisions: BoolProperty(default=False)
    show_hide_paint_tools_paint: BoolProperty(default=False)
    show_hide_paint_tools_annotate: BoolProperty(default=False)
    show_hide_paint_tools_proxy_section: BoolProperty(default=False)


    fracture_switch_scatter: EnumProperty(
        name="Scatter",
        items=(
            ('SCATTER',         "Scatter",          "", 0),
            ('EDGE_METHODS',    "Edge Methods",     "", 1),
        ),
        default='SCATTER'
    )

    physics_switch_subsections: EnumProperty(
        name="Physics",
        items=(
            ('GROUND',          "Ground",       "", 0),
            ('RBD',             "RBD",          "", 1),
            ('KINEMATICS',      "Kinematics",   "", 2),
            ('PARENTS',         "Parents",      "", 3),
        ),
        default='GROUND'
    )
    physics_rbd_subsections: EnumProperty(
        name="RBD Subsections",
        items=(
            ('SETTINGS',    "Settings",     "", 0),
            ('ANIMATION',   "Animation",    "", 1),
        ),
        default='SETTINGS'
    )
    parents_switch_subsections: EnumProperty(
        name="Parents",
        items=(
            ('HANDLER',         "Handler",          "", 0),
            ('COMPOUND',        "Compound",         "", 1),
        ),
        default='HANDLER'
    )
    parents_ds_setup_original: BoolProperty(default=True)
    dswitch_dynamic_parent: BoolProperty(default=True)

    # module switching:
    dswitch_subsections: EnumProperty(
        name="Dynamic Switch",
        description="Dynamic Switch Sections",
        items=(
            ('DYNAMIC_PARENT',      "Dynamic Parent",   "", 0),
            ('VISUAL_SWITCHING',    "Visual Switching", "", 1),
        ),
        default='DYNAMIC_PARENT'
    )
    visual_switch_type: EnumProperty(
        name="Visual Switch",
        items=(
            ('FRAME_SWITCH',    "Frame Switch",     "", 0),
            ('DYNAMIC_SWITCH',  "Dynamic Switch",   "", 1),
        ),
        default='FRAME_SWITCH'
    )

    show_hide_physics_ground_visualization: BoolProperty(default=True)
    show_hide_physics_ground_dimensions: BoolProperty(default=True)
    show_hide_physics_ground_rbd_collisions: BoolProperty(default=True)
    show_hide_physics_ground_particle_collision: BoolProperty(default=True)
    show_hide_physics_rbd_settings: BoolProperty(default=True)
    show_hide_rbd_passives_by_sel: BoolProperty(default=False)
    show_hide_rbd_merge_by_sel: BoolProperty(default=False)
    show_hide_rbd_collections: BoolProperty(default=False)
    show_hide_rbd_ground_collections: BoolProperty(default=False)
    show_hide_physics_kinematics_settings: BoolProperty(default=True)
    show_hide_physics_kinematics_by_selection_settings: BoolProperty(default=True)
    show_hide_physics_handler: BoolProperty(default=True)

    # nueva ui de domain como la de vdblab:
    domain_sections: EnumProperty(
        items=(
            ('RESOLUTION',      "Resolution",       "",     'MOD_MULTIRES',         0),
            ('COLLISION',       "Collision",        "",     'MOD_EDGESPLIT',        1),
            ('GAS',             "Gas",              "",     'FORCE_FLUIDFLOW',      2),
            ('FIRE',            "Fire",             "",     'SEQ_HISTOGRAM',        3),
            ('COLLECTION',      "Collection",       "",     'OUTLINER_COLLECTION',  4),
            ('CACHE',           "Cache",            "",     'FILE_CACHE',           5),
            ('WEIGHTS',         "Weights",          "",     'ORIENTATION_GIMBAL',   6),
            ('DISPLAY',         "Display",          "",     'RESTRICT_VIEW_OFF',    7),
        ),
        default='RESOLUTION',
    )
    domain_subcategory_collapsable: BoolProperty(default=True)
    show_hide_domain_resolution: BoolProperty(default=True)
    show_hide_domain_adaptative: BoolProperty(default=True)
    show_hide_domain_noise: BoolProperty(default=True)
    show_hide_domain_border_collisions: BoolProperty(default=True)
    show_hide_domain_gas: BoolProperty(default=True)
    show_hide_domain_fire: BoolProperty(default=True)
    show_hide_domain_collections: BoolProperty(default=True)
    show_hide_domain_guides: BoolProperty(default=True)
    show_hide_domain_cache: BoolProperty(default=True)
    show_hide_domain_weights: BoolProperty(default=True)
    show_hide_domain_display: BoolProperty(default=True)
    show_hide_domain_display_slice: BoolProperty(default=True)
    show_hide_domain_display_vector_display: BoolProperty(default=True)
    show_hide_domain_display_grid_display: BoolProperty(default=True)

    # nueva ui acrivators como la de vdblab:
    activators_mode: EnumProperty(
        items=(
            ('CREATION',            "Creation",         "",     '', 0),
            ('LAYERS',              "Layers",           "",     '', 1),
        ),
        default='CREATION',
    )
    

    # nueva ui particles update:
    particles_update_sections: EnumProperty(
        items=(
            ('EMISSION',        "Emission",         "", 0),
            ('PHYSICS',         "Physics",          "", 1),
            ('FIELD_WEIGHTS',   "Field Weights",    "", 2),
            ('DEBRIS_SETTINGS', "Basic Debris",     "", 3),
        ),
        default='EMISSION',
    )
    show_hide_viewport_display: BoolProperty(default=True)
    show_hide_emission: BoolProperty(default=True)
    show_hide_velociry_and_rotation: BoolProperty(default=True)
    show_hide_particles_physics: BoolProperty(default=True)
    show_hide_particles_field_weights: BoolProperty(default=True)
    show_hide_particles_basic_debris: BoolProperty(default=True)
    show_hide_filter_particles: BoolProperty(default=False)
    
    show_hide_bake_particles: BoolProperty(default=False)
    
    @staticmethod
    def particles_cache_update(self, context, call_from):
        
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        tcoll = tcoll_list.active

        valid_types = ("_debris", "_dust", "_smoke")
        ob_to_work = [ob for ob in tcoll.objects if ob.type == 'MESH' or len(ob.particle_systems) > 0]
        new_valule = getattr(self, "bake_particles_point_cache_" + call_from)

        bpy.ops.object.select_all(action='DESELECT')

        for ob in ob_to_work:
            set_active_object(context, ob)

            for mod in ob.modifiers:

                if mod.type != 'PARTICLE_SYSTEM':
                    continue
                
                can_continue = next((True for vt in valid_types if vt in mod.name), False)
                if not can_continue:
                    continue
                
                ob.modifiers.active = mod
                psys = ob.modifiers[mod.name].particle_system

                for cache in psys.point_cache.point_caches:
                    setattr(cache, call_from, new_valule)

                    
    bake_particles_point_cache_use_disk_cache: BoolProperty(
        default=False,
        update=lambda self, context: self.particles_cache_update(self, context, "use_disk_cache")
    )
    bake_particles_point_cache_compression: EnumProperty(
        items=[
            ('NO',      "None",     "", 0),
            ('LIGHT',   "Light",    "", 1),
            ('HEAVY',   "Heavy",    "", 2),
        ],
        default='NO',
        update=lambda self, context: self.particles_cache_update(self, context, "compression")
    )

    show_hide_custom_debris: BoolProperty(default=False)

    # nueva ui bake panel:
    bake_sub_sections: EnumProperty(
        # items=[
        #     ('RIGIDBODIES',     "RigidBodies",  "", 'ONIONSKIN_ON',             0),
        #     ('BK_TO_KEYFRAMES', "To Keyframes", "", 'KEYFRAME_HLT',             1),
        #     ('PARTICCLES',      "Particles",    "", 'MOD_PARTICLE_INSTANCE',    2),
        # ],
        items=[
            ('RIGIDBODIES',     "RigidBodies",  "", 0),
            ('BK_TO_KEYFRAMES', "To Keyframes", "", 1),
            ('PARTICCLES',      "Particles",    "", 2),
        ],
        default='RIGIDBODIES'
    )
    # old bake compactables:
    # show_hide_rbd_bake: BoolProperty(default=True)
    # show_hide_rbd_bake_to_keyframes: BoolProperty(default=True)
    # show_hide_rbd_bake_particles: BoolProperty(default=True)

    # nueva ui smoke:
    show_hide_filter_smoke: BoolProperty(default=False)

    # nuevo panel collisions:
    collision_module_subsections: EnumProperty(
        name="Collisions Subsections",
        items=[
            ('COLLISION', "Collision", "", 0),
            ('COLLISION_STATIC_OBJECTS', "Collision Static Objects", "", 1),
            ('SINGLE_OBJECT_COLLISION', "Single Object Collision", "", 2),
        ],
        default='COLLISION'
    )

    interpolation_type: EnumProperty(
        items=[
            ('CONSTANT',    "Constant", "", 0),
            ('LINEAR',      "Linear",   "", 1),
            ('BEZIER',      "Bezier",   "", 2),
        ],
        default='LINEAR'
    )

    #----------------------------------------------------------------------
    # Target Collection > DropDown > Merge Collections --------------------
    def coll_to_filter(self, coll):

        scn = bpy.context.scene
        rbdlab = scn.rbdlab

        if not rbdlab.root_collection:
            return -1

        blacklist_collections = [
                                    rbdlab.root_collection.name, 
                                    RBDLabNaming.RBD_CONSTRAINTS, 
                                    RBDLabNaming.RBD_WORLD, 
                                    RBDLabNaming.ORIGINALS, 
                                    RBDLabNaming.CONSTRAINTS, 
                                    RBDLabNaming.CONST_COLL,
                                    RBDLabNaming.METAL_MESHES, 
                                    RBDLabNaming.METAL_LINKS_COLL
                                ]

        if rbdlab.root_collection:
            if coll.name not in rbdlab.root_collection.children:
                blacklist_collections.append(coll.name)

        if coll.name not in blacklist_collections:
            
            if coll.name in blacklist_collections or "_GlueConstraints" in coll.name or "Debris" in coll.name or \
                coll.name.endswith(RBDLabNaming.SUFIX_HIGH) or coll.name.startswith(RBDLabNaming.PREFIX_CONST) or RBDLabNaming.METAL_LINKS_COLL in coll:

                return False
            else:
                return True
        else:
            return False
    
    coll_to: PointerProperty(type=Collection, poll=coll_to_filter)
    # end merge collections -----------------------------------------------
    #----------------------------------------------------------------------
 
    # metal main module:
    metal_subsections: EnumProperty(
        name="Metal Subsections",
        items=[
            ('REMESH',          "Remesh",           "", 0),
            ('METAL_CREATION',  "Metal Creation",   "", 1),
        ],
        # default='REMESH'
        default='METAL_CREATION'
    )
    
    show_hide_metal_clean_collection: BoolProperty(default=False)


    # Para filtrar las colecciones a mostrar en Constraints > Animation > Switcher Between Groups
    def filter_const_switcher_collections(self, coll):

        scn = bpy.context.scene
        rbdlab = scn.rbdlab

        all_active_groups = rbdlab.constraints.get_all_constraints_groups
        if not all_active_groups:
            return

        all_active_groups = [ag.collection.name for ag in all_active_groups]
        return coll.name in all_active_groups

    const_switcher_from_collections: PointerProperty(
        name="From Collection",
        description="Choose your collection",
        type=Collection,
        poll=filter_const_switcher_collections
    )

    const_switcher_to_collections: PointerProperty(
        name="To Collection",
        description="Choose your collection",
        type=Collection,
        poll=filter_const_switcher_collections
    )

    # BooleanFracture GN --------------------------------------------------------------------

    show_hide_bf_gn_distribution: BoolProperty(default=True)
    show_hide_bf_gn_planes_settings: BoolProperty(default=True)
    show_hide_bf_gn_planes_transformation: BoolProperty(default=True)
    show_hide_bf_gn_noise: BoolProperty(default=True)
    bf_gn_compute_neighbors: BoolProperty(default=True)

    bf_gn_use_auto_uv_cube_projection: BoolProperty(
        name="UV Cube Projection",
        default=True,
        description="Use Auto UV Cube Projection for inner materials",
    )

    # End BooleanFracture GN ----------------------------------------------------------------

    # Optional Calcute Neighbors:
    compute_neighbors: BoolProperty(default=True)









    def find_closest_objects(self, obj_dict):
            closest_objects = []
            min_distance = float('inf')
            closest_objects = []
            
            for key, objects_list in obj_dict.items():

                for obj1 in objects_list:
                    
                    for other_key, other_objects_list in obj_dict.items():
                        
                        if key != other_key:
                            
                            for obj2 in other_objects_list:
                                
                                distance = (obj1.location - obj2.location).length
                                if distance < min_distance:
                                    #min_distance = distance
                                    min_distance = self.select_adjacents
                                    closest_objects.append([obj1, obj2])
            
            return closest_objects, min_distance
    

    def select_adjacents_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'ERROR'}, "Invalid target collection!")
            return {'CANCELLED'}
        
        # vertex_distance_threshold: float = 0.001
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'ERROR'}, "Chunks could not be obtained from target collection!")
            return {'CANCELLED'}

        ###################################################################################
        bpy.ops.object.select_all(action='DESELECT')
        ob_by_from: dict[str, List[Object]] = defaultdict(list)

        for ob in chunks:
            from_name = ob.get("rbdlab_from")
            if from_name:
                ob_by_from[from_name].append(ob)

        closest_objects, min_distance = self.find_closest_objects(ob_by_from)
        if closest_objects:
            for l in closest_objects:
                print("Objetos más cercanos entre sí:")
                for ob in l:
                    print(ob.name)
                    ob.select_set(True)
            print("Distancia mínima:", min_distance)
        else:
            print("No se encontraron objetos en el diccionario para comparar.")


    select_adjacents: FloatProperty(default=1, update=select_adjacents_update)


    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default
