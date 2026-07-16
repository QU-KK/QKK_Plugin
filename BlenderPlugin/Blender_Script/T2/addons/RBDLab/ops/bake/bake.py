import bpy
import re
# from datetime import datetime
from bpy.types import Operator, Area
from bpy.props import BoolProperty
# from ...Global.functions import set_active_object
from ...Global.get_common_vars import get_common_vars


class BAKE_OT_current_to_cache(Operator):
    bl_idname = "rbdlab.bake_current_to_cache"
    bl_label = "Bake current to cache"
    bl_description = "Bake current to cache"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        rbw = scene.rigidbody_world
        msg_cache_status = rbw.point_cache.info
        match = re.match("(^[0-9]*)\s", msg_cache_status)

        if match:
            target_frame = int(match.group(1))
            # context.scene.frame_end = target_frame
            rbw = scene.rigidbody_world
            rbw.point_cache.frame_end = target_frame

        bpy.ops.ptcache.bake_from_cache()
        return {'FINISHED'}


'''
class BAKE_OT_transfer_to_frame_end(Operator):
    bl_idname = "rbdlab.bake_transefer_to_frame_end"
    bl_label = "Ttransfer Frame End"
    bl_description = "Transfer Frame End, in scene and bake to keyframes an particles ends"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        scn.frame_end = scn.rigidbody_world.point_cache.frame_end
        rbdlab.bk_to_kf_end = scn.rigidbody_world.point_cache.frame_end
        rbdlab.particles.debris.range_out = scn.rigidbody_world.point_cache.frame_end
        rbdlab.particles.dust.range_out = scn.rigidbody_world.point_cache.frame_end
        rbdlab.particles.smoke.range_out = scn.rigidbody_world.point_cache.frame_end
        rbdlab.bake.bake_action_end = scn.rigidbody_world.point_cache.frame_end

        return {'FINISHED'}
'''


# class BAKE_OT_bake_curren_particles(Operator):
#     bl_idname = "rbdlab.bake_current_particles_cache"
#     bl_label = "Bake current particles cache"
#     bl_description = "Free all paricles cache"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self, context):
#         # tarda demasiado no consigo optimizarlo más, es inviable

#         start = datetime.now()

#         scene = context.scene
#         rbdlab = scene.rbdlab
#         p_type = rbdlab.ui.selected_particle_type

#         bpy.ops.object.select_all(action='DESELECT')

#         objects_to_work = [ob for ob in rbdlab.filtered_target_collection.objects
#                            if ob.type == 'MESH' and len(ob.particle_systems) > 0]

#         data_pairs = {}
#         for ob in objects_to_work:
#             data_pairs[ob] = [psys for psys in ob.particle_systems if p_type in psys.name]

#         ob_override = {}
#         for ob, psys_arr in data_pairs.items():
#             for psys in psys_arr:
#                 if not psys.point_cache.is_baked:
#                     ob_override[ob] = {"scene": scene, "active_object": ob, "point_cache": psys.point_cache}

#         # print(ob_override)
#         for override in ob_override.values():
#             bpy.ops.ptcache.bake(override, bake=True)

#         print("current_particles_cache End: " + str(datetime.now() - start))
#         return {'FINISHED'}


class BAKE_OT_free_bake_all_particles(Operator):
    bl_idname = "rbdlab.bake_free_all_particles_cache"
    bl_label = "Free all particles cache"
    bl_description = "Free all paricles cache"
    bl_options = {'REGISTER', 'UNDO'}

    by_type: BoolProperty(default=False)

    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)
        
        tcoll = tcoll_list.active
        if tcoll:

            p_type = rbdlab.ui.selected_particle_type

            bpy.ops.object.select_all(action='DESELECT')

            ob_to_work = [ob for ob in tcoll.objects if ob.type == 'MESH' or len(ob.particle_systems) > 0]

            for ob in ob_to_work:

                for psys in ob.particle_systems:
                    cache = psys.point_cache

                    if self.by_type:
                        if p_type not in psys.name:
                            continue

                    # previous_active = ob.particle_systems.active_index
                    if cache.is_baked is True:
                        # set_active_object(context, ob)
                        # ob.particle_systems.active_index = i
                        # ob.particle_systems.active_index = previous_active
                        # sobreescribir el contexto:
                        with context.temp_override(scn=scn, active_object=ob, point_cache=cache):
                            bpy.ops.ptcache.free_bake()


        return {'FINISHED'}
