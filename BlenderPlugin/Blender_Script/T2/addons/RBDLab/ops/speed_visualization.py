import bpy
from datetime import datetime
from bpy.types import Operator


def get_color_from_gradient(vel):
    if vel == 0.0:
        color = (0.0, 0.0, 1.0, 1.0)
    elif vel == 0.5:
        color = (0.0, 1.0, 0.0, 1.0)
    elif vel == 1.0:
        color = (1.0, 0.0, 0.0, 1.0)
    elif vel < 0.5:
        color = (0.0, (2 * vel), (2 * (0.5 - vel)), 1.0)
    elif vel > 0.5:
        color = ((2 * (vel - 0.5)), (2 * (1 - vel)), 0.0, 1.0)

    if color:
        return color


class VISUAL_OT_speed(Operator):
    bl_idname = "rbdlab.visual_speed"
    bl_label = "Visual Speed"
    bl_description = "To be able to visualize the velocities of rigid bodies"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def execute(self, context):
        start = datetime.now()
        rbdlab = context.scene.rbdlab
        rbdlab.ui.visual_speed = True
        print("Compute Speed Visualization...")

        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:

            valid_objects = [obj for obj in bpy.data.collections[coll_name].objects
                             if obj.type == 'MESH' and obj.visible_get()]
            if valid_objects:

                ###########################################################################################
                # nuevo metodo usando las velocidades que se guardan en los chunks:
                # descartado por ser mas lento y menos preciso.
                ###########################################################################################
                # all_velocities = []
                #
                # have_velocities = [obj for obj in valid_objects if RBDLabNaming.VELOCITIES in obj]
                # # if not have_velocities:
                # #     bpy.ops.rbdlab.compute_velocities()
                # # las velocidades computadas por las particulas pueden estar en un rango x que no nos interesa
                # # por eso las computo si o si que no tardan tanto:
                # bpy.ops.rbdlab.compute_velocities()
                #
                # n = 0
                # for obj in have_velocities:
                #     v_data = obj[RBDLabNaming.VELOCITIES].split()
                #     a_frames = [int(v_data[i]) for i in range(len(v_data)) if i % 2 == 0]
                #     a_velocities = [float(v_data[i]) for i in range(len(v_data)) if i % 2 != 0]
                #     [all_velocities.append(vel) for vel in a_velocities]
                #     colors = [get_color_from_gradient(a_velocities[i] / max(all_velocities)) for i in range(len(a_frames))]
                #     [(setattr(obj, "color", colors[i]), obj.keyframe_insert(data_path="color", frame=a_frames[i])) for i in range(len(a_frames))]
                #     n += 1

                sf = context.scene.frame_start
                ef = context.scene.frame_end
                current_locations = []
                all_velocities = []
                obj_velocities = {}

                # loop per frames
                for f in range(sf - 1, ef + 1):
                    context.scene.frame_set(f)

                    previous_locations = current_locations.copy()
                    current_locations = []

                    # loop per objects
                    for i, obj in enumerate(valid_objects):

                        current_locations.append(obj.matrix_world.translation.copy())

                        if len(previous_locations) > i:
                            vel_vec = current_locations[i] - previous_locations[i]
                            vel = vel_vec.length

                            if obj.name not in obj_velocities:
                                obj_velocities[obj.name] = [vel]
                            else:
                                obj_velocities[obj.name].append(vel)

                            all_velocities.append(vel)

                glob_max_vel = max(all_velocities)

                # loop per objects
                for f in range(ef):
                    for obj in valid_objects:
                        if glob_max_vel > 0:
                            obj.color = get_color_from_gradient(obj_velocities[obj.name][f]/glob_max_vel)
                            obj.keyframe_insert(data_path="color", frame=f)

                if glob_max_vel == 0:
                    self.report({'WARNING'}, "No motion detected!")
                    bpy.ops.rbdlab.visual_speed_remove()

        context.scene.frame_set(context.scene.frame_start)
        print("Speed Visualization End: " + str(datetime.now() - start))
        return {'FINISHED'}


class VISUAL_OT_speed_remove(Operator):
    bl_idname = "rbdlab.visual_speed_remove"
    bl_label = "Visual Speed Remove"
    bl_description = "Visual Speed Remove"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def execute(self, context):
        start = datetime.now()
        rbdlab = context.scene.rbdlab
        print("Remove Speed Visualization start")

        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:

            valid_objects = [obj for obj in bpy.data.collections[coll_name].objects
                             if obj.type == 'MESH' and obj.visible_get()]

            frame_end = context.scene.frame_end

            for f in range(frame_end):
                for obj in valid_objects:

                    # remove keyframes in color:
                    ad = obj.animation_data
                    if ad:
                        action = ad.action
                        if action:
                            fcurves = [fc for fc in action.fcurves if fc.data_path.startswith("color")]
                            # remove fcurves
                            while (fcurves):
                                fc = fcurves.pop()
                                action.fcurves.remove(fc)

                    color = obj.color_stack.get_last_color()
                    if color:
                        obj.color = color

        context.scene.frame_set(context.scene.frame_start)
        print("Remove Speed Visualization End: " + str(datetime.now() - start))
        rbdlab.ui.visual_speed = False
        return {'FINISHED'}
