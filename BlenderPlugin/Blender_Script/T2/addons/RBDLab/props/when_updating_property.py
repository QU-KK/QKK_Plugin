import bpy
from bpy.types import Area
from mathutils import Vector
from ..addon.naming import RBDLabNaming
from ..addon.paths import RBDLabPreferences
from ..Global.functions import select_pieces_mass_less_than, select_pieces_dimensions_less_than, select_pieces_dimensions_more_than, hide_collection_in_viewport, unhide_collection_in_viewport, generic_copy, set_active_collection_to_master_coll
from ..Global.basics import enter_object_mode, select_object, set_active_object, deselect_all_objects, get_first_high_mesh_visible, context_override
from ..Global.get_common_vars import get_common_vars
# from ..ops.constraints.update import update_values


###########################################################################
# UPDATES
###########################################################################

def riggidbodies_update(self, context):
    bpy.ops.rbdlab.rigidbody_add()


# def update_constraints(self, context):
    """ PARECE QUE ESTO NO SE ESTA USANDO """
#     rbdlab = context.scene.rbdlab

#     if rbdlab.filtered_target_collection:
#         constraints_collection_name = rbdlab.filtered_target_collection.name + "_GlueConstraints"
#         if constraints_collection_name in bpy.data.collections:
#             update_values(context, constraints_collection_name)


def hide_const_coll_in_viewport_update(self, context):
    rbdlab = context.scene.rbdlab
    constraints_coll_name = None

    if rbdlab.filtered_target_collection:
        coll_name = rbdlab.filtered_target_collection.name

        all_coll_names = [coll.name for coll in rbdlab.root_collection.children]
        target_coll_name = rbdlab.filtered_target_collection.name
        if "." in target_coll_name:
            n = target_coll_name.split(".")
            for coll_n in all_coll_names:
                if n[0] in coll_n and "GlueConstraints" in coll_n and "." in coll_n:
                    constraints_coll_name = coll_n
        else:
            for coll_n in all_coll_names:
                if target_coll_name in coll_n and "GlueConstraints" in coll_n:
                    constraints_coll_name = coll_n
            # constraints_coll_name = target_coll_name + "_GlueConstraints"

        if constraints_coll_name in bpy.data.collections:
            # bpy.context.scene.frame_current = bpy.context.scene.frame_start
            contraints_visual_size_update(self, context)
            # bpy.context.space_data.overlay.show_relationship_lines = False
            # bpy.ops.view3d.toggle_xray()
            if rbdlab.constraints.hide_const_coll_in_viewport == 'HIDE':
                hide_collection_in_viewport(context, constraints_coll_name)
                unhide_collection_in_viewport(context, coll_name)
            else:
                unhide_collection_in_viewport(context, constraints_coll_name)
                hide_collection_in_viewport(context, coll_name)


def contraints_visual_size_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        constraints_collection_name = rbdlab.filtered_target_collection.name + "_GlueConstraints"
        if constraints_collection_name in bpy.data.collections:
            const_new_size = float("%f" % rbdlab.constraints.visual_size)
            for const in bpy.data.collections[constraints_collection_name].objects:
                # const.empty_display_size = rbdlab.constraints.visual_size
                const.scale = [const_new_size, const_new_size, const_new_size]


def part_count(self, context):
    rbdlab = context.scene.rbdlab

    for obj in context.selected_objects:
        if "Detail_Scatter" in obj.modifiers:
            obj.particle_systems["Detail_Scatter"].settings.count = rbdlab.particle_count


def part_second_count(self, context):
    rbdlab = context.scene.rbdlab

    for obj in context.selected_objects:
        if RBDLabNaming.SECOND_SCATTER in obj.modifiers:
            obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.count = rbdlab.particle_secondary_count


def scatter_detail_size_particles_update(self, context):
    for obj in context.selected_objects:
        if "Detail_Scatter" in obj.modifiers:
            obj.particle_systems["Detail_Scatter"].settings.display_size = self.scatter_detail_size_particles


def scatter_secondary_size_particles_update(self, context):
    for obj in context.selected_objects:
        if RBDLabNaming.SECOND_SCATTER in obj.modifiers:
            obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.display_size = self.scatter_secondary_size_particles


def show_emitter_viewport_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        for obj in bpy.data.collections[rbdlab.filtered_target_collection.name].objects:
            if obj.type == 'MESH' and obj.visible_get():
                obj.show_instancer_for_viewport = rbdlab.show_emitter_viewport


def show_emitter_render_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        for obj in bpy.data.collections[rbdlab.filtered_target_collection.name].objects:
            if obj.type == 'MESH' and obj.visible_get():
                obj.show_instancer_for_render = rbdlab.show_emitter_render


def mass_delimiter_by_mass_update(self, context):
    rbdlab = context.scene.rbdlab
    select_pieces_mass_less_than(context, rbdlab.mass_delimiter)


def size_delimiter_small_update(self, context):
    delimiter = self.size_delimiter_small / 10
    only_with_particles = False
    select_pieces_dimensions_less_than(self, context, delimiter, only_with_particles)


def particles_mute_size_delimiter_update(self, context):
    delimiter = self.particles_mute_size_delimiter / 10
    only_with_particles = True
    select_pieces_dimensions_less_than(self, context, delimiter, only_with_particles)


def smoke_mute_size_delimiter_update(self, context):
    delimiter = self.smoke_mute_size_delimiter / 10
    only_with_particles = False
    select_pieces_dimensions_less_than(self, context, delimiter, only_with_particles)


def size_delimiter_big_update(self, context):
    select_pieces_dimensions_more_than(self, context)


def subdiv_update(self, context):
    rbdlab = context.scene.rbdlab
    objects = bpy.context.selected_objects
    if objects:
        deselect_all_objects(context)
        for obj in objects:
            select_object(context, obj)
            set_active_object(context, obj)
            if obj.type == 'MESH':
                obj.display_type = 'SOLID'
                enter_object_mode(context)
                if rbdlab.subdivision_level > 0:
                    for obj in bpy.context.selected_objects:
                        set_active_object(context, obj)
                        obj.show_wire = True
                        bpy.ops.object.subdivision_set(level=rbdlab.subdivision_level, relative=False)
                        for mod in obj.modifiers:
                            if mod.type == 'SUBSURF':
                                mod.show_only_control_edges = False
                                if rbdlab.subdivision_simple:
                                    mod.subdivision_type = 'CATMULL_CLARK'
                                else:
                                    mod.subdivision_type = 'SIMPLE'
                else:
                    for obj in bpy.context.selected_objects:
                        obj.show_wire = False
                        set_active_object(context, obj)
                        bpy.ops.object.modifier_remove(modifier="Subdivision")


def scatter_detail_emit_from_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in bpy.context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Detail_Scatter" in obj.particle_systems:
                obj.particle_systems["Detail_Scatter"].settings.emit_from = rbdlab.scatter_detail_emit_from

#################################################################
# secondary para tipo lego:
#################################################################


def scatter_secondary_emit_from_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.emit_from = rbdlab.scatter_secondary_emit_from


def texture_secondary_emit_from_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                obj.particle_systems["Scatter_by_Texture"].settings.emit_from = rbdlab.scatter.texture_secondary_emit_from


def texture_noise_basis_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].noise_basis = rbdlab.scatter.texture_noise_basis


def texure_use_color_ramp_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].use_color_ramp = rbdlab.texure_use_color_ramp


def texture_mapping_offset_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            obj.particle_systems["Scatter_by_Texture"].settings.texture_slots[0].offset = rbdlab.scatter.texture_mapping_offset


def texture_mapping_size_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            obj.particle_systems["Scatter_by_Texture"].settings.texture_slots[0].scale = rbdlab.scatter.texture_mapping_size


