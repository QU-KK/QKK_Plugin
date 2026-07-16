import bpy

context = bpy.context
rbdlab = context.scene.rbdlab

rbdlab.particles.smoke.display_method = 'RENDER'
rbdlab.particles.smoke.display_size = 0.10000000149011612
rbdlab.particles.debris.display_color = 'MATERIAL'
rbdlab.particles.smoke.count = 20
rbdlab.particles.smoke.offset = 0
rbdlab.particles.smoke.enable_end_trails = False
rbdlab.particles.smoke.end_trails = 10
rbdlab.particles.smoke.lifetime = 250.0
rbdlab.particles.smoke.lifetime_random = 0.0
rbdlab.particles.smoke.normal = 0.5
rbdlab.particles.smoke.direction = (0.0, 0.0, 0.0)
rbdlab.particles.smoke.object_velocity = 0.0
rbdlab.particles.smoke.velocity_randomize = 2.0
rbdlab.particles.smoke.all = 1.0
rbdlab.particles.smoke.gravity = 1.0
rbdlab.particles.smoke.force = 1.0
rbdlab.particles.smoke.vortex = 1.0
rbdlab.particles.smoke.magnetic = 1.0
rbdlab.particles.smoke.harmonic = 1.0
rbdlab.particles.smoke.charge = 1.0
rbdlab.particles.smoke.lennardjones = 1.0
rbdlab.particles.smoke.wind = 1.0
rbdlab.particles.smoke.curve_guide = 1.0
rbdlab.particles.smoke.texture = 1.0
rbdlab.particles.smoke.smokeflow = 1.0
rbdlab.particles.smoke.turbulence = 1.0
rbdlab.particles.smoke.drag = 1.0
rbdlab.particles.smoke.boid = 1.0

if context.preferences.addons["RBDLab"].preferences.autto_apply_preset:
    bpy.ops.rbdlab.particles_update(type="smoke")
