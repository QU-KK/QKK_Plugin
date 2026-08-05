import bpy

from bpy.types import Operator
from ...Global.functions import (
    check_void_chunks,
)
from ...Global.basics import select_object, deselect_object
from ...addon.naming import RBDLabNaming

# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD
boolean_mod_name_up = RBDLabNaming.BOOLEAN_MOD_UP


class SELECT_OT_bad_chunks(Operator):
    bl_idname = "rbdlab.select_bad_chunks"
    bl_label = "RBDLab Select bad chunks"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        objects = None

        if not rbdlab.ui.select_bad_chunks_by_selection:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    coll_name = target_coll.name

                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    if coll_high_name in bpy.data.collections:
                        objects = bpy.data.collections[coll_high_name].objects
                    else:
                        objects = bpy.data.collections[coll_name].objects
        else:
            objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]
            # valid_chunks = [obj for obj in bpy.data.collections[coll_high_name].objects if obj.type == 'MESH' and obj.visible_get()]
            # valid_chunks = chunk_are_inside_original(valid_chunks)
            #
            # [select_object(context, obj) if check_void_chunks(obj) else deselect_object(obj) for obj in valid_chunks if obj.type == 'MESH' and obj.visible_get()]

        if objects:
            [select_object(context, obj) if check_void_chunks(context, obj) else deselect_object(obj)
             for obj in objects if obj.type == 'MESH' and obj.visible_get()]

        return {'FINISHED'}
