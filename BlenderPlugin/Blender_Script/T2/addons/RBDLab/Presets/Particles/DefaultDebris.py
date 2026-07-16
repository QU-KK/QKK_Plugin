import bpy

context = bpy.context
rbdlab = context.scene.rbdlab

rbdlab.particles.debris.display_method = 'RENDER'
rbdlab.particles.debris.display_size = 0.10000000149011612
rbdlab.particles.debris.display_color = 'MATERIAL'
rbdlab.particles.debris.show_instancer_for_viewport = True
rbdlab.particles.debris.count = 20
rbdlab.particles.debris.offset = 0
rbdlab.particles.debris.enable_end_trails = False
rbdlab.particles.debris.end_trails = 10
rbdlab.particles.debris.lifetime = 250.0
rbdlab.particles.debris.lifetime_random = 0.0
rbdlab.particles.debris.particle_size = 0.20000000298023224
rbdlab.particles.debris.size_random = 1.0
rbdlab.particles.debris.use_dead = False
rbdlab.particles.debris.show_instancer_for_render = False
rbdlab.particles.debris.normal = 0.5
rbdlab.particles.debris.direction = (0.0, 0.0, 0.0)
rbdlab.particles.debris.object_velocity = 0.0
rbdlab.particles.debris.velocity_randomize = 2.0
rbdlab.particles.debris.use_rotations = True
rbdlab.particles.debris.use_rotations = True
rbdlab.particles.debris.rotation_mode = 'VEL'
rbdlab.particles.debris.rotation_factor_random = 1.0
rbdlab.particles.debris.phase_factor = 0.0
rbdlab.particles.debris.phase_factor_random = 0.0
rbdlab.particles.debris.use_dynamic_rotation = False
if "Debris_Basics" in bpy.data.collections:
    rbdlab.particles.debris.debris_coll = bpy.data.collections["Debris_Basics"]
rbdlab.particles.debris.all = 1.0
rbdlab.particles.debris.gravity = 1.0
rbdlab.particles.debris.force = 1.0
rbdlab.particles.debris.vortex = 1.0
rbdlab.particles.debris.magnetic = 1.0
rbdlab.particles.debris.harmonic = 1.0
rbdlab.particles.debris.charge = 1.0
rbdlab.particles.debris.lennardjones = 1.0
rbdlab.particles.debris.wind = 1.0
rbdlab.particles.debris.curve_guide = 1.0
rbdlab.particles.debris.texture = 1.0
rbdlab.particles.debris.smokeflow = 1.0
rbdlab.particles.debris.turbulence = 1.0
rbdlab.particles.debris.drag = 1.0
rbdlab.particles.debris.boid = 1.0
rbdlab.particles.debris.basic_subdivision_type = 'SIMPLE'
rbdlab.particles.debris.basic_subdivision_level = 0
rbdlab.particles.debris.basic_decimate_collapse = 1.0
rbdlab.particles.debris.basic_disp_strength = 0.0
rbdlab.particles.debris.basic_clouds_size = 0.25
rbdlab.particles.debris.basic_clouds_depth = 2
rbdlab.particles.debris.basic_outher_material = "BasicDebris_Outer_mat"
rbdlab.particles.debris.basic_inner_material = "BasicDebris_Inner_mat"

if context.preferences.addons["RBDLab"].preferences.autto_apply_preset:
    bpy.ops.rbdlab.particles_update(type="debris")