def texture_texture_coords_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            obj.particle_systems["Scatter_by_Texture"].settings.texture_slots[0].texture_coords = rbdlab.scatter.texture_texture_coords


def texture_noise_depth_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].noise_depth = rbdlab.scatter.texture_noise_depth


def texture_noise_scale_upadte(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].noise_scale = rbdlab.scatter.texture_noise_scale


def texture_noise_type_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].noise_type = rbdlab.scatter.texture_noise_type


def texture_cloud_type_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if "Scatter_by_Texture" in obj.particle_systems:
                for texture in obj.particle_systems["Scatter_by_Texture"].settings.texture_slots:
                    if texture:
                        if texture.name.startswith("RBDLab_Scatter_Texture"):
                            bpy.data.textures[texture.name].cloud_type = rbdlab.scatter.texture_cloud_type


def scatter_secondary_use_modifier_stack_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.use_modifier_stack = rbdlab.scatter_secondary_use_modifier_stack


def scatter_secondary_distribution_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.distribution = rbdlab.scatter_secondary_distribution


def scatter_secondary_use_emit_random_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.use_emit_random = rbdlab.scatter_secondary_use_emit_random


def scatter_secondary_use_even_distribution_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.use_even_distribution = rbdlab.scatter_secondary_use_even_distribution


def scatter_secondary_invert_grid_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.invert_grid = rbdlab.scatter_secondary_invert_grid


def scatter_secondary_hexagonal_grid_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.hexagonal_grid = rbdlab.scatter_secondary_hexagonal_grid


def scatter_secondary_grid_resolution_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.grid_resolution = rbdlab.scatter_secondary_grid_resolution


def scatter_secondary_grid_random_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.grid_random = rbdlab.scatter_secondary_grid_random


def scatter_secondary_userjit_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.userjit = rbdlab.scatter_secondary_userjit


def scatter_secondary_jitter_factor_update(self, context):
    rbdlab = context.scene.rbdlab
    for obj in context.selected_objects:
        if len(obj.particle_systems) > 0:
            if RBDLabNaming.SECOND_SCATTER in obj.particle_systems:
                obj.particle_systems[RBDLabNaming.SECOND_SCATTER].settings.jitter_factor = rbdlab.scatter_secondary_jitter_factor

#################################################################
# end secondary para tipo lego
#################################################################


