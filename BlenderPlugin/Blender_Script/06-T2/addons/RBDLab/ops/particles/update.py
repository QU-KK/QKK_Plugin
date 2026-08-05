import bpy
import ast
from datetime import datetime
from ...Global.functions import (
    deselect_all_objects,
)
from bpy.types import Operator
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming
from ..smoke.smoke_common import get_frames_and_speeds, anim_smoke_mod_density, anim_smoke_mod_fuel


class RBDLAB_OT_particles_update(Operator):
    bl_idname = "rbdlab.particles_update"
    bl_label = "Update Particles"

    type: EnumProperty(name="Particle type",
                       items=(
                           ("debris", "Debris", ""),
                           ("dust", "Dust", ""),
                           ("smoke", "Smoke", "")
                       ),
                       default="debris")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Update %s particles" % properties.type

    def execute(self, context):
        start = datetime.now()
        rbdlab = context.scene.rbdlab
        ps_props = rbdlab.get_particles_properties(self.type)
        magic_bias = 0.002  # for fix particles apear in blender collision

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not rbdlab.has_particles(self.type):
            self.report({'WARNING'}, "Current collection doesn't have %s particles!" % self.type)
            return {'CANCELLED'}

        if tcoll is None:
            self.report({'WARNING'}, "Target collection is empty!")
            return {'CANCELLED'}

        # ps_name = tcoll.name + "_" + self.type

        deselect_all_objects(context)

        ps_list = [(ps, ob) for ob in chunks
                   for ps in ob.particle_systems
                   if hasattr(ps, "name") and self.type in ps.name]

        domain = rbdlab.get_smoke_domain(context)

        # print(ps_list)
        if ps_list:
            for ps, ob in ps_list:
                settings = ps.settings

                # End Trails y Frame Offse #######################################################

                if ps.name in ob:

                    fstart_fend: dict = ob[ps.name]
                    frame_start, frame_end = fstart_fend["frame_start"], fstart_fend["frame_end"]

                    # si se usa end trails:
                    if ps_props.enable_end_trails:
                        settings.frame_start = frame_start
                        settings.frame_end = frame_start + ps_props.end_trails

                        # si se usa offset con end trails:
                        if ps_props.frame_offset != 0:
                            settings.frame_start = settings.frame_start + ps_props.frame_offset
                            settings.frame_end = settings.frame_end + ps_props.frame_offset

                        # almacenamos el end trails:
                        ob[RBDLabNaming.END_TRAILS] = ps_props.end_trails
                    else:
                        # si no se usa end Trails:
                        settings.frame_start = frame_start
                        settings.frame_end = frame_end

                        # si no se usa end trails pero si se usa offset:
                        if ps_props.frame_offset != 0:
                            settings.frame_start = settings.frame_start + ps_props.frame_offset
                            settings.frame_end = settings.frame_end + ps_props.frame_offset
                        else:
                            settings.frame_start = frame_start
                            settings.frame_end = frame_end

                    ob["rbdlab_ps_enable_trails"] = ps_props.enable_end_trails

                # End Frame Offsey y End Trails ####################################################

                settings.display_method = ps_props.display_method

                settings.display_size = ps_props.display_size

                settings.display_color = ps_props.display_color
                settings.count = ps_props.count
                settings.count = ps_props.count
                settings.lifetime = ps_props.lifetime
                settings.lifetime_random = ps_props.lifetime_random

                # ahora manejamos el display_size y el particle_size desde el mismo input "el display_size":
                # ps.settings.particle_size = ps_props.particle_size
                settings.particle_size = ps_props.display_size
                settings.size_random = ps_props.size_random

                if self.type != "smoke":
                    settings.use_dead = ps_props.use_dead

                settings.use_rotations = ps_props.use_rotation
                settings.phase_factor_random = ps_props.random_phase
                if ps_props.dynamic:
                    if hasattr(settings, "use_dynamic_rotation"):
                        settings.use_dynamic_rotation = ps_props.dynamic
                if ps_props.debris_coll:
                    settings.instance_collection = ps_props.debris_coll
                settings.normal_factor = ps_props.normal
                settings.object_align_factor = ps_props.direction
                settings.object_factor = ps_props.object_velocity
                settings.factor_random = ps_props.velocity_randomize

                if self.type != "smoke":
                    settings.use_multiply_size_mass = ps_props.use_multiply_size_mass

                settings.timestep = ps_props.timestep
                settings.subframes = ps_props.subframes

                settings.use_rotations = ps_props.use_rotations
                settings.rotation_mode = ps_props.rotation_mode
                settings.rotation_factor_random = ps_props.rotation_factor_random
                settings.phase_factor = ps_props.phase_factor
                settings.phase_factor_random = ps_props.phase_factor_random
                settings.use_dynamic_rotation = ps_props.use_dynamic_rotation

                # Field Weights ######################################
                effector_weights_collection = rbdlab.particles.debris.effector_weights_collection
                settings.effector_weights.collection = effector_weights_collection

                settings.effector_weights.all = ps_props.all
                settings.effector_weights.gravity = ps_props.gravity
                settings.effector_weights.force = ps_props.force
                settings.effector_weights.vortex = ps_props.vortex
                settings.effector_weights.magnetic = ps_props.magnetic
                settings.effector_weights.harmonic = ps_props.harmonic
                settings.effector_weights.charge = ps_props.charge
                settings.effector_weights.lennardjones = ps_props.lennardjones
                settings.effector_weights.wind = ps_props.wind
                settings.effector_weights.curve_guide = ps_props.curve_guide
                settings.effector_weights.texture = ps_props.texture
                settings.effector_weights.smokeflow = ps_props.smokeflow
                settings.effector_weights.turbulence = ps_props.turbulence
                settings.effector_weights.drag = ps_props.drag
                settings.effector_weights.boid = ps_props.boid

                if self.type != "smoke":
                    ob.show_instancer_for_viewport = ps_props.show_instancer_for_viewport
                    ob.show_instancer_for_render = ps_props.show_instancer_for_render

                if self.type == "smoke":
                    ob[RBDLabNaming.SMOKE_FRAME_OFFSET] = ps_props.frame_offset

                    # si existe domain tengo que moverle sus keyframes del Fuel y el Density con el offset:
                    if domain:
                        if RBDLabNaming.SMOKE_MOD in ob.modifiers:
                            smoke_mod = ob.modifiers.get(RBDLabNaming.SMOKE_MOD)
                            if smoke_mod:
                                # necesito todos los frames y todos los speeds en 2 listados:
                                obj_all_frames, obj_all_speeds = get_frames_and_speeds(ob)
                                #################################################################################################
                                # Density
                                #################################################################################################
                                anim_smoke_mod_density(context, rbdlab, ob, smoke_mod,
                                                       obj_all_frames, obj_all_speeds, True)

                                #################################################################################################
                                # Fuel
                                #################################################################################################
                                anim_smoke_mod_fuel(context, rbdlab, ob, smoke_mod,
                                                    obj_all_frames, obj_all_speeds, True)

                # End Frame Offset ########################################################

            print("update particles " + str(datetime.now() - start))
            context.scene.frame_set(context.scene.frame_start)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}
