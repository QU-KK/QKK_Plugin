import bpy
from bpy.types import PropertyGroup, Object, Collection
from bpy.props import EnumProperty, BoolProperty, FloatProperty, \
    StringProperty, IntProperty, FloatVectorProperty, PointerProperty

from ..Global.basics import deselect_all_objects, select_object, set_active_object

from .constraints.constraints import RBDLab_PG_Constraints
from ..Global.functions import copy_modifier_by_name_from_active_to_selected
from .when_updating_property import subdiv_update, part_count, part_second_count, target_collection_update, \
    scatter_detail_emit_from_update, scatter_secondary_emit_from_update, mass_delimiter_by_mass_update, \
    use_auto_smooth_update, auto_smooth_update, show_emitter_viewport_update, show_emitter_render_update, \
    explode_slider_update, colorize_update, domain_size_update, domain_dissolve_time, domain_resolution, clouds_size_update, \
    inner_subdivisions_update, displace_strength_update, low_or_high_visibility_viewport_update, low_or_high_visibility_render_update, \
    scatter_detail_size_particles_update, scatter_secondary_size_particles_update, scatter_secondary_use_modifier_stack_update, \
    scatter_secondary_distribution_update, scatter_secondary_use_emit_random_update, scatter_secondary_use_even_distribution_update, \
    scatter_secondary_invert_grid_update, scatter_secondary_hexagonal_grid_update, scatter_secondary_userjit_update, \
    scatter_secondary_jitter_factor_update, scatter_secondary_grid_resolution_update, scatter_secondary_grid_random_update, \
    external_roughness_update, rbdlab_cf_fast_exact_update, \
    scatter_secondary_seed_update, particles_mute_size_delimiter_update, smoke_mute_size_delimiter_update, \
    ground_x_update, ground_y_update, show_hide_ground_update, show_wire_ground_update, selectable_ground_update, remesh_or_subdivision_update, depth_displace_texture_update, remesh_mode_update, \
    octree_depth_update, remesh_scale_update, use_smooth_shade_update, voxel_size_update, remesh_voxel_adaptivity_update, isolate_or_not_update, \
    rbdlab_cf_wood_directions_update, noise_basis_update, noise_type_update

from ..addon.naming import RBDLabNaming

from .ui import RBDLab_PG_UI
from .scatter import RBDLab_PG_scatter

from .physics.physics import RBDLAB_PG_Physics

from .activators import RBDLab_PG_activators
from .smoke import RBDLab_PG_Smoke
from .particles import RBDLab_PG_particles
from .bake import RBDLab_PG_Bake
from .collision import RBDLab_PG_collision #, RBDLab_PG_collision_so_list
from .motion import RBDLab_PG_motion
from .materials import RBDLab_PG_thumbnails, RBDLab_PG_Materials

# from .lists.target_collection_list import RBDLab_PG_TargetCollectionList
# from .lists.merge_collections_list import MergeCollectionsList
from .lists.all_lists_pointers import AllLists

from .physics.dswitch.visual_switching_props import RBDLab_PG_visual_switching_props


