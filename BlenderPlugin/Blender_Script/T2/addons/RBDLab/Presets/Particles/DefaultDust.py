import bpy

context = bpy.context
rbdlab = context.scene.rbdlab

rbdlab.particles.dust.display_method = 'RENDER'
rbdlab.particles.dust.display_size = 0.10000000149011612
rbdlab.particles.debris.display_color = 'MATERIAL'
rbdlab.particles.dust.show_instancer_for_viewport = True
rbdlab.particles.dust.count = 20
rbdlab.particles.dust.offset = 0
rbdlab.particles.dust.enable_end_trails = False
rbdlab.particles.dust.end_trails = 10
rbdlab.particles.dust.lifetime = 250.0
rbdlab.particles.dust.lifetime_random = 0.0
rbdlab.particles.dust.particle_size = 0.20000000298023224
rbdlab.particles.dust.size_random = 1.0
rbdlab.particles.dust.use_dead = False
rbdlab.particles.dust.show_instancer_for_render = False
rbdlab.particles.dust.normal = 0.5
rbdlab.particles.dust.direction = (0.0, 0.0, 0.0)
rbdlab.particles.dust.object_velocity = 0.0
rbdlab.particles.dust.velocity_randomize = 2.0
rbdlab.particles.dust.use_rotations = True
rbdlab.particles.dust.use_rotations = True
rbdlab.particles.dust.rotation_mode = 'VEL'
rbdlab.particles.dust.rotation_factor_random = 1.0
rbdlab.particles.dust.phase_factor = 0.0
rbdlab.particles.dust.phase_factor_random = 0.0
rbdlab.particles.dust.use_dynamic_rotation = False
if "Debris_Basics" in bpy.data.collections:
    rbdlab.particles.dust.dust_coll = bpy.data.collections["Debris_Basics"]
rbdlab.particles.dust.all = 1.0
rbdlab.particles.dust.gravity = 1.0
rbdlab.particles.dust.force = 1.0
rbdlab.particles.dust.vortex = 1.0
rbdlab.particles.dust.magnetic = 1.0
rbdlab.particles.dust.harmonic = 1.0
rbdlab.particles.dust.charge = 1.0
rbdlab.particles.dust.lennardjones = 1.0
rbdlab.particles.dust.wind = 1.0
rbdlab.particles.dust.curve_guide = 1.0
rbdlab.particles.dust.texture = 1.0
rbdlab.particles.dust.smokeflow = 1.0
rbdlab.particles.dust.turbulence = 1.0
rbdlab.particles.dust.drag = 1.0
rbdlab.particles.dust.boid = 1.0
rbdlab.particles.dust.basic_subdivision_type = 'SIMPLE'
rbdlab.particles.dust.basic_subdivision_level = 0
rbdlab.particles.dust.basic_decimate_collapse = 1.0
rbdlab.particles.dust.basic_disp_strength = 0.0
rbdlab.particles.dust.basic_clouds_size = 0.25
rbdlab.particles.dust.basic_clouds_depth = 2
rbdlab.particles.dust.basic_outher_material = "Basicdust_Outer_mat"
rbdlab.particles.dust.basic_inner_material = "Basicdust_Inner_mat"

if context.preferences.addons["RBDLab"].preferences.autto_apply_preset:
    bpy.ops.rbdlab.particles_update(type="dust")
