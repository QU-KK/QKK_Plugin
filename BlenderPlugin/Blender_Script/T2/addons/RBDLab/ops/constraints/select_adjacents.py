import bpy
from bpy.types import Operator
from datetime import datetime
from ...Global.get_common_vars import get_common_vars
from ...ops.constraints.detect import recalculate_neighbors_for_adjacents


class RBDLAB_OT_select_adjacents_neighbours(Operator):
    bl_idname = "rbdlab.select_adjacents_neighbours"
    bl_label = "Select Adjacents Neigbours"
    bl_description = "Select Adjacents Neigbours"

    def execute(self, context):
        start = datetime.now()

        rbdlab_const = get_common_vars(context, get_constraints=True)
        src_collections = rbdlab_const.get_selected_work_group_collections

        chunks = [ob for coll in src_collections for ob in coll.objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]

        if not chunks: 
            return {'CANCELLED'}
        
        # por si el usuario cambio algo, se recomputan solo si cambio algo:
        recalculate_neighbors_for_adjacents(context)
        #---------------------------------------------------------------------------

        bpy.ops.object.select_all(action='DESELECT')
        selected_objects = set()

        # def get_neighbors(chunk):            
        #     return chunk.neighbor_chunks.get_neighbors(use_cluster=False)

        ob1_and_froms = { ob1 : ob1.get("rbdlab_from") for ob1 in chunks }
        for ob1, ob1_from in ob1_and_froms.items(): 
            
            for ob2 in chunks:
                
                if ob1 == ob2: 
                    continue

                if ob2 in selected_objects:
                    continue

                if ob1_from == ob2.get("rbdlab_from"):
                    continue

                # Utilizando los vecinos guardados:
                for neighbor in ob1.neighbor_chunks.chunks: 
                    
                    if neighbor.object != ob2:
                        continue

                    # ob1 es vecino de ob2:
                    selected_objects.add(ob2)

        # Finalmente los selecciono:
        [ob.select_set(True) for ob in selected_objects]
        
        print("rbdlab.select_adjacents_neighbours End: " + str(datetime.now() - start))
        return {'FINISHED'}