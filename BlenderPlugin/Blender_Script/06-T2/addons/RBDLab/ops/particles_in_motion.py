import bpy
from datetime import datetime

from bpy.types import Operator
from mathutils.bvhtree import BVHTree as tree
from ..Global.functions import append_attribute_to_obj
from ..addon.naming import RBDLabNaming


class ComputeVelocities(Operator):
    bl_idname = "rbdlab.compute_velocities"
    bl_label = "Detect Velocities"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Compute Velocities"

    @classmethod
    def poll(cls, context):
        # Si "filtered_target_collection" es nulo no se ejecutará el Operator y el botón saldrá desactivado.
        return context.scene.rbdlab.filtered_target_collection

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "You need to select a target collection (viewport's header)"
        return cls.bl_description

    def execute(self, context):
        start = datetime.now()
        print("Compute Velocities...")

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        ps_props = rbdlab.get_particles_properties()

        # start0 = datetime.now()

        valid_objects = [ob for ob in chunks if RBDLabNaming.SUFIX_BBOX not in ob.name and ob.name != RBDLabNaming.GROUND]

        if not valid_objects:
            print("ComputeVelocities: not valid objects!")
            return {'CANCELLED'}

        for obj in valid_objects:
            if RBDLabNaming.VELOCITIES in obj:
                del obj[RBDLabNaming.VELOCITIES]

        # print("CV get valid objs: " + str(datetime.now() - start0))

        # for obj in bpy.data.collections[coll_name].objects:
        #     if obj.type == 'MESH' and obj.visible_get():
        #         if obj.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in obj.name:
        #
        #             # reseteo si ya tuviera velocities:
        #             if RBDLabNaming.VELOCITIES in obj:
        #                 del obj[RBDLabNaming.VELOCITIES]
        #
        #             valid_objects.append(obj)

        initial_frame = context.scene.frame_current

        # esto era para el nuevo metodo descartado por velocidad:
        # if rbdlab.ui.visual_speed:
        #     frame_start = context.scene.frame_start
        #     frame_end = context.scene.frame_end
        # else:
        #     frame_start = ps_props.range_in
        #     frame_end = ps_props.range_out

        frame_start = ps_props.range_in
        frame_end = ps_props.range_out

        current_locations = []
        obj_velocities = {}

        # loop per frames
        # for f in range(frame_start-1, frame_end+1):

        # start1 = datetime.now()

        for f in range(frame_start, frame_end):
            context.scene.frame_set(f)
            previous_locations = current_locations.copy()
            current_locations = [obj.matrix_world.translation.copy() for obj in valid_objects]
            # [append_attribute_to_obj(obj, RBDLabNaming.VELOCITIES, str(f) + " " + str((current_locations[i-1]-previous_locations[i]).length)) for i, obj in enumerate(valid_objects) if len(previous_locations) > i]
            [append_attribute_to_obj(
                obj, RBDLabNaming.VELOCITIES, str(f) + " " + str((current_locations[i] - previous_locations[i]).length))
                for i, obj in enumerate(valid_objects) if len(previous_locations) > i]

            # loop per objects
            # i = 0
            # for obj in valid_objects:
            #
            #     current_locations.append(obj.matrix_world.translation.copy())
            #
            #     if len(previous_locations) > i:
            #         vel_vec = current_locations[i-1] - previous_locations[i]
            #         print("current_locations[i], previous_locations[i]", current_locations[i], previous_locations[i])
            #         vel = vel_vec.length
            #
            #         print("############# VEL:", vel)
            #
            #         if float(vel) > 0:
            #             append_attribute_to_obj(obj, RBDLabNaming.VELOCITIES, str(f) + " " + str(vel))
            #
            #     i += 1
        # print("CV loop per frame: " + str(datetime.now() - start1))

        context.scene.frame_set(initial_frame)
        rbdlab.filtered_target_collection[RBDLabNaming.CMPUTD_VELOCITIES] = True
        print("Compute Velocities End: " + str(datetime.now() - start))
        return {'FINISHED'}
