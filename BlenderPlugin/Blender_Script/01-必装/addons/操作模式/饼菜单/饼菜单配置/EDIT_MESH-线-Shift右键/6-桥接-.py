import bpy
#桥接
bpy.ops.mesh.bridge_edge_loops('INVOKE_DEFAULT', type='SINGLE', use_merge=False, merge_factor=0.5, twist_offset=0, number_cuts=0, interpolation='PATH', smoothness=1.0, profile_shape_factor=0.0, profile_shape='SMOOTH')