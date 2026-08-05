import bpy
import bmesh

from bpy.types import Operator
from ...Global.basics import select_object, set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming

# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD


class SELECT_OT_rm_void_chunks(Operator):
    bl_idname = "rbdlab.rm_void_chunks"
    bl_label = "RBDLab Remove void chunks"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name

                target_collections = bpy.data.collections[coll_name]

                deselect_all_objects(context)
                objects_to_delete = []

                for obj in target_collections.objects:

                    if obj.type != 'MESH' and not obj.visible_get():
                        continue

                    dg = context.evaluated_depsgraph_get()
                    obj = obj.evaluated_get(dg)
                    me = obj.to_mesh()
                    bm = bmesh.new()
                    bm.from_mesh(me)

                    # Allow indexed access for vertices and edges
                    # bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()

                    # deteccion chunks invisibles parcial o completamente:
                    if len(me.vertices) <= 2:
                        obj.to_mesh_clear()
                        bm.clear()
                        objects_to_delete.append(obj)

                if objects_to_delete:
                    for obj in objects_to_delete:
                        select_object(context, obj)

                if context.selected_objects:
                    set_active_object(context, context.selected_objects[0])
                    bpy.ops.object.delete(use_global=False)

                print("Removed " + str(len(objects_to_delete)) + " void chunks")

        return {'FINISHED'}