def target_collection_update(self, context):
    # print("[target_collection_update] update target collection")

    rbdlab, ui, tcoll_list = get_common_vars(context, get_rbdlab=True, get_ui=True, get_tcoll_list=True)
    tcoll = tcoll_list.active

    chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    if chunks:

        # si el usuario cambia de coleccion volvemos a usar solo una coleccion:
        if tcoll:
            tcoll[RBDLabNaming.LAST_CREATED_COLLS] = [tcoll]

        # si esta joined puede estar de tipo mesh en lugar de convex hull como el resto, por eso los descartamos como muestra:
        valid_chunks = [ob for ob in chunks if RBDLabNaming.JOINED not in ob]

        # si el usuario hace merje a todos los chunks pues nada, se entregan le chunk:
        if not valid_chunks:
            valid_chunks = chunks

        ob = None
        if len(valid_chunks) > 0:
            ob = valid_chunks[0]

        ob_high = get_first_high_mesh_visible(context)

        if ob_high:

            if "RBDLab_Decimate_highs" in ob_high.modifiers:
                rbdlab.fracture_high_decimate_on_off = ob_high.modifiers["RBDLab_Decimate_highs"].show_viewport
            else:
                rbdlab.fracture_high_decimate_on_off = False

        if ob:

            rbdlab.show_boundingbox = True if ob.display_type == 'BOUNDS' else False

            # se perdia la seleccion con fracture_low_decimate_on_off:
            if "RBDLab_Decimate_lows" in ob.modifiers:
                rbdlab.fracture_low_decimate_on_off = ob.modifiers["RBDLab_Decimate_lows"].show_viewport
            else:
                rbdlab.fracture_low_decimate_on_off = False

            # update ui particles:
            if ui.main_modules == 'PARTICLES':
                ob_and_ps = {}

                # Buscar el primer objeto con al menos un sistema de partículas válido
                for ob in chunks:
                    if len(ob.particle_systems) <= 0:
                        continue
                    if RBDLabNaming.INNER_EMISOR not in ob:
                        continue

                    # Agregar todos los sistemas de partículas al diccionario obj_and_ps
                    ob_and_ps[ob] = [ps for ps in ob.particle_systems]
                    break

                # print(obj_and_ps)
                if ob_and_ps:
                    # print(obj_and_ps)
                    for ob, particle_systems in ob_and_ps.items():
                        for ps in particle_systems:

                            current_type = None
                            if "debris" in ps.name:
                                ps_props = rbdlab.get_particles_properties("debris")
                                current_type = "debris"
                            elif "dust" in ps.name:
                                ps_props = rbdlab.get_particles_properties("dust")
                                current_type = "dust"
                            elif "smoke" in ps.name:
                                ps_props = rbdlab.get_particles_properties("smoke")
                                current_type = "smoke"

                            if not ps_props:
                                continue

                            ps_props.display_method = ps.settings.display_method
                            ps_props.display_size = ps.settings.display_size
                            ps_props.display_color = ps.settings.display_color

                            if current_type != "smoke":
                                ps_props.show_instancer_for_viewport = ob.show_instancer_for_viewport

                            ps_props.count = ps.settings.count

                            ''' New neighbor system
                            if "rbdlab_ps_offset" in ob:
                                ps_props.offset = ob["rbdlab_ps_offset"]
                            else:
                                ps_props.offset = ps_props.get_default_properties("offset")
                            '''

                            if "rbdlab_ps_enable_trails" in ob:
                                ps_props.enable_end_trails = ob["rbdlab_ps_enable_trails"]
                            else:
                                ps_props.enable_end_trails = ps_props.get_default_properties("enable_end_trails")

                            if RBDLabNaming.END_TRAILS in ob:
                                ps_props.end_trails = ob[RBDLabNaming.END_TRAILS]
                            else:
                                ps_props.end_trails = ps_props.get_default_properties("end_trails")

                            ps_props.lifetime = ps.settings.lifetime
                            ps_props.lifetime_random = ps.settings.lifetime_random
                            ps_props.particle_size = ps.settings.particle_size
                            ps_props.size_random = ps.settings.size_random

                            if current_type != "smoke":
                                ps_props.use_dead = ps.settings.use_dead
                                ps_props.show_instancer_for_render = ob.show_instancer_for_render

                            ps_props.normal = ps.settings.normal_factor
                            ps_props.direction = ps.settings.object_align_factor
                            ps_props.object_velocity = ps.settings.object_factor
                            ps_props.velocity_randomize = ps.settings.factor_random
                            if current_type != "smoke":

                                ps_props.use_multiply_size_mass = ps.settings.use_multiply_size_mass
                                ps_props.timestep = ps.settings.timestep
                                ps_props.subframes = ps.settings.subframes

                                ps_props.use_rotations = ps.settings.use_rotations
                                ps_props.rotation_mode = ps.settings.rotation_mode
                                ps_props.rotation_factor_random = ps.settings.rotation_factor_random
                                ps_props.phase_factor = ps.settings.phase_factor
                                ps_props.phase_factor_random = ps.settings.phase_factor_random
                                ps_props.use_dynamic_rotation = ps.settings.use_dynamic_rotation
                                if ps.settings.instance_collection:
                                    ps_props.debris_coll = ps.settings.instance_collection
                            ps_props.all = ps.settings.effector_weights.all
                            ps_props.gravity = ps.settings.effector_weights.gravity
                            ps_props.force = ps.settings.effector_weights.force
                            ps_props.vortex = ps.settings.effector_weights.vortex
                            ps_props.magnetic = ps.settings.effector_weights.magnetic
                            ps_props.harmonic = ps.settings.effector_weights.harmonic
                            ps_props.charge = ps.settings.effector_weights.charge
                            ps_props.lennardjones = ps.settings.effector_weights.lennardjones
                            ps_props.wind = ps.settings.effector_weights.wind
                            ps_props.curve_guide = ps.settings.effector_weights.curve_guide
                            ps_props.texture = ps.settings.effector_weights.texture
                            ps_props.smokeflow = ps.settings.effector_weights.smokeflow
                            ps_props.turbulence = ps.settings.effector_weights.turbulence
                            ps_props.drag = ps.settings.effector_weights.drag
                            ps_props.boid = ps.settings.effector_weights.boid
                            if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
                                obj_basic_debris = bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects[0]
                                if obj_basic_debris:
                                    ps_props.basic_subdivision_type = obj_basic_debris.modifiers["Subdivision"].subdivision_type
                                    ps_props.basic_subdivision_level = obj_basic_debris.modifiers["Subdivision"].levels
                                    ps_props.basic_decimate_collapse = obj_basic_debris.modifiers["Decimate"].ratio
                                    ps_props.basic_disp_strength = obj_basic_debris.modifiers["Displace"].strength
                                    if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.textures:
                                        ps_props.basic_clouds_size = bpy.data.textures[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].noise_scale
                                        ps_props.basic_clouds_depth = bpy.data.textures[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].noise_depth
                                    # if "rbdlab_basic_outher_material" in obj_basic_debris:
                                    #     ps_props.basic_outher_material = obj_basic_debris["rbdlab_basic_outher_material"]
                                    # if "rbdlab_basic_inner_material" in obj_basic_debris:
                                    #     ps_props.basic_inner_material = obj_basic_debris["rbdlab_basic_inner_material"]

            if ui.main_modules == 'COLLISIONS':
                has_p_collision = rbdlab.has_p_collision()
                if has_p_collision and hasattr(ob, "collision"):
                    rbdlab.collision.stickiness = ob.collision.stickiness
                    rbdlab.collision.use_particle_kill = ob.collision.use_particle_kill
                    rbdlab.collision.damping_factor = ob.collision.damping_factor
                    rbdlab.collision.friction_factor = ob.collision.friction_factor
                    rbdlab.collision.friction_random = ob.collision.friction_random
                else:
                    rbdlab.collision.stickiness = rbdlab.collision.get_default_properties("stickiness")
                    rbdlab.collision.use_particle_kill = rbdlab.collision.get_default_properties("use_particle_kill")
                    rbdlab.collision.damping_factor = rbdlab.collision.get_default_properties("damping_factor")
                    rbdlab.collision.friction_factor = rbdlab.collision.get_default_properties("friction_factor")
                    rbdlab.collision.friction_random = rbdlab.collision.get_default_properties("friction_random")

            if ui.main_modules == 'PHYSICS':
                physics_props = rbdlab.physics
                rbd_props = physics_props.rigidbodies

                if ob.rigid_body:

                    # rbdlab.collision_shape_combobox = 'CONVEX_HULL'
                    rbd_props.collision_shape = 'CONVEX_HULL'

                    if RBDLabNaming.CURRENT_MASS in ob:
                        rbd_props.avalidable_mass = ob[RBDLabNaming.CURRENT_MASS].title()
                    else:
                        rbd_props.avalidable_mass = rbd_props.get_default_properties("avalidable_mass")

                    if RBDLabNaming.CUSTOM_MASS in ob:
                        rbd_props.custom_mass = ob[RBDLabNaming.CUSTOM_MASS]
                    else:
                        rbd_props.custom_mass = rbd_props.get_default_properties("custom_mass")
                    
                    if RBDLabNaming.METAL_MASS in ob:
                        rbd_props.metal_mass = ob[RBDLabNaming.METAL_MASS]
                    else:
                        rbd_props.metal_mass = rbd_props.get_default_properties("metal_mass")

                    rbd_props.collision_shape = ob.rigid_body.collision_shape

                    rbd_props.use_collision_margin = ob.rigid_body.use_margin
                    rbd_props.collision_margin = ob.rigid_body.collision_margin
                    rbd_props.rb_friction = ob.rigid_body.friction
                    rbd_props.restitution = ob.rigid_body.restitution
                    # if RBDLabNaming.RBD_SEL_KINEMATIC not in ob and RBDLabNaming.PASSIVE not in obj:
                    #     rbdlab.deactivation = ob.rigid_body.use_deactivation
                    #     rbdlab.kinematic = ob.rigid_body.kinematic
                    # else:
                    # get first chunk but no kinematc selected

                    if chunks:

                        for ob in chunks:
                            if RBDLabNaming.RBD_SEL_KINEMATIC in ob:
                                continue

                            if not hasattr(ob, "rigid_body"):
                                continue

                            if RBDLabNaming.PASSIVE in ob:
                                continue

                            rbd_props.kinematic = ob.rigid_body.kinematic
                            rbd_props.deactivation = ob.rigid_body.use_deactivation

                        rbd_props.d_translation = ob.rigid_body.linear_damping
                        rbd_props.d_rotation = ob.rigid_body.angular_damping

                    # key_constraints = RBDLabNaming.CONSTRAINTS
                    # if key_constraints in ob:
                    #     const_a = obj[key_constraints].split()
                    #     empty = const_a[0]
                    #     rbdlab.constraints.breakable = bpy.data.objects[empty].rigid_body_constraint.use_breaking
                    #     rbdlab.constraints.glue_strength = bpy.data.objects[empty].rigid_body_constraint.breaking_threshold
                    #     rbdlab.constraints.override_iterations = bpy.data.objects[empty].rigid_body_constraint.use_override_solver_iterations
                    #     rbdlab.constraints.iterations = bpy.data.objects[empty].rigid_body_constraint.solver_iterations
                    # else:
                    #     rbdlab.constraints.breakable = rbdlab.get_default_properties("breakable")
                    #     rbdlab.constraints.glue_strength = rbdlab.get_default_properties("glue_strength")
                    #     rbdlab.constraints.override_iterations = rbdlab.get_default_properties("override_iterations")
                    #     rbdlab.constraints.iterations = rbdlab.get_default_properties("iterations")
                else:

                    # Defaults:
                    # rbd
                    rbd_props.avalidable_mass = rbd_props.get_default_properties("avalidable_mass")
                    rbd_props.custom_mass = rbd_props.get_default_properties("custom_mass")

                    rbd_props.collision_shape = rbd_props.get_default_properties("collision_shape")

                    rbd_props.use_collision_margin = rbd_props.get_default_properties("use_collision_margin")
                    rbd_props.collision_margin = rbd_props.get_default_properties("collision_margin")
                    rbd_props.rb_friction = rbd_props.get_default_properties("rb_friction")
                    rbd_props.restitution = rbd_props.get_default_properties("restitution")
                    rbd_props.deactivation = rbd_props.get_default_properties("deactivation")
                    rbd_props.kinematic = rbd_props.get_default_properties("kinematic")
                    rbd_props.d_translation = rbd_props.get_default_properties("d_translation")
                    rbd_props.d_rotation = rbd_props.get_default_properties("d_rotation")
                    # const
                    # rbdlab.constraints.breakable = rbdlab.get_default_properties("breakable")
                    # rbdlab.constraints.glue_strength = rbdlab.get_default_properties("glue_strength")
                    # rbdlab.constraints.override_iterations = rbdlab.get_default_properties("override_iterations")
                    # rbdlab.constraints.iterations = rbdlab.get_default_properties("iterations")

        else:
            # Defaults sin obj:

            rbdlab.use_auto_smooth = rbdlab.get_default_properties("use_auto_smooth")
            rbdlab.auto_smooth = rbdlab.get_default_properties("auto_smooth")

            # rbd

            if ui.main_modules == 'PHYSICS':
                rbd_props.avalidable_mass = rbd_props.get_default_properties("avalidable_mass")
                rbd_props.custom_mass = rbd_props.get_default_properties("custom_mass")

                rbd_props.use_collision_margin = rbd_props.get_default_properties("use_collision_margin")
                rbd_props.collision_margin = rbd_props.get_default_properties(
                    "collision_margin")  # Cuando la prop tiene name hay que suar su name
                rbd_props.rb_friction = rbd_props.get_default_properties("rb_friction")
                rbd_props.restitution = rbd_props.get_default_properties("restitution")
                rbd_props.deactivation = rbd_props.get_default_properties("deactivation")
                rbd_props.kinematic = rbd_props.get_default_properties("kinematic")
                rbd_props.d_translation = rbd_props.get_default_properties("d_translation")
                rbd_props.d_rotation = rbd_props.get_default_properties("d_rotation")
            # const
            # rbdlab.constraints.breakable = rbdlab.get_default_properties("breakable")
            # rbdlab.constraints.glue_strength = rbdlab.get_default_properties("glue_strength")
            # rbdlab.constraints.override_iterations = rbdlab.get_default_properties("override_iterations")
            # rbdlab.constraints.iterations = rbdlab.get_default_properties("iterations")
            # auto smooth


