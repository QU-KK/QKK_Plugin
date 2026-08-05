from bpy.types import Operator
from datetime import datetime
from bpy.props import BoolProperty


class RBDLAB_OT_select_debug_neighbours(Operator):
    bl_idname = "rbdlab.select_debug_neighbours"
    bl_label = "Select/Increase Neigbours"
    bl_description = "Select/Increase Neigbours from active chunk"
    
    incremental: BoolProperty(default=False)

    def execute(self, context):
        start = datetime.now()

        if self.incremental:
            objects = [ob for ob in context.selected_objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]
        else:
            objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' and "rbdlab_from" in context.active_object and context.active_object.visible_get() and context.active_object.name in context.view_layer.objects else []
                
        if objects:

            for ob in objects:

                for neighbor in ob.neighbor_chunks.chunks:
                    if neighbor.object.select_get():
                        continue  
                    neighbor.object.select_set(True)

            print("rbdlab.select_debug_neighbours End: " + str(datetime.now() - start))

        return {'FINISHED'}


class RBDLAB_OT_clear_debug_neighbours(Operator):
    bl_idname = "rbdlab.clear_debug_neighbours"
    bl_label = "Clear Debug Neigbours"
    bl_description = "Clear Debug Neigbours from selected chunks"

    def execute(self, context):
        for ob in context.selected_objects:
            for k in list(ob.keys()):
                if k.startswith('neigh'):
                    del ob[k]
        return {'FINISHED'}
