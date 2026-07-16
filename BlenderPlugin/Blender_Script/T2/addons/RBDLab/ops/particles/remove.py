
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from ...Global.functions import (
    deselect_all_objects,
    select_object,
    set_active_object,
    remove_all_keyframes_in_action
)
from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming


class RBDLAB_OT_particles_remove(Operator):
    bl_idname = "rbdlab.particles_remove"
    bl_label = "Remove Particles"

    type: EnumProperty(name="Particle type",
                       items=(
                           ("debris", "Debris", ""),
                           ("dust", "Dust", ""),
                           ("smoke", "Smoke", "")
                       ),
                       default="debris")

    particles_systems_names = ("particles_debris", "particles_dust", "particles_smoke")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Remove %s particles" % properties.type

    def get_childrens(self, rbdlab, obj):
        return [ob for ob in rbdlab.filtered_target_collection.objects if ob.parent == obj]

    def rm_inners_without_particle_systems(self, rbdlab, chunks: list = []) -> None:

        # limpieza de inners sin particulas
        for ob in chunks:
            if ob.type != 'MESH':
                continue
            if not ob.visible_get():
                continue
            if ob.name == RBDLabNaming.GROUND:
                continue
            if RBDLabNaming.SUFIX_BBOX in ob.name:
                continue
            if RBDLabNaming.PASSIVE in ob:
                continue

            if RBDLabNaming.INNER_EMISOR in ob or RBDLabNaming.INNER_CHUNK in ob:
                if len(ob.particle_systems) == 0:

                    father = ob.parent
                    if father:

                        if RBDLabNaming.CHUNK_PART_CHILD in father:
                            del father[RBDLabNaming.CHUNK_PART_CHILD]

                        if RBDLabNaming.EXTRACTION_ID in father:
                            del father[RBDLabNaming.EXTRACTION_ID]

                        if RBDLabNaming.CHUNK_EXTRACTED in father:
                            # print(father.name + " Quitando propiedad:", RBDLabNaming.CHUNK_EXTRACTED)
                            del father[RBDLabNaming.CHUNK_EXTRACTED]

                    bpy.data.objects.remove(ob, do_unlink=True, do_id_user=True, do_ui_user=True)

    def execute(self, context):
        # start = datetime.now()
        rbdlab = context.scene.rbdlab
        addon_preferences = RBDLabPreferences.get_prefs(context)

        color_p_emiter = list(addon_preferences.color_p_emiter)

        if not rbdlab.has_particles(self.type):
            self.report({'WARNING'}, "Current collection doesn't have %s particles!" % self.type)
            return {'CANCELLED'}

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name

            if not coll_name:
                self.report({'WARNING'}, "Target collection is empty!")
                return {'CANCELLED'}

            ps_name = coll_name + "_" + self.type

            if not ps_name:
                self.report({'WARNING'}, "Not particle sistem name avalidable!")
                return {'CANCELLED'}

            if "particles_" + self.type in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["particles_" + self.type]

            if "particles_" + self.type + "_render" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["particles_" + self.type + "_render"]

            if "particles_" + self.type + "_viewport" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["particles_" + self.type + "_viewport"]

            properties_coll = list(rbdlab.filtered_target_collection.keys())
            have_any_ps_created = [item for item in properties_coll if item in self.particles_systems_names]

            blender_version = bpy.app.version

            valid_objects = [ob for ob in rbdlab.filtered_target_collection.objects if ob.type == 'MESH' and ob.visible_get()]  # and len(ob.particle_systems) > 0

            tcoll = rbdlab.filtered_target_collection
            has_motions = RBDLabNaming.HAS_MOTIONS in tcoll
            has_broken = RBDLabNaming.HAS_BROKEN in tcoll

            if has_motions:
                del tcoll[RBDLabNaming.HAS_MOTIONS]
            if has_broken:
                del tcoll[RBDLabNaming.HAS_BROKEN]

            # print("********* valid_objects", valid_objects)

            for ob in valid_objects:

                # Clear and reset Broken and Motion from chunk...
                rbdlab_ob = ob.rbdlab
                rbdlab_ob.clear_motions()
                rbdlab_ob.ok_distance_threshold = False
                rbdlab_ob.broken_at_frame = -1
                
                if "broken_state" in ob:
                    del ob["broken_state"]
                
                if "broken_at_frame" in ob:
                    del ob["broken_at_frame"]

                # Borramos también de la ui los motions_x para no crear confusiones.
                cp_motions_to_remove = [cp for cp in ob.keys() if cp.startswith("motion_")]
                for cp in cp_motions_to_remove:
                    del ob[cp]
                
                if "has_motions" in ob:
                    del ob["has_motions"]

                if len(ob.particle_systems) == 0:
                    continue

                set_active_object(context, ob)
                select_object(context, ob)

                # elimino el fstart y fend "del current type" (almacenados para el end trails):
                fstart_key = RBDLabNaming.PART_FSTART + "_" + self.type
                if fstart_key in ob:
                    del ob[fstart_key]

                fend_key = RBDLabNaming.PART_FEND + "_" + self.type
                if fend_key in ob:
                    del ob[fend_key]

                # elilmino las velocidades guardadas de los chunks
                if not have_any_ps_created:
                    if RBDLabNaming.VELOCITIES in ob:
                        del ob[RBDLabNaming.VELOCITIES]

                # if "rbdlab_motions" in ob:
                #     del ob["rbdlab_motions"]

                if "rbdlab_mute_particles_" + self.type in ob:
                    del ob["rbdlab_mute_particles_" + self.type]

                if blender_version[0] >= 3:
                    # for blender 3:
                    for mod in ob.modifiers:
                        mod_name = mod.name.lower()

                        if not mod_name.startswith(ps_name.lower()):
                            continue

                        ob.modifiers.remove(mod)
                else:
                    # for blender 2:
                    for mod in ob.modifiers:
                        mod_name = mod.name.lower()
                        if not mod_name.startswith(ps_name.lower()):
                            continue

                        match = False
                        i = 0
                        idx = -1
                        while not match and i < len(ob.particle_systems):
                            if ob.particle_systems[i].name.startswith(ps_name):
                                idx = i
                                match = True
                            i += 1
                        if idx >= 0:
                            ob.particle_systems.active_index = idx
                            ob.modifiers.remove(mod)

            deselect_all_objects(context)

            # reseteo cada vez que borramos:
            # si no quedan sistemas de particulas osea cuando se restaura el color reseteamos
            # para que se vuelva a calcular las velocities

            if len(have_any_ps_created) == 0:
                if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection[RBDLabNaming.CMPUTD_VELOCITIES]

                for ob in valid_objects:

                    all_colors = ob.color_stack.get_all_colors()
                    if all_colors:
                        if len(all_colors) > 1:
                            ob.color_stack.rm_last_color()

                    color = ob.color_stack.get_last_color()
                    if color:
                        remove_all_keyframes_in_action(context, ob, "color")
                        ob.color = color

                    if ob.parent:
                        ob.parent.color_stack.rm_color(color_p_emiter)
                        color = None
                        color = ob.parent.color_stack.get_last_color()
                        if color:
                            remove_all_keyframes_in_action(context, ob.parent, "color")
                            ob.parent.color = color

                    RBDLabNaming.EXTRACTION_ID

                    # propiedad para solo guardar un color en el stack:
                    if RBDLabNaming.PART_COLOR_ADDED in ob:
                        del ob[RBDLabNaming.PART_COLOR_ADDED]

            ps_name_control = "particles_" + self.type
            if ps_name_control in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection[ps_name_control]

            # restauramos color:
            inners_objects = [ob for ob in rbdlab.filtered_target_collection.objects if RBDLabNaming.INNER_CHUNK in ob and len(ob.particle_systems) > 0]
            if len(inners_objects) == 0:

                for ob in valid_objects:
                    if RBDLabNaming.INNER_EMISOR in ob:
                        del ob[RBDLabNaming.INNER_EMISOR]

                if RBDLabNaming.PART_COLLISION in rbdlab.filtered_target_collection:
                    bpy.ops.rbdlab.p_collision_remove(type="low")

                if "collision_high" in rbdlab.filtered_target_collection:
                    bpy.ops.rbdlab.p_collision_remove(type="high")

                # elimino las velocities y los motions:
                chunks = [ob for ob in rbdlab.filtered_target_collection.objects if ob.type == 'MESH' and ob.visible_get()]

                have_motions = []
                for ob in chunks:
                    if "rbdlab_motions" in ob:
                        have_motions.append(ob)
                        del ob["rbdlab_motions"]
                    if RBDLabNaming.VELOCITIES in ob:
                        del ob[RBDLabNaming.VELOCITIES]

                if len(have_motions) > 0:
                    if "computed_motions" in rbdlab.filtered_target_collection:
                        del rbdlab.filtered_target_collection["computed_motions"]

            objects = rbdlab.filtered_target_collection.objects
            self.rm_inners_without_particle_systems(rbdlab, objects)

            # al borrar las particulas digo q se fuerce el force_update_broken_motion:
            # rbdlab.particles.debris.create.force_update_broken_motion = True

            deselect_all_objects(context)

            if RBDLabNaming.COLL_WITH_PARTICLES in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection[RBDLabNaming.COLL_WITH_PARTICLES]

            # print("remove modifiers particles " + str(datetime.now() - start))
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}
