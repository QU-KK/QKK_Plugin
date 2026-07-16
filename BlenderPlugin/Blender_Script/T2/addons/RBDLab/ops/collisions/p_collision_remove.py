import bpy

from ...Global.basics import select_object, set_active_object, deselect_all_objects
# from ...addon.paths import RBDLabPreferences
from bpy.types import Operator, Object
from ...addon.naming import RBDLabNaming


class RBDLAB_OT_p_collisions_remove(Operator):
    bl_idname = "rbdlab.p_collision_remove"
    bl_label = "Remove Particle Collision"

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Remove collision"

    def restore_dynamic_rotation(self, coll_name: str, context=bpy.context) -> None:
        objects = [ob for ob in bpy.data.collections[coll_name].objects if ob.type ==
                   'MESH' and ob.visible_get() and RBDLabNaming.INNER_EMISOR in ob]
        rbdlab = context.scene.rbdlab

        if objects:
            for ob in objects:
                for ps in ob.particle_systems:
                    ps_props = None
                    if "debris" in ps.name:
                        ps_props = rbdlab.get_particles_properties("debris")
                    if "dust" in ps.name:
                        ps_props = rbdlab.get_particles_properties("dust")
                    if ps_props:
                        settings = ps.settings
                        if hasattr(settings, "use_dynamic_rotation"):
                            settings.use_dynamic_rotation = ps_props.use_dynamic_rotation

    def rm_c_t_ob_colors_acction(self, ob, col_p_collision):
        ob.color_stack.rm_color(col_p_collision)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color

    def remove_collision_to_objects(self, objects: list, context=bpy.context) -> None:
        if objects:

            # addon_preferences = RBDLabPreferences.get_prefs(context)
            # col_p_collision = list(addon_preferences.col_p_collision)

            deselect_all_objects(context)
            for ob in objects:
                # self.rm_c_t_ob_colors_acction(ob, col_p_collision)
                select_object(context, ob)

            set_active_object(context, context.selected_objects[0])
            bpy.ops.object.convert(target='MESH')
        else:
            print("update_objects: no objects received!")

    # def remove_bake_action_to_objects(self, valid_objects: list[Object]) -> None:
    #     for ob in valid_objects:

    #         if ob.animation_data is None:
    #             continue

    #         if ob.animation_data.action is None:
    #             continue

    #         bpy.data.actions.remove(ob.animation_data.action, do_unlink=True)

    #         if RBDLabNaming.BAKED_ACTION in rbdlab.filtered_target_collection:
    #             del rbdlab.filtered_target_collection[RBDLabNaming.BAKED_ACTION]

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if context.scene.frame_current != context.scene.frame_start:
                    context.scene.frame_set(context.scene.frame_start)

                if RBDLabNaming.PART_COLLISION in rbdlab.filtered_target_collection:

                    valid_objects = [ob for ob in rbdlab.filtered_target_collection.objects
                                     if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.INNER_EMISOR
                                     not in ob and RBDLabNaming.INNER_EMISOR not in ob]

                    if valid_objects:

                        self.remove_collision_to_objects(valid_objects, context)
                        self.restore_dynamic_rotation(coll_name, context)

                        # remove keyframes:
                        if valid_objects:
                            all_fcurves = [ob.animation_data.action.fcurves for ob in valid_objects
                                           if ob.animation_data and ob.animation_data.action]
                            for fcurves in all_fcurves:
                                damping = fcurves.find("collision.damping_factor")
                                permeability = fcurves.find("collision.permeability")
                                if damping:
                                    fcurves.remove(damping)
                                if permeability:
                                    fcurves.remove(permeability)

                            # if not rbdlab.ui.preserve_bake_action:
                            #     self.remove_bake_action_to_objects(valid_objects)

                    else:
                        self.report({'WARNING'}, "No valid objects in this collection!")
                        return {'CANCELLED'}

                    del rbdlab.filtered_target_collection[RBDLabNaming.PART_COLLISION]

        deselect_all_objects(context)

        if context.scene.frame_current != context.scene.frame_start:
            context.scene.frame_set(context.scene.frame_start)

        return {'FINISHED'}
