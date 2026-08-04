import bpy
#阈值焊接
bpy.ops.mesh.remove_doubles('INVOKE_DEFAULT', threshold=0.0001, use_centroid=True, use_unselected=False, use_sharp_edge_from_normals=False)