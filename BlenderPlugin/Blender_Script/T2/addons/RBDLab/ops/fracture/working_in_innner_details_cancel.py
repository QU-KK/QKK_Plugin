import bpy

from bpy.types import Operator
from ...Global.functions import (
    unhide_collection_in_viewport,
    remove_collection_by_name
)
from ...Global.basics import deselect_all_objects
from ...addon.naming import RBDLabNaming

# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD


class RBDLAB_OT_working_in_innner_detals_cancel(Operator):
    bl_idname = "rbdlab.working_in_inner_details_cancel"
    bl_label = "Cancell Working in inner details"
    bl_description = "Cancel Workin in inner details"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        # if rbdlab.filtered_target_collection:
        #     if rbdlab.filtered_target_collection.name:
        #         coll_name = rbdlab.filtered_target_collection.name
        #         if coll_name:

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name

                coll_high_name = None

                rbdlab.filtered_target_collection["fracture_applied"] = 0
                # if "fracture_applied" in rbdlab.filtered_target_collection:
                #     del rbdlab.filtered_target_collection["fracture_applied"]

                rbdlab.working_in_inner_details = False

                rbdlab.ui.show_mesh_visualization_settings = False
                rbdlab.scatter_working = False
                rbdlab.current_using_cell_fracture = True

                if coll_name.endswith(RBDLabNaming.SUFIX_LOW):
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)

                if coll_high_name in bpy.data.collections:
                    remove_collection_by_name(context, coll_high_name, True)
                unhide_collection_in_viewport(context, coll_name)

                if "use_highs" in bpy.data.collections[coll_name]:
                    del bpy.data.collections[coll_name]["use_highs"]

                for obj in bpy.data.collections[coll_name].objects:
                    if "rbdlab_have_high" in obj:
                        del obj["rbdlab_have_high"]

                # rbdlab.filtered_target_collection = bpy.data.collections[coll_name]
                deselect_all_objects(context)
        return {'FINISHED'}
