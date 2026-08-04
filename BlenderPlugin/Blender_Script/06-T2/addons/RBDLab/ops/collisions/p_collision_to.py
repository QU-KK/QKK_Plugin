import bpy
from typing import List
from ...Global.functions import (
    copy_modifier_by_name_from_active_to_selected
    # get_array_data_from_obj
)
from ...Global.basics import set_active_object, deselect_all_objects
# from ...addon.paths import RBDLabPreferences
from bpy.types import Operator, Object
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming
from datetime import datetime


class RBDLAB_OT_p_collisions_to(Operator):
    bl_idname = "rbdlab.p_collision_to"
    bl_label = "Create Particle Collision"
    bl_options = {'REGISTER', 'UNDO'}

    collision_type: EnumProperty(
        name="",
        items=(('SELECTION', "Selection", "", 0), ('COLLECTION', "Collection", "", 1))
    )

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Create collisions to %s" % properties.collision_type

    def check_if_exist_domain(self, context):
        scene = context.scene
        rbdlab = scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            domain_name = RBDLabNaming.DOMAIN_NAME

            have_fluids = [ob for ob in rbdlab.filtered_target_collection.objects
                           if RBDLabNaming.SMOKE_MOD in ob.modifiers]

            if domain_name in context.scene.objects or len(have_fluids) > 0:
                domain = bpy.data.objects.get(RBDLabNaming.DOMAIN_NAME)

                if domain:
                    return domain
                else:
                    print("I did not find the domain!")
                    return False
        else:
            return False

    def inser_keyframes(self, context, rbdlab, ob, collision_on: int = 0, collision_off: int = 1) -> None:

        damping_collision_off = 0
        damping_collision_on = rbdlab.collision.damping_factor

        ######################################################################################
        # si se esta usando el Use End Trails
        # entonces vemos de los sistemas de particulas cuales son
        # sus start end para setearlos con esa informacion:

        # NOTA: No debo usar el movimiento sin mas, asi que usare los settings de las particulas
        # Estas ya fueron calculadas con sus frame_start y frame_end con sus motions y brokens del usuario                 
        childs = None
        if RBDLabNaming.CHUNK_PART_CHILD in ob:
            childs = ob[RBDLabNaming.CHUNK_PART_CHILD]
        
        if childs:

            for child in childs:
                
                if child.name not in context.view_layer.objects:
                    continue
            
                if len(child.particle_systems) > 0:

                    frame_start = min([ps.settings.frame_start for ps in child.particle_systems])
                    frame_end = max([ps.settings.frame_end for ps in child.particle_systems])

                    # Fin use end Trails #################################################################

                    # pre start frame collision on:
                    pre_frame_start = frame_start - 1
                    pre_frame_end = frame_end - 1
    
                    # ahora animamos el ojito en lugar del damping y el permeability:
                    ob.collision.use = False
                    ob.keyframe_insert(
                        data_path="collision.use",
                        frame=(frame_start)
                    )
                    ob.collision.use = False
                    ob.keyframe_insert(
                        data_path="collision.use",
                        frame=(pre_frame_end)
                    )
                    ob.collision.use = True
                    ob.keyframe_insert(
                        data_path="collision.use",
                        frame=(frame_end)
                    )

                    # ob.collision.permeability = collision_on
                    # ob.keyframe_insert(
                    #     data_path="collision.permeability",
                    #     frame=(pre_frame_start)
                    # )
                    # ob.collision.damping_factor = damping_collision_on
                    # ob.keyframe_insert(
                    #     data_path="collision.damping_factor",
                    #     frame=(pre_frame_start)
                    # )

                    # # start frame collision off:
                    # ob.collision.permeability = collision_off
                    # ob.keyframe_insert(
                    #     data_path="collision.permeability",
                    #     frame=(frame_start)
                    # )
                    # ob.collision.damping_factor = damping_collision_off
                    # ob.keyframe_insert(
                    #     data_path="collision.damping_factor",
                    #     frame=(frame_start)
                    # )

                    # # pre end frame collision off:
                    # ob.collision.permeability = collision_off
                    # ob.keyframe_insert(
                    #     data_path="collision.permeability",
                    #     frame=(pre_frame_end)
                    # )
                    # ob.collision.damping_factor = damping_collision_off
                    # ob.keyframe_insert(
                    #     data_path="collision.damping_factor",
                    #     frame=(pre_frame_end)
                    # )

                    # # end frame collision on:
                    # ob.collision.permeability = collision_on
                    # ob.keyframe_insert(
                    #     data_path="collision.permeability",
                    #     frame=(frame_end)
                    # )
                    # ob.collision.damping_factor = damping_collision_on
                    # ob.keyframe_insert(
                    #     data_path="collision.damping_factor",
                    #     frame=(frame_end)
                    # )

    def disable_dynamic_rotation(self, inner_objects: List[Object]) -> None:
        # no seteo la ui para luego poder hacer restore en el remove
        # context.scene.rbdlab.particles.debris.use_dynamic_rotation = False
        # context.scene.rbdlab.particles.dust.use_dynamic_rotation = False
        if len(inner_objects) > 0:
            for ob in inner_objects:
                for ps in ob.particle_systems:
                    settings = ps.settings
                    if hasattr(settings, "use_dynamic_rotation"):
                        settings.use_dynamic_rotation = False

    def remove_rbd_to_the_selected_ob(self, context):
        # para impedir el Dependency cycle detected:
        # hay q quitar tambien los rbd a los childs o ponerlos animated...
        if len(context.selected_objects) > 0:
            set_active_object(context, context.selected_objects[0])
            bpy.ops.rigidbody.objects_remove()
        else:
            print("[remove_rbd_to_the_selected_ob]: No objects selected!")

    def store_rbd_info_in_ob(self, ob) -> None:
        if ob.rigid_body is not None:
            ob[RBDLabNaming.RBD_TYPE] = ob.rigid_body.type
            ob[RBDLabNaming.RBD_MASS] = ob.rigid_body.mass
            ob[RBDLabNaming.RBD_ENABLED] = ob.rigid_body.enabled
            ob[RBDLabNaming.RBD_KINEMATIC] = ob.rigid_body.kinematic
            ob[RBDLabNaming.RBD_SHAPE] = ob.rigid_body.collision_shape

    def bav_colors_acction(self, ob):
        if RBDLabNaming.CHUNK_EXTRACTED not in ob:
            color = ob.color_stack.get_first_color()
            if color:
                ob.color = color

    def bake_action_visual_keying(self, context, rbdlab, objects):
        start = datetime.now()
        fstart = rbdlab.bake.bake_action_start
        fend = rbdlab.bake.bake_action_end
        steps = rbdlab.bake.frame_step

        for ob in objects:

            if RBDLabNaming.BAKED_ACTION in ob:
                continue

            ob[RBDLabNaming.BAKED_ACTION] = True

            if RBDLabNaming.BAKED_ACTION not in rbdlab.filtered_target_collection:
                rbdlab.filtered_target_collection[RBDLabNaming.BAKED_ACTION] = True

            if ob.rigid_body is None:
                continue
            if RBDLabNaming.GROUND == ob.name:
                continue
            if RBDLabNaming.SUFIX_BBOX in ob.name:
                continue

            # self.bav_colors_acction(ob)

            # store info in ob:
            # cuando les borraba los rbd para poder luego restaurarlos:
            # self.store_rbd_info_in_ob(obj)

            ob.select_set(True)

            # guardo su active action para poder restaurarlo en el rm bake
            if ob.animation_data is not None:
                ob[RBDLabNaming.ACTIVE_ACTION] = ob.animation_data.action
            else:
                ob[RBDLabNaming.ACTIVE_ACTION] = None

        if len(context.selected_objects) > 0:
            bpy.ops.nla.bake(
                frame_start=fstart,
                frame_end=fend,
                step=steps,
                only_selected=True,
                visual_keying=True,
                clear_constraints=False,
                clear_parents=rbdlab.collision.use_clear_parents,
                use_current_action=False,
                clean_curves=False,
                bake_types={'OBJECT'}
            )

            # for ob in context.selected_objects:
            #     ob.rigid_body.kinematic = True

        # por ahora vamos a permitir que de el error de Dependency cycle detected
        # self.remove_rbd_to_the_selected_ob(context)

        # deselect_all_objects(context)
        # for ob in objects:
        #     # intentando evitar los problemas de dependency cycles

        #     childrens = get_array_data_from_ob(RBDLabNaming.COMPOUND_CHILDS, ob)
        #     if childrens == False:
        #         continue

        #     for ob_name in childrens:

        #         if ob_name in context.view_layer.objects:
        #             ob = context.view_layer.objects.get(ob_name)

        #         if ob is None:
        #             continue

        #         if RBDLabNaming.CHUNK_EXTRACTED in ob:
        #             continue

        #         ob.select_set(True)
        #         self.store_rbd_info_in_ob(ob)

        # self.remove_rbd_to_the_selected_ob(context)

        print("[Baking for particle collisions] End: " + str(datetime.now() - start))

    def sbc_colors_acction(self, ob, color_p_collision):
        ob.color_stack.add_color(color_p_collision)
        ob.color = color_p_collision

    def set_basic_collisions(self, context, rbdlab, objects):
        if objects:

            deselect_all_objects(context)
            # addon_preferences = RBDLabPreferences.get_prefs(context)
            # color_p_collision = list(addon_preferences.col_p_collision)

            {ob.select_set(True) for ob in objects}

            # le agrego la collision:
            active_object = objects[0]
            set_active_object(context, active_object)
            bpy.ops.object.modifier_add(type='COLLISION')

            collision_mod = active_object.modifiers[-1]
            collision_mod.name = RBDLabNaming.COLLISION_MOD

            # se los copiamos al resto:
            copy_modifier_by_name_from_active_to_selected(context, [RBDLabNaming.COLLISION_MOD])
            # seteo los settings porque copiando el modifier no se los lleva...

            for ob in objects:

                # self.sbc_colors_acction(ob, color_p_collision)
                
                if ob is None:
                    continue

                if ob.collision is None:
                    continue

                ob.collision.damping_factor = rbdlab.collision.get_default_properties("damping_factor")
                ob.collision.friction_factor = rbdlab.collision.get_default_properties("friction_factor")
                ob.collision.permeability = rbdlab.collision.get_default_properties("permeability")

                if RBDLabNaming.CHUNK_EXTRACTED not in ob:
                    ob.collision.permeability = 0
                    continue
                
                # con los nuevos motions:
                # if len(ob.rbdlab.motions) <= 0:
                #     ob.collision.permeability = collision_on

                # for motion in ob.rbdlab.motions:
                #     frame_start = motion.range[0]
                #     frame_end = motion.range[1]
                #     self.inser_keyframes(context, rbdlab, ob, frame_start, frame_end)

                self.inser_keyframes(context, rbdlab, ob)


    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                # Si existe domain, por rendimiento primero se desactiva:
                domain = self.check_if_exist_domain(context)
                if domain:
                    if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                        domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = False

                # por rendimiento desactivo si hay previos colliders
                all_ob_in_scene_with_collision = [
                    ob for ob in context.scene.objects
                    if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.COLLISION_MOD in ob.modifiers]
                if len(all_ob_in_scene_with_collision) > 0:
                    for ob in all_ob_in_scene_with_collision:
                        ob.collision.use = False

                if context.scene.frame_current != context.scene.frame_start:
                    context.scene.frame_set(context.scene.frame_start)

                if RBDLabNaming.PART_COLLISION not in rbdlab.filtered_target_collection:

                    if self.collision_type == 'SELECTION':

                        if len(context.selected_objects) == 0:
                            self.report({'WARNING'}, "No Selected objects!")
                            return {'CANCELLED'}

                        chunk_objects = [ob for ob in context.selected_objects
                                         if ob.type == 'MESH' and ob.visible_get()
                                         and ob.name in rbdlab.filtered_target_collection.objects
                                         and RBDLabNaming.INNER_EMISOR not in ob]

                    elif self.collision_type == 'COLLECTION':

                        chunk_objects = [ob for ob in rbdlab.filtered_target_collection.objects
                                         if ob.type == 'MESH' and ob.visible_get()
                                         and RBDLabNaming.INNER_EMISOR not in ob]

                    if chunk_objects:

                        # self.bake_action_visual_keying(context, rbdlab, rbdlab.filtered_target_collection.objects)
                        self.bake_action_visual_keying(context, rbdlab, chunk_objects)
                        self.set_basic_collisions(context, rbdlab, chunk_objects)

                        # # self.remove_rbd_to_the_selected_ob(context)

                        inner_objects = [ob for ob in rbdlab.filtered_target_collection.objects
                                         if ob.type == 'MESH' and ob.visible_get()
                                         and RBDLabNaming.INNER_EMISOR in ob]
                        if inner_objects:
                            self.disable_dynamic_rotation(inner_objects)

                        rbdlab.filtered_target_collection[RBDLabNaming.PART_COLLISION] = True

                    else:
                        self.report({'WARNING'}, "No valid objects in this " + self.collision_type.lower() + "!")
                        return {'CANCELLED'}

                    # por rendimiento primero se desactiva el domain.
                    # vuelvo a activar el domain:
                    if domain:
                        if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                            domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = True

                    # por rendimiento desactivo si hay previos colliders, ahora los restauro:
                    if len(all_ob_in_scene_with_collision) > 0:
                        for ob in all_ob_in_scene_with_collision:
                            ob.collision.use = True

                rbdlab.collision.through_offset = 0

                deselect_all_objects(context)
                self.report({'INFO'}, "It is highly recommended to save the scene now")
                return {'FINISHED'}