def use_auto_smooth_update(self, context):
    
    rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True,get_tcoll_list=True)
    tcoll = tcoll_list.active

    if tcoll:

        prev_active = context.active_object
        prev_selection = context.selected_objects

        if RBDLabNaming.LAST_CREATED_COLLS in tcoll:
            target_collections = tcoll[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:

                for target_coll in target_collections:
                    deselect_all_objects(context)

                    valid_objects = [ob for ob in target_coll.objects if ob.type == 'MESH']

                    if not valid_objects:
                        continue

                    if RBDLabNaming.SUFIX_LOW in target_coll.name:
                        target_high_coll_name = target_coll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        target_high_coll_name = target_coll.name + RBDLabNaming.SUFIX_HIGH

                    high_coll = bpy.data.collections.get(target_high_coll_name)

                    if high_coll is not None:
                        valid_objects += [ob for ob in high_coll.objects if ob.type == 'MESH']

                    # Seteamos el shade smooth al original solo en Fracture Details:
                    deselect_all_objects(context)
                    all_obs = set()

                    # print(valid_objects)
                    if "starting_fracture" in tcoll:
                        
                        org_obs_visibility = {}
                        obj_processed = set()

                        # select and unhide objects:
                        for valid_ob in valid_objects:

                            if valid_ob in obj_processed:
                                continue

                            if RBDLabNaming.FROM not in valid_ob:
                                continue

                            original_ob = bpy.data.objects.get(valid_ob[RBDLabNaming.FROM])
                            if not original_ob:
                                continue

                            if original_ob not in org_obs_visibility:
                                org_obs_visibility[original_ob] = original_ob.hide_get() 
                                original_ob.hide_set(False)

                            all_obs.add(valid_ob)
                            all_obs.add(original_ob)
                            obj_processed.add(valid_ob)

                        # a los originales y los chunks:
                        if len(all_obs) > 0:
                            [ob.select_set(True) for ob in all_obs]
                            set_active_object(context, list(all_obs)[0])
                            if rbdlab.use_auto_smooth:
                                bpy.ops.object.shade_smooth_by_angle(angle=rbdlab.auto_smooth)
                            
                        for ob, visibility in org_obs_visibility.items():
                            ob.hide_set(visibility)

                        bpy.ops.object.select_all(action='DESELECT')
                    
                    bpy.ops.object.select_all(action='DESELECT')
                    if len(valid_objects) > 0:

                        [ob.select_set(True) for ob in valid_objects]
                        set_active_object(context, valid_objects[0])
                        
                        if rbdlab.use_auto_smooth:
                            bpy.ops.object.shade_smooth_by_angle(angle=rbdlab.auto_smooth)
                        else:
                            bpy.ops.object.shade_flat()
                            
                deselect_all_objects(context)

        # restauramos la selection:
        if prev_active:
            set_active_object(context, prev_active)
        if prev_selection:
            [ob.select_set(True) for ob in prev_selection]


def auto_smooth_update(self, context):

    rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True,get_tcoll_list=True)
    tcoll = tcoll_list.active

    if tcoll:

        prev_active = context.active_object
        prev_selection = context.selected_objects

        if RBDLabNaming.LAST_CREATED_COLLS in tcoll:
            target_collections = tcoll[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    deselect_all_objects(context)

                    if RBDLabNaming.SUFIX_LOW in target_coll.name:
                        target_high_coll_name = target_coll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        target_high_coll_name = target_coll.name + RBDLabNaming.SUFIX_HIGH

                    valid_objects = [obj for obj in target_coll.objects if obj.type == 'MESH']

                    if not valid_objects:
                        continue

                    target_high_coll = bpy.data.collections.get(target_high_coll_name)
                    if target_high_coll:
                        valid_objects += [ob for ob in target_high_coll.objects if ob.type == 'MESH']

                    if rbdlab.use_auto_smooth:
                        bpy.ops.object.select_all(action='DESELECT')
                        [valid_obj.select_set(True) for valid_obj in valid_objects]
                        bpy.ops.object.shade_smooth_by_angle(angle=int(rbdlab.auto_smooth))

                deselect_all_objects(context)

        # restauramos la selection:
        if prev_active:
            set_active_object(context, prev_active)
        if prev_selection:
            [ob.select_set(True) for ob in prev_selection]

#######################################################################################################################
# Explode casero
#######################################################################################################################


def get_objects_centroids(context):

    scn = context.scene
    rbdlab = scn.rbdlab
    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active

    if tcoll:
        coll_name = tcoll.name
        if coll_name:

            if rbdlab.low_or_high_visibility_viewport == 'High':
                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                else:
                    coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH
                coll_high = bpy.data.collections.get(coll_high_name)
                valid_objects = coll_high.objects
            else:
                valid_objects = tcoll_list.get_current_active_tcoll_valild_objects(context)

    # print("****", valid_objects)
    if valid_objects:
        # if RBDLabNaming.SUFIX_LOW in coll_name:
        #     coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)

        # hallar el centroid de la seleccion:
        obx = []  # <- aqui iremos guardando las coordenadas x de todos los objetos
        oby = []  # <- aqui iremos guardando las coordenadas y de todos los objetos
        obz = []  # <- aqui iremos guardando las coordenadas z de todos los objetos

        # if coll_high_name:
        #     [valid_objects.append(obj) for obj in bpy.data.collections[coll_high_name].objects if obj.type == 'MESH' and obj.visible_get()]

        total_objects = 0
        for ob in valid_objects:
            # objx.append(obj.location.x)
            # objy.append(obj.location.y)
            # objz.append(obj.location.z)

            obx.append(ob.matrix_world.translation.x)
            oby.append(ob.matrix_world.translation.y)
            obz.append(ob.matrix_world.translation.z)

            total_objects += 1

        # obtenemos el centroid:
        centroid = None
        try:
            centroid = Vector((sum(obx) / total_objects, sum(oby) / total_objects, sum(obz) / total_objects))
        except:
            pass

        if centroid:
            return [centroid, total_objects, valid_objects]


def explode_slider_update(self, context):
    scn = context.scene
    rbdlab = scn.rbdlab

    # tcoll_list = rbdlab.lists.target_coll_list
    # tcoll = tcoll_list.active

    if rbdlab.exploding:
        deselect_all_objects(context)

        centroid, total_objects, valid_objects = get_objects_centroids(context)

        speed_decrementor = 28
        current_active = context.active_object


        fuerza = rbdlab.explode_slider
        # fuerza = math.degrees(rbdlab.explode_slider)/100
        # fuerza = math.radians(rbdlab.explode_slider)*1000

        for ob in valid_objects:
            
            translation = ob.matrix_world.translation

            if "exploded" not in ob:
                # obj["exploded"] = obj.location
                ob["exploded"] = translation

            initial_location = Vector((ob["exploded"]))

            '''
            # Con delta:
            direccion = obj.location - centroid
            # direccion.normalize()
            obj.delta_location = initial_location + (direccion * (fuerza/speed_decrementor)) - obj.location
            '''

            # sin delta:
            # direccion = ob.matrix_world.translation - centroid
            # ob.matrix_world.translation = initial_location + (direccion * (fuerza/speed_decrementor))

            # sin delta pero por axis:
            if rbdlab.explode_axis_x:
                x_direccion = translation.x - centroid.x
                translation.x = initial_location.x + (x_direccion * (fuerza/speed_decrementor))

            if rbdlab.explode_axis_y:
                y_direccion = translation.y - centroid.y
                translation.y = initial_location.y + (y_direccion * (fuerza/speed_decrementor))

            if rbdlab.explode_axis_z:
                z_direccion = translation.z - centroid.z
                translation.z = initial_location.z + (z_direccion * (fuerza/speed_decrementor))


        set_active_object(context, current_active)
        deselect_all_objects(context)


def colorize_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.colorize:
        if bpy.context.space_data.shading.type != 'SOLID':
            bpy.context.space_data.shading.type = 'SOLID'
        bpy.context.space_data.shading.color_type = 'RANDOM'
    else:
        if bpy.context.space_data.shading.type == 'SOLID':
            if "has_pretty_shading" in context.workspace:
                if context.workspace["has_pretty_shading"]:
                    if bpy.context.space_data.shading.color_type != 'MATERIAL':
                        bpy.context.space_data.shading.color_type = 'MATERIAL'
                else:
                    if bpy.context.space_data.shading.color_type != 'OBJECT':
                        bpy.context.space_data.shading.color_type = 'OBJECT'
            else:
                if bpy.context.space_data.shading.color_type != 'OBJECT':
                    bpy.context.space_data.shading.color_type = 'OBJECT'
        elif bpy.context.space_data.shading.type == 'WIREFRAME':
            if bpy.context.space_data.shading.color_type != 'OBJECT':
                bpy.context.space_data.shading.color_type = 'OBJECT'


def domain_size_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:
            domain_name = RBDLabNaming.DOMAIN_NAME
            domain = bpy.data.objects[domain_name]
            domain.dimensions = Vector(
                (rbdlab.ps_smoke_domain_dimensions[0],
                 rbdlab.ps_smoke_domain_dimensions[1],
                 rbdlab.ps_smoke_domain_dimensions[2]))
            # select_object(context, domain)
            set_active_object(context, domain)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
            deselect_all_objects(context)


def domain_dissolve_time(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:
            domain_name = RBDLabNaming.DOMAIN_NAME
            domain = bpy.data.objects[domain_name]
            domain.modifiers[RBDLabNaming.DOMAIN_NAME].domain_settings.dissolve_speed = rbdlab.ps_smoke_domain_dissolve_time


def domain_resolution(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:
            domain_name = RBDLabNaming.DOMAIN_NAME
            domain = bpy.data.objects[domain_name]
            domain.modifiers[RBDLabNaming.DOMAIN_NAME].domain_settings.resolution_max = rbdlab.ps_smoke_domain_resolution


def noise_basis_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        if RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    coll_name = target_coll.name

                    if coll_name:
                        if RBDLabNaming.SUFIX_LOW in coll_name:
                            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                        elif RBDLabNaming.SUFIX_HIGH not in coll_name:
                            coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                        if coll_high_name in bpy.data.collections:
                            work_coll = coll_high_name + "_Clouds"
                        else:
                            work_coll = coll_name + "_Clouds"

                        if work_coll in bpy.data.textures:
                            bpy.data.textures[work_coll].noise_basis = self.noise_basis


def noise_type_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        if RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    coll_name = target_coll.name

                    if coll_name:
                        if RBDLabNaming.SUFIX_LOW in coll_name:
                            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                        elif RBDLabNaming.SUFIX_HIGH not in coll_name:
                            coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                        if coll_high_name in bpy.data.collections:
                            work_coll = coll_high_name + "_Clouds"
                        else:
                            work_coll = coll_name + "_Clouds"

                        if work_coll in bpy.data.textures:
                            bpy.data.textures[work_coll].noise_type = self.noise_type


def clouds_size_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        if RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    coll_name = target_coll.name

                    if coll_name:
                        if RBDLabNaming.SUFIX_LOW in coll_name:
                            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                        elif RBDLabNaming.SUFIX_HIGH not in coll_name:
                            coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                        if coll_high_name in bpy.data.collections:
                            work_coll = coll_high_name + "_Clouds"
                        else:
                            work_coll = coll_name + "_Clouds"

                        if work_coll in bpy.data.textures:
                            bpy.data.textures[work_coll].noise_scale = self.clouds_size


def inner_subdivisions_update(self, context):
    rbdlab = context.scene.rbdlab

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
                                if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.SUBSURF_MOD in obj.modifiers:
                                    obj.modifiers[RBDLabNaming.SUBSURF_MOD].levels = self.inner_subdivision
                                    obj.modifiers[RBDLabNaming.SUBSURF_MOD].render_levels = self.inner_subdivision


def displace_strength_update(self, context):
    rbdlab = context.scene.rbdlab

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
                            work_coll = coll_high_name
                        else:
                            work_coll = coll_name

                        for obj in bpy.data.collections[work_coll].objects:
                            if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.DISPLACE in obj.modifiers:
                                obj.modifiers[RBDLabNaming.DISPLACE].strength = self.displace_strength


def remesh_or_subdivision_update(self, context):
    rbdlab = context.scene.rbdlab

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

                            valid_objects = [
                                obj for obj in bpy.data.collections[coll_high_name].objects
                                if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.REMESH in obj.modifiers and RBDLabNaming.SUBSURF_MOD in
                                obj.modifiers]

                            for obj in valid_objects:
                                select_object(context, obj)

                            if context.selected_objects:
                                active_object = valid_objects[0]
                                set_active_object(context, valid_objects[0])

                                if self.remesh_or_subdivision == "Remesh":
                                    active_object.modifiers[RBDLabNaming.REMESH].show_viewport = True
                                    active_object.modifiers[RBDLabNaming.REMESH].show_render = True
                                    active_object.modifiers[RBDLabNaming.SUBSURF_MOD].show_viewport = False
                                    active_object.modifiers[RBDLabNaming.SUBSURF_MOD].show_render = False
                                    # self.external_roughness = True
                                    active_object.modifiers[RBDLabNaming.LAPLACIAN_MOD].show_viewport = False
                                    active_object.modifiers[RBDLabNaming.LAPLACIAN_MOD].show_render = False
                                else:
                                    active_object.modifiers[RBDLabNaming.REMESH].show_viewport = False
                                    active_object.modifiers[RBDLabNaming.REMESH].show_render = False
                                    active_object.modifiers[RBDLabNaming.SUBSURF_MOD].show_viewport = True
                                    active_object.modifiers[RBDLabNaming.SUBSURF_MOD].show_render = True

                                    active_object.modifiers[RBDLabNaming.LAPLACIAN_MOD].show_viewport = rbdlab.lapsmooth_toggle
                                    active_object.modifiers[RBDLabNaming.LAPLACIAN_MOD].show_render = rbdlab.lapsmooth_toggle

                                self.external_roughness = False

                            bpy.ops.object.make_links_data(type='MODIFIERS')

                            # restore boolean targets:
                            for obj in valid_objects:
                                if RBDLabNaming.FROM not in obj:
                                    continue

                                obj_for_boolean = bpy.data.objects[obj[RBDLabNaming.FROM]]

                                if RBDLabNaming.BOOLEAN_MOD in obj.modifiers:
                                    obj.modifiers[RBDLabNaming.BOOLEAN_MOD].object = obj_for_boolean

                                if RBDLabNaming.BOOLEAN_MOD_UP in obj.modifiers:
                                    obj.modifiers[RBDLabNaming.BOOLEAN_MOD_UP].object = obj_for_boolean

                            deselect_all_objects(context)


def octree_depth_update(self, context):
    rbdlab = context.scene.rbdlab

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

                        if rbdlab.remesh_or_subdivision == "Remesh":
                            condition = True
                        else:
                            condition = False
                    
                        if condition:
                            if coll_high_name in bpy.data.collections:
                                work_coll = coll_high_name
                            else:
                                work_coll = coll_name

                            for obj in bpy.data.collections[work_coll].objects:
                                if obj.type == 'MESH' and obj.visible_get():
                                    if RBDLabNaming.REMESH in obj.modifiers:
                                        obj.modifiers[RBDLabNaming.REMESH].octree_depth = self.octree_depth


def remesh_mode_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection:
        if RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]

            for target_coll in target_collections:
                coll_name = target_coll.name

                if coll_name:

                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    if rbdlab.remesh_or_subdivision == "Remesh":
                        condition = True
                    else:
                        condition = False
                
                    if condition:
                        if coll_high_name in bpy.data.collections:
                            work_coll = coll_high_name
                        else:
                            work_coll = coll_name

                        for obj in bpy.data.collections[work_coll].objects:
                            if obj.type == 'MESH' and obj.visible_get():
                                if RBDLabNaming.REMESH in obj.modifiers:
                                    obj.modifiers[RBDLabNaming.REMESH].mode = self.remesh_mode


def remesh_scale_update(self, context):
    rbdlab = context.scene.rbdlab

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

                        if rbdlab.remesh_or_subdivision == "Remesh":
                            condition = True
                        else:
                            condition = False
                    
                        if condition:
                            if coll_high_name in bpy.data.collections:
                                work_coll = coll_high_name
                            else:
                                work_coll = coll_name

                            for obj in bpy.data.collections[work_coll].objects:
                                if obj.type == 'MESH' and obj.visible_get():
                                    if RBDLabNaming.REMESH in obj.modifiers:
                                        obj.modifiers[RBDLabNaming.REMESH].scale = self.remesh_scale


def voxel_size_update(self, context):
    rbdlab = context.scene.rbdlab

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

                        if rbdlab.remesh_or_subdivision == "Remesh":
                            condition = True
                        else:
                            condition = False
                    
                        if condition:
                            if coll_high_name in bpy.data.collections:
                                work_coll = coll_high_name
                            else:
                                work_coll = coll_name

                            for obj in bpy.data.collections[work_coll].objects:
                                if obj.type == 'MESH' and obj.visible_get():
                                    if RBDLabNaming.REMESH in obj.modifiers:
                                        obj.modifiers[RBDLabNaming.REMESH].voxel_size = self.voxel_size


def remesh_voxel_adaptivity_update(self, context):
    rbdlab = context.scene.rbdlab

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

                        if rbdlab.remesh_or_subdivision == "Remesh":
                            condition = True
                        else:
                            condition = False
                    
                        if condition:
                            if coll_high_name in bpy.data.collections:
                                work_coll = coll_high_name
                            else:
                                work_coll = coll_name

                            for obj in bpy.data.collections[work_coll].objects:
                                if obj.type == 'MESH' and obj.visible_get():
                                    if RBDLabNaming.REMESH in obj.modifiers:
                                        obj.modifiers[RBDLabNaming.REMESH].adaptivity = self.remesh_voxel_adaptivity


def use_smooth_shade_update(self, context):
    rbdlab = context.scene.rbdlab

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

                        if rbdlab.remesh_or_subdivision == "Remesh":
                            condition = True
                        else:
                            condition = False
                    
                        if condition:
                            if coll_high_name in bpy.data.collections:
                                work_coll = coll_high_name
                            else:
                                work_coll = coll_name

                            for obj in bpy.data.collections[work_coll].objects:
                                if obj.type == 'MESH' and obj.visible_get():
                                    if RBDLabNaming.REMESH in obj.modifiers:
                                        obj.modifiers[RBDLabNaming.REMESH].use_smooth_shade = self.use_smooth_shade


def external_roughness_update(self, context):
    rbdlab = context.scene.rbdlab

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

                                if obj.type != 'MESH':
                                    continue

                                if not obj.visible_get():
                                    continue

                                if RBDLabNaming.BOOLEAN_MOD not in obj.modifiers:
                                    continue

                                if RBDLabNaming.BOOLEAN_MOD_UP not in obj.modifiers:
                                    continue

                                bool_mod = obj.modifiers[RBDLabNaming.BOOLEAN_MOD]
                                bool_mod_up = obj.modifiers[RBDLabNaming.BOOLEAN_MOD_UP]

                                if self.external_roughness:    
                                    bool_mod.show_viewport = False
                                    bool_mod.show_render = False
                                    bool_mod_up.show_viewport = True
                                    bool_mod_up.show_render = True
                                else:
                                    bool_mod.show_viewport = True
                                    bool_mod.show_render = True
                                    bool_mod_up.show_viewport = False
                                    bool_mod_up.show_render = False


def low_or_high_visibility_viewport_update(self, context):
    ui, tcoll_list = get_common_vars(context, get_ui=True, get_tcoll_list=True)
    tcoll = tcoll_list.active

    # deseleccionamos al cambiar la visualizacion entre lows y/o highs:
    item = tcoll_list.get_item_by_name(tcoll.name)
    item.select = False

    if ui.show_low_high_to_all_or_tc:
        # all rbdlab collections:
        collections = [coll for coll in bpy.data.collections if 'RBDLAB' in coll]
    else:
        # only tarfet collection:
        if tcoll:
            coll_name = tcoll.name
            if coll_name:
                collections = [tcoll]
    
    for coll in collections:
        if "use_highs" in coll:
            coll_name = coll.name

            is_in_local_view = len([area for area in context.screen.areas if area.type == 'VIEW_3D' and area.spaces[0].local_view]) > 0
            if is_in_local_view:
                bpy.ops.view3d.localview(frame_selected=False)

            view_mode = self.low_or_high_visibility_viewport
            coll_name_clean = coll_name.replace(RBDLabNaming.SUFIX_LOW, "")
            coll_name_low = coll_name_clean + RBDLabNaming.SUFIX_LOW
            coll_name_high = coll_name_clean + RBDLabNaming.SUFIX_HIGH

            if coll_name_high in bpy.data.collections:
                unhide_collection_in_viewport(context, coll_name_high)

            if coll_name_low in bpy.data.collections:
                unhide_collection_in_viewport(context, coll_name_low)

                low_valid_objects = [obj for obj in bpy.data.collections[coll_name_low].objects
                                     if obj.type == 'MESH' and "rbdlab_have_high" in obj]

                if view_mode == "High":
                    # si es high
                    if len(low_valid_objects) > 0:
                        for obj in low_valid_objects:

                            show_instancer_match = False
                            for ps in obj.particle_systems:
                                if "_motion_" in ps.name:
                                    obj.show_instancer_for_viewport = False
                                    show_instancer_match = True

                            if show_instancer_match:
                                # si tiene nuestras particulas
                                obj.hide_set(False)
                            else:
                                obj.hide_set(True)

                        # oculto la collection de los low
                        # hide_collection_in_viewport(context, coll_name)

                        # cuando visualizaba el high cambiaba el active collection, para evitarlo:
                        set_active_collection_to_master_coll(context)
                else:
                    if len(low_valid_objects) > 0:

                        show_instancer_match = False
                        for obj in low_valid_objects:
                            obj.hide_set(False)
                            for ps in obj.particle_systems:
                                if "_motion_" in ps.name:
                                    obj.show_instancer_for_viewport = True
                                    show_instancer_match = True

                    # oculto la collection de los highs
                    hide_collection_in_viewport(context, coll_name_high)

            deselect_all_objects(context)

            # respetando el isolate
            list_index = tcoll_list.list_index
            coll_list = tcoll_list.list
            coll_list[list_index].isolate = coll_list[list_index].isolate


def low_or_high_visibility_render_update(self, context):

    ui, tcoll_list = get_common_vars(context, get_ui=True, get_tcoll_list=True)
    tcoll = tcoll_list.active

    if ui.show_low_high_to_all_or_tc:
        # all rbdlab collections:
        collections = [coll for coll in bpy.data.collections if 'RBDLAB' in coll]
    else:
        # only target collection:
        if tcoll:
            coll_name = tcoll.name
            if coll_name:
                collections = [tcoll]

    for coll in collections:
        if "use_highs" in coll:
            coll_name = coll.name

            view_mode = self.low_or_high_visibility_render
            coll_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, "").replace(RBDLabNaming.SUFIX_HIGH, "")
            if coll_name not in bpy.data.collections:
                coll_name_low = coll_name + RBDLabNaming.SUFIX_LOW
            else:
                coll_name_low = coll_name

            coll_name_high = coll_name + RBDLabNaming.SUFIX_HIGH

            if coll_name_low in bpy.data.collections:

                low_valid_objects = [obj for obj in bpy.data.collections[coll_name_low].objects
                                     if obj.type == 'MESH' and "rbdlab_have_high" in obj]

                if view_mode == "High":
                    # si es high
                    bpy.data.collections[coll_name_low].hide_render = False
                    if coll_name_high in bpy.data.collections:
                        bpy.data.collections[coll_name_high].hide_render = False

                    # si es rojo lo desoculto y sino lo oculto y pongo hidden los emitters
                    if len(low_valid_objects) > 0:
                        for obj in low_valid_objects:
                            match = [(obj, setattr(obj, "show_instancer_for_render", False))
                                     for ps in obj.particle_systems if "_motion_" in ps.name]
                            if match:
                                # si tiene nuestras particulas
                                obj.hide_render = False
                            else:
                                obj.hide_render = True
                else:
                    # si es low:
                    if coll_name_high in bpy.data.collections:
                        bpy.data.collections[coll_name_high].hide_render = True

                    # desoculto todos los low y restauro los emitters
                    if len(low_valid_objects) > 0:
                        for obj in low_valid_objects:
                            obj.hide_render = False
                            [setattr(obj, "show_instancer_for_render", True)
                             for ps in obj.particle_systems if "_motion_" in ps.name]

            deselect_all_objects(context)


def rbdlab_cf_fast_exact_prefs_update(self, context):
    rbdlab = context.scene.rbdlab
    addon_preferences = RBDLabPreferences.get_prefs(context)
    rbdlab.rbdlab_cf_fast_exact = addon_preferences.rbdlab_cf_fast_exact_prefs


def rbdlab_cf_fast_exact_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.filtered_target_collection and RBDLabNaming.LAST_CREATED_COLLS in rbdlab.filtered_target_collection:
        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name

                if coll_name:

                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    for obj in bpy.data.collections[coll_name].objects:
                        if obj.type == 'MESH' and obj.visible_get():
                            if RBDLabNaming.BOOLEAN_MOD in obj.modifiers:
                                obj.modifiers[RBDLabNaming.BOOLEAN_MOD].solver = self.rbdlab_cf_fast_exact

                    if coll_high_name in bpy.data.collections:
                        for obj in bpy.data.collections[coll_high_name].objects:
                            if obj.type == 'MESH' and obj.visible_get():
                                if RBDLabNaming.BOOLEAN_MOD in obj.modifiers:
                                    obj.modifiers[RBDLabNaming.BOOLEAN_MOD].solver = self.rbdlab_cf_fast_exact
                                    obj.modifiers[RBDLabNaming.BOOLEAN_MOD_UP].solver = self.rbdlab_cf_fast_exact


def rbdlab_cf_wood_directions_update(self, context):
    rbdlab = context.scene.rbdlab

    if rbdlab.rbdlab_cf_wood_directions == 'XDIR':
        rbdlab.rbdlab_cf_cell_scale[0] = 0.03
        rbdlab.rbdlab_cf_cell_scale[1] = 1
        rbdlab.rbdlab_cf_cell_scale[2] = 1

    if rbdlab.rbdlab_cf_wood_directions == 'YDIR':
        rbdlab.rbdlab_cf_cell_scale[0] = 1
        rbdlab.rbdlab_cf_cell_scale[1] = 0.03
        rbdlab.rbdlab_cf_cell_scale[2] = 1

    if rbdlab.rbdlab_cf_wood_directions == 'ZDIR':
        rbdlab.rbdlab_cf_cell_scale[0] = 1
        rbdlab.rbdlab_cf_cell_scale[1] = 1
        rbdlab.rbdlab_cf_cell_scale[2] = 0.03

    if rbdlab.rbdlab_cf_wood_directions == 'NONE':
        rbdlab.rbdlab_cf_cell_scale[0] = 1
        rbdlab.rbdlab_cf_cell_scale[1] = 1
        rbdlab.rbdlab_cf_cell_scale[2] = 1


def scatter_geo_particle_size_update(self, context):
    rbdlab = context.scene.rbdlab
    # ps_name = RBDLabNaming.SECOND_SCATTER
    ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.settings.particle_size = rbdlab.scatter.scatter_geo_particle_size


def scatter_geo_size_random_update(self, context):
    rbdlab = context.scene.rbdlab
    # ps_name = RBDLabNaming.SECOND_SCATTER
    ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.settings.size_random = rbdlab.scatter.scatter_geo_size_random


def scatter_secondary_seed_update(self, context):
    rbdlab = context.scene.rbdlab
    ps_name = RBDLabNaming.SECOND_SCATTER
    # ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    i = 0
    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.seed = rbdlab.scatter_secondary_seed + i
            i += 1


def scatter_geo_seed_update(self, context):
    rbdlab = context.scene.rbdlab
    # ps_name = RBDLabNaming.SECOND_SCATTER
    ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    i = 0
    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.seed = rbdlab.scatter.scatter_geo_seed + i
                i = i+1


def scatter_geo_from_update(self, context):
    rbdlab = context.scene.rbdlab
    # ps_name = RBDLabNaming.SECOND_SCATTER
    ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.settings.emit_from = rbdlab.scatter.scatter_geo_from


def scatter_geo_count_update(self, context):
    rbdlab = context.scene.rbdlab
    # ps_name = RBDLabNaming.SECOND_SCATTER
    ps_name = "scatter_organic"

    valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]

    for obj in valid_objects:
        if len(obj.particle_systems) > 0:
            if ps_name in obj.particle_systems:
                ps = obj.particle_systems[ps_name]
                ps.settings.count = rbdlab.scatter.scatter_geo_count


