import bpy
#选循环
bpy.ops.mesh.select_edge_loop_multi('INVOKE_DEFAULT', delimit_edge_loop={'OUTER_CORNERS', 'NGONS'})