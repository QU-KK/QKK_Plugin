import bpy
from bpy.types import Operator
from ...addon.naming import RBDLabNaming


class ACTIVATORS_OT_explode_done(Operator):
    bl_idname = "rbdlab.act_explode_done"
    bl_label = "Explode Done"
    bl_description = "Save/Set the Amount to be used with Preview and Record buttons"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE in obj]
                if len(valid_objects) > 0:

                    for obj in valid_objects:
                        if obj.matrix_world.translation != obj[RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE]:
                            obj[RBDLabNaming.ACTIVATORS_EXPLODED_DEST] = obj.matrix_world.translation

                # if "Activators_explode_centroid" in context.scene.objects:
                #     objs = bpy.data.objects
                #     objs.remove(objs["Activators_explode_centroid"], do_unlink=True, do_id_user=True)

                if RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in rbdlab.filtered_target_collection:
                    rbdlab.filtered_target_collection[RBDLabNaming.ACTIVATORS_EXPLODE_DONE] = True

                rbdlab.activators.activators_show_explode_amount_feedback = str(rbdlab.activators.force_explode_amount)

                rbdlab.activators.force_explode_amount = 0

        return {'FINISHED'}
