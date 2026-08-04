import bpy

from bpy.types import Operator
from ...addon.naming import RBDLabNaming

# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD


class OCTREE_DEPTH_OT_uniform(Operator):
    bl_idname = "rbdlab.octree_deepth_uniform"
    bl_label = "Octree Depth Uniform"
    bl_description = "Uniform density of meshesh in Remesh modifier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:

                    coll_high_name = None

                    if coll_name.endswith(RBDLabNaming.SUFIX_LOW):
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)

                    if coll_high_name:
                        # pongo un valor entre 3 y 6 dependiendo de las dimensiones de cada chunk
                        # para intentar dejar mas homogeneo la densidad de malla

                        # dict with the oject and dimensions
                        object_dimensions = {}
                        data_set = []
                        # range_min = 3
                        # range_max = 6
                        range_min = rbdlab.range_min
                        range_max = rbdlab.range_max

                        if coll_high_name in bpy.data.collections:
                            for obj in bpy.data.collections[coll_high_name].objects:
                                object_dimensions[obj.name] = sum(list(obj.dimensions))
                        else:
                            for obj in bpy.data.collections[coll_name].objects:
                                object_dimensions[obj.name] = sum(list(obj.dimensions))

                        # los ordenamos por value de menor a mayor:
                        d = dict(sorted(object_dimensions.items(), key=lambda item: item[1]))

                        for v in d.values():
                            data_set.append(v)

                        # normalizo los numeros al rango entre 3 y 6:
                        normalized = [
                            range_min + (xi - min(data_set)) * (range_max - range_min) / (max(data_set) - min(data_set))
                            for xi in data_set]

                        # for i, obj in enumerate(reversed(d.keys())):
                        for i, key in enumerate(d.keys()):
                            obj = bpy.data.objects[key]
                            if RBDLabNaming.REMESH in obj.modifiers:
                                obj.modifiers[RBDLabNaming.REMESH].octree_depth = int(normalized[i])

        return {'FINISHED'}