def scatter_geo_child_count_update(self, context):
    rbdlab = context.scene.rbdlab
    for ps in bpy.data.particles:
        if ps.name.startswith("child_particles"):
            ps.count = rbdlab.scatter.scatter_geo_child_count


def scatter_geo_ps_child_size_update(self, context):
    rbdlab = context.scene.rbdlab
    for ps in bpy.data.particles:
        if ps.name.startswith("child_particles"):
            ps.display_size = rbdlab.scatter.scatter_geo_ps_child_size


def texture_particle_count_update(self, context):
    rbdlab = context.scene.rbdlab

    for obj in bpy.context.selected_objects:
        if "Scatter_by_Texture" in obj.modifiers:
            obj.particle_systems["Scatter_by_Texture"].settings.count = rbdlab.scatter.texture_particle_count


def isolate_or_not_update(self, context):
    rbdlab = context.scene.rbdlab

    original_selection = context.selected_objects
    original_active = context.active_object

    is_in_local_view = len([area for area in context.screen.areas if area.type == 'VIEW_3D' and area.spaces[0].local_view]) > 0

    bpy.ops.view3d.localview()
    if not is_in_local_view:
        if original_active.name not in original_selection and len(original_selection) > 0:

            # cuando entro en isolate

            active = original_selection[0]
            set_active_object(context, active)
            original_active = active

            original_active["rbdlab_remesh_settings"] = {
                "inner_subdivision": rbdlab.inner_subdivision,
                "remesh_or_subdivision": rbdlab.remesh_or_subdivision,
                "clouds_size": rbdlab.clouds_size,
                "depth_displace_texture": rbdlab.depth_displace_texture,
                "displace_strength": rbdlab.displace_strength,
                "remesh_mode": rbdlab.remesh_mode,
                "octree_depth": rbdlab.octree_depth,
                "remesh_scale": rbdlab.remesh_scale,
                "use_smooth_shade": rbdlab.use_smooth_shade,
                "external_roughness": rbdlab.external_roughness,
                "voxel_size": rbdlab.voxel_size,
                "remesh_voxel_adaptivity": rbdlab.remesh_voxel_adaptivity,
                "range_min": rbdlab.range_min,
                "range_max": rbdlab.range_max,
                "ratio": rbdlab.ratio,
                # "show_viewport": original_active.modifiers["RBDLab_Decimate_collapse"].show_viewport,
                # "show_render": original_active.modifiers["RBDLab_Decimate_collapse"].show_render,
                # laplacian smooth:
                "lapsmooth_toggle": rbdlab.lapsmooth_toggle,
                "iterations": rbdlab.iterations,
                "use_x": rbdlab.use_x,
                "use_y": rbdlab.use_y,
                "use_z": rbdlab.use_z,
                "lambda_factor": rbdlab.lambda_factor,
                "lambda_border": rbdlab.lambda_border,
                "use_volume_preserve": rbdlab.use_volume_preserve,
                "use_normalized": rbdlab.use_normalized,

            }

    else:

        # cuando salgo de isolate

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name
                if coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    if coll_high_name in bpy.data.collections:

                        changes = False
                        current_settings = {
                            "inner_subdivision": rbdlab.inner_subdivision,
                            "remesh_or_subdivision": rbdlab.remesh_or_subdivision,
                            "clouds_size": rbdlab.clouds_size,
                            "depth_displace_texture": rbdlab.depth_displace_texture,
                            "displace_strength": rbdlab.displace_strength,
                            "remesh_mode": rbdlab.remesh_mode,
                            "octree_depth": rbdlab.octree_depth,
                            "remesh_scale": rbdlab.remesh_scale,
                            "use_smooth_shade": rbdlab.use_smooth_shade,
                            "external_roughness": rbdlab.external_roughness,
                            "voxel_size": rbdlab.voxel_size,
                            "remesh_voxel_adaptivity": rbdlab.remesh_voxel_adaptivity,
                            "range_min": rbdlab.range_min,
                            "range_max": rbdlab.range_max,
                            "ratio": rbdlab.ratio,
                            # "show_viewport": original_active.modifiers["RBDLab_Decimate_collapse"].show_viewport,
                            # "show_render": original_active.modifiers["RBDLab_Decimate_collapse"].show_render,
                            # laplacian smooth:
                            "lapsmooth_toggle": rbdlab.lapsmooth_toggle,
                            "iterations": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].iterations,
                            "use_x": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].use_x,
                            "use_y": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].use_y,
                            "use_z": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].use_z,
                            "lambda_factor": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].lambda_factor,
                            "lambda_border": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].lambda_border,
                            "use_volume_preserve": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].use_volume_preserve,
                            "use_normalized": original_active.modifiers[RBDLabNaming.LAPLACIAN_MOD].use_normalized,
                        }

                        if original_active.name not in original_selection and len(original_selection) > 0:
                            active = original_selection[0]
                            set_active_object(context, active)
                            original_active = active

                        if "rbdlab_remesh_settings" in original_active:
                            for old_key, old_vaue in original_active["rbdlab_remesh_settings"].items():
                                if current_settings[old_key] != old_vaue:
                                    changes = True

                        if changes:
                            # print("si hay cambios!")
                            [select_object(context, obj) for obj in original_selection]
                            set_active_object(context, original_active)

                            # bpy.ops.object.select_all(action='SELECT')
                            target_modifiers = [RBDLabNaming.SUBSURF_MOD, RBDLabNaming.REMESH,
                                                RBDLabNaming.DISPLACE, "RBDLab_Decimate_collapse", RBDLabNaming.LAPLACIAN_MOD]
                            [select_object(context, obj) for obj in bpy.data.collections[coll_high_name].objects
                             if obj.name != original_active.name]

                            if original_active and len(bpy.context.selected_objects) > 0 and len(target_modifiers) > 0:
                                for obj in bpy.context.selected_objects:
                                    # print("obj.name", obj.name)
                                    for old_modifier in original_active.modifiers:
                                        if old_modifier.name in target_modifiers:
                                            generic_copy(old_modifier, obj.modifiers[old_modifier.name])

    deselect_all_objects(context)
    # restore original selection
    [select_object(context, obj) for obj in original_selection]
    set_active_object(context, original_active)