class rbdlab(PropertyGroup):
    """ context.scene.rbdlab.x """

    """ root collection para el multiscene """
    root_collection: PointerProperty(type=Collection)

    """ originals collection para el multiscene """
    originals_collection: PointerProperty(type=Collection)

    """ Listado de Target collections """
    # target_coll_list: PointerProperty(type=RBDLab_PG_TargetCollectionList)
    # merge_collections_list: PointerProperty(type=MergeCollectionsList)
    lists: PointerProperty(type=AllLists)


    """ Sub-PropertyGroup/s. """
    ui: PointerProperty(type=RBDLab_PG_UI)
    scatter: PointerProperty(type=RBDLab_PG_scatter)
    physics: PointerProperty(type=RBDLAB_PG_Physics)
    activators: PointerProperty(type=RBDLab_PG_activators)
    smoke: PointerProperty(type=RBDLab_PG_Smoke)
    particles: PointerProperty(type=RBDLab_PG_particles)
    bake: PointerProperty(type=RBDLab_PG_Bake)
    collision: PointerProperty(type=RBDLab_PG_collision)
    motion: PointerProperty(type=RBDLab_PG_motion)

    """ constraints """
    constraints: PointerProperty(type=RBDLab_PG_Constraints)

    """ materials: """
    thumbnails: PointerProperty(type=RBDLab_PG_thumbnails)
    materials: PointerProperty(type=RBDLab_PG_Materials)

    """ Collision Static Objects list """
    # collision_so_list: PointerProperty(type=RBDLab_PG_collision_so_list)

    visual_switching: PointerProperty(type=RBDLab_PG_visual_switching_props)

    """ Properties. """
    folder_addon_name: StringProperty(
        default="RBDLab"
    )

    las_active_tool: StringProperty(default="builtin.select_box")
    in_annotation_mode: BoolProperty(default=False)
    current_proxy_ob: PointerProperty(type=Object)

    # Para filtrar el target collecttion
    def filter_target_collection_names(self, object):
        context = bpy.context
        scn = context.scene
        rbdlab = scn.rbdlab

        if not rbdlab.root_collection:
            return -1

        blacklist_collections = [rbdlab.root_collection.name, "RigidBodyConstraints", "RigidBodyWorld", RBDLabNaming.ORIGINALS]

        if rbdlab.root_collection:
            if object.name not in rbdlab.root_collection.children:
                blacklist_collections.append(object.name)
        # si no existe la coleccion RBDLab si se permie seleccionar colecciones fuera de RBDLab
        # else:
        #     return False

        if object.name not in blacklist_collections:
            if object.name == RBDLabNaming.CONST_COLL or "_GlueConstraints" in object.name or "Debris" in object.name or RBDLabNaming.SUFIX_HIGH in object.name or object.name.startswith(RBDLabNaming.PREFIX_CONST):
                return False
            else:
                return True
        else:
            return False

    # Para filtrar el target collecttion
    def filter_debris_target_collection_names(self, object):
        context = bpy.context
        scn = context.scene
        rbdlab = scn.rbdlab
        blacklist_collections = [rbdlab.root_collection.name, "RigidBodyConstraints", "RigidBodyWorld"]

        if rbdlab.root_collection:
            if object.name not in rbdlab.root_collection.children:
                blacklist_collections.append(object.name)

        if object.name not in blacklist_collections:
            if "debris" in object.name.lower():
                return True
            else:
                return False
        else:
            return False

    # para la seleccion por movimiento:
    motion_threshold: FloatProperty(
        name="Movement Threshold",
        description="Select Chunks without movement Threshold",
        default=0.005,
        precision=3
    )

    # Para filtrar el target collecttion
    filtered_target_collection: PointerProperty(
        name="TargetCollection",
        type=Collection,
        poll=filter_target_collection_names,
        update=target_collection_update,
        description="Collection we are working with"
    )

    debris_target_collection: PointerProperty(
        name="Debris Target Collection",
        type=Collection,
        poll=filter_debris_target_collection_names,
        # update=target_collection_update,
        description="Debris Collection we are working with"
    )

    custom_name_debris_collection: StringProperty(
        default=""
    )

    """ Fracture properties / compartidas con el scatter boolean de planos ya que tiene el remesh tambien """
    working_in_inner_details: BoolProperty(
        default=False
    )
    remesh_or_subdivision: EnumProperty(
        items=(
            ("Remesh", "Remesh", "Remesh", 'MOD_REMESH', 0),
            ("Subdivision", "Subdivision", "Subdivision", 'MOD_SUBSURF', 1),
        ),
        description="",
        default="Subdivision",
        update=remesh_or_subdivision_update
    )
    depth_displace_texture: IntProperty(
        min=0,
        max=10,
        default=5,
        update=depth_displace_texture_update
    )
    remesh_mode: EnumProperty(
        items=(
            ('SMOOTH', "Smooth", "Smooth"),
            ('SHARP', "Sharp", "Sharp"),
            ('VOXEL', "Voxel", "Voxel"),
        ),
        description="",
        default='VOXEL',
        update=remesh_mode_update
    )
    octree_depth: IntProperty(
        default=4,
        min=1,
        max=12,
        update=octree_depth_update
    )
    remesh_scale: FloatProperty(
        default=0.9,
        min=0.0,
        max=0.99,
        update=remesh_scale_update
    )
    use_smooth_shade: BoolProperty(
        default=False,
        update=use_smooth_shade_update
    )
    voxel_size: FloatProperty(
        default=0.1,
        min=0.0001,
        max=2,
        subtype='DISTANCE',
        update=voxel_size_update
    )
    remesh_voxel_adaptivity: FloatProperty(
        default=0,
        min=0,
        max=1,
        subtype='DISTANCE',
        update=remesh_voxel_adaptivity_update
    )
    range_min: IntProperty(
        min=0,
        max=7,
        default=3
    )
    range_max: IntProperty(
        min=0,
        max=7,
        default=5
    )
    isolate_or_not: BoolProperty(
        description="",
        default=False,
        update=isolate_or_not_update
    )

    """ Basic debris properties """

    def motion_emitter_target_object_update(self, context=bpy.context):
        pass

    def motion_object_for_emit_update(self, context=bpy.context):
        if self.motion_emitter_target_object and self.motion_object_for_emit:
            ps_name = self.motion_emitter_target_object.particle_systems[0].settings.name
            bpy.data.particles[ps_name].render_type = 'OBJECT'
            bpy.data.particles[ps_name].instance_object = self.motion_object_for_emit
        else:
            if self.motion_emitter_target_object:
                ps_name = self.motion_emitter_target_object.particle_systems[0].settings.name
                bpy.data.particles[ps_name].render_type = 'HALO'
                bpy.data.particles[ps_name].instance_object = None

    motion_emitter_target_object: PointerProperty(
        name="Emitter Target",
        type=bpy.types.Object,
        description="Emitter Object",
        update=motion_emitter_target_object_update
    )
    motion_object_for_emit: PointerProperty(
        name="Object to emit",
        type=bpy.types.Object,
        description="Object to emit",
        update=motion_object_for_emit_update
    )
    motion_ps_to_rbd_kinematics_end: IntProperty(
        name="Kinematics End",
        default=35,
        min=1,
        description="The point at which the particles will change from being kinematic objects to rigidbodies objects, for each of the objects."
    )

    def motion_p_to_rbd_show_hide_toggle_update(self, context):
        tcoll = self.filtered_target_collection
        obj_active = context.active_object
        if obj_active:

            # coll_name = obj_active.name + "_particles_copied"
            coll_name = None

            if "rbdlab_motion_collection_id" in obj_active:
                for coll in bpy.data.collections:
                    if "rbdlab_motion_collection_id" in coll:
                        if obj_active["rbdlab_motion_collection_id"] == coll["rbdlab_motion_collection_id"]:
                            coll_name = coll.name
            else:
                print("no rbdlab_motion_collection_id in " + obj_active.name)

            if coll_name in bpy.data.collections:

                for obj in tcoll.objects:
                    if obj.type == 'MESH':

                        if self.motion_p_to_rbd_show_hide_toggle:

                            # ocultacion
                            # viewport
                            if "rbdlab_hide_first_frame_True" in obj:
                                obj.hide_viewport = True
                                obj.keyframe_insert(data_path="hide_viewport", frame=obj
                                                    ["rbdlab_hide_first_frame_True"])
                            if "rbdlab_hide_second_frame_False" in obj:
                                obj.hide_viewport = False
                                obj.keyframe_insert(data_path="hide_viewport",
                                                    frame=obj["rbdlab_hide_second_frame_False"])
                            # render:
                            if "rbdlab_hide_first_frame_True" in obj:
                                obj.hide_render = True
                                obj.keyframe_insert(data_path="hide_render", frame=obj["rbdlab_hide_first_frame_True"])
                            if "rbdlab_hide_second_frame_False" in obj:
                                obj.hide_render = False
                                obj.keyframe_insert(data_path="hide_render", frame=obj
                                                    ["rbdlab_hide_second_frame_False"])
                        else:

                            # remove keyframes:
                            fc = obj.animation_data.action.fcurves
                            h_viewport = fc.find("hide_viewport")
                            h_render = fc.find("hide_render")
                            if h_viewport:
                                fc.remove(h_viewport)
                            if h_render:
                                fc.remove(h_render)

                            # seteando visibilidad
                            obj.hide_viewport = False
                            obj.hide_render = False

                context.scene.frame_current = context.scene.frame_start

    motion_p_to_rbd_show_hide_toggle: BoolProperty(
        name="Show or hide copies", default=False,
        description="Hide/Unhide copies when particles are not visible (if you need bake to keyframes is necesary unhide this option first)",
        update=motion_p_to_rbd_show_hide_toggle_update)

    remesh_for_coll_mesh: FloatProperty(
        default=0.02,
        description="Remesh value"
    )
    decimate_for_coll_mesh: FloatProperty(
        default=0.45,
        description="Decimate value"
    )

    eth_icons_t: BoolProperty(
        default=False
    )
    eth_icons_r: BoolProperty(
        default=False
    )
    eth_icons_s: BoolProperty(
        default=False
    )

    eth_trans_orientation: StringProperty(
        default='GLOBAL'
    )

    # new constraints properties
    max_const_dist: FloatProperty(name="Search Area", min=0, soft_max=500, default=5.0, description="The search area to connect the chunks among them")
    maximun_constraints: IntProperty(name="Maximum connections", soft_min=0, soft_max=100, default=3, description="Maximum connections per chunks")

    particle_count: IntProperty(
        default=50,
        min=1,
        update=part_count
    )
    particle_secondary_count: IntProperty(
        default=30,
        min=1,
        update=part_second_count
    )
    subdivision_level: IntProperty(
        default=0,
        min=0,
        max=6,
        update=subdiv_update
    )
    subdivision_simple: BoolProperty(
        default=False,
        update=subdiv_update
    )
    #############################################################
    # Isolator (old chipping) ###################################

    def selector_range(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                deselect_all_objects(context)

                valid_objects = [
                    obj for obj in rbdlab.filtered_target_collection.objects
                    if obj.type == 'MESH' and obj.visible_get()]

                for obj in valid_objects:
                    sx_sy_xz = obj.dimensions.x + obj.dimensions.y + obj.dimensions.z
                    if (self.size_delimiter_small/10) < sx_sy_xz < (self.size_delimiter_big/10):
                        obj.select_set(True)
                        context.view_layer.objects.active = obj

        rbdlab.chunks_selected = len(context.selected_objects)

    size_delimiter_big: FloatProperty(
        name="size_delimiter_big",
        description="Minimun size to be selected",
        default=0,
        min=0,
        precision=1,
        update=selector_range,
        # update=size_delimiter_big_update
    )
    size_delimiter_small: FloatProperty(
        name="size_delimiter_small",
        description="Minimun size to be selected",
        default=0,
        min=0,
        precision=1,
        update=selector_range,
        # update=size_delimiter_small_update
    )
    mass_delimiter: FloatProperty(
        default=1,
        min=0,
        precision=6,
        update=mass_delimiter_by_mass_update
    )
    chunks_selected: IntProperty(
        default=0
    )
    custom_name_isolations: StringProperty(
        default=""
    )
    # End Isolator (old chipping) ###############################
    #############################################################
    smoke_density: FloatProperty(
        default=1.0,
        min=0.0,
        max=1.0,
        precision=4,
        options={'ANIMATABLE'}
    )
    scatter_secondary_seed: IntProperty(
        default=0,
        update=scatter_secondary_seed_update
    )
    iter_seed: IntProperty(
        default=0
    )
    use_auto_smooth: BoolProperty(
        name="Auto Smooth",
        description="To visualise smooth objects, usually curved or more organic objects",
        default=False,
        update=use_auto_smooth_update
    )
    auto_smooth: FloatProperty(
        name="Auto Smooth Angle",
        description="the angle for smoothing",
        default=0.523599,
        min=0.0,
        max=3.141593,
        subtype='ANGLE',
        update=auto_smooth_update
    )
    remove_loose_verts: BoolProperty(
        name="Remove Loose vertices",
        description="Remove Loose vertices in high chunks",
        default=True,
    )
    scatter_working: BoolProperty(
        default=False
    )
    current_using_cell_fracture: BoolProperty(
        default=False
    )
    scatter_detail_emit_from: EnumProperty(
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        name="scatter_detail_type",
        description="Type of scatter",
        update=scatter_detail_emit_from_update
    )

    #################################################################
    # secondary para tipo lego:
    #################################################################
    scatter_secondary_emit_from: EnumProperty(
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        name="scatter_secondary_type",
        description="Type of scatter",
        update=scatter_secondary_emit_from_update
    )
    scatter_secondary_use_modifier_stack: BoolProperty(
        default=False,
        update=scatter_secondary_use_modifier_stack_update
    )
    scatter_secondary_distribution: EnumProperty(
        items=(
            ('JIT', "Jittered", "", 0),
            ('RAND', "Random", "", 1),
            ('GRID', "Grid", "", 2)
        ),
        name="scatter_secondary_distribution",
        description="Hot to distribute particles on selected element",
        update=scatter_secondary_distribution_update,
        default='RAND'
    )
    scatter_secondary_use_emit_random: BoolProperty(
        default=True,
        update=scatter_secondary_use_emit_random_update
    )
    scatter_secondary_use_even_distribution: BoolProperty(
        default=True,
        update=scatter_secondary_use_even_distribution_update
    )
    scatter_secondary_invert_grid: BoolProperty(
        default=False,
        update=scatter_secondary_invert_grid_update
    )
    scatter_secondary_hexagonal_grid: BoolProperty(
        default=False,
        update=scatter_secondary_hexagonal_grid_update
    )
    scatter_secondary_userjit: IntProperty(
        default=0,
        min=0,
        max=1000,
        update=scatter_secondary_userjit_update
    )
    scatter_secondary_jitter_factor: FloatProperty(
        default=1,
        min=0,
        max=2,
        precision=3,
        update=scatter_secondary_jitter_factor_update
    )
    scatter_secondary_grid_resolution: IntProperty(
        default=10,
        min=1,
        max=50,
        update=scatter_secondary_grid_resolution_update
    )
    scatter_secondary_grid_random: FloatProperty(
        default=0,
        min=0,
        max=1,
        precision=3,
        update=scatter_secondary_grid_random_update
    )
    #################################################################
    # end secondary para tipo lego
    #################################################################

    scatter_detail_size_particles: FloatProperty(
        default=0.028,
        description="Scatter Detail Size in Viewport",
        update=scatter_detail_size_particles_update
    )
    scatter_secondary_size_particles: FloatProperty(
        default=0.035,
        description="Scatter Secondary Size in Viewport",
        update=scatter_secondary_size_particles_update
    )

    ######################################################################################
    # particles
    ######################################################################################
    show_emitter_viewport: BoolProperty(
        default=True,
        update=show_emitter_viewport_update
    )
    show_emitter_render: BoolProperty(
        default=True,
        update=show_emitter_render_update
    )
    ps_debris_type = [
        ('VOLUME', "Volume", "", 0),
        ('VERT', "Vertex", "", 1),
        ('FACE', "Faces", "", 2)
    ]
    ps_debris_type_combobox: EnumProperty(
        items=ps_debris_type,
        name="Emit From",
        default='FACE'
    )
    ps_dust_type = [
        ('VOLUME', "Volume", "", 0),
        ('VERT', "Vertex", "", 1),
        ('FACE', "Faces", "", 2)
    ]
    ps_dust_type_combobox: EnumProperty(
        items=ps_dust_type,
        name="Emit From",
        default='FACE'
    )
    ps_smoke_type_combobox: EnumProperty(
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        name="Emit From",
        default='FACE'
    )
    ps_smoke_domain_dimensions: FloatVectorProperty(
        name="Size",
        description="Domain size",
        subtype='XYZ',
        unit='LENGTH',
        default=(20.0, 20.0, 20.0),
        update=domain_size_update
    )
    ps_smoke_domain_dissolve_time: IntProperty(
        name="Time",
        description="Dissolve Time",
        default=20,
        update=domain_dissolve_time
    )
    ps_smoke_domain_resolution: IntProperty(
        name="Resolution",
        description="Resolution of Domain",
        default=40,
        update=domain_resolution
    )

    debris_count: IntProperty(
        default=15
    )
    dust_count: IntProperty(
        default=150
    )
    smoke_count: IntProperty(
        default=10
    )

    ps_from = [
        ('BROKEN', "Broken", "", 0),
        ('ALLCHUNKS', "All Chunks", "", 1)
    ]
    ps_debris_from: EnumProperty(
        items=ps_from,
        name="Emit From",
        description="Emit from"
    )
    ps_dust_from: EnumProperty(
        items=ps_from,
        name="Emit From",
        description="Emit from"
    )
    ps_smoke_from: EnumProperty(
        items=ps_from,
        name="Emit From",
        description="Emit from"
    )

    ######################################################################################
    # Filter for mute particles by selection
    ######################################################################################
    particles_mute_size_delimiter: FloatProperty(
        name="particles_mute_size_delimiter",
        description="Select chunks that are smaller than this value",
        default=20,
        min=0,
        update=particles_mute_size_delimiter_update
    )
    ######################################################################################
    # Filter for mute smoke by selection
    ######################################################################################
    smoke_mute_size_delimiter: FloatProperty(
        name="smoke_mute_size_delimiter",
        description="Select chunks that are smaller than this value",
        default=20,
        min=0,
        update=smoke_mute_size_delimiter_update
    )

    ######################################################################################
    # Cell Fracture properties
    ######################################################################################
    # decimate:
    def rbdlab_fracture_decimate_on_off_update(self, context, target_coll, mod_name):
        scn = context.scene
        rbdlab = scn.rbdlab

        prev_active = context.active_object
        prev_selection = context.selected_objects

        if rbdlab.ui.show_low_high_to_all_or_tc:
            # all rbdlab collections:
            collections = [coll for coll in bpy.data.collections if 'RBDLAB' in coll]
        else:
            # only tarfet collection:
            tcoll = rbdlab.filtered_target_collection
            if tcoll:
                coll_name = tcoll.name
                if coll_name:
                    collections = [tcoll]

        for coll in collections:
            if coll:
                coll_name = coll.name

                if target_coll == 'HIGH':
                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    target_coll_name = coll_high_name
                    property_to_read = self.fracture_high_decimate_on_off

                elif target_coll == 'LOW':
                    if RBDLabNaming.SUFIX_HIGH in coll_name:
                        coll_low_name = coll_name.replace(RBDLabNaming.SUFIX_HIGH, RBDLabNaming.SUFIX_LOW)
                    else:
                        coll_low_name = coll_name

                    target_coll_name = coll_low_name
                    property_to_read = self.fracture_low_decimate_on_off

                # print("target_coll_name", target_coll_name)
                # print("property_to_read", property_to_read)

                my_target_coll = bpy.data.collections.get(target_coll_name)
                if my_target_coll:

                    valid_objects = [obj for obj in my_target_coll.objects if obj.type == 'MESH']
                    if valid_objects:

                        active_object = valid_objects[0]
                        set_active_object(context, active_object)

                        if property_to_read == True:
                            # creamos/agregamos:
                            if mod_name not in active_object.modifiers:
                                bpy.ops.object.modifier_add(type='DECIMATE')
                                decimate_modifier = active_object.modifiers[-1]
                                decimate_modifier.name = mod_name

                                if target_coll == 'HIGH':
                                    mode = 'COLLAPSE'  # collapse
                                elif target_coll == 'LOW':
                                    mode = 'DISSOLVE'  # planar

                                decimate_modifier.decimate_type = mode

                                for obj in valid_objects:
                                    select_object(context, obj)

                                copy_modifier_by_name_from_active_to_selected(context, [mod_name])

                        # si es false igualmente los vamos a apagar:
                        for obj in valid_objects:
                            if mod_name in obj.modifiers:
                                obj.modifiers[mod_name].show_viewport = property_to_read
                                obj.modifiers[mod_name].show_render = property_to_read

                        deselect_all_objects(context)

        # restauramos la selection:
        if prev_active:
            set_active_object(context, prev_active)
        if prev_selection:
            [ob.select_set(True) for ob in prev_selection]

    fracture_high_decimate_on_off: BoolProperty(
        default=False,
        description="Viewport optimization",
        update=lambda x, y: x.rbdlab_fracture_decimate_on_off_update(y, 'HIGH', "RBDLab_Decimate_highs")
    )
    fracture_low_decimate_on_off: BoolProperty(
        default=False,
        description="Viewport optimization",
        update=lambda x, y: x.rbdlab_fracture_decimate_on_off_update(y, 'LOW', "RBDLab_Decimate_lows")
    )

    def rbdlab_fracture_decimate_ratio_update(self, context, target_coll, mod_name):
        rbdlab = context.scene.rbdlab

        if rbdlab.ui.show_low_high_to_all_or_tc:
            # all rbdlab collections:
            collections = [coll for coll in bpy.data.collections if 'RBDLAB' in coll]
        else:
            # only tarfet collection:
            tcoll = rbdlab.filtered_target_collection
            if tcoll:
                coll_name = tcoll.name
                if coll_name:
                    collections = [tcoll]

        for coll in collections:
            if coll:
                coll_name = coll.name

                if target_coll == 'HIGH':
                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    target_coll_name = coll_high_name
                    property_to_read = self.rbdlab_fracture_high_decimate_ratio

                elif target_coll == 'LOW':
                    if RBDLabNaming.SUFIX_HIGH in coll_name:
                        coll_low_name = coll_name.replace(RBDLabNaming.SUFIX_HIGH, RBDLabNaming.SUFIX_LOW)
                    else:
                        coll_low_name = coll_name

                    target_coll_name = coll_low_name
                    property_to_read = self.rbdlab_fracture_low_decimate_angle

                my_target_coll = bpy.data.collections.get(target_coll_name)
                if my_target_coll:
                    valid_objects = [obj for obj in my_target_coll.objects if obj.type == 'MESH' and mod_name in obj.modifiers]

                    for obj in valid_objects:
                        if obj.modifiers[mod_name].decimate_type == 'COLLAPSE':
                            obj.modifiers[mod_name].ratio = property_to_read
                        elif obj.modifiers[mod_name].decimate_type == 'DISSOLVE':
                            obj.modifiers[mod_name].angle_limit = property_to_read

    rbdlab_fracture_high_decimate_ratio: FloatProperty(
        # default=1,
        default=0.3,
        precision=4,
        min=0,
        max=1,
        update=lambda x, y: x.rbdlab_fracture_decimate_ratio_update(y, 'HIGH', "RBDLab_Decimate_highs")
    )

    rbdlab_fracture_low_decimate_angle: FloatProperty(
        default=0.0872665,
        min=0,
        max=3.1477,
        subtype='ANGLE',
        update=lambda x, y: x.rbdlab_fracture_decimate_ratio_update(y, 'LOW', "RBDLab_Decimate_lows")
    )

    rbdlab_cf_fast_exact: EnumProperty(
        items=(
            ('FAST', "Fast", " "),
            ('EXACT', "Exact", ""),
        ),
        description="Fast or Exact methor for Booleans",
        default='FAST',
        update=rbdlab_cf_fast_exact_update
    )
    post_original_options = [
        ('HIDE', "Hide", "", 0),
        ('REMOVE', "Remove", "", 1),
    ]
    post_original: EnumProperty(
        items=post_original_options,
        name="Post Fracture Action",
        description="Action for original object",
        default='HIDE'
    )
    rbdlab_cf_source: EnumProperty(
        name="Source",
        items=(
            ('VERT_OWN', "Own Verts", "Use own vertices"),
            ('VERT_CHILD', "Child Verts", "Use child object vertices"),
            ('PARTICLE_OWN', "Own Particles", (
                "All particle systems of the "
                "source object"
            )),
            ('PARTICLE_CHILD', "Child Particles", (
                "All particle systems of the "
                "child objects"
            )),
            ('PENCIL', "Annotation Pencil", "Annotation Grease Pencil."),
        ),
        options={'ENUM_FLAG'},
        default={'PARTICLE_OWN'},
    )
    # max chunks:
    rbdlab_cf_source_limit: IntProperty(
        # default=0,
        default=1000,
        # default=500,
        min=0,
        max=5000,
        name="Max Chunks",
        description="Limit the number of Chunks (Source Limit in Cell Fracture), 0 for unlimited",
    )
    rbdlab_cf_noise: FloatProperty(
        default=0.05,
        min=0.0,
        max=1.0,
        name="Noise",
        description="Randomize point distribution",
    )
    rbdlab_cf_wood_directions: EnumProperty(
        items=(
            ('NONE', "No Wood", " "),
            ('XDIR', "X Direction", " "),
            ('YDIR', "Y Direction", " "),
            ('ZDIR', "Z Direction", " "),
        ),
        description="Directions for make wood",
        default='NONE',
        update=rbdlab_cf_wood_directions_update
    )
    rbdlab_cf_cell_scale: FloatVectorProperty(
        name="Scale",
        description="Scale Cell Shape",
        size=3,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0),
        subtype='XYZ'
    )
    rbdlab_cf_recursion: IntProperty(
        name="Recursion",
        description="Break shards recursively",
        min=0, max=5000,
        default=0,
    )
    rbdlab_cf_recursion_source_limit: IntProperty(
        name="Source Limit",
        description="Limit the number of input points, 0 for unlimited (applies to recursion only)",
        min=0, max=5000,
        default=8,
    )
    rbdlab_cf_recursion_clamp: IntProperty(
        name="Clamp Recursion",
        description=(
            "Finish recursion when this number of objects is reached "
            "(prevents recursing for extended periods of time), zero disables"
        ),
        min=0, max=10000,
        default=250,
    )
    rbdlab_cf_recursion_chance: FloatProperty(
        name="Random Factor",
        description="Likelihood of recursion",
        min=0.0, max=1.0,
        default=0.25,
    )
    rbdlab_cf_recursion_chance_select: EnumProperty(
        name="Recurse Over",
        items=(
            ('RANDOM', "Random", ""),
            ('SIZE_MIN', "Small", "Recursively subdivide smaller objects"),
            ('CURSOR_MIN', "Cursor Close", "Recursively subdivide objects closer to the cursor"),
            ('SIZE_MAX', "Big", "Recursively subdivide bigger objects"),
        ),
        default='SIZE_MIN',
    )
    rbdlab_cf_use_sharp_edges_apply: BoolProperty(
        name="Apply Split Edge",
        description="Split sharp hard edges",
        default=True,
    )
    rbdlab_cf_margin: FloatProperty(
        name="Margin",
        description="Gaps for the fracture (gives more stable physics)",
        min=0.0,
        max=1.0,
        # default=0.001,
        default=0.00001,
        precision=5,
    )
    rbdlab_cf_collection_name: StringProperty(
        name="Single Collection Name",
        description="Use only one output collection for all chunks",
    )
    use_single_collection_name: BoolProperty(
        default=False,
        description="Use only one output collection for all chunks"
    )

    # EXPLODE
    explode_slider: FloatProperty(
        name="Amount",
        description="Amount of separation",
        default=0,
        min=0,
        precision=4,
        update=explode_slider_update
    )
    exploding: BoolProperty(
        default=False
    )
    explode_axis_x: BoolProperty(
        name="Axis X",
        description="Explode in x",
        default=True
    ) 
    explode_axis_y: BoolProperty(
        name="Axis Y",
        description="Explode in y",
        default=True
    ) 
    explode_axis_z: BoolProperty(
        name="Axis Z",
        description="Explode in z",
        default=True
    ) 
    colorize: BoolProperty(
        default=True,
        update=colorize_update
    )
    rbdlab_shading_color_type: StringProperty(
        default=""
    )

    show_boundingbox: BoolProperty(
        default=False,
        description="Show Chunks as Bounding Box",
    )
    status_show_boundingbox_in_low: BoolProperty(
        default=False
    )
    status_show_boundingbox_in_high: BoolProperty(
        default=False
    )

    # inner details
    autofix_max_iterations: IntProperty(
        default=300
    )
    inner_subdivision: IntProperty(
        default=2,
        min=1,
        max=6,
        update=inner_subdivisions_update,
    )

    def ratio_update(self, context):
        rbdlab = context.scene.rbdlab

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name

                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                else:
                    coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                # valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
                if coll_high_name in bpy.data.collections:
                    valid_objects = [obj for obj in bpy.data.collections[coll_high_name].objects if obj.type == 'MESH']

                    if valid_objects:
                        for obj in valid_objects:
                            if "RBDLab_Decimate_collapse" in obj.modifiers:
                                obj.modifiers["RBDLab_Decimate_collapse"].ratio = self.ratio

    ratio: FloatProperty(
        default=0.5,
        min=0,
        max=1,
        precision=4,
        update=ratio_update
    )

    # inner details::LaplacianSmooth:
    @staticmethod
    def lapsmooth_update(self, context, property):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            if RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
                target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
                if target_collections:
                    for target_coll in target_collections:
                        coll_name = target_coll.name

                        if coll_name:
                            if RBDLabNaming.SUFIX_LOW in coll_name:
                                coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                            else:
                                coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                            if coll_high_name in bpy.data.collections:
                                for obj in bpy.data.collections[coll_high_name].objects:
                                    if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.LAPLACIAN_MOD in obj.modifiers:
                                        mod = obj.modifiers[RBDLabNaming.LAPLACIAN_MOD]
                                        if property == "lapsmooth_toggle":
                                            mod.show_viewport = self.lapsmooth_toggle
                                            mod.show_render = self.lapsmooth_toggle
                                        elif property == "iterations":
                                            mod.iterations = self.iterations
                                        elif property == "use_x":
                                            mod.use_x = self.use_x
                                        elif property == "use_y":
                                            mod.use_y = self.use_y
                                        elif property == "use_z":
                                            mod.use_z = self.use_z
                                        elif property == "lambda_factor":
                                            mod.lambda_factor = self.lambda_factor
                                        elif property == "lambda_border":
                                            mod.lambda_border = self.lambda_border
                                        elif property == "use_volume_preserve":
                                            mod.use_volume_preserve = self.use_volume_preserve
                                        elif property == "use_normalized":
                                            mod.use_normalized = self.use_normalized

    lapsmooth_toggle: BoolProperty(
        default=False,
        update=lambda self, context: self.lapsmooth_update(self, context, "lapsmooth_toggle")
    )
    iterations: IntProperty(
        name="Repeat",
        min=0,
        max=200,
        default=1,
        update=lambda self, context: self.lapsmooth_update(self, context, "iterations")
    )
    use_x: BoolProperty(
        name='X',
        default=True,
        update=lambda self, context: self.lapsmooth_update(self, context, "use_x")
    )
    use_y: BoolProperty(
        name='Y',
        default=True,
        update=lambda self, context: self.lapsmooth_update(self, context, "use_y")
    )
    use_z: BoolProperty(
        name='Z',
        default=True,
        update=lambda self, context: self.lapsmooth_update(self, context, "use_z")
    )
    lambda_factor: FloatProperty(
        name="Lambda Factror",
        precision=3,
        default=0.01,
        min=-1000.0,
        max=1000.0,
        update=lambda self, context: self.lapsmooth_update(self, context, "lambda_factor")
    )
    lambda_border: FloatProperty(
        name="Lambda Border",
        precision=3,
        default=0.01,
        min=-1000.0,
        max=1000.0,
        update=lambda self, context: self.lapsmooth_update(self, context, "lambda_border")
    )
    use_volume_preserve: BoolProperty(
        name="Preserve Volume",
        default=True,
        update=lambda self, context: self.lapsmooth_update(self, context, "use_volume_preserve")
    )
    use_normalized: BoolProperty(
        name="Normalized",
        default=True,
        update=lambda self, context: self.lapsmooth_update(self, context, "use_normalized")
    )
    # end inner details::LaplacianSmooth

    noise_basis: EnumProperty(
        name="Noise Basis",
        description="Noise basis used for turbulence",
        items=(
            ('BLENDER_ORIGINAL', "Blender Original", ""),
            ('ORIGINAL_PERLIN', "Original Perlin", ""),
            ('IMPROVED_PERLIN', "Improved Perlin", ""),
            ('VORONOI_F1', "Voronoi F1", ""),
            ('VORONOI_F2', "Voronoi F2", ""),
            ('VORONOI_F3', "Voronoi F3", ""),
            ('VORONOI_F4', "Voronoi F4", ""),
            ('VORONOI_F2_F1', "Voronoi F2-F1", ""),
            ('VORONOI_CRACKLE', "Voronoi Crackle", ""),
            ('CELL_NOISE', "Cell Noise", ""),
        ),
        default='BLENDER_ORIGINAL',
        update=noise_basis_update
    )
    noise_type: EnumProperty(
        name="Noise Type",
        description="Generate soft noise (smooth transitions)",
        items=(
            ('SOFT_NOISE', "Soft", ""),
            ('HARD_NOISE', "Hard", ""),
        ),
        default='SOFT_NOISE',
        update=noise_type_update
    )
    clouds_size: FloatProperty(
        default=0.2,
        min=0.03,
        update=clouds_size_update,
    )
    displace_strength: FloatProperty(
        default=0.1,
        min=-100,
        max=100,
        update=displace_strength_update,
    )

    external_roughness: BoolProperty(
        default=False,
        update=external_roughness_update
    )
    remesh_with_material: BoolProperty(
        default=True,
        description="User Inner Material or not in High remeshed chunks"
    )

    keyframes_added_text: StringProperty(
        default="Keyframes Added"
    )

    low_or_high_visibility_viewport: EnumProperty(
        items=(
            ("Low", "Low", "Low Viewport settings", "", 0),
            ("High", "High", "High Viewport settings", "", 1),
        ),
        description="View Low or High in Viewport",
        default="Low",
        update=low_or_high_visibility_viewport_update
    )
    low_or_high_visibility_render: EnumProperty(
        items=(
            ("Low", "Low", "Low Render settings", "", 0),
            ("High", "High", "High Render settings", "", 1),
        ),
        description="View Low or High in Render",
        default="High",
        update=low_or_high_visibility_render_update
    )

    # precision fro raycast
    # Increase the threshold for detecting overlap and raycast hits.
    # rbdlab_raycast_precision: FloatProperty(
    #     default=0.11,
    #     precision=6,
    #     description="values lower more chunks emit"
    # )
    # rbdlab_raycast_ray_length: FloatProperty(
    #     default=0.5,
    #     precision=6,
    #     description="values lower more chunks emit"
    # )
    # rbdlab_raycast_repeated: IntProperty(
    #     default=50,
    #     description="matches reapeated"
    # )

    # Ground
    ground_x: FloatProperty(
        default=1,
        min=0,
        update=ground_x_update
    )
    ground_y: FloatProperty(
        default=1,
        min=0,
        update=ground_y_update
    )
    show_hide_ground: BoolProperty(
        default=True,
        update=show_hide_ground_update
    )
    show_wire_ground: BoolProperty(
        default=True,
        update=show_wire_ground_update
    )

    selectable_ground: BoolProperty(
        default=True,
        update=selectable_ground_update
    )
    # End Ground

    world_position_to: EnumProperty(
        items=(
            ('HIGH', "High", "", 0),
            ('LOW', "Low", "", 1),
        ),
        default='HIGH',
        name="World Position To",
        description="For add world position uv attribute",
    )

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default

    """ TARGET COLLECTION FUNCTIONS. """

    def get_collection_name(self):
        return self.filtered_target_collection.name

    """ PARTICLE FUNCTIONS. """

    def get_particles_properties(self, _type: str = ""):
        """ Devuelve las properties del tipo de particulas especificado. """
        type = _type if _type else self.ui.selected_particle_type
        return getattr(self.particles, type, None)

    def set_particles(self, type: str) -> str:
        if not self.filtered_target_collection:
            return
        key = "particles_%s" % type
        
        # Me aseguro de que el nombre de las particulas sea menos de 63 chars, y dejo algo de margen para los suffix:
        coll_name = self.filtered_target_collection.name[:63-20]
        ps_name = "%s_%s" % (coll_name, type)

        self.filtered_target_collection[key] = ps_name
        # Particles visibility.
        self.set_particles_visibility(type, "viewport", True)
        self.set_particles_visibility(type, "render", True)
        return ps_name

    def is_particle_visible(self, type: str, view_mode: str = "") -> bool:
        if not self.filtered_target_collection:
            return False
        if not self.has_particles(type):
            return
        # Si no le especificas un modo, te devuelve la visibilidad de ambos modos... Util...
        if not view_mode:
            v_key = "particles_%s_%s" % (type, "viewport")
            r_key = "particles_%s_%s" % (type, "render")

            return bool(self.filtered_target_collection[v_key]), bool(self.filtered_target_collection[r_key])

        # Si le especificas, entonces te devuelve la visibilidad de ese modo...
        key = "particles_%s_%s" % (type, view_mode.lower())
        return self.has_flag_and_its_valid(key)

    def set_particles_visibility(self, type: str, view_mode: str = "viewport", state: bool = True):
        if not self.filtered_target_collection:
            return
        key = "particles_%s_%s" % (type, view_mode.lower())
        self.filtered_target_collection[key] = state

    def has_flag(self, flag: str) -> bool:
        return flag in self.filtered_target_collection

    def get_flag(self, flag: str):
        if not self.filtered_target_collection:
            return
        if not self.has_flag(flag):
            return
        return self.filtered_target_collection[flag]

    def set_flag(self, flag: str, value=True, create_if_not_found: bool = True) -> bool:
        if not self.filtered_target_collection:
            return False
        if not create_if_not_found:
            if not self.has_flag(flag):
                return False
        self.filtered_target_collection[flag] = value
        return True

    def remove_flag(self, flag: str) -> bool:
        if not self.filtered_target_collection:
            return False
        if not self.has_flag(flag):
            return False
        del self.filtered_target_collection[flag]
        return True

    def has_flag_and_its_valid(self, flag: str) -> bool:
        """ Flag es una custom property, esta debe ser un boolean o entero (valores 0 o 1). """
        if not self.filtered_target_collection:
            return False

        if not self.has_flag(flag):
            return False

        value = self.filtered_target_collection[flag]
        if isinstance(value, str):
            return value is not None
        return bool(value)

    def has_particles(self, _type: str = "") -> bool:
        if not self.filtered_target_collection:
            return False
        type = _type if _type else self.ui.selected_particle_type
        return self.has_flag_and_its_valid("particles_%s" % type)

    def has_p_collision(self) -> bool:
        if not self.filtered_target_collection:
            return False
        return self.has_flag_and_its_valid(RBDLabNaming.PART_COLLISION)

    def get_particles_name(self, type: str) -> str:
        if not self.has_particles(type):
            return
        return self.filtered_target_collection["particles_%s" % type]

    def has_debris_ps(self) -> bool:
        return self.has_particles("debris")

    def has_dust_ps(self) -> bool:
        return self.has_particles("dust")

    def has_smoke_ps(self) -> bool:
        return self.has_particles("smoke")

    def has_smoke(self) -> bool:
        return self.has_flag_and_its_valid("has_smoke")

    def get_smoke_domain(self, context) -> Object:
        view_layer = context.view_layer

        domains = [ob for ob in view_layer.objects if RBDLabNaming.DOMAIN_NAME in ob]
        domain = None
        if len(domains) > 0:
            domain = domains[0]

        if domain is not None:
            return domain
        else:
            print("404: No domain object found!")
            return None

    def get_smoke_domain_mod(self, context, return_settings: bool = True) -> Object:

        domain = self.get_smoke_domain(context)
        if domain is None:
            return None

        fluid = domain.modifiers.get(RBDLabNaming.SMOKE_MOD, None)
        if fluid is None:
            print("404: Domain object has not fluid modifier!")
            return None

        return fluid.domain_settings if return_settings else fluid

    def get_smoke_emiter(self, chunk: "Object", return_settings: bool = True):
        """ Returna el flow_settings del modificador flow del chunk pasado. """
        fluid = chunk.modifiers.get(RBDLabNaming.SMOKE_MOD, None)
        if not fluid:
            # print("404: Flow object has not fluid modifier!")
            return None
        return fluid.flow_settings if return_settings else fluid

    def get_chunks(self):
        tcoll = self.filtered_target_collection
        if not tcoll:
            return None

        def validate_chunk(chunk):
            return chunk.type == 'MESH' and chunk.visible_get()

        return [chunk for chunk in tcoll.objects if validate_chunk(chunk)]

    def get_selected_chunks(self):
        tcoll = self.filtered_target_collection
        if not tcoll:
            return None

        def validate_chunk(chunk):
            return chunk.type == 'MESH' and chunk.visible_get() and chunk.select_get()

        return [chunk for chunk in tcoll.objects if validate_chunk(chunk)]

    def get_selected_chunks_from_collections(self, collections):
        """ Collections es una lista de collecciones de Blender. """
        def validate_chunk(chunk):
            return chunk.type == 'MESH' and chunk.visible_get() and chunk.select_get()

        return [chunk for coll in collections for chunk in coll.objects if validate_chunk(chunk)]

    def get_chunks_from_collections(self, collections):
        """ Collections es una lista de collecciones de Blender. """
        def validate_chunk(chunk):
            return chunk.type == 'MESH' and chunk.visible_get()
        return [chunk for coll in collections for chunk in coll.objects if validate_chunk(chunk)]

    def setup_velocities(self):
        if RBDLabNaming.CMPUTD_VELOCITIES not in self.filtered_target_collection:
            bpy.ops.rbdlab.compute_velocities()

    def is_fractured(self):
        if not self.filtered_target_collection:
            return None
        return self.has_flag_and_its_valid("fracture_applied")

    def have_rbdlab_boolean_modifier(self):

        tcoll = self.filtered_target_collection
        # habilito la posibilidad de usar physics a colecciones normales
        if tcoll is None:
            return False

        if "use_highs" not in tcoll:
            coll_name = tcoll.name
        else:
            coll_name = tcoll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)

        # print("have_rbdlab_boolean_modifier coll_name:", coll_name)
        coll = bpy.data.collections.get(coll_name)
        if coll is None:
            return False

        return next((True for ob in coll.objects if RBDLabNaming.BOOLEAN_MOD in ob.modifiers), False)

