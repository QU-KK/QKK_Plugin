import bpy
#有限融并
bpy.ops.mesh.dissolve_limited('INVOKE_DEFAULT', angle_limit=5.0)