def depth_displace_texture_update(self, context):
    rbdlab = context.scene.rbdlab
    target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
    if target_collections:
        for target_coll in target_collections:
            coll_name = target_coll.name
            if coll_name:
                coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                if coll_high_name in bpy.data.collections:
                    work_coll = coll_high_name + "_Clouds"
                else:
                    work_coll = coll_name + "_Clouds"

                if work_coll in bpy.data.textures:
                    bpy.data.textures[work_coll].noise_depth = self.depth_displace_texture


def ground_x_update(self, context):
    grounds = [obj for obj in context.scene.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    if grounds:
        ground = grounds[0]
        ground.scale.x = self.ground_x


def ground_y_update(self, context):
    grounds = [obj for obj in context.scene.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    if grounds:
        ground = grounds[0]
        ground.scale.y = self.ground_y


def show_hide_ground_update(self, context):
    grounds = [obj for obj in context.scene.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    if grounds:
        ground = grounds[0]
        ground.hide_set(not ground.hide_get())


def show_wire_ground_update(self, context):
    grounds = [obj for obj in context.scene.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    if grounds:
        ground = grounds[0]

        if ground.display_type == 'TEXTURED':
            ground.display_type = 'WIRE'
        elif ground.display_type == 'WIRE':
            ground.display_type = 'TEXTURED'


def selectable_ground_update(self, context):
    grounds = [obj for obj in context.scene.objects if obj.name.startswith(RBDLabNaming.GROUND)]
    if grounds:
        ground = grounds[0]
        ground.hide_select = not self.selectable_ground


def stats_on(self, context):
    addon_preferences = RBDLabPreferences.get_prefs(context)
    # print(RBDLabPaths.ROOT)
    # RBDLabPaths.ROOT = __package__
    # RBDLabPaths.ROOT = "RBDLab"
    # print(RBDLabPaths.ROOT)

    # sobreescribir el contexto:
    def callback(area:Area) -> None:
        area = context.area  # Accedemos al área desde el contexto
        for space in area.spaces:
            if hasattr(space, "overlay"):
                if hasattr(space.overlay, "show_stats"):
                    space.overlay.show_stats = addon_preferences.show_statistics
        area.tag_redraw()
    context_override(context=context, area_type='VIEW_3D', callback=callback)
    