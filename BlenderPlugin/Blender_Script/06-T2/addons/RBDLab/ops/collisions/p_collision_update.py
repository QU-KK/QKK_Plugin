import bpy
from ...Global.basics import deselect_all_objects
from bpy.types import Operator
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming


class RBDLAB_OT_p_collisions_update(Operator):
    bl_idname = "rbdlab.p_collision_update"
    bl_label = "Update Particle Collision"

    type: EnumProperty(name="Collision to",
                       items=(
                           ("Low", "Low", ""),
                           ("High", "High", ""),
                       ),
                       default="Low")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Create %s collision" % properties.type

    @staticmethod
    def update_objects(objects: list, context=bpy.context) -> None:
        if objects:
            rbdlab = context.scene.rbdlab
            for obj in objects:

                if not obj.collision:
                    continue

                obj.collision.permeability = rbdlab.collision.permeability
                obj.collision.stickiness = rbdlab.collision.stickiness
                obj.collision.use_particle_kill = rbdlab.collision.use_particle_kill
                obj.collision.damping_factor = rbdlab.collision.damping_factor
                obj.collision.damping_random = rbdlab.collision.damping_random
                obj.collision.friction_factor = rbdlab.collision.friction_factor
                obj.collision.friction_random = rbdlab.collision.friction_random

                ### update damping factor keyframes ####################################################
                if obj.animation_data is not None and obj.animation_data.action is not None:
                    action = obj.animation_data.action

                    for fcu in action.fcurves:
                        if "damping_factor" in fcu.data_path:

                            if "damping_factor" in fcu.data_path:
                                for kp in fcu.keyframe_points:
                                    # si el keyframe no esta en y 0 entonces le ponemos el nuevo valor:
                                    if kp.co.y != 0:
                                        kp.co.y = rbdlab.collision.damping_factor
                                        kp.handle_left.y = rbdlab.collision.damping_factor
                                        kp.handle_right.y = rbdlab.collision.damping_factor
                ########################################################################################

        else:
            print("update_objects: no objects received!")

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                scn.frame_set(scn.frame_start)

                if RBDLabNaming.PART_COLLISION in rbdlab.filtered_target_collection:
                    valid_objects_low = [obj for obj in bpy.data.collections[coll_name].objects
                                         if obj.type == 'MESH' and obj.visible_get()
                                         and RBDLabNaming.INNER_EMISOR not in obj]

                    if valid_objects_low:
                        self.update_objects(valid_objects_low, context)
                    else:
                        self.report({'WARNING'}, "No valid objects in this collection!")
                        return {'CANCELLED'}

        deselect_all_objects(context)
        return {'FINISHED'}
