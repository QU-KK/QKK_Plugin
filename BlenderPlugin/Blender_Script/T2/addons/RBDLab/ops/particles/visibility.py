import bpy
from bpy.types import Operator
from bpy.props import EnumProperty


class RBDLAB_OT_particles_visibility(Operator):
    bl_idname = "rbdlab.particles_visibility"
    bl_label = "Visibility Particle"

    type: EnumProperty(name="Particle type",
                       items=(
                            ("debris", "Debris", ""),
                            ("dust", "Dust", ""),
                            ("smoke", "Smoke", "")
                       ),
                       default="debris")

    visibility_particle_type: EnumProperty(name="Visibility particle type",
                                           items=(
                                               ('VIEWPORT', "Viewport", ""),
                                               ('RENDER', "Render", ""),
                                           ),
                                           default='VIEWPORT')

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "%s visibility particles" % properties.type

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if not rbdlab.has_particles(self.type):
            self.report(
                {'WARNING'}, "Current collection does not have %s particles!" % self.type)
            return {'CANCELLED'}

        coll_name = rbdlab.filtered_target_collection.name
        if not coll_name:
            return {'CANCELLED'}

        ps_name = coll_name + "_" + self.type

        valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                         if obj.type == 'MESH' and obj.visible_get()]

        # que no tenga ningun mute para no hacerles toggle
        #blacklist_props = ["rbdlab_mute_particles_debris", "rbdlab_mute_particles_dust", "rbdlab_mute_particles_smoke"]

        # para todos los chunks validos:
        for obj in valid_objects:
            obj_muted = False

            # si es un chunk muteado lo skipeo:
            custom_properties = list(obj.keys())
            for cp in custom_properties:
                if cp == "rbdlab_mute_particles_" + self.type:
                    obj_muted = True

            if obj_muted:
                continue

            # para todos los modifiers de particulas:
            for ps_modifier in obj.modifiers:

                # si no es del tipo deseado lo skipeo:
                if not ps_modifier.name.startswith(ps_name):
                    continue

                n_v_status = not ps_modifier.show_viewport
                n_r_status = not ps_modifier.show_render

                if self.visibility_particle_type == 'VIEWPORT':
                    ps_modifier.show_viewport = n_v_status
                    rbdlab.set_particles_visibility(
                        self.type, self.visibility_particle_type, n_v_status)

                elif self.visibility_particle_type == 'RENDER':
                    ps_modifier.show_render = n_r_status
                    rbdlab.set_particles_visibility(
                        self.type, self.visibility_particle_type, n_r_status)

        return {'FINISHED'}
